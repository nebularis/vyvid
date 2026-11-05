# SPDX-License-Identifier: MIT
"""VYD-2, second step: facet registers read and merged in scope order."""

from __future__ import annotations

import random

import pyoxigraph as ox
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


SKOS = "http://www.w3.org/2004/02/skos/core#"
SCHEMES_HEAD = "## Schemes\n\n| ID | Label | Definition |\n|---|---|---|\n| Activity | activity | What is done. |\n| Quality | quality | What is protected. |\n| Technology | technology | What it is specific to. |\n\n"
ROWS = {
    "Activity": ["| design | design | | | yes | Any design. | | yes |", "| api-design | API design | design | interaction | | Designing an interface. | Not for a UI. | yes |",
                 "| query-writing | query writing | design | | | Writing queries. | | no |"],
    "Quality": ["| interaction | interaction | | | | Being usable. | | yes |"],
    "Technology": ["| language | language | | | yes | A language. | | yes |", "| platform | platform | | | yes | A platform. | | yes |",
                   "| java | Java | language platform | | | A language and platform. | | yes |"],
}


def register(order=None) -> str:
    return SCHEMES_HEAD + "".join(f"## {scheme}\n\n{HEAD}" + "\n".join(order(rows) if order else rows) + "\n\n" for scheme, rows in ROWS.items())


def quads(register_text: str) -> set[tuple]:
    schemes, values = facets.merge([("r.md", register_text)])
    return {(t.subject, t.predicate, t.object) for t in ox.parse(facets.turtle(schemes, values).encode("utf-8"), format=ox.RdfFormat.TURTLE)}


def test_each_column_becomes_the_skos_property_that_states_its_meaning():
    g = quads(register())
    iri = lambda local: ox.NamedNode(facets.NS + local)  # noqa: E731
    skos = lambda local: ox.NamedNode(SKOS + local)  # noqa: E731
    assert (iri("design"), skos("topConceptOf"), iri("Activity")) in g
    assert not {t for t in g if t[0] == iri("api-design") and t[1] == skos("topConceptOf")}
    assert (iri("api-design"), skos("broader"), iri("design")) in g
    assert (iri("api-design"), skos("related"), iri("interaction")) in g, "a related value may sit in another scheme"
    assert (iri("api-design"), skos("scopeNote"), ox.Literal("Not for a UI.")) in g
    assert (iri("design"), skos("editorialNote"), ox.Literal("group")) in g
    assert (iri("query-writing"), skos("editorialNote"), ox.Literal("proposed")) in g
    assert {o for s, p, o in g if s == iri("java") and p == skos("broader")} == {iri("language"), iri("platform")}


def test_the_same_register_gives_the_same_bytes_and_any_row_order_the_same_graph():
    """A repeat gives the same bytes, and a permutation of each scheme's rows the same graph."""
    def text(register_text):
        return facets.turtle(*facets.merge([("r.md", register_text)]))

    assert text(register()) == text(register())
    rng = random.Random(7)
    shuffled = register(lambda rows: rng.sample(rows, len(rows)))
    assert shuffled != register(), "the permutation must change the order"
    assert quads(shuffled) == quads(register())
