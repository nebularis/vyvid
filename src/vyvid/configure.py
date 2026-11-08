# SPDX-License-Identifier: MIT
"""Commands that edit the configuration: ``vyd domain add | remove | trust``, ``vyd project add | set | remove | scan`` and
``vyd family add | remove``.

Every command works on text. It finds the table it changes by its header lines, edits that span and leaves
the rest of the file as it was, comments and ordering included. tomlkit edits and renders the values inside a
span, but is not asked to write the whole file, since it moves a ``[[projects]]`` that sits after a
``[[domains]]`` to join the others. The result is held to two tests before anything is written. Parsed, it must
equal the old data with the intended change and nothing else, and loaded by the real loader it must raise no
problem. The user's configuration is the default target. ``--file`` targets the repository's vyvid.toml, read
through its own path, and refuses what a vyvid.toml may not set.
"""

from __future__ import annotations

import copy
import difflib
import os
import re
import shlex
import stat
import subprocess
import sys
import tempfile
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import tomlkit

from . import config as cf
from .anchors import Fences
from .config import Config, ConfigError, Scope
from .credentials import private_dir
from .registers import SEPARATOR_RE, DeclarationError, _cells, default_declarations, type_texts, types_for
from .resolve import layers, normalise_remote, project_file, remotes as git_remotes

# Project keys `project set` writes, by how the value is read. The rest of an entry has its own command or stays hand-edited.
SCALARS = {"docs": "path", "code": "path", "skill_additions": "path", "visibility": cf.VISIBILITIES, "docs_visibility": cf.VISIBILITIES,
           "skill_prefix": "text", "doc_share": "number"}
LISTS = {"domains": "name", "contract": "path", "skills": "path", "facets": "path", "register_types": "path", "vocabulary": "path",
         "skill_targets": "folder", "hook_clients": "client", "remote": "remote"}
ELSEWHERE = {"families": "vyd family add and vyd family remove", "moves": "hand-editing", "extractors": "hand-editing", "recipes": "hand-editing"}
# Keys whose change reaches what a client loads or runs, so a person at a terminal makes it.
GATED = ("skills", "skill_additions", "hook_clients", "skill_targets")
FILE_PATHS = ("docs", "contract", "skills", "facets", "register_types", "vocabulary", "skill_additions")
TOKEN = re.compile(r"^([a-z]+):(?!/)")
ID_RE = re.compile(r"^([A-Z][A-Z0-9]*)-\d+[a-z]?$")
LOOSE_ID_RE = re.compile(r"^([A-Z][A-Z0-9]*)-\d[\w.]*$")


class Refusal(Exception):
    """A request the command will not carry out, with every reason."""

    def __init__(self, *problems: str):
        super().__init__("\n".join(problems))
        self.problems = list(problems)


@dataclass(frozen=True)
class Target:
    path: Path
    project_file: bool


@dataclass
class Plan:
    """One edit: how it changes the lines and the data, and what is checked about the result."""

    edit: Callable[[list[str], dict], tuple[list[str], Callable[[dict], None]]]
    project: str | None = None  # the project whose families are checked after the edit
    types: dict[str, str] = field(default_factory=dict)  # family -> its type, which must be declared
    domains: tuple[str, ...] = ()  # domains this edit adds, none of which may be set aside
    gate: str = ""  # why a person at a terminal must run it, if one must
    notes: list[str] = field(default_factory=list)  # printed after a write


def target(file: bool) -> Target:
    if not file:
        return Target(cf.config_path(), False)
    if (existing := project_file(Path.cwd())) is not None:
        return Target(existing, True)
    done = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True)
    if done.returncode:
        raise Refusal(f"--file writes the {cf.PROJECT_FILE} of the repository you are in, and this folder is not in one")
    return Target(Path(cf.git_path(done.stdout)) / cf.PROJECT_FILE, True)


# -- rendering ---------------------------------------------------------------------------------------------

class Literal(str):
    """A string written between single quotes where it can be, as a pattern reads best."""


def _key(name: str) -> str:
    return tomlkit.key(name).as_string()


def _rhs(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, Literal):
        try:
            return tomlkit.string(str(value), literal=True).as_string()
        except Exception:
            return tomlkit.string(str(value)).as_string()
    if isinstance(value, str):
        return tomlkit.string(value).as_string()
    if isinstance(value, list):
        return "[" + ", ".join(_rhs(v) for v in value) + "]"
    return "{ " + ", ".join(f"{_key(k)} = {_rhs(v)}" for k, v in value.items()) + " }" if value else "{}"


def _item(value):
    return tomlkit.parse(f"v = {_rhs(value)}")["v"]


def _block(root: str, table: dict, array: bool = True) -> list[str]:
    return [f"[[{root}]]" if array else f"[{root}]", *(f"{_key(k)} = {_rhs(v)}" for k, v in table.items())]


# -- finding a table by its header ------------------------------------------------------------------------

@dataclass
class Section:
    start: int
    end: int  # the line after its last
    path: tuple[str, ...]
    array: bool


@dataclass
class Entry:
    head: Section
    subs: list[Section]
    end: int


def _header_lines(lines: list[str]) -> list[int]:
    """The lines that open a table, which is a line starting with ``[`` outside a multi-line string and an open array."""
    found, multi, depth = [], None, 0
    for number, line in enumerate(lines):
        if multi is None and depth == 0 and line.lstrip().startswith("["):
            found.append(number)
            continue
        at = 0
        while at < len(line):
            if multi:
                close = line.find(multi, at)
                if close < 0:
                    break
                at, multi = close + 3, None
                continue
            c = line[at]
            if c == "#":
                break
            if line.startswith(('"""', "'''"), at):
                multi, at = line[at:at + 3], at + 3
                continue
            if c in "\"'":
                at += 1
                while at < len(line) and line[at] != c:
                    at += 2 if c == '"' and line[at] == "\\" else 1
            elif c in "[{":
                depth += 1
            elif c in "]}":
                depth -= 1
            at += 1
    return found


def _path_of(line: str) -> tuple[tuple[str, ...], bool]:
    node, path = tomllib.loads(line), []
    while True:
        ((key, value),) = node.items()
        path.append(key)
        if isinstance(value, list) or not value:
            return tuple(path), line.lstrip().startswith("[[")
        node = value


def _sections(lines: list[str]) -> list[Section]:
    heads = _header_lines(lines)
    try:
        return [Section(h, heads[i + 1] if i + 1 < len(heads) else len(lines), *_path_of(lines[h])) for i, h in enumerate(heads)]
    except (tomllib.TOMLDecodeError, ValueError) as error:
        raise Refusal(f"a table header in this file cannot be read ({error}), so edit it by hand")


def _find(lines: list[str], data: dict, root: str, name: str | None, array: bool = True) -> Entry:
    """The entry named ``name`` of the ``[[root]]`` tables, or the ``[root]`` table, and the tables under it."""
    sections = _sections(lines)
    heads = [s for s in sections if s.path == (root,) and s.array == array]
    index = 0
    if array:
        items = data.get(root)
        if not isinstance(items, list) or len(items) != len(heads):
            raise Refusal(f"'{root}' in this file is not written as one [[{root}]] table per entry, so edit it by hand")
        index = [i.get("name") for i in items].index(name)
    elif not heads:
        raise Refusal(f"this file has no [{root}] table")
    subs = []
    for s in sections[sections.index(heads[index]) + 1:]:
        if s.path[0] != root or (s.array and s.path == (root,)):
            break
        subs.append(s)
    return Entry(heads[index], subs, subs[-1].end if subs else heads[index].end)


def _content_end(lines: list[str], start: int, end: int) -> int:
    """The line after the last line in ``start:end`` that holds a key, a value or a header, so comments after it stay below an insertion."""
    last = start
    for number in range(start, end):
        text = lines[number].strip()
        if text and not text.startswith("#"):
            last = number + 1
    return last


def _flat(lines: list[str], start: int, end: int, edit: Callable) -> list[str]:
    """Edit the keys in ``start:end``, which hold no table header, through tomlkit, and splice them back."""
    doc = tomlkit.parse("\n".join(lines[start:end]) + "\n" if end > start else "")
    edit(doc)
    out = tomlkit.dumps(doc).split("\n")
    while out and not out[-1]:
        out.pop()
    return [*lines[:start], *out, *lines[end:]]


def _region(lines: list[str], entry: Entry, sub: tuple[str, ...]) -> tuple[int, int] | None:
    """The lines holding the keys of the entry itself, or of its table at ``sub``, else None."""
    if not sub:
        stop = entry.subs[0].start if entry.subs else entry.head.end
        return entry.head.start + 1, _content_end(lines, entry.head.start + 1, stop)
    for s in entry.subs:
        if s.path == (*entry.head.path, *sub) and not s.array:
            return s.start + 1, _content_end(lines, s.start + 1, s.end)
    return None


def _set(lines: list[str], entry: Entry, sub: tuple[str, ...], key: str, value) -> list[str]:
    item = _item(value)
    if (region := _region(lines, entry, sub)) is not None:
        return _flat(lines, *region, lambda d: d.__setitem__(key, item))
    top = _region(lines, entry, ())
    if sub and sub[0] in tomlkit.parse("\n".join(lines[top[0]:top[1]]) + "\n"):
        return _flat(lines, *top, lambda d: d[sub[0]].__setitem__(key, item))
    at = _content_end(lines, entry.head.start, entry.end)
    header = ".".join(_key(k) for k in (*entry.head.path, *sub))
    return [*lines[:at], "", f"[{header}]", f"{_key(key)} = {_rhs(value)}", *lines[at:]]


def _delete(lines: list[str], entry: Entry, sub: tuple[str, ...], key: str) -> list[str]:
    """Remove ``key`` from the table at ``sub``, and that table too if it is left empty."""
    if (region := _region(lines, entry, sub)) is not None and key in (inside := tomlkit.parse("\n".join(lines[region[0]:region[1]]) + "\n")):
        if sub and len(inside) == 1:
            section = next(s for s in entry.subs if s.path == (*entry.head.path, *sub) and not s.array)
            return _cut(lines, section.start, section.end)
        return _flat(lines, *region, lambda d: d.__delitem__(key))
    top = _region(lines, entry, ())
    if sub and sub[0] in (doc := tomlkit.parse("\n".join(lines[top[0]:top[1]]) + "\n")) and key in doc[sub[0]]:
        def drop(d) -> None:
            del d[sub[0]][key]
            if not d[sub[0]]:
                del d[sub[0]]

        return _flat(lines, *top, drop)
    for s in entry.subs:
        if s.path[:len(entry.head.path) + len(sub) + 1] == (*entry.head.path, *sub, key):
            return _cut(lines, s.start, s.end)
    raise Refusal(f"'{key}' is not set there")


def _cut(lines: list[str], start: int, end: int) -> list[str]:
    """Remove a span with the comments directly above it, which are its own, and keep those directly above what follows."""
    while start > 0 and lines[start - 1].lstrip().startswith("#"):
        start -= 1
    if end < len(lines):
        while end > start and lines[end - 1].lstrip().startswith("#"):
            end -= 1
    out = [*lines[:start], *lines[end:]]
    if 0 < start < len(out) and not out[start - 1].strip() and not out[start].strip():
        del out[start]
    while out and not out[-1].strip():
        out.pop()
    return out


def _drop(data: dict, root: str, name: str) -> None:
    data[root].remove(next(x for x in data[root] if x.get("name") == name))
    if not data[root]:
        del data[root]


def _append(lines: list[str], block: list[str]) -> list[str]:
    return [*lines, *([""] if lines and lines[-1].strip() else []), *block]


# -- writing ----------------------------------------------------------------------------------------------

def _read(path: Path) -> str:
    try:
        return cf.read_toml_text(path)
    except FileNotFoundError:
        return ""


def _write(tg: Target, text: str) -> None:
    """Replace the file whole or not at all, keeping its mode. A new user configuration is owner-only."""
    real = Path(os.path.realpath(tg.path))
    existed = real.exists()
    mode = stat.S_IMODE(real.stat().st_mode) if existed else (0o644 if tg.project_file else 0o600)
    if not real.parent.exists():
        private_dir(real.parent)
    handle, name = tempfile.mkstemp(dir=real.parent, prefix=".vyd-", suffix=".tmp")
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as out:
            out.write(text)
        os.chmod(name, mode)
        os.replace(name, real)
    except BaseException:
        Path(name).unlink(missing_ok=True)
        raise


def _validate(tg: Target, text: str, plan: Plan) -> list[str]:
    """Every problem the real loader finds in the file as it would be."""
    scope = None
    if tg.project_file:
        table, problems = cf.read_project_file(tg.path, text)
        if problems:
            return problems
        try:
            config = cf.load()
        except ConfigError as error:
            return [f"the user's configuration at {cf.config_path()} cannot be used, so the project file cannot be checked:", *error.problems]
        scope, problems = cf.file_project(config, tg.path, table, tg.path.parent.resolve(), None)
        if scope is None:
            return problems
    else:
        try:
            config = cf.load(tg.path, text)
        except ConfigError as error:
            return error.problems
        scope = config.projects.get(plan.project) if plan.project else None
    problems = [f"domain '{d}' is set aside: {'; '.join(config.set_aside[d])}" for d in plan.domains if d in config.set_aside]
    if plan.types and scope is not None:
        try:
            known = types_for(layers(config, scope)).types
        except DeclarationError as error:
            return [*problems, *error.problems]
        problems += [f"family {f} has the type '{t}', which no register types of this project declare. Choose one of {', '.join(sorted(known))}"
                     for f, t in plan.types.items() if t not in known]
    return problems


def _fail(problems: list[str]) -> int:
    for problem in problems:
        print(f"vyd: {problem}", file=sys.stderr)
    return 1


def run(tg: Target, plan: Plan, dry_run: bool, person: Callable[[], bool]) -> int:
    """Apply a plan to its file: gate, edit, check, then show the change or write it."""
    old = _read(tg.path)
    try:
        data = tomllib.loads(old)
    except tomllib.TOMLDecodeError as error:
        return _fail([f"{tg.path} does not parse ({error})"])
    if plan.gate and not dry_run and not person():
        return _fail([f"{plan.gate}. A person must run this command, in a terminal"])
    try:
        lines, change = plan.edit(old.splitlines(), data)
        new = "\n".join(lines) + "\n"
        expected = copy.deepcopy(data)
        change(expected)
        if tomllib.loads(new) != expected:
            raise Refusal(f"the edit would change more of {tg.path} than it should, as its layout is unusual. Nothing was written. Edit it by hand")
    except Refusal as refusal:
        return _fail(refusal.problems)
    if problems := _validate(tg, new, plan):
        print(f"vyd: nothing written, since {tg.path} would not load cleanly:", file=sys.stderr)
        return _fail(problems)
    if new == old:
        print(f"nothing to change in {tg.path}")
        return 0
    print(f"{'would write' if dry_run else 'writing'} {tg.path}")
    for line in difflib.unified_diff(old.splitlines(), new.splitlines(), str(tg.path), "after", lineterm="", n=2):
        print(line)
    if dry_run:
        print("dry run, nothing written" + (f". {plan.gate}, so a person must run it for real, in a terminal" if plan.gate else ""))
        return 0
    _write(tg, new)
    print(f"wrote {tg.path}")
    if tg.project_file:
        print(f"{cf.PROJECT_FILE} changed, so any trust recorded for it lapses. A person runs vyd trust, in a terminal, in this repository, to restore it")
    for note in plan.notes:
        print(note)
    return 0


# -- values -----------------------------------------------------------------------------------------------

def place(value: str) -> str:
    """A path as the configuration keeps it: a token path as written, else absolute with ``~`` for the home folder."""
    if TOKEN.match(value) and not re.match(r"^[A-Za-z]:[\\/]", value):
        return value
    path = Path(os.path.abspath(Path(value).expanduser()))
    try:
        return "~" if path == Path.home() else "~/" + path.relative_to(Path.home()).as_posix()
    except ValueError:
        return path.as_posix()


def in_repository(value: str, root: Path, key: str) -> str:
    """A path for a vyvid.toml, which is committed. It stays in the repository as ``code:`` or ``docs:``, else it is refused."""
    if (m := TOKEN.match(value)) and m.group(1) in ("code", "docs"):
        return value
    path = Path(os.path.abspath(Path(value).expanduser()))
    if TOKEN.match(value) or not Path(os.path.realpath(path)).is_relative_to(Path(os.path.realpath(root))):
        raise Refusal(f"{key} '{value}' is outside the repository, and a {cf.PROJECT_FILE} is committed, so it belongs in the user's configuration. Leave out --file")
    return "code:" + path.relative_to(Path(os.path.abspath(root))).as_posix() if path != Path(os.path.abspath(root)) else "code:."


def _clean(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


def _users(entry: dict, domain: str) -> bool:
    return (domain in entry.get("domains", []) or domain in entry.get("uses", {}) or domain in entry.get("specialises", {})
            or any(m.get("to") == domain for m in entry.get("moves", []) if isinstance(m, dict)) or domain in entry.get("delegates", {}).values())


def _user_config() -> Config:
    try:
        return cf.load()
    except ConfigError as error:
        raise Refusal(f"the configuration at {cf.config_path()} cannot be used, so nothing is changed:", *error.problems)


def _raising(config: Config, names: list[str]) -> list[str]:
    """The domains among ``names`` that give more than knowledge, whose binding to a project widens what runs for it."""
    return [n for n in names if n in config.domains and config.domains[n].trust != "knowledge"]


# -- domains ----------------------------------------------------------------------------------------------

def domain_add(name: str, path: str | None, remote: str | None, trust: str, commit: str | None, visibility: str | None,
               file: bool, dry_run: bool, person: Callable[[], bool]) -> int:
    try:
        if file:
            raise Refusal(f"a domain is the user's own, so a {cf.PROJECT_FILE} cannot hold one. Leave out --file")
        if path is None and remote is None:
            raise Refusal("a domain needs --path, its folder, or --remote, the repository to clone it from")
        entry = {"name": name, **({"visibility": visibility} if visibility else {}), **({"path": place(path)} if path else {}),
                 **({"remote": remote} if remote else {}), "trust": trust, **({"commit": commit} if commit else {})}
        try:
            kb = tomllib.loads(_read(cf.config_path())).get("framework", {}).get("kb")
        except tomllib.TOMLDecodeError:
            kb = None  # run() reports a file that does not parse
        folder = Path(path).expanduser() if path else (Path(kb).expanduser() / "domains" / name if kb else None)
        notes = []
        if folder is not None and not folder.exists():
            notes.append(f"{folder} does not exist yet. " + (f"Clone it with: vyd kb clone {name}" if remote else f"Write it with: vyd domain new {name} --path {shlex.quote(str(folder))}"))
        plan = Plan(lambda lines, data: (_append(lines, _block("domains", entry)), lambda d: d.setdefault("domains", []).append(copy.deepcopy(entry))),
                    domains=(name,), notes=notes,
                    gate=f"trust {trust} gives the domain's rules, skills and recipes to every project that uses it" if trust != "knowledge" else "")
        return run(target(False), plan, dry_run, person)
    except Refusal as refusal:
        return _fail(refusal.problems)


def domain_remove(name: str, file: bool, dry_run: bool, person: Callable[[], bool]) -> int:
    try:
        if file:
            raise Refusal(f"a domain is the user's own, so a {cf.PROJECT_FILE} cannot hold one. Leave out --file")
        config = _user_config()
        if name not in config.domains and name not in config.set_aside:
            raise Refusal(f"domain '{name}' is not configured")
        users = [f"project '{n}'" for n, e in config.entries.items() if _users(e, name)]
        users += [f"project '{p.name}'" for p in config.projects.values() if name in p.domains and f"project '{p.name}'" not in users]
        users += [f"domain '{d.name}', which has it as a parent" for d in config.domains.values() if name in d.parents]
        if (file_at := project_file(Path.cwd())) is not None:
            table, _ = cf.read_project_file(file_at)
            if _users(table, name):
                users.append(f"project '{table.get('name')}', declared in {file_at}")
        if users:
            raise Refusal(f"domain '{name}' is not removed, since it is used by {', '.join(users)}. Change those first")
        folder = config.domains[name].path if name in config.domains else None

        def edit(lines: list[str], data: dict):
            entry = _find(lines, data, "domains", name)
            return _cut(lines, entry.head.start, entry.end), lambda d: _drop(d, "domains", name)

        notes = [f"left {folder} as it is. A remove never deletes a clone or a folder"] if folder else []
        return run(target(False), Plan(edit, notes=notes), dry_run, person)
    except Refusal as refusal:
        return _fail(refusal.problems)


TRUST_RANK = {"knowledge": 0, "reviewed": 1, "own": 2}  # what each gives: reviewed gives what own does, but only while the folder is at its commit


def _head(folder: Path | None) -> str | None:
    if folder is None or not folder.is_dir():
        return None
    done = subprocess.run(["git", "-C", str(folder), "rev-parse", "HEAD"], capture_output=True, text=True, encoding="utf-8", errors="replace")
    return done.stdout.strip() or None if done.returncode == 0 else None


def domain_trust(name: str, trust: str, commit: str | None, dry_run: bool, person: Callable[[], bool]) -> int:
    """Change the trust of a configured domain. Raising it, or moving a reviewed commit, needs a person. Lowering does not."""
    try:
        config = _user_config()
        if name in config.set_aside:
            raise Refusal(f"domain '{name}' is set aside ({'; '.join(config.set_aside[name])}), so its trust is not changed. Fix that first")
        if name not in config.domains:
            raise Refusal(f"domain {name!r} is not configured. The configured domains are {', '.join(sorted(config.domains)) or 'none'}")
        if trust not in cf.TRUSTS:
            raise Refusal(f"trust is '{trust}', not one of {', '.join(cf.TRUSTS)}")
        domain = config.domains[name]
        if trust == "reviewed" and commit is None:
            head = _head(domain.path)
            raise Refusal("trust reviewed needs --commit, the commit you read. Name it yourself, since it is the record of what you reviewed"
                          + (f". The folder's current head is {head}, which is help and never taken for you" if head else ""))
        if trust != "reviewed" and commit is not None:
            raise Refusal(f"--commit is for trust reviewed, and this is {trust}")
        if commit is not None and not cf.COMMIT_RE.fullmatch(commit):
            raise Refusal(f"--commit '{commit}' is not a commit of 7 to 64 hexadecimal characters")
        if (domain.trust, (domain.commit or "").lower()) == (trust, (commit or "").lower()):
            print(f"domain {name} already has trust {trust}" + (f" at {commit}" if commit else "") + ", so nothing is written")
            return 0
        raising = TRUST_RANK[trust] > TRUST_RANK[domain.trust] or (trust == "reviewed" == domain.trust)

        def edit(lines: list[str], data: dict):
            if name not in [d.get("name") for d in data.get("domains", []) if isinstance(d, dict)]:
                raise Refusal(f"domain '{name}' is not declared in {cf.config_path()}, so this command does not change it")
            entry = _find(lines, data, "domains", name)
            lines = _set(lines, entry, (), "trust", trust)
            if commit is not None:
                lines = _set(lines, _find(lines, data, "domains", name), (), "commit", commit)
            elif "commit" in next(d for d in data["domains"] if d.get("name") == name):
                lines = _delete(lines, _find(lines, data, "domains", name), (), "commit")

            def change(d: dict) -> None:
                row = next(x for x in d["domains"] if x.get("name") == name)
                row["trust"] = trust
                row.pop("commit", None)
                if commit is not None:
                    row["commit"] = commit

            return lines, change

        install = "run vyd install --project in a project that uses it to pick up its skills" + (
            ", and vyd install --client for the user's folder, since it is private" if domain.visibility == "private" else "")
        notes = {"own": f"domain {name} now gives its rules, skills and recipes to every project that uses it, so its skills will compose. {install[0].upper() + install[1:]}",
                 "reviewed": f"domain {name} now gives what own does while its folder is at commit {commit}, and knowledge alone at any other. "
                             f"Its skills will compose. {install[0].upper() + install[1:]}. After a pull moves it, read what changed and name the new commit with this command",
                 "knowledge": f"domain {name} now gives knowledge alone. A project already installed keeps the skills written for it until the next vyd install --project, which removes them"}
        plan = Plan(edit, notes=[notes[trust]],
                    gate=f"trust {trust}" + (f" at {commit}" if commit else "") + " gives the domain's rules, skills and recipes to every project that uses it" if raising else "")
        return run(target(False), plan, dry_run, person)
    except Refusal as refusal:
        return _fail(refusal.problems)


# -- projects ---------------------------------------------------------------------------------------------

def _checkout() -> Path | None:
    done = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True)
    return Path(cf.git_path(done.stdout)) if done.returncode == 0 else None


def project_add(name: str, code: str | None, docs: str | None, contracts: list[str], remotes: list[str], domains: list[str],
                visibility: str, file: bool, dry_run: bool, person: Callable[[], bool]) -> int:
    try:
        tg = target(file)
        config = _user_config()
        if not (cf.NAME_RE.match(name) and name != "general") or name in config.domains:
            raise Refusal(f"project '{name}': a project needs a unique lower-case name, distinct from every domain")
        if missing := [d for d in domains if d not in config.domains]:
            raise Refusal(*(f"project '{name}': domain '{d}' is not configured. Add it first with vyd domain add" for d in missing))
        entry: dict = {"name": name, "visibility": visibility}
        root = tg.path.parent if file else None
        if file:
            if code or remotes:
                raise Refusal(f"a {cf.PROJECT_FILE} may not set code or match, since the checkout is where it is read. Leave out --code and --remote, or leave out --file")
            if any(name == t.get("name") for t in [tomllib.loads(_read(tg.path)).get("project", {})]) or "project" in tomllib.loads(_read(tg.path)):
                raise Refusal(f"{tg.path} already declares a project")
            if docs:
                entry["docs"] = in_repository(docs, root, "--docs")
            if contracts:
                values = [in_repository(c, root, "--contract") for c in contracts]
                entry["contract"] = values[0] if len(values) == 1 else values
        else:
            checkout = Path(code).expanduser() if code else _checkout()
            if checkout is not None:
                entry["code"] = place(str(checkout))
                if not remotes:
                    remotes = git_remotes(checkout)
            if remotes:
                entry["match"] = {"remote": _clean([normalise_remote(r) for r in remotes])}
            if docs:
                entry["docs"] = place(docs)
            if contracts:
                values = [place(c) for c in contracts]
                entry["contract"] = values[0] if len(values) == 1 else values
        if domains:
            entry["domains"] = _clean(domains)
        raising = _raising(config, domains)
        gate = ("it binds " + ", ".join(raising) + ", which give more than knowledge, to a project, and what it gives runs there") if raising else ""

        def edit(lines: list[str], data: dict):
            if file:
                table = {k: v for k, v in entry.items()}
                return _append(lines, _block("project", table, array=False)), lambda d: d.__setitem__("project", copy.deepcopy(table))
            return _append(lines, _block("projects", entry)), lambda d: d.setdefault("projects", []).append(copy.deepcopy(entry))

        notes = []
        if not file and "code" not in entry:
            notes.append("no code folder was given and this folder is not a git checkout")
        return run(tg, Plan(edit, project=name, gate=gate, notes=notes), dry_run, person)
    except Refusal as refusal:
        return _fail(refusal.problems)


def _convert(key: str, values: list[str], file: bool, root: Path | None):
    kind = SCALARS.get(key) or LISTS[key]
    if key in SCALARS and len(values) != 1:
        raise Refusal(f"{key} takes one value")
    out: list = []
    for v in values:
        if isinstance(kind, tuple) and v not in kind:
            raise Refusal(f"{key} is one of {', '.join(kind)}, not '{v}'")
        if kind == "number":
            try:
                out.append(float(v))
            except ValueError:
                raise Refusal(f"{key} is a number from 0 to 1, not '{v}'")
        elif kind == "path":
            out.append(in_repository(v, root, key) if file and key in FILE_PATHS else place(v))
        elif kind == "remote":
            out.append(normalise_remote(v))
        else:
            out.append(v)
    return out if key in LISTS else out[0]


def project_set(name: str, key: str, values: list[str], file: bool, dry_run: bool, person: Callable[[], bool]) -> int:
    try:
        if key in ELSEWHERE:
            raise Refusal(f"{key} is changed by {ELSEWHERE[key]}, not by vyd project set")
        if key not in SCALARS and key not in LISTS:
            raise Refusal(f"'{key}' is not a key vyd project set writes. Choose one of {', '.join(sorted({*SCALARS, *LISTS}))}")
        tg = target(file)
        if file and (key in cf.PROJECT_REFUSED or key == "remote"):
            raise Refusal(f"a {cf.PROJECT_FILE} may not set {'match' if key == 'remote' else key}, which only the user's configuration may. Leave out --file")
        config = _user_config()
        value = _convert(key, values, file, tg.path.parent if file else None)
        if key == "domains":
            if missing := [d for d in value if d not in config.domains]:
                raise Refusal(*(f"domain '{d}' is not configured. Add it first with vyd domain add" for d in missing))
        gate = f"{key} reaches what a client loads or runs" if key in GATED else ""
        if key == "domains" and (raising := _raising(config, value)):
            gate = "it binds " + ", ".join(raising) + ", which give more than knowledge, to a project, and what it gives runs there"
        sub, leaf = (("match",), "remote") if key == "remote" else ((), key)

        def edit(lines: list[str], data: dict):
            if file:
                entry = _find(lines, data, "project", None, array=False)
            else:
                if name not in [p.get("name") for p in data.get("projects", [])]:
                    raise Refusal(f"project '{name}' is not in {tg.path}" + (". If a vyvid.toml declares it, use --file" if name in config.projects else ""))
                entry = _find(lines, data, "projects", name)

            def change(d: dict) -> None:
                item = d["project"] if file else next(p for p in d["projects"] if p.get("name") == name)
                (item.setdefault(sub[0], {}) if sub else item)[leaf] = copy.deepcopy(value)

            return _set(lines, entry, sub, leaf, value), change

        return run(tg, Plan(edit, project=name, gate=gate), dry_run, person)
    except Refusal as refusal:
        return _fail(refusal.problems)


def reads_pin(project: Scope, read: str, commit: str, dry_run: bool, person: Callable[[], bool]) -> int:
    """Write ``commit`` as the pin of ``read`` where the project declares it: its vyvid.toml, else the user's own entry."""
    try:
        file = project.file is not None and "reads" in project.file_keys
        tg = Target(project.file, True) if file else target(False)

        def edit(lines: list[str], data: dict):
            if not file and project.name not in [p.get("name") for p in data.get("projects", [])]:
                raise Refusal(f"project '{project.name}' declares its reads in neither a {cf.PROJECT_FILE} nor {tg.path}")
            entry = _find(lines, data, "project", None, array=False) if file else _find(lines, data, "projects", project.name)

            def change(d: dict) -> None:
                item = d["project"] if file else next(p for p in d["projects"] if p.get("name") == project.name)
                item["reads"][read]["commit"] = commit

            return _set(lines, entry, ("reads", read), "commit", commit), change

        return run(tg, Plan(edit, project=project.name, notes=["The index is rebuilt at the next question. A review of the old pin does not carry to the new one."]), dry_run, person)
    except Refusal as refusal:
        return _fail(refusal.problems)


def reads_review(project: str, read: str, commit: str, dry_run: bool, person: Callable[[], bool]) -> int:
    """Record, in the user's own configuration, that a person reviewed ``read`` at ``commit`` for ``project``."""
    try:
        tg = target(False)

        def edit(lines: list[str], data: dict):
            if project not in [p.get("name") for p in data.get("projects", [])]:
                raise Refusal(f"project '{project}' is not in {tg.path}. A review is kept in your own configuration, so add the project there with vyd project add")
            entry = _find(lines, data, "projects", project)

            def change(d: dict) -> None:
                next(p for p in d["projects"] if p.get("name") == project).setdefault("reviewed_reads", {})[read] = commit

            return _set(lines, entry, ("reviewed_reads",), read, commit), change

        return run(tg, Plan(edit, project=project, gate=f"a review lets the read of {read} bring skills and recipes into {project}"), dry_run, person)
    except Refusal as refusal:
        return _fail(refusal.problems)


def project_remove(name: str, file: bool, dry_run: bool, person: Callable[[], bool]) -> int:
    try:
        if file:
            raise Refusal(f"a remove never deletes a file, and removing the project of a {cf.PROJECT_FILE} would leave it empty. Delete the file yourself")
        tg = target(False)
        data = tomllib.loads(_read(tg.path))
        if name not in [p.get("name") for p in data.get("projects", [])]:
            raise Refusal(f"project '{name}' is not in {tg.path}")

        def edit(lines: list[str], data: dict):
            entry = _find(lines, data, "projects", name)
            return _cut(lines, entry.head.start, entry.end), lambda d: _drop(d, "projects", name)

        return run(tg, Plan(edit, notes=[f"project '{name}' is removed from the configuration. Its index store and logs, its folders and its documents are left as they are"]),
                   dry_run, person)
    except Refusal as refusal:
        return _fail(refusal.problems)


# -- families ---------------------------------------------------------------------------------------------

def _project_scope(config: Config, tg: Target, name: str) -> Scope:
    if tg.project_file:
        table, problems = cf.read_project_file(tg.path)
        if problems:
            raise Refusal(*problems)
        if table.get("name") != name:
            raise Refusal(f"{tg.path} declares the project '{table.get('name')}', not '{name}'")
        scope, problems = cf.file_project(config, tg.path, table, tg.path.parent.resolve(), None)
        if scope is None:
            raise Refusal(*problems)
        return scope
    if name not in config.entries:
        raise Refusal(f"project '{name}' is not in {tg.path}" + (". A vyvid.toml declares it, so use --file" if name in config.projects else ""))
    return config.projects[name]


def defined_path(value: str, scope: Scope) -> str:
    """A family's ``defined`` as the configuration keeps it, ``docs:`` or ``code:`` and inside the project, else refused."""
    bases = {"docs": scope.docs, "code": scope.code}
    if m := TOKEN.match(value):
        if m.group(1) not in bases or bases[m.group(1)] is None:
            raise Refusal(f"'{value}' starts with a token a family's definition may not use. Use docs: or code:")
        rest, base = value[len(m.group(0)):], bases[m.group(1)]
        if not Path(os.path.realpath(base / rest)).is_relative_to(Path(os.path.realpath(base))):
            raise Refusal(f"'{value}' leaves the project's {m.group(1)} folder, so it is not written")
        return value
    path = Path(os.path.abspath(Path(value).expanduser()))
    for token, base in bases.items():
        if base is not None and Path(os.path.realpath(path)).is_relative_to(Path(os.path.realpath(base))):
            return f"{token}:{path.relative_to(Path(os.path.abspath(base))).as_posix()}"
    raise Refusal(f"'{value}' is outside the project's documents and code folders, so it is not written as a family's definition")


@dataclass
class FamilySpec:
    name: str
    defined: str
    type: str
    pattern: str | None = None
    removable: bool = False

    def table(self) -> dict:
        return {**({"pattern": Literal(self.pattern)} if self.pattern else {}), "defined": self.defined, "type": self.type,
                **({"removable": True} if self.removable else {})}


def family_plan(project: str, specs: list[FamilySpec], scope: Scope, file: bool) -> Plan:
    for spec in specs:
        if spec.name in scope.families:
            raise Refusal(f"project '{project}': family '{spec.name}' exists. Remove it first with vyd family remove")
        if not cf.FAMILY_RE.match(spec.name):
            raise Refusal(f"project '{project}': family '{spec.name}' is not a family name")

    def edit(lines: list[str], data: dict):
        entry = _find(lines, data, "project", None, array=False) if file else _find(lines, data, "projects", project)
        for spec in specs:
            lines = _set(lines, entry, ("families",), spec.name, spec.table())
            entry = _find(lines, tomllib.loads("\n".join(lines) + "\n"), "project", None, array=False) if file else _find(lines, tomllib.loads("\n".join(lines) + "\n"), "projects", project)

        def change(d: dict) -> None:
            item = d["project"] if file else next(p for p in d["projects"] if p.get("name") == project)
            for spec in specs:
                item.setdefault("families", {})[spec.name] = {k: str(v) if isinstance(v, Literal) else v for k, v in spec.table().items()}

        return lines, change

    return Plan(edit, project=project, types={s.name: s.type for s in specs})


def family_add(project: str, name: str, defined: str, type_: str, pattern: str | None, removable: bool, file: bool, dry_run: bool,
               person: Callable[[], bool]) -> int:
    try:
        tg = target(file)
        scope = _project_scope(_user_config(), tg, project)
        value = defined_path(defined, scope)
        plan = family_plan(project, [FamilySpec(name, value, type_, pattern, removable)], scope, file)
        if not any(p.exists() for p in [_expand_defined(value, scope)]) and "*" not in value:
            plan.notes.append(f"NOTE: {value} does not exist yet, so the build will report that the family matches no file until it does")
        return run(tg, plan, dry_run, person)
    except Refusal as refusal:
        return _fail(refusal.problems)


def _expand_defined(value: str, scope: Scope) -> Path:
    token, _, rest = value.partition(":")
    return (scope.docs if token == "docs" else scope.code) / rest


def family_remove(project: str, name: str, file: bool, dry_run: bool, person: Callable[[], bool]) -> int:
    try:
        tg = target(file)
        scope = _project_scope(_user_config(), tg, project)
        if name not in scope.families:
            raise Refusal(f"project '{project}' declares no family '{name}'")

        def edit(lines: list[str], data: dict):
            entry = _find(lines, data, "project", None, array=False) if file else _find(lines, data, "projects", project)

            def change(d: dict) -> None:
                item = d["project"] if file else next(p for p in d["projects"] if p.get("name") == project)
                del item["families"][name]
                if not item["families"]:
                    del item["families"]

            return _delete(lines, entry, ("families",), name), change

        return run(tg, Plan(edit, project=project, notes=[f"family '{name}' is removed. The register it was defined in is left as it is"]), dry_run, person)
    except Refusal as refusal:
        return _fail(refusal.problems)


# -- scanning a project's documents for registers ---------------------------------------------------------

@dataclass
class Table:
    file: str  # relative to the documents folder
    line: int
    header: list[str]
    cells: list[str]  # the nonempty cells of the first column


def tables(root: Path) -> list[Table]:
    """Every Markdown table of the folder, outside code fences, with its header and the first cell of each row."""
    found = []
    for path in sorted(root.rglob("*.md")):
        relative = path.relative_to(root)
        if any(part.startswith(".") for part in relative.parts) or not path.is_file() or not Path(os.path.realpath(path)).is_relative_to(Path(os.path.realpath(root))):
            continue
        lines, fences, header, first = path.read_text(encoding="utf-8", errors="replace").splitlines(), Fences(indent=None), None, []
        for number, line in enumerate(lines + [""], 1):
            text = line.strip()
            if fences(line) or not text.startswith("|"):
                if header is not None:
                    found.append(Table(relative.as_posix(), header[0], header[1], first))
                header, first = None, []
                continue
            following = lines[number].strip() if number < len(lines) else ""
            if header is None and SEPARATOR_RE.match(following) and not SEPARATOR_RE.match(text):
                header = (number, _cells(text))
            elif header is not None and not SEPARATOR_RE.match(text):
                cells = _cells(text)
                if cells and cells[0]:
                    first.append(cells[0])
    return found


def signs(stack: list[Scope]) -> dict[str, set[str]]:
    """The columns each register type declares as its own, from the packaged declarations and the stack's."""
    texts = [default_declarations(), *(text for _, text in type_texts(stack))]
    out: dict[str, set[str]] = {}
    for text in texts:
        for name, spec in tomllib.loads(text).get("types", {}).items():
            if "signs" in spec:
                out[name] = set(spec["signs"])
    return out


@dataclass
class Proposal:
    specs: list[FamilySpec]
    counts: dict[str, int]
    where: dict[str, list[str]]
    named: list[str]
    existing: list[str]


def scan(scope: Scope, config: Config) -> Proposal:
    name_ = scope.name
    """The families a project's documents hold registers for, and the tables that were not placed, each with its reason."""
    stack = layers(config, scope)
    types = types_for(stack)
    sign = signs(stack)
    found: dict[str, list[tuple[Table, str, bool]]] = {}
    named: list[str] = []
    existing: list[str] = []
    for table in tables(scope.docs):
        label = f"{table.file}:{table.line}"
        if not table.cells:
            if table.header[0] in types.columns and types.columns[table.header[0]].kind == "id":
                fits = sorted(t for t, s in sign.items() if s <= set(table.header) and t in types.types)
                named.append(f"{label}, columns {', '.join(table.header)}: it has no rows, so its prefix cannot be told"
                             + (f". Its signs give the type {fits[0]}" if len(fits) == 1 else ". Its signs give no single type")
                             + f". Declare it with: vyd family add {name_} <PREFIX> --defined docs:{table.file} --type {fits[0] if len(fits) == 1 else '<type>'}")
            continue
        matches = [LOOSE_ID_RE.match(c) for c in table.cells]
        if not any(matches):
            if table.header[0] in types.columns and types.columns[table.header[0]].kind == "id":
                named.append(f"{label}, columns {', '.join(table.header)}: its first column is an identifier column, but no cell is an identifier of the form PREFIX-number, so it is not placed")
            continue
        prefixes = sorted({m.group(1) for m in matches if m})
        if not all(matches):
            named.append(f"{label}, columns {', '.join(table.header)}: its first column mixes identifiers with other text")
        elif len(prefixes) > 1:
            named.append(f"{label}, columns {', '.join(table.header)}: its identifiers have several prefixes ({', '.join(prefixes)})")
        elif prefixes[0] in scope.families:
            if prefixes[0] not in existing:
                existing.append(prefixes[0])
        elif unread := [h for h in table.header if h not in types.columns and h not in types.unmapped]:
            named.append(f"{label}, prefix {prefixes[0]}: no register can read its column {', '.join(unread)}, which is neither declared nor on the unmapped list")
        elif (id_at := next((i for i, h in enumerate(table.header) if h in types.columns and types.columns[h].kind == "id"), 0)) != 0:
            named.append(f"{label}, prefix {prefixes[0]}: its identifier column is not the first")
        else:
            fits = sorted(t for t, s in sign.items() if s <= set(table.header) and t in types.types)
            if len(fits) == 1:
                found.setdefault(prefixes[0], []).append((table, fits[0], not all(ID_RE.match(c) for c in table.cells)))
            else:
                named.append(f"{label}, prefix {prefixes[0]}, columns {', '.join(table.header)}: "
                             + (f"they fit several register types ({', '.join(fits)})" if fits else "they carry the signs of no register type, so its type is not guessed"))
    specs, counts, where = [], {}, {}
    for prefix, tabs in found.items():
        files = sorted({t.file for t, _, _ in tabs})
        kinds = sorted({k for _, k, _ in tabs})
        folders = {str(Path(f).parent) for f in files}
        if len(kinds) > 1 or len(folders) > 1:
            named += [f"{t.file}:{t.line}, prefix {prefix}: its tables differ in type ({', '.join(kinds)}) or sit in different folders, so no single family covers them" for t, _, _ in tabs]
            continue
        parent = folders.pop()
        defined = f"docs:{files[0]}" if len(files) == 1 else f"docs:{'' if parent == '.' else parent + '/'}*.md"
        loose = any(flag for _, _, flag in tabs)
        specs.append(FamilySpec(prefix, defined, kinds[0], rf"{prefix}-\d[\w.]*" if loose else None))
        counts[prefix], where[prefix] = sum(len(t.cells) for t, _, _ in tabs), files
    return Proposal(specs, counts, where, named, existing)


def project_scan(name: str, apply: bool, file: bool, dry_run: bool, person: Callable[[], bool]) -> int:
    try:
        tg = target(file)
        config = _user_config()
        scope = _project_scope(config, tg, name)
        if scope.docs is None or not scope.docs.is_dir():
            raise Refusal(f"project '{name}': its documents folder {scope.docs} does not exist")
        found = scan(scope, config)
        header = "[project.families]" if file else "[projects.families]"
        print(f"project {name}: scanned {scope.docs}")
        if found.specs:
            print(f"Proposed, to read before it is written to {tg.path}:\n{header}")
            for spec in found.specs:
                rows = found.counts[spec.name]
                print(f"{_key(spec.name)} = {_rhs(spec.table())}   # {rows} row{'s' * (rows != 1)} in {', '.join(found.where[spec.name])}"
                      + ("   # a pattern, since an identifier does not fit the default. Read it" if spec.pattern else ""))
        else:
            print("Nothing to propose.")
        if found.existing:
            print(f"Left alone, as the project declares them: {', '.join(found.existing)}")
        if found.named:
            print("Not placed, and nothing proposed for them:")
            for line in found.named:
                print(f"  {line}")
        if not apply:
            if found.specs:
                print("Write them with: vyd project scan " + name + " --apply" + (" --file" if file else ""))
            return 0
        if not found.specs:
            return 0
        plan = family_plan(name, found.specs, scope, file)
        return run(tg, plan, dry_run, person)
    except Refusal as refusal:
        return _fail(refusal.problems)

