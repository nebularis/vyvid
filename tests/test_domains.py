# SPDX-License-Identifier: MIT
"""VYD-3: a domain is a folder with a manifest, its extractors are plug-ins, and a project runs them."""

from __future__ import annotations

import pyoxigraph as ox
import pytest

from test_index_core import Words
from test_index_extract import LEDGER
from vyvid import build as builder
from vyvid import cli, embed, extractors
from vyvid.config import ConfigError, extractor_runs, load
from vyvid.model import KI, ki, node
from vyvid.resolve import layers


def write(root, name, text):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def config_for(tmp_path, text):
    """A configuration whose DOMAINS and CODE are the temporary folders."""
    return write(tmp_path, "config.toml", text.replace("DOMAINS", (tmp_path / "domains").as_posix()).replace("CODE", (tmp_path / "code").as_posix()))


def refused(tmp_path, text):
    with pytest.raises(ConfigError) as error:
        load(config_for(tmp_path, text))
    return error.value.problems


OWL = """
[[domains]]
name = "owl"
path = "DOMAINS/owl"

[[projects]]
name = "proj"
code = "CODE"
domains = ["owl"]
"""


def test_a_manifest_is_merged_with_the_configuration_overriding_it(tmp_path):
    write(tmp_path, "domains/d/domain.toml", 'name = "d"\nparents = ["base"]\nfamilies = { NOTE = {} }\nrules = "self:my-rules.md"\n')
    config = load(config_for(tmp_path, '''
[[domains]]
name = "base"
path = "DOMAINS/base"

[[domains]]
name = "d"
path = "DOMAINS/d"
families = { ITEM = {} }
skills = "self:my-skills"
'''))
    d = config.domains["d"]
    assert d.parents == ["base"], "a key only the manifest sets stands"
    assert list(d.families) == ["ITEM"], "a key the configuration sets replaces the manifest's whole"
    assert d.rules == [tmp_path / "domains" / "d" / "my-rules.md"], "self: is the domain's folder"
    assert d.skills == [tmp_path / "domains" / "d" / "my-skills"]


def test_a_domain_without_a_manifest_is_what_the_configuration_says(tmp_path):
    config = load(config_for(tmp_path, '[[domains]]\nname = "d"\npath = "DOMAINS/absent"\nparents = []\n'))
    assert config.domains["d"].parents == [] and config.domains["d"].extractors == []


def test_a_manifest_must_name_its_domain_and_use_known_keys(tmp_path):
    write(tmp_path, "domains/d/domain.toml", 'name = "other"\nparent = ["x"]\n')
    problems = refused(tmp_path, '[[domains]]\nname = "d"\npath = "DOMAINS/d"\n')
    assert any("domain.toml names the domain 'other'" in p for p in problems) and any("unknown keys parent" in p for p in problems)


def test_a_cycle_declared_across_manifests_is_refused(tmp_path):
    write(tmp_path, "domains/a/domain.toml", 'name = "a"\nparents = ["b"]\n')
    write(tmp_path, "domains/b/domain.toml", 'name = "b"\nparents = ["a"]\n')
    problems = refused(tmp_path, '[[domains]]\nname = "a"\npath = "DOMAINS/a"\n[[domains]]\nname = "b"\npath = "DOMAINS/b"\n')
    assert any("domains form a cycle: a -> b -> a" in p for p in problems)


def test_an_unknown_extractor_kind_is_refused_naming_the_installed_kinds(tmp_path):
    write(tmp_path, "domains/owl/domain.toml", 'name = "owl"\nextractors = [{ kind = "nonesuch" }]\n')
    problems = refused(tmp_path, OWL)
    assert any("not 'nonesuch'" in p and "owl-terms" in p for p in problems), problems


def test_a_project_may_use_only_what_a_domain_of_its_stack_brings(tmp_path):
    write(tmp_path, "domains/owl/domain.toml", 'name = "owl"\nextractors = [{ kind = "owl-terms" }]\n')
    problems = refused(tmp_path, OWL + '\n[projects.uses.owl.nothing]\npaths = ["code:x"]\n[projects.uses.elsewhere.owl-terms]\npaths = ["code:x"]\n')
    assert any("owl.nothing, and owl brings no such extractor" in p for p in problems)
    assert any("uses 'elsewhere', which is not in its stack" in p for p in problems)


def test_a_domains_defaults_are_updated_by_the_project_and_say_where_each_came_from(tmp_path):
    write(tmp_path, "domains/owl/domain.toml",
          'name = "owl"\nextractors = [{ kind = "owl-terms", paths = ["self:vocab/*.ttl"], note = "x" }]\n')
    plain = load(config_for(tmp_path, OWL))
    (run,) = extractor_runs(plain, plain.projects["proj"])
    assert run.settings["paths"] == [tmp_path / "domains" / "owl" / "vocab" / "*.ttl"] and run.domain == "owl"
    assert run.sources == {"paths": "domain 'owl'", "note": "domain 'owl'"}
    over = load(config_for(tmp_path, OWL + '\n[projects.uses.owl.owl-terms]\npaths = ["code:ontology/**/*.ttl"]\n'))
    (run,) = extractor_runs(over, over.projects["proj"])
    assert run.settings["paths"] == [tmp_path / "code" / "ontology" / "**" / "*.ttl"] and run.settings["note"] == "x"
    assert run.sources["paths"] == "project 'proj', uses.owl.owl-terms" and run.sources["note"] == "domain 'owl'"


def owl_world(tmp_path, uses=True):
    write(tmp_path, "domains/owl/domain.toml", 'name = "owl"\nextractors = [{ kind = "owl-terms" }]\n')
    write(tmp_path / "code", "ontology/ledger/ledger.ttl", LEDGER)
    return load(config_for(tmp_path, OWL + ('\n[projects.uses.owl.owl-terms]\npaths = ["code:ontology/**/*.ttl"]\n' if uses else "")))


def graph_ids(store, graph):
    return {str(r["id"].value) for r in store.query(f"SELECT ?id WHERE {{ GRAPH <{graph}> {{ ?t <{KI}identifier> ?id ; a <{KI}Term> }} }}")}


def test_a_domains_extractor_runs_over_the_projects_files_into_the_projects_graphs(tmp_path):
    config = owl_world(tmp_path)
    out = builder.build(config, config.projects["proj"], tmp_path / "index" / "store", model=Words())
    store = builder.open_store(tmp_path / "index" / "store")
    assert graph_ids(store, KI + "terms/proj") == {"https://example.org/ledger#Account", "https://example.org/ledger#keyDimension",
                                                   "https://example.org/ledger#first"}
    assert graph_ids(store, KI + "terms/owl") == set(), "the domain brings the extractor, the project owns what it finds"
    assert bool(store.query(f"ASK {{ GRAPH <{KI}graph/proj/ontology/ledger/ledger.ttl> {{ ?s ?p ?o }} }}"))
    assert out.counts["term"] == 3 and out.counts["ontology-document"] == 1
    nodes, _ = embed.load(tmp_path / "index", config.embedding)
    assert any(n.startswith(KI + "term/proj/") for n in nodes), "a term's claim is embedded from the extractor's texts"


def test_a_project_with_no_paths_for_a_domains_extractor_skips_it_without_a_problem(tmp_path):
    config = owl_world(tmp_path, uses=False)
    assert extractor_runs(config, config.projects["proj"]) == []
    out = builder.build(config, config.projects["proj"], tmp_path / "index" / "store", embed=False)
    assert "term" not in out.counts and out.problems == ["no embeddings, because the build was told not to make them"]


def test_a_project_still_declares_an_extractor_of_its_own(tmp_path):
    write(tmp_path, "domains/owl/domain.toml", 'name = "owl"\nextractors = [{ kind = "owl-terms" }]\n')
    write(tmp_path / "code", "ontology/ledger/ledger.ttl", LEDGER)
    config = load(config_for(tmp_path, OWL + '\n[[projects.extractors]]\nkind = "owl-terms"\npaths = ["code:ontology/**/*.ttl"]\n'))
    (run,) = extractor_runs(config, config.projects["proj"])
    assert run.domain is None and run.sources == {"paths": "project 'proj', extractors"}
    assert builder.build(config, config.projects["proj"], tmp_path / "i" / "store", embed=False).counts["term"] == 3


# ---- The interface ---------------------------------------------------------------------------------


class Entry:
    name = "fake-kind"

    @staticmethod
    def load():
        def extract(context, settings):
            result = extractors.Result()
            thing = node(context.scope.name, "THING-1")
            result.quads.append(ox.Quad(thing, ki("identifier"), ox.Literal("THING-1"), context.index_graph))
            result.texts[thing.value] = "a thing of " + settings["colour"]
            result.prefixes["th"] = "https://example.org/thing#"
            result.problems.append("one thing is odd")
            result.bump("thing")
            return result

        return extract


def test_an_installed_kind_is_a_plug_in_whose_result_is_merged_into_the_build(tmp_path, monkeypatch):
    monkeypatch.setattr(extractors, "_entry_points", lambda: [Entry])
    assert extractors.kinds() == ["fake-kind"]
    config = load(config_for(tmp_path, '''
[[domains]]
name = "d"
path = "DOMAINS/d"
extractors = [{ kind = "fake-kind", colour = "red", paths = ["self:*.x"] }]

[[projects]]
name = "proj"
code = "CODE"
domains = ["d"]

[projects.uses.d.fake-kind]
colour = "blue"
'''))
    out = builder.build(config, config.projects["proj"], tmp_path / "index" / "store", model=Words())
    assert out.counts["thing"] == 1 and "one thing is odd" in out.problems
    nodes, _ = embed.load(tmp_path / "index", config.embedding)
    assert node("proj", "THING-1").value in nodes
    store = builder.open_store(tmp_path / "index" / "store")
    assert bool(store.query(f'ASK {{ GRAPH <{KI}index/proj> {{ <{node("proj", "THING-1").value}> <{KI}identifier> "THING-1" }} }}'))


# ---- Vocabulary ------------------------------------------------------------------------------------

VOCAB = """@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix ex: <https://example.org/vocab#> .
ex:%s a owl:Class .
"""


def test_vocabulary_a_scope_adds_is_loaded_into_the_tbox_graph_after_the_packaged_one(tmp_path):
    write(tmp_path, "domains/d/domain.toml", 'name = "d"\nvocabulary = ["self:vocab.ttl"]\n')
    write(tmp_path, "domains/d/vocab.ttl", VOCAB % "DomainThing")
    write(tmp_path / "code", "vocab.ttl", VOCAB % "ProjectThing")
    config = load(config_for(tmp_path, '''
[[domains]]
name = "d"
path = "DOMAINS/d"

[[projects]]
name = "proj"
code = "CODE"
domains = ["d"]
vocabulary = ["code:vocab.ttl", "code:missing.ttl"]
'''))
    out = builder.build(config, config.projects["proj"], tmp_path / "index" / "store", embed=False)
    store = builder.open_store(tmp_path / "index" / "store")
    declared = lambda iri: bool(store.query(f"ASK {{ GRAPH <{KI}tbox> {{ <{iri}> a <http://www.w3.org/2002/07/owl#Class> }} }}"))
    assert declared("https://example.org/vocab#DomainThing") and declared("https://example.org/vocab#ProjectThing")
    assert declared(KI + "Decision"), "the packaged vocabulary is still there"
    assert out.counts["vocabulary-file"] == 2
    assert any("missing.ttl: vocabulary of 'proj' does not load" in p for p in out.problems)


# ---- Context ---------------------------------------------------------------------------------------


def test_vyd_context_lists_the_extractors_a_domain_brings_and_a_project_runs(tmp_path, monkeypatch, capsys):
    config = owl_world(tmp_path)
    monkeypatch.setenv("VYVID_CONFIG", str(config.source))
    assert cli.main(["context", str(tmp_path / "code")]) == 0
    out = capsys.readouterr().out
    assert out.index("domain owl") < out.index("brings extractor owl-terms") < out.index("project proj") < out.index("runs extractor owl-terms of domain owl")
    assert "(project 'proj', uses.owl.owl-terms)" in out
    assert [s.name for s in layers(config, config.projects["proj"])] == ["general", "owl", "proj"]
