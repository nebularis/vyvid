# SPDX-License-Identifier: MIT
"""``vyd cloud script``: the setup script it writes embeds only the private domains named, writes them byte for byte, clones the
public ones and exits 0. Scratch homes, stub tools and local git repositories only, no network and nothing of the real home."""

from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path

import pytest

from subprocess_support import POSIX, environment, git, vyd
from vyvid import __version__, cli, cloud
from vyvid import config as cf

SENTINEL = "SENTINEL-UNNAMED-7731"
TRAP = b"line before\nVYD_B64\nVYD_CONFIG\nEOF\n$(echo no) `no` \\ '\"\nlast, no newline"
FILES = {"rules.md": "Правила, вивід. Naïve café ☃\n".encode(), "notes/trap.txt": TRAP, "empty.txt": b"", "deep/a/b/c.md": b"nested\n",
         "bin.dat": bytes(range(256))}


def repo(root: Path, files: dict[str, bytes]) -> Path:
    root.mkdir(parents=True)
    git(root, "init", "-q")
    for name, data in files.items():
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_bytes(data)
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "x")
    return root


@pytest.fixture
def world(tmp_path, monkeypatch):
    """A local home holding a configuration of two private and two public domains, and the folder of a cloud home."""
    home = tmp_path / "local"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    for k, v in environment(home).items():
        if k.startswith(("GIT_",)):
            monkeypatch.setenv(k, v)
    named = repo(home / "work" / "mine", FILES)
    repo(home / "work" / "other", {"secret.md": SENTINEL.encode()})
    withkey = repo(home / "work" / "pub1", {"a.md": b"a"})
    viaorigin = repo(home / "work" / "pub2", {"a.md": b"a"})
    git(viaorigin, "remote", "add", "origin", "git@github.com:Owner/Repo.git")
    git(withkey, "remote", "add", "origin", "https://example.org/ignored.git")
    cf.config_path().parent.mkdir(parents=True, exist_ok=True)
    cf.config_path().write_text(
        f'[framework]\nkb = "~/kb"\n\n[[domains]]\nname = "mine"\npath = "{named}"\ntrust = "own"\n\n'
        f'[[domains]]\nname = "other"\npath = "{home / "work" / "other"}"\ntrust = "own"\n\n'
        f'[[domains]]\nname = "pub-key"\npath = "{withkey}"\nvisibility = "public"\nremote = "https://github.com/example/pub-key.git"\ntrust = "own"\n\n'
        f'[[domains]]\nname = "pub-origin"\npath = "{viaorigin}"\nvisibility = "public"\ntrust = "knowledge"\n', encoding="utf-8")
    return tmp_path


def make(tmp_path, capsys, *args) -> tuple[int, str, str, Path]:
    out = tmp_path / "out" / "cloud.sh"
    code = cli.main(["cloud", "script", "--output", str(out), *args])
    seen = capsys.readouterr()
    return code, seen.out, seen.err, out


def test_only_the_named_domain_is_embedded_and_the_rest_is_said(world, capsys):
    code, out, err, script = make(world, capsys, "--domain", "mine")
    assert code == 0, err
    text = script.read_text(encoding="utf-8")
    assert SENTINEL not in text and "secret.md" not in text
    assert "domain mine: embedded, 5 files at ~/work/mine" in out
    assert "domain other: left out, it was not named" in out
    assert "domain pub-key: cloned from https://github.com/example/pub-key.git" in out
    assert "domain pub-origin: cloned from https://github.com/Owner/Repo.git" in out
    assert out.splitlines()[0] == f"written {script}" and "fingerprint " in out and "bytes of 65536" in out
    assert text.startswith("#!/bin/sh\n# Written by vyd cloud script")
    assert "private text" in text.splitlines()[3]
    assert f"@v{__version__}" in text


def test_the_output_is_owner_only_and_prints_no_content(world, capsys):
    code, out, err, script = make(world, capsys, "--domain", "mine")
    assert code == 0
    if os.name == "posix":
        assert stat.S_IMODE(script.stat().st_mode) == 0o600
    for shown in (out, err):
        assert "Правила" not in shown and "VYD_B64" not in shown and "nested" not in shown


def test_a_dry_run_prints_the_same_lines_and_writes_nothing(world, capsys):
    real = make(world, capsys, "--domain", "mine")
    script = real[3]
    script.unlink()
    out = world / "out" / "dry.sh"
    assert cli.main(["cloud", "script", "--output", str(out), "--domain", "mine", "--dry-run"]) == 0
    dry = capsys.readouterr().out
    assert not out.exists() and not script.exists()
    assert dry.splitlines()[1:] == real[1].splitlines()[1:]


def test_a_script_over_the_limit_warns(world, capsys, monkeypatch):
    monkeypatch.setattr(cloud, "LIMIT", 100)
    code, out, _, script = make(world, capsys, "--domain", "mine")
    assert code == 0 and "WARNING" in out and script.exists()


def test_a_named_domain_can_be_written_where_asked(world, capsys):
    code, out, err, script = make(world, capsys, "--domain", "mine=~/elsewhere/rules")
    assert code == 0, err
    assert "at ~/elsewhere/rules" in out and 'path = "~/elsewhere/rules"' in script.read_text(encoding="utf-8")


@POSIX
def test_the_script_writes_every_file_byte_for_byte_and_a_loadable_configuration(world, capsys, monkeypatch):
    _, _, _, script = make(world, capsys, "--domain", "mine", "--grant", "github.com/example/project")
    cloud_home = world / "cloud"
    stubs = world / "stubs"
    stubs.mkdir()
    cloud_home.mkdir()
    for tool in ("uv", "git", "vyd"):
        (stubs / tool).write_text(f'#!/bin/sh\necho {tool} "$@" >>"$HOME/calls"\nexit "${{STUB_EXIT:-0}}"\n')
        (stubs / tool).chmod(0o755)
    env = environment(cloud_home, PATH=f"{stubs}{os.pathsep}{os.environ['PATH']}", VYD_CLOUD_LOG=str(world / "log"))
    done = subprocess.run(["sh", str(script)], env=env, capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    for name, data in FILES.items():
        assert (cloud_home / "work" / "mine" / name).read_bytes() == data, name
    calls = (cloud_home / "calls").read_text().splitlines()
    assert f"uv tool install --force git+https://github.com/nebularis/vyvid.git@v{__version__}" in calls
    assert "vyd kb clone" in calls and "vyd install --client claude-code" in calls
    monkeypatch.setenv("HOME", str(cloud_home))
    config = cf.load(cloud_home / ".config" / "vyvid" / "config.toml")
    assert set(config.domains) == {"mine", "pub-key", "pub-origin"}
    assert config.domains["mine"].path == cloud_home / "work" / "mine" and config.domains["mine"].trust == "own"
    assert config.domains["mine"].visibility == "private" and config.glue == "stop"
    assert config.trusted_repositories == ("github.com/example/project",)
    assert config.domains["pub-origin"].remote == "https://github.com/Owner/Repo.git" and config.domains["pub-origin"].trust == "knowledge"
    assert config.domains["pub-key"].git.pull == config.domains["pub-key"].git.push == "manual"
    assert SENTINEL not in (world / "log").read_text()

    # A tool that fails leaves the exit at 0 and the failure in the log.
    failing = subprocess.run(["sh", str(script)], env={**env, "STUB_EXIT": "1"}, capture_output=True, text=True)
    assert failing.returncode == 0
    log = (world / "log").read_text()
    assert "FAILED: installing vyd" in log and "FAILED: cloning the public domains" in log


@POSIX
def test_a_real_install_from_the_written_files_matches_installing_from_the_domain(world, capsys):
    _, _, _, script = make(world, capsys, "--domain", "mine")
    cloud_home, local = world / "cloud", world / "local"
    stubs = world / "stubs"
    stubs.mkdir()
    cloud_home.mkdir()
    for tool in ("uv", "git", "vyd"):
        (stubs / tool).write_text("#!/bin/sh\nexit 0\n")
        (stubs / tool).chmod(0o755)
    env = environment(cloud_home, PATH=f"{stubs}{os.pathsep}{os.environ['PATH']}", VYD_CLOUD_LOG=str(world / "log"))
    assert subprocess.run(["sh", str(script)], env=env, capture_output=True).returncode == 0

    real = environment(cloud_home, VYVID_CONFIG=str(cloud_home / ".config" / "vyvid" / "config.toml"))
    assert vyd(real, "install", "--client", "claude-code").code == 0

    original = world / "orig"
    original.mkdir()
    (original / "config.toml").write_text(f'[framework]\nglue = "stop"\n\n[[domains]]\nname = "mine"\npath = "{local / "work" / "mine"}"\ntrust = "own"\nvisibility = "private"\n')
    base = environment(original, VYVID_CONFIG=str(original / "config.toml"))
    assert vyd(base, "install", "--client", "claude-code").code == 0

    def tree(home: Path) -> dict[str, bytes]:
        return {p.relative_to(home / ".claude").as_posix(): p.read_bytes() for p in (home / ".claude").rglob("*") if p.is_file()}

    wrote = tree(cloud_home)
    assert wrote == tree(original) and any("mine" in k for k in wrote)
    assert "rules/vyvid.md" in wrote


def refused(world, capsys, *args, output=True) -> str:
    out = world / "out" / "x.sh"
    argv = ["cloud", "script", *(["--output", str(out)] if output else []), *args]
    try:
        code = cli.main(argv)
    except SystemExit as stop:
        code = stop.code
    assert code != 0
    assert not out.exists()
    seen = capsys.readouterr()
    return seen.out + seen.err


def test_no_output_is_refused(world, capsys):
    assert "--output" in refused(world, capsys, "--domain", "mine", output=False)


def test_a_domain_not_configured_is_refused(world, capsys):
    assert "domain nope is not in the configuration" in refused(world, capsys, "--domain", "nope")


def test_a_folder_outside_home_needs_a_path(world, capsys, monkeypatch):
    monkeypatch.setenv("HOME", str(world / "elsewhere"))
    assert "outside the home folder" in refused(world, capsys, "--domain", "mine")


def test_a_path_must_start_with_the_home_folder(world, capsys):
    assert "must start with ~/" in refused(world, capsys, "--domain", "mine=/etc/x")
    assert "must not hold '..'" in refused(world, capsys, "--domain", "mine=~/../x")


@POSIX
def test_a_link_leaving_the_folder_is_refused(world, capsys):
    folder = world / "local" / "work" / "mine"
    (world / "outside.txt").write_text("x")
    (folder / "link").symlink_to(world / "outside.txt")
    git(folder, "add", "-A")
    git(folder, "commit", "-q", "-m", "link")
    assert "link leaves the domain's folder" in refused(world, capsys, "--domain", "mine")


def test_a_file_over_the_limit_is_refused(world, capsys):
    folder = world / "local" / "work" / "mine"
    (folder / "big.bin").write_bytes(b"x" * (cloud.FILE_LIMIT + 1))
    git(folder, "add", "-A")
    git(folder, "commit", "-q", "-m", "big")
    assert "big.bin is over 256 KB" in refused(world, capsys, "--domain", "mine")


def test_an_unnormalised_grant_is_refused(world, capsys):
    assert "must be written as github.com/example/project" in refused(world, capsys, "--domain", "mine", "--grant", "https://github.com/Example/project.git")


def run_and_install(world, script) -> Path:
    """Runs the script into a cloud home with stub tools, then the real install there, and returns the cloud home."""
    cloud_home, stubs = world / "cloud", world / "stubs"
    stubs.mkdir()
    cloud_home.mkdir()
    for tool in ("uv", "git", "vyd"):
        (stubs / tool).write_text("#!/bin/sh\nexit 0\n")
        (stubs / tool).chmod(0o755)
    env = environment(cloud_home, PATH=f"{stubs}{os.pathsep}{os.environ['PATH']}", VYD_CLOUD_LOG=str(world / "log"))
    assert subprocess.run(["sh", str(script)], env=env, capture_output=True).returncode == 0
    real = environment(cloud_home, VYVID_CONFIG=str(cloud_home / ".config" / "vyvid" / "config.toml"))
    assert vyd(real, "install", "--client", "claude-code").code == 0
    return cloud_home


@pytest.mark.skipif(not POSIX, reason="runs the script with sh")
def test_a_named_domain_with_skills_is_always_on_in_the_cloud_only(world, capsys):
    local = world / "local"
    skilled = repo(local / "work" / "skilled", {"domain.toml": b'name = "skilled"\n', "skills/careful/SKILL.md": b"---\nname: careful\ndescription: x\n---\n\nBe careful.\n",
                                               "skills/careful/notes.md": b"n\n"})
    ruled = repo(local / "work" / "ruled", {"domain.toml": b'name = "ruled"\nalways_rules = "self:rules/on.md"\n', "rules/on.md": b"On.\n",
                                           "skills/other/SKILL.md": b"---\nname: other\ndescription: y\n---\n"})
    with cf.config_path().open("a", encoding="utf-8") as f:
        f.write(f'\n[[domains]]\nname = "skilled"\npath = "{skilled}"\ntrust = "own"\n\n[[domains]]\nname = "ruled"\npath = "{ruled}"\ntrust = "own"\n')
    code, out, err, script = make(world, capsys, "--domain", "skilled", "--domain", "ruled")
    assert code == 0, err
    assert "domain skilled: its 1 skill always on in the cloud" in out and "domain ruled: its" not in out
    rules = run_and_install(world, script) / ".claude" / "rules"
    on = (rules / "skilled.md").read_text(encoding="utf-8")
    assert "@~/work/skilled/skills/careful/SKILL.md" in on and "notes.md" not in on
    assert (rules / "on.md").is_file() and not (rules / "ruled.md").exists()
    assert "always_rules" not in cf.config_path().read_text(encoding="utf-8")


@pytest.mark.skipif(not POSIX, reason="runs the script with sh")
def test_lines_pasted_after_the_script_run_with_their_own_output(world, capsys):
    _, _, _, script = make(world, capsys, "--domain", "mine")
    stubs = world / "stubs"
    stubs.mkdir()
    for tool in ("uv", "git", "vyd"):
        (stubs / tool).write_text("#!/bin/sh\nexit 1\n")
        (stubs / tool).chmod(0o755)
    combined = world / "combined.sh"
    combined.write_text(script.read_text(encoding="utf-8") + "echo after-the-script\n", encoding="utf-8")
    env = environment(world / "cloud", PATH=f"{stubs}{os.pathsep}{os.environ['PATH']}", VYD_CLOUD_LOG=str(world / "log"))
    done = subprocess.run(["sh", str(combined)], env=env, capture_output=True, text=True)
    assert done.returncode == 0 and done.stdout == "after-the-script\n"
    assert "FAILED: installing vyd" in (world / "log").read_text(encoding="utf-8")
    plain = subprocess.run(["sh", str(script)], env=env, capture_output=True, text=True)
    assert plain.returncode == 0 and plain.stdout == ""


@pytest.mark.skipif(not POSIX, reason="runs the script with sh")
def test_run_adds_the_projects_own_setup_after_the_rest(world, capsys):
    code, out, err, script = make(world, capsys, "--domain", "mine", "--run", "tools/setup.sh")
    assert code == 0, err
    assert "then runs tools/setup.sh from the session's checkout" in out
    checkout = world / "checkout"
    (checkout / "tools").mkdir(parents=True)
    (checkout / "tools" / "setup.sh").write_text('echo "project setup ran in $PWD"\nexit 3\n')
    stubs = world / "stubs"
    stubs.mkdir()
    for tool in ("uv", "git", "vyd"):
        (stubs / tool).write_text("#!/bin/sh\nexit 0\n")
        (stubs / tool).chmod(0o755)
    env = environment(world / "cloud", PATH=f"{stubs}{os.pathsep}{os.environ['PATH']}", VYD_CLOUD_LOG=str(world / "log"))
    done = subprocess.run(["sh", str(script)], env=env, cwd=checkout, capture_output=True, text=True)
    assert done.returncode == 0 and done.stdout == f"project setup ran in {checkout}\n"
    assert "project setup" not in (world / "log").read_text(encoding="utf-8")
    elsewhere = subprocess.run(["sh", str(script)], env=env, cwd=world, capture_output=True, text=True)
    assert elsewhere.returncode == 0 and "no tools/setup.sh in a checkout" in elsewhere.stdout


def test_without_run_the_script_runs_nothing_of_the_projects(world, capsys):
    _, _, _, script = make(world, capsys, "--domain", "mine")
    assert "/home/user/" not in script.read_text(encoding="utf-8")


@pytest.mark.parametrize("path", ["/etc/setup.sh", "~/setup.sh", "../setup.sh", "tools/../x.sh", "./setup.sh", "tools/set up.sh",
                                  "tools/$(id).sh", "tools/`id`.sh", "tools/a;b.sh", "tools/*.sh", "tools\\setup.sh", ""])
def test_run_refuses_anything_but_a_plain_path_in_the_repository(world, capsys, path):
    assert "must be a path inside the repository" in refused(world, capsys, "--domain", "mine", "--run", path)
