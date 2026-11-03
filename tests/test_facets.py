# SPDX-License-Identifier: MIT
"""VYD-2, second step: facet registers read and merged in scope order."""

from __future__ import annotations

import pytest

from vyvid import facets
from vyvid.config import load
from vyvid.resolve import bind, layers

HEAD = "| ID | Label | Broader | Related | Group | Definition | Scope note | Ratified |\n|---|---|---|---|---|---|---|---|\n"


def extension(rows: str, scheme: str = "Technology") -> tuple[str, str]:
    return ("ext.md", f"## {scheme}\n\n{HEAD}{rows}")


def test_the_packaged_general_register_holds_the_three_schemes():
    schemes, values = facets.merge([("default", facets.default_register())])
    assert [s.slug for s in schemes] == ["Activity", "Quality", "Technology"]
    assert len(values) > 300 and "physical-data-modelling" in facets.taggable(values)["Activity"]


def test_a_later_register_extends_a_general_scheme():
    _, values = facets.merge([("default", facets.default_register()),
                              extension("| cabal | cabal | |  |  | Haskell's build tool. |  | yes |\n")])
    assert "cabal" in facets.taggable(values)["Technology"]


@pytest.mark.parametrize("rows, scheme, message", [
    ("| java | Java again | | | | A second Java. | | yes |\n", "Technology", "java is already defined"),
    ("| x | x | nowhere | | | X. | | yes |\n", "Technology", "broader value nowhere is defined nowhere"),
    ("| y | y | coding | | | Y. | | yes |\n", "Technology", "broader value coding is in Activity, not Technology"),
    ("| z | z | | | | Z. | | yes |\n", "Mood", "which no register declares as a scheme"),
    ("| w | w | | | maybe | W. | | yes |\n", "Technology", "Group is 'maybe'"),
])
def test_a_merge_that_cannot_be_read_is_refused_with_its_problem(rows, scheme, message):
    with pytest.raises(facets.RegisterError) as error:
        facets.merge([("default", facets.default_register()), extension(rows, scheme)])
    assert any(message in p for p in error.value.problems), error.value.problems


def test_the_turtle_is_the_same_bytes_for_the_same_registers():
    merged = facets.merge([("default", facets.default_register())])
    assert facets.turtle(*merged) == facets.turtle(*merged)
    assert "fct:java rdf:type skos:Concept" in facets.turtle(*merged)


def test_a_projects_registers_follow_the_general_one(tmp_path, monkeypatch):
    project = tmp_path / "p"
    (project / "docs").mkdir(parents=True)
    (project / "docs/facets.md").write_text("## Technology\n\n" + HEAD + "| cabal | cabal | | | | Haskell's build tool. | | yes |\n", encoding="utf-8")
    config = tmp_path / "c.toml"
    config.write_text(f'[[projects]]\nname = "p"\ncode = "{project.as_posix()}"\nfacets = ["docs:facets.md"]\n', encoding="utf-8")
    monkeypatch.setenv("VYVID_CONFIG", str(config))
    c = load()
    names = [name for name, _ in facets.registers(layers(c, bind(c, project)))]
    assert names[0] == "vyvid:data/facets.md" and names[1].endswith("docs/facets.md")
    assert "cabal" in facets.taggable(facets.merge(facets.registers(layers(c, bind(c, project))))[1])["Technology"]
