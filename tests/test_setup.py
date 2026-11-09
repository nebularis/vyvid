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


def test_a_project_set_aside_for_a_domain_nobody_configured_is_the_one_setup_mends(tmp_path, capsys):
    root = project(tmp_path, ["lifecycle"])
    put(root, "vyvid.toml", (root / "vyvid.toml").read_text() + '\n[project.delegates]\nTSD = "triple-stores"\n\n[[project.moves]]\nfamily = "STD"\nto = "tools"\n'
        'source = "code:README.md"\ncommit = "abc1234"\n')
    commit(root)
    assert cli.main(["setup", str(root)]) == 0
    assert set(load().domains) == {"lifecycle", "triple-stores", "tools"}, "a delegation's and a move's domains are named too"


# ---- SU-4 and SU-5: skills while a domain is unreviewed ------------------------------------------


def skills_world(tmp_path, monkeypatch, trust: str):
    """A project with composed skills committed from an own domain, then its configuration at ``trust``. The domain is a git clone."""
    from test_skills import world

    config, code = world(tmp_path)
    domain = tmp_path / "lifecycle-domain"
    sh(domain, "init", "-q", "-b", "main")
    commit(domain)
    head = subprocess.run(["git", "-C", str(domain), "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    assert cli.main(["install", "--project", "--in", str(code), "--no-git-hooks"]) == 0
    committed = sorted(p for p in code.rglob("SKILL.md") if ".vyvid" not in p.parts)
    assert committed
    path = tmp_path / "config.toml"
    path.write_text(path.read_text(encoding="utf-8").replace('trust = "own"', f'trust = "{trust}"'), encoding="utf-8")
    monkeypatch.setenv("VYVID_CONFIG", str(path))
    return code, domain, head, committed


@pytest.mark.parametrize("trust", ["knowledge", "reviewed-elsewhere"])
def test_the_skills_check_does_not_run_while_a_domain_is_unreviewed_and_names_it_and_the_line_that_reviews_it(tmp_path, monkeypatch, capsys, trust):
    code, domain, head, committed = skills_world(tmp_path, monkeypatch, "knowledge")
    if trust == "reviewed-elsewhere":
        path = tmp_path / "config.toml"
        path.write_text(path.read_text(encoding="utf-8").replace('trust = "knowledge"', f'trust = "reviewed"\ncommit = "{"b" * 40}"'), encoding="utf-8")
    capsys.readouterr()
    assert cli.main(["check", "skills", str(code)]) == 2
    out = capsys.readouterr().out
    assert "not reviewed" in out and "lifecycle" in out and f"vyd domain trust lifecycle reviewed --commit {head}" in out
    assert "generated and no source makes it now" not in out and "vyd install --project" not in out


def test_install_writes_what_it_can_and_removes_no_skill_while_a_domain_is_unreviewed(tmp_path, monkeypatch, capsys):
    code, domain, head, committed = skills_world(tmp_path, monkeypatch, "knowledge")
    stale = code / ".claude" / "skills" / "gone" / "SKILL.md"
    stale.parent.mkdir(parents=True)
    stale.write_text(committed[0].read_text(encoding="utf-8").replace("name: ", "name: gone-", 1), encoding="utf-8")
    capsys.readouterr()
    assert cli.main(["install", "--project", "--in", str(code), "--no-git-hooks"]) == 1
    out = capsys.readouterr().out
    assert all(p.exists() for p in committed) and stale.exists(), "nothing is removed"
    assert "removed" not in out and "not reviewed" in out and f"reviewed --commit {head}" in out


def test_install_still_removes_a_stale_skill_once_every_domain_is_trusted(tmp_path, monkeypatch, capsys):
    code, domain, head, committed = skills_world(tmp_path, monkeypatch, "knowledge")
    path = tmp_path / "config.toml"
    path.write_text(path.read_text(encoding="utf-8").replace('trust = "knowledge"', 'trust = "own"'), encoding="utf-8")
    stale = code / ".claude" / "skills" / "gone" / "SKILL.md"
    stale.parent.mkdir(parents=True)
    stale.write_text(committed[0].read_text(encoding="utf-8").replace("name: ", "name: gone-", 1), encoding="utf-8")
    assert cli.main(["install", "--project", "--in", str(code), "--no-git-hooks"]) == 0
    assert not stale.exists() and all(p.exists() for p in committed)


def test_setup_prints_each_cloned_domains_review_line_with_its_commit(tmp_path, capsys):
    root = project(tmp_path, ["lifecycle", "tools"])
    assert cli.main(["setup", str(root)]) == 0
    out = capsys.readouterr().out
    config = load()
    for name in ("lifecycle", "tools"):
        head = subprocess.run(["git", "-C", str(config.domains[name].path), "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
        assert f"vyd domain trust {name} reviewed --commit {head}" in out
    assert "read it first" in out
