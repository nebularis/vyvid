# SPDX-License-Identifier: MIT
"""``units`` in the extractor contract: a module column names units an extractor declared."""

from __future__ import annotations

import pytest

from test_command_extractors import block, built, claims, problems, script
from test_identifiers import write
from vyvid import extractors
from vyvid.model import KI, node

STANDARDS = ("| ID | Claim | Owner |\n|---|---|---|\n"
             "| STD-1 | **One.** | `core` (the lot), tools |\n| STD-2 | **Two.** | ghost |\n")
FAMILIES = '\n[projects.families]\nSTD = { defined = "docs:standards.md", type = "standard" }\n'
UNITS = "finish(units={'core': ['mod-a', 'mod-b'], 'tools': ['tools/x']})\n"


def owners(store) -> dict[str, set[str]]:
    found: dict[str, set[str]] = {}
    for r in store.query(f"SELECT ?id ?o WHERE {{ GRAPH ?g {{ ?n <{KI}identifier> ?id ; <{KI}ownedBy> ?o }} }}"):
        found.setdefault(r["id"].value, set()).add(r["o"].value.removeprefix(KI))
    return found


def run(tmp_path, body=None, **kwargs):
    write(tmp_path / "code/docs/standards.md", STANDARDS)
    blocks = [block("units", script(tmp_path / "code", body).as_posix())] if body else []
    return built(tmp_path, *blocks, extra=FAMILIES, **kwargs)


def test_a_value_naming_units_is_one_edge_per_unit_and_an_unknown_one_is_reported_and_kept(tmp_path):
    out, store = run(tmp_path, UNITS)
    assert owners(store) == {"STD-1": {"module/proj/mod-a", "module/proj/mod-b", "module/proj/tools/x"}, "STD-2": {"ghost"}}
    kept = [r["o"].value for r in store.query(f"SELECT ?o WHERE {{ GRAPH ?g {{ ?n <{KI}ownedBy> ?o }} FILTER (isLiteral(?o)) }}")]
    assert kept == ["ghost"], "a name no extractor declared stays as written"
    assert [p for p in out.problems if "ghost" in p] == ["docs/standards.md:4: STD-2 has ownedBy 'ghost', which names no unit an extractor declared"]


def test_a_folder_owner_matches_its_unit_whatever_its_trailing_slash(tmp_path):
    write(tmp_path / "code/docs/standards.md", "| ID | Claim | Owner |\n|---|---|---|\n| STD-1 | **One.** | `tools/` |\n")
    out, store = built(tmp_path, block("units", script(tmp_path / "code", UNITS).as_posix()), extra=FAMILIES)
    assert owners(store) == {"STD-1": {"module/proj/tools/x"}} and not [p for p in out.problems if "ownedBy" in p]


TERM = ('@prefix owl: <http://www.w3.org/2002/07/owl#> .\n@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .\n'
        '<https://example.org/t#%s> a owl:Class ; rdfs:label "%s" .\n')


def test_a_term_under_a_unit_path_is_owned_by_that_unit_and_meets_an_owner_edge(tmp_path):
    for rel, name in (("onto/ledger/spec/a.ttl", "A"), ("onto/ledger/vocab/deep/b.ttl", "B"), ("onto/other/c.ttl", "C")):
        write(tmp_path / "code" / rel, TERM % (name, name))
    write(tmp_path / "code/docs/standards.md", "| ID | Claim | Owner |\n|---|---|---|\n| STD-1 | **One.** | ledger |\n")
    body = "finish(units={'ledger': ['ledger'], 'deep': ['deep']}, unit_paths={'onto/ledger/': 'ledger', 'onto/ledger/vocab': 'deep', 'onto/x': 'ghost'})\n"
    owl = '\n[[projects.extractors]]\nkind = "owl-terms"\npaths = ["code:onto/**/*.ttl"]\n'
    out, store = built(tmp_path, owl, block("units", script(tmp_path / "code", body).as_posix()), extra=FAMILIES)
    found = owners(store)
    assert found["https://example.org/t#A"] == found["STD-1"] == {"module/proj/ledger"}, "the longest path wins and the two meet"
    assert found["https://example.org/t#B"] == {"module/proj/deep"}
    assert found["https://example.org/t#C"] == {"module/proj/onto/other"}, "under no path, a term keeps its document's folder"
    assert [p for p in out.problems if "unit_paths" in p] == ["unit_paths of 'proj' gives onto/x to 'ghost', which no extractor's units declare"]


def test_a_names_cell_is_an_edge_to_the_node_of_that_name(tmp_path):
    """A check can then ask whether something defines the node, as a project's derived entries may."""
    write(tmp_path / "code/docs/standards.md", "| ID | Claim | Governs |\n|---|---|---|\n| STD-1 | **One.** | data/a, data/b |\n")
    _, store = built(tmp_path, extra=FAMILIES)
    found = {r["q"].value for r in store.query(f"SELECT ?q WHERE {{ GRAPH ?g {{ ?n <{KI}governs> ?q FILTER (isIRI(?q)) }} }}")}
    assert found == {str(node("proj", "data/a").value), str(node("proj", "data/b").value)}


def test_with_no_units_declared_every_cell_stays_literal_and_nothing_is_reported(tmp_path):
    out, store = run(tmp_path)
    assert owners(store) == {"STD-1": {"core", "tools"}, "STD-2": {"ghost"}} and not [p for p in out.problems if "ownedBy" in p]
    out, store = run(tmp_path / "again", "finish(units={})\n")
    assert owners(store)["STD-2"] == {"ghost"} and not [p for p in out.problems if "ownedBy" in p], "an empty units declares none"


def test_a_malformed_unit_paths_is_a_failure_of_that_extractor(tmp_path):
    out, _ = run(tmp_path, "finish(unit_paths={'onto': ['mod-a']})\n")
    assert problems(out, "units") and "unit_paths" in problems(out, "units")[0]


@pytest.mark.parametrize("units", ["{'core': 'mod-a'}", "['core']", "{'core': [1]}"])
def test_a_malformed_units_is_a_failure_of_that_extractor(tmp_path, units):
    out, store = run(tmp_path, f"finish(entry('X-1', 'kept'), units={units})\n")
    assert any("units are malformed" in p for p in problems(out, "units")) and "X-1" not in claims(store)


def test_an_in_process_extractor_may_declare_units(tmp_path, monkeypatch):
    monkeypatch.setattr(extractors, "load", lambda kind: (lambda context, settings: extractors.Result(units={"core": ["mod-a"]})))
    write(tmp_path / "code/docs/standards.md", STANDARDS)
    out, store = built(tmp_path, '\n[[projects.extractors]]\nkind = "owl-terms"\npaths = ["code:docs/*.md"]\n', extra=FAMILIES)
    assert owners(store)["STD-1"] >= {"module/proj/mod-a"} and any("ghost" in p for p in out.problems)
