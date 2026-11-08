# SPDX-License-Identifier: MIT
# Ported from LATTICE's tools/work_board.py, relicensed MIT by its author.
"""Where the work is: the slice boards of the status records, read across every branch.

A status record's slice board is the one place a slice's state is written. This module reads the boards at
the tip of every local and remote branch without a checkout, joins the rows per slice, and prints where
everything is. It also writes the generated regions of the project's index and roadmap from the records.

A state cell opens with a word of the ladder and the day it was reached, newest first, so
"merged 2026-10-28, built 2026-10-25" is a trail. The join across branches takes the row furthest along the
ladder, then the latest day. Two branches other than the trunk both building one slice is a double claim,
printed and never chosen. A branch's row behind the trunk's is stale, not a claim.

**A branch's text is data.** Another branch's files are read as blobs through ``git cat-file`` and parsed, and
nothing in them is run, joined into a command or used as a path. Every ``git`` call is an argument list.
Names that come from a branch are used only as text in the output, and the files this module writes are
named by the configuration, never by a record.
"""

from __future__ import annotations

import datetime
import json
import os
import re
import subprocess
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional, Sequence

from .settings import NUMBER_WORDS, Work

SEPARATOR_RE = re.compile(r"^\|[\s:|-]*\|$")
STATUS_LINE_RE = re.compile(r"^\*\*Status:\*\*[ \t]*(.+?)[ \t]*$", re.M)  # never past its line
PREFIX_RE = re.compile(r"^\*\*Prefix:\*\*\s*([A-Z]{2,5}(?:,\s*[A-Z]{2,5})*)\s*$", re.M)
LINK_RE = re.compile(r"\[([^\]]*)\]\([^)]*\)")
REGISTER_ROW_RE = re.compile(r"^\| ([A-Z]+-\d+) \| (.*)$")
ENCODING = {"encoding": "utf-8", "newline": "\n"}


class NotARepository(Exception):
    """The board's folders are in no git repository, so no branch can be read."""


# ---- the board -----------------------------------------------------------------------------------

@dataclass(frozen=True)
class Row:
    """One slice's row. ``trail`` is newest first, ``state`` and ``day`` its head. A cell that does not
    open with a word of the ladder parses as state None, which the board prints and the check refuses."""
    unit: str
    id: str
    deliverable: str
    state: Optional[str]
    day: str
    trail: tuple[tuple[str, str], ...]
    blocked_on: str
    raw: str
    line: int
    rank: int = -2

    @property
    def key(self) -> tuple[int, str]:
        return (self.rank, self.day)


@dataclass(frozen=True)
class Board:
    unit: str
    columns: tuple[str, ...]
    rows: tuple[Row, ...]
    line: int
    heading: str = ""

    @property
    def anchor(self) -> str:
        """The slug of the heading above the board, as GitHub renders it, so a pointer names a
        section that survives an edit rather than a line number."""
        slug = re.sub(r"[^a-z0-9 -]", "", self.heading.lower()).strip().replace(" ", "-")
        return f"#{slug}" if slug else ""


@dataclass(frozen=True)
class Unit:
    """A record as its status record and plan describe it at one ref."""
    id: str
    kind: str
    state: Optional[str]
    day: str
    status_text: str
    board: Optional[Board]
    prefix: str = ""
    next: str = ""


@dataclass(frozen=True)
class Branch:
    """A branch name with the tip the board reads, folded over its local and remote refs. ``drift``
    says how the local branch stands to its upstream, so an unpushed or unpulled worktree is seen."""
    name: str
    tip: str
    day: str
    local: bool
    remote: bool
    drift: str
    worktree: str = ""
    ahead_of_main: int = 0


@dataclass
class Joined:
    """One slice across branches. ``rows`` maps branch name to its row."""
    unit: str
    id: str
    main_name: str = "main"
    rows: dict[str, Row] = field(default_factory=dict)

    @property
    def main(self) -> Optional[Row]:
        return self.rows.get(self.main_name)

    @property
    def winner(self) -> tuple[str, Row]:
        return max(self.rows.items(), key=lambda item: (item[1].key, item[0] == self.main_name, item[0]))

    @property
    def claims(self) -> list[str]:
        """The branches other than the trunk whose row is the one being worked, which is the third word."""
        return sorted(name for name, row in self.rows.items() if row.state == self.working and name != self.main_name)

    working: str = ""

    @property
    def stale(self) -> list[str]:
        base = self.main
        return sorted(name for name, row in self.rows.items() if base and row.key < base.key and name != self.main_name)

    @property
    def moved(self) -> list[str]:
        """Branches whose row is further on than the trunk's, or that hold a row it lacks."""
        base = self.main
        return sorted(name for name, row in self.rows.items() if name != self.main_name and (base is None or row.key > base.key))


def cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def table(headers: Sequence[str], rows: Iterable[Sequence[str]]) -> list[str]:
    out = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    out += ["| " + " | ".join(str(c).replace("|", "\\|") for c in row) + " |" for row in rows]
    return out


# The key under which the boards of an unpushed current branch are read, which no branch name can equal because it holds a space.
THIS_CHECKOUT = "this checkout"


def cut_label(text: str, limit: int = 30) -> str:
    """A bar's label from a deliverable: the whole text within ``limit`` characters, otherwise the longest prefix that ends at a comma,
    otherwise the last whole word, and a single word longer than ``limit`` is cut at ``limit``."""
    if len(text) <= limit:
        return text
    comma = text.rfind(",", 0, limit)
    if comma > 0:
        return text[:comma + 1]
    if text[limit].isspace():
        return text[:limit]
    space = text.rfind(" ", 0, limit)
    return text[:space] if space > 0 else text[:limit]


def plain(cell: str, limit: int = 0) -> str:
    """A cell as the generated tables carry it: a link reduced to its text, since the record's
    relative links do not resolve from another file, and no semicolon, since the writing rule
    reads a generated line as prose."""
    text = LINK_RE.sub(r"\1", cell).replace(";", ",").strip()
    return text[:limit] if limit else text


def words_or(words: Sequence[str]) -> str:
    return words[0] if len(words) == 1 else ", ".join(words[:-1]) + " or " + words[-1]


# ---- the rules: the ladder, the grammar and the roll-up --------------------------------------------

class Rules:
    """The pure part: how a record's text reads under one project's settings."""

    def __init__(self, work: Work):
        self.work = work
        self.state_re = re.compile(r"^(" + "|".join(re.escape(s) for s in work.states) + r")\b\s*(\d{4}-\d{2}-\d{2})?\s*(.*)$")
        title = work.unit.capitalize()
        self.unit_type_re = re.compile(rf"^\*\*{re.escape(title)} type:\*\*\s*(.+?)\s*$", re.M)
        self.unit_id_re = re.compile(rf"^\*\*{re.escape(title)} ID:\*\*[^\n]*$", re.M)
        self.title, self.piece = title, work.piece.capitalize()

    def valid_id(self, slice_id: str) -> bool:
        return self.work.slice_id.fullmatch(slice_id) is not None

    def rank(self, state: Optional[str]) -> int:
        return self.work.rank[state] if state else -2

    def parse_state(self, cell: str) -> tuple[Optional[str], str, tuple[tuple[str, str], ...]]:
        """The state, the day and the trail of a cell. The trail stops at the first item that is not
        a state word, so free text after the dated word is kept out of it."""
        trail: list[tuple[str, str]] = []
        for item in cell.split(","):
            m = self.state_re.match(item.strip().strip("*").strip())
            if not m:
                break
            trail.append((m.group(1), m.group(2) or ""))
            if m.group(3) and not m.group(3).startswith(","):
                break
        if not trail:
            return None, "", ()
        return trail[0][0], trail[0][1], tuple(trail)

    def find_board(self, unit: str, text: str) -> Optional[Board]:
        """The first table with a state column and an identifier column. The standard board is
        ``Slice, Deliverable, State, Blocked on``, the first word being the name of the smallest level. A board
        headed ``#`` keeps its ids there, and its slice column is then the deliverable, which is how older boards are written."""
        lines = text.splitlines()
        heading = ""
        name = self.work.piece
        for number, line in enumerate(lines, 1):
            if line.startswith("#"):
                heading = line.lstrip("#").strip()
            if not line.startswith("|") or number >= len(lines) or not SEPARATOR_RE.match(lines[number].strip()):
                continue
            header = cells(line)
            lower = [h.lower() for h in header]
            state_at = next((i for i, h in enumerate(lower) if h in ("state", "status")), None)
            if state_at is None:
                continue
            named = "slice" if "slice" in lower else name
            if "#" in lower:
                id_at = lower.index("#")
                deliverable_at = lower.index(named) if named in lower else None
            elif named in lower:
                id_at = lower.index(named)
                deliverable_at = next((i for i, h in enumerate(lower) if h in ("deliverable", "delivers", "scope")), None)
            else:
                continue
            blocked_at = next((i for i, h in enumerate(lower) if h.startswith("blocked")), None)
            rows: list[Row] = []
            for offset, body in enumerate(lines[number + 1:], number + 2):
                if not body.startswith("|"):
                    break
                row = cells(body)
                if len(row) < len(header):
                    row += [""] * (len(header) - len(row))
                raw_id = row[id_at].strip("`* ")
                slice_id = raw_id.split(" ")[0].split("(")[0].strip("`*,;:") or raw_id
                state, day, trail = self.parse_state(row[state_at])
                rows.append(Row(unit, slice_id, row[deliverable_at] if deliverable_at is not None else "",
                                state, day, trail, row[blocked_at] if blocked_at is not None else "",
                                row[state_at], offset, self.rank(state)))
            return Board(unit, tuple(header), tuple(rows), number, heading)
        return None

    def rollup(self, rows: Iterable[Row]) -> Optional[tuple[str, str]]:
        """The state a board gives its record, the rule its Status word is held to. The working word while any
        row is on it, dated by the earliest, the day the work started. Otherwise, once a row has reached the first
        done word, the lowest word the rows at done or later share, dated by the latest, since a planned row left
        over is the next slice, not work under way. Otherwise the held word if any row is, else the highest of the
        words before. Dropped rows count only when every row is dropped. None for a board with no row a word parses."""
        w = self.work
        dropped = w.aside[1] if len(w.aside) > 1 else None
        rows = [r for r in rows if r.state]
        if not rows:
            return None
        if dropped and all(r.state == dropped for r in rows):
            return dropped, ""
        rows = [r for r in rows if r.state != dropped]
        working = [r.day for r in rows if r.state == w.dated_from]
        if working:
            return w.dated_from, min((d for d in working if d), default="")
        floor = w.rank[w.done_from]
        done = [r for r in rows if r.state in w.ladder and w.rank[r.state] >= floor]
        if done:
            return w.ladder[min(w.rank[r.state] for r in done)], max((r.day for r in done if r.day), default="")
        if any(r.state == w.aside[0] for r in rows):
            return w.aside[0], ""
        return w.ladder[max(w.rank[r.state] for r in rows if r.state in w.ladder)], ""

    def next_of(self, board: Optional[Board]) -> str:
        if not board:
            return ""
        return next((row.id for row in board.rows if row.state in self.work.open), "")

    def parse_unit(self, unit: str, status_text: str, plan_text: str = "") -> Unit:
        status_line = STATUS_LINE_RE.search(status_text)
        state, day = None, ""
        text = status_line.group(1) if status_line else ""
        if status_line:
            state, day, _ = self.parse_state(text)
        kind_match = self.unit_type_re.search(plan_text)
        kind = re.split(r"[,(]", kind_match.group(1))[0].strip().lower() if kind_match else self.work.unit
        prefix = PREFIX_RE.search(plan_text)
        board = self.find_board(unit, status_text)
        return Unit(unit, kind, state, day, text, board, prefix.group(1) if prefix else "", self.next_of(board))

    def join(self, boards: dict[str, dict[str, Unit]]) -> dict[tuple[str, str], Joined]:
        """The rows per slice across branches. A row whose id is outside the grammar is a board not yet
        normalised, never a slice the other branches lack, so it is left out here and counted by ``off_grammar``."""
        out: dict[tuple[str, str], Joined] = {}
        for branch, units in boards.items():
            for unit in units.values():
                for row in (unit.board.rows if unit.board else ()):
                    if self.valid_id(row.id):
                        out.setdefault((unit.id, row.id), Joined(unit.id, row.id, self.work.main, working=self.work.dated_from)).rows[branch] = row
        return dict(sorted(out.items()))

    def off_grammar(self, boards: dict[str, dict[str, Unit]]) -> dict[str, int]:
        """Per branch, how many board rows carry an id outside the grammar, which says the branch has
        not been normalised and renamed since merging the trunk."""
        return {branch: sum(1 for unit in units.values() for row in (unit.board.rows if unit.board else ()) if not self.valid_id(row.id))
                for branch, units in boards.items()}

    def moves_text(self, moved: list[str], off: int) -> str:
        c = self.work.commands
        if moved:
            return ", ".join(moved) + (f", and {off} rows not on the grammar" if off else "")
        return f"board not on the grammar, {off} rows. Run `{c['normalise']}` and `{c['rename']}` there" if off else "no mark"

    def unit_state(self, name: str, base: Optional[Unit], boards: dict[str, dict[str, Unit]]) -> str:
        """A record's state as a cell: the base's, then each branch whose record is further on, furthest
        first, so a record built on a branch never reads planned. A branch whose record has no
        state word, or is behind, is left out, as the Work table leaves a stale row out."""
        def text(unit: Unit) -> str:
            return f"{unit.state or '?'} {unit.day}".strip()

        def key(unit: Optional[Unit]) -> tuple[int, str]:
            return (self.rank(unit.state), unit.day) if unit else (-2, "")
        own = text(base) if base else "?"
        others: dict[str, list[tuple[int, str]]] = {}
        for branch, units in boards.items():
            unit = units.get(name)
            if branch not in (self.work.main, THIS_CHECKOUT) and unit and unit.state and key(unit) > key(base):
                others.setdefault(text(unit), []).append((self.rank(unit.state), branch))
        ordered = sorted(others.items(), key=lambda kv: (-max(r for r, _ in kv[1]), kv[0]))
        return own + "".join(f" · {state} on {', '.join(sorted(b for _, b in hold))}" for state, hold in ordered)

    def state_text(self, row: Row) -> str:
        if row.state is None:
            return f"? {plain(row.raw, 40)}"
        return f"{row.state} {row.day}".strip()

    # ---- the gantt ----

    def gantt_key(self) -> list[str]:
        w = self.work
        early = [s for s in w.ladder[w.ladder.index(w.dated_from) + 1:] if s not in w.closed]
        return ["```mermaid", "flowchart LR",
                f'    K1["{w.dated_from}"]:::active --- K2["{words_or(early) if early else w.dated_from}"]:::open --- K3["{words_or(w.closed[:len(w.closed) - len(w.aside[1:])] or w.closed)}"]:::done --- K4["{w.aside[0]}"]:::crit',
                "    classDef active fill:#4e9af1,stroke:#1f5fbf,color:#000", "    classDef open fill:#f2c14e,stroke:#b8860b,color:#000",
                "    classDef done fill:#8fcf8f,stroke:#2f7d32,color:#000", "    classDef crit fill:#f28b82,stroke:#b23a30,color:#000", "```"]

    def gantt_text(self, joined: dict[tuple[str, str], Joined], title: str, names: Optional[Iterable[str]] = None,
                   completed: bool = False) -> list[str]:
        """One bar per dated slice of the named records, from the earliest day in its trail to the latest,
        a section per record, coloured by state as the key says. The chart runs from the first day any of
        its slices has, so a group's chart goes back to its first commit. With ``completed`` only
        closed slices are drawn. An undated slice is never drawn, since a bar invented for it would be a
        plan nobody made. Nothing is returned where nothing is dated."""
        w = self.work
        wanted = set(names) if names is not None else None
        by_unit: dict[str, list[str]] = {}
        for (unit, slice_id), j in joined.items():
            if wanted is not None and unit not in wanted:
                continue
            _, row = j.winner
            days = sorted(d for _, d in row.trail if d)
            if not days or row.state is None:
                continue
            closed = row.state in w.closed
            if completed and not closed:
                continue
            tag = "done" if closed else "crit" if row.state == w.aside[0] else "active" if row.state == w.dated_from else ""
            start, end = days[0], days[-1]
            if start == end:
                end = (datetime.date.fromisoformat(end) + datetime.timedelta(days=1)).isoformat()
            label = re.sub(r"\s+", " ", re.sub(r"[^A-Za-z0-9 .-]", " ", re.sub(r"'s\b", "", f"{slice_id} {cut_label(row.deliverable)}"))).strip()
            ident = re.sub(r"[^a-z0-9]", "", slice_id.lower()) or "s"
            by_unit.setdefault(unit, []).append(f"    {label} :{tag + ', ' if tag else ''}{ident}, {start}, {end}")
        if not by_unit:
            return []
        lines = ["```mermaid", GANTT_THEME, "gantt", f"    title {title}", "    dateFormat YYYY-MM-DD", "    axisFormat %d %b"]
        for unit, bars in sorted(by_unit.items()):
            lines.append(f"    section {unit}")
            lines += bars
        lines.append("```")
        return lines

    def chart_groups(self, units: dict[str, Unit], joined: dict[tuple[str, str], Joined], names: Iterable[str]) -> list[tuple[str, list[str]]]:
        """How the records share charts: a group with every record named after it, a record outside a
        group with ``chart_after`` dated slices or more on its own, and the rest together as the smaller ones."""
        w = self.work
        names = list(names)
        dated = {n: sum(1 for (u, _), j in joined.items() if u == n and any(d for _, d in j.winner[1].trail)) for n in names}
        groups_of = sorted((n for n in names if w.group and units[n].kind.startswith(w.group)), key=len, reverse=True)
        owned: dict[Optional[str], list[str]] = {}
        for n in names:
            parent = next((e for e in groups_of if n == e or n.startswith(e + "-")), None)
            owned.setdefault(parent, []).append(n)
        groups: list[tuple[str, list[str]]] = [(f"the {e} {w.group}", owned[e]) for e in sorted(groups_of) if e in owned]
        small: list[str] = []
        for n in owned.get(None, []):
            if dated[n] >= w.chart_after:
                groups.append((n, [n]))
            else:
                small.append(n)
        if small:
            groups.append((f"the smaller {w.unit}s", small))
        return groups

    def charts_text(self, units: dict[str, Unit], joined: dict[tuple[str, str], Joined], names: Iterable[str], completed: bool = False) -> list[str]:
        """The key once, then one chart per group, each from its first day. A group with nothing dated draws nothing."""
        lines: list[str] = list(self.gantt_key())
        for title, members in self.chart_groups(units, joined, names):
            chart = self.gantt_text(joined, title.capitalize() if title[0].islower() else title, members, completed)
            if chart:
                lines += [""] + chart
        return lines

    # ---- generated regions ----

    def render_index(self, existing: str, region: str) -> str:
        begin, end = self.work.markers["index_begin"], self.work.markers["index_end"]
        body = f"{begin}\n\n{region}\n{end}"
        if begin in existing and end in existing:
            head, _, rest = existing.partition(begin)
            _, _, tail = rest.partition(end)
            return head + body + tail
        return existing.rstrip("\n") + "\n\n" + body + "\n"

    def markers_for(self, name: str) -> tuple[str, str]:
        return (self.work.markers["roadmap_begin"].replace("{name}", name), self.work.markers["roadmap_end"].replace("{name}", name))

    def render_regions(self, existing: str, regions: dict[str, str]) -> str:
        out = existing
        for name, body in regions.items():
            begin, end = self.markers_for(name)
            block = f"{begin}\n\n{body}\n{end}"
            if begin in out and end in out:
                head, _, rest = out.partition(begin)
                _, _, tail = rest.partition(end)
                out = head + block + tail
            else:
                out = out.rstrip("\n") + "\n\n" + block + "\n"
        return out

    # ---- the check ----

    def findings(self, rel: str, text: str) -> list[str]:
        """What is wrong with one status record: its Status line and every row of its board open with a
        state word, dated from the dated word on, each slice id is in the grammar, and the Status line is what
        the board rolls up to."""
        w = self.work
        messages: list[str] = []
        unit = self.parse_unit(Path(rel).stem, text)
        if unit.status_text and unit.state is None:
            messages.append(f"{rel}: the Status line opens with '{unit.status_text[:30]}', not a word of {', '.join(w.states)}, then its day")
        rolled = self.rollup(unit.board.rows) if unit.board else None
        if rolled and unit.state and (unit.state, unit.day) != rolled:
            said, given = f"{unit.state} {unit.day}".strip(), f"{rolled[0]} {rolled[1]}".strip()
            messages.append(f"{rel}: the Status line reads '{said}', its board rolls up to '{given}'. Run `{w.commands['normalise']}`")
        for row in (unit.board.rows if unit.board else ()):
            where = f"{rel}:{row.line}: {row.id}"
            if row.state is None:
                messages.append(f"{where}: the State cell opens with '{plain(row.raw, 30)}', not a word of {', '.join(w.states)}. Run `{w.commands['normalise']}` for the historic words")
            elif row.state in w.dated and not row.day:
                messages.append(f"{where}: {row.state} needs the day it was reached, as `{row.state} YYYY-MM-DD`")
            if not self.valid_id(row.id):
                messages.append(f"{where}: a slice id must match {w.slice_pattern}. Run `{w.commands['rename']}` for the historic ids")
        return messages


GANTT_THEME = ('%%{init: {"themeVariables": {"taskBkgColor": "#f2c14e", "taskBorderColor": "#b8860b", "taskTextColor": "#000000", '
               '"activeTaskBkgColor": "#4e9af1", "activeTaskBorderColor": "#1f5fbf", "activeTaskBorderColor": "#1f5fbf", '
               '"doneTaskBkgColor": "#8fcf8f", "doneTaskBorderColor": "#2f7d32", "critBkgColor": "#f28b82", "critBorderColor": "#b23a30", '
               '"taskTextDarkColor": "#000000", "taskTextLightColor": "#000000"}}}%%')


# ---- the repository ---------------------------------------------------------------------------------

class Repo(Rules):
    """The rules over a git repository: its branches, its working tree and the files it writes."""

    def __init__(self, root: Path, work: Work, registers: Optional[dict[str, list[Path]]] = None, exceptions: Sequence[Path] = ()):
        super().__init__(work)
        self.root = Path(os.path.realpath(root))
        self.registers = registers or {}
        self.exceptions = tuple(exceptions)

    @classmethod
    def open(cls, work: Work, **kwargs) -> "Repo":
        """The repository holding the status folder, or the nearest folder above it that exists."""
        folder = work.status
        while not folder.exists() and folder != folder.parent:
            folder = folder.parent
        done = subprocess.run(["git", "-C", str(folder), "rev-parse", "--show-toplevel"], capture_output=True)
        if done.returncode:
            raise NotARepository(f"{work.status} is in no git repository")
        return cls(Path(os.fsdecode(done.stdout.strip())), work, **kwargs)

    # ---- git and paths ----

    def git(self, *args: str, check: bool = True) -> str:
        result = subprocess.run(["git", "-c", "i18n.logOutputEncoding=UTF-8", *args], cwd=self.root, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if check and result.returncode:
            raise RuntimeError(f"git {' '.join(args)}: {result.stderr.strip()}")
        return result.stdout

    def rel(self, path: Path) -> str:
        """The path relative to the repository's root, in POSIX form."""
        return Path(os.path.realpath(path)).relative_to(self.root).as_posix()

    def link(self, target: Path, source: Path) -> str:
        """A path from the folder of ``source`` to ``target``, for a link in a generated file."""
        return Path(os.path.relpath(os.path.realpath(target), os.path.realpath(source.parent))).as_posix()

    def contained(self, path: Path) -> bool:
        return Path(os.path.realpath(path)).is_relative_to(self.root)

    def records(self, folder: Path) -> list[Path]:
        """The Markdown files directly in ``folder``, less any link that leaves the repository."""
        return [p for p in sorted(folder.glob("*.md"), key=lambda p: p.name) if p.is_file() and self.contained(p)] if folder.is_dir() else []

    def writable(self, path: Path) -> bool:
        """Whether the module may write the path: inside the repository and outside every ``.git``."""
        real = Path(os.path.realpath(path))
        return real.is_relative_to(self.root) and ".git" not in real.relative_to(self.root).parts

    def write(self, path: Path, text: str) -> None:
        if not self.writable(path):
            raise PermissionError(f"{path} is outside the repository or inside its git directory, so it is not written")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, **ENCODING)

    # ---- branches ----

    def remotes(self) -> dict[str, str]:
        out: dict[str, str] = {}
        for line in self.git("config", "--get-regexp", r"^remote\..*\.url$", check=False).splitlines():
            key, _, url = line.partition(" ")
            out[key.split(".")[1]] = url.strip()
        return out

    def worktrees(self) -> dict[str, str]:
        out: dict[str, str] = {}
        path = ""
        for line in self.git("worktree", "list", "--porcelain", check=False).splitlines():
            if line.startswith("worktree "):
                path = line[9:]
            elif line.startswith("branch refs/heads/"):
                out[line[18:]] = path
        return out

    def branches(self, published: bool = False) -> list[Branch]:
        """Every branch, local or remote, one row each. Remotes that share a URL are one remote. Where
        the local and remote tips differ, the tip read is the one further on, and ``drift`` says so.
        With ``published`` only the branches known from a remote are returned, each at its remote tip,
        so nothing of a local-only branch or of a local commit not pushed is read. It reads refs alone."""
        main = self.work.main
        urls = self.remotes()
        seen_urls: dict[str, str] = {}
        folded = {name: seen_urls.setdefault(url, name) for name, url in urls.items()}
        local: dict[str, tuple[str, str]] = {}
        remote: dict[str, tuple[str, str]] = {}
        for line in self.git("for-each-ref", "--format=%(refname) %(objectname) %(committerdate:short)", "refs/heads", "refs/remotes").splitlines():
            ref, sha, day = line.rsplit(" ", 2)
            if ref.startswith("refs/heads/"):
                local[ref[11:]] = (sha, day)
            else:
                rest = ref[13:]
                remote_name, _, name = rest.partition("/")
                if not name or name == "HEAD" or folded.get(remote_name, remote_name) != remote_name:
                    continue
                remote.setdefault(name, (sha, day))
        if published:
            local = {}
        trees = {} if published else self.worktrees()
        main_sha = local.get(main, remote.get(main, ("", "")))[0]
        out: list[Branch] = []
        for name in sorted(set(local) | set(remote)):
            l, r = local.get(name), remote.get(name)
            if published:
                tip, day, drift = r[0], r[1], "pushed"
            elif l and r and l[0] != r[0]:
                ahead, behind = self.git("rev-list", "--count", "--left-right", f"{l[0]}...{r[0]}").split()
                tip, day = (l if int(ahead) else r)
                drift = f"local ahead {ahead}, behind {behind}" if int(ahead) and int(behind) else (
                    f"local ahead {ahead}, not pushed" if int(ahead) else f"local behind {behind}, not pulled")
            elif l and r:
                tip, day, drift = l[0], l[1], "pushed"
            elif l:
                tip, day, drift = l[0], l[1], "local only"
            else:
                tip, day, drift = r[0], r[1], "remote only"
            ahead_of_main = int(self.git("rev-list", "--count", f"{main_sha}..{tip}").strip()) if main_sha else 0
            out.append(Branch(name, tip, day, bool(l), bool(r), drift, trees.get(name, ""), ahead_of_main))
        return out

    def read_blobs(self, shas: Sequence[str]) -> dict[str, str]:
        """The text of objects by id through one ``git cat-file --batch`` call. Nothing in them is run."""
        if not shas:
            return {}
        result = subprocess.run(["git", "cat-file", "--batch"], cwd=self.root, input=("\n".join(shas) + "\n").encode(), capture_output=True)
        out: dict[str, str] = {}
        data = result.stdout
        pos = 0
        while pos < len(data):
            end = data.index(b"\n", pos)
            head = data[pos:end].split()
            pos = end + 1
            if len(head) < 3:
                continue
            size = int(head[2])
            out[head[0].decode()] = data[pos:pos + size].decode("utf-8", errors="replace")
            pos += size + 1
        return out

    def units_at(self, tip: str) -> dict[str, Unit]:
        """Every record's status file, and its plan where one exists, read at ``tip`` without a checkout.
        Only regular files directly in the two folders are read, never a link."""
        status_dir, plans_dir = self.rel(self.work.status), self.rel(self.work.plans)
        listing = self.git("ls-tree", "-r", "-z", "--format=%(objectmode) %(objectname) %(path)", tip, "--", status_dir, plans_dir, check=False)
        wanted: dict[str, tuple[str, str]] = {}
        for entry in listing.split("\0"):
            mode, _, rest = entry.partition(" ")
            sha, _, path = rest.partition(" ")
            if mode not in ("100644", "100755") or not path.endswith(".md"):
                continue
            parent = Path(path).parent.as_posix()
            if parent == status_dir:
                wanted[sha] = ("status", Path(path).stem)
            elif parent == plans_dir:
                wanted[sha] = ("plan", Path(path).stem)
        blobs = self.read_blobs(list(wanted))
        statuses: dict[str, str] = {}
        plans: dict[str, str] = {}
        for sha, (kind, name) in wanted.items():
            (statuses if kind == "status" else plans)[name] = blobs.get(sha, "")
        return {name: self.parse_unit(name, text, plans.get(name, "")) for name, text in sorted(statuses.items())}

    def units_here(self) -> dict[str, Unit]:
        """The records as the working tree has them, which is what ``build`` reads."""
        out: dict[str, Unit] = {}
        for path in self.records(self.work.status):
            plan = self.work.plans / path.name
            out[path.stem] = self.parse_unit(path.stem, path.read_text(encoding="utf-8"),
                                             plan.read_text(encoding="utf-8") if plan.is_file() and self.contained(plan) else "")
        return out

    # ---- measuring ----

    def share_on_main(self, tip: str) -> str:
        """The content measure: of the lines the branch added since its merge-base, the share present on
        the trunk today. Squash merges leave ancestry silent, and this is the answer."""
        main = self.work.main
        base = self.git("merge-base", main, tip).strip()
        added = present = 0
        for path in filter(None, self.git("diff", "--name-only", "-z", base, tip).split("\0")):
            before = set(self.git("show", f"{base}:{path}", check=False).splitlines())
            after = set(self.git("show", f"{tip}:{path}", check=False).splitlines())
            on_main = set(self.git("show", f"{main}:{path}", check=False).splitlines())
            new = after - before
            added += len(new)
            present += len(new & on_main)
        return f"{present / added:.0%} of {added}" if added else "nothing added"

    def commit_of(self, tip: str, row: Row) -> str:
        """The commit that set the row's current state on that branch, read from git rather than written."""
        path = self.rel(self.work.status / f"{row.unit}.md")
        needle = f"{row.state} {row.day}".strip()
        return self.git("log", "-1", "--format=%h", f"-S{needle}", tip, "--", path, check=False).strip()

    # ---- rendering ----

    def board_text(self, show_all: bool, measure: bool, commits: bool, state: Optional[str] = None) -> str:
        """The live board: records, work and branches, filtered to what differs from the trunk unless ``show_all``."""
        w, main = self.work, self.work.main
        unit, piece = self.title, self.piece
        found = self.branches()
        boards = {b.name: self.units_at(b.tip) for b in found}
        joined = self.join(boards)
        main_units = boards.get(main, {})
        lines = [f"# Work board, {len(found)} branches", "", f"## {unit}s", ""]
        unit_rows = []
        for name, record in main_units.items():
            on = sorted({b for (u, _), j in joined.items() if u == name for b in j.moved})
            if show_all or on:
                unit_rows.append((name, record.kind, self.unit_state(name, record, boards), record.next, ", ".join(on)))
        lines += table((unit, "Kind", "State", "Next", "Moved on"), unit_rows)
        lines += ["", "## Work", ""]
        work_rows = []
        for (name, slice_id), j in joined.items():
            winner_branch, winner = j.winner
            if state is not None and not re.match(rf"{re.escape(state)}\b", winner.state or "", re.I):
                continue
            flags = []
            if len(j.claims) > 1:
                flags.append("double claim: " + ", ".join(j.claims))
            if j.stale:
                flags.append("stale: " + ", ".join(j.stale))
            if winner.state is None:
                flags.append("unparsed")
            if show_all or j.moved or len(j.claims) > 1 or winner.state is None:
                where = winner_branch + (f" at {self.commit_of(next(b.tip for b in found if b.name == winner_branch), winner)}" if commits else "")
                work_rows.append((slice_id, name, plain(winner.deliverable, 60), self.state_text(winner), where, plain(winner.blocked_on), ". ".join(flags)))
        lines += table((piece, unit, "Deliverable", "State", "Where", "Blocked on", "Flags"), work_rows)
        lines += ["", "## Branches", ""]
        branch_rows = []
        off = self.off_grammar(boards)
        for b in found:
            if b.name == main or (b.ahead_of_main == 0 and not show_all):
                continue
            moved = sorted(s for (u, s), j in joined.items() if b.name in j.moved)
            row = [b.name, b.day, str(b.ahead_of_main), b.drift, b.worktree, self.moves_text(moved, off.get(b.name, 0))]
            if measure:
                row.append(self.share_on_main(b.tip))
            branch_rows.append(row)
        headers = ["Branch", "Tip", f"Ahead of {main}", "Upstream", "Worktree", "Moves"] + ([f"On {main} by content"] if measure else [])
        lines += table(headers, branch_rows)
        return "\n".join(lines) + "\n"

    def region_text(self) -> str:
        """The index's generated region: the records and work tables from the working tree. Links are
        relative to the index, and every row is deterministic in the records' order."""
        w = self.work
        units = self.units_here()
        unit, base = self.title, w.index or w.status / "x"
        lines = [f"## {unit}s", "", f"Every {w.unit} with a status record, its state from the record's Status line, and its documents where they exist.", ""]
        unit_rows = []
        for name, record in units.items():
            docs = []
            for label, folder, file in (("plan", w.plans, f"{name}.md"), ("status", w.status, f"{name}.md"), ("review", w.reviews, f"{name}-review.md")):
                if folder is not None and (folder / file).exists():
                    docs.append(f"[{label}]({self.link(folder / file, base)})")
            packs = sorted(p.name for prefix in record.prefix.replace(" ", "").split(",") if prefix and w.validation is not None
                           for p in w.validation.glob(f"{prefix}-*.md"))
            if packs:
                docs.append(f"{len(packs)} Validation Packs")
            unit_rows.append((name, record.kind, record.prefix, f"{record.state or '?'} {record.day}".strip() or "?", record.next, ", ".join(docs)))
        lines += table(("ID", "Kind", "Prefix", "State", "Next", "Documents"), unit_rows)
        lines += ["", "## Work", "", f"Every {w.piece} on a board, keyed by its id, with the record and section it was read from.", ""]
        work_rows = []
        for name, record in units.items():
            for row in (record.board.rows if record.board else ()):
                work_rows.append((row.id, plain(row.deliverable, 190) or row.id, name, self.state_text(row), plain(row.blocked_on),
                                  f"{self.rel(w.status / name)}.md{record.board.anchor}"))
        lines += table(("ID", "Claim", unit, "State", "Blocked on", "Pointer"), work_rows)
        return "\n".join(lines) + "\n"

    def build(self, check: bool, say=print) -> int:
        w = self.work
        if w.index is None:
            say("this project declares no index, so there is no region to build")
            return 0
        existing = w.index.read_text(encoding="utf-8") if w.index.exists() else ""
        wanted = self.render_index(existing, self.region_text())
        if wanted == existing:
            return 0
        if check:
            say(f"{self.rel(w.index)}: the work-board region is stale against the status records. Run `{w.commands['build']}`")
            return 1
        self.write(w.index, wanted)
        return 0

    # ---- the roadmap ----

    def roadmap_regions(self) -> dict[str, str]:
        """The regions the roadmap carries: the programme at a glance (records and the gantt), the branches and
        the completed work, from every branch, dated by the newest day any board holds, and what waits on the maintainer."""
        w, main = self.work, self.work.main
        unit = self.title
        found = self.branches(published=True)  # the roadmap is committed, so no local-only branch reaches it
        boards = {b.name: self.units_at(b.tip) for b in found}
        # A record's own state and its documents come from the tree the roadmap is built in, which is the trunk
        # after a merge, so a branch sees its own records rather than the trunk's older copy of them.
        main_units = self.units_here()
        # The tree being built is committed, so its boards count whether or not its branch is pushed. A branch
        # no remote knows is read under a name that is not a branch, so its own name is never written.
        current = self.git("symbolic-ref", "--short", "-q", "HEAD", check=False).strip()
        if current:
            boards[current if current in boards else THIS_CHECKOUT] = main_units
        joined = self.join(boards)
        newest = max((d for j in joined.values() for r in j.rows.values() for _, d in r.trail if d), default="")
        glance = [f"Built from the status records on {len(found)} branches, the {w.unit}s' own state from this tree, the newest board day {newest or 'unknown'}.", ""]
        unit_rows = []
        done_rows = []
        open_units: list[str] = []
        done_units: list[str] = []

        def named(name: str) -> str:
            plan = w.plans / f"{name}.md"
            return f"[{name}]({self.link(plan, w.roadmap)})" if plan.exists() else name

        for name, record in main_units.items():
            slices = [j for (u, _), j in joined.items() if u == name]
            if record.state in w.closed and not any(j.moved for j in slices):
                last = max((d for j in slices for _, d in j.winner[1].trail if d), default=record.day)
                done_rows.append((named(name), record.kind, f"{record.state} {record.day}".strip(), str(len(slices)), last))
                done_units.append(name)
                continue
            open_units.append(name)
            counts: dict[str, int] = {}
            for j in slices:
                counts[j.winner[1].state or "?"] = counts.get(j.winner[1].state or "?", 0) + 1
            summary = ", ".join(f"{n} {st}" for st, n in sorted(counts.items(), key=lambda kv: -kv[1])) or "no board"
            on = sorted({b for j in slices for b in j.moved} - {THIS_CHECKOUT})
            unit_rows.append((named(name), record.kind, self.unit_state(name, record, boards), record.next, summary, ", ".join(on)))
        glance += table((unit, "Kind", "State", "Next", f"{self.piece}s", "Moved on"), unit_rows)
        count = NUMBER_WORDS.get(w.chart_after, str(w.chart_after))
        chart = f"One chart per {w.group}, or per {w.unit} outside {'an' if w.group[0] in 'aeiou' else 'a'} {w.group}" if w.group else f"One chart per {w.unit}"
        glance += ["", f"{chart} with {count} dated {w.piece}s or more, from the first day it has to the newest, every dated {w.piece} in the state its board gives.", ""]
        glance += self.charts_text(main_units, joined, open_units)
        completed = [f"Every {w.unit} whose Status line reads {words_or(w.closed)} and that no branch moves, with its {w.piece}s, and a chart per group of their {words_or(w.closed)} {w.piece}s with a day, whatever its age.", ""]
        completed += table((unit, "Kind", "State", f"{self.piece}s", "Last day"), done_rows)
        completed += [""] + self.charts_text(main_units, joined, done_units, completed=True)
        branch_rows = []
        off = self.off_grammar(boards)
        for b in found:
            if b.name == main or b.ahead_of_main == 0:
                continue
            moved = sorted(s for (u, s), j in joined.items() if b.name in j.moved)
            branch_rows.append((f"`{b.name}`", b.day, str(b.ahead_of_main), b.drift, self.moves_text(moved, off.get(b.name, 0))))
        branches_text = [f"Branches with a commit `{main}` lacks, from the same reading.", ""]
        branches_text += table(("Branch", "Tip", f"Ahead of {main}", "Upstream", "Moves"), branch_rows)
        return {"glance": "\n".join(glance) + "\n", "branches": "\n".join(branches_text) + "\n",
                "completed": "\n".join(completed) + "\n", "decisions": self.decisions_text()}

    def decisions_text(self) -> str:
        """What waits on the maintainer, read from the registers in the working tree: the Proposed decisions
        from the decision catalogue, the pending decisions, the open debt, and the slices named only in prose.
        The registers are the project's families of type ``pending-decision`` and ``debt``."""
        w = self.work
        proposed = []
        catalogue = w.decisions / "README.md" if w.decisions else None
        if catalogue and catalogue.is_file() and self.contained(catalogue):
            folder = self.link(w.decisions / "x", w.roadmap).removesuffix("/x")
            for line in catalogue.read_text(encoding="utf-8").splitlines():
                row = [c.strip() for c in line.strip().strip("|").split("|")]
                if len(row) >= 3 and row[0].startswith("[") and row[-1].lower().startswith("proposed"):
                    # The catalogue's links are relative to its own folder, and this region lives in the roadmap's.
                    proposed.append((row[0].replace("](", f"]({folder}/"), plain(row[1], 90), row[-1]))

        def register_rows(path: Path) -> list[tuple[str, str]]:
            out = []
            for line in (path.read_text(encoding="utf-8").splitlines() if path.is_file() and self.contained(path) else []):
                m = REGISTER_ROW_RE.match(line)
                if m:
                    row = [c.strip() for c in m.group(2).split("|")]
                    bold = re.match(r"\*\*(.+?)\*\*", row[0])
                    out.append((m.group(1), plain(bold.group(1) if bold else row[0], 160)))
            return out

        pending_files, debt_files = self.registers.get("pending-decision", []), self.registers.get("debt", [])
        pending = [r for p in pending_files for r in register_rows(p)]
        debt = sum(len(register_rows(p)) for p in debt_files)
        prose_only = 0
        for path in self.exceptions:
            if path.is_file() and self.contained(path) and "# unit " in path.read_text(encoding="utf-8"):
                prose_only = sum(1 for l in path.read_text(encoding="utf-8").split(w.exceptions_heading, 1)[-1].splitlines()
                                 if l.strip() and not l.startswith("#"))
        parts = [f"{len(proposed)} Proposed decisions"]
        if pending_files:
            parts.append(f"{len(pending)} pending design decisions")
        if debt_files:
            parts.append(f"{debt} rows of [technical debt]({self.link(debt_files[0], w.roadmap)})")
        if self.exceptions:
            parts.append(f"{prose_only} slices named only in prose, listed by {w.unit} in the identifier exceptions baseline")
        sentence = parts[0] if len(parts) == 1 else " and ".join(parts) if len(parts) == 2 else ", ".join(parts[:-1]) + ", and " + parts[-1]
        number = f"{w.roadmap_section}." if w.roadmap_section else ""
        lines = [f"Read from the registers in this tree: {sentence}.", "", f"### {number + '1 ' if number else ''}Proposed decisions", ""]
        lines += table(("Decision", "Subject", "Status"), proposed)
        if pending_files:
            first = self.link(pending_files[0], w.roadmap)
            lines += ["", f"### {number + '2 ' if number else ''}Pending design decisions", "",
                      f"Every row of [{Path(first).name}]({first}), which loses a row when a sketch, a plan or a decision settles it.", ""]
            lines += table(("Decision", "Question"), pending)
        return "\n".join(lines) + "\n"

    def build_roadmap(self, check: bool, say=print) -> int:
        w = self.work
        if w.roadmap is None:
            say("this project declares no roadmap, so there are no regions to build")
            return 0
        existing = w.roadmap.read_text(encoding="utf-8") if w.roadmap.exists() else ""
        wanted = self.render_regions(existing, self.roadmap_regions())
        if wanted == existing:
            return 0
        if check:
            say(f"{self.rel(w.roadmap)}: the work-board regions are stale. Run `{w.commands['roadmap']}`")
            return 1
        self.write(w.roadmap, wanted)
        return 0

    # ---- the check, over files ----

    def check(self, touched: Optional[Sequence[str]] = None, say=print) -> int:
        """The hook check: each status record, or only those named by ``touched`` (paths relative to the repository),
        is held to the ladder and the grammar, and the index's region to the records, when a record or the index is touched."""
        w = self.work
        status_dir = self.rel(w.status) + "/"
        index = self.rel(w.index) if w.index is not None else None
        messages: list[str] = []
        for path in self.records(w.status):
            rel = self.rel(path)
            if touched is None or rel in touched:
                messages += self.findings(rel, path.read_text(encoding="utf-8"))
        if index and (touched is None or any(t.startswith(status_dir) or t == index for t in touched)):
            messages += self.region_stale()
        for message in messages:
            say(message)
        return 1 if messages else 0

    def region_stale(self) -> list[str]:
        out: list[str] = []
        self.build(True, out.append)
        return out

    # ---- presence ----

    def presence_dir(self) -> Path:
        """Where ``here`` writes: the configured folder in the checkout, else a folder in the checkout's own git
        directory, which git never tracks and so needs no ignore rule."""
        if self.work.presence:
            return self.root / self.work.presence
        path = Path(self.git("rev-parse", "--git-path", "vyd/agents").strip())
        return path if path.is_absolute() else self.root / path


PRESENCE_HOURS = 12
ROLES = ("build", "review", "read")
# The variables each client sets for the commands it runs: the session, then the client's name. A client that sets
# none is read from VYD_SESSION_ID and VYD_CLIENT, which a person or a wrapper may set.
SESSION_VARIABLES = ("CLAUDE_CODE_SESSION_ID", "AGENT_SESSION_ID", "VYD_SESSION_ID")
CLIENT_VARIABLES = ("AI_AGENT", "CLAUDE_CODE_ENTRYPOINT", "VYD_CLIENT")


def session_from_environment(environ: dict[str, str]) -> tuple[str, str]:
    """(session, client) as the client exposes them. Claude Code sets CLAUDE_CODE_SESSION_ID and
    AI_AGENT in every command it runs. Another client is read the same way when it names them."""
    session = next((environ[k] for k in SESSION_VARIABLES if environ.get(k)), "")
    client = next((environ[k] for k in CLIENT_VARIABLES if environ.get(k)), "")
    return session, client


def file_name(session: str) -> str:
    """The presence file's name for a session. A session id comes from the environment, so only letters, digits,
    dots, hyphens and underscores are kept, and it can name no other folder."""
    return (re.sub(r"[^A-Za-z0-9._-]", "_", session).lstrip(".") or "unnamed") + ".toml"


def write_presence(directory: Path, session: str, client: str, model: str, role: str, on: Sequence[str], now: str) -> Path:
    """Write or refresh this session's presence file. The file's modification time is the fact the listing
    compares, so a later run with the same arguments touches it."""
    if role not in ROLES:
        raise ValueError(f"role is one of {', '.join(ROLES)}, not {role!r}")
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / file_name(session)
    since = now
    if path.exists():
        try:
            since = str(tomllib.loads(path.read_text(encoding="utf-8")).get("since", now))
        except (tomllib.TOMLDecodeError, UnicodeDecodeError):
            pass
    quote = lambda s: json.dumps(s)  # a JSON string is a TOML basic string
    path.write_text(f"session = {quote(session)}\nclient = {quote(client)}\nmodel = {quote(model)}\nrole = {quote(role)}\n"
                    f"on = [{', '.join(quote(s) for s in on)}]\nsince = {quote(since)}\n", **ENCODING)
    os.utime(path, None)
    return path


def list_presence(directory: Path, now_epoch: float) -> list[dict[str, str]]:
    """Every session whose file was touched within PRESENCE_HOURS of ``now_epoch``, oldest first. A
    crashed session ages out, a left one is gone, and no lock is ever held."""
    found: list[dict[str, str]] = []
    for path in sorted(directory.glob("*.toml"), key=lambda p: p.name) if directory.is_dir() else []:
        age = max(0.0, now_epoch - path.stat().st_mtime)
        if age > PRESENCE_HOURS * 3600:
            continue
        try:
            data = tomllib.loads(path.read_text(encoding="utf-8"))
        except (tomllib.TOMLDecodeError, UnicodeDecodeError, OSError):
            continue
        on = data.get("on", [])
        found.append({"session": str(data.get("session", path.stem)), "client": str(data.get("client", "")),
                      "model": str(data.get("model", "")), "role": str(data.get("role", "")),
                      "on": ", ".join(str(s) for s in on) if isinstance(on, list) else str(on), "since": str(data.get("since", "")),
                      "touched": f"{int(age // 60)} min ago"})
    return found


def leave_presence(directory: Path, session: str) -> bool:
    path = directory / file_name(session)
    if path.exists():
        path.unlink()
        return True
    return False


def presence_text(found: list[dict[str, str]], me: str, command: str = "vyd here") -> str:
    if not found:
        return f"nobody here. Run `{command} --role build|review|read --model <model>` before your first edit.\n"
    rows = [(("you " if f["session"] == me else "") + f["session"][:8], f["client"], f["model"], f["role"], f["on"], f["since"], f["touched"]) for f in found]
    lines = table(("Session", "Client", "Model", "Role", "On", "Since", "Touched"), rows)
    if [f for f in found if f["role"] == "build" and f["session"] != me]:
        lines += ["", "another session is building here. Say who is here and ask the maintainer before writing."]
    return "\n".join(lines) + "\n"
