# SPDX-License-Identifier: MIT
"""Credentials: a remote URL, a credential setting and a staged file are refused by their shape, free
text is scanned for known formats, and a refusal never prints the credential. Every fake credential
is built here at run time, so no file of the repository holds a string that matches a rule."""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
import sys

import pytest

from test_command_extractors import block, built, script
from test_index_core import Words
from test_kb import cloned, sh, world  # noqa: F401  world is a fixture
from test_recipes import World, glue, recipe_text
from vyvid import ask, build as builder, cli, credentials as cr, kb
from vyvid.config import ConfigError, load

ALNUM = "A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q7r8S9t0U1v2"
FAKES = {
    "private-key": "-----BEGIN " + "RSA PRIVATE KEY-----",
    "github-token": "gh" + "p_" + ALNUM[:36],
    "github-pat": "github" + "_pat_" + (ALNUM + ALNUM)[:60],
    "gitlab-token": "glp" + "at-" + ALNUM[:24],
    "aws-key-id": "AK" + "IA" + "ABCDEFGH12345678",
    "slack-token": "xo" + "xb-" + "1234567890-" + ALNUM[:12],
    "anthropic-key": "sk" + "-ant-" + ALNUM[:30],
    "api-key": "s" + "k-" + ALNUM[:40],
    "google-key": "AI" + "za" + ALNUM[:35],
    "bearer-token": "Bea" + "rer " + ALNUM[:30],
}
GITHUB = FAKES["github-token"]


@pytest.mark.parametrize("rule,fake", FAKES.items(), ids=list(FAKES))
def test_each_known_format_is_found_by_line_and_rule_and_redacted(rule, fake):
    text = f"first line\ntoken is {fake} here\n"
    assert cr.scan(text) == [(2, rule)]
    assert fake not in cr.redact(text) and "[redacted]" in cr.redact(text)


@pytest.mark.parametrize("text", [
    "gh" + "p_abc", "an example such as gh" + "p_xxxx is short", "sk" + "-", "the task-force and a desk" + "-lamp-with-a-very-long-name-of-fifty-characters-or-so",
    "s" + "k-short", "a" * 40, "da39a3ee5e6b4b0d3255bfef95601890afd80709", "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "Bea" + "rer of bad news", "AK" + "IA" + "SHORT", "AK" + "IA" + "abcdefgh12345678", "AI" + "za" + "short",
    "Це звичайний український текст про реєстри, рішення та стандарти. Ключ, пароль і токен названі словами.",
])
def test_ordinary_text_hashes_and_short_examples_are_left_alone(text):
    assert cr.scan(text) == [] and cr.redact(text) == text


def test_scan_numbers_lines_and_a_longer_match_is_not_cut():
    fake = FAKES["github-token"] + "Z9"
    assert cr.scan("a\n\nb " + fake) == [(3, "github-token")]
    assert cr.redact(fake) == "[redacted]"


@pytest.mark.parametrize("url", [
    "git@github.com:o/r.git", "git@ssh.dev.azure.com:v3/org/proj/repo", "ssh://git@host/o/r.git", "https://github.com/o/r.git",
    "https://dev.azure.com/org/proj/_git/repo", "github.com/acme/proj", "file:///tmp/r.git", "/tmp/some/remote.git"])
def test_the_usual_remote_forms_are_allowed(url):
    assert cr.remote_problem(url) is None


@pytest.mark.parametrize("url,said", [
    ("https://user:pw@github.com/o/r.git", "password"), ("ssh://git:pw@host/o/r.git", "password"), ("user:pw@host:o/r.git", "password"),
    ("https://" + "gh" + "p_abc@github.com/o/r.git", "user part"), ("https://tim@bitbucket.org/o/r.git", "Remove the user part and use a credential helper"),
    ("http://tim@host/o/r.git", "user part"), ("https://github.com/o/r.git?token=x", "query"), ("https://github.com/o/r.git#frag", "fragment"),
    ("https://github.com/o/" + FAKES["github-token"] + ".git", "shaped like a credential")],
                         ids=lambda value: "case")  # an id would carry the fake credential into the pytest cache
def test_a_remote_holding_a_credential_is_refused_without_naming_it(url, said):
    why = cr.remote_problem(url)
    assert why and said in why and "pw" not in why and "abc" not in why and GITHUB not in why


def load_text(tmp_path, text):
    path = tmp_path / "config.toml"
    path.write_text(text, encoding="utf-8")
    return load(path)


def refused(tmp_path, text) -> str:
    with pytest.raises(ConfigError) as error:
        load_text(tmp_path, text)
    return str(error.value)


def test_a_remote_with_a_credential_is_a_configuration_problem_naming_scope_and_host_only(tmp_path):
    url = f"https://{GITHUB}@github.com/o/r.git"
    said = refused(tmp_path, f'[[domains]]\nname = "tools"\nremote = "{url}"\n\n[[projects]]\nname = "p"\ncode = "{tmp_path.as_posix()}"\n'
                             f'match = {{ remote = ["git@github.com:o/ok.git", "https://tim:pw@gitlab.com/o/r.git"] }}\n')
    assert "domain 'tools': the remote at github.com" in said and "project 'p': the remote at gitlab.com" in said
    assert GITHUB not in said and "pw@" not in said and "https://" not in said


def test_remotes_in_the_usual_forms_load(tmp_path):
    config = load_text(tmp_path, f'[framework]\nkb = "{tmp_path.as_posix()}"\n\n[[domains]]\nname = "tools"\nremote = "git@github.com:o/r.git"\n\n[[projects]]\nname = "p"\n'
                                 f'code = "{tmp_path.as_posix()}"\nmatch = {{ remote = "github.com/acme/proj" }}\n')
    assert config.domains["tools"].remote and config.projects["p"].remotes == ["github.com/acme/proj"]


def test_a_credential_setting_must_name_env_or_keychain(tmp_path):
    secret = "hunter2-" + "plain"
    code = f'code = "{tmp_path.as_posix()}"'
    ex = f'[[projects.extractors]]\nkind = "x"\ncommand = ["x"]\n'
    said = refused(tmp_path, f'[[projects]]\nname = "p"\n{code}\n\n{ex}api_key = "{secret}"\ndb_password = "env:DB"\ncredentials = "keychain:a"\ntoken = "{secret}"\n'
                             f'\n[[projects.recipes]]\nname = "r"\ndescription = "d"\nsteps = [{{ step = "glue", command = ["x"], password = "{secret}" }}]\n'
                             f'\n[projects.uses.d.k]\nclient_secret = "{secret}"\nfine = "{secret}"\n')
    for key in ("api_key", "token", "password", "client_secret"):
        assert f"'{key}' must start with env: or keychain:" in said
    assert secret not in said and "db_password" not in said and "credentials'" not in said and "'fine'" not in said


def test_credential_settings_that_name_a_reference_load(tmp_path):
    load_text(tmp_path, f'[[projects]]\nname = "p"\ncode = "{tmp_path.as_posix()}"\n\n[[projects.extractors]]\nkind = "x"\ncommand = ["x"]\n'
                        'api_key = "env:KEY"\nsecret = "keychain:vyvid/x"\n')


# ---- vyd kb record -------------------------------------------------------------------------------


def no_gitleaks(monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda name: None)


def staged(folder):
    return sh("git", "diff", "--cached", "--name-only", cwd=folder)


def test_record_refuses_a_credential_and_stages_nothing(world, monkeypatch, capsys):
    no_gitleaks(monkeypatch)
    config = cloned(world, 'git = { commit = "auto", push = "auto" }')
    (world["folder"] / "clean.md").write_text("nothing here\n", encoding="utf-8")
    (world["folder"] / "notes.md").write_text(f"a\nkey = {GITHUB}\n", encoding="utf-8")
    (world["folder"] / "sub").mkdir()
    (world["folder"] / "sub" / "deep.md").write_text(FAKES["private-key"] + "\n", encoding="utf-8")
    (result,) = kb.record(config, [str(world["folder"] / "clean.md"), str(world["folder"] / "notes.md"), str(world["folder"] / "sub")], "add")
    assert not result.ok and "nothing staged" in result.text and "stage the file with git yourself" in result.text
    assert "notes.md:2 github-token" in result.text and "sub/deep.md:1 private-key" in result.text
    assert GITHUB not in result.text and "PRIVATE KEY" not in result.text
    assert staged(world["folder"]) == ""
    assert sh("git", "log", "--oneline", cwd=world["folder"]).count("\n") == 0, "nothing was committed"


def test_record_through_the_command_prints_no_credential(world, monkeypatch, capsys):
    no_gitleaks(monkeypatch)
    cloned(world)
    (world["folder"] / "n.md").write_text(GITHUB + "\n", encoding="utf-8")
    capsys.readouterr()
    assert cli.main(["kb", "record", str(world["folder"] / "n.md"), "-m", "x"]) == 1
    out = capsys.readouterr()
    assert "n.md:1 github-token" in out.out and GITHUB not in out.out + out.err
    assert staged(world["folder"]) == ""


def test_record_stages_a_clean_file_as_before(world, monkeypatch):
    no_gitleaks(monkeypatch)
    config = cloned(world)
    (world["folder"] / "register.md").write_text("| NOTE-1 | changed, with a short ghp_abc example and a sha 3b18e512dba79e4c8300dd08aeb37f8e728b8dad |\n", encoding="utf-8")
    (result,) = kb.record(config, [str(world["folder"] / "register.md")], "x")
    assert result.ok and staged(world["folder"]) == "register.md"


def test_a_failing_gitleaks_is_said_and_the_built_in_scan_goes_on(world, monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda name: "/nowhere/gitleaks")
    monkeypatch.setattr(kb, "run_limited", lambda *a, **k: (_ for _ in ()).throw(FileNotFoundError("gone")))
    config = cloned(world)
    (world["folder"] / "n.md").write_text(GITHUB + "\n", encoding="utf-8")
    notes, refusal = kb.record(config, [str(world["folder"] / "n.md")], "x")
    assert notes.ok and "gitleaks could not be run" in notes.text and "only the built-in scan was done" in notes.text
    assert not refusal.ok and "n.md:1 github-token" in refusal.text and GITHUB not in notes.text + refusal.text


@pytest.mark.skipif(shutil.which("gitleaks") is None, reason="gitleaks is not installed")
def test_gitleaks_where_installed_also_refuses_and_prints_no_secret(world):
    config = cloned(world)
    (world["folder"] / "n.md").write_text(f"x\n{GITHUB}\n", encoding="utf-8")
    (result,) = kb.record(config, [str(world["folder"] / "n.md")], "x")
    assert not result.ok and "n.md:2 github-pat" in result.text and "n.md:2 github-token" in result.text
    assert GITHUB not in result.text and staged(world["folder"]) == ""


# ---- redaction of what commands print --------------------------------------------------------------


def test_a_token_glue_prints_never_reaches_the_briefing_or_the_error(tmp_path):
    out = glue(tmp_path, f"import json\nprint(json.dumps([{{'id': 'G-1', 'claim': 'key {GITHUB} end'}}]))\n", "out")
    err = glue(tmp_path, f"import sys\nsys.stderr.write('bad {GITHUB} ' + 'x' * 50)\nsys.exit(2)\n", "err")
    w = World(tmp_path, recipe_text("out", out) + recipe_text("err", err))
    (entry,) = recipes_run(w, "out")
    assert entry["claim"] == "key [redacted] end"
    with pytest.raises(Exception) as error:
        w.run("err")
    assert "[redacted]" in str(error.value) and GITHUB not in str(error.value) and "gh" + "p_" not in str(error.value)


def recipes_run(w, name):
    from vyvid import recipes
    return recipes.run(w.ask, recipes.available(w.stack)[name], "ledger")


def test_a_token_a_command_extractor_prints_or_reports_is_redacted(tmp_path):
    failing = script(tmp_path / "code", f"sys.stderr.write('oops {GITHUB}')\nsys.exit(1)\n", "fail.py")
    reporting = script(tmp_path / "code", f"finish(problems=['saw {GITHUB}'], findings=['and {GITHUB}'])\n", "report.py")
    out, _ = built(tmp_path, block("fail", failing.as_posix()), block("report", reporting.as_posix()))
    mine = [p for p in out.problems + out.findings if "extractor" in p or "saw" in p or "and" in p]
    assert any("oops [redacted]" in p for p in mine) and any("saw [redacted]" in p for p in mine) and any("and [redacted]" in p for p in mine)
    assert GITHUB not in "\n".join(out.problems + out.findings)


# ---- files at rest ---------------------------------------------------------------------------------

posix = pytest.mark.skipif(os.name != "posix", reason="owner-only modes mean little elsewhere")


def mode(path):
    return stat.S_IMODE(path.stat().st_mode)


@posix
def test_the_store_folder_is_created_owner_only_and_an_existing_one_is_tightened(tmp_path):
    w = World(tmp_path)
    (tmp_path / "idx").mkdir(exist_ok=True)
    (tmp_path / "idx").chmod(0o755)
    builder.build(w.config, w.project, model=Words())
    assert mode(tmp_path / "idx") == 0o700


@posix
def test_the_logs_are_created_owner_only(tmp_path):
    w = World(tmp_path)
    ask.log_ask(w.ask, "find", "q", 0.1, [])
    ask.log_miss(w.ask, "find q")
    assert mode(w.ask.ask_log) == 0o600 and mode(w.ask.miss_log) == 0o600


def test_logs_false_writes_no_line_and_misses_and_gap_say_so(tmp_path, capsys):
    w = World(tmp_path, framework="logs = false")
    assert w.config.logs is False
    ask.log_ask(w.ask, "find", "q", 0.1, [])
    ask.log_miss(w.ask, "find q")
    assert ask.gap(w.ask, "something", ["STD-1"]) == 0
    assert "logging is off" in capsys.readouterr().out and not w.ask.ask_log.exists() and not w.ask.miss_log.exists()
    ask.misses(w.ask, 20)
    assert "logging is off" in capsys.readouterr().out


def test_logs_default_to_on_and_must_be_true_or_false(tmp_path):
    assert load_text(tmp_path, "").logs is True
    assert "logs must be true or false" in refused(tmp_path, '[framework]\nlogs = "no"\n')
