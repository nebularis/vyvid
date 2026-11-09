# SPDX-License-Identifier: MIT
"""SU-1 and SU-2: a first local setup a person can follow. A command that asks a question refuses at once where its output is
captured, the error for an unset knowledge base says what to do, and ``vyd setup`` sets one up. Real git repositories under a
temporary folder, the user's own git and Вивід configuration replaced by files of the test's, and no network."""

from __future__ import annotations

import builtins
import subprocess
from pathlib import Path

import pytest

from test_checkouts import quiet_git  # noqa: F401  an autouse fixture
from test_project_file import commit, put, sh
from vyvid import cli, setup
from vyvid.config import load


@pytest.fixture(autouse=True)
def machine(tmp_path, monkeypatch):
    """A configuration file and a git configuration of the test's own, and a stand-in for the published domains' remotes."""
    monkeypatch.setenv("VYVID_CONFIG", str(tmp_path / "config.toml"))
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(tmp_path / "gitconfig"))
    (tmp_path / "gitconfig").write_text("[user]\n\tname = t\n\temail = t@example.com\n[protocol \"file\"]\n\tallow = always\n", encoding="utf-8")
    from vyvid import config as configuration

    monkeypatch.setattr(configuration, "own_config", lambda: tmp_path / "config.toml")
    monkeypatch.setattr(setup, "REMOTE", str(tmp_path / "remotes" / "vyvid-{name}"))
    for name in setup.PUBLISHED:
        remote = tmp_path / "remotes" / f"vyvid-{name}"
        remote.mkdir(parents=True)
        sh(remote, "init", "-q", "-b", "main")
        put(remote, "domain.toml", f'name = "{name}"\n')
        commit(remote)


def project(tmp_path: Path, domains: list[str]) -> Path:
    root = tmp_path / "proj"
    root.mkdir(parents=True, exist_ok=True)
    sh(root, "init", "-q", "-b", "main")
    names = ", ".join(f'"{d}"' for d in domains)
    put(root, "vyvid.toml", f'[project]\nname = "proj"\ndomains = [{names}]\n')
    put(root, "README.md", "x\n")
    commit(root)
    return root


# ---- SU-1: a command that asks a question, and the error for an unset kb -------------------------


@pytest.mark.parametrize("stdin,stdout", [(True, False), (False, True), (False, False)])
def test_trust_refuses_at_once_where_a_question_could_not_be_seen_and_says_what_to_run(monkeypatch, capsys, stdin, stdout):
    monkeypatch.setattr(cli, "_person", lambda: stdin)
    monkeypatch.setattr(cli, "_output_terminal", lambda: stdout)
    monkeypatch.setattr(builtins, "input", lambda prompt="": (_ for _ in ()).throw(AssertionError("asked a question nobody could see")))
    assert cli.main(["trust"]) == 1
    err = capsys.readouterr().err
    assert "asks a question" in err and "Run it yourself: vyd trust" in err and "mise exec -- vyd trust" in err and "mise run" in err


def test_kb_accept_refuses_the_same_way(monkeypatch, capsys):
    monkeypatch.setattr(cli, "_person", lambda: True)
    monkeypatch.setattr(cli, "_output_terminal", lambda: False)
    assert cli.main(["kb", "accept", "lifecycle"]) == 1
    assert "Run it yourself: vyd kb accept lifecycle" in capsys.readouterr().err


def test_an_unset_kb_says_where_to_set_it_and_what_to_run(tmp_path, capsys):
    assert cli.main(["domain", "add", "lifecycle", "--remote", "https://example.org/x.git", "--dry-run"]) == 1
    err = capsys.readouterr().err
    assert "needs 'kb', which is not set" in err and "[framework]" in err and "vyd setup" in err


# ---- SU-2: vyd setup ----------------------------------------------------------------------------


def test_a_dry_run_says_what_it_would_do_and_writes_nothing(tmp_path, capsys):
    root = project(tmp_path, ["lifecycle", "custom"])
    assert cli.main(["setup", str(root), "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "would set [framework] kb" in out and "would add the domain lifecycle" in out and "custom" in out and "not a published domain" in out
    assert not (tmp_path / "config.toml").exists()


def test_setup_sets_the_kb_adds_and_clones_the_published_domains_a_project_names_and_lists_the_rest(tmp_path, capsys):
    root = project(tmp_path, ["lifecycle", "tools", "custom"])
    assert cli.main(["setup", str(root)]) == 0
    out = capsys.readouterr().out
    config = load()
    assert config.kb is not None and set(config.domains) == {"lifecycle", "tools"}
    assert all(d.trust == "knowledge" and d.remote and d.visibility == "public" for d in config.domains.values())
    assert all((d.path / "domain.toml").is_file() for d in config.domains.values()), "each is cloned under the knowledge base"
    assert "custom" in out and "not a published domain" in out
    assert "vyd trust" in out and "mise exec -- vyd trust" in out and "vyd domain trust" in out and "reviewed --commit" in out


def test_setup_leaves_what_is_set_and_a_second_run_changes_nothing(tmp_path, capsys):
    kb = tmp_path / "mykb"
    (tmp_path / "config.toml").write_text(f'[framework]\nkb = "{kb.as_posix()}"\n', encoding="utf-8")
    root = project(tmp_path, ["lifecycle"])
    assert cli.main(["setup", str(root)]) == 0
    assert load().kb == kb and (kb / "domains" / "lifecycle" / "domain.toml").is_file()
    before = (tmp_path / "config.toml").read_text()
    capsys.readouterr()
    assert cli.main(["setup", str(root)]) == 0
    assert (tmp_path / "config.toml").read_text() == before and "nothing to set up" in capsys.readouterr().out


def test_no_clone_adds_the_domains_and_leaves_their_folders_to_vyd_kb_clone(tmp_path, capsys):
    root = project(tmp_path, ["lifecycle"])
    assert cli.main(["setup", str(root), "--no-clone"]) == 0
    config = load()
    assert "lifecycle" in config.domains and not config.domains["lifecycle"].path.exists()
    assert "vyd kb clone" in capsys.readouterr().out


def test_a_clone_that_fails_is_reported_and_the_configuration_is_kept(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(setup, "REMOTE", str(tmp_path / "nowhere" / "{name}"))
    root = project(tmp_path, ["lifecycle"])
    assert cli.main(["setup", str(root)]) == 1
    assert "lifecycle" in load().domains and "lifecycle:" in capsys.readouterr().out


def test_a_folder_that_belongs_to_no_project_is_said_so(tmp_path, capsys):
    empty = tmp_path / "empty"
    empty.mkdir()
    assert cli.main(["setup", str(empty)]) == 1
    assert "no project" in capsys.readouterr().err
