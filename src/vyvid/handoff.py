# SPDX-License-Identifier: MIT
"""``vyd handoff``: the exact commands for a code index a project registers, printed and never run.

Whether a name is called, and by whom, is a question for a compiler's index, and Вивід builds none and runs none.
A project registers the index it has in ``[[project.code_index]]``, and this prints the command lines that ask it.

**The commands come from templates in this file.** The file contributes a path, which is quoted whole with ``shlex.join``
and held inside the repository, and nothing else. ``built_by`` is shown as text, and withheld while the file that
declares it is not trusted, so a hostile vyvid.toml cannot put a command in front of an agent. A name or a module
the asker types is held to the characters of a Haskell name before it reaches a template.

**What is guarded, since each of these misled an agent in silence:** a database that does not exist, which ``hiedb -D``
would create empty and report success for, is checked first by reading it here, read-only and immutable, and no command is
printed for one that is absent or holds no rows. Every SQL line opens ``file:<path>?immutable=1`` and carries a
limit, because ``hiedb`` keeps its database in WAL mode, where a read-only open otherwise writes files beside it or fails.
Every ``hiedb`` line carries ``-D`` with the absolute path, since none writes a database to the home folder, and a limit. A
missing tool is named, and SQL stands in for ``hiedb``. An index older than its sources is reported as possibly stale.
An empty answer is said not to prove that nothing calls a name.
"""

from __future__ import annotations

import os
import re
import shlex
import shutil
import sqlite3
import subprocess
import time
from pathlib import Path
from urllib.parse import quote

from .config import CodeIndex, Scope
from .symbols import store as symbol_store

KNOWN = ("hiedb",)
LIMIT = 50
NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_']*\Z")
MODULE = re.compile(r"[A-Z][A-Za-z0-9_']*(?:\.[A-Z][A-Za-z0-9_']*)*\Z")
UNIT = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]*\Z")
NEEDED = ("refs", "mods", "defs")
SECONDS = 2


def registered(project: Scope | None) -> list[CodeIndex]:
    return list(project.code_index) if project is not None else []


def clean(text: str) -> str:
    """Text a file gave, on one line with no control characters, for showing and never for running."""
    return "".join(c for c in " ".join(text.split()) if c.isprintable())[:200]


def inside(path: Path, root: Path) -> bool:
    return Path(os.path.realpath(path)).is_relative_to(Path(os.path.realpath(root)))


def uri(database: Path) -> str:
    """The database as a SQLite URI, its path written with forward slashes, which SQLite reads on every platform."""
    return f"file:{quote(Path(database).as_posix(), safe='/:')}?immutable=1"


def opened(database: Path) -> sqlite3.Connection:
    """The database read-only and immutable, stopped after a few seconds, so a hostile file cannot hold the command."""
    db = sqlite3.connect(uri(database), uri=True)
    deadline = time.monotonic() + SECONDS
    db.set_progress_handler(lambda: int(time.monotonic() > deadline), 10000)
    return db


def problem(database: Path, root: Path) -> str | None:
    """Why the database cannot be used, or None when it exists inside the repository, opens as SQLite with the tables of an index, and holds rows."""
    if not database.is_file():
        return f"{database} does not exist, and hiedb -D would create an empty database there and report success"
    if not inside(database, root):
        return f"{database} is a link that leaves the repository, so it is not read"
    try:
        db = opened(database)
        try:
            tables = {name for (name,) in db.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
            if missing := [t for t in NEEDED if t not in tables]:
                return f"{database} has no table {', '.join(missing)}, so it is not an hiedb database"
            if not db.execute("SELECT 1 FROM refs LIMIT 1").fetchone():
                return f"{database} holds no references"
        finally:
            db.close()
    except sqlite3.Error as error:
        return f"{database} cannot be read as a database ({error.__class__.__name__})"
    return None


def stale(index: CodeIndex, project: Scope) -> str | None:
    """A sentence saying the database may be stale, when a tracked file under ``sources`` is newer than it."""
    if index.sources is None:
        return None
    try:
        wanted = symbol_store.glob_regex(index.sources.relative_to(project.code).as_posix(), prefix=True)
        files = [project.code / n for n in symbol_store.tracked(project.code) if wanted.match(n)]
        built = index.database.stat().st_mtime
        newest = max((f for f in files if f.is_file()), key=lambda f: f.stat().st_mtime, default=None)
        newer = newest is not None and newest.stat().st_mtime > built
    except (ValueError, OSError, subprocess.CalledProcessError):
        return None
    return f"{newest.relative_to(project.code).as_posix()} is newer than the database, so the index may be stale" if newer else None


def lit(text: str) -> str:
    """A SQL string literal. Names are held to a Haskell name's characters, of which only the prime needs doubling."""
    return "'" + text.replace("'", "''") + "'"


def occ(column: str, name: str) -> str:
    """The SQL test for the occurrence names of ``name``: a value ``v:``, a constructor ``c:``, a type ``t:`` or a field ``f<Type>:``."""
    return f"({column} in ({', '.join(lit(p + name) for p in ('v:', 'c:', 't:'))}) or {column} glob {lit('f*:' + name)})"


def sqlite(database: Path, sql: str) -> str:
    """The sqlite3 line for one statement, the statement in double quotes. It holds nothing a shell expands, which is checked."""
    sql = " ".join(sql.split())
    if re.search(r'["`$\\!]', sql):
        raise ValueError("a statement holds a character a shell would expand")
    return f'sqlite3 -header {shlex.quote(uri(database))} "{sql}"'


def hiedb(database: Path, *words: str) -> str:
    return shlex.join(["hiedb", "-D", str(database), *words]) + f" | head -n {LIMIT}"


def commands(database: Path, name: str | None, module: str | None, tools: dict[str, str | None], unit: str | None = None) -> list[tuple[str, str]]:
    """The labelled command lines for a name, a module or both, the module's calls kept to units that start with ``unit``. The only text not fixed
    here is ``name``, ``module`` and ``unit``, each checked, and the path, quoted."""
    out: list[tuple[str, str]] = []
    if name:
        defined_in, referenced_in = (f" and m.mod = {lit(module)}", f" and r.mod = {lit(module)}") if module else ("", "")
        if tools["hiedb"]:
            extra = [module] if module else []
            for what, verbs in (("where it is defined", ("name-def", "type-def")), ("who references it", ("name-refs", "type-refs"))):
                out += [(f"{what} (hiedb)", hiedb(database, verb, name, *extra)) for verb in verbs if name[:1].isupper() or verb.startswith("name")]
        if tools["sqlite3"]:
            out.append(("where it is defined (SQL)", sqlite(database, f"""select m.mod, m.unit, d.occ, d.sl from defs d join mods m on m.hieFile = d.hieFile
                where {occ('d.occ', name)}{defined_in} order by m.mod limit {LIMIT};""")))
            out.append(("who references it (SQL)", sqlite(database, f"""select m.mod as caller, r.sl as line, r.mod as defined_in, group_concat(distinct d.occ) as enclosing_decl
                from refs r join mods m on m.hieFile = r.hieFile left join decls d on d.hieFile = r.hieFile and r.sl between d.sl and d.el
                where {occ('r.occ', name)}{referenced_in} group by m.mod, r.sl order by 1, 2 limit {LIMIT};""")))
    if module and tools["sqlite3"]:
        only = f" and r.unit glob {lit(unit + '*')}" if unit else ""
        out.append(("what the module calls in other indexed packages (SQL)", sqlite(database, f"""select r.occ, r.mod, r.unit, count(*) as n, min(r.sl) as first_line
            from refs r join mods m on m.hieFile = r.hieFile where m.mod = {lit(module)} and r.unit <> m.unit and r.unit in (select unit from mods){only}
            and r.occ not like 'v:' || char(36) || 'f%' group by r.occ, r.mod, r.unit order by r.mod, r.occ limit {LIMIT};""")))
    return out


def near(directory: Path, name: str) -> list[str]:
    """Up to five symbols of the project's symbol store whose names are close to ``name``, as ``name (kind in module)``."""
    path = directory / symbol_store.DB
    if not path.is_file():
        return []
    db = symbol_store.connect(path)
    try:
        ranked = symbol_store.word_rank(db, symbol_store.split_words(name), 40)
        rows = {r["rowid"]: r for r in symbol_store.rows(db, f"WHERE rowid IN ({','.join('?' * len(ranked))})", tuple(ranked))} if ranked else {}
    finally:
        db.close()
    if any(r["name"] == name for r in rows.values()):
        return []  # the name exists, so a miss is not a misspelling
    found = dict.fromkeys(f"{r['name']} ({r['kind']} in {r['module']})" for i in ranked if (r := rows[i])["kind"] != "instance")
    return list(found)[:5]


def has_module(database: Path, module: str) -> bool:
    db = opened(database)
    try:
        return db.execute("SELECT 1 FROM mods WHERE mod = ? LIMIT 1", (module,)).fetchone() is not None
    finally:
        db.close()


def report(index: CodeIndex, project: Scope, directory: Path, name: str | None, module: str | None, unit: str | None = None) -> list[str]:
    """The lines to print for one registered index."""
    head = f"code index {clean(index.kind)}"
    if index.kind not in KNOWN:
        return [f"{head} is registered, and vyd knows no commands for a kind of that name, so it prints none.", f"  database {index.database}"]
    lines = [f"{head}: {index.database}"]
    built = clean(index.built_by) if index.built_by and project.trusted else ""
    how = (f"It is built by: {built}" if built else "built_by is withheld, since the vyvid.toml that declares it is not trusted" if index.built_by
           else "No built_by is declared")
    if why := problem(index.database, project.code):
        return lines + [f"  {why}.", f"  No command is printed. {how}."]
    if Path(f"{index.database}-wal").is_file() and Path(f"{index.database}-wal").stat().st_size:
        lines.append("  A -wal file sits beside it, and immutable=1 does not see what it holds, so recent writes may be missing from the SQL lines.")
    tools = {t: shutil.which(t) for t in ("hiedb", "sqlite3")}
    lines += [f"  {t} is not on PATH" + (", so SQL stands in for it." if t == "hiedb" else ", so only the hiedb lines are printed.") for t, found in tools.items() if not found]
    if not any(tools.values()):
        return lines + ["  Neither is installed, so no command is printed."]
    if why := stale(index, project):
        lines.append(f"  {why}. {how}.")
    for label, line in commands(index.database, name, module, tools, unit):
        lines += [f"  {label}:", f"    {line}"]
    lines.append("  An empty result does not prove that nothing refers to a name. A misspelt name, a name in another namespace and a stale index all give none.")
    if name and (close := near(directory, name)):
        lines.append("  Near matches in the symbol store: " + "; ".join(close))
    return lines


def command(project: Scope | None, directory: Path, name: str, module: str | None, unit: str | None = None) -> int:
    """Print the hand-off for each registered index. ``name`` is a symbol, or a module the index holds. Returns 1 for no project or no index and 2 for a name that is not a plain name."""
    tools = registered(project)
    if project is None or not tools:
        print("no code index is registered here. A project registers one in a [[project.code_index]] table of its vyvid.toml, with a kind, a database and, to say how it is built, built_by.")
        return 1
    if not project.trusted:
        print(f"vyd: the vyvid.toml of project {project.name} is not trusted, so no code index it names is opened and no command is printed. A person runs vyd trust in a terminal, after reading what it declares.")
        return 1
    asked = ((name, NAME.match(name) or MODULE.match(name)), (module, not module or MODULE.match(module)), (unit, not unit or UNIT.match(unit)))
    if bad := [clean(value) for value, fine in asked if value and not fine]:
        print(f"vyd: {', '.join(bad)} is not a plain name, module or unit, so no command is printed. Operators and quoted names are not supported.")
        return 2
    for index in tools:
        usable = index.kind in KNOWN and not problem(index.database, project.code)
        as_module = usable and "." in name and MODULE.match(name) and has_module(index.database, name)
        print("\n".join(report(index, project, directory, None if as_module else name, name if as_module else module, unit)))
    return 0
