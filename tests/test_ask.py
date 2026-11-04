# SPDX-License-Identifier: MIT
# Ported from LATTICE's tools/knowledge/test_ask.py and the find tests of test_embed.py, relicensed MIT
# by its author, over stores built in a temporary folder with a stand-in model.
"""What find and read show beside an answer, what the ask log keeps, and what a stack can see.

The index returns the right entry and loses what sits at its edge: the case it does not cover, the
entry it is confused with, the addendum that reversed it, the debt recorded against it. These tests
build small stores with a stand-in model and check that each of those reaches the reader in the
output a question already prints, that every question leaves a line in the log, and that a question
asked in one project never returns another project's entries.
"""

from __future__ import annotations

import os
from importlib import resources

import pyoxigraph as ox
import pytest

from test_index_core import Words
from vyvid import ask, embed, facets
from vyvid import build as builder
from vyvid.config import load
from vyvid.model import FACETS_GRAPH, KI, RDF_TYPE, RDFS_LABEL, TBOX_GRAPH, index_graph, ki, node, term, terms_graph
from vyvid.resolve import layers

CONFIG = """
[framework]
store = "STORE"

[[domains]]
name = "tools"
path = "DOMAIN"
families = { NOTE = {} }

[[projects]]
name = "proj"
code = "CODE"
domains = ["tools"]

[projects.families]
STD = { defined = "docs:standards.md", type = "standard" }
MEC = {}
CAP = {}
TD = {}


[[projects]]
name = "rival"
code = "RIVAL"

[projects.families]
STD = { defined = "docs:standards.md", type = "standard" }
MEC = {}
"""


class World:
    """A configuration of two projects and a domain, and a store the tests fill with quads."""

    def __init__(self, tmp_path, project: str = "proj"):
        self.tmp = tmp_path
        text = CONFIG.replace("STORE", (tmp_path / "idx").as_posix()).replace("CODE", (tmp_path / "code").as_posix()).replace("DOMAIN", (tmp_path / "tools").as_posix())
        (tmp_path / "config.toml").write_text(text.replace("RIVAL", (tmp_path / "rival").as_posix()), encoding="utf-8")
        self.config = load(tmp_path / "config.toml")
        self.project = self.config.projects[project]
        self.store = ox.Store()
        self.ask = ask.Asker(self.config, self.project, layers(self.config, self.project), tmp_path / "idx", self.store, Words())

    def vectorise(self) -> int:
        entries = {str(r["n"].value): embed.join_text([r["label"] and r["label"].value, r["claim"].value,
                                                       r["shape"] and r["shape"].value, r["uncovered"] and r["uncovered"].value])
                   for r in self.store.query(builder.TEXTS)}
        # A term's text comes from the extractor that declared it, here its claim.
        entries.update({str(r["n"].value): embed.join_text([r["c"].value]) for r in self.store.query(
            f'SELECT ?n ?c WHERE {{ GRAPH ?g {{ ?n <{KI}claim> ?c }} FILTER (STRSTARTS(STR(?g), "{KI}terms/")) }}')})
        return embed.build(entries, self.ask.directory, self.config.embedding, self.ask.model)

    def entry(self, ident, kind, claim, scope="proj", phase=None, activity=None):
        n = node(scope, ident)
        quads = [(n, ki("identifier"), ox.Literal(ident)), (n, ki("claim"), ox.Literal(claim)),
                 (n, RDF_TYPE, ki(kind)), (n, RDFS_LABEL, ox.Literal(ident.lower()))]
        if phase:
            quads.append((n, ki("phase"), ki(phase)))
        if activity:
            quads.append((n, ki("activity"), ox.NamedNode(facets.NS + activity)))
        self.store.extend([ox.Quad(s, p, o, index_graph(scope)) for s, p, o in quads])

    def fact(self, ident, prop, value, scope="proj"):
        obj = value if isinstance(value, ox.NamedNode) else ox.Literal(value)
        self.store.add(ox.Quad(node(scope, ident), ki(prop), obj, index_graph(scope)))

    def section(self, parent, number, claim, pointer, scope="proj"):
        n = ox.NamedNode(f"{node(scope, parent).value}/section-{number}")
        self.store.extend([ox.Quad(n, ki("sectionOf"), node(scope, parent), index_graph(scope)),
                           ox.Quad(n, ki("claim"), ox.Literal(claim), index_graph(scope)),
                           ox.Quad(n, ki("pointer"), ox.Literal(pointer), index_graph(scope))])
        return n

    def tbox(self):
        self.store.bulk_load(input=resources.files("vyvid").joinpath("data/knowledge.ttl").read_bytes(), format=ox.RdfFormat.TURTLE, to_graph=TBOX_GRAPH)

    def facets(self):
        schemes, values = facets.merge([("default", facets.default_register())])
        self.store.bulk_load(input=facets.turtle(schemes, values).encode("utf-8"), format=ox.RdfFormat.TURTLE, to_graph=FACETS_GRAPH)


@pytest.fixture
def w(tmp_path):
    return World(tmp_path)


def table(out: str) -> list[list[str]]:
    """The cells of a printed table's rows, read by the columns its dashes mark, so an empty cell
    stays a cell, without the indented line find prints under each row."""
    lines = out.splitlines()
    at = next(i for i, line in enumerate(lines) if line.startswith("---"))
    spans, column = [], 0
    for dashes in lines[at].split("  "):
        spans.append((column, column + len(dashes)))
        column += len(dashes) + 2
    rows = []
    for line in lines[at + 1 :]:
        if not line.strip():
            break
        if not line.startswith(" "):
            rows.append([line[a:b].strip() for a, b in spans])
    return rows


def under_row(out: str, ident: str) -> str:
    """The indented line find prints under the row of ``ident``."""
    lines = out.splitlines()
    i = next(n for n, line in enumerate(lines) if not line.startswith(" ") and line.split()[1:2] == [ident])
    return lines[i + 1].strip()


def find(w, words, kinds=(), phases=(), audiences=(), facets=None, limit=8):
    return ask.find(w.ask, words, set(kinds), set(phases), set(audiences), limit, facets)


# ---- Ranking, filtering and the fallback --------------------------------------------------------


@pytest.fixture
def index(w):
    w.entry("MEC-1", "Mechanism", "a ledger account consumed and restored", phase="Runtime")
    w.entry("CAP-1", "Capability", "minting in Java", phase="Runtime")
    w.entry("STD-1", "Standard", "slow slow tests", phase="Development")
    w.vectorise()
    return w


def test_find_ranks_by_meaning_and_filters_exactly(index, capsys):
    find(index, "a ledger")
    assert table(capsys.readouterr().out)[0][1] == "MEC-1"
    find(index, "a ledger", {"Capability", "Standard"})
    out = capsys.readouterr().out
    assert "MEC-1" not in out and "CAP-1" in out
    find(index, "slow", phases={"Runtime"})
    assert "STD-1" not in capsys.readouterr().out


def test_find_falls_back_when_nothing_is_close(index, capsys):
    find(index, "graph")
    out = capsys.readouterr().out
    assert "weak match" in out and "Fall back to reading the documents" in out and "ask again\nwith --kind term" in out


def test_find_falls_back_when_no_entry_has_the_facets(index, capsys):
    find(index, "a ledger", {"Debt"})
    out = capsys.readouterr().out
    assert "no entry has the facets" in out and "Fall back to reading the documents" in out


def test_find_falls_back_when_there_are_no_vectors(index, capsys):
    (index.ask.directory / embed.VECTORS).unlink()
    find(index, "a ledger")
    out = capsys.readouterr().out
    assert "find cannot rank here" in out and "Fall back to reading the documents" in out


def test_the_thresholds_are_the_configurations_not_constants(index, capsys):
    """A model's weak score is part of its configuration, so a stricter one calls a closer match weak."""
    find(index, "a ledger")
    assert "weak match" not in capsys.readouterr().out
    index.config.embedding = embed.ModelSpec(weak=1.5)
    find(index, "a ledger")
    assert "no entry scored 1.5 or more" in capsys.readouterr().out


def test_a_matching_facet_raises_an_entry_and_a_mismatch_hides_none(w, capsys):
    """Activity is a judgement two taggers can disagree on, so it boosts and never filters. PAT-1
    trails MEC-1 by about 0.01 in meaning, less than one boost, so naming its activity puts it first,
    and MEC-1 is still listed."""
    w.entry("MEC-1", "Mechanism", "ledger", activity="ontology-design")
    w.entry("PAT-1", "Pattern", "ledger " * 7 + "minting", activity="solution-design")
    w.vectorise()
    find(w, "ledger")
    assert table(capsys.readouterr().out)[0][1] == "MEC-1"
    find(w, "ledger", facets={"activities": {"solution-design"}})
    rows = table(capsys.readouterr().out)
    assert rows[0][1] == "PAT-1" and rows[0][0].endswith("+")
    assert any(row[1] == "MEC-1" for row in rows[:2]), "a mismatched activity must not hide an entry"


def test_an_identifier_in_the_question_ranks_its_entry_first(w, capsys):
    w.entry("MEC-1", "Mechanism", "a ledger account")
    w.entry("STD-9", "Standard", "graph graph graph")
    w.vectorise()
    find(w, "a ledger account std9")
    assert table(capsys.readouterr().out)[0][1] == "STD-9"


def test_find_lists_what_the_top_answers_are_linked_to(w, capsys):
    """A standard that supports the principle a question finds is shown with it, whatever its words,
    because its author declared the link. STD-1 shares no word with the question."""
    w.entry("PRI-1", "Principle", "ledger accounts are restored")
    w.entry("STD-1", "Standard", "graph graph graph")
    w.fact("STD-1", "supports", node("proj", "PRI-1"))
    w.vectorise()
    find(w, "ledger", {"Principle"})
    out = capsys.readouterr().out
    assert "linked to the top answers" in out and "supports PRI-1" in out and "STD-1" in out


def test_a_phase_matches_up_and_down_its_chain_and_never_a_sibling(w):
    """An entry tagged runtime binds in every environment, so a question about production finds it.
    A question about runtime finds one tagged testing. A question about testing never finds one
    tagged production."""
    w.tbox()
    assert ask.phase_matches(w.ask, {"Production"}) == {"Production", "Runtime"}
    assert ask.phase_matches(w.ask, {"Runtime"}) == {"Runtime", "Testing", "Benchmarking", "Production"}
    assert "Production" not in ask.phase_matches(w.ask, {"Testing"})
    assert ask.phase_matches(w.ask, {"Authoring"}) == {"Authoring"}


def test_the_filters_are_the_values_the_stack_declares(w):
    w.tbox()
    w.facets()
    kinds, phases, audiences, wanted = ask.filters(w.ask, kind="standard,term", phase="production", activity="data-modelling")
    assert kinds == {"Standard", "Term"} and phases == {"Production", "Runtime"} and not audiences
    assert "conceptual-data-modelling" in wanted["activities"], "a value matches what is under it"
    with pytest.raises(ValueError, match="--kind nonsense is not one of"):
        ask.filters(w.ask, kind="nonsense")
    with pytest.raises(ValueError, match="--tech nonsense is not a value of the Technology facet"):
        ask.filters(w.ask, tech="nonsense")


def test_a_kind_can_be_excluded_and_every_other_kept(w):
    """Questions cost some ranking, so an agent whose answers are crowded by them leaves them out
    without naming every other kind, and terms stay out unless they are named."""
    every = set(w.ask.kinds().values()) - ask.asked_for(w.ask)
    assert ask.without(w.ask, set(), {"Question"}) == every - {"Question"}
    assert ask.without(w.ask, {"Standard", "Question"}, {"Question"}) == {"Standard"}
    assert ask.without(w.ask, set(), set()) == set()


# ---- What sits beside an answer ------------------------------------------------------------------


def test_find_prints_the_whole_claim_under_each_row(w, capsys):
    """The table cuts a claim at 90 characters, and a qualification is usually written after that."""
    claim = "A ledger amount is never restored within a period, " + "except by the reinstatement credit the terms state. " * 2
    w.entry("STD-1", "Standard", claim)
    w.vectorise()
    find(w, "ledger")
    assert len(claim) > 90 and claim.strip() in under_row(capsys.readouterr().out, "STD-1")


def test_flags_mark_a_boundary_a_debt_and_a_proposed_entry(w, capsys):
    """! says the entry states a case it does not cover, TD that an open debt bears on it, and ? that
    it is Proposed. The line under the row says what each is, and a legend names the marks shown."""
    w.entry("MEC-1", "Mechanism", "a ledger account per key")
    w.fact("MEC-1", "doesNotCover", "a keyed child under a keyed parent")
    w.fact("MEC-1", "status", ki("Proposed"))
    w.entry("TD-1", "Debt", "minting minting")
    w.fact("TD-1", "status", ki("Open"))
    w.fact("TD-1", "bearsOn", node("proj", "MEC-1"))
    w.vectorise()
    find(w, "ledger", {"Mechanism"})
    out = capsys.readouterr().out
    row = table(out)[0]
    assert row[1] == "MEC-1" and row[4] == "!TD?"
    line = under_row(out, "MEC-1")
    assert "Does not cover: a keyed child under a keyed parent." in line and "Open debt: TD-1." in line
    assert "! the entry states a case it does not cover" in out and "TD an open debt" in out and "? the entry is Proposed" in out


def test_an_open_backlog_idea_flags_the_entry_it_bears_on(w, capsys):
    """BL says an unbuilt idea on the backlog bears on the entry, and the line under the row names it."""
    w.entry("CAP-1", "Capability", "compile a mapping to RML")
    w.entry("BL-1", "Backlog", "compile a mapping to XSLT")
    w.fact("BL-1", "status", ki("Open"))
    w.fact("BL-1", "bearsOn", node("proj", "CAP-1"))
    w.vectorise()
    find(w, "mapping", {"Capability"})
    out = capsys.readouterr().out
    assert table(out)[0][4] == "BL" and "On the backlog, not built: BL-1." in under_row(out, "CAP-1")


def test_a_closed_debt_does_not_flag_its_entry(w, capsys):
    w.entry("MEC-1", "Mechanism", "a ledger account")
    w.entry("TD-1", "Debt", "minting")
    w.fact("TD-1", "status", ki("Accepted"))
    w.fact("TD-1", "bearsOn", node("proj", "MEC-1"))
    w.vectorise()
    find(w, "ledger", {"Mechanism"})
    assert "TD" not in table(capsys.readouterr().out)[0][4:5]


def test_a_superseded_decision_is_kept_marked_and_ranked_below_its_successor(w, capsys):
    """Equal in meaning, the superseded decision loses SUPERSEDED and so follows its successor. It
    is still shown, since a question may be about the history, and names the decision that replaced it."""
    w.entry("ADR-1", "Decision", "a ledger account")
    w.fact("ADR-1", "status", ki("Superseded"))
    w.fact("ADR-1", "supersededBy", node("proj", "ADR-2"))
    w.entry("ADR-2", "Decision", "a ledger account")
    w.vectorise()
    find(w, "a ledger account")
    out = capsys.readouterr().out
    rows = table(out)
    assert [r[1] for r in rows] == ["ADR-2", "ADR-1"]
    assert rows[1][4] == "~" and "Superseded by ADR-2." in under_row(out, "ADR-1")
    assert abs(float(rows[0][0]) - float(rows[1][0]) - ask.SUPERSEDED) < 0.011


def test_a_reversed_section_is_marked_and_names_the_addendum(w, capsys):
    """When the section that answered was reversed by an addendum, the row keeps its rank, is marked
    ~, and the line under it names the addendum's lines, so the reader lands on the live text."""
    w.entry("ADR-1", "Decision", "a ledger account")
    reversed_ = w.section("ADR-1", 1, "minting minting slow", "adr.md:10-12")
    addendum = w.section("ADR-1", 2, "graph graph", "adr.md:40-60")
    w.store.add(ox.Quad(reversed_, ki("supersededBy"), addendum, index_graph("proj")))
    w.vectorise()
    find(w, "minting slow")
    out = capsys.readouterr().out
    row = table(out)[0]
    assert row[1] == "ADR-1" and row[4] == "~" and row[-1] == "adr.md:10-12"
    line = under_row(out, "ADR-1")
    assert "Reversed by adr.md:40-60." in line and "The section that answered: minting minting slow" in line


def test_an_entry_and_a_decision_name_the_addendum_that_narrowed_them(w, capsys):
    """A principle whose Narrowed by names an addendum, and a decision whose first numbered decision,
    its claim, an addendum narrows, each print the addendum under the row, even where no section
    outranks the claim."""
    w.entry("ADR-1", "Decision", "one release for every module")
    first = w.section("ADR-1", 1, "one release for every module", "adr.md:10-12")
    addendum = w.section("ADR-1", 2, "graph graph", "adr.md:40-60")
    w.store.add(ox.Quad(first, ki("narrowedBy"), addendum, index_graph("proj")))
    w.entry("PRI-1", "Principle", "one release for every module")
    w.fact("PRI-1", "narrowedBy", addendum)
    w.vectorise()
    find(w, "one release for every module")
    out = capsys.readouterr().out
    assert "Narrowed by adr.md:40-60." in under_row(out, "PRI-1")
    assert "Narrowed by adr.md:40-60." in under_row(out, "ADR-1")
    assert {r[1]: r[4] for r in table(out)} == {"ADR-1": "~", "PRI-1": "~"}, "a narrowed row is marked as a reversed one is"


def test_a_decision_is_scored_by_its_best_section_and_points_at_it(w, capsys):
    """ADR-1's own claim says nothing about minting, but its second section does. It is found by that
    section, reports the section's pointer, and appears once, since a section is no entry. A question
    that its own claim answers keeps the whole-file pointer."""
    w.entry("ADR-1", "Decision", "a ledger account")
    w.entry("CAP-1", "Capability", "minting in Java")
    w.fact("ADR-1", "pointer", "adr.md:1-90")
    w.section("ADR-1", 1, "a ledger account", "adr.md:10-20")
    w.section("ADR-1", 2, "minting minting slow", "adr.md:30-40")
    assert w.vectorise() == 4, "the sections are embedded beside the entries"
    assert len(embed.load(w.ask.directory, w.config.embedding)[0]) == 4
    assert {r["id"] for r in ask.candidates(w.ask, set(), set(), set())} == {"ADR-1", "CAP-1"}
    find(w, "minting slow")
    rows = table(capsys.readouterr().out)[:2]
    assert [r[1] for r in rows] == ["ADR-1", "CAP-1"] and rows[0][-1] == "adr.md:30-40"
    find(w, "a ledger account")
    assert table(capsys.readouterr().out)[0][-1] == "adr.md:1-90"


def test_declared_terms_are_searched_only_when_their_kind_is_named(w, capsys):
    """Terms crowded the entries out of questions about a design, so a question without --kind term
    never sees one. Named alone, the kind finds only terms, named with another it ranks both, and a
    phase or audience filter hides terms, which state neither."""
    w.entry("MEC-1", "Mechanism", "a ledger account", phase="Runtime")
    t = term("proj", "https://example.org/ledger#keyDimension")
    w.store.extend([
        ox.Quad(t, ki("identifier"), ox.Literal("https://example.org/ledger#keyDimension"), terms_graph("proj")),
        ox.Quad(t, ki("claim"), ox.Literal("key dimension. ledger ledger per key. functional"), terms_graph("proj")),
        ox.Quad(t, ki("pointer"), ox.Literal("ledger.ttl:9"), terms_graph("proj")),
        ox.Quad(t, ki("declaredAs"), ox.Literal("Class"), terms_graph("proj")),
        ox.Quad(t, ki("ownedBy"), ox.NamedNode(f"{KI}module/proj/ledger"), terms_graph("proj")),
    ])
    assert w.vectorise() == 2, "the term is embedded beside the entry"
    find(w, "ledger")
    out = capsys.readouterr().out
    assert [r[1] for r in table(out)] == ["MEC-1"] and "module" not in out.splitlines()[0]
    find(w, "ledger", {"Term"})
    out = capsys.readouterr().out
    assert out.splitlines()[0].split()[:5] == ["score", "id", "kind", "module", "flags"], "a term has a module and no status"
    assert [r[1:4] for r in table(out)] == [["keyDimension", "Term", "ledger"]]
    find(w, "ledger", {"Term", "Mechanism"})
    assert sorted(r[1] for r in table(capsys.readouterr().out)) == ["MEC-1", "keyDimension"]
    find(w, "ledger", {"Term", "Mechanism"}, {"Runtime"})
    assert [r[1] for r in table(capsys.readouterr().out)] == ["MEC-1"]
    ask.lookup(w.ask, "exists", "KEYDIM")
    assert [r[:3] for r in table(capsys.readouterr().out)] == [["term", "proj", "keyDimension"]]


def test_the_case_an_entry_does_not_cover_is_embedded_with_it(w):
    """So a question about the uncovered case still finds the entry, which is then flagged."""
    w.entry("MEC-1", "Mechanism", "One account per key.")
    w.fact("MEC-1", "doesNotCover", "a keyed child under a keyed parent")
    (text,) = [r["uncovered"].value for r in w.store.query(builder.TEXTS)]
    assert text == "a keyed child under a keyed parent"


# ---- Read ----------------------------------------------------------------------------------------


@pytest.fixture
def neighbourhood(w):
    code = w.tmp / "code"
    code.mkdir()
    w.entry("STD-1", "Standard", "a period's amount is never restored")
    w.fact("STD-1", "problemShape", "restoring an amount drawn in a period")
    w.fact("STD-1", "doesNotCover", "the reinstatement credit")
    w.fact("STD-1", "distinguishedFrom", node("proj", "MEC-2"))
    w.entry("MEC-2", "Mechanism", "a reinstatement restores within a period")
    w.entry("TD-3", "Debt", "the range disagrees with the shape")
    w.fact("TD-3", "bearsOn", node("proj", "STD-1"))
    (code / "short.md").write_text("\n".join(f"line {n}" for n in range(1, 11)), encoding="utf-8")
    (code / "register.md").write_text("\n".join(f"row {n}" for n in range(1, ask.WHOLE_FILE + 50)), encoding="utf-8")
    w.fact("STD-1", "pointer", "short.md:2-3")
    w.fact("MEC-2", "pointer", f"register.md:1-{ask.WHOLE_FILE + 49}")
    return w


def test_read_prints_the_fields_and_every_neighbour_before_the_text(neighbourhood, capsys):
    """read STD-1 gives what find does not show and each entry linked to it, in either direction:
    the entry it is distinguished from and the debt that bears on it, with their claims."""
    ask.read(neighbourhood.ask, "STD-1")
    out = capsys.readouterr().out
    assert "Problem shape: restoring an amount drawn in a period" in out
    assert "Does not cover: the reinstatement credit" in out
    assert "distinguished from MEC-2 (Mechanism): a reinstatement restores within a period" in out
    assert "TD-3 bears on this (Debt): the range disagrees with the shape" in out
    assert out.index("Linked:") < out.index("== short.md:2-3") and "line 2\nline 3" in out


def test_a_symmetric_neighbour_is_shown_from_either_end(neighbourhood, capsys):
    ask.read(neighbourhood.ask, "MEC-2")
    assert "STD-1 distinguished from this (Standard)" in capsys.readouterr().out


def test_read_refuses_a_pointer_to_a_whole_long_file(neighbourhood, capsys):
    """A pointer naming all of a long register hands the reader every row of it. read says so and
    prints none of it, and the entry's own fields stand in."""
    ask.read(neighbourhood.ask, "MEC-2")
    out = capsys.readouterr().out
    assert "pointer defect" in out and "row 1\n" not in out
    assert ask.whole_file(neighbourhood.tmp / "code", "short.md:1-10") is None


def test_read_prints_an_entry_with_a_register_row_and_a_pointer(neighbourhood, capsys):
    """An entry with its defining register row and a pointer, as every register entry has, prints
    both under their labels, rather than reading the label as a path."""
    (neighbourhood.tmp / "code" / "reg.md").write_text("| MEC-1 | a row |", encoding="utf-8")
    neighbourhood.entry("MEC-1", "Mechanism", "a mechanism")
    neighbourhood.fact("MEC-1", "row", "reg.md:1-1")
    neighbourhood.fact("MEC-1", "pointer", "short.md:2-3")
    ask.read(neighbourhood.ask, "MEC-1")
    out = capsys.readouterr().out
    assert "== row reg.md:1-1\n| MEC-1 | a row |" in out
    assert "== pointed-at short.md:2-3\nline 2\nline 3" in out


def test_a_domain_entry_is_read_from_the_domains_own_path(w, capsys):
    """A pointer is written relative to the root of the scope that owns the entry."""
    domain = w.config.domains["tools"]
    domain.path.mkdir(parents=True)
    (domain.path / "notes.md").write_text("one\ntwo\nthree\n", encoding="utf-8")
    w.entry("NOTE-1", "Standard", "a note", scope="tools")
    w.fact("NOTE-1", "pointer", "notes.md:2-3", scope="tools")
    ask.read(w.ask, "tools:NOTE-1")
    out = capsys.readouterr().out
    assert out.startswith("tools:NOTE-1  Standard") and "== notes.md:2-3\ntwo\nthree" in out


def test_node_and_reaches_name_the_edges_the_authors_declared(w, capsys):
    w.entry("STD-1", "Standard", "a period's amount is never restored")
    w.entry("MEC-2", "Mechanism", "a reinstatement restores within a period")
    w.fact("STD-1", "relatedTo", node("proj", "MEC-2"))
    ask.lookup(w.ask, "node", "STD-1")
    assert table(capsys.readouterr().out)[0][:3] == ["STD-1", "Standard", ""]
    ask.lookup(w.ask, "reaches", "MEC-2")
    assert table(capsys.readouterr().out)[0][:3] == ["in", "STD-1", "Standard"]
    ask.lookup(w.ask, "node", "STD-77")
    assert "nothing found for: node STD-77" in capsys.readouterr().out
    ask.lookup(w.ask, "sparql", "SELECT ?id WHERE { GRAPH ?g { ?n <%sidentifier> ?id } }" % KI)
    assert "2 row(s)" in capsys.readouterr().out


# ---- The logs ------------------------------------------------------------------------------------


def test_every_find_and_read_is_logged_with_its_best_score(w, capsys):
    w.entry("MEC-1", "Mechanism", "a ledger account")
    w.vectorise()
    find(w, "ledger")
    logged = ask.asks(w.ask)
    assert [(r["verb"], r["ids"], r["text"]) for r in logged] == [("find", "MEC-1", "ledger")]
    assert float(logged[0]["best"]) > 0.9


def test_a_gap_is_recorded_with_its_entry_and_line(w, capsys):
    """An agent records what reading found at the moment it finds it, with the entry it qualifies and
    the line it was read from, so the handoff report is a query rather than a memory."""
    ask.gap(w.ask, "LG-Q7 covers an unkeyed parent only", ["STD-280", "docs/developer/plans/ledger.md:416"])
    capsys.readouterr()
    (recorded,) = ask.asks(w.ask)
    assert recorded["verb"] == "gap" and recorded["ids"] == "STD-280"
    assert recorded["text"] == "LG-Q7 covers an unkeyed parent only @ docs/developer/plans/ledger.md:416"
    ask.misses(w.ask, 20)
    out = capsys.readouterr().out
    assert "gaps recorded by reading" in out and "LG-Q7 covers an unkeyed parent only" in out


def test_misses_near_lists_the_confident_and_incomplete(w, capsys):
    """A question answered at 0.71 leaves no miss, and is where a confident wrong answer lives."""
    ask.log_ask(w.ask, "find", "a child account finds its parent", 0.71, ["PAT-41"])
    ask.log_ask(w.ask, "find", "a ledger account", 0.86, ["MEC-1"])
    ask.log_ask(w.ask, "find", "nothing like it", 0.60, [])
    ask.misses(w.ask, 20, near=True)
    out = capsys.readouterr().out.split("near answers", 1)[1]
    assert "a child account finds its parent" in out and "PAT-41" in out
    assert "a ledger account" not in out and "nothing like it" not in out


def test_misses_lists_each_question_once_newest_first(w, capsys):
    """The miss log is read at a handoff to decide what the index lacks, so a question asked three
    times is one row with its count, and the newest gap comes first."""
    w.ask.directory.mkdir(parents=True)
    w.ask.miss_log.write_text("2026-10-24T09:00:00+00:00\tfind a\n2026-10-26T09:00:00+00:00\tfind b\n"
                              "2026-10-25T09:00:00+00:00\tfind a\n2026-10-25T10:00:00+00:00\tfind a\n", encoding="utf-8")
    ask.misses(w.ask, 20)
    lines = capsys.readouterr().out.splitlines()
    assert lines[2].split() == ["2026-10-26", "1", "find", "b"]
    assert lines[3].split() == ["2026-10-25", "3", "find", "a"]
    assert "2 distinct question(s)" in lines[-1]


def test_closing_a_gap_removes_its_lines_and_the_question_behind_it(w, capsys):
    """Pruning happens when a gap is closed: the gap goes, with the miss and the near answers of the
    question asked just before it, and nothing else."""
    ask.log_ask(w.ask, "find", "a child account finds its parent", 0.71, ["PAT-41"])
    ask.log_miss(w.ask, "find a child account finds its parent")
    ask.gap(w.ask, "LG-Q7 covers an unkeyed parent only", ["STD-280"])
    ask.log_ask(w.ask, "find", "something else", 0.70, ["MEC-1"])
    ask.gap(w.ask, "another entry's gap", ["MEC-9"])
    assert next(r for r in ask.asks(w.ask) if r["ids"] == "STD-280")["asked"] == "a child account finds its parent"
    ask.close(w.ask, ["STD-280"])
    assert [r["text"] for r in ask.asks(w.ask)] == ["something else", "another entry's gap"]
    assert not w.ask.miss_log.read_text(encoding="utf-8").strip()
    assert "closed 1 gap(s) on STD-280" in capsys.readouterr().out


def test_misses_removes_a_question_the_index_now_answers(w, capsys):
    """A logged question asked again that now scores at the near score or above was closed by an entry
    written since, so its lines go. One still weak stays."""
    w.entry("MEC-1", "Mechanism", "a ledger account")
    w.vectorise()
    ask.log_miss(w.ask, "find ledger")
    ask.log_ask(w.ask, "find", "ledger", 0.60, [])
    ask.log_ask(w.ask, "find", "graph", 0.60, [])
    ask.log_miss(w.ask, "find graph")
    ask.misses(w.ask, 20, again=True)
    assert "1 question(s) the index now answers" in capsys.readouterr().out
    assert [r["text"] for r in ask.asks(w.ask)] == ["graph"]
    assert w.ask.miss_log.read_text(encoding="utf-8").count("find ") == 1


# ---- Scopes --------------------------------------------------------------------------------------


def test_an_entry_of_another_scope_is_shown_qualified(w, capsys):
    """The project's own entries are bare and a domain's, or the general scope's, carry their scope,
    in the table, under a linked row and in what read prints. A bare identifier means the home scope."""
    w.entry("STD-1", "Standard", "ledger one")
    w.entry("NOTE-1", "Standard", "ledger two", scope="tools")
    w.entry("GEN-1", "Principle", "ledger three", scope="general")
    w.fact("STD-1", "supports", node("tools", "NOTE-1"))
    w.vectorise()
    find(w, "ledger")
    out = capsys.readouterr().out
    assert sorted(r[1] for r in table(out)) == ["STD-1", "general:GEN-1", "tools:NOTE-1"]
    assert all(r["scope"] in ("proj", "tools", "general") for r in ask.candidates(w.ask, set(), set(), set()))
    ask.lookup(w.ask, "reaches", "NOTE-1")
    assert "nothing found" in capsys.readouterr().out, "a bare identifier is the home scope's, which has no NOTE family"
    w.fact("STD-1", "relatedTo", node("tools", "NOTE-1"))
    ask.lookup(w.ask, "reaches", "STD-1")
    assert table(capsys.readouterr().out)[0][:2] == ["out", "tools:NOTE-1"]
    ask.lookup(w.ask, "node", "tools:NOTE-1")
    assert table(capsys.readouterr().out)[0][:2] == ["tools:NOTE-1", "Standard"]


def test_a_question_in_one_project_never_returns_another_projects_entries(tmp_path, capsys):
    """Both projects hold an STD-1 and a ledger entry in one store. Each is asked from its own folder
    and sees its own, never the rival's, through find, read, node, reaches, exists and sparql."""
    (tmp_path / "code").mkdir()
    (tmp_path / "rival").mkdir()
    a = World(tmp_path, "proj")
    b = World(tmp_path, "rival")
    b.store = a.store
    b.ask.db = a.store
    a.entry("STD-1", "Standard", "ledger of the first project")
    a.entry("MEC-5", "Mechanism", "ledger secret", scope="rival")
    a.entry("STD-1", "Standard", "ledger of the rival", scope="rival")
    a.vectorise()
    (tmp_path / "code" / "a.md").write_text("first\n", encoding="utf-8")
    (tmp_path / "rival" / "a.md").write_text("rival\n", encoding="utf-8")
    a.fact("STD-1", "pointer", "a.md:1-1")
    a.fact("STD-1", "pointer", "a.md:1-1", scope="rival")
    find(a, "ledger")
    mine = capsys.readouterr().out
    assert "first project" in mine and "rival" not in mine and "MEC-5" not in mine
    find(b, "ledger")
    theirs = capsys.readouterr().out
    assert "of the rival" in theirs and "first project" not in theirs
    ask.read(a.ask, "STD-1")
    assert "first" in capsys.readouterr().out
    ask.read(a.ask, "rival:STD-1")
    assert "nothing to read for: rival:STD-1" in capsys.readouterr().out
    ask.lookup(a.ask, "node", "rival:MEC-5")
    assert "nothing found" in capsys.readouterr().out
    ask.lookup(a.ask, "sparql", "SELECT ?id WHERE { GRAPH ?g { ?n <%sclaim> ?id } }" % KI)
    assert "rival" not in capsys.readouterr().out
    ask.lookup(a.ask, "exists", "secret")
    assert "MEC-5" not in capsys.readouterr().out


# ---- Staleness -----------------------------------------------------------------------------------


@pytest.fixture
def built(tmp_path):
    """A real project with a register, built into the store directory."""
    code = tmp_path / "code"
    (code / "docs").mkdir(parents=True)
    (code / "docs" / "standards.md").write_text(
        "| ID | Claim | Pointer |\n|---|---|---|\n| STD-1 | A ledger is kept per key. | docs/standards.md |\n", encoding="utf-8")
    w = World(tmp_path)
    builder.build(w.config, w.project, model=Words())
    return w


def test_a_built_index_is_stale_only_when_a_file_the_stack_reads_is_newer(built):
    a = ask.open_stack(built.config, built.tmp / "code", model=Words())
    assert not ask.stale(a)
    register = built.tmp / "code" / "docs" / "standards.md"
    stamp = float((a.directory / "built-from").read_text(encoding="utf-8"))
    os.utime(register, (stamp + 100, stamp + 100))
    assert ask.stale(a)
    (a.directory / "built-for").write_text("rival\n", encoding="utf-8")
    os.utime(register, (stamp - 100, stamp - 100))
    assert ask.stale(a), "an index built for another stack is stale for this one"


def test_a_stale_index_is_rebuilt_before_it_answers(built, capsys):
    register = built.tmp / "code" / "docs" / "standards.md"
    register.write_text(register.read_text(encoding="utf-8").replace("per key", "per period"), encoding="utf-8")
    stamp = float((built.ask.directory / "built-from").read_text(encoding="utf-8"))
    os.utime(register, (stamp + 100, stamp + 100))
    a = ask.open_stack(built.config, built.tmp / "code", model=Words())
    assert "building it" in capsys.readouterr().err
    assert ask.find(a, "ledger period", set(), set(), set(), 8) == 0
    assert "per period" in capsys.readouterr().out
