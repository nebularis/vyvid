# SPDX-License-Identifier: MIT
"""VYD-21: a repository named in the user's own configuration is trusted while its vyvid.toml is the committed one,
with no terminal and no hash record, and the automatic build says why it made no embeddings and retries once a while.
Real git repositories under a temporary folder, no network, a stand-in model, and nothing of the real home."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from test_ask import built  # noqa: F401  a fixture
from test_index_core import Words
from test_project_file import BASE, commit, no_configuration, put, quiet_git, repo, sh  # noqa: F401  the last two are autouse fixtures
from vyvid import ask, cli, embed
from vyvid import build as builder
from vyvid import config as configuration
from vyvid.config import ConfigError, load

ORIGIN = "https://github.com/example/project"
LISTED = "github.com/example/project"


def own(text: str) -> Path:
    """Write the user's own configuration."""
    path = configuration.own_config()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def grant(*repositories: str) -> Path:
    return own("[framework]\ntrusted_repositories = [" + ", ".join(f'"{r}"' for r in repositories) + "]\n")


def cloned(tmp_path: Path, remote: str = "origin", url: str = ORIGIN, **kwargs) -> Path:
    root = repo(tmp_path, **kwargs)
    if remote:
        sh(root, "remote", "add", remote, url)
    return root


# ---- The grant ----------------------------------------------------------------------------------


@pytest.mark.real_trust
def test_a_listed_origin_and_the_committed_bytes_are_trusted_with_no_record_and_no_terminal(tmp_path):
    root = cloned(tmp_path)
    assert not configuration.file_trusted(root / "vyvid.toml")
    grant(LISTED)
    assert configuration.file_trusted(root / "vyvid.toml")
    assert not configuration.trust_file().exists(), "nothing was recorded"


@pytest.mark.real_trust
def test_an_uncommitted_edit_lapses_the_trust_and_committing_it_restores_it(tmp_path):
    root = cloned(tmp_path)
    grant(LISTED)
    put(root, "vyvid.toml", (root / "vyvid.toml").read_text(encoding="utf-8") + "\n# edited\n")
    assert not configuration.file_trusted(root / "vyvid.toml")
    commit(root)
    assert configuration.file_trusted(root / "vyvid.toml")


@pytest.mark.real_trust
def test_an_origin_that_is_not_listed_and_a_listed_upstream_alone_are_not_trusted(tmp_path):
    grant("github.com/example/other")
    assert not configuration.file_trusted(cloned(tmp_path, "origin") / "vyvid.toml")
    grant(LISTED)
    fork = cloned(tmp_path, "upstream", name="fork")
    sh(fork, "remote", "add", "origin", "https://github.com/someone/project")
    assert not configuration.file_trusted(fork / "vyvid.toml")


@pytest.mark.real_trust
def test_no_origin_and_no_repository_are_not_trusted_and_raise_nothing(tmp_path):
    grant(LISTED)
    assert not configuration.file_trusted(cloned(tmp_path, "", name="local") / "vyvid.toml")
    loose = put(tmp_path / "loose", "vyvid.toml", BASE)
    assert not configuration.file_trusted(loose)
    assert not configuration.file_trusted(tmp_path / "nothing" / "vyvid.toml")


@pytest.mark.real_trust
def test_only_the_users_own_configuration_can_grant_it(tmp_path, monkeypatch, capsys):
    root = cloned(tmp_path)
    elsewhere = put(tmp_path, "other.toml", f'[framework]\ntrusted_repositories = ["{LISTED}"]\n')
    monkeypatch.setenv("VYVID_CONFIG", str(elsewhere))
    assert not configuration.file_trusted(root / "vyvid.toml")
    assert cli.main(["config", str(root)]) == 0
    said = capsys.readouterr().out
    assert f"trusted repositories: {LISTED}" in said and "NOTE: trusted_repositories is ignored here" in said
    assert "not trusted" in said


@pytest.mark.real_trust
def test_a_vyvid_toml_cannot_set_the_key(tmp_path):
    from vyvid.config import read_project_file
    root = repo(tmp_path, toml=BASE.replace("visibility", f'trusted_repositories = ["{LISTED}"]\nvisibility'))
    _, problems = read_project_file(root / "vyvid.toml")
    assert any("trusted_repositories" in p for p in problems)
    root = repo(tmp_path, "second", toml=BASE + f'\n[framework]\ntrusted_repositories = ["{LISTED}"]\n')
    _, problems = read_project_file(root / "vyvid.toml")
    assert any("framework" in p for p in problems)
    sh(root, "remote", "add", "origin", ORIGIN)
    assert not configuration.file_trusted(root / "vyvid.toml"), "no grant exists in the user's own configuration"


def test_a_malformed_grant_or_an_unnormalised_entry_is_a_problem(tmp_path):
    for text, said in (('trusted_repositories = "github.com/example/project"', "must be a list of strings"),
                       ("trusted_repositories = [1]", "must be a list of strings"),
                       (f'trusted_repositories = ["{ORIGIN}.git"]', f"must be written as {LISTED}"),
                       ('trusted_repositories = ["GitHub.com/Example/Project"]', f"must be written as {LISTED}")):
        with pytest.raises(ConfigError) as caught:
            load(put(tmp_path, "c.toml", f"[framework]\n{text}\n"))
        assert any(said in p for p in caught.value.problems), caught.value.problems
    assert load(put(tmp_path, "ok.toml", f'[framework]\ntrusted_repositories = ["{LISTED}"]\n')).trusted_repositories == (LISTED,)


@pytest.mark.real_trust
def test_a_malformed_own_configuration_grants_nothing(tmp_path):
    root = cloned(tmp_path)
    own(f'[framework]\ntrusted_repositories = [1, "{LISTED}"]\n')
    assert not configuration.file_trusted(root / "vyvid.toml")
    own("[framework\n")
    assert not configuration.file_trusted(root / "vyvid.toml")


@pytest.mark.real_trust
def test_a_real_command_with_no_terminal_trusts_the_listed_repository_and_trust_still_refuses(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    env = {k: v for k, v in os.environ.items() if not k.startswith(("VYVID", "XDG_"))}
    env |= {"HOME": str(home), "XDG_CONFIG_HOME": str(home / "xdg" / "config"), "XDG_STATE_HOME": str(home / "xdg" / "state"),
            "XDG_DATA_HOME": str(home / "xdg" / "data"), "XDG_CACHE_HOME": str(home / "xdg" / "cache"), "USERPROFILE": str(home),
            "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}

    def run(*args, cwd):
        return subprocess.run([sys.executable, "-c", "import sys; from vyvid.cli import main; sys.exit(main(sys.argv[1:]))", *args],
                              stdin=subprocess.DEVNULL, capture_output=True, text=True, env=env, cwd=cwd)

    # Where platformdirs puts the configuration depends on the platform, so ask it under the same environment.
    folder = subprocess.run([sys.executable, "-c", "import platformdirs; print(platformdirs.user_config_path('vyvid'))"],
                            capture_output=True, text=True, env=env, check=True).stdout.strip()
    domain = tmp_path / "domain"
    domain.mkdir()
    (Path(folder) / "config.toml").parent.mkdir(parents=True)
    (Path(folder) / "config.toml").write_text(
        f'[framework]\ntrusted_repositories = ["{LISTED}"]\n\n[[domains]]\nname = "shared"\npath = "{domain.as_posix()}"\ntrust = "own"\n', encoding="utf-8")
    root = cloned(tmp_path)
    for args in (("config",), ("context",), ("check", "skills")):
        done = run(*args, cwd=root)
        assert done.returncode == 0, (args, done.stdout, done.stderr)
        assert "not trusted" not in done.stdout + done.stderr, (args, done.stdout, done.stderr)
    said = run("config", cwd=root).stdout
    assert f"trusted repositories: {LISTED}" in said and "trusted through trusted_repositories" in said
    refused = run("trust", cwd=root)
    assert refused.returncode == 1 and "a person must run vyd trust" in refused.stderr
    put(root, "vyvid.toml", (root / "vyvid.toml").read_text(encoding="utf-8") + "\n# edited\n")
    assert "not trusted" in run("config", cwd=root).stdout


# ---- The automatic build ------------------------------------------------------------------------


def test_the_automatic_build_says_why_it_made_no_embeddings(built, capsys, monkeypatch):  # noqa: F811
    def unavailable(*_args, **_kwargs):
        raise embed.Unavailable("the model could not be fetched")

    monkeypatch.setattr(builder.vectors, "build", unavailable)
    (built.ask.directory / "built-for").unlink()
    ask.open_stack(built.config, built.tmp / "code", model=Words())
    said = capsys.readouterr()
    assert "no embeddings, so nothing can be ranked by meaning: the model could not be fetched" in said.err
    assert "no embeddings" not in said.out


def test_a_store_without_vectors_is_rebuilt_for_a_ranking_question_only_after_the_retry_wait(built):  # noqa: F811
    a = ask.open_stack(built.config, built.tmp / "code", model=Words())
    stamp = a.directory / "built-from"
    (a.directory / embed.VECTORS).unlink()
    assert not ask.stale(a, ranking=True), "a build just made is not retried"
    old = float(stamp.read_text(encoding="utf-8")) - ask.RETRY_EMBEDDING - 60
    os.utime(stamp, (old, old))
    assert ask.stale(a, ranking=True)
    assert not ask.stale(a), "a question that does not rank leaves it alone"
    (a.directory / embed.VECTORS).write_bytes(b"")
    assert not ask.stale(a, ranking=True), "a store with vectors is not retried"


def test_a_build_told_not_to_embed_is_not_undone_by_a_later_question(built):  # noqa: F811
    builder.build(built.config, built.project, model=Words(), embed=False)
    a = ask.open_stack(built.config, built.tmp / "code", model=Words())
    stamp = a.directory / "built-from"
    os.utime(stamp, (1, 1))
    assert not (a.directory / embed.VECTORS).exists() and not ask.stale(a, ranking=True)
    builder.build(built.config, built.project, model=Words())
    assert (a.directory / embed.VECTORS).exists() and not (a.directory / builder.NO_VECTORS).exists()
