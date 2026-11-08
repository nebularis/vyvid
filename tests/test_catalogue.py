# SPDX-License-Identifier: MIT
"""CT-1 and CT-2: a repository catalogue that Вивід reads, and the places that use it."""

from __future__ import annotations

from pathlib import Path

import pytest

from test_project_file import put
from vyvid import catalogue
from vyvid.catalogue import CatalogueError, load

FENCE = "```"
CATALOGUE = f"""# Catalogue

Prose, and a block shown as an example inside a longer fence is text:

````markdown
{FENCE}toml repository-catalogue
[catalogue]
modules = ["not-read"]
{FENCE}
````

{FENCE}python
x = 1
{FENCE}

{FENCE}toml repository-catalogue
[conventions]
roles = ["spec", "docs"]

[conventions.kinds]
substrate = "a layer"
applied = "an applied module"
{FENCE}

{FENCE}toml repository-catalogue
[conventions.release]
version = "1.2.3"
kinds = ["substrate"]

[catalogue]
modules = ["foundation", "applied/cap"]
{FENCE}

{FENCE}toml repository-catalogue
[[roots]]
name = "ontology"
path = "ontology/"
owns = "semantic assets"
colour = "red"

[[docs]]
name = "developer"
path = "docs/developer/"
owns = "working documents"

[[tools]]
name = "reader"
path = "tools/reader"
import-names = ["reader"]

[generated]
paths = ["build"]

[site]
title = "a block the reader does not know"
{FENCE}
"""


def module_readme(kind: str, extra: str = "") -> str:
    return f"# M\n\n{FENCE}toml repository-catalogue\n[module]\nkind = \"{kind}\"\nroles = [\"spec\", \"docs\"]\n{extra}{FENCE}\n"


def tree(root: Path, **changes) -> Path:
    files = {"repository-catalogue.md": CATALOGUE,
             "ontology/foundation/README.md": module_readme("substrate", 'imports = []\n[module.extract]\nspec = ["spec/f.ttl"]\n'),
             "ontology/applied/cap/README.md": module_readme("applied", 'imports = ["foundation"]\nmystery = 3\n')}
    files.update(changes)
    for name, text in files.items():
        if text is not None:
            put(root, name, text)
    return root


def test_the_catalogue_is_read_with_its_modules_areas_tools_and_conventions(tmp_path):
    c = load(tree(tmp_path) / "repository-catalogue.md", "ontology")
    assert c.root == tmp_path.resolve() and list(c.modules) == ["foundation", "applied/cap"]
    foundation, cap = c.module("foundation"), c.module("applied/cap")
    assert (foundation.kind, foundation.path, foundation.imports) == ("substrate", Path("ontology/foundation"), ())
    assert cap.imports == ("foundation",) and cap.path == Path("ontology/applied/cap") and cap.extra == {"mystery": 3}
    assert foundation.directory("spec") == Path("ontology/foundation/spec") and foundation.files("spec") == (Path("ontology/foundation/spec/f.ttl"),)
    assert c.area("developer") == Path("docs/developer") and c.area("ontology") == Path("ontology")
    assert [t.name for t in c.tools] == ["reader"] and c.tools[0].import_names == ("reader",)
    assert c.release_version == "1.2.3" and [m.name for m in c.release_members()] == ["foundation"]
    assert [m.name for m in c.modules_of_kind("applied")] == ["applied/cap"]
    assert c.is_generated("build/x/y") and not c.is_generated("builder")


def test_what_the_reader_does_not_know_is_kept_and_a_fenced_example_is_not_read(tmp_path):
    c = load(tree(tmp_path) / "repository-catalogue.md", "ontology")
    assert c.extra == {"site": {"title": "a block the reader does not know"}} and c.roots[0].extra == {"colour": "red"}
    assert "not-read" not in c.modules


def test_a_role_a_module_lacks_and_an_area_nobody_named_are_refused_with_what_is_known(tmp_path):
    c = load(tree(tmp_path) / "repository-catalogue.md", "ontology")
    with pytest.raises(CatalogueError, match="no role 'shapes'"):
        c.module("foundation").directory("shapes")
    with pytest.raises(CatalogueError, match=r"known: developer, ontology"):
        c.area("nonesuch")
    with pytest.raises(CatalogueError, match="no module 'nonesuch'"):
        c.module("nonesuch")


@pytest.mark.parametrize("change,why", [
    ({"repository-catalogue.md": CATALOGUE.replace('modules = ["foundation", "applied/cap"]', 'modules = ["foundation", "foundation"]')}, "listed twice"),
    ({"ontology/foundation/README.md": None, "repository-catalogue.md": CATALOGUE.replace('"foundation", ', '"gone", ')}, "does not exist"),
    ({"ontology/foundation/README.md": module_readme("mystery")}, "kind 'mystery'"),
    ({"ontology/foundation/README.md": "# no block\n"}, "[module] table"),
    ({"repository-catalogue.md": CATALOGUE.replace('kinds = ["substrate"]', 'kinds = ["nonesuch"]')}, "not conventions' kinds"),
    ({"repository-catalogue.md": CATALOGUE.replace('name = "developer"', 'name = "ontology"')}, "used twice"),
    ({"repository-catalogue.md": CATALOGUE.replace("[generated]", "[conventions]\nroles = []\n[generated]")}, "defined twice"),
    ({"repository-catalogue.md": CATALOGUE.replace('owns = "working documents"', "")}, "needs 'owns'"),
    ({"repository-catalogue.md": CATALOGUE.replace('name = "developer"', 'name = "Not Lower"')}, "lower-case"),
    ({"repository-catalogue.md": CATALOGUE.replace('paths = ["build"]', "paths = [")}, "does not parse"),
    ({"repository-catalogue.md": CATALOGUE + f"\n{FENCE}toml repository-catalogue\n[x]\n"}, "unterminated fence"),
])
def test_a_catalogue_that_cannot_be_used_is_refused_naming_the_file_and_the_reason(tmp_path, change, why):
    if change.get("ontology/foundation/README.md", 1) is None:
        tree(tmp_path)
        (tmp_path / "ontology/foundation/README.md").unlink()
        change = {k: v for k, v in change.items() if v is not None}
    with pytest.raises(CatalogueError, match=why.replace("[", r"\[").replace("]", r"\]")):
        load(tree(tmp_path, **change) / "repository-catalogue.md", "ontology")


def test_a_missing_file_is_refused_and_the_nearest_catalogue_above_a_path_is_found(tmp_path):
    with pytest.raises(CatalogueError, match="does not exist"):
        load(tmp_path / "repository-catalogue.md")
    tree(tmp_path)
    (tmp_path / "a" / "b").mkdir(parents=True)
    assert catalogue.root_above(tmp_path / "a" / "b") == tmp_path.resolve() and catalogue.root_above(tmp_path.parent / "elsewhere") is None


def test_dump_holds_every_path_relative_to_the_root(tmp_path):
    out = catalogue.dump(load(tree(tmp_path) / "repository-catalogue.md", "ontology"))
    assert out["modules"]["applied/cap"]["path"] == "ontology/applied/cap" and out["release"] == {"version": "1.2.3", "members": ["foundation"]}
    assert out["docs"] == [{"name": "developer", "path": "docs/developer/", "owns": "working documents"}]


# ---- CT-2: the project setting, vyd catalogue, quanta from the catalogue --------------------------

import subprocess

import pyoxigraph as ox

from test_project_file import commit, configure, sh
from vyvid import ask, cli
from vyvid import build as builder
from vyvid.config import load as load_config
from vyvid.resolve import bind_in

KI = "https://www.nebularis.org/vyvid/knowledge#"
ONTO = '@prefix owl: <http://www.w3.org/2002/07/owl#> .\n<{iri}> a owl:Ontology ; owl:versionIRI <{iri}/1>{imports} .\n'
PROJECT = """[project]
name = "proj"
visibility = "public"

[project.catalogue]
file = "code:repository-catalogue.md"
module_root = "ontology"

[[project.extractors]]
kind = "quanta"
paths = ["code:ontology/**/*.ttl"]
"""


def project(root: Path, toml: str = PROJECT) -> Path:
    tree(root)
    put(root, "vyvid.toml", toml)
    put(root, "ontology/foundation/spec/f.ttl", ONTO.format(iri="https://example.org/f", imports=""))
    put(root, "ontology/applied/cap/spec/c.ttl", ONTO.format(iri="https://example.org/c", imports=" ;\n owl:imports <https://example.org/f/1>"))
    return root


@pytest.fixture(autouse=True)
def no_configuration(tmp_path, monkeypatch):
    monkeypatch.setenv("VYVID_CONFIG", str(tmp_path / "absent.toml"))
    configure(tmp_path, monkeypatch, "")


def test_a_project_names_its_catalogue_and_a_module_root_that_leaves_it_is_refused(tmp_path):
    root = project(tmp_path / "p")
    config, bound = bind_in(load_config(), root)
    assert bound.catalogue.file == root.resolve() / "repository-catalogue.md" and bound.catalogue.module_root == "ontology"
    put(root, "vyvid.toml", PROJECT.replace('"ontology"', '"../x"'))
    config, bound = bind_in(load_config(), root)
    assert bound is None and any("module_root" in p for ps in config.files_aside.values() for p in ps)


def test_vyd_catalogue_answers_by_name_relative_to_the_root_or_absolute(tmp_path, capsys):
    root = project(tmp_path / "p")
    assert cli.main(["catalogue", "area", "developer", "--in", str(root)]) == 0
    assert capsys.readouterr().out == "docs/developer\n"
    assert cli.main(["catalogue", "path", "foundation", "spec", "--in", str(root), "--absolute"]) == 0
    assert capsys.readouterr().out.strip() == str(root.resolve() / "ontology/foundation/spec")
    assert cli.main(["catalogue", "paths", "foundation", "spec", "--in", str(root)]) == 0
    assert capsys.readouterr().out == "ontology/foundation/spec/f.ttl\n"
    assert cli.main(["catalogue", "modules", "--kind", "applied", "--in", str(root)]) == 0
    assert capsys.readouterr().out == "applied/cap  applied  ontology/applied/cap\n"
    assert cli.main(["catalogue", "show", "--in", str(root)]) == 0 and "2 module(s), 2 area(s)" in capsys.readouterr().out
    assert cli.main(["catalogue", "dump", "--in", str(root)]) == 0 and '"applied/cap"' in capsys.readouterr().out


def test_vyd_catalogue_says_what_is_wrong_and_exits_1(tmp_path, capsys):
    root = project(tmp_path / "p")
    assert cli.main(["catalogue", "area", "nonesuch", "--in", str(root)]) == 1
    assert "known: developer, ontology" in capsys.readouterr().err
    bare = tmp_path / "bare"
    bare.mkdir()
    put(bare, "vyvid.toml", '[project]\nname = "bare"\n')
    assert cli.main(["catalogue", "show", "--in", str(bare)]) == 1
    assert "declares no catalogue" in capsys.readouterr().err


def quanta_of(directory: Path) -> set[str]:
    store = ox.Store.read_only(str(directory / "store"))
    return {str(r["id"].value) for r in store.query(f"SELECT ?id WHERE {{ GRAPH ?g {{ ?n <{KI}identifier> ?id ; a <{KI}Quantum> }} }}")}


def test_the_quanta_kind_takes_its_modules_from_the_catalogue_and_an_edit_to_it_makes_the_index_stale(tmp_path):
    root = project(tmp_path / "p")
    config, bound = bind_in(load_config(), root)
    builder.build(config, bound, embed=False)
    assert quanta_of(builder.store_dir(config, bound)) == {"data/substrate", "data/applied/cap"}
    stack = ask.layers(config, bound) if hasattr(ask, "layers") else [config.general, bound]
    assert root.resolve() / "ontology/foundation/README.md" in ask.declared_files(config, stack)


def test_a_project_that_reads_another_gets_the_modules_of_the_others_catalogue(tmp_path, monkeypatch):
    lib = project(tmp_path / "lib")
    put(lib, "vyvid.toml", PROJECT.replace('name = "proj"', 'name = "lib"'))
    sh(lib, "init", "-b", "main")
    commit(lib)
    head = subprocess.run(["git", "-C", str(lib), "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    app = tmp_path / "app"
    app.mkdir()
    sh(app, "init", "-b", "main")
    put(app, "vyvid.toml", f'[project]\nname = "app"\nvisibility = "private"\n\n[project.reads.lib]\ncommit = "{head}"\n')
    put(app, "README.md", "x\n")
    commit(app)
    configure(tmp_path, monkeypatch, f'[[projects]]\nname = "lib"\ncode = "{lib.as_posix()}"\nvisibility = "public"\n')
    config, bound = bind_in(load_config(), app)
    assert config.projects["lib"].catalogue.file.is_relative_to(builder.store_dir(config)), "the read's catalogue is its snapshot's"
    builder.build(config, bound, embed=False)
    assert quanta_of(builder.store_dir(config, bound)) == {"data/substrate", "data/applied/cap"}
