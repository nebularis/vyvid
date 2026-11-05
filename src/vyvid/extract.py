# SPDX-License-Identifier: MIT
# From LATTICE's tools/knowledge/extract.py and identifiers.py, relicensed MIT by its author.
"""Derive the knowledge index from a scope's working documents, as quads.

The index holds no content of its own. Every fact here is read from a Markdown or Turtle document,
every claim is the lead sentence of its own entry rather than a second copy of it, and deleting the
store loses nothing but speed. Each scope's entries go in a graph of its own, and the terms a
plug-in extractor declares in another (``extractors``).

What a family's identifiers are defined by is its rule:

``table``
    a row of a register, read by ``registers``
``file``
    a file named by the identifier, as a decision is
``heading``
    a Markdown heading that opens with the identifier, as a finding of a store record is
``question``
    a bold lead or a table row of a plan or a sketch that opens with the identifier

Every extractor adds quads, problems and findings to an ``Extract``. A problem is a fact it could not
read, reported and never guessed. A finding is a thing worth the maintainer's attention that is not
a fault in a document.

These are the framework's own extractors, selected by a family's rule. A plug-in extractor of a
domain is in ``extractors``.
"""

from __future__ import annotations

import datetime as dt
import functools
import re
from dataclasses import dataclass, field
from pathlib import Path

import pyoxigraph as ox
import regex

from . import anchors, facets, registers
from .config import Config, Family, Scope
from .model import KI, RDF_TYPE, RDFS_LABEL, document, index_graph, ki, node, node_of, normalise, term
from .patterns import Pattern
from .registers import SEPARATOR_RE, shorten
from .registers import _cells as table_cells
from .resolve import Unresolved, mentions, moved, resolve, visible_families

CLAIM_LIMIT = 200

# The status words a decision's Status line may open with. The line's freeform tail is discarded,
# since the typed individual is the fact.
PUBLISHED_RE = re.compile(r"^Published, (?P<date>\d{4}-\d{2}-\d{2})\.")
STATUS_WORDS = ("Superseded", "Proposed", "Accepted", "Rejected", "Withdrawn", "Deferred", "Complete")
STATUS_RE = re.compile(r"^\*\*Status:\*\*\s*(?P<status>.+?)\s*$")
RELATED_RE = re.compile(r"^\*\*Related:\*\*\s*(?P<rest>.+?)\s*$")
BOLD_RE = registers.BOLD_RE

# A section's own text is embedded, and the model reads at most 512 tokens, so more would not be
# read. Measured on LATTICE, 2026-10-28: at 1,800 characters the longest section is 479 tokens and
# 30 of 512 are cut, against 120 cut at 600.
SECTION_LIMIT = 1800
# A numbered decision opens its line with its number, bold where the decision is a paragraph.
NUMBERED_RE = re.compile(r"^(?:\*\*)?\d+\.\s")
NUMBER_RE = re.compile(r"^(?:\*\*)?(?P<n>\d+)\.\s")
# The bold lead an addendum opens with when it reverses or narrows numbered decisions of its file,
# ``**Reverses decision 8.**`` or ``**Narrows decisions 3, 6 and 7.**``.
SUPERSESSION_RE = re.compile(r"\*\*(?P<verb>Reverses|Narrows) decisions? (?P<numbers>\d+(?:(?:,| and|, and) \d+)*)\.\*\*")
SUPERSESSION_EDGE = {"Reverses": "supersededBy", "Narrows": "narrowedBy"}
# An addendum is named by its decision and the day in its heading, which survives an edit as a
# section's position does not. ``decisions`` records them before the registers are read, so a
# register's Narrowed by can point an entry at the addendum that narrowed the decision it rests on.
ADDENDUM_DATE_RE = re.compile(r"^## Addendum\b\D{0,12}?(\d{4}-\d{2}-\d{2})")  # ", 2026-11-02", " (2026-10-26)", " of 2026-10-25"

CURIE_RE = re.compile(r"(?<![\w/#.-])(?P<prefix>[a-z][\w-]*):(?P<local>[A-Za-z][\w-]*)(?![\w-])")

# An answer that states a rule a later slice must obey says so in these words.
RULE_WORDS_RE = re.compile(r"\b(must|never|only)\b", re.I)
# ``Answered 2026-10-19, (a), now MEC-nn.``: the entry the answer was promoted to.
PROMOTED_RE = re.compile(r"\bnow (?P<ids>[^.;]*)")
# How long an answered rule may live in a plan before the build reports it unpromoted.
PROMOTION_DAYS = 30
ANSWERED_RE = re.compile(r"\banswered\b(?:\W+(?P<date>\d{4}-\d{2}-\d{2}))?", re.I)


@dataclass
class Extract:
    quads: list[ox.Quad] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=dict)
    problems: list[str] = field(default_factory=list)
    findings: list[str] = field(default_factory=list)
    # (scope, normalised decision, day) -> the addendum's section node
    addenda: dict[tuple[str, str, str], ox.NamedNode] = field(default_factory=dict)
    # scope -> the units its extractors declared, each name to the units it stands for
    units: dict[str, dict[str, list[str]]] = field(default_factory=dict)

    def bump(self, key: str, by: int = 1) -> None:
        self.counts[key] = self.counts.get(key, 0) + by


@dataclass
class Context:
    """What an extractor needs to read one scope: the configuration, where to put what it finds, the
    register types, the taggable facet values and the words that find a technology in text."""

    config: Config
    scope: Scope
    out: Extract
    types: registers.RegisterTypes
    taggable: dict[str, set[str]]
    words: dict[str, re.Pattern[str]] = field(default_factory=dict)
    # Every prefix the scope's extractors found, so a Bears on cell may name a term by the CURIE its own layer writes.
    prefixes: dict[str, str] = field(default_factory=dict)

    @property
    def graph(self) -> ox.NamedNode:
        return index_graph(self.scope.name)

    def add(self, subject, predicate, obj) -> None:
        self.out.quads.append(ox.Quad(subject, predicate, obj, self.graph))

    def rel(self, path: Path) -> str:
        root = self.scope.code or self.scope.path or Path.cwd()
        try:
            return path.resolve().relative_to(root.resolve()).as_posix()
        except ValueError:
            return path.as_posix()

    def mentions(self, text: str) -> list[str]:
        return mentions(self.config, text, self.scope)

    def moved(self, identifier: str) -> bool:
        """Whether a move hands this identifier to a domain, which now answers for it. It is counted, never indexed."""
        if (hit := moved(self.config, self.scope, identifier)) is None:
            return False
        self.out.bump(f"moved:{self.scope.name}>{hit[0].to}")
        return True

    def families(self, rule: str) -> list[Family]:
        return [f for f in self.scope.families.values() if f.rule == rule]


def head(pattern: Pattern, text: str):
    """The identifier a text opens with: the family's pattern at the start, not run into a longer word."""
    return pattern.derive(lambda p: rf"(?:{p})(?!\w)").match(text)


def status_of(line: str) -> str | None:
    """The typed status a Status line opens with, or None if it opens with nothing known."""
    for word in STATUS_WORDS:
        if line.startswith(word):
            return word
    return None


def technology_words(values: list[facets.Value]) -> dict[str, re.Pattern[str]]:
    """Each taggable Technology value, with a pattern that finds its slug or label as a whole word."""
    words = {}
    for value in values:
        if value.scheme == "Technology" and not value.group:
            names = {value.slug, value.label}
            words[value.slug] = re.compile(r"(?<![\w.-])(" + "|".join(map(re.escape, names)) + r")(?![\w-])", re.I)
    return words


# ---- Decisions ---------------------------------------------------------------------------------


def decision_claim(lines: list[str]) -> str | None:
    """What a decision decides: the start of its Decision section, read as text.

    A title names a decision, often by a noun phrase such as "Provenance Model", which says too
    little for a question phrased as the problem to reach it. So the claim is the section's own
    words up to the claim limit: paragraphs, subheadings and table rows, without code blocks or a
    table's header row. A bold lead that is a whole sentence, as in a numbered list of decisions,
    is the claim by itself. A lead-in such as "Rules:" is not."""
    start = next((i for i, l in enumerate(lines) if re.match(r"^##\s+Decision", l)), None)
    if start is None:
        return None
    items: list[str] = []
    fenced = False
    for line in lines[start + 1 :]:
        stripped = line.strip()
        if line.startswith("## "):
            break
        if stripped.startswith("```"):
            fenced = not fenced
            continue
        if fenced or not stripped or stripped.startswith(("<!--", ">")):
            continue
        if SEPARATOR_RE.match(stripped):
            if items:
                items.pop()  # the row above a separator is the table's header
            continue
        if stripped.startswith("|"):
            items.append(", ".join(c for c in table_cells(stripped) if c))
        else:
            items.append(re.sub(r"^(#+\s*|[-*]\s+)", "", stripped))
        if not items[:-1] and (bold := BOLD_RE.match(re.sub(r"^\d+\.\s*", "", items[-1]))):
            lead = bold.group("claim").strip()
            if len(lead) > 30 and not lead.endswith(":"):
                return shorten(lead, CLAIM_LIMIT)
        if sum(map(len, items)) >= CLAIM_LIMIT:
            break
    text = re.sub(r"\*\*|`", "", " ".join(items))
    return shorten(text, CLAIM_LIMIT) if text.strip() else None


def decision_sections(lines: list[str]) -> list[tuple[str, int, int]]:
    """The parts of a decision file that state a rule of their own, as ``(text, start, end)``.

    Each numbered item of the Decision section and each ``## Addendum`` section. A decision's claim
    is the opening of its Decision section, so a rule stated further down, or in an addendum, would
    never be found by its subject. Code blocks are left out of the text, which is cut at
    ``SECTION_LIMIT``."""
    top = anchors.headings(lines)
    decision = next((i for i, (n, lv, _) in enumerate(top) if lv == 2 and lines[n - 1].startswith("## Decision")), None)
    found: list[tuple[int, int, str]] = []
    if decision is not None:
        last = anchors.section_end(top, decision, len(lines))
        opens: list[int] = []
        fenced = False
        for number in range(top[decision][0] + 1, last + 1):
            if lines[number - 1].lstrip().startswith(("```", "~~~")):
                fenced = not fenced
            elif not fenced and NUMBERED_RE.match(lines[number - 1]):
                opens.append(number)
        for start, stop in zip(opens, opens[1:] + [last + 1]):
            end = stop - 1
            while end > start and not lines[end - 1].strip():
                end -= 1
            found.append((start, end, ""))
    for number, level, _ in top:
        if level == 2 and lines[number - 1].startswith("## Addendum"):
            found.append((*anchors.section_at(lines, number), re.sub(r"^## Addendum[^:]*:\s*", "", lines[number - 1])))
    out = []
    for start, end, title in found:
        body, fenced = [title], False
        for line in lines[start - 1 : end]:
            stripped = line.strip()
            if stripped.startswith(("```", "~~~")):
                fenced = not fenced
            elif not fenced and stripped and not stripped.startswith(("#", "<!--")) \
                    and not SEPARATOR_RE.match(stripped) and not STATUS_RE.match(stripped):
                body.append(stripped.replace("|", " "))
        text = re.sub(r"\*\*|`", "", " ".join(body))
        out.append((shorten(NUMBERED_RE.sub("", text.strip(), 1), SECTION_LIMIT), start, end))
    return out


def section_numbers(lines: list[str], start: int, end: int) -> list[int]:
    """The decision numbers the lines from ``start`` to ``end`` open, outside code blocks."""
    numbers, fenced = [], False
    for line in lines[start - 1 : end]:
        if line.lstrip().startswith(("```", "~~~")):
            fenced = not fenced
        elif not fenced and (match := NUMBER_RE.match(line)):
            numbers.append(int(match.group("n")))
    return numbers


def supersessions(lines: list[str], sections: list[tuple[str, int, int]], rel: str, out: Extract) -> list[tuple[int, str, int]]:
    """What each addendum's bold lead reverses or narrows, as ``(section, edge, addendum section)``
    indexes into ``sections``.

    A number names the numbered decision of the Decision section, and otherwise the one addendum
    that numbers it, as an addendum may continue the numbering. A number that names neither, or
    names several addenda and no decision, is reported, never guessed."""
    is_addendum = [lines[start - 1].startswith("## Addendum") for _, start, _ in sections]
    by_number: dict[int, int] = {}
    in_addenda: dict[int, list[int]] = {}
    for index, (_, start, end) in enumerate(sections):
        if is_addendum[index]:
            for number in section_numbers(lines, start, end):
                in_addenda.setdefault(number, []).append(index)
        elif (match := NUMBER_RE.match(lines[start - 1])):
            by_number.setdefault(int(match.group("n")), index)
    for number, places in in_addenda.items():
        if number not in by_number and len(set(places)) == 1:
            by_number[number] = places[0]
    edges = []
    for index, (_, start, end) in enumerate(sections):
        if not is_addendum[index]:
            continue
        # A lead quoted in a code span is an example of the grammar, never a lead.
        for match in SUPERSESSION_RE.finditer(re.sub(r"`[^`]*`", "", "\n".join(lines[start - 1 : end]))):
            for number in map(int, re.findall(r"\d+", match.group("numbers"))):
                target = by_number.get(number)
                if target is None:
                    out.problems.append(f"{rel}:{start}: {match.group('verb')} decision {number}, which names no numbered decision of the file")
                elif target != index:
                    edges.append((target, SUPERSESSION_EDGE[match.group("verb")], index))
    return edges


def decisions(ctx: Context) -> None:
    """One node per decision file, named by its title, with what it decides as the claim and its
    Related line as declared edges."""
    out, scope = ctx.out, ctx.scope
    for family in ctx.families("file"):
        files = family.paths()
        defined = {normalise(m.group(0)) for p in files if (m := head(family.pattern, p.stem))}
        title_re = family.pattern.derive(lambda p: rf"^#\s+(?:{p})\s*[:.]\s*(?P<title>.+?)\s*$")
        for path in files:
            if not (match := head(family.pattern, path.stem)):
                continue
            canonical = match.group(0)
            if ctx.moved(canonical):
                continue
            subject = node(scope.name, canonical)
            rel = ctx.rel(path)
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
            seen_status = False

            ctx.add(subject, RDF_TYPE, ki(ctx.types.types.get(family.type or "decision", "Decision")))
            ctx.add(subject, ki("identifier"), ox.Literal(canonical))
            ctx.add(subject, ki("definedIn"), document(scope.name, rel))
            for number, line in enumerate(lines, 1):
                # A heading may spell the identifier with a space or a non-breaking hyphen, "ADR A-07".
                if (title := title_re.match(re.sub(r"^(#+\s+\w+)[‑ ]", r"\1-", line))) is not None:
                    name = shorten(title.group("title"), CLAIM_LIMIT)
                    ctx.add(subject, RDFS_LABEL, ox.Literal(name))
                    ctx.add(subject, ki("claim"), ox.Literal(decision_claim(lines) or name))
                    start, end = anchors.section_at(lines, number)
                    ctx.add(subject, ki("pointer"), ox.Literal(f"{rel}:{start}-{end}"))
                elif (st := STATUS_RE.match(line)) is not None and not seen_status:
                    # Only the header's Status line is the decision's status. A later one belongs to a
                    # dated addendum, and taking both would give one node two statuses, which would
                    # make the check that no Accepted decision depends on a Proposed one meaningless.
                    seen_status = True
                    line_status = st.group("status")
                    # Publication is a flag, not a lifecycle state, so a published decision keeps the
                    # state its own line gives it after the publication clause.
                    if (published := PUBLISHED_RE.match(line_status)) is not None:
                        ctx.add(subject, ki("publishedOn"), ox.Literal(published.group("date")))
                        out.bump("published")
                        line_status = line_status[published.end():].strip()
                    word = status_of(line_status)
                    if word is None:
                        out.problems.append(f"{rel}:{number}: Status line opens with no known word")
                    else:
                        ctx.add(subject, ki("status"), ki(word))
                        out.bump(f"status:{word}")
                    if word == "Superseded":
                        # "Superseded by ADR-104" names the live decision, so a reader of this one is sent there.
                        successors = [c for c in ctx.mentions(line_status)
                                      if c.split(":", 1)[0] == scope.name and family.pattern.fullmatch(c.split(":", 1)[1])
                                      and normalise(c.split(":", 1)[1]) != normalise(canonical)]
                        for other in successors[:1]:
                            ctx.add(subject, ki("supersededBy"), node_of(other))
                            out.bump("supersededBy")
                        if not successors:
                            out.problems.append(f"{rel}:{number}: {canonical} is Superseded and its Status line names no successor")
                elif (related := RELATED_RE.match(line)) is not None:
                    for other in ctx.mentions(related.group("rest")):
                        name, local = other.split(":", 1)
                        if name == scope.name and normalise(local) in defined and normalise(local) != normalise(canonical):
                            ctx.add(subject, ki("relatedTo"), node_of(other))
                            out.bump("relatedTo")
            # Auxiliary nodes, not entries: no type and no identifier, so no query for entries returns them.
            # The embedder scores them and a ranking reports the best one's pointer under the decision.
            found = decision_sections(lines)
            for count, (text, start, end) in enumerate(found, 1):
                section = ox.NamedNode(f"{subject.value}/section-{count}")
                ctx.add(section, ki("sectionOf"), subject)
                ctx.add(section, ki("claim"), ox.Literal(text))
                ctx.add(section, ki("pointer"), ox.Literal(f"{rel}:{start}-{end}"))
                out.bump("decision-section")
                if (dated := ADDENDUM_DATE_RE.match(lines[start - 1])):
                    out.addenda[(scope.name, normalise(canonical), dated.group(1))] = section
            for target, edge, by in supersessions(lines, found, rel, out):
                ctx.add(ox.NamedNode(f"{subject.value}/section-{target + 1}"), ki(edge), ox.NamedNode(f"{subject.value}/section-{by + 1}"))
                out.bump(edge)
            if not seen_status:
                # A decision may carry its status as a `## Status` section rather than a `**Status:**`
                # header field. Reported rather than guessed at, because a node with no status is
                # invisible to every check that compares one.
                out.problems.append(f"{rel}: no **Status:** header field, so {canonical} has no status")
                out.bump("decision-without-status")
            out.bump("decision")


# ---- Registers ---------------------------------------------------------------------------------


def targets(ctx: Context, cell: str, here: str) -> list[ox.NamedNode]:
    """What a Bears on cell names: entries by identifier, and declared terms by CURIE. A CURIE whose
    prefix no ontology declares is reported. Whether each target exists is checked once the terms
    are loaded (``dangling``)."""
    found = [node_of(c) for c in ctx.mentions(cell)]
    for match in CURIE_RE.finditer(cell):
        if ctx.config.scope(match.group("prefix")) is not None:
            continue  # a qualified identifier, which mentions has already read
        namespace = ctx.prefixes.get(match.group("prefix"))
        if namespace is None:
            ctx.out.problems.append(f"{here} has Bears on '{match.group(0)}', whose prefix no ontology document declares")
        else:
            found.append(term(ctx.scope.name, namespace + match.group("local")))
    return found


def addendum_refs(ctx: Context, cell: str) -> list[tuple[str, str, str]]:
    """The addenda a Narrowed by cell names, as ``(spelling, scope, day)`` and a key into
    ``Extract.addenda``: a decision of a ``file`` family and the day of its addendum."""
    refs = []
    for family in (f for f in visible_families(ctx.config, ctx.scope) if f.rule == "file"):
        form = family.pattern.derive(lambda p: rf"(?<![\w-])(?P<id>{p})\s+addendum\s+(?P<day>\d{{4}}-\d{{2}}-\d{{2}})", regex.I)
        for m in form.finditer(cell):
            refs.append((m.group("id"), m.group("day"), m.start()))
    return [(spelling, day) for spelling, day, _ in sorted(refs, key=lambda r: r[2])]


def register_rows(ctx: Context) -> None:
    """One node per row of each register of the scope, read by column header (see ``registers``)."""
    out, scope = ctx.out, ctx.scope
    rows, problems = registers.read_scope(scope, ctx.types, ctx.taggable)
    out.problems += problems
    columns = {c.property: c for c in ctx.types.columns.values()}
    for row in (r for r in rows if not ctx.moved(r.identifier)):
        subject = node(scope.name, row.identifier)
        here = f"{row.source}:{row.line}: {row.identifier}"
        ctx.add(subject, RDF_TYPE, ki(row.cls))
        ctx.add(subject, ki("identifier"), ox.Literal(row.identifier))
        if row.claim is not None:
            ctx.add(subject, ki("claim"), ox.Literal(row.claim))
        if row.label is not None:
            ctx.add(subject, RDFS_LABEL, ox.Literal(row.label))
        ctx.add(subject, ki("status"), ki(row.status))
        # The defining row, kept apart from the Pointer column so a reader prints it first.
        ctx.add(subject, ki("row"), ox.Literal(f"{row.source}:{row.line}-{row.line}"))
        ctx.add(subject, ki("pointer"), ox.Literal(",".join(row.pointer)))
        for prop, cells in row.values.items():
            column = columns[prop]
            for cell in cells:
                if column.kind == "controlled":
                    ctx.add(subject, ki(prop), ki(cell))
                elif column.kind == "facet":
                    ctx.add(subject, ki(prop), ox.NamedNode(facets.NS + cell))
                    out.bump(f"facet:{column.scheme}")
                elif column.kind == "ids":
                    for other in ctx.mentions(cell):
                        name, local = other.split(":", 1)
                        if (name, normalise(local)) != (scope.name, normalise(row.identifier)):
                            ctx.add(subject, ki(prop), node_of(other))
                            out.bump(prop)
                elif column.kind == "targets":
                    for target in targets(ctx, cell, here):
                        ctx.add(subject, ki(prop), target)
                        out.bump(prop)
                elif column.kind == "addenda":
                    refs = addendum_refs(ctx, cell)
                    if not refs:
                        out.problems.append(f"{here} has {prop} '{cell}', which names no addendum as '<ID> addendum YYYY-MM-DD'")
                    for spelling, day in refs:
                        try:
                            name, local = resolve(ctx.config, spelling, scope).split(":", 1)
                        except Unresolved:
                            name, local = scope.name, spelling
                        target = out.addenda.get((name, normalise(local), day))
                        if target is None:
                            out.problems.append(f"{here} has {prop} '{spelling} addendum {day}', and {spelling} has no addendum of that day")
                        else:
                            ctx.add(subject, ki(prop), target)
                            out.bump(prop)
                elif column.kind in ("names", "module"):
                    # A names cell is an edge to the node of that name, which something derived may define, so a
                    # check can ask whether it exists. A module stays a literal unless an extractor of the project
                    # declared units. What a module means belongs to the project, so it is resolved only through
                    # those, and a name they do not know is reported and kept. A module loses its code quotes,
                    # a folder's trailing slash and any annotation in parentheses.
                    units = out.units.get(scope.name) if column.kind == "module" else None
                    for name in (re.sub(r"\s*\(.*?\)", "", n).strip(" `").rstrip("/") if column.kind == "module" else n.strip() for n in cell.split(",")):
                        if not name:
                            continue
                        if column.kind == "names":
                            ctx.add(subject, ki(prop), node(scope.name, name))
                            out.bump(prop)
                            continue
                        if units and name in units:
                            for unit in units[name]:
                                ctx.add(subject, ki(prop), ox.NamedNode(f"{KI}module/{scope.name}/{unit}"))
                                out.bump(prop)
                            continue
                        if units:
                            out.problems.append(f"{here} has {prop} '{name}', which names no unit an extractor declared")
                        ctx.add(subject, ki(prop), ox.Literal(name))
                        out.bump(prop)
                else:
                    ctx.add(subject, ki(prop), ox.Literal(cell))
                    if prop == "problemShape":
                        out.bump("problem-shape")
                    if prop == "doesNotCover":
                        out.bump(prop)
        out.bump(row.cls)


# ---- Headings ----------------------------------------------------------------------------------


def discoveries(ctx: Context) -> None:
    """One node per discovery, whose heading already is its claim.

    A finding's technology is derived from its Evidence line, which names the engines and versions it
    was found on, so the fact is read where the record states it and never authored twice. "Both
    stores" means the stores the record's own Stores covered line names, and an engine named in the
    heading, which is the finding's claim, counts too. Its activity and quality are not stated, so it
    carries none, which hides it from no question."""
    out, scope = ctx.out, ctx.scope
    for family in ctx.families("heading"):
        cls = ctx.types.types.get(family.type or "discovery", "Discovery")
        for path in family.paths():
            rel = ctx.rel(path)
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
            covered = next((l for l in lines if l.startswith("**Stores covered:**")), "")
            both = {slug for slug, pattern in ctx.words.items() if pattern.search(covered)}
            for number, line in enumerate(lines, 1):
                stripped = line.strip()
                if not stripped.startswith("#"):
                    continue
                heading = stripped.lstrip("#").strip()
                match = head(family.pattern, heading)
                if not match:
                    continue
                canonical = match.group(0)
                if ctx.moved(canonical):
                    continue
                subject = node(scope.name, canonical)
                claim = heading[match.end() :].lstrip(". ").strip()
                ctx.add(subject, RDF_TYPE, ki(cls))
                ctx.add(subject, ki("identifier"), ox.Literal(canonical))
                start, end = anchors.section_at(lines, number)
                ctx.add(subject, ki("pointer"), ox.Literal(f"{rel}:{start}-{end}"))
                ctx.add(subject, ki("claim"), ox.Literal(shorten(claim, CLAIM_LIMIT)))
                evidence = next((l for l in lines[start - 1 : end] if l.startswith("**Evidence:**")), "")
                bears = next((l for l in lines[start - 1 : end] if l.startswith("**Bears on:**")), "")
                for target in targets(ctx, bears.removeprefix("**Bears on:**"), f"{rel}:{number}: {canonical}") if bears else []:
                    ctx.add(subject, ki("bearsOn"), target)
                    out.bump("bearsOn")
                for slug, pattern in ctx.words.items():
                    if pattern.search(evidence) or pattern.search(heading) or ("both stores" in evidence and slug in both):
                        ctx.add(subject, ki("technology"), ox.NamedNode(facets.NS + slug))
                        out.bump("facet:Technology:derived")
                out.bump(family.name)


# ---- Questions ---------------------------------------------------------------------------------


@dataclass(frozen=True)
class Question:
    """A question as a plan or a sketch raises it: its own words, the answer beside it if any, and
    the lines that hold both."""

    identifier: str
    start: int
    end: int
    question: str
    answer: str
    answered: bool
    answered_on: str | None


@functools.lru_cache(maxsize=None)
def _question_forms(id_pattern: Pattern) -> tuple[Pattern, Pattern]:
    # ``**LG-Q7. A question?**``, ``- **C6-Q1. A question.** text`` and ``- **C3-Q1.** text``.
    lead = id_pattern.derive(lambda p: rf"^\s*(?:[-*]\s+|\d+\.\s+)?\*\*(?P<id>{p})(?:[.:](?P<inside>[^*]*))?\*\*\s*(?P<after>.*)$")
    row = id_pattern.derive(lambda p: rf"^\|\s*(?:\*\*)?(?P<id>{p})(?:\*\*)?\s*\|(?P<rest>.*)$")
    return lead, row


def _sentence(text: str) -> tuple[str, str]:
    """The first sentence of a text and the rest of it."""
    match = re.match(r"(.+?[.?!])(\s+|$)", text)
    return (match.group(1), text[match.end():]) if match else (text, "")


def questions_in(lines: list[str], id_pattern: Pattern) -> list[Question]:
    """Every question a document raises by a bold lead or a table row, in order.

    A lead's paragraph runs to the next blank line or the next lead. A row is its own line, its
    second cell the question and the rest its options and answer. A question is answered when its
    text says Answered, with the date that follows the word if one does."""
    lead_re, row_re = _question_forms(id_pattern)
    found: list[Question] = []
    for number, line in enumerate(lines, 1):
        row = row_re.match(line)
        lead = None if row else lead_re.match(line)
        if row:
            cells = [c.strip() for c in row.group("rest").split("|")]
            cells = [c for c in cells if c]
            question = cells[0] if cells else ""
            answer = next((c for c in cells[1:] if ANSWERED_RE.search(c)), cells[-1] if len(cells) > 1 else "")
            end = number
        elif lead:
            body = [lead.group("after").strip()]
            end = number
            while end < len(lines) and lines[end].strip() and not lead_re.match(lines[end]):
                body.append(lines[end].strip())
                end += 1
            text = " ".join(b for b in body if b)
            inside = (lead.group("inside") or "").strip()
            question, answer = (inside, text) if inside else _sentence(text)
        else:
            continue
        answered = ANSWERED_RE.search(answer) or ANSWERED_RE.search(question)
        found.append(Question(
            (row or lead).group("id"), number, end, question.strip(), answer.strip(),
            bool(answered), answered.group("date") if answered else None,
        ))
    return found


def questions(ctx: Context, today: dt.date | None = None) -> None:
    """One node per question a plan or a sketch raises, open or answered.

    The claim is the question and the start of its answer, each cut at the claim limit, so a
    question in the words of its answer still finds it. An identifier defined twice keeps its first
    definition, a plan's before a sketch's. An answer naming the entry it was promoted to, ``now
    MEC-nn``, gives that entry ki:answers to the question. An answered question whose answer states
    a rule and names no such entry, answered more than PROMOTION_DAYS ago, is reported, never failed."""
    out, scope = ctx.out, ctx.scope
    today = today or dt.date.today()
    for family in ctx.families("question"):
        cls = ctx.types.types.get(family.type or "question", "Question")
        seen: set[str] = set()
        for path in family.paths():
            rel = ctx.rel(path)
            for q in questions_in(path.read_text(encoding="utf-8", errors="replace").splitlines(), family.pattern):
                key = normalise(q.identifier)
                if key in seen:
                    out.bump("question-defined-again")
                    continue
                seen.add(key)
                if ctx.moved(q.identifier):
                    continue
                subject = node(scope.name, q.identifier)
                answer = q.answer.replace("**", "")
                claim = shorten(q.question.replace("**", ""), CLAIM_LIMIT) + (" " + shorten(answer, CLAIM_LIMIT) if answer else "")
                ctx.add(subject, RDF_TYPE, ki(cls))
                ctx.add(subject, ki("identifier"), ox.Literal(q.identifier))
                ctx.add(subject, ki("claim"), ox.Literal(claim))
                ctx.add(subject, ki("pointer"), ox.Literal(f"{rel}:{q.start}-{q.end}"))
                ctx.add(subject, ki("status"), ki("Answered" if q.answered else "Open"))
                ctx.add(subject, ki("definedIn"), document(scope.name, rel))
                promoted = [e for m in PROMOTED_RE.finditer(answer) for e in ctx.mentions(m.group("ids"))]
                for entry in promoted:
                    ctx.out.quads.append(ox.Quad(node_of(entry), ki("answers"), subject, ctx.graph))
                    out.bump("answers")
                if q.answered and not promoted and q.answered_on and RULE_WORDS_RE.search(answer) \
                        and (today - dt.date.fromisoformat(q.answered_on)).days > PROMOTION_DAYS:
                    out.findings.append(
                        f"{q.identifier} ({rel}:{q.start}) was answered {q.answered_on} with a rule and names no entry "
                        f"it was promoted to, so the rule lives only in a plan. Promote it and write 'now <ID>' in the answer"
                    )
                out.bump(f"question:{'answered' if q.answered else 'open'}")


# ---- Dangling ----------------------------------------------------------------------------------

DANGLING = f"""
PREFIX ki: <{KI}>
SELECT ?id ?edge ?o WHERE {{
  GRAPH ?gi {{ VALUES ?p {{ ki:distinguishedFrom ki:bearsOn }} ?s ?p ?o ; ki:identifier ?id . }}
  FILTER (STRSTARTS(STR(?gi), "{KI}index/"))
  FILTER NOT EXISTS {{ GRAPH ?g {{ ?o ki:identifier ?any }} }}
  BIND (REPLACE(STR(?p), "^.*#", "") AS ?edge)
}}"""


def dangling(store: ox.Store, out: Extract) -> None:
    """A signpost to nothing is reported: a Distinguished from or Bears on that names no entry or
    declared term, in any scope. Run once the terms are loaded, since a Bears on may name a term."""
    for row in store.query(DANGLING):
        target = re.sub(r"^term/[^/]+/", "term ", re.sub(r"^node/[^/]+/", "", str(row["o"].value).removeprefix(KI)))
        out.problems.append(f"{row['id'].value} has {row['edge'].value} {target}, which names no entry or declared term")
