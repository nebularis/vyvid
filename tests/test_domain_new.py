# SPDX-License-Identifier: MIT
"""VYD-8: `vyd domain new` writes a domain that loads and audits clean, a note register type lets a project
specialise a domain's row, and a vyvid.toml naming a domain nobody configured drops that domain and keeps the project."""

from __future__ import annotations

import pytest

from test_index_core import Words
from test_project_file import configure, repo
from vyvid import ask, audit, cli, newdomain
from vyvid import build as builder
from vyvid.config import ConfigError, load
from vyvid.resolve import bind_in

HEAD = "| ID | Tool | Claim | Problem shape | Evidence | Activity | Technology | Specialises | Overrides |\n|---|---|---|---|---|---|---|---|---|\n"
NOTE = "| NOTE-1 | mise | mise run starts a task. | how to run a task | ran it | | | | |\n"
FILE = """[project]
name = "proj"
domains = ["tools"]
specialises = { tools = "docs:tools.md" }

[project.families]
TOOL = { defined = "docs:tools.md", type = "note" }
"""
TOOLS = HEAD + "| TOOL-1 | mise | Here every task goes through mise run. | how to run a task here | read mise.toml | | | tools:NOTE-1 | |\n"


@pytest.fixture(autouse=True)
def no_configuration(tmp_path, monkeypatch):
    monkeypatch.setenv("VYVID_CONFIG", str(tmp_path / "absent.toml"))


def make(tmp_path, name="tools"):
    folder = tmp_path / name
    assert newdomain.new("tools", "note", folder) == 0
    (folder / "notes.md").write_text((folder / "notes.md").read_text(encoding="utf-8") + NOTE, encoding="utf-8")
    return folder


def project(tmp_path, files=None):
    return repo(tmp_path, "proj", FILE, {"docs/tools.md": TOOLS} if files is None else files)


def test_a_new_domain_loads_audits_clean_and_is_a_repository(tmp_path, monkeypatch, capsys):
    folder = tmp_path / "tools"
    assert newdomain.new("tools", "note", folder) == 0
    out = capsys.readouterr().out
    assert '[[domains]]\nname = "tools"\npath = ' in out
    assert (folder / ".git").is_dir() and {p.name for p in folder.iterdir()} == {".git", "domain.toml", "facets.md", "notes.md", "skills"}
    assert "git" not in (folder / "domain.toml").read_text(encoding="utf-8").replace("digit", "")
    findings = audit.audit(folder)
    assert findings and all(f.kind == "html-comment" and "SPDX" in f.text for f in findings), findings
    configure(tmp_path, monkeypatch, f'[[domains]]\nname = "tools"\npath = "{folder.as_posix()}"\n')
    config = load()
    assert list(config.domains["tools"].families) == ["NOTE"] and [r.name for r in config.domains["tools"].recipes] == ["how-do-i"]
    (folder / "notes.md").write_text((folder / "notes.md").read_text(encoding="utf-8") + NOTE, encoding="utf-8")
    result = builder.build(config, None, embed=False, scopes=[config.general, config.domains["tools"]])
    assert result.counts["Note"] == 1 and all("embeddings" in p for p in result.problems), result.problems


def test_it_refuses_a_bad_name_a_folder_with_content_an_unknown_type_and_a_missing_path(tmp_path, capsys):
    for bad in ("Bad", "general", "1x", "a b"):
        assert newdomain.new(bad, "note", tmp_path / "x") == 2
    assert not (tmp_path / "x").exists()
    full = tmp_path / "full"
    full.mkdir()
    (full / "keep.md").write_text("mine", encoding="utf-8")
    assert newdomain.new("tools", "note", full) == 2 and [p.name for p in full.iterdir()] == ["keep.md"]
    assert newdomain.new("tools", "nonsense", tmp_path / "y") == 2
    capsys.readouterr()
    assert newdomain.new("tools", "note", None) == 2 and "Give one with --path" in capsys.readouterr().out
    (tmp_path / "empty").mkdir()
    assert newdomain.new("tools", "note", tmp_path / "empty") == 0, "an empty folder is fine"


def test_the_default_folder_is_the_knowledge_bases_and_the_configuration_is_left_alone(tmp_path, monkeypatch, capsys):
    path = configure(tmp_path, monkeypatch, f'[framework]\nkb = "{(tmp_path / "kb").as_posix()}"\n')
    before = path.read_text(encoding="utf-8")
    assert cli.main(["domain", "new", "tools"]) == 0
    assert (tmp_path / "kb" / "domains" / "tools" / "domain.toml").is_file()
    assert capsys.readouterr().out.rstrip().endswith('[[domains]]\nname = "tools"') and path.read_text(encoding="utf-8") == before


def test_a_project_row_specialises_a_domain_row_and_the_domain_row_is_beneath_it(tmp_path, monkeypatch):
    folder, root = make(tmp_path), project(tmp_path)
    configure(tmp_path, monkeypatch, f'[[domains]]\nname = "tools"\npath = "{folder.as_posix()}"\n')
    config, bound = bind_in(load(), root)
    assert bound.domains == ["tools"] and not bound.dropped
    a = ask.open_stack(config, root, model=Words())
    rows = ask.fold(a, ask.candidates(a, set(), set(), set()))
    assert [r["id"] for r in rows] == ["TOOL-1"]
    assert [p["shown_as"] for p in rows[0]["specialises"]] == ["tools:NOTE-1"]


def test_a_domain_nobody_configured_is_dropped_with_a_note_and_the_specialising_cell_is_left_unresolved(tmp_path, capsys):
    root = project(tmp_path)
    config, bound = bind_in(load(), root)
    assert bound.name == "proj" and bound.domains == [] and bound.dropped == ["tools"] and bound.specialises == {}
    assert not config.files_aside
    assert cli.main(["context", str(root), "--no-pull"]) == 0
    captured = capsys.readouterr()
    assert "project: proj" in captured.out and "NOTE: domain tools is named by vyvid.toml and is not configured here" in captured.err
    assert cli.main(["build", str(root), "--no-embed"]) == 0
    captured = capsys.readouterr()
    assert "NOTE: domain tools is named by vyvid.toml" in captured.err and "tools:" not in captured.out.replace("NOTE: no embeddings", "")
    a = ask.open_stack(config, root, model=Words())
    rows = ask.fold(a, ask.candidates(a, set(), set(), set()))
    assert [r["id"] for r in rows] == ["TOOL-1"] and "specialises" not in rows[0]


def test_the_users_own_entry_naming_an_unknown_domain_stays_an_error(tmp_path, monkeypatch):
    root = project(tmp_path)
    configure(tmp_path, monkeypatch, f'[[projects]]\nname = "proj"\ncode = "{root.as_posix()}"\ndomains = ["tools"]\n')
    with pytest.raises(ConfigError, match="domain 'tools' is not configured"):
        load()
    configure(tmp_path, monkeypatch, f'[[projects]]\nname = "other"\ncode = "{tmp_path.as_posix()}/elsewhere"\ndomains = ["tools"]\n')
    with pytest.raises(ConfigError, match="domain 'tools' is not configured"):
        load()
