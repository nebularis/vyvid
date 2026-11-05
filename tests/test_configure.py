# SPDX-License-Identifier: MIT
"""VYD-23: the commands that edit the configuration. Each write is checked by the real loader before it lands, keeps the
file's comments and layout, refuses what a vyvid.toml may not hold, and is proven on a scratch VYVID_CONFIG."""

from __future__ import annotations

import os
import stat
import subprocess
import tomllib
from pathlib import Path

import pytest

from test_index_core import Words
from vyvid import ask, cli, configure
from vyvid import build as builder
from vyvid.config import load
from vyvid.resolve import bind_in


def git(folder: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(folder), *args], check=True, capture_output=True)


def checkout(tmp_path: Path, name: str, remote: str | None = None) -> Path:
    root = tmp_path / name
    root.mkdir(parents=True)
    git(root, "init", "-q", "-b", "main")
    if remote:
        git(root, "remote", "add", "origin", remote)
    return root


@pytest.fixture
def conf(tmp_path, monkeypatch):
    """The user's configuration, a file under the temporary folder that ``VYVID_CONFIG`` names."""
    path = tmp_path / "config.toml"
    monkeypatch.setenv("VYVID_CONFIG", str(path))
    return path


def vyd(capsys, *argv: str):
    code = cli.main(list(argv))
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def ok(capsys, *argv: str) -> bool:
    code, out, err = vyd(capsys, *argv)
    assert code == 0, (argv, out, err)
    return True


def person(monkeypatch) -> None:
    monkeypatch.setattr(cli, "_person", lambda: True)


REGISTERS = {
    "standards.md": "# Standards\n\n| ID | Claim | Problem shape | Evidence |\n|---|---|---|---|\n| STD-1 | **Write plainly.** | writing | none |\n",
    "notes.md": "| ID | Tool | Claim | Problem shape | Evidence | Activity | Technology | Specialises | Overrides |\n|---|---|---|---|---|---|---|---|---|\n"
                "| TOOL-1 | mise | **Run tests with mise run check, which keeps the ledger.** | How do I run the tests | check | | | | |\n"
                "| TOOL-2 | uv | **Use uv for packages.** | How do I add a package | lock | | | | |\n",
    "debt.md": "| ID | Debt | Why it matters |\n|---|---|---|\n| TD-1 | **A thing owed.** | it costs |\n| TD-2 | **Another.** | it costs |\n",
    "board.md": "| Slice | Deliverable | State | Blocked on |\n|---|---|---|---|\n| SL-1 | **Do a thing.** | planned | |\n",
    "plain.md": "| Option | Cost |\n|---|---|\n| fast | high |\n| slow | low |\n",
    "prose.md": "| Encoding | Width |\n|---|---|\n| fast | high |\n| UTF-8 | wide |\n",
}


def docs_repo(tmp_path: Path, files: dict[str, str] | None = None) -> Path:
    root = checkout(tmp_path, "private-docs")
    folder = root / "some-project"
    folder.mkdir()
    for name, text in (REGISTERS if files is None else files).items():
        (folder / name).parent.mkdir(parents=True, exist_ok=True)
        (folder / name).write_text(text, encoding="utf-8")
    return folder


LAYOUT = """# my configuration
[framework]
kb = "{kb}"   # the base

[[projects]]
# the first project
name = "a"
code = "{a}"
visibility = "public"

[[domains]]
name = "d"   # keep me
trust = "own"

# the second project
[[projects]]
name = "b"
code = "{b}"
domains = ["d"]
"""


def layout(tmp_path: Path, conf: Path) -> str:
    text = LAYOUT.format(kb=(tmp_path / "kb").as_posix(), a=(tmp_path / "a").as_posix(), b=(tmp_path / "b").as_posix())
    conf.write_text(text, encoding="utf-8")
    return text


# ---- Every write is checked, and written whole -----------------------------------------------------------


def test_a_write_the_loader_refuses_writes_nothing_and_lists_every_problem(tmp_path, conf, capsys):
    before = layout(tmp_path, conf)
    code, out, err = vyd(capsys, "project", "add", "a", "--code", str(tmp_path / "x"), "--domain", "ghost")
    assert code == 1 and "domain 'ghost' is not configured" in err
    code, out, err = vyd(capsys, "project", "add", "Bad Name", "--code", str(tmp_path / "x"))
    assert code == 1 and "a project needs a unique lower-case name" in err
    code, out, err = vyd(capsys, "project", "add", "a", "--code", str(tmp_path / "x"))
    assert code == 1 and "unique lower-case name" in err, "a name that exists"
    code, out, err = vyd(capsys, "project", "set", "b", "doc_share", "7")
    assert code == 1 and "doc_share" in err and conf.read_text(encoding="utf-8") == before
    code, out, err = vyd(capsys, "project", "set", "b", "domains", "ghost", "phantom")
    assert code == 1 and err.count("is not configured") == 2, "each problem is listed"
    assert conf.read_text(encoding="utf-8") == before and not list(tmp_path.glob(".vyd-*"))


def test_comments_and_odd_ordering_survive_an_edit_in_the_middle_and_a_remove(tmp_path, conf, capsys, monkeypatch):
    before = layout(tmp_path, conf)
    assert ok(capsys, "project", "set", "a", "visibility", "private")
    middle = conf.read_text(encoding="utf-8")
    assert middle == before.replace('visibility = "public"', 'visibility = "private"'), "only the one line changed"
    assert ok(capsys, "family", "add", "a", "STD", "--defined", f"code:standards.md", "--type", "standard")
    after = conf.read_text(encoding="utf-8")
    assert after == middle.replace('[[domains]]', '[projects.families]\nSTD = { defined = "code:standards.md", type = "standard" }\n\n[[domains]]', 1)
    assert [d["name"] for d in tomllib.loads(after)["domains"]] == ["d"]
    code, out, err = vyd(capsys, "domain", "remove", "d")
    assert code == 1 and "used by project 'b'" in err and conf.read_text(encoding="utf-8") == after
    assert ok(capsys, "project", "remove", "b")
    removed = conf.read_text(encoding="utf-8")
    assert removed == after.split("\n# the second project")[0], "the entry and the comment above it went, and nothing else"
    assert ok(capsys, "domain", "remove", "d")
    final = conf.read_text(encoding="utf-8")
    assert "keep me" not in final and "# my configuration" in final and "# the base" in final and "# the first project" in final
    assert [p["name"] for p in tomllib.loads(final)["projects"]] == ["a"] and "domains" not in tomllib.loads(final)


def test_the_file_is_written_whole_in_utf8_with_lf_and_keeps_its_mode(tmp_path, conf, capsys):
    conf.write_bytes(b"\xef\xbb\xbf# \xd0\x92\xd0\xb8\xd0\xb2\xd1\x96\xd0\xb4\r\n[framework]\r\nkb = \"k\"\r\n")
    conf.chmod(0o640)
    assert ok(capsys, "domain", "add", "tools", "--path", str(tmp_path / "tools"))
    raw = conf.read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf") and b"\r" not in raw and "# Вивід".encode() in raw
    assert stat.S_IMODE(conf.stat().st_mode) == 0o640 and not list(tmp_path.glob(".vyd-*"))


def test_a_missing_configuration_is_created_owner_only_in_a_folder_made_for_it(tmp_path, monkeypatch, capsys):
    path = tmp_path / "new" / "vyvid" / "config.toml"
    monkeypatch.setenv("VYVID_CONFIG", str(path))
    assert ok(capsys, "domain", "add", "tools", "--path", str(tmp_path / "tools"))
    assert stat.S_IMODE(path.stat().st_mode) == 0o600 and stat.S_IMODE(path.parent.stat().st_mode) == 0o700
    assert load().domains["tools"].trust == "knowledge"


def test_every_command_prints_the_change_and_the_file_with_dry_run_and_writes_nothing(tmp_path, conf, capsys, monkeypatch):
    person(monkeypatch)
    before = layout(tmp_path, conf)
    docs = docs_repo(tmp_path)
    for argv in (("domain", "add", "n", "--path", str(tmp_path / "n")), ("domain", "remove", "d"), ("project", "add", "c", "--code", str(tmp_path / "c")),
                 ("project", "set", "a", "docs", str(docs)), ("project", "remove", "a"), ("family", "add", "a", "TD", "--defined", f"code:debt.md", "--type", "debt"),
                 ("project", "set", "a", "visibility", "private")):
        code, out, err = vyd(capsys, *argv, "--dry-run")
        assert code in (0, 1), argv
        if code == 0:
            assert f"would write {conf}" in out and "dry run, nothing written" in out and out.count("\n+") + out.count("\n-") >= 1, (argv, out)
        assert conf.read_text(encoding="utf-8") == before
    assert not list(tmp_path.glob(".vyd-*"))
    code, out, err = vyd(capsys, "domain", "remove", "d", "--dry-run")
    assert code == 1 and "used by project 'b'" in err, "a dry run refuses what a run would"


# ---- project add ------------------------------------------------------------------------------------------


def test_project_add_in_a_checkout_takes_the_code_folder_and_the_remotes_as_the_matcher_reads_them(tmp_path, conf, capsys, monkeypatch):
    code_root = checkout(tmp_path, "some-project", "git@github.com:Example/Some-Project.git")
    git(code_root, "remote", "add", "mirror", "https://user:secret@example.org/x/some-project.git/")
    docs = docs_repo(tmp_path)
    monkeypatch.chdir(code_root / ".git" / "..")
    assert ok(capsys, "domain", "add", "tools", "--path", str(tmp_path / "tools"))
    code, out, err = vyd(capsys, "project", "add", "some-project", "--docs", str(docs), "--contract", "docs:CONTRACT.md", "--domain", "tools", "--visibility", "public")
    assert code == 0, err
    project = load().projects["some-project"]
    assert project.code == code_root and project.docs == docs and project.domains == ["tools"] and project.visibility == "public"
    assert project.remotes == ["github.com/example/some-project", "example.org/x/some-project"] and "secret" not in conf.read_text(encoding="utf-8")
    entry = tomllib.loads(conf.read_text(encoding="utf-8"))["projects"][0]
    assert list(entry) == ["name", "visibility", "code", "match", "docs", "contract", "domains"]
    assert ok(capsys, "project", "add", "other", "--code", str(tmp_path / "x"), "--remote", "git@github.com:A/B.git")
    assert load().projects["other"].remotes == ["github.com/a/b"]


# ---- domains and trust ------------------------------------------------------------------------------------


def test_raising_trust_needs_a_person_and_the_message_says_so(tmp_path, conf, capsys, monkeypatch):
    code, out, err = vyd(capsys, "domain", "add", "tools", "--path", str(tmp_path / "tools"), "--trust", "own")
    assert code == 1 and "A person must run this command, in a terminal" in err and not conf.exists()
    code, out, err = vyd(capsys, "domain", "add", "tools", "--path", str(tmp_path / "tools"), "--trust", "own", "--dry-run")
    assert code == 0 and 'trust = "own"' in out and "a person must run it for real" in out and not conf.exists()
    code, out, err = vyd(capsys, "domain", "add", "rev", "--path", str(tmp_path / "rev"), "--trust", "reviewed", "--commit", "abcdef1")
    assert code == 1 and "A person must run" in err
    person(monkeypatch)
    assert ok(capsys, "domain", "add", "tools", "--path", str(tmp_path / "tools"), "--trust", "own")
    code, out, err = vyd(capsys, "domain", "add", "rev", "--path", str(tmp_path / "rev"), "--trust", "reviewed")
    assert code == 1 and "needs a commit" in err
    assert ok(capsys, "domain", "add", "rev", "--path", str(tmp_path / "rev"), "--trust", "reviewed", "--commit", "abcdef1")
    assert [load().domains[n].trust for n in ("tools", "rev")] == ["own", "reviewed"]


def test_an_agent_adds_a_knowledge_domain_and_a_remote_without_a_path_is_left_to_vyd_kb_clone(tmp_path, conf, capsys):
    conf.write_text(f'[framework]\nkb = "{(tmp_path / "kb").as_posix()}"\n', encoding="utf-8")
    code, out, err = vyd(capsys, "domain", "add", "tools", "--remote", "https://github.com/example/vyvid-tools")
    assert code == 0 and "vyd kb clone tools" in out
    domain = load().domains["tools"]
    assert domain.trust == "knowledge" and domain.path == tmp_path / "kb" / "domains" / "tools" and not domain.path.exists(), "nothing was cloned"
    code, out, err = vyd(capsys, "domain", "add", "x", "--remote", "https://user:pw@example.org/x/y")
    assert code == 1 and "has a password" in err or "user part" in err
    code, out, err = vyd(capsys, "domain", "add", "y")
    assert code == 1 and "--path" in err and "--remote" in err
    code, out, err = vyd(capsys, "domain", "add", "z", "--path", "p", "--file")
    assert code == 1 and "Leave out --file" in err


def test_binding_a_domain_that_gives_more_than_knowledge_needs_a_person(tmp_path, conf, capsys, monkeypatch):
    conf.write_text('[[domains]]\nname = "mine"\npath = "m"\ntrust = "own"\n[[domains]]\nname = "theirs"\npath = "t"\ntrust = "knowledge"\n[[projects]]\nname = "a"\ncode = "x"\n', encoding="utf-8")
    code, out, err = vyd(capsys, "project", "add", "b", "--code", str(tmp_path), "--domain", "mine")
    assert code == 1 and "A person must run" in err and "mine" in err
    assert ok(capsys, "project", "add", "b", "--code", str(tmp_path), "--domain", "theirs")
    assert vyd(capsys, "project", "set", "a", "domains", "mine")[0] == 1
    person(monkeypatch)
    assert ok(capsys, "project", "set", "a", "domains", "mine", "theirs") and load().projects["a"].domains == ["mine", "theirs"]


TRUSTED = ('# top\n[[domains]]\n# about d\nname = "d"   # keep me\npath = "{p}"\ntrust = "knowledge"\n\n# second\n[[domains]]\nname = "e"\ntrust = "own"\npath = "{q}"\n'
           '\n[[domains]]\nname = "r"\npath = "{r}"\ntrust = "reviewed"\ncommit = "abcdef1"\n')


def trusted(tmp_path, conf) -> str:
    text = TRUSTED.format(p=(tmp_path / "d").as_posix(), q=(tmp_path / "e").as_posix(), r=(tmp_path / "r").as_posix())
    conf.write_text(text, encoding="utf-8")
    return text


def test_raising_a_domains_trust_needs_a_person_and_dry_run_does_not(tmp_path, conf, capsys, monkeypatch):
    before = trusted(tmp_path, conf)
    for argv in (("d", "own"), ("d", "reviewed", "--commit", "abcdef2"), ("r", "own"), ("r", "reviewed", "--commit", "abcdef2")):
        code, out, err = vyd(capsys, "domain", "trust", *argv)
        assert code == 1 and "A person must run this command, in a terminal" in err, argv
        assert conf.read_text(encoding="utf-8") == before
    code, out, err = vyd(capsys, "domain", "trust", "d", "own", "--dry-run")
    assert code == 0 and "a person must run it for real" in out and conf.read_text(encoding="utf-8") == before
    person(monkeypatch)
    assert ok(capsys, "domain", "trust", "d", "own") and load().domains["d"].trust == "own"
    assert ok(capsys, "domain", "trust", "r", "reviewed", "--commit", "abcdef2") and load().domains["r"].commit == "abcdef2"


def test_lowering_a_domains_trust_needs_no_terminal_and_own_to_reviewed_is_lowering(tmp_path, conf, capsys):
    trusted(tmp_path, conf)
    code, out, err = vyd(capsys, "domain", "trust", "e", "reviewed", "--commit", "abcdef1")
    assert code == 0 and "knowledge alone at any other" in out, err
    assert load().domains["e"].trust == "reviewed"
    code, out, err = vyd(capsys, "domain", "trust", "r", "knowledge")
    assert code == 0 and "until the next vyd install --project" in out, err
    domain = load().domains["r"]
    assert domain.trust == "knowledge" and domain.commit is None and "commit" not in tomllib.loads(conf.read_text(encoding="utf-8"))["domains"][2]
    assert ok(capsys, "domain", "trust", "e", "knowledge") and load().domains["e"].trust == "knowledge"


def test_reviewed_needs_a_commit_that_a_person_names_and_only_reviewed_takes_one(tmp_path, conf, capsys, monkeypatch):
    person(monkeypatch)
    folder = checkout(tmp_path, "d")
    (folder / "f").write_text("x", encoding="utf-8")
    git(folder, "add", "f")
    git(folder, "-c", "user.name=t", "-c", "user.email=t@example.org", "commit", "-q", "-m", "x")
    head = subprocess.run(["git", "-C", str(folder), "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    conf.write_text(f'[[domains]]\nname = "d"\npath = "{folder.as_posix()}"\ntrust = "knowledge"\n', encoding="utf-8")
    before = conf.read_text(encoding="utf-8")
    code, out, err = vyd(capsys, "domain", "trust", "d", "reviewed")
    assert code == 1 and "needs --commit" in err and head in err and conf.read_text(encoding="utf-8") == before
    for bad in ("zzzzzzz", "abc", 'abcdef1"\n[x]', "abcdef1\n"):
        code, out, err = vyd(capsys, "domain", "trust", "d", "reviewed", "--commit", bad)
        assert code == 1 and "hexadecimal" in err and conf.read_text(encoding="utf-8") == before, bad
    for level in ("own", "knowledge"):
        code, out, err = vyd(capsys, "domain", "trust", "d", level, "--commit", "abcdef1")
        assert code == 1 and "--commit is for trust reviewed" in err and conf.read_text(encoding="utf-8") == before
    assert ok(capsys, "domain", "trust", "d", "reviewed", "--commit", head[:12]) and load().domains["d"].commit == head[:12]


def test_the_same_trust_and_commit_is_no_change(tmp_path, conf, capsys, monkeypatch):
    before = trusted(tmp_path, conf)
    for argv in (("d", "knowledge"), ("e", "own"), ("r", "reviewed", "--commit", "ABCDEF1")):
        code, out, err = vyd(capsys, "domain", "trust", *argv)
        assert code == 0 and "already has trust" in out and conf.read_text(encoding="utf-8") == before, argv


def test_an_unknown_or_set_aside_domain_or_a_file_flag_is_refused(tmp_path, conf, capsys, monkeypatch):
    person(monkeypatch)
    before = trusted(tmp_path, conf)
    code, out, err = vyd(capsys, "domain", "trust", "nope", "own")
    assert code == 1 and "not configured" in err and "d, e, r" in err
    code, out, err = vyd(capsys, "domain", "trust", 'd"\n[x]', "own")
    assert code == 1 and "not configured" in err
    with pytest.raises(SystemExit):
        cli.main(["domain", "trust", "d", "own", "--file"])
    capsys.readouterr()
    assert conf.read_text(encoding="utf-8") == before
    folder = tmp_path / "d"
    folder.mkdir()
    (folder / "domain.toml").write_text('name = "d"\ntrust = "own"\n', encoding="utf-8")
    code, out, err = vyd(capsys, "domain", "trust", "d", "own")
    assert code == 1 and "set aside" in err and conf.read_text(encoding="utf-8") == before


def test_a_trust_change_keeps_comments_and_layout_and_adds_or_keeps_the_line_where_it_is(tmp_path, conf, capsys, monkeypatch):
    person(monkeypatch)
    text = trusted(tmp_path, conf)
    assert ok(capsys, "domain", "trust", "d", "own")
    assert conf.read_text(encoding="utf-8") == text.replace('trust = "knowledge"', 'trust = "own"', 1)
    # no trust line at all, in a domain with a remote-free default of own
    conf.write_text('# lead\n[[domains]]\nname = "x"   # c\npath = "p"\n\n[[domains]]\nname = "y"\npath = "q"\n', encoding="utf-8")
    assert ok(capsys, "domain", "trust", "x", "knowledge")
    assert conf.read_text(encoding="utf-8") == '# lead\n[[domains]]\nname = "x"   # c\npath = "p"\ntrust = "knowledge"\n\n[[domains]]\nname = "y"\npath = "q"\n'
    # trust written first, before the name
    conf.write_text('[[domains]]\ntrust = "knowledge"\nname = "x"\npath = "p"\n', encoding="utf-8")
    assert ok(capsys, "domain", "trust", "x", "own")
    assert conf.read_text(encoding="utf-8") == '[[domains]]\ntrust = "own"\nname = "x"\npath = "p"\n'
    # a loader refusal writes nothing
    conf.write_text('[[domains]]\nname = "x"\npath = "p"\ntrust = "knowledge"\nbogus = 1\n', encoding="utf-8")
    before = conf.read_text(encoding="utf-8")
    code, out, err = vyd(capsys, "domain", "trust", "x", "own")
    assert code == 1 and conf.read_text(encoding="utf-8") == before


def test_a_knowledge_domains_skill_composes_once_a_person_raises_its_trust(tmp_path, capsys, monkeypatch):
    from test_skills import world

    config, code = world(tmp_path)
    path = tmp_path / "config.toml"
    path.write_text(path.read_text(encoding="utf-8").replace('trust = "own"', 'trust = "knowledge"'), encoding="utf-8")
    monkeypatch.setenv("VYVID_CONFIG", str(path))

    def written() -> list[Path]:
        return [p for p in code.rglob("SKILL.md") if ".vyvid" not in p.parts]

    assert cli.main(["install", "--project", "--in", str(code)]) in (0, 1)
    out = capsys.readouterr().out
    assert not written() and "no skill from domain lifecycle" in out and "vyd domain trust lifecycle own" in out
    assert vyd(capsys, "domain", "trust", "lifecycle", "own")[0] == 1
    person(monkeypatch)
    code_, out, err = vyd(capsys, "domain", "trust", "lifecycle", "own")
    assert code_ == 0 and "vyd install --project" in out, err
    assert cli.main(["install", "--project", "--in", str(code)]) == 0
    capsys.readouterr()
    assert written()


# ---- project set ------------------------------------------------------------------------------------------


def test_project_set_writes_scalars_and_lists_and_refuses_what_has_its_own_command(tmp_path, conf, capsys, monkeypatch):
    layout(tmp_path, conf)
    assert ok(capsys, "project", "set", "a", "docs", "docs") and load().projects["a"].docs == Path.cwd() / "docs"
    assert ok(capsys, "project", "set", "a", "doc_share", "0.25") and load().projects["a"].doc_share == 0.25
    assert ok(capsys, "project", "set", "b", "contract", "docs:one.md", "docs:two.md") and len(load().projects["b"].rules) == 2
    assert ok(capsys, "project", "set", "b", "remote", "git@github.com:X/Y.git") and load().projects["b"].remotes == ["github.com/x/y"]
    assert vyd(capsys, "project", "set", "b", "visibility", "secret")[0] == 1
    for key, where in (("families", "vyd family add"), ("moves", "hand-editing"), ("extractors", "hand-editing"), ("recipes", "hand-editing")):
        code, out, err = vyd(capsys, "project", "set", "a", key, "x")
        assert code == 1 and where in err
    code, out, err = vyd(capsys, "project", "set", "a", "banana", "x")
    assert code == 1 and "not a key" in err and "visibility" in err
    for key in ("hook_clients", "skill_targets", "skills", "skill_additions"):
        code, out, err = vyd(capsys, "project", "set", "a", key, "claude-code" if key == "hook_clients" else "x")
        assert code == 1 and "A person must run" in err, key
    person(monkeypatch)
    assert ok(capsys, "project", "set", "a", "hook_clients", "claude-code", "copilot") and load().projects["a"].hook_clients == ("claude-code", "copilot")
    assert vyd(capsys, "project", "set", "ghost", "docs", "x")[0] == 1


# ---- families ---------------------------------------------------------------------------------------------


def test_family_add_checks_the_type_the_name_and_the_path_and_remove_takes_it_out(tmp_path, conf, capsys):
    code_root = checkout(tmp_path, "code")
    docs = docs_repo(tmp_path)
    conf.write_text(f'[[projects]]\nname = "p"\ncode = "{code_root.as_posix()}"\ndocs = "{docs.as_posix()}"\n', encoding="utf-8")
    code, out, err = vyd(capsys, "family", "add", "p", "STD", "--defined", "docs:standards.md", "--type", "standrad")
    assert code == 1 and "type 'standrad'" in err and "standard" in err
    code, out, err = vyd(capsys, "family", "add", "p", "STD", "--defined", "docs:standards.md", "--type", "standard", "--pattern", "STD-(")
    assert code == 1 and "does not compile" in err
    assert ok(capsys, "family", "add", "p", "SL", "--defined", "docs:board.md", "--type", "slice", "--pattern", r"SL-\d[\w.]*", "--removable")
    spec = tomllib.loads(conf.read_text(encoding="utf-8"))["projects"][0]["families"]["SL"]
    assert spec == {"pattern": r"SL-\d[\w.]*", "defined": "docs:board.md", "type": "slice", "removable": True}
    assert "pattern = 'SL-\\d[\\w.]*'" in conf.read_text(encoding="utf-8"), "a pattern is read as it is, between single quotes"
    code, out, err = vyd(capsys, "family", "add", "p", "SL", "--defined", "docs:board.md", "--type", "slice")
    assert code == 1 and "exists" in err
    assert vyd(capsys, "family", "add", "p", "TD", "--defined", str(docs / "debt.md"), "--type", "debt")[0] == 0, "an absolute path inside the documents becomes docs:"
    assert 'defined = "docs:debt.md"' in conf.read_text(encoding="utf-8")
    code, out, err = vyd(capsys, "family", "remove", "p", "SL")
    assert code == 0 and "left as it is" in out and "SL" not in load().projects["p"].families and "TD" in load().projects["p"].families
    assert vyd(capsys, "family", "remove", "p", "SL")[0] == 1
    assert ok(capsys, "family", "remove", "p", "TD") and "families" not in tomllib.loads(conf.read_text(encoding="utf-8"))["projects"][0]


# ---- project scan -----------------------------------------------------------------------------------------


def test_scan_proposes_a_family_where_the_header_tells_the_type_and_names_what_it_cannot_place(tmp_path, conf, capsys):
    docs = docs_repo(tmp_path)
    (docs / "mixed.md").write_text("| ID | Debt | Why it matters |\n|---|---|---|\n| TD-9 | **x** | y |\n| see below | **x** | y |\n", encoding="utf-8")
    (docs / "fenced.md").write_text("```\n| ID | Debt | Why it matters |\n|---|---|---|\n| ZZ-1 | **x** | y |\n```\n", encoding="utf-8")
    (docs / "unknown.md").write_text("| ID | Claim | Mystery |\n|---|---|---|\n| QQ-1 | **x** | y |\n", encoding="utf-8")
    (docs / "two.md").write_text("| ID | Debt | Why it matters |\n|---|---|---|\n| MM-1 | **x** | y |\n| NN-1 | **x** | y |\n", encoding="utf-8")
    conf.write_text(f'[[projects]]\nname = "p"\ncode = "{tmp_path.as_posix()}"\ndocs = "{docs.as_posix()}"\n', encoding="utf-8")
    code, out, err = vyd(capsys, "project", "scan", "p")
    assert code == 0, err
    proposed = out.split("Not placed")[0]
    assert 'SL = { defined = "docs:board.md", type = "slice" }' in proposed and "# 1 row in board.md" in proposed
    assert 'TOOL = { defined = "docs:notes.md", type = "note" }' in proposed and "# 2 rows in notes.md" in proposed
    assert 'TD = { defined = "docs:debt.md", type = "debt" }' in proposed and "# 2 rows" in proposed
    assert "STD" not in proposed and "ZZ" not in out and "Option" not in out and "plain.md" not in out and "UTF" not in proposed, "a table with no identifiers, or in a fence, is ignored"
    named = out.split("Not placed")[1]
    assert "standards.md:3, prefix STD" in named and "signs of no register type" in named, "a register that fits no type is named"
    assert "mixed.md:1" in named and "mixes identifiers" in named
    assert "unknown.md:1" in named and "Mystery" in named
    assert "two.md:1" in named and "several prefixes" in named
    assert "prose.md:1" in named and "mixes identifiers" in named, "an identifier-shaped cell among prose is named, never read as a family"
    assert tomllib.loads(conf.read_text(encoding="utf-8"))["projects"][0].get("families") is None, "nothing is written without --apply"


def test_scan_leaves_an_existing_family_alone_proposes_a_pattern_only_where_the_default_does_not_fit_and_applies(tmp_path, conf, capsys):
    docs = docs_repo(tmp_path, {"debt.md": REGISTERS["debt.md"], "board.md": "| Slice | Deliverable | State | Blocked on |\n|---|---|---|---|\n| SL-1.2 | **a** | planned | |\n"})
    conf.write_text(f'[[projects]]\nname = "p"\ncode = "{tmp_path.as_posix()}"\ndocs = "{docs.as_posix()}"\n[projects.families]\nTD = {{ defined = "docs:old.md", type = "debt" }}\n', encoding="utf-8")
    code, out, err = vyd(capsys, "project", "scan", "p", "--apply")
    assert code == 0, err
    assert "Left alone, as the project declares them: TD" in out and "pattern = 'SL-\\d[\\w.]*'" in out and "Read it" in out
    families = load().projects["p"].families
    assert families["TD"].defined == docs.parent.parent / "old.md" or families["TD"].defined.name == "old.md", "the existing family is as it was"
    assert families["SL"].pattern.fullmatch("SL-1.2")
    code, out, err = vyd(capsys, "project", "scan", "p", "--apply")
    assert code == 0 and "Nothing to propose" in out


def test_scan_over_several_files_of_one_folder_and_type_proposes_a_glob(tmp_path, conf, capsys):
    board = "| Slice | Deliverable | State | Blocked on |\n|---|---|---|---|\n| SL-{n} | **a** | planned | |\n"
    docs = docs_repo(tmp_path, {"status/a.md": board.format(n=1), "status/b.md": board.format(n=2), "other/c.md": board.format(n=3)})
    conf.write_text(f'[[projects]]\nname = "p"\ncode = "{tmp_path.as_posix()}"\ndocs = "{docs.as_posix()}"\n', encoding="utf-8")
    code, out, err = vyd(capsys, "project", "scan", "p")
    assert code == 0 and "sit in different folders" in out and "SL = {" not in out, "two folders, so no single definition, and nothing is guessed"
    (docs / "other" / "c.md").unlink()
    code, out, err = vyd(capsys, "project", "scan", "p")
    assert 'SL = { defined = "docs:status/*.md", type = "slice" }' in out and "# 2 rows" in out


# ---- a vyvid.toml -----------------------------------------------------------------------------------------


def test_file_writes_the_repositorys_vyvid_toml_refuses_what_it_may_not_hold_and_says_trust_lapses(tmp_path, conf, capsys, monkeypatch):
    root = checkout(tmp_path, "repo")
    (root / "docs").mkdir()
    (root / "docs" / "debt.md").write_text(REGISTERS["debt.md"], encoding="utf-8")
    monkeypatch.chdir(root)
    code, out, err = vyd(capsys, "project", "add", "repo", "--file", "--code", str(root))
    assert code == 1 and "may not set code or match" in err
    code, out, err = vyd(capsys, "project", "add", "repo", "--file", "--docs", str(tmp_path / "elsewhere"))
    assert code == 1 and "belongs in the user's configuration" in err and not (root / "vyvid.toml").exists()
    code, out, err = vyd(capsys, "project", "add", "repo", "--file", "--docs", "docs", "--contract", "docs:CONTRACT.md", "--visibility", "public")
    assert code == 0 and "vyd trust" in out and "lapses" in out, out
    assert (root / "vyvid.toml").read_text(encoding="utf-8") == '[project]\nname = "repo"\nvisibility = "public"\ndocs = "code:docs"\ncontract = "docs:CONTRACT.md"\n'
    assert vyd(capsys, "project", "add", "repo", "--file")[0] == 1
    code, out, err = vyd(capsys, "project", "set", "repo", "code", "x", "--file")
    assert code == 1 and "may not set code" in err
    code, out, err = vyd(capsys, "project", "set", "repo", "docs", str(tmp_path), "--file")
    assert code == 1 and "belongs in the user's configuration" in err
    assert ok(capsys, "project", "scan", "repo", "--apply", "--file")
    assert 'TD = { defined = "docs:debt.md", type = "debt" }' in (root / "vyvid.toml").read_text(encoding="utf-8")
    assert ok(capsys, "family", "remove", "repo", "TD", "--file") and "TD" not in (root / "vyvid.toml").read_text(encoding="utf-8")
    code, out, err = vyd(capsys, "project", "remove", "repo", "--file")
    assert code == 1 and "never deletes a file" in err and (root / "vyvid.toml").exists()
    code, out, err = vyd(capsys, "family", "add", "repo", "X", "--defined", str(tmp_path / "x.md"), "--type", "debt", "--file")
    assert code == 1 and "outside" in err


def test_a_domain_a_checkouts_vyvid_toml_uses_cannot_be_removed(tmp_path, conf, capsys, monkeypatch):
    root = checkout(tmp_path, "repo")
    (root / "vyvid.toml").write_text('[project]\nname = "repo"\ndomains = ["tools"]\n', encoding="utf-8")
    conf.write_text('[[domains]]\nname = "tools"\npath = "t"\n', encoding="utf-8")
    monkeypatch.chdir(root)
    code, out, err = vyd(capsys, "domain", "remove", "tools")
    assert code == 1 and "project 'repo'" in err and "vyvid.toml" in err and "tools" in conf.read_text(encoding="utf-8")


# ---- removes never delete ---------------------------------------------------------------------------------


def test_removing_a_project_or_a_domain_deletes_no_folder_and_says_so(tmp_path, conf, capsys):
    folder = tmp_path / "tools"
    folder.mkdir()
    (folder / "keep.md").write_text("mine", encoding="utf-8")
    code_root = checkout(tmp_path, "code")
    conf.write_text(f'[[domains]]\nname = "tools"\npath = "{folder.as_posix()}"\n[[projects]]\nname = "p"\ncode = "{code_root.as_posix()}"\n', encoding="utf-8")
    code, out, err = vyd(capsys, "project", "remove", "p")
    assert code == 0 and "store and logs" in out and "left as they are" in out and code_root.is_dir()
    code, out, err = vyd(capsys, "domain", "remove", "tools")
    assert code == 0 and "never deletes a clone or a folder" in out and (folder / "keep.md").read_text(encoding="utf-8") == "mine"
    assert vyd(capsys, "domain", "remove", "tools")[0] == 1


# ---- security ---------------------------------------------------------------------------------------------


def test_a_value_with_quotes_and_newlines_is_escaped_and_cannot_add_a_key_or_a_table(tmp_path, conf, capsys):
    conf.write_text("", encoding="utf-8")
    hostile = 'x"\n[[domains]]\nname = "evil"\ntrust = "own"\n# '
    assert ok(capsys, "project", "add", "p", "--code", str(tmp_path), "--contract", "docs:" + hostile)
    data = tomllib.loads(conf.read_text(encoding="utf-8"))
    assert list(data) == ["projects"] and data["projects"][0]["contract"] == "docs:" + hostile
    assert vyd(capsys, "project", "set", "p", "skill_prefix", hostile)[0] == 1, "refused by the loader and not written"
    assert ok(capsys, "domain", "add", "q", "--path", hostile, "--dry-run")
    assert "evil" not in [d.get("name") for d in tomllib.loads(conf.read_text(encoding="utf-8")).get("domains", [])]


def test_a_family_definition_cannot_leave_the_project(tmp_path, conf, capsys):
    code_root = checkout(tmp_path, "code")
    docs = docs_repo(tmp_path)
    secret = tmp_path / "secret.md"
    secret.write_text("| ID | Debt | Why it matters |\n|---|---|---|\n| TD-1 | **x** | y |\n", encoding="utf-8")
    (docs / "link.md").symlink_to(secret)
    conf.write_text(f'[[projects]]\nname = "p"\ncode = "{code_root.as_posix()}"\ndocs = "{docs.as_posix()}"\n', encoding="utf-8")
    for defined in ("docs:../secret.md", "code:../secret.md", str(secret), "kb:x", "~/x.md", "self:x"):
        code, out, err = vyd(capsys, "family", "add", "p", "TD", "--defined", defined, "--type", "debt")
        assert code == 1 and ("leaves" in err or "outside" in err or "token" in err), (defined, err)
    assert "TD" not in load().projects["p"].families
    assert vyd(capsys, "family", "add", "p", "TD", "--defined", "docs:link.md", "--type", "debt")[0] == 1, "a link out of the documents is refused too"
    found = configure.tables(docs)
    assert all(t.file != "link.md" for t in found), "a link out of the documents is not read by a scan"
    code, out, err = vyd(capsys, "project", "add", "q", "--code", str(code_root), "--docs", str(docs / ".." / ".." / "x"))
    assert code == 0, "a path with .. in the user's own configuration is made absolute, not kept"
    assert ".." not in tomllib.loads(conf.read_text(encoding="utf-8"))["projects"][1]["docs"]


def test_a_domain_manifest_that_is_refused_stops_the_add(tmp_path, conf, capsys):
    folder = tmp_path / "bad"
    folder.mkdir()
    (folder / "domain.toml").write_text('name = "bad"\ntrust = "own"\n', encoding="utf-8")
    code, out, err = vyd(capsys, "domain", "add", "bad", "--path", str(folder))
    assert code == 1 and "set aside" in err and not conf.exists()


# ---- end to end -------------------------------------------------------------------------------------------


def test_commands_alone_set_up_a_project_whose_documents_live_in_another_repository(tmp_path, conf, capsys, monkeypatch):
    code_root = checkout(tmp_path, "some-project", "git@github.com:example/some-project.git")
    docs = docs_repo(tmp_path)
    (docs / "tools.md").write_text(REGISTERS["notes.md"].replace("mise run check", "mise run check the ledger"), encoding="utf-8")
    (docs / "notes.md").unlink()
    tools = tmp_path / "tools"
    assert cli.main(["domain", "new", "tools", "--path", str(tools)]) == 0
    capsys.readouterr()
    monkeypatch.chdir(code_root)
    assert not conf.exists()
    for argv in (("domain", "add", "tools", "--path", str(tools)),
                 ("project", "add", "some-project", "--docs", str(docs), "--contract", "docs:CONTRACT.md", "--domain", "tools"),
                 ("project", "scan", "some-project", "--apply")):
        code, out, err = vyd(capsys, *argv)
        assert code == 0, (argv, err)
    code, out, err = vyd(capsys, "config")
    assert code == 0 and "projects: some-project" in out and "domains: tools" in out, (out, err)
    assert ok(capsys, "build", str(code_root), "--no-embed")
    config, project = bind_in(load(), code_root)
    assert project.name == "some-project" and set(project.families) >= {"TD", "TOOL", "SL"}
    result = builder.build(config, project, model=Words())
    assert result.counts["Note"] == 2 and result.counts["Debt"] == 2, result.counts
    a = ask.open_stack(config, code_root, model=Words())
    assert {"TOOL-1", "TD-1"} <= {r["id"] for r in ask.fold(a, ask.candidates(a, set(), set(), set()))}
    ask.find(a, "ledger", set(), set(), set(), 8)
    assert "TOOL-1" in capsys.readouterr().out, "find answers from a note of the other repository"


def test_a_layout_it_cannot_edit_faithfully_is_refused_and_other_ways_of_writing_families_are_edited_in_place(tmp_path, conf, capsys):
    code_root = checkout(tmp_path, "code")
    docs = docs_repo(tmp_path)
    inline = f'projects = [{{ name = "p", code = "{code_root.as_posix()}" }}]\n'
    conf.write_text(inline, encoding="utf-8")
    code, out, err = vyd(capsys, "project", "set", "p", "visibility", "private")
    assert code == 1 and "edit it by hand" in err and conf.read_text(encoding="utf-8") == inline
    head = f'[[projects]]\nname = "p"\ncode = "{code_root.as_posix()}"\ndocs = "{docs.as_posix()}"\n'
    conf.write_text(head + 'families = { SL = { defined = "docs:board.md", type = "slice" } }\n', encoding="utf-8")
    assert ok(capsys, "family", "add", "p", "TD", "--defined", "docs:debt.md", "--type", "debt")
    assert set(load().projects["p"].families) == {"SL", "TD"} and conf.read_text(encoding="utf-8").startswith(head)
    assert ok(capsys, "family", "remove", "p", "SL") and ok(capsys, "family", "remove", "p", "TD")
    assert conf.read_text(encoding="utf-8") == head
    conf.write_text(head + '[projects.families.SL]\ndefined = "docs:board.md"\ntype = "slice"\n', encoding="utf-8")
    assert ok(capsys, "family", "add", "p", "TD", "--defined", "docs:debt.md", "--type", "debt")
    assert set(load().projects["p"].families) == {"SL", "TD"}
    assert ok(capsys, "family", "remove", "p", "SL")
    assert set(load().projects["p"].families) == {"TD"} and "[projects.families.SL]" not in conf.read_text(encoding="utf-8")


def test_a_register_with_a_header_and_no_rows_is_named_and_nothing_is_written_for_it(tmp_path, conf, capsys):
    docs = docs_repo(tmp_path, {"standards.md": "| ID | Claim | Problem shape | Evidence |\n|---|---|---|---|\n",
                                "technical-debt.md": "| ID | Debt | Why it matters |\n|---|---|---|\n"})
    conf.write_text(f'[[projects]]\nname = "p"\ncode = "{tmp_path.as_posix()}"\ndocs = "{docs.as_posix()}"\n', encoding="utf-8")
    before = conf.read_text(encoding="utf-8")
    code, out, err = vyd(capsys, "project", "scan", "p", "--apply")
    assert code == 0 and "Nothing to propose" in out, err
    assert "standards.md:1" in out and "no rows" in out and "signs give no single type" in out and "--type <type>" in out
    assert "technical-debt.md:1" in out and "signs give the type debt" in out
    assert "vyd family add p <PREFIX> --defined docs:technical-debt.md --type debt" in out
    assert conf.read_text(encoding="utf-8") == before
