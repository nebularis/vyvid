# SPDX-License-Identifier: MIT
# Ported from LATTICE's tools/work_migrate.py, relicensed MIT by its author.
"""Move a project's slice boards and slice ids onto the work board's shape.

``rename`` builds the crosswalk from historic ids and sweeps every mention onto the grammar, ``normalise`` puts
every board into the standard columns and state words, and ``adopt`` brings the slices a record's other tables,
a Validation Pack or a plan name onto the board. Each is idempotent, so a branch runs them once after merging the
trunk. Without ``apply`` each reports what it would do and writes nothing, the crosswalk included.

The grammar is the project's ``slice_pattern``. A historic id is crossed over by taking its body after its old
letters and joining its digit groups with dots, by the ``rename`` rules the project declares, so ``C9b3b`` is
``CCS-9b.3b`` under a rule with the prefix ``CCS``.

A state cell opens with a word of the ladder and the day it was reached. The historic words map onto the ladder
by position, and a cell with no day takes the day its text was committed, read from git, since a day is a fact
the record already held and never invented here.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

import regex

from .core import PREFIX_RE, SEPARATOR_RE, STATUS_LINE_RE, Board, Repo, cells, plain
from .settings import DEFAULT_LADDER, RenameRule

SEGMENT_RE = re.compile(r"[A-Z]*\d+[a-z]?")
PACKS = "validation pack"  # the unit column of a crosswalk row that records a Validation Pack's file name
# The historic state words, longest first, each mapped onto the default ladder and from there onto the project's.
# A cell is read lowercased with its bold and emoji stripped.
WORDS: tuple[tuple[str, str], ...] = (
    ("merged and signed off", "merged"), ("merged by squash", "merged"), ("squash-merged", "merged"),
    ("merged", "merged"), ("tagged", "tagged"), ("released", "tagged"),
    ("signed off", "verified"), ("signed-off", "verified"), ("accepted", "verified"), ("approved", "verified"),
    ("verified", "verified"), ("passed", "verified"), ("validated", "verified"),
    ("complete", "built"), ("done", "built"), ("committed", "built"), ("implemented", "built"), ("built", "built"),
    ("delivered", "built"), ("placed", "built"), ("drafted", "built"), ("handed off", "built"), ("handed over", "built"),
    ("written", "built"), ("in review", "built"), ("awaiting review", "built"),
    ("half built", "building"), ("in progress", "building"), ("building", "building"), ("started", "building"),
    ("attempted", "building"), ("under way", "building"), ("underway", "building"),
    ("briefed", "briefed"), ("brief written", "briefed"),
    ("retired", "dropped"), ("dropped", "dropped"), ("superseded", "dropped"), ("moved to", "dropped"),
    ("folded into", "dropped"), ("withdrawn", "dropped"), ("abandoned", "dropped"),
    ("blocked", "blocked"), ("waiting", "blocked"), ("on hold", "blocked"), ("paused", "blocked"),
    ("not started", "planned"), ("queued", "planned"), ("outline only", "planned"), ("outlined", "planned"),
    ("scoped", "planned"), ("planned", "planned"), ("proposed", "planned"), ("pending", "planned"), ("open", "planned"),
    ("deferred", "planned"), ("conditional", "planned"), ("not yet", "planned"),
)
DAY_RE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")
BRANCH_LINE_RE = re.compile(r"^\*\*Branch:\*\*[^\n]*\n", re.M)
EMOJI = ("✅", "🔨", "📝", "⏳")


def full(pattern: str, text: str):
    """A whole-text match of a pattern the project declared, under the same time limit as a family's."""
    try:
        return regex.fullmatch(pattern, text, timeout=0.5)
    except TimeoutError:
        return None


def crossed(prefix: str, body: str) -> str:
    return f"{prefix}-{'.'.join(SEGMENT_RE.findall(body))}"


def translate(repo: Repo, word: str) -> Optional[str]:
    """A word of the default ladder, or ``blocked`` or ``dropped``, as the project spells it. None where the project has no such word."""
    w = repo.work
    if word in DEFAULT_LADDER:
        return w.ladder[min(DEFAULT_LADDER.index(word), len(w.ladder) - 1)]
    if word == "blocked":
        return w.aside[0]
    return w.aside[1] if len(w.aside) > 1 else None


def map_state(repo: Repo, cell: str, blocked: str) -> Optional[tuple[str, str, str]]:
    """(state, day, remainder) for a historic cell, or None where no word maps. The earliest word
    in the cell wins, the longest on a tie, so "not started" is read before "started". A cell that
    says merged anywhere is at least merged. The remainder is the cell with the word, the day and
    the bold stripped, kept after the dated word."""
    text = cell.replace("**", "")
    for emoji in EMOJI:
        text = text.replace(emoji, "")
    text = text.strip()
    lower = text.lower()
    merged, tagged = translate(repo, "merged"), translate(repo, "tagged")
    first = repo.state_re.match(lower)
    if first and lower.split()[0] in repo.work.states and not (lower.startswith(merged or "") and (tagged or "") in lower):
        return None  # already on the ladder
    found = [(lower.find(word), -len(word), word, state) for word, state in WORDS if 0 <= lower.find(word) <= 24]
    if not found:
        return None
    at, _, word, state = min(found)
    cleared = blocked.strip().lower() in ("", "nothing", "none", "—", "-")
    if state == "blocked" and word == "waiting" and cleared:
        state = "planned"
    if "merged" in lower and state in ("verified", "built", "building", "merged"):
        state = "tagged" if "tagged" in lower else "merged"
    day = DAY_RE.search(text)
    remainder = text[:at] + text[at + len(word):]
    if day:
        remainder = remainder.replace(day.group(1), "")
    if state in ("merged", "tagged") and word not in ("merged", "tagged"):
        remainder = re.sub(r"\b(merged|tagged)\b", "", remainder)
    remainder = re.sub(r"\s+([,.])(?=\s|$)", r"\1", remainder)
    remainder = re.sub(r"([,.])(?:\s*[,.])+(?=\s|$)", r"\1", remainder).strip(" ,.:")
    if remainder.startswith("(") and remainder.endswith(")") and remainder.count("(") == 1:
        remainder = remainder[1:-1].strip()
    mapped = translate(repo, state)
    return (mapped, day.group(1) if day else "", remainder) if mapped else None


# ---- the crosswalk --------------------------------------------------------------------------------

@dataclass(frozen=True)
class Crossing:
    unit: str
    old: str
    new: str


def unit_ids(repo: Repo, unit: str) -> list[str]:
    path = repo.work.status / f"{unit}.md"
    if not path.is_file() or not repo.contained(path):
        return []
    parsed = repo.parse_unit(unit, path.read_text(encoding="utf-8"))
    return [row.id for row in (parsed.board.rows if parsed.board else ())]


def cross(repo: Repo, rule: RenameRule, old: str) -> Optional[str]:
    if repo.valid_id(old):
        return old
    for pattern in rule.patterns:
        m = full(pattern, old)
        if m:
            return crossed(rule.prefixes[0], m.group(1))
    return None


def pack_target(rule: RenameRule, stem: str) -> Optional[str]:
    for pattern in rule.packs:
        m = full(pattern, stem)
        if m:
            return crossed(rule.prefixes[0], ".".join(g for g in m.groups()))
    return None


def crosswalk(repo: Repo) -> list[Crossing]:
    """One crossing per historic id on a record's board, from the record's rule, and one per historic
    spelling of an id on the grammar that prose still uses, for a rule that names a ``spelled`` letter. An id the rule does not
    match, and an id already in the grammar, are left out."""
    out: list[Crossing] = []
    for rule in repo.work.rename:
        for old in unit_ids(repo, rule.unit):
            new = cross(repo, rule, old)
            if new and new != old:
                out.append(Crossing(rule.unit, old, new))
            elif new and rule.spelled and new.startswith(rule.prefixes[0] + "-") and new[len(rule.prefixes[0]) + 1:][:1].isdigit():
                body = new[len(rule.prefixes[0]) + 1:]
                out += [Crossing(rule.unit, f"{rule.prefixes[0]}-{rule.spelled}{spelling}", new) for spelling in (body, body.replace(".", "-", 1))]
    return sorted(set(out), key=lambda c: (c.unit, c.old))


def folders(repo: Repo) -> list[Path]:
    """The folders the sweep reads: the records' and the plans' own, those the project names, and the decisions."""
    w = repo.work
    found: list[Path] = []
    for folder in (w.status.parent, w.plans.parent, w.decisions, *w.sweep):
        if folder is not None and folder.is_dir() and repo.contained(folder) and folder not in found:
            found.append(folder)
    return found


def own_files(repo: Repo, unit: str) -> set[Path]:
    """The record's own documents: its status record, its plans, its review and its Validation Packs, by the
    record's name or, for a pack, its prefix. A longer name wins a file it shares a start with, so a record
    ``track-b`` owns its own files and ``track`` does not."""
    w = repo.work
    longer = [r.unit for r in w.rename if r.unit != unit and r.unit.startswith(unit + "-")]
    found: set[Path] = set()
    for folder in (w.status, w.plans, w.reviews, w.validation):
        for path in folder.glob(f"{unit}*.md") if folder is not None and folder.is_dir() else ():
            if not any(path.stem == o or path.stem.startswith(o + "-") for o in longer):
                found.add(path)
    rule = next((r for r in w.rename if r.unit == unit), None)
    for prefix in (rule.prefixes if rule else ()):
        found |= set(w.validation.glob(f"{prefix}-*.md")) if w.validation is not None and w.validation.is_dir() else set()
    return found


def crosswalk_path(repo: Repo) -> Path:
    return repo.work.crosswalk or repo.work.status.parent / "notes" / "slice-crosswalk.md"


def sweep_files(repo: Repo, exceptions: bool = True) -> list[Path]:
    """Every file the sweep rewrites: the Markdown under each folder of ``folders`` and, unless told not to, the
    identifier exceptions baseline. The crosswalk is never rewritten."""
    files = [p for folder in folders(repo) for p in sorted(folder.rglob("*.md"), key=lambda p: p.as_posix()) if p.is_file() and repo.contained(p)]
    files += [p for p in repo.exceptions if p.exists()] if exceptions else []
    walk = Path(crosswalk_path(repo))
    return [f for f in files if f.resolve() != walk.resolve()]


def still_mentioned(repo: Repo, old: str) -> bool:
    """Whether a tracked file outside the baseline still spells the id, as itself or as the start of a longer
    spelling such as a pack's FMH-H2-1, which the identifier check reads as FMH-H2. The sweep reaches only some
    areas and leaves such spellings, so an exception may still be needed."""
    out = subprocess.run(["git", "grep", "-lP", "-e", r"(?<![\w\-/.])" + re.escape(old) + r"(?![\w.])", "--"],
                         cwd=repo.root, capture_output=True, text=True, encoding="utf-8", errors="replace").stdout.split("\n")
    baseline = {Path(p).resolve() for p in repo.exceptions}
    return any((repo.root / f).resolve() not in baseline for f in out if f)


def cross_exceptions(repo: Repo, crossings: list[Crossing], apply: bool) -> list[str]:
    """Each exception names a spelling the text still holds, so it takes the new id only beside its
    old line while the old spelling is mentioned, and alone once it is not."""
    new_of = {c.old: c.new for c in crossings}
    kept_old: list[str] = []
    for path in repo.exceptions:
        if not path.exists():
            continue
        out: list[str] = []
        lines = path.read_text(encoding="utf-8").splitlines()
        present = {l.split("#")[0].strip() for l in lines}
        for line in lines:
            key = line.split("#")[0].strip()
            if key not in new_of:
                out.append(line)
                continue
            crossed_line = line.replace(key, new_of[key], 1)
            if still_mentioned(repo, key):
                out.append(line)
                kept_old.append(key)
            if new_of[key] not in present:
                out.append(crossed_line)
        if apply:
            repo.write(path, "\n".join(out) + "\n")
    return [f"exceptions: kept beside their new id, since still mentioned: {', '.join(kept_old)}"] if kept_old else []


def pattern_for(old: str) -> re.Pattern[str]:
    """The whole id, not inside another id: not after a word character, a hyphen, a slash or a
    dot, and not before one, nor before a question, decision or test suffix such as -Q1 or -01."""
    return re.compile(r"(?<![\w\-/.])" + re.escape(old) + r"(?![\w.]|-[A-Z]?\d)")


def distinctive(old: str) -> bool:
    """An id safe to replace outside its record's own documents: prefixed, dotted, or with an inner
    letter, since a bare letter and digit such as C2 or B1 is also prose."""
    return "-" in old or "." in old or re.search(r"\d[a-z]\d", old) is not None or re.match(r"[A-Z]{2,}", old) is not None


def rename(repo: Repo, apply: bool) -> list[str]:
    """Build the crosswalk, write it, then sweep. A record's own documents take every crossing of the
    record. Every other file takes only a distinctive old id that one record claims."""
    w = repo.work
    crossings = crosswalk(repo)
    report: list[str] = []
    walk = crosswalk_path(repo)
    kept: set[Crossing] = set()  # rows written by an earlier run, pack renames among them
    if walk.exists():
        for line in walk.read_text(encoding="utf-8").splitlines():
            row = cells(line)
            if len(row) == 3 and row[0] not in ("Was", "---") and not set(row[0]) <= set("-"):
                kept.add(Crossing(row[2], row[0], row[1]))
    every = sorted(kept | set(crossings), key=lambda c: (c.unit, c.old))
    head = ["# Slice id crosswalk", "",
            f"The historic slice ids and the ids the grammar gives them, kept so an old commit message or tag note still resolves. Written by `{w.commands['rename']}`, which keeps every row it ever wrote, never by hand.", "",
            "| Was | Is | Unit |", "|---|---|---|"]

    def write_walk() -> None:
        repo.write(walk, "\n".join(head + [f"| {c.old} | {c.new} | {c.unit} |" for c in every]) + "\n")

    if every:
        write_walk()  # the crosswalk is written even without apply, for the maintainer to read first
    report.append(f"crosswalk: {len(crossings)} ids over {len({c.unit for c in crossings})} units this run, {len(every)} rows in {repo.rel(walk)}")
    by_unit: dict[str, list[Crossing]] = {}
    claims: dict[str, set[str]] = {}
    for c in crossings:
        by_unit.setdefault(c.unit, []).append(c)
        claims.setdefault(c.old, set()).add(c.unit)
    every = [c for c in every if c.unit != PACKS] + [c for c in every if c.unit == PACKS]
    shared = sorted(old for old, units in claims.items() if len(units) > 1 and not old.rstrip(".").isdigit())
    if shared:
        report.append("claimed by two units, left for the hand outside their own documents: " + ", ".join(shared))
    bare_units = {r.unit for r in w.rename if r.bare}
    by_unit = {u: cs for u, cs in by_unit.items() if u not in bare_units}
    general = [c for c in crossings if len(claims[c.old]) == 1 and distinctive(c.old) and c.unit not in bare_units]
    owned = {u: own_files(repo, u) for u in by_unit}
    changed = 0
    for path in sweep_files(repo, exceptions=False):
        text = path.read_text(encoding="utf-8")
        new = text
        owner = max((u for u in by_unit if path in owned[u]), key=len, default=None)
        rules = sorted(by_unit.get(owner, []), key=lambda c: -len(c.old)) if owner else []
        rules += [c for c in sorted(general, key=lambda c: -len(c.old)) if c.unit != owner]
        for c in rules:
            new = pattern_for(c.old).sub(c.new, new)
        for prefix in {p for r in w.rename for p in r.prefixes}:
            new = re.sub(rf"\b{re.escape(prefix)} ({re.escape(prefix)}-)", r"\1", new)
        if new != text:
            changed += 1
            if apply:
                repo.write(path, new)
    report.append(f"mentions: {changed} files {'rewritten' if apply else 'would change'}")
    report += cross_exceptions(repo, crossings, apply)  # after the sweep, which it must see written
    # Validation Packs
    validation = w.validation
    moves: list[tuple[str, str]] = []
    unmatched: list[str] = []
    for pack in (sorted(validation.glob("*.md"), key=lambda p: p.name) if validation is not None and validation.is_dir() else []):
        target = next((t for r in w.rename if (t := pack_target(r, pack.stem))), None)
        if target and target != pack.stem:
            moves.append((pack.name, f"{target}.md"))
        elif not target and not repo.valid_id(pack.stem):
            unmatched.append(pack.name)
    if apply and validation is not None:
        for old, new in moves:
            if not (repo.writable(validation / old) and repo.writable(validation / new)):
                raise PermissionError(f"{old} or {new} is outside the repository, so it is not renamed")
            subprocess.run(["git", "mv", "--", str(validation / old), str(validation / new)], cwd=repo.root, check=True)
        recorded = {(c.old, c.new) for c in every if c.unit == PACKS} | set(moves)
        for path in sweep_files(repo):
            text = path.read_text(encoding="utf-8")
            new_text = text
            for old, new in recorded:
                new_text = (new_text.replace(f"{validation.name}/{old}", f"{validation.name}/{new}").replace(f"]({old})", f"]({new})")
                            .replace(f"](./{old})", f"]({new})").replace(f"]({old}#", f"]({new}#"))
            if new_text != text:
                repo.write(path, new_text)
        every = sorted(set(every) | {Crossing(PACKS, old, new) for old, new in moves}, key=lambda c: (c.unit, c.old))
        if every:
            write_walk()
    report.append(f"validation packs: {len(moves)} {'renamed' if apply else 'to rename'}, {len(unmatched)} left as they are: " + ", ".join(unmatched))
    return report


# ---- normalising -----------------------------------------------------------------------------------

def committed_day(repo: Repo, path: Path, needle: str) -> str:
    rel = repo.rel(path)
    out = repo.git("log", "-1", "--format=%cs", f"-S{needle}", "--", rel, check=False).strip() if needle else ""
    return out or repo.git("log", "-1", "--format=%cs", "--", rel, check=False).strip()


def split_ids(cell: str) -> list[str]:
    """``AOR-10, AOR-11`` and ``PF1/PF4`` are two slices, ``AOR-2 to AOR-4`` three."""
    cell = cell.strip("`* ")
    m = re.fullmatch(r"([A-Z]+-?)(\d+)\s+to\s+\1(\d+)", cell)
    if m:
        return [f"{m.group(1)}{n}" for n in range(int(m.group(2)), min(int(m.group(3)), int(m.group(2)) + 200) + 1)]
    head = cell.split("(")[0].strip()
    parts = [p.strip("`* ") for p in re.split(r"[,/]| and ", head) if p.strip("`* ")]
    ids = [p.split(" ")[0].strip("`*,;:") for p in parts]
    if len(parts) > 1 and all(re.fullmatch(r"[A-Z]{0,5}-?\d[\w.]*|\d+\.?", i) for i in ids) and all(" " not in p for p in parts):
        return ids
    return [ids[0]] if ids and ids[0] else [cell]


def normalise_record(repo: Repo, path: Path) -> tuple[str, list[str]]:
    """The record's text with its board on the standard columns and words, its Branch line gone and
    an ID line present, plus the cells no word maps, left as they were."""
    w = repo.work
    text = path.read_text(encoding="utf-8")
    unit = path.stem
    where = repo.rel(path)
    notes: list[str] = []
    text = BRANCH_LINE_RE.sub("", text)
    if not repo.unit_id_re.search(text):
        text = re.sub(r"^(# [^\n]*\n)", lambda m: f"{m.group(1)}\n**{repo.title} ID:** `{unit}`\n", text, count=1, flags=re.M)
    parsed = repo.parse_unit(unit, text)
    board = parsed.board
    if board:
        lines = text.splitlines()
        header = list(board.columns)
        lower = [h.lower() for h in header]
        piece = w.piece
        fixed = ("#", "slice", piece, "state", "status", "deliverable", "delivers", "scope")
        keep = [i for i, h in enumerate(lower) if h not in fixed and not h.startswith("blocked")]
        id_at = lower.index("#") if "#" in lower else lower.index("slice") if "slice" in lower else lower.index(piece)
        state_at = lower.index("state") if "state" in lower else lower.index("status")
        new_rows: list[str] = []
        for row in board.rows:
            raw = cells(lines[row.line - 1])
            raw += [""] * (len(header) - len(raw))
            id_cell = raw[id_at]
            ids = split_ids(id_cell)
            rule = next((r for r in w.rename if r.unit == unit and r.bare), None)
            if rule:
                ids = [cross(repo, rule, i) or i for i in ids]
            deliverable = row.deliverable
            if not deliverable and "#" not in lower:
                rest = id_cell.strip("`* ")
                m = re.match(r"\S+\s*\(?(.*?)\)?$", rest)
                deliverable = m.group(1).strip() if m and m.group(1) and m.group(1) != rest else ""
            if row.state is None:
                mapped = map_state(repo, row.raw, row.blocked_on)
                if mapped:
                    state, day, remainder = mapped
                    if state in w.dated and not day:
                        day = committed_day(repo, path, raw[state_at])
                    cell = f"{state} {day}".strip() + (f", {remainder}" if remainder else "")
                else:
                    cell = row.raw
                    notes.append(f"{where}:{row.line}: no word maps '{row.raw[:50]}'")
            else:
                cell = row.raw
                if row.state in w.dated and not row.day:
                    cell = f"{row.state} {committed_day(repo, path, row.raw)}" + row.raw[len(row.state):]
            blocked = row.blocked_on
            if blocked.strip().lower() in ("nothing", "none", "—", "-"):
                blocked = ""
            extras = [raw[i] for i in keep]
            for slice_id in ids:
                new_rows.append("| " + " | ".join(c.replace(";", ",") for c in [slice_id, deliverable, cell, blocked, *extras]) + " |")
        new_header = "| " + " | ".join([repo.piece, "Deliverable", "State", "Blocked on", *[header[i] for i in keep]]) + " |"
        separator = "|" + "---|" * (4 + len(keep))
        first, last = board.line - 1, board.rows[-1].line if board.rows else board.line + 1
        lines[first:last] = [new_header, separator, *new_rows]
        text = "\n".join(lines) + "\n"
        parsed = repo.parse_unit(unit, text)
    status = STATUS_LINE_RE.search(text)
    if status and parsed.state is None:
        if parsed.board and parsed.board.rows:
            nxt = next((r for r in parsed.board.rows if r.id == parsed.next), None)
            row = nxt or max(parsed.board.rows, key=lambda r: r.key)
            state, day = (row.state or w.ladder[0]), row.day
            if not day and state in w.dated:
                day = committed_day(repo, path, status.group(1)[:40])
            text = text.replace(status.group(0), f"**Status:** {state} {day}. {status.group(1)}".replace("  ", " "), 1)
        else:
            notes.append(f"{where}: Status line opens with no state word and the record has no board")
    elif not status and parsed.board and parsed.board.rows:
        nxt = next((r for r in parsed.board.rows if r.id == parsed.next), None)
        row = nxt or max(parsed.board.rows, key=lambda r: r.key)
        state, day = (row.state or w.ladder[0]), row.day
        line = f"**Status:** {state} {day}.".replace(" .", ".")
        m = repo.unit_id_re.search(text)
        text = text[:m.end() + 1] + line + "\n" + text[m.end() + 1:]
    elif not status:
        notes.append(f"{where}: no Status line")
    return hold_status(repo, text, unit), notes


def hold_status(repo: Repo, text: str, unit: str) -> str:
    """The record with its Status word and day set to what its board rolls up to, the text after them
    kept. A record with no board, or whose board gives no word, is left as it is."""
    parsed = repo.parse_unit(unit, text)
    rolled = repo.rollup(parsed.board.rows) if parsed.board else None
    status = STATUS_LINE_RE.search(text)
    if not rolled or not status or (parsed.state, parsed.day) == rolled:
        return text
    m = repo.state_re.match(status.group(1))
    rest = m.group(3) if m else status.group(1)
    sep = "" if not rest or rest.startswith((".", ",")) else ". "
    return text.replace(status.group(0), f"**Status:** {rolled[0]} {rolled[1]}".rstrip() + sep + rest, 1)


def declare_prefixes(repo: Repo, apply: bool) -> list[str]:
    out: list[str] = []
    for rule in repo.work.rename:
        plan = repo.work.plans / f"{rule.unit}.md"
        if not plan.is_file() or not repo.contained(plan):
            continue
        text = plan.read_text(encoding="utf-8")
        if PREFIX_RE.search(text) or "**Prefix:**" in text:
            continue
        line = f"**Prefix:** {', '.join(rule.prefixes)}\n"
        m = repo.unit_id_re.search(text)
        new = text[:m.end() + 1] + line + text[m.end() + 1:] if m else re.sub(r"^(# [^\n]*\n)", lambda g: f"{g.group(1)}\n{line}", text, count=1, flags=re.M)
        out.append(f"{repo.rel(plan)}: Prefix {', '.join(rule.prefixes)}")
        if apply:
            repo.write(plan, BRANCH_LINE_RE.sub("", new))
    return out


def normalise(repo: Repo, apply: bool) -> list[str]:
    report: list[str] = []
    changed = 0
    for path in repo.records(repo.work.status):
        new, notes = normalise_record(repo, path)
        report += notes
        if new != path.read_text(encoding="utf-8"):
            changed += 1
            if apply:
                repo.write(path, new)
    for plan in repo.records(repo.work.plans):
        text = plan.read_text(encoding="utf-8")
        if BRANCH_LINE_RE.search(text):
            changed += 1
            if apply:
                repo.write(plan, BRANCH_LINE_RE.sub("", text))
    report += declare_prefixes(repo, apply)
    report.append(f"records and plans: {changed} {'rewritten' if apply else 'would change'}")
    return report


# ---- adopting ----------------------------------------------------------------------------------------

def tables_in(repo: Repo, text: str) -> list[tuple[int, list[str], list[list[str]]]]:
    """Every table as (header line number, headers, rows of cells)."""
    lines = text.splitlines()
    out: list[tuple[int, list[str], list[list[str]]]] = []
    for number, line in enumerate(lines, 1):
        if not line.startswith("|") or number >= len(lines) or not SEPARATOR_RE.match(lines[number].strip()):
            continue
        header = cells(line)
        rows: list[list[str]] = []
        for body in lines[number + 1:]:
            if not body.startswith("|"):
                break
            row = cells(body)
            rows.append(row + [""] * (len(header) - len(row)))
        out.append((number, header, rows))
    return out


def first_commit_day(repo: Repo, path: Path) -> str:
    out = repo.git("log", "--follow", "--diff-filter=A", "--format=%cs", "--", repo.rel(path), check=False).strip()
    return out.splitlines()[-1] if out else committed_day(repo, path, "")


def candidates_for(repo: Repo, unit: str, prefixes: tuple[str, ...], record_text: str, board: Board) -> dict[str, tuple[str, str, str, str]]:
    """Slices the record names outside its board, as id -> (state cell, deliverable, blocked on, source),
    the record's other tables first, then the Validation Packs, then the plans' tables."""
    w = repo.work
    skip = regex.compile(w.adopt_skip)
    found: dict[str, tuple[str, str, str, str]] = {}

    def mine(i: str) -> bool:
        return repo.valid_id(i) and not skip.match(i) and i.split("-")[0] in prefixes

    def take(header: list[str], rows: list[list[str]], source: str, default_state: str, day_for: Callable[[], str]) -> None:
        lower = [h.lower() for h in header]
        id_at = next((i for i, h in enumerate(lower) if h in ("slice", "#", "id", "slices", w.piece)), None)
        if id_at is None:
            return
        state_at = next((i for i, h in enumerate(lower) if h in ("state", "status")), None)
        blocked_at = next((i for i, h in enumerate(lower) if h.startswith(("blocked", "depends", "start after", "waits"))), None)
        text_at = next((i for i, h in enumerate(lower) if i != id_at and h in ("deliverable", "delivers", "content", "scope", "note", "slice")), None)
        for row in rows:
            for slice_id in split_ids(row[id_at]):
                if not mine(slice_id) or slice_id in found:
                    continue
                cell = row[state_at] if state_at is not None else ""
                state, day, _ = repo.parse_state(cell)
                if state is None and cell:
                    mapped = map_state(repo, cell, row[blocked_at] if blocked_at is not None else "")
                    if mapped:
                        state, day, _ = mapped
                state = state or default_state
                if state in w.dated and not day:
                    day = day_for()
                found[slice_id] = (f"{state} {day}".strip(), row[text_at] if text_at is not None else "", row[blocked_at] if blocked_at is not None else "", source)

    record = w.status / f"{unit}.md"
    for number, header, rows in tables_in(repo, record_text):
        if number != board.line:
            take(header, rows, f"{repo.rel(record)}:{number}", w.ladder[0], lambda: committed_day(repo, record, ""))
    if w.validation is not None and w.validation.is_dir():
        for prefix in prefixes:
            for pack in sorted(w.validation.glob(f"{prefix}-*.md")):
                if mine(pack.stem) and pack.stem not in found and repo.contained(pack):
                    found[pack.stem] = (f"{w.done_from} {first_commit_day(repo, pack)}", "", "", repo.rel(pack))
    for plan in repo.records(w.plans):
        if not plan.name.startswith(unit):
            continue
        for number, header, rows in tables_in(repo, plan.read_text(encoding="utf-8")):
            take(header, rows, f"{repo.rel(plan)}:{number}", w.ladder[0], lambda p=plan: committed_day(repo, p, ""))
    return found


def plain_cell(cell: str) -> str:
    return plain(cell).replace("|", "/")


def adopt(repo: Repo, apply: bool) -> list[str]:
    """Append to each record's board the slices its other tables, its Validation Packs and its plans name and
    the board lacks, each in the state its source gives, then drop them from the identifier exceptions
    baseline. Idempotent, and reports without ``apply``."""
    w = repo.work
    report: list[str] = []
    adopted: set[str] = set()
    for unit, parsed in repo.units_here().items():
        prefixes = tuple(p.strip() for p in parsed.prefix.split(",") if p.strip())
        if not prefixes:
            continue
        record = w.status / f"{unit}.md"
        text = record.read_text(encoding="utf-8")
        if not parsed.board:
            # A record with no board gains the standard one at its end, so the record's slices have a home.
            text = text.rstrip("\n") + f"\n\n## Board\n\n| {repo.piece} | Deliverable | State | Blocked on |\n|---|---|---|---|\n"
            parsed = repo.parse_unit(unit, text, "")
            if not parsed.board:
                report.append(f"{unit}: no board to adopt onto")
                continue
            report.append(f"{unit}: a board added at the end of the record")
        have = {row.id for row in parsed.board.rows}
        new = {i: c for i, c in candidates_for(repo, unit, prefixes, text, parsed.board).items() if i not in have}
        if not new:
            continue
        lines = text.splitlines()
        last = parsed.board.rows[-1].line if parsed.board.rows else parsed.board.line + 1
        extra = len(parsed.board.columns) - 4
        for slice_id, (state, deliverable, blocked, source) in sorted(new.items()):
            lines.insert(last, "| " + " | ".join([slice_id, plain_cell(deliverable), state, plain_cell(blocked)] + [""] * extra) + " |")
            last += 1
        adopted |= set(new)
        by_source: dict[str, int] = {}
        for _, (_, _, _, source) in new.items():
            by_source[source.split(":")[0]] = by_source.get(source.split(":")[0], 0) + 1
        report.append(f"{unit}: {len(new)} rows " + ("adopted" if apply else "to adopt") + " from " + ", ".join(f"{s} ({n})" for s, n in sorted(by_source.items())))
        if apply:
            repo.write(record, "\n".join(lines) + "\n")
    if apply and adopted:
        for path in repo.exceptions:
            if path.exists():
                kept = [l for l in path.read_text(encoding="utf-8").splitlines() if l.split("#")[0].strip() not in adopted]
                repo.write(path, "\n".join(kept) + "\n")
    report.append(f"{len(adopted)} slices {'adopted' if apply else 'would be adopted'}")
    return report


def regroup_exceptions(repo: Repo, apply: bool) -> list[str]:
    """Rewrite the section of the exceptions baseline that follows its heading, grouped by record, each group
    headed by the record it belongs to, so a record's next slice sees its own list."""
    heading = repo.work.exceptions_heading
    prefixes: dict[str, str] = {}
    for unit, parsed in repo.units_here().items():
        for p in parsed.prefix.split(","):
            if p.strip():
                prefixes[p.strip()] = unit
    for plan in repo.records(repo.work.plans):
        m = re.search(r"^\*\*Prefix:\*\*\s*(.+?)\s*$", plan.read_text(encoding="utf-8"), re.M)
        if m:
            for p in m.group(1).split(","):
                prefixes.setdefault(p.strip(), plan.stem)
    out: list[str] = []
    for path in repo.exceptions:
        if not path.exists() or heading not in path.read_text(encoding="utf-8"):
            continue
        text = path.read_text(encoding="utf-8")
        head, _, tail = text.partition(heading)
        section_lines = (heading + tail).splitlines()
        comment = [l for l in section_lines if l.startswith("#") and not l.startswith("# unit ")]
        ids = [l.split("#")[0].strip() for l in section_lines if l.strip() and not l.startswith("#")]
        groups: dict[str, list[str]] = {}
        for i in ids:
            groups.setdefault(prefixes.get(i.split("-")[0], f"no {repo.work.unit} declares this prefix"), []).append(i)
        body = "\n".join(comment) + "\n"
        for unit, members in sorted(groups.items()):
            body += f"# unit {unit}, {len(members)} slice(s)\n" + "".join(f"{i}  # named in a plan, no board row yet\n" for i in sorted(set(members)))
        out.append(f"{repo.rel(path)}: {len(ids)} ids in {len(groups)} groups")
        if apply:
            repo.write(path, head.rstrip("\n") + "\n\n" + body)
    return out
