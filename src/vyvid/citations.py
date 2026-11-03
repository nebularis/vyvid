# SPDX-License-Identifier: MIT
"""Stop a public project's text from citing an entry of a private scope.

The lines a change adds are read, from the staged diff of the project's code folder and of its
documents folder when that is a repository of its own, or from the files named. Every identifier
they cite is resolved in the project's scope, and one that names an entry of a private scope is
refused. A mention that resolves to nothing is not this check's business.
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

from .config import Config, Scope
from .resolve import mentions

HUNK_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+(?P<start>\d+)(?:,(?P<count>\d+))? @@")


class GitError(Exception):
    """A git call the check depends on failed."""


def git(folder: Path, *args: str) -> str:
    done = subprocess.run(["git", *args], cwd=folder, capture_output=True, text=True,
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
    """The lines staged in the project's code folder, and in its documents folder when that is another repository."""
    tops: list[Path] = []
    for folder in (project.code, project.docs):
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


def private_citations(config: Config, project: Scope, lines: list[tuple[str, int, str]]) -> list[str]:
    """One ``path:line: cites <scope:LOCAL>, which is private`` for each identifier of a private scope a line cites."""
    found = []
    for path, number, text in lines:
        for canonical in mentions(config, text, project):
            if config.scope(canonical.split(":", 1)[0]).visibility == "private":
                found.append(f"{path}:{number}: cites {canonical}, which is private")
    return found
