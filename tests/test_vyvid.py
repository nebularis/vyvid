# SPDX-License-Identifier: MIT
"""VYD-1: the configuration, binding a folder to a project, the layers of rules, and identifiers."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from vyvid import cli
from vyvid.config import ConfigError, load
from vyvid.resolve import Unresolved, bind, layers, normalise_remote, resolve

CONFIG = """
[framework]
kb = "{kb}"

[general]
rules = "kb:general/rules.md"

[[domains]]
name = "software-engineering"

[[domains]]
name = "functional"
parents = ["software-engineering"]

[[domains]]
name = "haskell"
parents = ["functional", "software-engineering"]

[[domains]]
name = "triple-stores"
parents = ["software-engineering"]
families = {{ TSD = {{ pattern = 'TSD-\\d+[a-z]?' }} }}

[[projects]]
name = "lattice"
code = "{code}"
match = {{ remote = "github.com/nebularis/lattice" }}
contract = ["code:AGENTS.md"]
domains = ["triple-stores"]
families = {{ STD = {{}}, ADR = {{ pattern = 'ADR-A\\d+' }} }}
delegates = {{ TSD = "triple-stores" }}

[[projects]]
name = "dp"
code = "{dp}"
docs = "{dpdocs}"
domains = ["haskell"]
families = {{ STD = {{}} }}
"""


@pytest.fixture
def world(tmp_path, monkeypatch):
    paths = {k: tmp_path / k for k in ("kb", "code", "dp", "dpdocs", "elsewhere")}
    for p in paths.values():
        p.mkdir()
    (paths["code"] / "AGENTS.md").write_text("contract", encoding="utf-8")
    config = tmp_path / "config.toml"
    config.write_text(CONFIG.format(**{k: v.as_posix() for k, v in paths.items()}), encoding="utf-8")
    monkeypatch.setenv("VYVID_CONFIG", str(config))
    return paths


def test_a_project_folder_gets_general_then_its_domains_then_the_project_last(world):
    config = load()
    stack = [s.name for s in layers(config, bind(config, world["code"] / "deep" / "inside"))]
    assert stack == ["general", "software-engineering", "triple-stores", "lattice"]


def test_a_domain_graph_puts_every_ancestor_before_its_children(world):
    config = load()
    assert [s.name for s in layers(config, bind(config, world["dp"]))] == ["general", "software-engineering", "functional", "haskell", "dp"]


def test_a_projects_private_documents_folder_binds_to_it(world):
    assert bind(load(), world["dpdocs"]).name == "dp"


def test_a_folder_no_project_claims_gets_the_general_scope_alone(world):
    config = load()
    assert bind(config, world["elsewhere"]) is None
    assert [s.name for s in layers(config, None)] == ["general"]


def test_a_clone_elsewhere_binds_by_its_remote(world):
    clone = world["elsewhere"]
    subprocess.run(["git", "init", "-q", str(clone)], check=True)
    subprocess.run(["git", "-C", str(clone), "remote", "add", "origin", "git@github.com:Nebularis/lattice.git"], check=True)
    assert bind(load(), clone).name == "lattice"


@pytest.mark.parametrize("url", [
    "git@github.com:Nebularis/lattice.git", "https://github.com/nebularis/lattice", "ssh://git@github.com/nebularis/lattice.git/",
])
def test_a_remote_is_normalised_as_host_owner_repository(url):
    assert normalise_remote(url) == "github.com/nebularis/lattice"


def test_a_bare_identifier_means_the_scope_it_is_written_in(world):
    config = load()
    assert resolve(config, "STD-12", config.projects["lattice"]) == "lattice:STD-12"
    assert resolve(config, "STD-12", config.projects["dp"]) == "dp:STD-12"


def test_a_delegated_family_resolves_in_the_scope_it_moved_to(world):
    config = load()
    assert resolve(config, "TSD-41", config.projects["lattice"]) == "triple-stores:TSD-41"
    assert resolve(config, "lattice:TSD-41b", config.general) == "triple-stores:TSD-41b"


def test_a_qualified_identifier_names_its_own_scope(world):
    config = load()
    assert resolve(config, "dp:STD-3", config.projects["lattice"]) == "dp:STD-3"


@pytest.mark.parametrize("mention, message", [
    ("XYZ-1", "matches no family"), ("nowhere:STD-1", "not configured"), ("ADR-B12", "matches no family"),
])
def test_an_identifier_that_names_nothing_is_refused(world, mention, message):
    config = load()
    with pytest.raises(Unresolved, match=message):
        resolve(config, mention, config.projects["lattice"])


@pytest.mark.parametrize("extra, message", [
    ('[[domains]]\nname = "a"\nparents = ["b"]\n[[domains]]\nname = "b"\nparents = ["a"]\n', "cycle: a -> b -> a"),
    ('[[domains]]\nname = "a"\nparents = ["missing"]\n', "parent 'missing' is no domain"),
    ('[[projects]]\nname = "p"\ncode = "/tmp"\ndomains = ["missing"]\n', "domain 'missing' is not configured"),
    ('[[projects]]\nname = "q"\ncode = "/tmp"\ndelegates = { STD = "triple-stores" }\n', "declares no such family"),
])
def test_an_unsound_configuration_is_refused_whole(world, tmp_path, monkeypatch, extra, message):
    bad = tmp_path / "bad.toml"
    bad.write_text((tmp_path / "config.toml").read_text(encoding="utf-8") + extra, encoding="utf-8")
    monkeypatch.setenv("VYVID_CONFIG", str(bad))
    with pytest.raises(ConfigError) as error:
        load()
    assert any(message in p for p in error.value.problems), error.value.problems


def test_no_configuration_is_the_general_scope_alone(tmp_path, monkeypatch):
    monkeypatch.setenv("VYVID_CONFIG", str(tmp_path / "absent.toml"))
    config = load()
    assert config.source is None and not config.projects and [s.name for s in layers(config, None)] == ["general"]


def test_vyd_context_prints_the_project_last_and_marks_what_is_missing(world, capsys):
    assert cli.main(["context", str(world["code"])]) == 0
    out = capsys.readouterr().out
    assert out.index("1. general") < out.index("domain triple-stores") < out.index("project lattice")
    assert "AGENTS.md" in out and "rules.md   (missing)" in out
    assert cli.main(["context", str(world["code"]), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["layers"][-1]["scope"] == "lattice"


def test_vyd_resolve_exits_one_on_an_unresolved_identifier(world, capsys):
    assert cli.main(["resolve", "TSD-41", "--in", str(world["code"])]) == 0
    assert capsys.readouterr().out.strip() == "triple-stores:TSD-41"
    assert cli.main(["resolve", "XYZ-1", "--in", str(world["code"])]) == 1
