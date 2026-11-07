# SPDX-License-Identifier: MIT
"""Which project a folder belongs to, the layers of rules that apply there, and what an identifier names.

A folder belongs to the project whose code or documents folder holds it, the deepest such folder
winning, and otherwise to the project whose remote its git repository has. The layers are the
general scope, then the domains the project uses with all their ancestors, parents before children,
then the project, so a later layer overrides an earlier one. A folder no project claims gets the
general scope alone.

A repository may declare its own project in a ``vyvid.toml`` at its root (``project_file``). It binds the folders
inside it, ahead of a remote, and a configured project holding the folder more deeply still wins. The user's
``[[projects]]`` entry of the same name overrides the file's keys one by one. A file that cannot be used sets
its project aside and the folder gets the general scope (``bind_in``).
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import replace
from pathlib import Path

from .config import PROJECT_FILE, Config, Family, Move, Scope, file_project, read_project_file
from .model import normalise
from .registers import _cells

QUALIFIED_RE = re.compile(r"^(?P<scope>[a-z][a-z0-9-]*):(?P<local>.+)$")


class Unresolved(Exception):
    """An identifier names nothing the configuration knows, or names more than one thing."""


def normalise_remote(url: str) -> str:
    """A remote URL as host/owner/repository, lower case: no scheme, no user, no .git. A local remote's backslashes are
    slashes, since git keeps a remote as it was given and a Windows path may be written either way."""
    url = re.sub(r"^[a-z+]+://", "", url.strip().replace("\\", "/"))
    url = re.sub(r"^[^@/]+@", "", url)
    url = re.sub(r"^([^/:]+):(?!\d)", r"\1/", url)
    return re.sub(r"(\.git)?/*$", "", url).lower()


def remotes(folder: Path) -> list[str]:
    """The normalised remote URLs of the git repository holding ``folder``, if any."""
    found = subprocess.run(
        ["git", "-C", str(folder), "config", "--get-regexp", r"^remote\..*\.url$"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    return [normalise_remote(line.split(None, 1)[1]) for line in found.stdout.splitlines() if " " in line]


def _by_path(config: Config, folder: Path) -> tuple[Scope | None, int]:
    """The project whose code or documents folder holds ``folder`` most deeply, and how deep that is."""
    best, depth = None, -1
    for project in config.projects.values():
        for root in (project.code, project.docs):
            if root is None:
                continue
            root = root.resolve()
            if (folder == root or root in folder.parents) and len(root.parts) > depth:
                best, depth = project, len(root.parts)
    return best, depth


def bind(config: Config, folder: Path) -> Scope | None:
    """The project a folder belongs to, by the deepest code or documents folder holding it, then by the
    git repository it shares with a project's code folder, so a worktree may be anywhere, then by remote."""
    folder = folder.expanduser().resolve()
    best, _ = _by_path(config, folder)
    if best is not None:
        return best
    common = _common(folder) if folder.exists() else None
    if common is not None:
        for project in config.projects.values():
            if project.code is not None and project.code.exists() and _common(project.code.resolve()) == common:
                return project
    found = set(remotes(folder)) if folder.exists() else set()
    for project in config.projects.values():
        if found & {normalise_remote(r) for r in project.remotes}:
            return project
    return None


def _git(folder: Path, *args: str) -> str | None:
    from .config import _git_out  # config imports this module

    return _git_out(folder, *args) or None  # a path or a ref, never NUL-laden or oversized


def _common(folder: Path) -> Path | None:
    out = _git(folder, "rev-parse", "--git-common-dir")
    return (folder / out).resolve() if out else None


def checkout_of(project: Scope, folder: Path) -> Path | None:
    """The root of the linked checkout of the project that holds ``folder``, else None.

    It is a checkout when its git root is not the code folder and it shares the code folder's git common
    directory, or, with a code folder that is missing or no repository, a normalised remote. A different
    repository nested in the code folder, a folder outside git, and a code folder that is only part of a
    repository keep the project as configured."""
    folder = folder.expanduser().resolve()
    top = _git(folder, "rev-parse", "--show-toplevel") if folder.exists() else None
    if top is None or project.code is None:
        return None
    root, code = Path(top).resolve(), project.code.resolve()
    if root == code:
        return None
    code_top = _git(code, "rev-parse", "--show-toplevel") if code.exists() else None
    if code_top is None:
        return root if set(remotes(root)) & {normalise_remote(r) for r in project.remotes} else None
    return root if Path(code_top).resolve() == code and _common(root) == _common(code) else None


def rebase(config: Config, project: Scope, root: Path) -> Config:
    """``config`` with ``project`` answered from the checkout at ``root``: its code folder, and every
    path it holds inside the code folder, moved there. A documents folder outside the code folder stays."""
    old = project.code

    def move(path: Path | None) -> Path | None:
        try:
            return root / path.relative_to(old) if path is not None else None
        except ValueError:
            return path

    def family(f: Family) -> Family:
        return replace(f, defined=move(f.defined), also=tuple(move(p) for p in f.also), exceptions=move(f.exceptions))

    moved = replace(
        project, code=root, docs=move(project.docs), checkout=root,
        moves=[replace(m, source=move(m.source)) for m in project.moves],
        rules=[move(p) for p in project.rules], skills=[move(p) for p in project.skills], skill_additions=move(project.skill_additions),
        facets=[move(p) for p in project.facets], register_types=[move(p) for p in project.register_types],
        vocabulary=[move(p) for p in project.vocabulary], specialises={k: move(p) for k, p in project.specialises.items()},
        families={k: family(f) for k, f in project.families.items()},
        identifiers=replace(project.identifiers, exceptions=move(project.identifiers.exceptions)),
        symbols=[replace(x, paths=tuple(move(p) for p in x.paths)) for x in project.symbols],
        work=project.work.moved(move) if project.work else None,
        code_index=[replace(x, database=move(x.database), sources=move(x.sources)) for x in project.code_index])
    return replace(config, projects={**config.projects, project.name: moved})


def project_file(folder: Path) -> Path | None:
    """The vyvid.toml that declares the project of ``folder``: at the git toplevel of the folder, else, where the
    folder is not in git, in the nearest folder above it that has one. Nothing else reads it."""
    folder = folder.expanduser().resolve()
    if not folder.exists():
        return None
    folder = folder if folder.is_dir() else folder.parent
    if (top := _git(folder, "rev-parse", "--show-toplevel")) is not None:
        file = Path(top).resolve() / PROJECT_FILE
        return file if file.is_file() else None
    return next((p / PROJECT_FILE for p in (folder, *folder.parents) if (p / PROJECT_FILE).is_file()), None)


def main_root(root: Path) -> Path:
    """The folder of the repository's main checkout, else ``root`` itself."""
    common = _common(root)
    return common.parent if common is not None and common.name == ".git" else root


def _same_repository(code: Path, root: Path) -> bool:
    """Whether a configured code folder is ``root`` or another checkout of the repository ``root`` is in, as
    ``checkout_of`` counts one, so its paths may be moved to ``root``."""
    code = code.resolve()
    if code == root:
        return True
    top = _git(code, "rev-parse", "--show-toplevel") if code.exists() else None
    return top is not None and Path(top).resolve() == code and _common(code) is not None and _common(code) == _common(root)


def _with_file(config: Config, folder: Path, file: Path) -> tuple[Config, Scope | None] | None:
    """The configuration and project the vyvid.toml at ``file`` gives ``folder``. None when it is not the file's
    to bind: a project the user configured holds the folder as deeply, under another name. A file that cannot
    be used is recorded in ``files_aside`` and gives the general scope."""
    root = file.parent.resolve()
    table, problems = read_project_file(file)
    name = table.get("name")
    near, depth = _by_path(config, folder)
    entry = config.entries.get(name) if isinstance(name, str) else None
    same = entry is not None and "code" in entry and _same_repository(Path(entry["code"]).expanduser(), root)
    if near is not None and near.name != name and depth >= len(root.parts):
        return None
    if entry is not None and not same:
        problems.append(f"{file}: project '{name}' is configured with the code folder {entry.get('code')}, which is not this repository")
    scope = None
    if not problems:
        code = Path(entry["code"]).expanduser() if same else main_root(root)
        scope, problems = file_project(config, file, table, code, entry if same else None)
    if scope is None:
        return replace(config, files_aside={**config.files_aside, str(file): problems}), None
    config = replace(config, projects={**config.projects, scope.name: scope})
    if scope.code.resolve() != root:
        config = rebase(config, scope, root)
    return config, config.projects[scope.name]


def file_scope(config: Config, file: Path) -> tuple[Scope | None, list[str]]:
    """The project a vyvid.toml declares by itself, with the reasons it cannot be used. For ``vyd trust``, which
    lists what the file would run."""
    table, problems = read_project_file(file)
    if problems:
        return None, problems
    return file_project(config, file, table, file.parent.resolve(), None)


def bind_in(config: Config, folder: Path) -> tuple[Config, Scope | None]:
    """The configuration to answer ``folder`` from and its project: the project its repository's vyvid.toml
    declares, else ``bind``, with the project rebased onto the folder's checkout when it is a linked one.
    Binding the result again changes nothing."""
    folder = folder.expanduser()
    if (file := project_file(folder)) is not None and (decided := _with_file(config, folder.resolve(), file)) is not None:
        return decided
    project = bind(config, folder)
    if project is not None and (root := checkout_of(project, folder)) is not None:
        config = rebase(config, project, root)
        project = config.projects[project.name]
    return config, project


def layers(config: Config, project: Scope | None) -> list[Scope]:
    """General, then every domain the project uses and their ancestors, parents first, then the project.

    Of two domains with no order between them, the one named first in the project comes first, so the
    order is the same on every run."""
    if project is None:
        return [config.general]
    return [config.general, *(config.domains[n] for n in config.domain_order(project)), project]


def resolve(config: Config, mention: str, scope: Scope, how: list[str] | None = None) -> str:
    """The canonical ``scope:LOCAL`` an identifier names, written in ``scope``.

    A qualified mention names its own scope. A bare one means the scope it is written in, through a
    family that scope declares, or one it delegates to another scope. A project's move comes first,
    whether the project still holds the entry or not. A mention no family matches, or more than one
    does, is refused rather than guessed. ``how`` collects a line for each move followed."""
    if (q := QUALIFIED_RE.match(mention)) is not None:
        target = config.scope(q.group("scope"))
        if target is None:
            raise Unresolved(f"'{mention}' names the scope '{q.group('scope')}', which is not configured")
        return _within(config, q.group("local"), target, set(), how)
    return _within(config, mention, scope, set(), how)


def moved(config: Config, scope: Scope, local: str) -> tuple[Move, str] | None:
    """The move of ``scope`` that covers ``local`` and the identifier it has in the domain, else None."""
    for move in scope.moves:
        if move.rows:
            for key, target in move.rows.items():
                if normalise(key) == normalise(local):
                    return move, target
        elif (family := config.domains[move.to].families.get(move.family)) is not None and family.pattern.fullmatch(local):
            return move, local
    return None


_SITES: dict[Family, dict[str, list[tuple[Path, int, str]]]] = {}


def forget() -> None:
    """Drop the definitions read so far, so the next call reads the files again. A build and a check do."""
    _SITES.clear()


def definition_sites(family: Family) -> dict[str, list[tuple[Path, int, str]]]:
    """Every site that defines an identifier of ``family``, as normalised key -> ``(path, line, spelling)``,
    line 0 for a file named by it. Read once per run, by the family's rule. The identifier is the first cell
    of a table row, the start of a heading or a file's name, or the lead of a question."""
    if (found := _SITES.get(family)) is not None:
        return found
    from .extract import head, questions_in  # extract imports this module

    found = _SITES[family] = {}
    for path in family.paths():
        if family.rule == "file":
            if match := head(family.pattern, path.stem):
                found.setdefault(normalise(match.group(0)), []).append((path, 0, match.group(0)))
            continue
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        if family.rule == "question":
            for q in questions_in(lines, family.pattern):
                found.setdefault(normalise(q.identifier), []).append((path, q.start, q.identifier))
            continue
        for number, line in enumerate(lines, 1):
            stripped = line.strip()
            if family.rule == "table" and stripped.startswith("|"):
                cells = _cells(stripped)
                spelling = cells[0] if cells and family.pattern.fullmatch(cells[0]) else None
            elif family.rule == "heading" and stripped.startswith("#"):
                spelling = match.group(0) if (match := head(family.pattern, stripped.lstrip("#").strip())) else None
            else:
                spelling = None
            if spelling:
                found.setdefault(normalise(spelling), []).append((path, number, spelling))
    return found


def live(family: Family, local: str) -> bool:
    """Whether ``local`` names something in ``family``: it matches the pattern, and for a family that is
    ``defined_only``, its source defines it. A loose pattern then does not read ``UTF-8`` as an entry."""
    return family.pattern.fullmatch(local) is not None and (not family.defined_only or normalise(local) in definition_sites(family))


def private_entry(project: Scope, local: str) -> bool:
    """Whether ``local`` is an entry of a project's private documents: the files that define it all lie under
    the documents folder, which is outside the code folder. An entry defined in the code folder, in both, or
    nowhere is not, since the file that defines an entry decides and never its family's name."""
    if not project.private_docs or project.docs is None:
        return False
    docs = project.docs.resolve()
    for family in project.families.values():
        if family.pattern.fullmatch(local) and (sites := definition_sites(family).get(normalise(local))):
            return all(docs in site[0].resolve().parents for site in sites)
    return False


def _within(config: Config, local: str, scope: Scope, seen: set[str], how: list[str] | None = None) -> str:
    if scope.name in seen:
        raise Unresolved(f"'{local}' is delegated in a circle through '{scope.name}'")
    seen.add(scope.name)
    if (hit := moved(config, scope, local)) is not None:
        move, target = hit
        if how is not None:
            how.append(f"{scope.name}:{local} moved to {move.to}:{target} (family {move.family}, from {move.source} at {move.commit})")
        return f"{move.to}:{target}"
    own = [f for f in scope.families.values() if live(f, local)]
    delegated = []
    for family, target in scope.delegates.items():
        other = config.scope(target)
        if other is not None and family in other.families and live(other.families[family], local):
            delegated.append(other)
    if len(own) + len(delegated) > 1:
        names = [f.name for f in own] + [f"{o.name} by delegation" for o in delegated]
        raise Unresolved(f"'{local}' in '{scope.name}' matches more than one family: {', '.join(names)}")
    if own:
        return f"{scope.name}:{local}"
    if delegated:
        return _within(config, local, delegated[0], seen)
    raise Unresolved(f"'{local}' matches no family of '{scope.name}'")


def visible_families(config: Config, scope: Scope) -> list:
    """The families a bare mention in ``scope`` can mean: its own and the ones it delegates."""
    out = list(scope.families.values())
    for family, target in scope.delegates.items():
        other = config.scope(target)
        if other is not None and family in other.families:
            out.append(other.families[family])
    return out


def mentions(config: Config, text: str, scope: Scope) -> list[str]:
    """Every identifier written in ``text``, as canonical ``scope:LOCAL``, once each, in order.

    A qualified mention names a configured scope, ``other:STD-1``, and a bare one matches a family
    ``scope`` declares or delegates. A mention that resolves to nothing, or to more than one thing,
    is skipped here, never raised, since a cell of prose may hold text that only looks like one.
    Two spellings of one identifier count once, under the first."""
    found: list[tuple[int, int, str]] = []
    qualified: list[tuple[int, int]] = []
    for target in [config.general, *config.domains.values(), *config.projects.values()]:
        for family in visible_families(config, target):
            qualified_form = family.pattern.derive(lambda p: rf"(?<![\w-]){re.escape(target.name)}:(?:{p})(?![\w-])")
            for m in qualified_form.finditer(text):
                found.append((m.start(), m.end(), m.group(0)))
                qualified.append((m.start(), m.end()))
    for family in visible_families(config, scope):
        for m in family.pattern.derive(lambda p: rf"(?<![\w-])(?:{p})(?![\w-])").finditer(text):
            if not any(a <= m.start() and m.end() <= b for a, b in qualified):
                found.append((m.start(), m.end(), m.group(0)))
    out: dict[tuple[str, str], str] = {}
    for _, _, mention in sorted(found):
        try:
            canonical = resolve(config, mention, scope)
        except Unresolved:
            continue
        name, local = canonical.split(":", 1)
        out.setdefault((name, normalise(local)), canonical)
    return list(out.values())
