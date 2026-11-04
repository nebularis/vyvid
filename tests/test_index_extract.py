# SPDX-License-Identifier: MIT
# Ported from LATTICE's tools/knowledge/test_extract.py, relicensed MIT by its author, over fixtures.
"""VYD-2, fourth step: identifiers in a cell, family rules, the extractors and the build."""

from __future__ import annotations

import datetime as dt

import pyoxigraph as ox
import pytest

from test_index_core import Words
from vyvid import build as builder
from vyvid import embed, extract, extractors, facets, registers
from vyvid.extractors import owl
from vyvid.config import ConfigError, load
from vyvid.model import KI, index_graph, ki, node, normalise, term
from vyvid.patterns import Pattern
from vyvid.resolve import layers, mentions

CONFIG = """
[framework]
kb = "CODE/kb"

[[domains]]
name = "tools"
families = { NOTE = {} }

[[projects]]
name = "proj"
code = "CODE"
docs = "code:docs"
domains = ["tools"]

[projects.families]
STD = { defined = "docs:developer/standards.md", type = "standard" }
MEC = { defined = "docs:developer/mechanisms.md", type = "mechanism" }
ADR = { pattern = 'ADR-A\\d+[a-z]?', rule = "file", type = "decision", defined = "docs:architecture/decisions/*.md" }
TSD = { pattern = 'TSD-\\d+[a-z]?', rule = "heading", type = "discovery", defined = "docs:architecture/store.md" }
LGQ = { pattern = '[A-Z]{1,4}\\d*[a-z]?-Q\\d+', rule = "question", type = "question", defined = ["docs:developer/plans/*.md", "docs:developer/sketches/*.md"] }

[[projects.extractors]]
kind = "owl-terms"
paths = ["code:ontology/**/*.ttl"]
"""

LEDGER_PREFIXES = {"ldg": "https://example.org/ledger#"}

SPEC = embed.ModelSpec()


def write(root, name, text):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text if isinstance(text, str) else "\n".join(text), encoding="utf-8")
    return path


@pytest.fixture
def world(tmp_path):
    config_file = write(tmp_path, "config.toml", CONFIG.replace("CODE", (tmp_path / "code").as_posix()))
    config = load(config_file)
    project = config.projects["proj"]
    stack = layers(config, project)
    _, values = facets.merge([("default", facets.default_register())])
    ctx = extract.Context(config, project, extract.Extract(), registers.types_for(stack), facets.taggable(values),
                          extract.technology_words(values))
    return ctx


def facts(ctx, subject):
    return {(q.predicate.value.removeprefix(KI), q.object.value.removeprefix(KI)) for q in ctx.out.quads if q.subject == subject}


# ---- Mentions, rules and globs -------------------------------------------------------------------


def test_every_identifier_in_a_cell_is_found_once_in_order(world):
    config, scope = world.config, world.scope
    text = "after STD-3, then MEC-2 and STD-3 again, tools:NOTE-1, proj:MEC-9, STD-3xy, NOTE-4 and ADR-A1"
    assert mentions(config, text, scope) == ["proj:STD-3", "proj:MEC-2", "tools:NOTE-1", "proj:MEC-9", "proj:ADR-A1"], \
        "a family the scope lacks and a run into a longer word are skipped, never raised"
    assert mentions(config, "see proj:STD-4", config.general) == ["proj:STD-4"], "a qualified mention names its own scope"
    assert mentions(config, "proj:STD-4", scope) == ["proj:STD-4"], "a qualified mention is not read again as a bare one"


def test_a_domains_family_is_a_qualified_mention_and_a_delegated_one_is_bare(world):
    config, scope = world.config, world.scope
    assert mentions(config, "tools:NOTE-7", scope) == ["tools:NOTE-7"]
    assert mentions(config, "NOTE-7", scope) == []
    scope.delegates["NOTE"] = "tools"
    assert mentions(config, "NOTE-7", scope) == ["tools:NOTE-7"]


def test_two_spellings_of_one_identifier_count_once_under_the_first(world):
    assert mentions(world.config, "ADR-A1 and ADR-A1", world.scope) == ["proj:ADR-A1"]
    assert normalise("ADR-A-C2") == normalise("ADR AC2") == "ADRAC2" and normalise("AIR-6.6") != normalise("AIR-66")


def test_an_unknown_family_rule_is_refused(tmp_path):
    config = write(tmp_path, "c.toml", '[[projects]]\nname = "p"\ncode = "x"\n[projects.families]\nA = { rule = "scan" }\n')
    with pytest.raises(ConfigError, match="the rule 'scan'"):
        load(config)


def test_a_definition_is_a_file_a_folder_or_a_glob_and_lists_come_in_order(world, tmp_path):
    code = tmp_path / "code"
    for name in ("b", "a"):
        write(code, f"docs/developer/plans/{name}.md", "x")
    write(code, "docs/developer/sketches/s.md", "x")
    write(code, "docs/architecture/decisions/ADR-A1-x.md", "x")
    write(code, "docs/developer/standards.md", "x")
    families = world.scope.families
    assert [p.name for p in families["LGQ"].paths()] == ["a.md", "b.md", "s.md"], "a plan's before a sketch's, each sorted"
    assert [p.name for p in families["ADR"].paths()] == ["ADR-A1-x.md"]
    assert [p.name for p in families["STD"].paths()] == ["standards.md"]
    assert families["MEC"].paths() == []


# ---- Decisions -----------------------------------------------------------------------------------


def test_a_decision_is_claimed_by_what_it_decides_not_its_title():
    """A title such as "Provenance Model" says too little for a question phrased as the problem, so
    the claim is the Decision section's own words. A bold lead that is a whole sentence stands alone,
    a lead-in such as "Rules:" does not, a table's rows are read without its header, and code is not
    read at all."""
    lead = ["# ADR-A1: X", "## Decision", "", "**1. We keep one release number for the substrate layers.** More text."]
    assert extract.decision_claim(lead) == "1. We keep one release number for the substrate layers."
    table = ["## Decision", "", "```", "Principal { subject }", "```", "**Rules:**", "",
             "| Tier | Contract |", "|---|---|", "| **Core** | Every adapter implements it. |", "## Consequences", "later"]
    claim = extract.decision_claim(table)
    assert claim.startswith("Rules: Core, Every adapter implements it.")
    assert "Tier" not in claim and "Principal" not in claim and "later" not in claim
    assert extract.decision_claim(["# ADR-A1: X", "## Context", "text"]) is None


SECTIONED = [
    "# ADR-A998: Sectioned", "", "**Status:** Accepted", "", "## Context", "1. not a decision", "",
    "## Decision", "", "Preamble.", "",
    "1. **A shape is a tree.** First rule.", "   continued.", "",
    "```", "2. inside a fence", "```", "",
    "2. **An IRI is injective in its root.** Second rule.", "",
    "## Consequences", "", "1. not a decision either", "",
    "## Addendum, 2026-10-12: who names a graph", "", "**Status:** Accepted", "", "The caller does.", "",
    "### Detail", "kept in the addendum", "",
    "## Provenance", "text",
]


def test_each_numbered_decision_and_addendum_is_a_section_with_its_own_range():
    found = extract.decision_sections(SECTIONED)
    assert [(s, e) for _, s, e in found] == [(12, 17), (19, 19), (25, 33)]
    assert found[0][0] == "A shape is a tree. First rule. continued."  # the fenced line is range, not text
    assert found[1][0].startswith("An IRI is injective in its root.")
    assert found[2][0].startswith("who names a graph The caller does. kept in the addendum")
    assert "Accepted" not in found[2][0] and "inside a fence" not in found[0][0]
    assert extract.decision_sections(["# ADR-A1: X", "## Context", "1. text"]) == []


def test_a_decision_carries_its_title_claim_status_and_pointer(world, tmp_path):
    write(tmp_path / "code", "docs/architecture/decisions/ADR-A998-sectioned.md", SECTIONED)
    extract.decisions(world)
    subject = node("proj", "ADR-A998")
    found = facts(world, subject)
    assert ("status", "Accepted") in found and ("identifier", "ADR-A998") in found
    assert any(p == "pointer" and o.startswith("docs/architecture/decisions/ADR-A998-sectioned.md:1-") for p, o in found)
    assert ("claim", "A shape is a tree. First rule.") not in found and any(p == "claim" for p, _ in found)
    assert any(q.predicate == extract.RDFS_LABEL and q.object.value == "Sectioned" for q in world.out.quads)
    assert not world.out.problems


def test_a_section_is_an_auxiliary_node_and_never_an_entry(world, tmp_path):
    """A section node carries a claim, a pointer and its parent. It has no identifier and no type,
    so a query for entries never returns it as a row of its own."""
    write(tmp_path / "code", "docs/architecture/decisions/ADR-A998-sectioned.md", SECTIONED)
    extract.decisions(world)
    out = world.out
    parent = node("proj", "ADR-A998")
    sections = [q.subject for q in out.quads if q.predicate == ki("sectionOf") and q.object == parent]
    assert len(sections) == out.counts["decision-section"] == 3
    for section in sections:
        assert {q.predicate.value.rsplit("#", 1)[-1] for q in out.quads if q.subject == section} == {"sectionOf", "claim", "pointer"}
    assert {q.object.value for q in out.quads if q.predicate == ki("pointer") and q.subject in sections} == {
        "docs/architecture/decisions/ADR-A998-sectioned.md:" + r for r in ("12-17", "19-19", "25-33")
    }
    entries = {q.subject for q in out.quads if q.predicate == ki("identifier")}
    assert entries == {parent} and not entries & set(sections)


def test_a_decision_with_no_readable_status_is_reported_not_guessed(world, tmp_path):
    write(tmp_path / "code", "docs/architecture/decisions/ADR-A999-fixture.md", "# ADR-A999: A fixture\n\n## Status\n\nAccepted\n")
    extract.decisions(world)
    assert world.out.counts.get("decision-without-status") == 1
    assert sum("no **Status:** header field" in p for p in world.out.problems) == 1


def test_a_published_decision_keeps_the_state_its_line_gives_and_a_later_status_line_is_ignored(world, tmp_path):
    write(tmp_path / "code", "docs/architecture/decisions/ADR-A5-x.md",
          "# ADR-A5. X\n\n**Status:** Published, 2026-10-01. Accepted, with a tail.\n\n## Decision\n\n1. **A rule.** Text.\n\n"
          "## Addendum, 2026-10-12: later\n\n**Status:** Proposed\n")
    extract.decisions(world)
    found = facts(world, node("proj", "ADR-A5"))
    assert ("status", "Accepted") in found and ("status", "Proposed") not in found and ("publishedOn", "2026-10-01") in found


SUPERSEDING = [
    "# ADR-A997: Superseding", "", "**Status:** Accepted", "", "## Decision", "",
    "**1. A first rule.** Text.", "", "**2. A second rule.** Text.", "", "**3. A third rule.** Text.", "",
    "## Addendum, 2026-10-12: later", "", "**Reverses decision 2. ** not a lead", "",
    "**Reverses decision 2.** **Narrows decisions 1 and 3.** The second no longer holds.", "",
    "**4. A fourth rule.** Text.", "",
    "## Addendum, 2026-10-13: later still", "", "**Narrows decision 4.** **Reverses decision 9.** Text.", "",
    "Quoted, `**Reverses decision 1.**` is an example and no lead.", "",
    "## Provenance", "text",
]


def test_an_addendum_lead_supersedes_or_narrows_numbered_decisions(world, tmp_path):
    """A bold-paragraph decision is a section too. A lead reverses or narrows the Decision section's
    item of that number, or else the one addendum that numbers it, and a number naming nothing is
    reported rather than guessed."""
    write(tmp_path / "code", "docs/architecture/decisions/ADR-A997-superseding.md", SUPERSEDING)
    extract.decisions(world)
    base = node("proj", "ADR-A997").value
    edges = {(q.subject.value.removeprefix(base), q.predicate.value.rsplit("#", 1)[-1], q.object.value.removeprefix(base))
             for q in world.out.quads if q.predicate.value.endswith(("#supersededBy", "#narrowedBy"))}
    assert edges == {
        ("/section-2", "supersededBy", "/section-4"), ("/section-1", "narrowedBy", "/section-4"),
        ("/section-3", "narrowedBy", "/section-4"), ("/section-4", "narrowedBy", "/section-5"),
    }, "decision 4 is numbered only in the first addendum, so that addendum is its section"
    assert [p for p in world.out.problems if "Reverses decision 9" in p], world.out.problems


def test_a_superseded_decision_names_its_successor_and_related_names_only_defined_decisions(world, tmp_path):
    decisions = tmp_path / "code/docs/architecture/decisions"
    write(decisions, "ADR-A1-old.md", "# ADR-A1: Old\n\n**Status:** Superseded by ADR-A2\n**Related:** ADR-A2, ADR-A77, ADR-A1\n")
    write(decisions, "ADR-A2-new.md", "# ADR-A2: New\n\n**Status:** Accepted\n")
    write(decisions, "ADR-A3-orphan.md", "# ADR-A3: Orphan\n\n**Status:** Superseded\n")
    extract.decisions(world)
    old = facts(world, node("proj", "ADR-A1"))
    assert ("supersededBy", "node/proj/ADRA2") in old and ("relatedTo", "node/proj/ADRA2") in old
    assert ("relatedTo", "node/proj/ADRA77") not in old and ("relatedTo", "node/proj/ADRA1") not in old
    assert any("ADR-A3 is Superseded and its Status line names no successor" in p for p in world.out.problems)


# ---- Registers -----------------------------------------------------------------------------------


def rows(ctx, tmp_path, header, *lines, name="mechanisms"):
    table = f"{header}\n|{'---|' * (header.count('|') - 1)}\n" + "\n".join(lines) + "\n"
    write(tmp_path / "code", f"docs/developer/{name}.md", table)
    extract.register_rows(ctx)


def test_the_signpost_columns_are_read_and_checked(world, tmp_path):
    """Does not cover is text, Distinguished from names entries, and Bears on names entries and
    declared terms by the CURIE their layer writes."""
    world.prefixes = LEDGER_PREFIXES  # what an extractor found
    rows(world, tmp_path, "| ID | Claim | Does not cover | Distinguished from | Bears on |",
         f"| MEC-1 | **A claim.** | {'x' * 121} | MEC-2 | STD-3, ldg:keyDimension, zz:nothing, proj:STD-4 |")
    found = facts(world, node("proj", "MEC-1"))
    assert ("distinguishedFrom", "node/proj/MEC2") in found and ("bearsOn", "node/proj/STD3") in found
    assert ("bearsOn", "node/proj/STD4") in found
    assert ("bearsOn", "term/proj/ledger.keyDimension") in found
    assert any("Does not cover of 121 characters" in p for p in world.out.problems)
    assert any("'zz:nothing', whose prefix no ontology document declares" in p for p in world.out.problems)
    assert not any("proj:STD" in p for p in world.out.problems), "a qualified identifier is not a CURIE"


def test_a_row_becomes_a_typed_node_with_its_facets_and_edges(world, tmp_path):
    rows(world, tmp_path, "| ID | Name | Claim | Audience | Technology | Waits for | Ratified | Owner |",
         "| MEC-1 | a mechanism | **The claim.** More. | published | java | MEC-2, MEC-1, NOTE-9 | no | tools, core |")
    found = facts(world, node("proj", "MEC-1"))
    assert ("http://www.w3.org/1999/02/22-rdf-syntax-ns#type", "Mechanism") in found
    assert ("claim", "The claim.") in found and ("audience", "PublishedUse") in found and ("status", "Proposed") in found
    assert {q.object.value for q in world.out.quads if q.predicate == ki("technology")} == {facets.NS + "java"}
    assert ("waitsOn", "node/proj/MEC2") in found, "a row never waits on itself, and a family the scope lacks is skipped"
    assert ("waitsOn", "node/proj/MEC1") not in found
    assert {("ownedBy", "tools"), ("ownedBy", "core")} <= found
    assert world.out.counts["Mechanism"] == 1 and world.out.counts["facet:Technology"] == 1


def test_a_narrowed_by_cell_points_an_entry_at_the_addendum_by_its_day(world, tmp_path):
    """A principle restated a decision after its addendum had narrowed it, and no signpost said so. A
    Narrowed by cell names the addendum by decision and day, which survive an edit, and resolves to
    that addendum's section, or is reported."""
    section = ox.NamedNode(KI + "node/proj/ADRA129/section-4")
    world.out.addenda[("proj", "ADRA129", "2026-10-26")] = section
    rows(world, tmp_path, "| ID | Claim | Narrowed by |",
         "| MEC-1 | **A claim.** | ADR-A129 addendum 2026-10-26 |", "| MEC-2 | **A claim.** | ADR-A129 addendum 2026-01-01 |",
         "| MEC-3 | **A claim.** | decision 1 |")
    assert ("narrowedBy", section.value) in {(q.predicate.value.removeprefix(KI), q.object.value) for q in world.out.quads
                                              if q.subject == node("proj", "MEC-1")}
    assert any("ADR-A129 has no addendum of that day" in p for p in world.out.problems)
    assert any("names no addendum" in p for p in world.out.problems)


# ---- Headings ------------------------------------------------------------------------------------

STORE_RECORD = [
    "# Store record", "", "**Stores covered:** rdflib and Oxigraph", "",
    "## TSD-23. Validation on a large graph is slow", "", "**Evidence:** pySHACL 0.30 took 9 s.", "**Bears on:** STD-3, ldg:Account", "",
    "## TSD-07. An update runs in order", "", "**Evidence:** both stores agree.", "",
    "## Not a finding", "text",
]


def test_a_store_finding_takes_its_technology_from_its_evidence(world, tmp_path):
    """TSD-23's Evidence line names pySHACL, so it carries pySHACL without anyone authoring it.
    TSD-07's says "both stores", which the record's Stores covered line names as rdflib and Oxigraph."""
    write(tmp_path / "code", "docs/architecture/store.md", STORE_RECORD)
    world.prefixes = LEDGER_PREFIXES
    extract.discoveries(world)
    technology = lambda ident: {q.object.value.rsplit("#", 1)[1] for q in world.out.quads
                                if q.subject == node("proj", ident) and q.predicate == ki("technology")}
    assert technology("TSD-23") == {"pyshacl"}
    assert technology("TSD-07") == {"rdflib", "oxigraph"}
    found = facts(world, node("proj", "TSD-23"))
    assert ("claim", "Validation on a large graph is slow") in found
    assert ("bearsOn", "node/proj/STD3") in found and ("bearsOn", "term/proj/ledger.Account") in found
    assert ("http://www.w3.org/1999/02/22-rdf-syntax-ns#type", "Discovery") in found
    assert world.out.counts["TSD"] == 2


# ---- Questions -----------------------------------------------------------------------------------

QUESTIONS = [
    "# A plan", "",
    "**LG-Q1. Which word names an account?** Account, since it has no market meaning.", "",
    "- **C6-Q1. Where term ownership is built.** The plan puts it in C8.", "  It is continued here.", "",
    "- **C3-Q1.** Wording ships a baseline scheme. Deployments add more.", "",
    "| ID | Question | Options | Answer |", "|---|---|---|---|",
    "| **LG-Q7** | Amounts per key | (a) derived. (b) authored | **Answered 2026-10-21, as leaned:** (a), now MEC-5. A child must name its key. |",
    "| LG-Q8 | A draw in another unit | (a) refused | leaning (a) |",
    "| PV-D3 | a decision point, not a question | x | y |",
]
ID = r"[A-Z]{1,4}\d*[a-z]?-Q\d+"


def test_a_question_is_read_from_its_lead_or_its_row():
    """Three lead forms and the table row plans use. A lead's paragraph runs to the next blank line,
    and a question is answered when its text says so, with the date that follows."""
    found = {q.identifier: q for q in extract.questions_in(QUESTIONS, Pattern(ID))}
    assert sorted(found) == ["C3-Q1", "C6-Q1", "LG-Q1", "LG-Q7", "LG-Q8"], "a decision point is not a question"
    assert found["LG-Q1"].question == "Which word names an account?" and found["LG-Q1"].answer.startswith("Account")
    assert (found["C6-Q1"].start, found["C6-Q1"].end) == (5, 6) and found["C6-Q1"].answer.endswith("continued here.")
    assert found["C3-Q1"].question == "Wording ships a baseline scheme." and found["C3-Q1"].answer == "Deployments add more."
    assert found["LG-Q7"].question == "Amounts per key" and found["LG-Q7"].answered and found["LG-Q7"].answered_on == "2026-10-21"
    assert not found["LG-Q8"].answered and found["LG-Q8"].answer == "leaning (a)"


def test_a_question_is_an_entry_and_a_promotion_answers_it(world, tmp_path):
    """A question node carries its kind, status, claim and pointer. 'now MEC-5' in its answer makes
    MEC-5 answer it, so the rule and the question that decided it reach each other."""
    write(tmp_path / "code", "docs/developer/plans/a.md", QUESTIONS)
    extract.questions(world, today=dt.date(2026, 10, 28))
    q7 = node("proj", "LG-Q7")
    found = facts(world, q7)
    assert ("status", "Answered") in found and ("pointer", "docs/developer/plans/a.md:12-12") in found
    claim = next(v for p, v in found if p == "claim")
    assert claim.startswith("Amounts per key Answered 2026-10-21") and "**" not in claim
    assert any(q.subject == node("proj", "MEC-5") and q.predicate == ki("answers") and q.object == q7 for q in world.out.quads)
    assert world.out.counts["question:open"] == 4 and world.out.counts["question:answered"] == 1


def test_a_question_defined_twice_keeps_the_plans_and_not_the_sketchs(world, tmp_path):
    write(tmp_path / "code", "docs/developer/plans/a.md", ["**LG-Q1. In the plan?** Yes."])
    write(tmp_path / "code", "docs/developer/sketches/s.md", ["**LG-Q1. In the sketch?** Yes."])
    extract.questions(world)
    assert [q.object.value for q in world.out.quads if q.predicate == ki("claim")] == ["In the plan? Yes."]
    assert world.out.counts["question-defined-again"] == 1


def test_an_unpromoted_rule_in_an_answer_is_reported_after_thirty_days(world, tmp_path):
    """Reported, never failed: a durable rule decided in a plan, with no entry to carry it."""
    write(tmp_path / "code", "docs/developer/plans/a.md",
          ["| ID | Q | A |", "|---|---|---|", "| LG-Q9 | Shared parent | Answered 2026-09-01: the parent must be unkeyed |"])
    extract.questions(world, today=dt.date(2026, 10, 28))
    assert any("LG-Q9" in f and "names no entry it was promoted to" in f for f in world.out.findings)
    assert not world.out.problems
    soon = extract.Context(world.config, world.scope, extract.Extract(), world.types, world.taggable)
    extract.questions(soon, today=dt.date(2026, 9, 20))
    assert not soon.out.findings


# ---- Dangling ------------------------------------------------------------------------------------


def test_a_signpost_to_nothing_is_reported(tmp_path):
    store = ox.Store(str(tmp_path / "s"))
    g = index_graph("proj")
    a = node("proj", "MEC-1")
    store.extend([
        ox.Quad(a, ki("identifier"), ox.Literal("MEC-1"), g),
        ox.Quad(a, ki("bearsOn"), node("proj", "MEC-404"), g),
        ox.Quad(a, ki("bearsOn"), term("proj", "https://x.org/l#gone"), g),
        ox.Quad(a, ki("distinguishedFrom"), a, g),
    ])
    out = extract.Extract()
    extract.dangling(store, out)
    assert sorted(out.problems) == ["MEC-1 has bearsOn MEC404, which names no entry or declared term",
                                    "MEC-1 has bearsOn term l.gone, which names no entry or declared term"]


# ---- Terms ---------------------------------------------------------------------------------------

LEDGER = """@prefix ldg: <https://example.org/ledger#> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

<https://example.org/ledger> a owl:Ontology .
ldg:Account a owl:Class ; rdfs:label "account" ; rdfs:comment "A keyed account." .
ldg:keyDimension a owl:DatatypeProperty , owl:FunctionalProperty ;
    rdfs:label "key dimension" ;
    rdfs:comment "The dimension that derives one account per key value." ;
    rdfs:domain ldg:Account ; rdfs:range xsd:string .
ldg:KeyShape a sh:NodeShape ; sh:property [ sh:path ldg:keyDimension ; sh:maxCount 1 ] .
ldg:first a ldg:Account ; rdfs:label "first account" .
"""
EXAMPLE = """@prefix ldg: <https://example.org/ledger#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
ldg:sample a ldg:Account ; rdfs:label "a sample" .
"""


def load_terms(world, tmp_path, extra=()):
    write(tmp_path / "code", "ontology/ledger/ledger.ttl", LEDGER)
    write(tmp_path / "code", "ontology/ledger/examples/sample.ttl", EXAMPLE)
    for name, text in extra:
        write(tmp_path / "code", name, text)
    store = ox.Store()
    context = extractors.Context(world.scope, tmp_path / "code", world.config, world.taggable, store)
    result = owl.extract(context, {"paths": [tmp_path / "code" / "ontology" / "**" / "*.ttl"]})
    store.bulk_extend(result.quads)
    world.out.problems += result.problems
    world.out.counts.update(result.counts)
    world.prefixes = result.prefixes
    return store


def term_rows(store, where=""):
    return list(store.query(f"""PREFIX ki: <{KI}> SELECT ?id ?claim ?kind ?owner ?pointer WHERE {{ GRAPH <{KI}terms/proj> {{
        ?t ki:identifier ?id ; ki:declaredAs ?kind ; ki:pointer ?pointer . OPTIONAL {{ ?t ki:claim ?claim }}
        OPTIONAL {{ ?t ki:ownedBy ?owner }} {where} }} }}"""))


def test_a_declared_term_carries_a_claim_from_its_own_document(world, tmp_path):
    store = load_terms(world, tmp_path)
    rows_ = {str(r["id"].value): r for r in term_rows(store)}
    key = rows_["https://example.org/ledger#keyDimension"]
    assert str(key["claim"].value) == ("key dimension. The dimension that derives one account per key value. "
                                       "functional, domain Account, range string, at most 1.")
    assert str(key["kind"].value) == "DatatypeProperty"
    assert str(key["pointer"].value) == "ontology/ledger/ledger.ttl:9"
    assert str(key["owner"].value) == KI + "module/proj/ontology/ledger"
    first = rows_["https://example.org/ledger#first"]
    assert "an individual of Account" in str(first["claim"].value)
    assert world.out.counts["ontology-document"] == 2


def test_example_data_declares_no_term(world, tmp_path):
    rows_ = {str(r["id"].value) for r in term_rows(load_terms(world, tmp_path))}
    assert "https://example.org/ledger#sample" not in rows_
    assert {"https://example.org/ledger#Account", "https://example.org/ledger#first"} <= rows_


def test_an_unparseable_document_is_reported_and_loses_only_itself(world, tmp_path):
    """A document holding an IRI with two fragment separators, which Oxigraph refuses. A single batch
    load would lose every document to it, so the parse is per document."""
    load_terms(world, tmp_path, [("ontology/bad.ttl", "<https://example.org/a#b#c> <https://example.org/p> <https://example.org/b> .\n")])
    assert world.out.counts["ontology-document"] == 2 and world.out.counts["ontology-document-failed"] == 1
    assert any("ontology/bad.ttl: does not parse" in p for p in world.out.problems)


# ---- The build -----------------------------------------------------------------------------------


def make_project(world, tmp_path):
    code = tmp_path / "code"
    write(code, "docs/developer/standards.md",
          "| ID | Claim | Technology | Bears on |\n|---|---|---|---|\n| STD-1 | **Write a test for every rule.** More. | java | ldg:keyDimension, STD-404 |\n")
    write(code, "docs/developer/mechanisms.md", "| ID | Claim |\n|---|---|\n| MEC-1 | **A mechanism.** |\n")
    write(code, "docs/architecture/decisions/ADR-A1-ledger.md",
          "# ADR-A1: Ledger\n\n**Status:** Accepted\n\n## Decision\n\n**1. A ledger keeps one account per key.** Text.\n")
    write(code, "docs/developer/plans/p.md", "**LG-Q1. Which word names an account?** Account, now STD-1.\n")
    write(code, "ontology/ledger/ledger.ttl", LEDGER)
    return world.config


def test_a_build_loads_the_index_and_embeds_its_text(world, tmp_path):
    config = make_project(world, tmp_path)
    store_path = tmp_path / "index" / "store"
    out = builder.build(config, config.projects["proj"], store_path, model=Words())
    assert out.counts["decision"] == 1 and out.counts["Standard"] == 1 and out.counts["Mechanism"] == 1 and out.counts["question:open"] == 1
    assert out.counts["term"] == 3 and out.counts["embedded"] > 0
    assert out.problems == ["STD-1 has bearsOn STD404, which names no entry or declared term"]
    store = builder.open_store(store_path)
    rows_ = list(store.query(f"""PREFIX ki: <{KI}> SELECT ?claim ?status WHERE {{ GRAPH <{KI}index/proj> {{
        ?n ki:identifier "ADR-A1" ; ki:claim ?claim ; ki:status ?status }} }}"""))
    assert [str(r["claim"].value) for r in rows_] == ["1. A ledger keeps one account per key."]
    assert str(rows_[0]["status"].value) == KI + "Accepted"
    answered = list(store.query(f"""PREFIX ki: <{KI}> SELECT ?q WHERE {{ GRAPH <{KI}index/proj> {{ ?s ki:answers ?q }} }}"""))
    assert len(answered) == 1
    assert bool(store.query(f"ASK {{ GRAPH <{KI}tbox> {{ <{KI}Decision> a <http://www.w3.org/2002/07/owl#Class> }} }}"))
    assert bool(store.query(f"ASK {{ GRAPH <{KI}facets> {{ <https://www.nebularis.org/vyvid/facets#java> a <http://www.w3.org/2004/02/skos/core#Concept> }} }}"))
    nodes, vectors = embed.load(tmp_path / "index", config.embedding)
    assert len(nodes) == vectors.shape[0] and node("proj", "ADR-A1").value in nodes
    assert any(n.endswith("/section-1") for n in nodes), "a decision's section is embedded as its own text"
    assert (tmp_path / "index" / "built-from").exists()


def test_the_store_stays_within_a_default_open_file_limit(world, tmp_path):
    """One bulk load per document left over a thousand SST files, which compaction did not merge, so
    a read-only open exceeded macOS's default limit of 256 open files."""
    config = make_project(world, tmp_path)
    for n in range(40):
        write(tmp_path / "code", f"ontology/m{n}/m.ttl", LEDGER.replace("ledger#", f"m{n}#").replace("example.org/ledger", f"example.org/m{n}"))
    builder.build(config, config.projects["proj"], tmp_path / "s" / "store", embed=False)
    assert len(list((tmp_path / "s" / "store").glob("*.sst"))) <= 32


def test_a_build_without_embedding_removes_stale_vectors_and_says_so(world, tmp_path):
    config = make_project(world, tmp_path)
    store_path = tmp_path / "index" / "store"
    builder.build(config, config.projects["proj"], store_path, model=Words())
    assert (tmp_path / "index" / embed.VECTORS).exists()
    out = builder.build(config, config.projects["proj"], store_path, embed=False)
    assert not (tmp_path / "index" / embed.VECTORS).exists()
    assert any(p.startswith("no embeddings") for p in out.problems) and out.counts["embeddings-unavailable"] == 1


def test_an_unavailable_model_is_a_problem_and_leaves_no_vectors(world, tmp_path, monkeypatch):
    config = make_project(world, tmp_path)

    def unavailable(spec):
        raise embed.Unavailable("no network")

    monkeypatch.setattr(embed, "Model", unavailable)
    out = builder.build(config, config.projects["proj"], tmp_path / "index" / "store")
    assert any("no network" in p for p in out.problems) and not (tmp_path / "index" / embed.VECTORS).exists()


def test_the_store_directory_is_configured_or_the_platforms(world, tmp_path):
    assert builder.store_dir(world.config).name == "index"
    world.config.store = tmp_path / "elsewhere"
    assert builder.store_dir(world.config) == tmp_path / "elsewhere"
