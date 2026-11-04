# SPDX-License-Identifier: MIT
# The prose rules from LATTICE's tools/writing_rules.py, relicensed MIT by its author, with the
# publication rules of this repository added.
"""Check this repository's text against its writing and publication rules.

Writing, on every tracked Markdown file (PRI-1): a semicolon in prose fails (STD-4), and a
hard-wrapped line warns (STD-3). Publication, on user-facing text, which is the README, every
document outside docs/developer/ and the code under src/ (STD-14, STD-15): a link or a path to a
working document fails, and so does a delivery identifier, a slice or question of a unit whose
prefix INDEX.md's Units table declares.

Prose only: a fenced code block, front matter, an HTML comment, an inline code span, a URL and an
HTML entity are never judged for semicolons.

    mise run check:writing
"""

from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

CODE_SPAN = re.compile(r"(`+)(?:(?!\1).)+?\1")
URL = re.compile(r"<?https?://\S+")
ENTITY = re.compile(r"&(?:[A-Za-z][A-Za-z0-9]*|#[0-9]+|#x[0-9A-Fa-f]+);")
LIST_ITEM = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")
FENCE = re.compile(r"^\s*(`{3,}|~{3,})")
FIELD = re.compile(r"^\*\*[^*\n]{1,60}?(?::\*\*|\*\*:)")


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    rule: str
    blocking: bool

    def __str__(self) -> str:
        return f"{self.path}:{self.line}: {self.rule}"


# A working document named by path, or linked, below docs/developer/. The folder named alone is not one.
WORKING = re.compile(r"(?:docs/)?developer/[A-Za-z]|\]\((?:\.\./)*(?:docs/)?developer/")


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    rule: str
    blocking: bool

    def __str__(self) -> str:
        return f"{self.path}:{self.line}: {self.rule}"


def kinds(lines: Sequence[str]) -> list[str]:
    """For each line: code, frontmatter, comment, blank, heading, table, quote, field, item,
    continuation or text. An item starts a list entry. A continuation is indented text inside a list
    entry. A field opens with a bold label, as a document's header lines do (**Status:** ...)."""
    out, fence, comment, front = [], None, False, bool(lines) and lines[0].strip() == "---"
    in_item = False
    for number, line in enumerate(lines):
        stripped = line.strip()
        if front:
            out.append("frontmatter")
            if number > 0 and stripped == "---":
                front = False
            continue
        opening = FENCE.match(line)
        if fence:
            out.append("code")
            if opening and opening.group(1)[0] == fence[0] and len(opening.group(1)) >= len(fence):
                fence = None
            continue
        if opening:
            fence = opening.group(1)
            out.append("code")
            continue
        if comment or stripped.startswith("<!--"):
            out.append("comment")
            comment = "-->" not in stripped
            continue
        if not stripped:
            out.append("blank")
            in_item = False if not line.startswith(" ") else in_item
            continue
        if stripped.startswith("#"):
            kind = "heading"
        elif stripped.startswith("|"):
            kind = "table"
        elif stripped.startswith(">"):
            kind = "quote"
        elif FIELD.match(stripped):
            kind, in_item = "field", False
        elif LIST_ITEM.match(line):
            kind, in_item = "item", True
        elif in_item and line.startswith(" "):
            kind = "continuation"
        else:
            kind, in_item = "text", False
        out.append(kind)
    return out


def prose(text: str) -> str:
    return ENTITY.sub("", URL.sub("", CODE_SPAN.sub("", text)))


def prose(text: str) -> str:
    return ENTITY.sub("", URL.sub("", CODE_SPAN.sub("", text)))


def user_facing(path: str) -> bool:
    return path in ("README.md", "SECURITY.md") or path.startswith("src/") or (
        path.endswith(".md") and path.startswith("docs/") and not path.startswith("docs/developer/"))


def delivery_ids(root: Path) -> re.Pattern[str] | None:
    """A slice or question of any unit INDEX.md's Units table declares, such as VYD-2 or VYD-Q10."""
    index = root / "docs/developer/INDEX.md"
    prefixes = re.findall(r"^\| [a-z0-9-]+ \| ([A-Z][A-Z0-9]*) \|", index.read_text(encoding="utf-8"), re.M) if index.exists() else []
    return re.compile(rf"\b(?:{'|'.join(map(re.escape, prefixes))})-(?:Q)?\d+[a-z]?\b") if prefixes else None


def check_file(path: str, text: str, ids: re.Pattern[str] | None) -> list[Finding]:
    lines = text.splitlines()
    findings = []
    if path.endswith(".md"):
        line_kinds = kinds(lines)
        for number, (kind, line) in enumerate(zip(line_kinds, lines), 1):
            if kind in ("code", "frontmatter", "comment", "blank"):
                continue
            if ";" in prose(line):
                findings.append(Finding(path, number, "a semicolon in prose. Use a period or a comma (STD-4)", True))
            previous = line_kinds[number - 2] if number > 1 else "blank"
            if kind in ("text", "continuation") and previous in ("text", "item", "continuation", "quote") \
                    and not lines[number - 2].endswith("  "):
                findings.append(Finding(path, number, "a hard-wrapped line. Keep a paragraph or a list entry on one line (STD-3)", False))
    if user_facing(path):
        for number, line in enumerate(lines, 1):
            if WORKING.search(line):
                findings.append(Finding(path, number, "user-facing text refers to a working document (STD-14)", True))
            if ids and (found := ids.search(line)):
                findings.append(Finding(path, number, f"user-facing text names the delivery identifier {found.group(0)} (STD-15)", True))
    return findings


def tracked(root: Path) -> list[str]:
    out = subprocess.run(["git", "ls-files", "-co", "--exclude-standard"], cwd=root, capture_output=True, text=True, check=True).stdout
    return [p for p in out.splitlines() if p.endswith((".md", ".py", ".toml")) and (root / p).is_file()]


def main(argv: Sequence[str] | None = None) -> int:
    root = Path.cwd()
    ids = delivery_ids(root)
    findings = [f for path in tracked(root) for f in check_file(path, (root / path).read_text(encoding="utf-8"), ids)]
    for finding in findings:
        print(f"{'' if finding.blocking else 'warning: '}{finding}")
    blocking = [f for f in findings if f.blocking]
    print(f"writing and publication rules: {len(blocking)} failure(s), {len(findings) - len(blocking)} warning(s)")
    return 1 if blocking else 0


if __name__ == "__main__":
    sys.exit(main())
