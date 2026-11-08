# SPDX-License-Identifier: MIT
"""GD-1 to GD-4: the guard that keeps a user's private terms out of public repositories. Real git repositories under a
temporary folder, invented terms, and the user's own global git configuration replaced by a file of the test's."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from test_checkouts import quiet_git  # noqa: F401  an autouse fixture
from test_project_file import commit, configure, put, sh
from vyvid import guard
from vyvid.config import ConfigError, load

CONFIG = """[framework.guard]
domains = ["priv"]
watch_owners = ["github.com/example-org", "Github.com/Other-Org"]

[[domains]]
name = "priv"
path = "TMP/priv"
visibility = "private"
"""
FILES = {
    "upstreams": "# repositories that are public\ngithub.com/example-org/open\ngithub.com/example-org/open-two\n",
    "private-upstreams": "github.com/example-org/closed\n",
    "guard/deny-terms": "# everywhere\n\\bfoobar\\b\n!docs/legal/**\n",
    "guard/public-deny-terms": "\\bsecret-project\\b\nquux[\\s-]+corp\n",
    "guard/warn-terms": "example tripwire\n",
    "guard/never-track": ".local/**\n",
    "guard/sensitive-paths": "github.com/example-org/open: ontology/applied/**\nsketches/**\n",
}


@pytest.fixture(autouse=True)
def no_configuration(tmp_path, monkeypatch):
    monkeypatch.setenv("VYVID_CONFIG", str(tmp_path / "absent.toml"))


def priv(tmp_path: Path, files: dict | None = None) -> Path:
    root = tmp_path / "priv"
    root.mkdir(parents=True, exist_ok=True)
    for name, text in (FILES if files is None else files).items():
        put(root, name, text)
    return root


def guarded(tmp_path, monkeypatch, config: str = CONFIG, files: dict | None = None):
    priv(tmp_path, files)
    configure(tmp_path, monkeypatch, config)
    return load()


def repo(tmp_path: Path, name: str, remote: str | None) -> Path:
    root = tmp_path / name
    root.mkdir(parents=True)
    sh(root, "init", "-b", "main")
    if remote:
        sh(root, "remote", "add", "origin", remote)
    put(root, "README.md", "hello\n")
    commit(root)
    return root


# ---- GD-1: the configuration, the lists and the class of a repository --------------------------


def test_the_guard_settings_are_read_from_the_framework_table(tmp_path, monkeypatch):
    config = guarded(tmp_path, monkeypatch)
    assert config.guard.domains == ("priv",)
    assert config.guard.watch_owners == ("github.com/example-org", "github.com/other-org"), "owners are normalised"
    assert guarded(tmp_path, monkeypatch, "[framework]\n").guard.domains == (), "no guard is configured by default"


@pytest.mark.parametrize("text,why", [
    ('[framework.guard]\ndomains = ["nope"]\n', "nope"),
    ('[framework.guard]\ncolour = 1\n', "colour"),
    ('[framework.guard]\nwatch_owners = ["not an owner"]\n', "host/owner"),
    ('[framework.guard]\ndomains = "priv"\n', "list"),
])
def test_a_guard_table_that_cannot_be_used_is_refused_with_its_reason(tmp_path, monkeypatch, text, why):
    priv(tmp_path)
    configure(tmp_path, monkeypatch, text + '\n[[domains]]\nname = "priv"\npath = "TMP/priv"\n')
    with pytest.raises(ConfigError) as error:
        load()
    assert any(why in p for p in error.value.problems), error.value.problems


def test_the_lists_come_from_the_named_domains_with_their_line_numbers_and_skips(tmp_path, monkeypatch):
    lists = guard.read_lists(guarded(tmp_path, monkeypatch))
    assert lists.public == {"github.com/example-org/open", "github.com/example-org/open-two"}
    assert lists.private == {"github.com/example-org/closed"}
    assert [(e.source, e.number) for e in lists.deny] == [("deny-terms", 2)]
    assert [(e.source, e.number) for e in lists.public_deny] == [("public-deny-terms", 1), ("public-deny-terms", 2)]
    assert lists.skips == ("docs/legal/**",) and lists.never_track == (".local/**",)
    assert lists.sensitive == (("github.com/example-org/open", "ontology/applied/**"), (None, "sketches/**"))
    assert lists.deny[0].pattern.search("a FOOBAR b") and not lists.deny[0].pattern.search("foobarbaz")


def test_a_domain_root_supplies_the_repository_lists_when_it_has_no_guard_folder(tmp_path, monkeypatch):
    files = {k: v for k, v in FILES.items() if k.startswith("guard/") is False}
    lists = guard.read_lists(guarded(tmp_path, monkeypatch, files=files))
    assert lists.public and lists.deny == []


@pytest.mark.parametrize("remote,kind", [
    ("git@github.com:example-org/open.git", "public"),
    ("https://github.com/Example-Org/OPEN-two.git", "public"),
    ("git@github.com:example-org/closed.git", "private"),
    ("git@github.com:example-org/brand-new.git", "unclassified"),
    ("git@github.com:other-org/anything", "unclassified"),
    ("git@github.com:somebody/else.git", "none"),
    (None, "none"),
])
def test_a_repository_is_classified_by_its_remotes(tmp_path, monkeypatch, remote, kind):
    config = guarded(tmp_path, monkeypatch)
    folder = repo(tmp_path, "r", remote)
    assert guard.classify(config, guard.read_lists(config), folder).kind == kind


def test_a_repository_listed_both_ways_is_public_and_an_unconfigured_guard_classifies_nothing(tmp_path, monkeypatch):
    config = guarded(tmp_path, monkeypatch)
    folder = repo(tmp_path, "r", "git@github.com:example-org/open.git")
    sh(folder, "remote", "add", "second", "git@github.com:example-org/closed.git")
    assert guard.classify(config, guard.read_lists(config), folder).kind == "public"
    plain = guarded(tmp_path / "x", monkeypatch, "[framework]\n")
    assert guard.classify(plain, guard.read_lists(plain), folder).kind == "none"


# ---- GD-2: the checks ---------------------------------------------------------------------------


def lists_of(tmp_path, monkeypatch, files=None):
    return guard.read_lists(guarded(tmp_path, monkeypatch, files=files))


def hits(findings):
    return [(f.path, f.line, f.what, f.warn) for f in findings]


def test_terms_apply_by_class_and_a_finding_never_holds_the_term(tmp_path, monkeypatch):
    lists = lists_of(tmp_path, monkeypatch)
    lines = [("a.md", 1, "the Secret-Project is here"), ("a.md", 2, "a foobar b"), ("a.md", 3, "an example tripwire"), ("b.md", 4, "QUUX  corp")]
    public = guard.check_lines(lists, "public", lines)
    assert hits(public) == [("a.md", 1, "matches public-deny-terms:1", False), ("a.md", 2, "matches deny-terms:2", False),
                            ("a.md", 3, "matches warn-terms:1", True), ("b.md", 4, "matches public-deny-terms:2", False)]
    private = guard.check_lines(lists, "private", lines)
    assert hits(private) == [("a.md", 2, "matches deny-terms:2", False)], "public-only terms and warnings leave a private repository alone"
    assert not any("secret" in str(f).lower() or "foobar" in str(f).lower() for f in public)


def test_a_skip_glob_leaves_a_path_alone(tmp_path, monkeypatch):
    lists = lists_of(tmp_path, monkeypatch)
    assert guard.check_lines(lists, "public", [("docs/legal/notice.md", 1, "foobar"), ("docs/other.md", 1, "foobar")]) == [
        guard.Finding("docs/other.md", 1, "matches deny-terms:2")]


def token() -> str:
    return "ghp_" + "a" * 36


def test_built_in_patterns_guard_paths_everywhere_and_secrets_in_every_class(tmp_path, monkeypatch):
    lists = lists_of(tmp_path, monkeypatch)
    home = "see " + "/" + "Users" + "/someone/work/x"
    lines = [("a", 1, home), ("a", 2, "token " + token()), ("a", 3, "-----BEGIN RSA " + "PRIVATE KEY-----"), ("a", 4, "/" + "Users" + "/example/x")]
    assert [f.what for f in guard.check_lines(lists, "public", lines)] == [
        "matches the built-in pattern home-path", "matches the built-in pattern token", "matches the built-in pattern private-key"]
    assert [f.what for f in guard.check_lines(lists, "private", lines)] == ["matches the built-in pattern token", "matches the built-in pattern private-key"]


def test_an_allow_file_switches_a_built_in_pattern_off(tmp_path, monkeypatch):
    lists = lists_of(tmp_path, monkeypatch, {**FILES, "guard/allow": "token\n"})
    assert guard.check_lines(lists, "public", [("a", 1, token())]) == []


def test_a_message_is_checked_without_its_comment_lines_or_skips(tmp_path, monkeypatch):
    lists = lists_of(tmp_path, monkeypatch)
    found = guard.check_message(lists, "public", "Fix a thing\n\n# secret-project in a comment\nabout secret-project here\n")
    assert hits(found) == [("the commit message", 3, "matches public-deny-terms:1", False)]


def test_a_path_that_is_never_tracked_and_a_sensitive_path_without_a_trailer_are_found(tmp_path, monkeypatch):
    lists = lists_of(tmp_path, monkeypatch)
    repo = "github.com/example-org/open"
    assert [f.path for f in guard.check_paths(lists, "public", repo, [".local/note.md", "src/a.py"], None)] == [".local/note.md"]
    sensitive = ["ontology/applied/x/y.ttl", "src/a.py"]
    no_trailer = guard.check_paths(lists, "public", repo, sensitive, "Add x\n")
    assert len(no_trailer) == 1 and "Placement trailer" in no_trailer[0].what and no_trailer[0].path == "ontology/applied/x/y.ttl"
    assert guard.check_paths(lists, "public", repo, sensitive, "Add x\n\nPlacement: T1, public applied\n") == []
    assert guard.check_paths(lists, "private", repo, sensitive, "Add x\n") == [], "a private repository needs no placement"
    assert guard.check_paths(lists, "public", "github.com/example-org/open-two", ["ontology/applied/x"], "x\n") == [], "a repository-specific glob is that repository's"
    assert len(guard.check_paths(lists, "public", "github.com/example-org/open-two", ["sketches/a.md"], "x\n")) == 1, "a bare glob is every repository's"


# ---- GD-3: the hooks, their install and the chain -----------------------------------------------


@pytest.fixture
def machine(tmp_path, monkeypatch):
    """A git configuration of the test's own and a ``vyd`` on the path that runs this checkout's code."""
    import os
    import sys

    git_config = tmp_path / "gitconfig"
    git_config.write_text("[user]\n\tname = t\n\temail = t@example.com\n", encoding="utf-8")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(git_config))
    bin_ = tmp_path / "bin"
    bin_.mkdir()
    script = bin_ / "vyd"
    script.write_text(f'#!/bin/sh\nexec "{sys.executable}" -c "import sys; from vyvid.cli import main; raise SystemExit(main(sys.argv[1:]))" "$@"\n', encoding="utf-8")
    script.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_}{os.pathsep}{os.environ['PATH']}")
    return git_config


def run(folder: Path, *args: str, **env) -> subprocess.CompletedProcess:
    import os

    return subprocess.run(["git", "-C", str(folder), *args], capture_output=True, text=True, env={**os.environ, **env})


def installed(tmp_path, monkeypatch, machine):
    config = guarded(tmp_path, monkeypatch)
    assert guard.hooks_state() == "absent"
    assert guard.install_hooks(False) == 0 and guard.hooks_state() == "installed"
    return config


def test_install_writes_a_shim_for_every_client_hook_and_leaves_another_hookspath_alone(tmp_path, monkeypatch, machine):
    installed(tmp_path, monkeypatch, machine)
    assert {p.name for p in guard.hook_dir().iterdir()} == set(guard.ALL_HOOKS)
    assert "vyd guard hook" in (guard.hook_dir() / "pre-push").read_text() and "vyd guard" not in (guard.hook_dir() / "post-merge").read_text()
    subprocess.run(["git", "config", "--global", "core.hooksPath", "/elsewhere"], check=True)
    assert guard.hooks_state() == "other" and guard.install_hooks(False) == 1
    assert subprocess.run(["git", "config", "--global", "--get", "core.hooksPath"], capture_output=True, text=True).stdout.strip() == "/elsewhere"


def test_a_dry_run_installs_nothing(tmp_path, monkeypatch, machine):
    guarded(tmp_path, monkeypatch)
    assert guard.install_hooks(True) == 0 and guard.hooks_state() == "absent" and not guard.hook_dir().exists()


def test_a_commit_that_holds_a_term_stops_and_a_clean_one_goes_through(tmp_path, monkeypatch, machine):
    installed(tmp_path, monkeypatch, machine)
    folder = repo(tmp_path, "open", "git@github.com:example-org/open.git")
    put(folder, "a.md", "about secret-project\n")
    run(folder, "add", "-A")
    done = run(folder, "commit", "-m", "Add a")
    assert done.returncode != 0 and "vyd guard" in done.stderr and "a.md:1" in done.stderr and "Do not bypass" in done.stderr
    assert "secret-project" not in done.stderr.lower(), "the log never repeats the term"
    put(folder, "a.md", "about nothing\n")
    run(folder, "add", "-A")
    assert run(folder, "commit", "-m", "Add a").returncode == 0


def test_a_message_that_holds_a_term_and_a_sensitive_path_without_a_trailer_stop_the_commit(tmp_path, monkeypatch, machine):
    installed(tmp_path, monkeypatch, machine)
    folder = repo(tmp_path, "open", "git@github.com:example-org/open.git")
    put(folder, "a.md", "fine\n")
    run(folder, "add", "-A")
    assert run(folder, "commit", "-m", "Mention secret-project").returncode != 0
    put(folder, "sketches/x.md", "fine\n")
    run(folder, "add", "-A")
    done = run(folder, "commit", "-m", "Add a sketch")
    assert done.returncode != 0 and "Placement trailer" in done.stderr
    assert run(folder, "commit", "-m", "Add a sketch", "-m", "Placement: T1, public applied").returncode == 0


def test_a_private_repository_only_meets_the_terms_that_apply_everywhere(tmp_path, monkeypatch, machine):
    installed(tmp_path, monkeypatch, machine)
    folder = repo(tmp_path, "closed", "git@github.com:example-org/closed.git")
    put(folder, "a.md", "about secret-project\n")
    run(folder, "add", "-A")
    assert run(folder, "commit", "-m", "Add a").returncode == 0
    put(folder, "b.md", "about foobar\n")
    run(folder, "add", "-A")
    assert run(folder, "commit", "-m", "Add b").returncode != 0


def test_an_unlisted_repository_under_a_watched_owner_fails_closed_and_an_unwatched_one_is_left_alone(tmp_path, monkeypatch, machine):
    new = repo(tmp_path, "new", "git@github.com:example-org/brand-new.git")
    other = repo(tmp_path, "other", "git@github.com:somebody/else.git")
    installed(tmp_path, monkeypatch, machine)
    put(new, "a.md", "fine\n")
    run(new, "add", "-A")
    done = run(new, "commit", "-m", "x")
    assert done.returncode != 0 and "neither list" in done.stderr
    put(other, "a.md", "secret-project foobar\n")
    run(other, "add", "-A")
    assert run(other, "commit", "-m", "x").returncode == 0


def test_the_maintainers_skip_passes_and_is_logged_with_its_reason(tmp_path, monkeypatch, machine):
    import os

    installed(tmp_path, monkeypatch, machine)
    folder = repo(tmp_path, "open", "git@github.com:example-org/open.git")
    put(folder, "a.md", "about secret-project\n")
    run(folder, "add", "-A")
    assert run(folder, "commit", "-m", "Add a", "-q", **{guard.SKIP_ENV: "a quoted source, reviewed"}).returncode == 0
    log = (Path(os.environ["XDG_STATE_HOME"]) / "vyvid" / "guard-skips.log").read_text()
    assert "a quoted source, reviewed" in log and "pre-commit" in log and "public" in log


def test_a_push_is_checked_so_a_commit_made_with_no_verify_is_still_stopped(tmp_path, monkeypatch, machine):
    installed(tmp_path, monkeypatch, machine)
    folder = repo(tmp_path, "open", "git@github.com:example-org/open.git")
    bare = tmp_path / "bare.git"
    subprocess.run(["git", "init", "-q", "--bare", str(bare)], check=True)
    run(folder, "remote", "add", "elsewhere", str(bare))
    put(folder, "a.md", "about secret-project\n")
    run(folder, "add", "-A")
    assert run(folder, "commit", "-n", "-m", "Add a").returncode == 0
    done = run(folder, "push", "elsewhere", "main")
    assert done.returncode != 0 and "vyd guard" in done.stderr and "a.md:1" in done.stderr
    assert "secret-project" not in done.stderr.lower()
    put(folder, "a.md", "about nothing\n")
    run(folder, "add", "-A")
    run(folder, "commit", "-n", "-m", "Fix a")
    assert run(folder, "push", "elsewhere", "main").returncode != 0, "the earlier commit is still in the push"
    assert run(folder, "push", "elsewhere", "main", **{guard.SKIP_ENV: "reviewed"}).returncode == 0


def test_a_repositorys_own_hooks_still_run_after_the_guard_and_may_stop_the_commit(tmp_path, monkeypatch, machine):
    installed(tmp_path, monkeypatch, machine)
    folder = repo(tmp_path, "open", "git@github.com:example-org/open.git")
    hook = folder / ".git" / "hooks" / "pre-commit"
    hook.write_text("#!/bin/sh\ntouch ran-own-hook\nexit 3\n", encoding="utf-8")
    hook.chmod(0o755)
    put(folder, "a.md", "fine\n")
    run(folder, "add", "-A")
    done = run(folder, "commit", "-m", "x")
    assert done.returncode != 0 and (folder / "ran-own-hook").exists()
    hook.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    assert run(folder, "commit", "-m", "x").returncode == 0
    post = folder / ".git" / "hooks" / "post-commit"
    post.write_text("#!/bin/sh\ntouch ran-post\n", encoding="utf-8")
    post.chmod(0o755)
    put(folder, "b.md", "fine\n")
    run(folder, "add", "-A")
    run(folder, "commit", "-m", "y")
    assert (folder / "ran-post").exists(), "a hook the guard does not use is chained too"


# ---- GD-4: vyd guard and the line in vyd context -------------------------------------------------


def test_status_check_and_context_say_what_a_folder_is(tmp_path, monkeypatch, machine, capsys):
    from vyvid import cli

    guarded(tmp_path, monkeypatch)
    folder = repo(tmp_path, "open", "git@github.com:example-org/open.git")
    capsys.readouterr()
    assert cli.main(["guard", "status", "--in", str(folder)]) == 0
    out = capsys.readouterr().out
    assert ": public (github.com/example-org/open)" in out and "git hooks: absent" in out and "NOTE: the guard's git hooks are not installed" in out
    assert cli.main(["context", str(folder), "--no-pull"]) == 0
    assert "guarded: a public repository" in capsys.readouterr().out
    put(folder, "a.md", "about secret-project\n")
    run(folder, "add", "-A")
    assert cli.main(["guard", "check", "--in", str(folder)]) == 1
    assert "a.md:1: matches public-deny-terms:1" in capsys.readouterr().out
    commit(folder)
    assert cli.main(["guard", "check", "--all", "--in", str(folder)]) == 1
    assert "a.md:1" in capsys.readouterr().out


def test_install_sets_up_the_hooks_where_a_guard_is_configured_and_not_with_the_opt_out(tmp_path, monkeypatch, machine):
    from vyvid import cli

    guarded(tmp_path, monkeypatch)
    assert cli.main(["install", "--no-git-hooks", "--dry-run"]) in (0, 1) and guard.hooks_state() == "absent"
    cli.main(["install"])
    assert guard.hooks_state() == "installed"


def test_nothing_is_guarded_and_no_hook_is_set_up_where_no_guard_is_configured(tmp_path, monkeypatch, machine, capsys):
    from vyvid import cli

    configure(tmp_path, monkeypatch, "[framework]\n")
    cli.main(["install"])
    assert guard.hooks_state() == "absent"
    folder = repo(tmp_path, "open", "git@github.com:example-org/open.git")
    capsys.readouterr()
    assert cli.main(["guard", "status", "--in", str(folder)]) == 0 and "no guard is configured" in capsys.readouterr().out
