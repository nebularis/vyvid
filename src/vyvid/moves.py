# SPDX-License-Identifier: MIT
"""``vyd move check``: what changed in a moved source file since it moved.

A project's moves name the file the knowledge came from and the commit it was taken at. A branch
that still has the file may have edited a moved entry, added one or removed one, and merging it
would lose that unseen. This compares the file at the commit with the file at a ref, by identifier,
and reports what the ref itself changed since it forked from that commit, so a branch older than the
move is not blamed for what its base changed, and one already carrying the moved text reports nothing.

A table family's entry is its row, and a heading family's its section, to the next heading of the
same or a higher level. A row move compares only the rows it names, since the project keeps its
family. A table row is taken by its first cell, so a register whose identifier is in another column
is not read.

A move with ``copy_removed = true`` says the project has removed its copy, so the copy is not compared. With
no ref that move is reported as ``copy-removed``. With a ref, the move is reported so where the source at the
ref is byte-identical to the working tree's, since the ref then carries the removal, and no ancestry is
read, which holds after a squash merge. Where the source at the ref differs, it is compared as usual, except
that an entry the ref still has and the tree no longer has is dropped, since that removal loses nothing.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from . import anchors
from .citations import GitError, git
from .config import Config, Move, Scope
from .extract import head
from .registers import SEPARATOR_RE, _cells

ABSENT = "file-absent"
REMOVED = "copy-removed"


def entries(rule: str, pattern, text: str) -> dict[str, str]:
    """Each identifier the file defines and the text that defines it, whitespace aside."""
    lines = text.splitlines()
    out: dict[str, str] = {}
    if rule == "heading":
        for start, end, _ in anchors.sections(lines):
            if match := head(pattern, lines[start - 1].lstrip("#").strip()):
                out.setdefault(match.group(0), "\n".join(l.rstrip() for l in lines[start - 1 : end]).strip())
    else:
        for line in lines:
            if line.lstrip().startswith("|") and not SEPARATOR_RE.match(line.strip()) and (cells := _cells(line)):
                if pattern.fullmatch(first := cells[0].strip("*` ")):
                    out.setdefault(first, " ".join(line.split()))
    return out


def compare(move: Move, rule: str, pattern, old: str, new: str) -> list[tuple[str, str]]:
    """``(identifier, state)`` for each entry that differs, the state ``changed``, ``added`` or ``removed``."""
    before, after = entries(rule, pattern, old), entries(rule, pattern, new)
    found = []
    for identifier in [*before, *(i for i in after if i not in before)]:
        if move.rows and identifier not in move.rows:
            continue
        if identifier not in after:
            found.append((identifier, "removed"))
        elif identifier not in before:
            found.append((identifier, "added"))
        elif before[identifier] != after[identifier]:
            found.append((identifier, "changed"))
    return found


def _top(path: Path) -> Path:
    here = path.parent
    while not here.exists():
        here = here.parent
    return Path(git(here, "rev-parse", "--show-toplevel").strip()).resolve()


def _at_fork(top: Path, commit: str, ref: str, rel: str, moved: str) -> str:
    """The file where the ref forked from the moved commit, or as moved where it has no such history."""
    try:
        return git(top, "show", f"{git(top, 'merge-base', commit, ref).strip()}:{rel}")
    except GitError:
        return moved


def _same(top: Path, ref: str, rel: str, source: Path) -> bool:
    """Whether the file at the ref is byte-identical to the one in the working tree."""
    done = subprocess.run(["git", "show", f"{ref}:{rel}"], cwd=top, capture_output=True)
    return source.is_file() and done.returncode == 0 and done.stdout == source.read_bytes()


def check(project: Scope, config: Config, ref: str | None) -> list[tuple[str, str, str]]:
    """``(family, identifier, state)`` for everything that differs, over every move of the project.
    Raises GitError for a rev that does not exist, and OSError for a file that cannot be read."""
    found = []
    for move in project.moves:
        family = project.families.get(move.family) or config.domains[move.to].families[move.family]
        if family.rule not in ("table", "heading"):
            raise OSError(f"family {move.family} is a {family.rule} family, which move check does not read")
        if move.source is None:
            raise OSError(f"the move of {move.family} names no source")
        source = move.source.parent.resolve() / move.source.name
        top = _top(source)
        rel = source.relative_to(top).as_posix()
        try:
            old = git(top, "show", f"{move.commit}:{rel}")
        except GitError:
            raise GitError(f"{rel} cannot be read at {move.commit} in {top}") from None
        if ref is None and move.copy_removed:
            found.append((move.family, "-", REMOVED))
            continue
        if ref is None:
            new = source.read_text(encoding="utf-8") if source.is_file() else None
        else:
            try:
                git(top, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}")
            except GitError:
                raise GitError(f"{ref} is no git ref in {top}") from None
            try:
                new = git(top, "show", f"{ref}:{rel}")
            except GitError:
                new = None
        if new is None:
            found.append((move.family, "-", ABSENT))
        elif move.copy_removed and _same(top, ref, rel, source):
            found.append((move.family, "-", REMOVED))
        else:
            differs = compare(move, family.rule, family.pattern, old, new)
            if ref is not None:
                ours = {i for i, _ in compare(move, family.rule, family.pattern, _at_fork(top, move.commit, ref, rel, old), new)}
                differs = [(i, state) for i, state in differs if i in ours]
            if move.copy_removed:
                differs = [(i, state) for i, state in differs if state != "removed"]
            found += [(move.family, i, state) for i, state in differs]
    return found


def command(config: Config, project: Scope | None, ref: str | None, as_json: bool) -> int:
    """Print the differences, plain or as JSON. Returns 1 if there are any, 2 if something cannot be read.
    A file absent at the ref is one line, ``file-absent``, and a removed copy one, ``copy-removed``, and neither is a difference."""
    if project is None or not project.moves:
        print("no move is declared for this folder's project")
        return 0
    try:
        found = check(project, config, ref)
    except (GitError, OSError, UnicodeDecodeError) as error:
        print(f"vyd: {error}", file=sys.stderr)
        return 2
    if as_json:
        print(json.dumps([{"family": f, "id": i, "state": s} for f, i, s in found], indent=2))
    else:
        for line in found:
            print(*line)
        if not found:
            print("nothing differs")
    return 1 if any(s not in (ABSENT, REMOVED) for _, _, s in found) else 0
