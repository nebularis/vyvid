# SPDX-License-Identifier: MIT
"""``units`` in the extractor contract: a module column names units an extractor declared."""

from __future__ import annotations

import pytest

from test_command_extractors import block, built, claims, problems, script
from test_identifiers import write
from vyvid import extractors
from vyvid.model import KI

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


def test_with_no_units_declared_every_cell_stays_literal_and_nothing_is_reported(tmp_path):
    out, store = run(tmp_path)
    assert owners(store) == {"STD-1": {"core", "tools"}, "STD-2": {"ghost"}} and not [p for p in out.problems if "ownedBy" in p]
    out, store = run(tmp_path / "again", "finish(units={})\n")
    assert owners(store)["STD-2"] == {"ghost"} and not [p for p in out.problems if "ownedBy" in p], "an empty units declares none"


@pytest.mark.parametrize("units", ["{'core': 'mod-a'}", "['core']", "{'core': [1]}"])
def test_a_malformed_units_is_a_failure_of_that_extractor(tmp_path, units):
    out, store = run(tmp_path, f"finish(entry('X-1', 'kept'), units={units})\n")
    assert any("units are malformed" in p for p in problems(out, "units")) and "X-1" not in claims(store)


def test_an_in_process_extractor_may_declare_units(tmp_path, monkeypatch):
    monkeypatch.setattr(extractors, "load", lambda kind: (lambda context, settings: extractors.Result(units={"core": ["mod-a"]})))
    write(tmp_path / "code/docs/standards.md", STANDARDS)
    out, store = built(tmp_path, '\n[[projects.extractors]]\nkind = "owl-terms"\npaths = ["code:docs/*.md"]\n', extra=FAMILIES)
    assert owners(store)["STD-1"] >= {"module/proj/mod-a"} and any("ghost" in p for p in out.problems)
