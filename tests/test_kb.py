# SPDX-License-Identifier: MIT
"""Managed assets: domains under the knowledge base are git clones kept by their policy."""

from __future__ import annotations

import os
import subprocess
from dataclasses import replace

import pytest

from vyvid import cli, kb
from vyvid.config import ConfigError, GitPolicy, load

HOUR = 3600
TRAILER = "Co-Authored-By: Test Agent <agent@example.invalid>"


def sh(*args, cwd):
    done = subprocess.run(args, cwd=cwd, capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    return done.stdout.strip()


@pytest.fixture
def world(tmp_path, monkeypatch):
    for key, value in {"GIT_AUTHOR_NAME": "T", "GIT_AUTHOR_EMAIL": "t@example.invalid", "GIT_COMMITTER_NAME": "T",
                       "GIT_COMMITTER_EMAIL": "t@example.invalid", "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}.items():
        monkeypatch.setenv(key, value)
    remote = tmp_path / "remote.git"
    sh("git", "init", "--bare", "-b", "main", str(remote), cwd=tmp_path)
    seed = tmp_path / "seed"
    sh("git", "clone", str(remote), str(seed), cwd=tmp_path)
    (seed / "register.md").write_text("| NOTE-1 | first |\n", encoding="utf-8")
    sh("git", "add", ".", cwd=seed)
    sh("git", "commit", "-m", "seed", cwd=seed)
    sh("git", "push", "origin", "HEAD:main", cwd=seed)
    (tmp_path / "code").mkdir()
    (tmp_path / "kb").mkdir()

    def configure(git="", trailers=True):
        text = f'''
[framework]
kb = "{(tmp_path / "kb").as_posix()}"
store = "{(tmp_path / "store").as_posix()}"
{f"commit_trailers = [{TRAILER!r}]" if trailers else ""}

[[domains]]
name = "tools"
remote = "{remote.as_posix()}"
{git}

[[projects]]
name = "proj"
code = "{(tmp_path / "code").as_posix()}"
domains = ["tools"]
'''
        path = tmp_path / "config.toml"
        path.write_text(text, encoding="utf-8")
        monkeypatch.setenv("VYVID_CONFIG", str(path))
        return load(path)

    return {"tmp": tmp_path, "remote": remote, "seed": seed, "folder": tmp_path / "kb" / "domains" / "tools", "configure": configure}


def cloned(world, git=""):
    config = world["configure"](git)
    assert kb.clone(config, config.domains["tools"]).ok
    return config


def test_clone_then_status_reports_a_clean_clone_of_its_remote(world, capsys):
    config = world["configure"]()
    assert [d.name for d in kb.managed(config)] == ["tools"]
    assert cli.main(["kb", "clone"]) == 0
    status = kb.inspect(config, config.domains["tools"])
    assert status.clone and status.branch == "main" and (status.ahead, status.behind, status.changes) == (0, 0, 0)
    capsys.readouterr()
    assert cli.main(["kb", "status"]) == 0
    out = capsys.readouterr().out
    assert "clone of" in out and "clean" in out and "pull=on-start commit=manual push=manual" in out


def test_a_folder_that_is_another_repository_is_reported_and_not_overwritten(world, capsys):
    config = world["configure"]()
    folder = world["folder"]
    folder.mkdir(parents=True)
    sh("git", "init", "-b", "main", str(folder), cwd=world["tmp"])
    (folder / "mine.md").write_text("mine\n", encoding="utf-8")
    assert not kb.clone(config, config.domains["tools"]).ok
    assert cli.main(["kb", "clone", "tools"]) == 1
    assert (folder / "mine.md").read_text(encoding="utf-8") == "mine\n" and not (folder / "register.md").exists()
    assert not kb.inspect(config, config.domains["tools"]).clone
    cli.main(["kb", "status"])
    assert "is not a clone" in capsys.readouterr().out


def test_a_domain_outside_the_knowledge_base_is_not_managed(world):
    config = world["configure"]()
    outside = world["tmp"] / "code" / "dom"
    outside.mkdir()
    text = (world["tmp"] / "config.toml").read_text(encoding="utf-8") + f'\n[[domains]]\nname = "loose"\npath = "{outside.as_posix()}"\n'
    (world["tmp"] / "config.toml").write_text(text, encoding="utf-8")
    config = load(world["tmp"] / "config.toml")
    assert [d.name for d in kb.managed(config)] == ["tools"]
    with pytest.raises(kb.KbError):
        kb.select(config, ["loose"])


def test_record_commits_and_pushes_under_auto_with_the_trailers(world):
    config = cloned(world, 'git = { commit = "auto", push = "auto" }')
    register = world["folder"] / "register.md"
    register.write_text("| NOTE-1 | first |\n| NOTE-2 | second |\n", encoding="utf-8")
    results = kb.record(config, [str(register)], "Add NOTE-2")
    assert all(r.ok for r in results), results
    message = sh("git", "log", "-1", "--format=%B", cwd=world["remote"])
    assert message.startswith("Add NOTE-2") and message.endswith(TRAILER)
    assert "NOTE-2" in sh("git", "show", "main:register.md", cwd=world["remote"])


def test_record_under_manual_stages_and_does_not_commit(world, capsys):
    config = cloned(world)
    register = world["folder"] / "register.md"
    register.write_text("changed\n", encoding="utf-8")
    assert cli.main(["kb", "record", str(register), "-m", "x"]) == 0
    assert "staged register.md" in capsys.readouterr().out
    assert sh("git", "diff", "--cached", "--name-only", cwd=world["folder"]) == "register.md"
    assert sh("git", "log", "--format=%s", cwd=world["folder"]) == "seed"


def test_record_refuses_a_path_outside_every_managed_domain_and_a_ignored_one(world):
    config = cloned(world, 'git = { commit = "auto", push = "auto" }')
    stray = world["tmp"] / "code" / "plan.md"
    stray.write_text("p\n", encoding="utf-8")
    (world["folder"] / ".gitignore").write_text("*.log\n", encoding="utf-8")
    ignored = world["folder"] / "run.log"
    ignored.write_text("x\n", encoding="utf-8")
    good = world["folder"] / "register.md"
    good.write_text("changed\n", encoding="utf-8")
    [outside] = kb.record(config, [str(stray)], "m")
    assert not outside.ok and "never commits or pushes a project's files" in outside.text
    [hidden] = kb.record(config, [str(ignored)], "m")
    assert not hidden.ok and "ignored" in hidden.text
    assert not all(r.ok for r in kb.record(config, [str(good), str(stray)], "m")), "one refused path stages nothing"
    assert sh("git", "diff", "--cached", "--name-only", cwd=world["folder"]) == ""


def test_pull_due_with_daily_follows_the_injected_clock(world):
    config = cloned(world, 'git = { pull = "daily" }')
    scopes = [config.domains["tools"]]
    assert [r.ok for r in kb.pull(config, scopes, due=True, clock=lambda: 1000.0)] == [True], "never pulled, so due"
    assert kb.pull(config, scopes, due=True, clock=lambda: 1000.0 + 2 * HOUR) == [], "not due after 2 hours"
    assert len(kb.pull(config, scopes, due=True, clock=lambda: 1000.0 + 25 * HOUR)) == 1
    manual = kb.pull(config, [replace(config.domains["tools"], git=GitPolicy(pull="manual"))], due=True, clock=lambda: 1e9)
    assert manual == [], "manual is never due"


def test_a_pull_that_cannot_fast_forward_is_reported_and_leaves_everything(world):
    config = cloned(world)
    second = world["tmp"] / "second"
    sh("git", "clone", str(world["remote"]), str(second), cwd=world["tmp"])
    (second / "other.md").write_text("remote side\n", encoding="utf-8")
    sh("git", "add", ".", cwd=second)
    sh("git", "commit", "-m", "remote", cwd=second)
    sh("git", "push", cwd=second)
    folder = world["folder"]
    (folder / "local.md").write_text("local side\n", encoding="utf-8")
    sh("git", "add", ".", cwd=folder)
    sh("git", "commit", "-m", "local", cwd=folder)
    (folder / "register.md").write_text("dirty\n", encoding="utf-8")
    head = sh("git", "rev-parse", "HEAD", cwd=folder)
    [result] = kb.pull(config, [config.domains["tools"]])
    assert not result.ok and result.text
    assert sh("git", "rev-parse", "HEAD", cwd=folder) == head and not (folder / "other.md").exists()
    assert (folder / "register.md").read_text(encoding="utf-8") == "dirty\n"
    assert kb.inspect(config, config.domains["tools"]).last_pull is None, "a failed pull is not recorded"


def test_push_auto_with_commit_manual_is_refused_at_load(world):
    with pytest.raises(ConfigError) as error:
        world["configure"]('git = { push = "auto" }')
    assert any("nothing would be pushed" in p for p in error.value.problems)


def test_an_unknown_policy_value_is_a_problem(world):
    with pytest.raises(ConfigError) as error:
        world["configure"]('git = { pull = "hourly" }')
    assert any("git.pull" in p for p in error.value.problems)


def test_context_pulls_what_is_due_and_no_pull_skips_it(world, capsys):
    config = cloned(world)
    second = world["tmp"] / "second"
    sh("git", "clone", str(world["remote"]), str(second), cwd=world["tmp"])
    (second / "new.md").write_text("new\n", encoding="utf-8")
    sh("git", "add", ".", cwd=second)
    sh("git", "commit", "-m", "new", cwd=second)
    sh("git", "push", cwd=second)
    code = str(world["tmp"] / "code")
    assert cli.main(["context", code, "--no-pull"]) == 0
    assert not (world["folder"] / "new.md").exists()
    assert cli.main(["context", code]) == 0
    assert (world["folder"] / "new.md").exists()
    assert kb.inspect(config, config.domains["tools"]).last_pull is not None
    capsys.readouterr()
    (world["folder"] / "register.md").write_text("dirty\n", encoding="utf-8")
    sh("git", "commit", "-am", "local", cwd=world["folder"])
    (second / "again.md").write_text("again\n", encoding="utf-8")
    sh("git", "add", ".", cwd=second)
    sh("git", "commit", "-m", "again", cwd=second)
    sh("git", "push", cwd=second)
    assert cli.main(["context", code]) == 0
    assert "pull of tools failed" in capsys.readouterr().err
