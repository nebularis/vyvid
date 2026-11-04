# SPDX-License-Identifier: MIT
"""A project whose documents lie outside its code: its entries are private, its git policy is its own, its board
reads one set of documents, and no command writes into the code repository. Real git repositories and linked
worktrees under a temporary folder, a stand-in model and no network."""

from __future__ import annotations

import subprocess
from pathlib import Path

import numpy as np
import pytest

from test_checkouts import git, quiet_git  # noqa: F401  quiet_git is an autouse fixture
from vyvid import ask, cli, embed
from vyvid import build as builder
from vyvid.config import ConfigError, load, read_project_file
from vyvid.resolve import bind_in, forget, private_entry
from vyvid.symbols import store

CONFIG = """
[framework]
store = "{store}"

[[projects]]
name = "proj"
code = "{code}"
docs = "{docs}"
contract = "docs:CONTRACT.md"
{extra}
[projects.match]
remote = "github.com/acme/proj"

[projects.families]
STD = {{ defined = "code:STANDARDS.md", type = "standard" }}
PD = {{ defined = "docs:INDEX.md", type = "slice" }}
PDQ = {{ pattern = 'PD-Q\\d+', defined = "docs:plans", rule = "question", type = "question" }}
MIX = {{ defined = ["docs:mix.md", "code:mix.md"], type = "note", removable = true }}

[[projects.symbols]]
language = "haskell"
paths = ["code:src/**/*.hs"]

[[projects.recipes]]
name = "ask"
description = "When asking about a ledger"
steps = [{{ step = "find", words = "{{question}}", limit = 3 }}]
"""
STANDARDS = "| ID | Claim |\n|---|---|\n| STD-1 | A ledger is kept per key. |\n"
INDEX = ("| Slice | Deliverable | State | Blocked on |\n|---|---|---|---|\n"
         "| PD-0 | Set up the ledger documents. | built 2026-11-04 | |\n"
         "| PD-1 | Draft the ledger retry plan. | building 2026-11-04 | PD-0 |\n"
         "| PD-2 | A later ledger slice. | planned | PD-1 |\n")
PLAN = "**PD-Q1. Which retry policy for a ledger?** Open.\n"
MIX = "| ID | Claim |\n|---|---|\n| MIX-{n} | Ledger text. |\n"
HS = "module Demo ({names}) where\n\n-- | Start a ledger process.\n{first} :: Int -> IO ()\n{first} n = return ()\n"
CREDENTIAL = "gh" + "p_" + "A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q7r8"


class Words:
    AXES = ("ledger", "process", "slice", "graph")

    def embed(self, texts):
        v = np.array([[t.lower().count(a) + 0.01 for a in self.AXES] for t in texts], dtype=np.float32)
        return v / np.linalg.norm(v, axis=1, keepdims=True)

    def question(self, text):
        return self.embed([text])[0]


def put(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def out(folder: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(folder), *args], check=True, capture_output=True, text=True).stdout.strip()


def snapshot(*folders: Path) -> list[str]:
    return [out(f, "status", "--short", "--ignored") for f in folders]


class World:
    def __init__(self, tmp_path, monkeypatch, extra="", docs_repo=True):
        self.tmp, self.code, self.docs = tmp_path, tmp_path / "code", tmp_path / "docs"
        put(self.code / "STANDARDS.md", STANDARDS)
        put(self.code / "src" / "Demo.hs", HS.format(names="mainOnly", first="mainOnly"))
        put(self.code / "notes.md", "start\n")
        for name, text in (("INDEX.md", INDEX), ("plans/plan.md", PLAN), ("CONTRACT.md", "The contract.\n"), ("mix.md", MIX.format(n=1)), ):
            put(self.docs / name, text)
        put(self.code / "mix.md", MIX.format(n=2))
        git(self.code, "init", "-q", "-b", "main")
        git(self.code, "remote", "add", "origin", "git@github.com:acme/proj.git")
        git(self.code, "add", "-A")
        git(self.code, "commit", "-q", "-m", "x")
        if docs_repo:
            git(self.docs, "init", "-q", "-b", "main")
            git(self.docs, "add", "-A")
            git(self.docs, "commit", "-q", "-m", "x")
        self.config_path = tmp_path / "config.toml"
        self.write(extra)
        monkeypatch.setenv("VYVID_CONFIG", str(self.config_path))
        monkeypatch.setattr(embed, "Model", lambda spec: Words())

    def write(self, extra="", docs=None):
        text = CONFIG.format(store=(self.tmp / "idx").as_posix(), code=self.code.as_posix(), docs=docs or self.docs.as_posix(), extra=extra)
        self.config_path.write_text(text, encoding="utf-8")
        self.config = load(self.config_path)
        self.project = self.config.projects["proj"]

    def stage(self, text: str, name="notes.md"):
        put(self.code / name, text)
        git(self.code, "add", "-A")

    def check(self, *args):
        return cli.main(["check", "citations", "--in", str(self.code), *args])


@pytest.fixture
def w(tmp_path, monkeypatch):
    return World(tmp_path, monkeypatch)


# ---- Private documents and the citation check -----------------------------------------------------


def test_documents_outside_the_code_are_private_unless_declared_public(tmp_path, monkeypatch):
    w = World(tmp_path, monkeypatch)
    assert w.project.private_docs
    w.write('docs_visibility = "public"')
    assert not w.project.private_docs
    w.write(docs="code:docs")
    assert not w.project.private_docs, "inside the code repository there is nothing to keep apart"
    with pytest.raises(ConfigError, match="docs_visibility: visibility is 'hidden'"):
        w.write('docs_visibility = "hidden"')


def test_an_entry_is_private_by_the_file_that_defines_it_and_not_by_its_family(w):
    put(w.code / "mix.md", MIX.format(n=2) + "| MIX-1 | Ledger text, also in code. |\n")
    forget()
    p = w.project
    assert [private_entry(p, x) for x in ("PD-0", "PD-Q1", "STD-1", "MIX-1", "MIX-2", "PD-99", "NOPE-1")] == [True, True, False, False, False, False, False], \
        "MIX-1 is defined in both folders, so it stays public. An entry no file defines is not private"
    w.write('docs_visibility = "public"')
    assert not private_entry(w.project, "PD-0")


def test_a_staged_line_citing_a_slice_or_a_question_is_refused_bare_or_qualified(w, capsys):
    w.stage("start\nsee PD-0 here\nand proj:PD-Q1 there\nand STD-1 is public\nPD-99 names nothing\n")
    assert w.check("--staged") == 1
    printed = capsys.readouterr().out
    assert "notes.md:2: cites proj:PD-0, which is private" in printed
    assert "notes.md:3: cites proj:PD-Q1, which is private" in printed
    assert "STD-1" not in printed and "PD-99" not in printed


def test_a_clean_staged_change_passes_and_private_documents_may_cite_each_other(w, capsys):
    w.stage("start\nsee STD-1\n")
    put(w.docs / "INDEX.md", INDEX + "\nPD-1 waits for PD-0\n")
    git(w.docs, "add", "-A")
    assert w.check("--staged") == 0
    assert "none cites" in capsys.readouterr().out


def test_a_message_is_checked_as_a_file_outside_the_staged_diff(w, capsys):
    bad, clean = put(w.tmp / "bad.txt", "Fix the retry\n\nSee PD-0 and PD-Q1.\n"), put(w.tmp / "clean.txt", "Fix the retry\n\nSee STD-1.\n")
    assert w.check("--message", str(bad)) == 1
    printed = capsys.readouterr().out
    assert "bad.txt:3: cites proj:PD-0, which is private" in printed and "proj:PD-Q1" in printed
    assert w.check("--message", str(clean)) == 0
    assert w.check("--message", str(w.tmp / "absent.txt")) == 2
    assert w.check() == 2


def test_find_labels_an_entry_of_the_private_documents_and_no_other(w, capsys):
    assert cli.main(["find", "ledger", "--kind", "slice,standard", "--in", str(w.code)]) == 0
    lines = capsys.readouterr().out.splitlines()
    under = lambda ident: lines[next(i for i, l in enumerate(lines) if l.split()[1:2] == [ident]) + 1]
    assert "Private, so this project's public text never cites it." in under("PD-1")
    assert "Private" not in under("STD-1")


# ---- The git policy of private documents ----------------------------------------------------------


def record(w, *paths, message="Add a note"):
    return cli.main(["docs", "record", *map(str, paths), "-m", message, "--in", str(w.code)])


def test_a_project_file_may_not_set_the_git_policy_and_the_user_entry_is_checked(w, tmp_path):
    file = put(tmp_path / "repo" / "vyvid.toml", '[project]\nname = "x"\ngit = { docs = { commit = "auto" } }\n')
    assert any("sets 'git', which only the user's configuration may" in p for p in read_project_file(file)[1])
    for bad, why in (('git = { docs = { commit = "manual", push = "auto" } }', "nothing would be pushed"), ('git = { docs = { commit = "sometimes" } }', "not one of manual, auto"),
                     ('git = { pull = "daily" }', "docs = { commit, push } alone"), ('git = { docs = { pull = "daily" } }', "docs = { commit, push } alone")):
        with pytest.raises(ConfigError, match=why):
            w.write(bad)


def test_record_under_manual_stages_and_commits_nothing(w, capsys):
    note = put(w.docs / "notes.md", "a note\n")
    assert record(w, note) == 0
    assert "staged notes.md. Commit is manual" in capsys.readouterr().out
    assert out(w.docs, "diff", "--cached", "--name-only") == "notes.md" and out(w.docs, "log", "--format=%s") == "x"
    assert out(w.code, "status", "--short") == "", "nothing reached the code repository"


def test_record_commits_under_auto_and_pushes_under_auto(w, capsys):
    remote = w.tmp / "remote.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(remote)], check=True)
    git(w.docs, "remote", "add", "origin", str(remote))
    git(w.docs, "push", "-q", "-u", "origin", "main")
    w.write('git = { docs = { commit = "auto", push = "manual" } }')
    assert record(w, put(w.docs / "a.md", "a\n")) == 0
    assert "committed a.md. Push is manual" in capsys.readouterr().out
    assert out(w.docs, "log", "-1", "--format=%s") == "Add a note" and out(remote, "log", "--format=%s", "main") == "x"
    w.write('git = { docs = { commit = "auto", push = "auto" } }')
    assert record(w, put(w.docs / "b.md", "b\n"), message="Add b") == 0
    assert "committed and pushed b.md" in capsys.readouterr().out
    assert out(remote, "log", "-1", "--format=%s", "main") == "Add b"


def test_record_refuses_a_path_outside_the_documents_a_credential_and_an_ignored_file(w, capsys):
    w.write('git = { docs = { commit = "auto", push = "manual" } }')
    assert record(w, w.code / "notes.md") == 1
    assert "is outside the documents folder" in capsys.readouterr().out
    assert record(w, put(w.docs / "secret.md", f"token {CREDENTIAL}\n")) == 1
    printed = capsys.readouterr().out
    assert "secret.md:1" in printed and CREDENTIAL not in printed and out(w.docs, "diff", "--cached", "--name-only") == ""
    put(w.docs / ".gitignore", "*.log\n")
    assert record(w, put(w.docs / "x.log", "x\n")) == 1
    assert "is ignored by git" in capsys.readouterr().out
    assert out(w.docs, "log", "--format=%s") == "x"


def test_documents_in_no_repository_keep_nothing_in_git_and_exit_zero(tmp_path, monkeypatch, capsys):
    w = World(tmp_path, monkeypatch, docs_repo=False)
    assert record(w, put(w.docs / "n.md", "n\n")) == 0
    assert "in no git repository, so nothing is kept in git and nothing was done" in capsys.readouterr().out


def test_documents_inside_the_code_repository_are_not_recorded_by_it(w, capsys):
    w.write(docs="code:docs")
    assert record(w, put(w.code / "docs" / "n.md", "n\n")) == 1
    assert "is in the code repository" in capsys.readouterr().out
    assert out(w.code, "diff", "--cached", "--name-only") == ""


# ---- The board ----------------------------------------------------------------------------------


def test_the_board_lists_the_slices_in_order_and_filters_by_the_first_word_of_the_state(w, capsys):
    assert cli.main(["board", str(w.code)]) == 0
    rows = [l.split() for l in capsys.readouterr().out.splitlines()[2:]]
    assert [r[0] for r in rows] == ["PD-0", "PD-1", "PD-2"] and rows[1][-3:] == ["building", "2026-11-04", "PD-0"]
    assert cli.main(["board", str(w.code), "--state", "building"]) == 0
    assert [l.split()[0] for l in capsys.readouterr().out.splitlines()[2:]] == ["PD-1"]
    assert cli.main(["board", str(w.code), "--state", "build"]) == 0
    assert "no slice of project proj is in state build" in capsys.readouterr().out


def test_a_project_with_no_slice_family_or_no_project_gets_a_plain_message(tmp_path, monkeypatch, capsys):
    w = World(tmp_path, monkeypatch)
    text = w.config_path.read_text(encoding="utf-8").replace('PD = { defined = "docs:INDEX.md", type = "slice" }', "")
    w.config_path.write_text(text, encoding="utf-8")
    assert cli.main(["board", str(w.code)]) == 0
    assert "declares no family of type slice" in capsys.readouterr().out
    assert cli.main(["board", str(tmp_path)]) == 0
    assert "no project claims" in capsys.readouterr().out


def test_find_reaches_a_slice_by_identifier_and_by_kind(w, capsys):
    assert cli.main(["find", "PD-1", "--in", str(w.code)]) == 0
    assert "PD-1" in capsys.readouterr().out
    assert cli.main(["find", "ledger retry plan", "--kind", "slice", "--in", str(w.code)]) == 0
    assert "PD-1" in capsys.readouterr().out


# ---- Nothing is written into the code repository ---------------------------------------------------


def test_no_command_writes_into_the_code_repository_or_its_worktree(w, capsys):
    git(w.code, "worktree", "add", "-q", "-b", "feat", str(w.tmp / "wt"))
    wt = w.tmp / "wt"
    put(wt / "src" / "Branch.hs", HS.format(names="branchOnly", first="branchOnly"))
    put(wt / "STANDARDS.md", STANDARDS + "| STD-2 | A graph is slow. |\n")
    git(wt, "add", "-A")
    git(wt, "commit", "-q", "-m", "b")
    message = put(w.tmp / "msg.txt", "A change\n")
    before = snapshot(w.code, wt)
    for folder in (w.code, wt):
        for args in (["context", str(folder), "--no-pull"], ["build", str(folder)], ["find", "ledger", "--in", str(folder)],
                     ["find", "ledger process", "--kind", "symbol", "--in", str(folder)], ["read", "PD-1", "--in", str(folder)], ["board", str(folder)],
                     ["recipe", "run", "ask", "a ledger", "--in", str(folder)], ["check", "identifiers", str(folder)],
                     ["check", "citations", "--staged", "--in", str(folder)], ["check", "citations", "--message", str(message), "--in", str(folder)]):
            assert cli.main(args) == 0, args
    capsys.readouterr()
    assert snapshot(w.code, wt) == before


def test_a_linked_worktree_is_answered_from_its_own_code_and_the_one_documents_folder(w):
    git(w.code, "worktree", "add", "-q", "-b", "feat", str(w.tmp / "wt"))
    wt = w.tmp / "wt"
    put(wt / "src" / "Branch.hs", HS.format(names="branchOnly", first="branchOnly"))
    put(wt / "STANDARDS.md", STANDARDS + "| STD-2 | A graph is slow. |\n")
    git(wt, "add", "-A")
    git(wt, "commit", "-q", "-m", "b")
    config, linked = bind_in(w.config, wt)
    assert linked.checkout == wt.resolve() and linked.docs == w.docs and linked.private_docs, "the documents folder is shared"
    _, main = bind_in(w.config, w.code)
    names = {}
    for label, c, p in (("wt", config, linked), ("main", w.config, main)):
        builder.build(c, p, model=Words())
        db = store.connect(builder.store_dir(c, p) / store.DB)
        names[label] = {r["name"] for r in store.rows(db)}
        db.close()
    assert names == {"wt": {"mainOnly", "branchOnly"}, "main": {"mainOnly"}}
    assert builder.store_dir(config, linked) != builder.store_dir(w.config, main)
    ids = lambda c, p: {r["id"] for r in ask.candidates(ask.open_stack(c, p.checkout or p.code, model=Words()), {"Slice", "Standard"}, set(), set())}
    assert {"STD-2", "PD-0"} <= ids(config, linked) and "STD-2" not in ids(w.config, main) and "PD-0" in ids(w.config, main)


def test_private_documents_in_no_repository_do_not_stop_the_identifier_check(tmp_path, monkeypatch, capsys):
    w = World(tmp_path, monkeypatch, docs_repo=False)
    assert cli.main(["check", "identifiers", str(w.code)]) == 0
    out = capsys.readouterr().out
    assert "identifier check passed" in out and "not read: " in out, "a pass says what it could not read"
