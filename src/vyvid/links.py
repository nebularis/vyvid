# SPDX-License-Identifier: MIT
"""Links between code and the entries that documents define: ``vyd check links``, ``vyd refs``, ``vyd expand`` and ``vyd mcp``.

*A backlink* is a comment in a tracked file that is not Markdown, holding the marker, an at sign then ``vyd:``, and
the identifiers the code implements, separated by commas, to the end of the line. Only a marked line is checked,
since code and its tests write text that merely looks like an identifier.

*``check links``* fails on a backlink that resolves to nothing, on a pointer of the project's own entries that
names a file or a line that is not there, and, with ``--require``, on an entry of a family that no backlink names.

*``refs``* lists every tracked line that writes one identifier: where it is defined, backlinked and mentioned.

*``expand``* prints a prompt followed by the claim and pointer of every identifier it mentions.

*``mcp``* serves the questions to an editor as Model Context Protocol tools over standard input and output.
Each call runs ``vyd`` as a process of its own, so the server holds no state between calls.
"""

from __future__ import annotations

import fnmatch
import json
import re
import subprocess
import sys
from pathlib import Path

from . import __version__, anchors, ask, identifiers
from .config import Config, Scope, git_names
from .model import node, normalise
from .resolve import Unresolved, definition_sites, forget, resolve, visible_families
from .resolve import mentions as mentioned

MARKER = "@" "vyd:"  # written in two parts so this file holds no backlink of its own
MARK = re.compile(re.escape(MARKER) + r"[ \t]*(?P<rest>.*)")
CLOSERS = ("*/", "-->", "-}", "#}", "%>")  # what ends a block comment on the marker's line


def code_files(project: Scope) -> list[Path]:
    """The tracked text files of the project's code that are not Markdown, from ``git ls-files``, less what the project skips."""
    if project.code is None or not project.code.is_dir():
        return []
    listing = subprocess.run(["git", "-C", str(project.code), "ls-files", "-z"], capture_output=True, check=True).stdout
    keep = []
    for name in git_names(listing):
        path = project.code / name
        if name.endswith(".md") or not path.is_file() or any(fnmatch.fnmatchcase(name, g) or fnmatch.fnmatchcase(path.name, g) for g in project.identifiers.skip):
            continue
        with path.open("rb") as handle:
            if b"\0" in handle.read(1024):  # a binary file holds no comment
                continue
        keep.append(path)
    return keep


def backlinks(config: Config, project: Scope, paths: list[Path]) -> list[tuple[Path, int, str, str | None]]:
    """Every identifier a marked line names, as the file, line, spelling and canonical ``scope:LOCAL``, or None where it resolves to nothing.
    A marker with nothing after it is one broken backlink with an empty spelling."""
    found: list[tuple[Path, int, str, str | None]] = []
    for path in paths:
        for number, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            if (match := MARK.search(line)) is None:
                continue
            rest = match.group("rest")
            for closer in CLOSERS:
                rest = rest.split(closer, 1)[0]
            names = [n for n in (part.strip().rstrip(".") for part in rest.split(",")) if n]
            for name in names or [""]:
                try:
                    canonical = resolve(config, name, project) if name else None
                except Unresolved:
                    canonical = None
                found.append((path, number, name, canonical if canonical and defined(config, canonical) else None))
    return found


def defined(config: Config, canonical: str) -> bool:
    """Whether a register of the scope a canonical identifier names defines it, since resolving says only which scope it would be in."""
    name, local = canonical.split(":", 1)
    scope = {s.name: s for s in [config.general, *config.domains.values(), *config.projects.values()]}.get(name)
    return scope is not None and any(normalise(local) in definition_sites(f) for f in visible_families(config, scope) if f.defined is not None)


def broken_pointers(a: ask.Asker, project: Scope) -> tuple[int, list[str]]:
    """How many pointers the project's own entries hold, and those that name a file that is not there, or a line past its end.
    The build refuses a pointer it cannot resolve, so what is found here went missing after the index was built."""
    root, problems, read = a.root(project.name), [], 0
    for row in a.rows(ask.ALL_POINTERS):
        if row["scope"] != project.name:
            continue
        for part in str(row["pointer"]).split(","):
            try:
                path, start, _ = anchors.parse_range(part)
            except ValueError:
                continue
            read += 1
            if not (root / path).is_file():
                problems.append(f"{part.strip()} names a file that is not there")
            elif start and start > len((root / path).read_text(encoding="utf-8", errors="replace").splitlines()):
                problems.append(f"{part.strip()} starts past the end of its file")
    return read, sorted(set(problems))


# @vyd: CAP-37
def check(config: Config, project: Scope | None, folder: Path, require: list[str]) -> int:
    """``vyd check links``. Returns 1 on a broken backlink, a broken pointer or a required entry with no backlink, 2 if the files cannot be listed."""
    if project is None:
        print("no project claims this folder, so there are no links to check")
        return 0
    forget()
    families = {f.name: f for f in visible_families(config, project) if f.defined is not None}
    if unknown := [name for name in require if name not in families]:
        print(f"vyd: --require names no family of {project.name} with a register: {', '.join(unknown)}", file=sys.stderr)
        return 2
    try:
        paths = code_files(project)
    except (subprocess.CalledProcessError, OSError) as error:
        print(f"vyd: cannot list the tracked files of {project.name}: {error}", file=sys.stderr)
        return 2
    roots = [r for r in (project.code, project.docs) if r is not None]
    found = backlinks(config, project, paths)
    broken = [(p, n, name) for p, n, name, canonical in found if canonical is None]
    for path, number, name in broken:
        print(f"ERROR: {identifiers._name(path, roots)}:{number} backlinks {name or 'nothing'}, which no register defines")
    read, pointers = broken_pointers(ask.open_stack(config, folder), project)
    for problem in pointers:
        print(f"ERROR: pointer {problem}")
    linked = {normalise(c.split(":", 1)[1]) for _, _, _, c in found if c is not None and c.split(":", 1)[0] == project.name}
    unlinked = [sites[0] for name in require for key, sites in sorted(definition_sites(families[name]).items()) if key not in linked]
    for path, number, spelling in unlinked:
        print(f"ERROR: {spelling} ({identifiers._name(path, roots)}:{number}) has no backlink in code")
    failed = bool(broken or pointers or unlinked)
    print(f"{'link check failed' if failed else 'link check passed'}: {len(found)} backlinks in {len(paths)} files, {len(broken)} broken, "
          f"{read} pointers read, {len(pointers)} broken" + (f", {len(unlinked)} of {', '.join(require)} with no backlink" if require else ""))
    return int(failed)


# @vyd: CAP-38
def refs(config: Config, project: Scope | None, identifier: str) -> int:
    """``vyd refs``: every tracked line that writes the identifier, and whether it defines, backlinks or mentions it."""
    if project is None:
        print("no project claims this folder, so there is nothing to search")
        return 0
    forget()
    scope_name, local = resolve(config, identifier, project).split(":", 1)
    key, roots = normalise(local), [r for r in (project.code, project.docs) if r is not None]
    # A mention is compared on its key, which drops only these separators, so a file this does not match holds none.
    spelt = re.compile(r"[-\u2011 _]*".join(map(re.escape, key)), re.IGNORECASE)
    code = [p for p in code_files(project) if spelt.search(p.read_text(encoding="utf-8", errors="replace"))]
    documents = [p for p in identifiers.tracked(project) if spelt.search(p.read_text(encoding="utf-8", errors="replace"))]
    defined = {(p, n) for f in visible_families(config, project) if f.defined is not None for p, n, _ in definition_sites(f).get(key, [])}
    marked = {(p, n) for p, n, _, c in backlinks(config, project, code) if c is not None and c.split(":", 1)[0] == scope_name and normalise(c.split(":", 1)[1]) == key}
    sites = {site for (scope, _, k), mention in identifiers.mentions(config, project, [*documents, *code]).items()
             if scope == scope_name and k == key for site in mention.sites} | marked
    rows = [{"where": f"{identifiers._name(p, roots)}:{n}", "as": "defines" if (p, n) in defined else "backlinks" if (p, n) in marked else "mentions"}
            for p, n in sorted(sites)]
    if not rows:
        print(f"nothing refers to {scope_name}:{local}")
        return 0
    ask.show(rows, ("where", "as"))
    print(f"\n{len(rows)} reference(s) to {scope_name}:{local}")
    return 0


# @vyd: CAP-39
def expand(config: Config, folder: Path, text: str) -> int:
    """``vyd expand``: the prompt, then what each identifier it mentions claims and where to read it."""
    a = ask.open_stack(config, folder)
    print(text.rstrip("\n"))
    lines = []
    for canonical in mentioned(config, text, a.home):
        scope_name, local = canonical.split(":", 1)
        if rows := a.rows(ask.NODE, subject=node(scope_name, local)):
            r = rows[0]
            what = ", ".join(v for v in (r.get("kind"), r.get("status")) if v)
            lines.append(f"- {canonical} ({what}): {r.get('claim') or 'no claim'}" + (f" Read at {r['pointer']}" if r.get("pointer") else ""))
    if lines:
        print("\nThe entries this names:")
        print("\n".join(lines))
    return 0


# ---- The MCP server --------------------------------------------------------------------------------

_ID = {"identifier": {"type": "string", "description": "an identifier, such as STD-14 or scope:STD-14"}}
# name -> (description, properties, required, argv built from the arguments). Every value follows ``--``, so none is read as an option.
TOOLS = {
    "context": ("The contract that applies in the folder, general first and the project last.", {}, [], lambda g: ["context", "--no-pull"]),
    "find": ("Entries ranked by how close their meaning is to your words. Kind symbol searches the code.",
             {"words": {"type": "string"}, "kind": {"type": "string"}, "limit": {"type": "integer"}}, ["words"],
             lambda g: ["find", f"--limit={int(g.get('limit', 8))}", *([f"--kind={g['kind']}"] if g.get("kind") else []), "--", str(g["words"])]),
    "node": ("What one identifier is, and where to read it.", _ID, ["identifier"], lambda g: ["node", "--", str(g["identifier"])]),
    "read": ("The text of the section or definition an identifier's pointer names.", _ID, ["identifier"], lambda g: ["read", "--", str(g["identifier"])]),
    "reaches": ("What an identifier touches, by declared relations.", _ID, ["identifier"], lambda g: ["reaches", "--", str(g["identifier"])]),
    "refs": ("Every tracked line that defines, backlinks or mentions an identifier.", _ID, ["identifier"], lambda g: ["refs", "--", str(g["identifier"])]),
    "expand": ("A prompt followed by the claim and pointer of every identifier it mentions.", {"text": {"type": "string"}}, ["text"],
               lambda g: ["expand", "--", str(g["text"])]),
}


def _call(folder: Path, name: str, given: dict) -> dict:
    """Run one tool as ``vyd`` in a process of its own, and give its output as the tool's text."""
    if name not in TOOLS:
        return {"content": [{"type": "text", "text": f"no tool is named {name}"}], "isError": True}
    try:
        verb, *rest = TOOLS[name][3](given)
    except (KeyError, TypeError, ValueError) as error:
        return {"content": [{"type": "text", "text": f"{name} was called with arguments it cannot read: {error!r}"}], "isError": True}
    where = [str(folder)] if verb == "context" else ["--in", str(folder)]  # context takes its folder by position
    done = subprocess.run([sys.executable, "-m", "vyvid.cli", verb, *where, *rest], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL)
    return {"content": [{"type": "text", "text": (done.stdout + done.stderr).strip() or "no output"}], "isError": done.returncode != 0}


def answer(folder: Path, message: dict) -> dict | None:
    """The reply to one JSON-RPC message, or None for a notification."""
    method, given = message.get("method"), message.get("params") or {}
    if "id" not in message:
        return None
    if method == "initialize":
        result: dict = {"protocolVersion": given.get("protocolVersion", "2024-11-05"), "capabilities": {"tools": {}},
                        "serverInfo": {"name": "vyvid", "version": __version__}}
    elif method == "ping":
        result = {}
    elif method == "tools/list":
        result = {"tools": [{"name": n, "description": d, "inputSchema": {"type": "object", "properties": p, "required": r}} for n, (d, p, r, _) in TOOLS.items()]}
    elif method == "tools/call":
        result = _call(folder, str(given.get("name")), given.get("arguments") or {})
    else:
        return {"jsonrpc": "2.0", "id": message["id"], "error": {"code": -32601, "message": f"no method {method}"}}
    return {"jsonrpc": "2.0", "id": message["id"], "result": result}


# @vyd: CAP-40
def serve(folder: Path) -> int:
    """``vyd mcp``: read one JSON-RPC message a line from standard input and write each reply as one line, until the input ends."""
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            message = json.loads(line)
            reply = answer(folder, message) if isinstance(message, dict) else None
        except json.JSONDecodeError:
            reply = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "the line is not JSON"}}
        if reply is not None:
            sys.stdout.write(json.dumps(reply) + "\n")
            sys.stdout.flush()
    return 0
