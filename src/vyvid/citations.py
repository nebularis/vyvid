# SPDX-License-Identifier: MIT
"""Stop a public project's text from citing an entry of a private scope.

The lines a change adds are read, from the staged diff of the project's code folder and of its
documents folder when that is a repository of its own, or from the files named. Every identifier
they cite is resolved in the project's scope, and one that names an entry of a private scope, or of the
project's private documents, is refused. A commit message or pull request text is checked as a file. A mention that resolves to nothing is not this check's business.
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

from .audit import CITES_RE
from .config import Config, Scope
from .resolve import mentions, private_entry

HUNK_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+(?P<start>\d+)(?:,(?P<count>\d+))? @@")


class GitError(Exception):
    """A git call the check depends on failed."""


def git(folder: Path, *args: str) -> str:
    done = subprocess.run(["git", "-c", "i18n.logOutputEncoding=UTF-8", *args], cwd=folder, capture_output=True, text=True, encoding="utf-8", errors="replace",
                          env={**os.environ, "GIT_TERMINAL_PROMPT": "0"})
    if done.returncode != 0:
        raise GitError(f"git {' '.join(args)} failed in {folder}: {done.stderr.strip()}")
    return done.stdout


def parse_diff(diff: str) -> list[tuple[str, int, str]]:
    """The ``(path, line, text)`` of every line a ``git diff -U0`` adds. Inside a hunk the counts in
    its header decide what is content, so an added line that reads ``++ x`` is not taken for a file header."""
    out: list[tuple[str, int, str]] = []
    path, line, left = None, 0, 0
    for text in diff.splitlines():
        if left == 0 and text.startswith("+++ "):
            name = text[4:].split("\t")[0]
            path = name[2:] if name.startswith("b/") else None
        elif (hunk := HUNK_RE.match(text)) is not None:
            line, left = int(hunk.group("start")), int(hunk.group("count") or 1)
        elif left > 0 and text.startswith("+"):
            if path is not None:
                out.append((path, line, text[1:]))
            line, left = line + 1, left - 1
    return out


def staged_lines(project: Scope) -> list[tuple[str, int, str]]:
    """The lines staged in the project's code folder, and in its documents folder when that is another repository
    and its text is public. Private documents may cite each other."""
    tops: list[Path] = []
    for folder in (project.code, None if project.private_docs else project.docs):
        if folder is not None and folder.is_dir():
            top = Path(git(folder, "rev-parse", "--show-toplevel").strip()).resolve()
            if top not in tops:
                tops.append(top)
    return [line for top in tops for line in parse_diff(git(top, "-c", "core.quotepath=off", "diff", "--cached", "-U0", "--no-color", "--no-ext-diff", "--src-prefix=a/", "--dst-prefix=b/"))]


def file_lines(paths: list[Path]) -> list[tuple[str, int, str]]:
    """Every line of the files named, a folder standing for the files under it."""
    out = []
    for path in paths:
        for file in sorted(f for f in path.rglob("*") if f.is_file() and ".git" not in f.parts) if path.is_dir() else [path]:
            try:
                out += [(str(file), n, text) for n, text in enumerate(file.read_text(encoding="utf-8").splitlines(), 1)]
            except UnicodeDecodeError:
                continue  # a binary file cites nothing
    return out


def is_private(config: Config, project: Scope, canonical: str) -> bool:
    """Whether a canonical ``scope:LOCAL`` names an entry of a private scope, or of the project's private documents."""
    name, local = canonical.split(":", 1)
    return config.scope(name).visibility == "private" or (name == project.name and private_entry(project, local))


def private_citations(config: Config, project: Scope, lines: list[tuple[str, int, str]]) -> list[str]:
    """One ``path:line: cites <scope:LOCAL>, which is private`` for each identifier of a private scope, or of the
    project's private documents, a line cites."""
    found = []
    for path, number, text in lines:
        for canonical in mentions(config, text, project):
            if is_private(config, project, canonical):
                found.append(f"{path}:{number}: cites {canonical}, which is private")
    return found


def domain_citations(config: Config, domain: Scope) -> list[str]:
    """One ``path:line: ...`` for each qualified mention, in the text a domain's families, rules and skills
    read, of a project or of a domain outside its ancestors. A domain may cite itself, its ancestors and the
    general scope alone, since it cannot depend on what a project may not use."""
    allowed, todo = {domain.name, config.general.name}, [domain.name]
    while todo:
        for parent in config.domains[todo.pop()].parents:
            if parent not in allowed and parent in config.domains:
                allowed.add(parent)
                todo.append(parent)
    named = [*domain.rules, *domain.skills, *(p for f in domain.families.values() for p in f.paths())]
    found = []
    for path, number, text in file_lines([p for p in domain.readable(named) if p.exists()]):
        for m in CITES_RE.finditer(text):
            other = config.scope(m.group("scope"))
            if other is not None and other.name not in allowed:
                found.append(f"{path}:{number}: domain '{domain.name}' cites {other.kind} '{other.name}' in {m.group(0)}, "
                             f"and a domain may cite its ancestors and itself alone")
    return found
