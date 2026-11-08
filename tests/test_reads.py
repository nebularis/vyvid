# SPDX-License-Identifier: MIT
"""RD-1 to RD-4: a project reads another's knowledge from a pinned commit, and skills and recipes come only by name
under review. Real git repositories under a temporary folder, a stand-in model, no network."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from test_checkouts import quiet_git  # noqa: F401  an autouse fixture
from test_index_core import Words
from test_project_file import commit, configure, put, sh
from vyvid import ask
from vyvid import config as configuration
from vyvid.config import ConfigError, load
from vyvid.resolve import bind_in

PIN = "a" * 40
STANDARDS = "| ID | Claim | Pointer |\n|---|---|---|\n| STD-1 | A ledger is kept per key. | docs/standards.md |\n"
SKILL = "---\nname: architecture\ndescription: How the layers fit\n---\n\n# Architecture\n\n## Layers\n\nThree of them.\n"
UPSTREAM = """[project]
name = "up"
visibility = "VIS"
skills = ["code:own"]
skill_prefix = "up-"
contract = "docs:contract.md"

[project.families]
STD = { defined = "docs:standards.md", type = "standard" }

[[project.recipes]]
name = "r"
description = "Use r"
steps = [{ step = "find", words = "{question}", limit = 3 }]

[[project.recipes]]
name = "other"
description = "Another"
steps = [{ step = "find", words = "{question}", limit = 3 }]
"""
DOWN = """[project]
name = "down"
visibility = "VIS"
domains = []
EXTRA
[project.reads.up]
commit = "COMMIT"
READ
"""


def upstream(tmp_path: Path, visibility: str = "public") -> tuple[Path, str]:
    """A repository of project ``up`` with a standard, a contract, a skill and two recipes, and its commit."""
    root = tmp_path / "up"
    root.mkdir()
    sh(root, "init", "-b", "main")
    put(root, "vyvid.toml", UPSTREAM.replace("VIS", visibility))
    put(root, "docs/standards.md", STANDARDS)
    put(root, "docs/contract.md", "# Rules of up\n")
    put(root, "own/architecture/SKILL.md", SKILL)
    commit(root)
    head = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    return root, head


def downstream(tmp_path: Path, pin: str, visibility: str = "public", extra: str = "", read: str = "") -> Path:
    root = tmp_path / "down"
    root.mkdir(parents=True)
    sh(root, "init", "-b", "main")
    put(root, "vyvid.toml", DOWN.replace("VIS", visibility).replace("COMMIT", pin).replace("EXTRA", extra).replace("READ", read))
    put(root, "docs/notes.md", "# Notes\n")
    commit(root)
    return root


@pytest.fixture(autouse=True)
def no_configuration(tmp_path, monkeypatch):
    monkeypatch.setenv("VYVID_CONFIG", str(tmp_path / "absent.toml"))


# ---- RD-1: the configuration ---------------------------------------------------------------------


def test_a_read_is_parsed_with_its_pin_and_allow_lists(tmp_path, monkeypatch):
    up, head = upstream(tmp_path)
    down = downstream(tmp_path, head, read='skills = ["architecture"]\nrecipes = ["r"]\n')
    configure(tmp_path, monkeypatch, f'[[projects]]\nname = "up"\ncode = "{up.as_posix()}"\n')
    config, project = bind_in(load(), down)
    read = project.reads["up"]
    assert (read.name, read.commit, read.skills, read.recipes) == ("up", head, ("architecture",), ("r",))
    assert project.unread == [] and not config.files_aside


def test_a_read_needs_a_full_commit_and_known_keys(tmp_path, monkeypatch):
    up, head = upstream(tmp_path)
    configure(tmp_path, monkeypatch, f'[[projects]]\nname = "up"\ncode = "{up.as_posix()}"\n')
    for pin, text in (("abc1234", "full commit"), ("main", "full commit")):
        config, project = bind_in(load(), downstream(tmp_path / pin, pin))
        assert project is None and any(text in p for ps in config.files_aside.values() for p in ps), pin
    config, project = bind_in(load(), downstream(tmp_path / "keys", head, read="colour = 1\n"))
    assert project is None and any("colour" in p for ps in config.files_aside.values() for p in ps)
    config, project = bind_in(load(), downstream(tmp_path / "list", head, read="skills = \"architecture\"\n"))
    assert project is None and any("skills" in p and "list" in p for ps in config.files_aside.values() for p in ps)


def test_a_project_does_not_read_itself(tmp_path, monkeypatch):
    up, head = upstream(tmp_path)
    put(up, "vyvid.toml", UPSTREAM.replace("VIS", "public") + f'\n[project.reads.up]\ncommit = "{head}"\n')
    config, project = bind_in(load(), up)
    assert project is None and any("itself" in p for ps in config.files_aside.values() for p in ps)


def test_a_read_of_a_project_that_is_not_configured_is_noted_and_skipped(tmp_path, monkeypatch):
    up, head = upstream(tmp_path)
    down = downstream(tmp_path, head)
    config, project = bind_in(load(), down)
    assert project.name == "down" and project.reads == {} and project.unread == ["up"] and not config.files_aside


def test_the_review_is_the_users_alone_and_stands_only_at_the_pin(tmp_path, monkeypatch):
    up, head = upstream(tmp_path)
    down = downstream(tmp_path, head, extra='reviewed_reads = { up = "ABC" }\n')
    configure(tmp_path, monkeypatch, f'[[projects]]\nname = "up"\ncode = "{up.as_posix()}"\n')
    config, project = bind_in(load(), down)
    assert project is None and any("reviewed_reads" in p and "only the user's configuration" in p for ps in config.files_aside.values() for p in ps)
    plain = downstream(tmp_path / "plain", head)
    for recorded, standing in ((head, "reviewed"), (head[:10], "reviewed"), ("b" * 40, "knowledge"), ("", "knowledge")):
        text = f'[[projects]]\nname = "up"\ncode = "{up.as_posix()}"\n[[projects]]\nname = "down"\ncode = "{plain.as_posix()}"\n'
        if recorded:
            text += f'[projects.reviewed_reads]\nup = "{recorded}"\n'
        configure(tmp_path, monkeypatch, text)
        project = bind_in(load(), plain)[1]
        assert project.reads["up"].standing(project) == standing, recorded


def test_a_public_project_never_reads_a_private_one(tmp_path, monkeypatch):
    up, head = upstream(tmp_path, "private")
    down = downstream(tmp_path, head)
    configure(tmp_path, monkeypatch, f'[[projects]]\nname = "up"\ncode = "{up.as_posix()}"\nvisibility = "private"\n')
    config, project = bind_in(load(), down)
    assert project is None
    assert any("public" in p and "private" in p and "up" in p for ps in config.files_aside.values() for p in ps)
    # A private project may read a private one, and a private or public one a public one.
    assert bind_in(load(), downstream(tmp_path / "p", head, "private"))[1].reads["up"].commit == head


def test_the_guard_holds_in_the_users_own_entry(tmp_path, monkeypatch):
    up, head = upstream(tmp_path, "private")
    down = tmp_path / "plain"
    down.mkdir()
    configure(tmp_path, monkeypatch, f'[[projects]]\nname = "up"\ncode = "{up.as_posix()}"\nvisibility = "private"\n'
                                    f'[[projects]]\nname = "down"\ncode = "{down.as_posix()}"\n[projects.reads.up]\ncommit = "{head}"\n')
    with pytest.raises(ConfigError) as error:
        load()
    assert any("public" in p and "private" in p for p in error.value.problems)


def test_scope_refuses_a_private_project_for_a_public_one_and_leaves_domains_as_they_were(tmp_path, monkeypatch):
    pub, priv = tmp_path / "pub", tmp_path / "priv"
    for r in (pub, priv):
        r.mkdir()
    dom = tmp_path / "dom"
    (dom / "knowledge").mkdir(parents=True)
    configure(tmp_path, monkeypatch, f'[[domains]]\nname = "secret"\npath = "{dom.as_posix()}"\nvisibility = "private"\n'
                                    f'[[projects]]\nname = "pub"\ncode = "{pub.as_posix()}"\n'
                                    f'[[projects]]\nname = "priv"\ncode = "{priv.as_posix()}"\nvisibility = "private"\n')
    config, project = bind_in(load(), pub)
    a = ask.Asker(config, project, [config.general, project], tmp_path / "store")
    with pytest.raises(ValueError, match="private"):
        a.choose("priv")
    with pytest.raises(ValueError, match="private"):
        a.choose("only:priv,pub")
    a.choose("secret")
    assert [s.name for s in a.visible][-1] == "secret"
    config, project = bind_in(load(), priv)
    ask.Asker(config, project, [config.general, project], tmp_path / "store").choose("pub")


def test_context_shows_what_a_project_reads_and_says_what_it_cannot(tmp_path, monkeypatch, capsys):
    import json

    from vyvid import cli

    up, head = upstream(tmp_path)
    down = downstream(tmp_path, head, read='skills = ["architecture"]\n')
    configure(tmp_path, monkeypatch, f'[[projects]]\nname = "up"\ncode = "{up.as_posix()}"\n')
    assert cli.main(["context", str(down), "--no-pull", "--json"]) == 0
    layer = json.loads(capsys.readouterr().out)["layers"][-1]
    assert layer["reads"] == [{"name": "up", "commit": head, "standing": "knowledge", "skills": ["architecture"], "recipes": []}]
    assert cli.main(["context", str(down), "--no-pull"]) == 0
    assert f"reads up at {head[:12]}, knowledge alone" in capsys.readouterr().out
    configure(tmp_path, monkeypatch, "")
    assert cli.main(["context", str(down), "--no-pull"]) == 0
    assert "NOTE: reads up, which is not configured here" in capsys.readouterr().err
