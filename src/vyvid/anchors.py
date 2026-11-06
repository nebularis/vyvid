# SPDX-License-Identifier: MIT
# From LATTICE's tools/knowledge/anchors.py, relicensed MIT by its author.
"""Resolve a register's ``Pointer`` anchors to the current line ranges of the text they name.

A pointer never states a line number, because a line number is frozen when it is typed and goes
quietly wrong when the document above it changes. It names a stable anchor instead, and the
extractor resolves the anchor to a range on every build.

Anchor forms, comma-separated when there are several:

``path#slug``
    a Markdown section. ``slug`` is the heading's GitHub anchor, with the ``-1``, ``-2`` suffix
    GitHub gives a repeated heading, so it matches the anchor GitHub renders and the repository's
    own links use. The section runs from its heading to the line before the next heading of the
    same or a higher level, or to the end of the file.
``path::Name``
    a top-level ``def`` or ``class`` of a Python file, over its ``ast`` span, or the module
    docstring as ``path::__doc__``. In a TOML file, the table whose last key is ``Name``, so a
    ``mise`` task is ``mise.toml::check:knowledge``.
``path``
    a whole file, for Turtle, a manifest and anything without a structure to anchor to.

An anchor that does not resolve is an error and never a guessed range.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

HEADING_RE = re.compile(r"^ {0,3}(#{1,6})[ \t]+(.*?)[ \t]*$")
FENCE_RE = re.compile(r"^(\s*)(`{3,}|~{3,})(.*)$", re.S)
LINE_NUMBER_RE = re.compile(r":\d+(?:-\d+)?(?:,\d+(?:-\d+)?)*$")


class Unresolved(ValueError):
    """An anchor that names nothing in the current text."""


class Fences:
    """Whether each line in turn belongs to a code fence, as CommonMark has it, called once per line in order.

    A backtick fence's opening line holds no other backtick, so an inline code span that starts a line opens
    nothing. A fence closes on the same mark, at least as long, with only spaces after it. ``indent`` is the
    most a marker may be indented, and None is any, for a fence inside a list item."""

    def __init__(self, indent: int | None = 3):
        self.indent = indent
        self.opening = ""

    def __call__(self, line: str) -> bool:
        match = FENCE_RE.match(line)
        if match and self.indent is not None and len(match.group(1)) > self.indent:
            match = None
        if self.opening:
            if match and match.group(2)[0] == self.opening[0] and len(match.group(2)) >= len(self.opening) and not match.group(3).strip():
                self.opening = ""
            return True
        if match and not (match.group(2)[0] == "`" and "`" in match.group(3)):
            self.opening = match.group(2)
            return True
        return False


def _plain(heading: str) -> str:
    """The visible text of a heading, as GitHub slugs it: links and markup reduced to their words."""
    heading = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", heading)
    heading = re.sub(r"<[^>]+>", "", heading)
    heading = re.sub(r"\s+#+$", "", heading)
    return heading.replace("`", "").replace("*", "")


def base_slug(heading: str) -> str:
    text = _plain(heading).lower()
    return "".join(c for c in text if c.isalnum() or c in "-_ ").replace(" ", "-")


def headings(lines: list[str]) -> list[tuple[int, int, str]]:
    """Every heading outside a fenced block as ``(line, level, slug)``, repeated slugs suffixed
    ``-1``, ``-2`` exactly as GitHub's slugger does."""
    found: list[tuple[int, int, str]] = []
    seen: dict[str, int] = {}
    fenced = Fences()
    for number, line in enumerate(lines, 1):
        if fenced(line):
            continue
        match = HEADING_RE.match(line)
        if not match:
            continue
        original = slug = base_slug(match.group(2))
        while slug in seen:
            seen[original] = seen.get(original, 0) + 1
            slug = f"{original}-{seen[original]}"
        seen[slug] = 0
        found.append((number, len(match.group(1)), slug))
    return found


def section_end(found: list[tuple[int, int, str]], index: int, total: int) -> int:
    """The line before the next heading of the same or a higher level, or the last line."""
    _, level, _ = found[index]
    for line, other, _ in found[index + 1 :]:
        if other <= level:
            return line - 1
    return total


def sections(lines: list[str]) -> list[tuple[int, int, str]]:
    """Every Markdown section as ``(start, end, slug)``."""
    found = headings(lines)
    return [(found[i][0], section_end(found, i, len(lines)), found[i][2]) for i in range(len(found))]


def section_at(lines: list[str], number: int) -> tuple[int, int]:
    """The range of the section whose heading is on line ``number``."""
    for start, end, _ in sections(lines):
        if start == number:
            return start, end
    return number, number


def _read(root: Path, rel: str) -> list[str]:
    path = (root / rel).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError:
        raise Unresolved(f"{rel} lies outside the repository") from None
    if not path.is_file():
        raise Unresolved(f"{rel} is not a file")
    return path.read_text(encoding="utf-8", errors="replace").splitlines()


def _python(rel: str, lines: list[str], name: str) -> tuple[int, int]:
    tree = ast.parse("\n".join(lines))
    if name == "__doc__":
        first = tree.body[0] if tree.body else None
        if isinstance(first, ast.Expr) and isinstance(getattr(first, "value", None), ast.Constant) and isinstance(first.value.value, str):
            return first.lineno, first.end_lineno or first.lineno
        raise Unresolved(f"{rel} has no module docstring")
    hits = [
        n for n in tree.body
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and n.name == name
    ]
    if not hits:
        raise Unresolved(f"{rel} defines no top-level def or class '{name}'")
    if len(hits) > 1:
        raise Unresolved(f"{rel} defines '{name}' more than once, so the anchor is ambiguous")
    return hits[0].lineno, hits[0].end_lineno or hits[0].lineno


def _toml(rel: str, lines: list[str], name: str) -> tuple[int, int]:
    header = re.compile(r'^\[(?:[A-Za-z0-9_\-]+\.)*"?([^"\[\]]+?)"?\]\s*$')
    for i, line in enumerate(lines):
        match = header.match(line)
        if match and match.group(1) == name:
            for j in range(i + 1, len(lines)):
                if lines[j].startswith("["):
                    return i + 1, j
            return i + 1, len(lines)
    raise Unresolved(f"{rel} has no table '{name}'")


def resolve_part(root: Path, part: str) -> str:
    """One anchor resolved to ``path:start-end`` against the files as they are now."""
    part = part.strip().strip("`")
    if "::" in part:
        rel, name = part.split("::", 1)
        lines = _read(root, rel)
        start, end = (_toml if rel.endswith(".toml") else _python)(rel, lines, name)
    elif "#" in part:
        rel, slug = part.split("#", 1)
        lines = _read(root, rel)
        hit = next(((s, e) for s, e, found in sections(lines) if found == slug), None)
        if hit is None:
            raise Unresolved(f"{rel} has no heading with the anchor '{slug}'")
        start, end = hit
    elif LINE_NUMBER_RE.search(part):
        raise Unresolved(f"'{part}' names a line number, which goes stale, so name an anchor: path#slug, path::Name or path")
    else:
        rel = part
        lines = _read(root, rel)
        start, end = 1, max(len(lines), 1)
    return f"{rel}:{start}-{end}"


def resolve(root: Path, cell: str) -> tuple[list[str], list[str]]:
    """The ranges a ``Pointer`` cell names now, and one reason for each anchor that names nothing."""
    ranges: list[str] = []
    problems: list[str] = []
    for part in (p for p in cell.replace("`", "").split(",") if p.strip()):
        try:
            ranges.append(resolve_part(root, part))
        except (Unresolved, SyntaxError) as error:
            problems.append(f"'{part.strip()}': {error}")
    return ranges, problems


def parse_range(text: str) -> tuple[str, int, int | None]:
    """``path:start-end`` as ``(path, start, end)``. A bare path has no range."""
    match = re.fullmatch(r"(?P<path>.+?):(?P<start>\d+)(?:-(?P<end>\d+))?", text)
    if not match:
        return text, 1, None
    start = int(match.group("start"))
    return match.group("path"), start, int(match.group("end") or start)


# A pointer to more lines than this that names a whole file is a pointer defect, and read refuses it.
WHOLE_FILE = 200


def whole_file(root: Path, where: str) -> int | None:
    """The length of the file a range covers whole, when it is longer than WHOLE_FILE, else None.

    ``where`` is a label from read_ranges, so the row and pointed-at prefixes are dropped first."""
    path, start, end = parse_range(where.removeprefix("row ").removeprefix("pointed-at "))
    total = len((root / path).read_text(encoding="utf-8", errors="replace").splitlines())
    return total if start == 1 and end in (None, total) and total > WHOLE_FILE else None
