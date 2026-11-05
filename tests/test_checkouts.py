# SPDX-License-Identifier: MIT
"""VYD-6c: a linked checkout is answered from its own files and has its own store, over real git
repositories and worktrees under a temporary folder, with a stand-in model and no network."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from test_index_core import Words
from vyvid import ask, cli
from vyvid import build as builder
from vyvid.config import load
from vyvid.resolve import bind_in

CONFIG = """
[framework]
store = "STORE"

[[projects]]
name = "proj"
code = "CODE"
DOCS
[projects.match]
remote = "github.com/acme/proj"

[projects.families]
STD = { defined = "docs:standards.md", type = "standard" }
"""

HEAD = "| ID | Claim | Pointer |\n|---|---|---|\n"


def row(n: int, claim: str) -> str:
    return f"| STD-{n} | {claim} | docs/standards.md |\n"


def git(folder: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(folder), *args], check=True, capture_output=True)


def commit(folder: Path, text: str, message: str = "x") -> None:
    (folder / "docs" / "standards.md").write_text(text, encoding="utf-8")
    git(folder, "add", "-A", "docs")
    git(folder, "commit", "-m", message)


@pytest.fixture(autouse=True)
def quiet_git(monkeypatch):
    for key, value in {"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1", "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com",
                       "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com"}.items():
        monkeypatch.setenv(key, value)


class Repo:
    """A main checkout holding STD-1, a configuration whose project is bound to it, and helpers."""

    def __init__(self, tmp_path, monkeypatch, docs=""):
        self.tmp, self.code = tmp_path, tmp_path / "main"
        (self.code / "docs").mkdir(parents=True)
        git(self.code, "init", "-b", "main")
        git(self.code, "remote", "add", "origin", "git@github.com:acme/proj.git")
        commit(self.code, HEAD + row(1, "A ledger is kept per key."))
        self.config_path = tmp_path / "config.toml"
        self.config_path.write_text(CONFIG.replace("STORE", (tmp_path / "idx").as_posix()).replace("CODE", self.code.as_posix()).replace("DOCS", docs), encoding="utf-8")
        monkeypatch.setenv("VYVID_CONFIG", str(self.config_path))
        self.config = load(self.config_path)

    def worktree(self, where: Path, branch: str, claim: str) -> Path:
        git(self.code, "worktree", "add", "-b", branch, str(where))
        commit(where, HEAD + row(1, "A ledger is kept per key.") + row(2, claim), f"on {branch}")
        return where

    def ids(self, folder: Path) -> set[str]:
        return {r["id"] for r in ask.candidates(self.asker(folder), set(), set(), set())}

    def asker(self, folder: Path) -> ask.Asker:
        return ask.open_stack(self.config, folder, model=Words())


def test_a_worktree_outside_the_code_folder_is_answered_from_its_own_files(tmp_path, monkeypatch):
    repo = Repo(tmp_path, monkeypatch)
    wt = repo.worktree(tmp_path / "wt" / "x", "feat", "A graph is slow.")
    commit(repo.code, HEAD + row(1, "A ledger is kept per key.") + row(3, "Minting is slow."))
    assert repo.ids(wt) == {"STD-1", "STD-2"}, "the row only the branch has, and not the one only main has"
    assert repo.ids(repo.code) == {"STD-1", "STD-3"}, "and the main checkout does not see the branch's row"


def test_a_worktree_anywhere_is_found_with_no_remote_configured(tmp_path, monkeypatch):
    """Only the code folder is configured, and the worktree sits far from it, so the repository they
    share is all that ties them."""
    repo = Repo(tmp_path, monkeypatch)
    text = repo.config_path.read_text(encoding="utf-8")
    bare = "\n".join(l for l in text.split("\n") if not l.startswith(("[projects.match]", "remote =")))
    repo.config_path.write_text(bare, encoding="utf-8")
    repo.config = load(repo.config_path)
    assert not repo.config.projects["proj"].remotes
    wt = repo.worktree(tmp_path / "far" / "away" / "x", "feat", "A graph is slow.")
    (wt / "docs" / "deep").mkdir()
    assert repo.ids(wt) == {"STD-1", "STD-2"}
    assert bind_in(repo.config, wt / "docs" / "deep")[1].checkout == wt.resolve(), "from a folder inside it too"


def test_another_repository_with_no_remote_binds_to_no_project(tmp_path, monkeypatch):
    repo = Repo(tmp_path, monkeypatch)
    other = tmp_path / "other"
    other.mkdir()
    git(other, "init", "-b", "main")
    assert bind_in(repo.config, other)[1] is None


def test_a_worktree_nested_in_the_code_folder_is_answered_from_its_own_files(tmp_path, monkeypatch):
    repo = Repo(tmp_path, monkeypatch)
    wt = repo.worktree(repo.code / ".claude" / "worktrees" / "x", "feat", "A graph is slow.")
    assert repo.ids(wt / "docs") == {"STD-1", "STD-2"}, "bound by the code folder's path, from a folder inside the worktree"
    assert repo.ids(repo.code) == {"STD-1"}


def test_each_checkout_has_its_own_store_and_neither_overwrites_the_other(tmp_path, monkeypatch):
    repo = Repo(tmp_path, monkeypatch)
    wt = repo.worktree(tmp_path / "wt" / "x", "feat", "A graph is slow.")
    main, other = repo.asker(repo.code), repo.asker(wt)
    assert main.directory == tmp_path / "idx", "the main checkout keeps the path it always had"
    assert other.directory.parent == tmp_path / "idx" / "checkouts" and other.directory.name.startswith("x-")
    assert (main.directory / "store").is_dir() and (other.directory / "store").is_dir()
    assert repo.ids(repo.code) == {"STD-1"} and repo.ids(wt) == {"STD-1", "STD-2"}, "asked again, each still answers its own"
    assert (other.directory / builder.ROOT_FILE).read_text(encoding="utf-8").strip() == str(wt.resolve())


def test_a_build_in_one_worktree_does_not_make_another_read_as_fresh(tmp_path, monkeypatch):
    repo = Repo(tmp_path, monkeypatch)
    wt = repo.worktree(tmp_path / "wt" / "x", "feat", "A graph is slow.")
    main, other = repo.asker(repo.code), repo.asker(wt)
    stamp = float((other.directory / "built-from").read_text(encoding="utf-8"))
    os.utime(wt / "docs" / "standards.md", (stamp + 100, stamp + 100))
    assert ask.stale(repo.asker(wt)) and not ask.stale(main), "an edit in the worktree stales the worktree's store alone"


def test_the_embedding_cache_is_shared_so_a_checkout_embeds_only_what_is_new(tmp_path, monkeypatch):
    repo = Repo(tmp_path, monkeypatch)
    wt = repo.worktree(tmp_path / "wt" / "x", "feat", "A graph is slow.")
    repo.asker(repo.code)
    model = Words()
    ask.open_stack(repo.config, wt, model=model)
    assert sum(model.calls) == 1, "the one row the branch added, not the rows main had"


def test_the_logs_stay_with_the_project_and_not_the_checkout(tmp_path, monkeypatch):
    repo = Repo(tmp_path, monkeypatch)
    wt = repo.worktree(tmp_path / "wt" / "x", "feat", "A graph is slow.")
    a = repo.asker(wt)
    ask.log_ask(a, "find", "ledger", 0.9, ["STD-1"])
    ask.log_miss(a, "find nothing")
    assert (tmp_path / "idx" / "logs" / "proj" / "asks.log").exists() and (tmp_path / "idx" / "logs" / "proj" / "misses.log").exists()
    assert not (a.directory / "asks.log").exists()


def test_a_different_repository_nested_in_the_code_folder_is_not_rebased(tmp_path, monkeypatch):
    repo = Repo(tmp_path, monkeypatch)
    nested = repo.code / "vendor" / "other"
    (nested / "docs").mkdir(parents=True)
    git(nested, "init", "-b", "main")
    commit(nested, HEAD + row(9, "Another repository's row."))
    config, project = bind_in(repo.config, nested)
    assert project.checkout is None and project.code == repo.code
    assert repo.ids(nested) == {"STD-1"}


def test_a_folder_outside_git_keeps_the_project_as_configured(tmp_path, monkeypatch):
    repo = Repo(tmp_path, monkeypatch)
    plain = tmp_path / "plain"
    (plain / "docs").mkdir(parents=True)
    (plain / "docs" / "standards.md").write_text(HEAD + row(5, "No git here."), encoding="utf-8")
    text = repo.config_path.read_text(encoding="utf-8").replace(repo.code.as_posix(), plain.as_posix())
    repo.config_path.write_text(text, encoding="utf-8")
    repo.config = load(repo.config_path)
    config, project = bind_in(repo.config, plain)
    assert project.checkout is None and config is repo.config
    assert repo.ids(plain) == {"STD-5"}


def test_a_private_documents_folder_outside_the_code_folder_stays_where_it_is(tmp_path, monkeypatch):
    docs = tmp_path / "private-docs"
    docs.mkdir()
    (docs / "standards.md").write_text(HEAD + row(7, "Private."), encoding="utf-8")
    repo = Repo(tmp_path, monkeypatch, docs=f'docs = "{docs.as_posix()}"')
    wt = repo.worktree(tmp_path / "wt" / "x", "feat", "A graph is slow.")
    config, project = bind_in(repo.config, wt)
    assert project.code == wt and project.docs == docs and project.families["STD"].defined == docs / "standards.md"
    assert config.scope("proj") is project and repo.config.projects["proj"].code == repo.code, "the loaded configuration is not changed"


def test_context_says_which_checkout_it_answers_from(tmp_path, monkeypatch, capsys):
    repo = Repo(tmp_path, monkeypatch)
    wt = repo.worktree(tmp_path / "wt" / "x", "feat", "A graph is slow.")
    assert cli.main(["context", str(repo.code), "--no-pull"]) == 0
    assert "checkout:" not in capsys.readouterr().out
    assert cli.main(["context", str(wt), "--no-pull"]) == 0
    out = capsys.readouterr().out
    assert f"checkout: answering from {wt.resolve()}" in out and f"not the configured code folder {repo.code}" in out


def test_prune_removes_only_the_store_of_a_removed_worktree(tmp_path, monkeypatch, capsys):
    repo = Repo(tmp_path, monkeypatch)
    gone = repo.worktree(tmp_path / "wt" / "gone", "a", "A graph is slow.")
    kept = repo.worktree(tmp_path / "wt" / "kept", "b", "Minting is slow.")
    stores = {n: repo.asker(p).directory for n, p in (("gone", gone), ("kept", kept), ("main", repo.code))}
    ask.log_miss(repo.asker(gone), "find lost")
    git(repo.code, "worktree", "remove", "--force", str(gone))
    assert cli.main(["store", "prune", "--dry-run"]) == 0
    assert f"would remove {stores['gone']}" in capsys.readouterr().out and stores["gone"].exists()
    assert cli.main(["store", "prune"]) == 0
    assert f"removed {stores['gone']}" in capsys.readouterr().out
    assert not stores["gone"].exists() and stores["kept"].exists() and (stores["main"] / "store").exists()
    assert "find lost" in (tmp_path / "idx" / "logs" / "proj" / "misses.log").read_text(encoding="utf-8"), "the gaps a removed worktree found are kept"
    assert cli.main(["store", "prune"]) == 0 and "no checkout store is left behind" in capsys.readouterr().out
