# SPDX-License-Identifier: MIT
"""The store across scopes: what a question may see, how the scopes rank, what a row specialises or
overrides, and the check that a public project cites no private entry."""

from __future__ import annotations

import os
import subprocess
from contextlib import contextmanager

import pyoxigraph as ox
import pytest

from test_ask import table, under_row
from test_index_core import Words
from vyvid import ask, cli, embed
from vyvid import build as builder
from vyvid.config import ConfigError, load
from vyvid.model import KI, RDF_TYPE, RDFS_LABEL, index_graph, ki, node
from vyvid.resolve import layers

CONFIG = """
[framework]
store = "STORE"

[[domains]]
name = "wide"
path = "WIDE"
families = { WIDE = {} }

[[domains]]
name = "deep"
path = "DEEP"
parents = ["wide"]
visibility = "public"
families = { DEEP = {} }

[[domains]]
name = "secret"
path = "SECRET"
families = { RULE = {} }

[[domains]]
name = "open"
path = "OPEN"
visibility = "public"
families = { OPEN = {} }

[[projects]]
name = "proj"
code = "CODE"
domains = ["deep"]
visibility = "VISIBILITY"
delegates = { RULE = "secret" }

[projects.families]
STD = {}

[[projects]]
name = "other"
code = "OTHER"
domains = ["open", "secret"]
families = { OTH = {} }
"""


class Scopes:
    """A configuration of four domains and two projects, and a store the tests fill with quads."""

    def __init__(self, tmp_path, visibility: str = "public", bound: str = "proj"):
        self.tmp = tmp_path
        text = CONFIG.replace("STORE", (tmp_path / "idx").as_posix()).replace("VISIBILITY", visibility)
        for name in ("WIDE", "DEEP", "SECRET", "OPEN", "CODE", "OTHER"):
            text = text.replace(f'"{name}"', f'"{(tmp_path / name.lower()).as_posix()}"')
        (tmp_path / "config.toml").write_text(text, encoding="utf-8")
        self.config = load(tmp_path / "config.toml")
        self.project = self.config.projects[bound]
        self.store = ox.Store()
        self.ask = ask.Asker(self.config, self.project, layers(self.config, self.project), tmp_path / "idx", self.store, Words())

    def entry(self, scope, ident, claim, kind="Standard"):
        n = node(scope, ident)
        self.store.extend([ox.Quad(s, p, o, index_graph(scope)) for s, p, o in (
            (n, ki("identifier"), ox.Literal(ident)), (n, ki("claim"), ox.Literal(claim)),
            (n, RDF_TYPE, ki(kind)), (n, RDFS_LABEL, ox.Literal(ident.lower())))])

    def edge(self, scope, ident, prop, other_scope, other):
        self.store.add(ox.Quad(node(scope, ident), ki(prop), node(other_scope, other), index_graph(scope)))

    def ready(self, scope: str = ""):
        entries = {str(r["n"].value): embed.join_text([r["label"] and r["label"].value, r["claim"].value, None, None])
                   for r in self.store.query(builder.TEXTS)}
        embed.build(entries, self.ask.directory, self.config.embedding, self.ask.model)
        if scope:
            self.ask.choose(scope)

    def find(self, words="ledger", kinds=(), limit=8):
        return ask.find(self.ask, words, set(kinds), set(), set(), limit, None)


@pytest.fixture
def s(tmp_path):
    return Scopes(tmp_path)


def ids(out: str) -> list[str]:
    return [row[1] for row in table(out)]


# ---- Visibility ----------------------------------------------------------------------------------


def test_visibility_defaults_by_kind_and_an_unknown_one_is_refused(tmp_path):
    config = Scopes(tmp_path).config
    assert (config.general.visibility, config.domains["wide"].visibility, config.domains["open"].visibility,
            config.projects["proj"].visibility) == ("public", "private", "public", "public")
    (tmp_path / "wide").mkdir()
    (tmp_path / "wide" / "domain.toml").write_text('visibility = "public"\n', encoding="utf-8")
    assert load(tmp_path / "config.toml").domains["wide"].visibility == "public", "a manifest may say it"
    text = (tmp_path / "config.toml").read_text(encoding="utf-8").replace('visibility = "public"', 'visibility = "hidden"', 1)
    (tmp_path / "bad.toml").write_text(text, encoding="utf-8")
    with pytest.raises(ConfigError) as error:
        load(tmp_path / "bad.toml")
    assert any("domain 'deep': visibility is 'hidden', not one of public, private" in p for p in error.value.problems)


# ---- What a question may see ---------------------------------------------------------------------


def test_a_scope_outside_the_stack_is_never_shown_unless_named(s, capsys):
    s.entry("proj", "STD-1", "ledger rule")
    s.entry("secret", "RULE-1", "ledger secret rule")
    s.ready()
    s.find()
    assert ids(capsys.readouterr().out) == ["STD-1"]
    s.ask.choose("secret")
    s.find()
    assert set(ids(capsys.readouterr().out)) == {"STD-1", "secret:RULE-1"}
    s.ask.choose("only:secret")
    s.find()
    assert ids(capsys.readouterr().out) == ["secret:RULE-1"]


def test_an_unknown_scope_is_an_argument_error_naming_the_configured_ones(s):
    with pytest.raises(ValueError, match="--scope nowhere is not one of general, wide, deep, secret, open, proj, other"):
        s.ask.choose("only:nowhere")
    with pytest.raises(ValueError, match="names no scope"):
        s.ask.choose("only:")


def test_read_node_and_reaches_follow_the_scope_too(s):
    s.entry("secret", "RULE-1", "ledger secret rule")
    assert ask.canonical_of(s.ask, "secret:RULE-1") is None
    s.ask.choose("secret")
    assert ask.canonical_of(s.ask, "secret:RULE-1") == ("secret", "RULE-1")


def test_a_private_scope_in_the_stack_is_flagged_and_not_to_be_cited(tmp_path, capsys):
    s = Scopes(tmp_path)
    s.entry("wide", "WIDE-1", "ledger wide rule")
    s.entry("deep", "DEEP-1", "ledger deep rule")
    s.entry("proj", "STD-1", "ledger rule")
    s.ready()
    s.find()
    out = capsys.readouterr().out
    rows = {row[1]: row for row in table(out)}
    assert rows["wide:WIDE-1"][4] == "P" and rows["deep:DEEP-1"][4] == "" and rows["STD-1"][4] == ""
    assert "Private, so this project's public text never cites it." in under_row(out, "wide:WIDE-1")
    assert "P the entry is private, so this project's public text never cites it." in out


def test_a_private_project_reads_its_private_domains_without_that_warning(tmp_path, capsys):
    s = Scopes(tmp_path, visibility="private")
    s.entry("wide", "WIDE-1", "ledger wide rule")
    s.ready()
    s.find()
    out = capsys.readouterr().out
    assert "P the entry is private." in out and "never cites" not in out


# ---- Ranking -------------------------------------------------------------------------------------


def test_at_equal_meaning_the_project_ranks_above_a_domain_and_a_deeper_domain_above_a_wider(s, capsys):
    for scope, ident in (("wide", "WIDE-1"), ("deep", "DEEP-1"), ("proj", "STD-1")):
        s.entry(scope, ident, "ledger rule")
    s.entry("deep", "DEEP-2", "ledger rule graph graph")
    s.ready()
    s.find()
    assert ids(capsys.readouterr().out) == ["STD-1", "deep:DEEP-1", "wide:WIDE-1", "deep:DEEP-2"], "meaning still decides first"


def test_a_scope_added_by_name_ranks_below_the_stack(s, capsys):
    s.entry("secret", "RULE-1", "ledger rule")
    s.entry("wide", "WIDE-1", "ledger rule")
    s.ready("secret")
    s.find()
    assert ids(capsys.readouterr().out) == ["wide:WIDE-1", "secret:RULE-1"]


# ---- Specialising and overriding -----------------------------------------------------------------


def test_a_row_that_specialises_another_shows_it_beneath_and_it_has_no_row_of_its_own(s, capsys):
    s.entry("wide", "WIDE-1", "ledger rule in general")
    s.entry("deep", "DEEP-1", "ledger rule graph graph")
    s.entry("proj", "STD-1", "ledger rule graph")
    s.edge("proj", "STD-1", "specialises", "deep", "DEEP-1")
    s.edge("deep", "DEEP-1", "specialises", "wide", "WIDE-1")
    s.ready()
    s.find()
    out = capsys.readouterr().out
    assert ids(out) == ["STD-1"]
    line = under_row(out, "STD-1")
    assert "Specialises deep:DEEP-1: ledger rule graph graph" in line and "Specialises wide:WIDE-1: ledger rule in general" in line


def test_a_specialised_row_stays_a_row_unless_its_specialising_row_is_an_answer_too(s, capsys):
    s.entry("wide", "WIDE-1", "ledger rule")
    s.entry("proj", "STD-1", "ledger rule graph", kind="Pattern")
    s.edge("proj", "STD-1", "specialises", "wide", "WIDE-1")
    s.ready()
    s.find(kinds={"Standard"})
    assert ids(capsys.readouterr().out) == ["wide:WIDE-1"]
    s.find(kinds={"Pattern"})
    out = capsys.readouterr().out
    assert ids(out) == ["STD-1"] and "Specialises" not in out


def test_a_circle_of_specialisations_hides_no_row(s, capsys):
    s.entry("deep", "DEEP-1", "ledger rule")
    s.entry("proj", "STD-1", "ledger rule")
    s.edge("proj", "STD-1", "specialises", "deep", "DEEP-1")
    s.edge("deep", "DEEP-1", "specialises", "proj", "STD-1")
    s.ready()
    s.find()
    assert len(ids(capsys.readouterr().out)) == 1, "one folds under the other and the second edge is left"


def test_an_overridden_row_is_hidden_unless_its_scope_is_named(s, capsys):
    s.entry("deep", "DEEP-1", "ledger rule")
    s.entry("proj", "STD-1", "ledger rule graph")
    s.edge("proj", "STD-1", "overrides", "deep", "DEEP-1")
    s.ready()
    s.find()
    assert ids(capsys.readouterr().out) == ["STD-1"]
    s.ask.choose("deep")
    s.find()
    assert set(ids(capsys.readouterr().out)) == {"STD-1", "deep:DEEP-1"}


# ---- The citation check --------------------------------------------------------------------------


def run(folder, *args):
    env = {**os.environ, "GIT_CONFIG_GLOBAL": str(folder.parent / "empty.gitconfig"), "GIT_CONFIG_SYSTEM": os.devnull,
           "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com"}
    subprocess.run(["git", *args], cwd=folder, env=env, check=True, capture_output=True)


@contextmanager
def bound(tmp_path, monkeypatch, visibility="public"):
    s = Scopes(tmp_path, visibility)
    (tmp_path / "empty.gitconfig").write_text("", encoding="utf-8")
    code = tmp_path / "code"
    code.mkdir()
    run(code, "init", "-q")
    (code / "notes.md").write_text("start\n", encoding="utf-8")
    run(code, "add", ".")
    run(code, "commit", "-q", "-m", "start")
    monkeypatch.setenv("VYVID_CONFIG", str(tmp_path / "config.toml"))
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(tmp_path / "empty.gitconfig"))
    yield s, code


def check(code, *args):
    return cli.main(["check", "citations", "--in", str(code), *args])


def test_a_public_project_staging_a_private_citation_is_refused(tmp_path, monkeypatch, capsys):
    with bound(tmp_path, monkeypatch) as (_, code):
        (code / "notes.md").write_text("start\nsee secret:RULE-1 for why\nand RULE-2 bare\nand open:OPEN-3 is public\n", encoding="utf-8")
        run(code, "add", ".")
        assert check(code, "--staged") == 1
        out = capsys.readouterr().out
        assert "notes.md:2: cites secret:RULE-1, which is private" in out
        assert "notes.md:3: cites secret:RULE-2, which is private" in out, "a bare id delegated to a private scope"
        assert "OPEN-3" not in out


def test_only_what_is_staged_is_checked_and_a_public_citation_passes(tmp_path, monkeypatch, capsys):
    with bound(tmp_path, monkeypatch) as (_, code):
        (code / "notes.md").write_text("start\nsee open:OPEN-3\n", encoding="utf-8")
        run(code, "add", ".")
        (code / "notes.md").write_text("start\nsee open:OPEN-3\nsecret:RULE-1 but unstaged\n", encoding="utf-8")
        assert check(code, "--staged") == 0
        assert "none cites" in capsys.readouterr().out
        assert check(code, str(code / "notes.md")) == 1, "every line of a named path"
        assert "notes.md:3: cites secret:RULE-1" in capsys.readouterr().out


def test_a_private_project_or_an_unclaimed_folder_is_not_checked(tmp_path, monkeypatch, capsys):
    with bound(tmp_path, monkeypatch, "private") as (_, code):
        (code / "notes.md").write_text("secret:RULE-1\n", encoding="utf-8")
        run(code, "add", ".")
        assert check(code, "--staged") == 0
        assert "is private" in capsys.readouterr().out
        assert check(tmp_path / "elsewhere", "--staged") == 0
        assert "no project claims" in capsys.readouterr().out
