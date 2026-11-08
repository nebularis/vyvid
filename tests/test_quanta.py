# SPDX-License-Identifier: MIT
"""QU-1 and QU-2: architectural quanta, derived from coupling by a built-in extractor, and run over a read."""

from __future__ import annotations

from pathlib import Path

import pyoxigraph as ox
import pytest

from test_checkouts import quiet_git  # noqa: F401  an autouse fixture
from test_project_file import commit, configure, put, sh
from vyvid import build as builder
from vyvid.config import load
from vyvid.extractors import quanta
from vyvid.resolve import bind_in

KINDS = {"foundation": "substrate", "ledger": "substrate", "mork": "standalone", "capacity": "applied"}
RELEASE = {"foundation", "ledger", "mork"}
KI = "https://www.nebularis.org/vyvid/knowledge#"


def parts(found, identifier):
    return next(q.parts for q in found if q.identifier == identifier)


def test_the_core_is_one_quantum_and_a_one_way_dependent_is_its_own():
    found, _ = quanta.data_quanta(KINDS, {("ledger", "foundation"), ("mork", "foundation")}, RELEASE, {})
    assert parts(found, "data/substrate") == ["foundation", "ledger"]
    assert parts(found, "data/mork") == ["mork"] and parts(found, "data/capacity") == ["capacity"]


def test_a_quantum_grows_as_a_dependency_is_added():
    found, straddling = quanta.data_quanta(KINDS, {("ledger", "mork")}, RELEASE, {})
    assert parts(found, "data/substrate") == ["foundation", "ledger", "mork"]
    assert not any(q.identifier == "data/mork" for q in found) and straddling == []


def test_a_release_member_outside_the_core_quantum_is_reported():
    _, straddling = quanta.data_quanta(KINDS, {("mork", "foundation")}, RELEASE, {})
    assert straddling == ["mork"]


def test_the_core_kind_is_a_setting():
    found, _ = quanta.data_quanta({"a": "core", "b": "core", "c": "other"}, set(), set(), {}, core="core")
    assert parts(found, "data/core") == ["a", "b"] and "The core's 2 layers" in found[0].claim


def compose(**services):
    return {"services": services}


BROKER = {"image": "rabbitmq:3.13"}
STORE = {"image": "stain/jena-fuseki:5.1.0"}


def test_a_shared_store_defeats_a_broker():
    found = quanta.software_quanta("d", compose(
        bus=BROKER, store=STORE,
        service={"environment": {"AMQP": "amqp://bus:5672", "SPARQL": "http://store:3030"}},
        worker={"environment": {"AMQP": "amqp://bus:5672", "SPARQL": "http://store:3030"}}), "p")
    assert [q.parts for q in found] == [["service", "store", "worker"]] and "broker" in found[0].claim


def test_a_broker_separates_components_nothing_else_couples():
    found = quanta.software_quanta("d", compose(
        bus=BROKER, service_store=STORE, worker_store={"image": "postgres:16"},
        service={"environment": {"AMQP": "amqp://bus:5672", "DB": "http://service_store:3030"}},
        worker={"environment": {"AMQP": "amqp://bus:5672", "DB": "postgres://worker_store/x"}}), "p")
    assert sorted(q.parts for q in found) == [["service", "service_store"], ["worker", "worker_store"]]


def test_a_synchronous_call_binds_caller_and_callee():
    assert [q.parts for q in quanta.software_quanta("d", compose(proxy={"depends_on": ["api"]}, api={}), "p")] == [["api", "proxy"]]


# ---- the kind over a project and over a read ------------------------------------------------------

ONTOLOGY = '@prefix owl: <http://www.w3.org/2002/07/owl#> .\n<{iri}> a owl:Ontology ; owl:versionIRI <{iri}/1>{imports} .\n'
TOML = """[project]
name = "{name}"
visibility = "public"

[[project.extractors]]
kind = "quanta"
paths = ["code:ontology/**/*.ttl", "code:deploy/**/docker-compose.yml"]

[[project.extractors.modules]]
name = "foundation"
path = "ontology/foundation"
kind = "substrate"
release = true

[[project.extractors.modules]]
name = "ledger"
path = "ontology/ledger"
kind = "substrate"
release = true

[[project.extractors.modules]]
name = "capacity"
path = "ontology/capacity"
kind = "applied"
"""


def library(root: Path, name: str = "lib") -> Path:
    root.mkdir(parents=True)
    sh(root, "init", "-b", "main")
    put(root, "vyvid.toml", TOML.format(name=name))
    put(root, "ontology/foundation/f.ttl", ONTOLOGY.format(iri="https://example.org/f", imports=""))
    put(root, "ontology/ledger/l.ttl", ONTOLOGY.format(iri="https://example.org/l", imports=" ;\n owl:imports <https://example.org/f/1>"))
    put(root, "ontology/capacity/c.ttl", ONTOLOGY.format(iri="https://example.org/c", imports=" ;\n owl:imports <https://example.org/l/1>"))
    put(root, "deploy/prod/docker-compose.yml", "services:\n  api:\n    environment:\n      DB: http://db:5432\n  db:\n    image: postgres:16\n  web:\n    image: nginx\n")
    commit(root)
    return root


def quanta_of(store_dir: Path) -> dict[str, str]:
    store = ox.Store.read_only(str(store_dir / "store"))
    rows = store.query(f"SELECT ?id ?claim WHERE {{ GRAPH ?g {{ ?n <{KI}identifier> ?id ; <{KI}claim> ?claim ; a <{KI}Quantum> }} }}")
    return {str(r["id"].value): str(r["claim"].value) for r in rows}


@pytest.fixture(autouse=True)
def no_configuration(tmp_path, monkeypatch):
    monkeypatch.setenv("VYVID_CONFIG", str(tmp_path / "absent.toml"))


def test_a_project_gets_its_data_and_software_quanta_from_its_modules_and_compose_files(tmp_path, monkeypatch):
    root = library(tmp_path / "lib")
    configure(tmp_path, monkeypatch, "")
    config, project = bind_in(load(), root)
    builder.build(config, project, embed=False)
    found = quanta_of(builder.store_dir(config, project))
    assert set(found) == {"data/substrate", "data/capacity", "software/prod/api", "software/prod/web"}
    assert "2 layers" in found["data/substrate"] and "coupled through db" in found["software/prod/api"]
    assert "capacity is its own data quantum" in found["data/capacity"]


def test_a_module_outside_the_project_or_without_a_name_is_reported_and_the_rest_still_runs(tmp_path, monkeypatch):
    root = library(tmp_path / "lib")
    put(root, "vyvid.toml", (root / "vyvid.toml").read_text() + '\n[[project.extractors.modules]]\nname = "bad"\npath = "../outside"\n\n[[project.extractors.modules]]\npath = "x"\n')
    commit(root)
    configure(tmp_path, monkeypatch, "")
    config, project = bind_in(load(), root)
    out = builder.build(config, project, embed=False)
    assert sum("module" in p for p in out.problems) == 2 and "data/substrate" in quanta_of(builder.store_dir(config, project))


def test_a_project_that_reads_another_gets_its_quanta_with_no_review_and_no_command(tmp_path, monkeypatch):
    lib = library(tmp_path / "lib")
    head = __import__("subprocess").run(["git", "-C", str(lib), "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    app = tmp_path / "app"
    app.mkdir()
    sh(app, "init", "-b", "main")
    put(app, "vyvid.toml", f'[project]\nname = "app"\nvisibility = "private"\n\n[project.reads.lib]\ncommit = "{head}"\n')
    put(app, "README.md", "x\n")
    commit(app)
    configure(tmp_path, monkeypatch, f'[[projects]]\nname = "lib"\ncode = "{lib.as_posix()}"\nvisibility = "public"\n')
    config, project = bind_in(load(), app)
    assert config.projects["lib"].standing == "knowledge", "the read is not reviewed"
    builder.build(config, project, embed=False)
    found = quanta_of(builder.store_dir(config, project))
    assert "data/substrate" in found and "software/prod/api" in found


def test_a_kind_can_be_skipped_and_the_core_points_at_the_catalogue_when_there_is_one():
    found, _ = quanta.data_quanta({"a": "core", "b": "scaffold", "c": "applied"}, set(), set(), {}, core="core", core_pointer="cat.md", skip=("scaffold",))
    assert [q.identifier for q in found] == ["data/core", "data/c"] and found[0].pointer == "cat.md"
