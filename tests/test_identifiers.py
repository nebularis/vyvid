# SPDX-License-Identifier: MIT
"""``vyd check identifiers`` over real git repositories, and the ``defined_only`` family key it shares with
mention matching."""

from __future__ import annotations

import json
import os
import subprocess

import pytest

from vyvid import cli
from vyvid.config import ConfigError, load
from vyvid.resolve import forget, mentions, resolve

STANDARDS = "| ID | Claim |\n|---|---|\n| STD-1 | **One.** |\n| STD-2 | **Two.** |\n"
FAMILIES = 'STD = { defined = "docs:standards.md", type = "standard" }\n'


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def git(folder, *args, when=None):
    env = {**os.environ, "GIT_AUTHOR_DATE": when, "GIT_COMMITTER_DATE": when} if when else None
    subprocess.run(["git", "-C", str(folder), "-c", "user.name=t", "-c", "user.email=t@example.com", *args], check=True, capture_output=True, env=env)


def commit(folder, when="2026-01-01T00:00:00Z"):
    git(folder, "add", "-A")
    git(folder, "commit", "-q", "-m", "c", when=when)
    return subprocess.run(["git", "-C", str(folder), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()


class Repo:
    """A project in a git repository with one register, and a configuration for it."""

    def __init__(self, tmp_path, monkeypatch, notes="No mention.\n", families=FAMILIES, extra="", standards=STANDARDS):
        self.tmp, self.code = tmp_path, tmp_path / "code"
        write(self.code / "docs/standards.md", standards)
        write(self.code / "docs/notes.md", notes)
        write(self.code / ".gitignore", "private/\n")
        git(self.code, "init", "-q", "-b", "main")
        self.head = commit(self.code)
        self.config(families, extra)
        monkeypatch.setenv("VYVID_CONFIG", str(tmp_path / "config.toml"))

    def config(self, families=FAMILIES, extra="", domains=""):
        write(self.tmp / "config.toml", f'{domains}\n[[projects]]\nname = "proj"\ncode = "{self.code}"\n{extra}\n[projects.families]\n{families}')

    def check(self, capsys, *args):
        forget()
        code = cli.main(["check", "identifiers", str(self.code), *args])
        return code, capsys.readouterr().out

    def report(self, capsys):
        code, out = self.check(capsys, "--json")
        return code, json.loads(out)


def test_a_resolved_mention_passes_and_an_unresolved_one_fails(tmp_path, monkeypatch, capsys):
    repo = Repo(tmp_path, monkeypatch, notes="See STD-1 and STD-2.\n")
    code, out = repo.check(capsys)
    assert code == 0 and out.startswith("identifier check passed: 2 identifiers mentioned in 2 files, 0 unresolved")
    write(repo.code / "docs/notes.md", "See STD-1 and STD-9.\nSTD-9 again.\n")
    commit(repo.code)
    code, out = repo.check(capsys)
    assert code == 1 and "ERROR: STD-9 (STD) is mentioned but never defined: docs/notes.md:1, docs/notes.md:2" in out
    code, report = repo.report(capsys)
    assert code == 1 and [(u["identifier"], len(u["sites"])) for u in report["unresolved"]] == [("STD-9", 2)]


def test_another_spelling_of_a_defined_identifier_is_a_variant_and_never_fails(tmp_path, monkeypatch, capsys):
    repo = Repo(tmp_path, monkeypatch, notes="STD 1 and STD-1.\n", families='STD = { pattern = "STD[- ]\\\\d+", defined = "docs:standards.md", type = "standard" }\n')
    code, out = repo.check(capsys, "--all")
    assert code == 0 and "variant: STD 1 -> STD-1 (STD)" in out
    assert [v["canonical"] for v in repo.report(capsys)[1]["variants"]] == ["STD-1"]


def test_a_removable_family_is_reported_and_never_failed(tmp_path, monkeypatch, capsys):
    repo = Repo(tmp_path, monkeypatch, notes="TD-5 was rehomed.\n",
                families=FAMILIES + 'TD = { defined = "docs:debt.md", type = "debt", removable = true }\n')
    write(repo.code / "docs/debt.md", "| ID | Debt |\n|---|---|\n| TD-1 | **One.** |\n")
    commit(repo.code)
    code, out = repo.check(capsys, "--all")
    assert code == 0 and "removable: TD-5 (TD) is no longer defined: docs/notes.md:1" in out
    assert [r["identifier"] for r in repo.report(capsys)[1]["removable"]] == ["TD-5"]
    repo.config(FAMILIES + 'TD = { defined = "docs:debt.md", type = "debt" }\n')
    assert repo.check(capsys)[0] == 1


def test_an_exception_excuses_an_unresolved_identifier_and_a_stale_one_is_reported(tmp_path, monkeypatch, capsys):
    repo = Repo(tmp_path, monkeypatch, notes="STD-9 and STD-1.\n")
    write(repo.code / "docs/exceptions.txt", "# why\nSTD-9  # planned, never drafted\nSTD-7  # gone since\n")
    write(repo.code / "docs/family.txt", "STD-8\n")
    commit(repo.code)
    repo.config('STD = { defined = "docs:standards.md", type = "standard", exceptions = "docs:family.txt" }\n', extra='identifiers = { exceptions = "docs:exceptions.txt" }\n')
    code, out = repo.check(capsys)
    assert code == 0 and "stale: STD-7 (docs/exceptions.txt:3)" in out and "stale: STD-8 (docs/family.txt:1)" in out
    assert "STD-9" not in out.replace("STD-9  #", "")
    assert [s["identifier"] for s in repo.report(capsys)[1]["stale"]] == ["STD-7", "STD-8"]
    write(repo.code / "docs/notes.md", "STD-1 only.\n")
    commit(repo.code)
    assert "stale: STD-9" in repo.check(capsys)[1]


def test_the_first_row_committed_keeps_a_duplicated_number(tmp_path, monkeypatch, capsys):
    repo = Repo(tmp_path, monkeypatch)
    write(repo.code / "docs/more.md", "| ID | Claim |\n|---|---|\n| STD-2 | **Again.** |\n")
    commit(repo.code, when="2026-01-02T03:04:05Z")
    repo.config('STD = { defined = ["docs:standards.md", "docs:more.md"], type = "standard" }\n')
    code, out = repo.check(capsys)
    assert code == 1
    assert ("ERROR: STD-2 (STD) is defined 2 times: docs/standards.md:4 (2026-01-01T00:00:00Z), docs/more.md:3 (2026-01-02T03:04:05Z). "
            "docs/standards.md:4 keeps the number.") in out
    assert repo.report(capsys)[1]["duplicates"][0]["keeps"] == "docs/standards.md:4"


def test_two_rows_committed_in_the_same_second_are_left_to_the_maintainer(tmp_path, monkeypatch, capsys):
    repo = Repo(tmp_path, monkeypatch, standards=STANDARDS + "| STD-2 | **Again.** |\n")
    code, out = repo.check(capsys)
    assert code == 1 and "No one site was committed first, so the maintainer decides which keeps it." in out
    assert repo.report(capsys)[1]["duplicates"][0]["keeps"] is None


def test_an_ignored_or_untracked_file_is_never_read(tmp_path, monkeypatch, capsys):
    repo = Repo(tmp_path, monkeypatch)
    write(repo.code / "private/secret.md", "STD-98 is confidential.\n")
    write(repo.code / "docs/untracked.md", "STD-99 is not added.\n")
    code, out = repo.check(capsys)
    assert code == 0 and "98" not in out and "99" not in out and "in 2 files" in out


def test_a_skipped_file_and_a_generated_copy_are_not_read(tmp_path, monkeypatch, capsys):
    repo = Repo(tmp_path, monkeypatch)
    write(repo.code / "docs/crosswalk-old.md", "STD-98 under an old name.\n")
    write(repo.code / "docs/copy.md", "{% comment %}Copied from notes.md{% endcomment %}\nSTD-99 twice.\n")
    commit(repo.code)
    assert repo.check(capsys)[0] == 1
    repo.config(extra='identifiers = { skip = ["crosswalk-*"], generated = "\\\\A\\\\{% comment %\\\\}Copied from" }\n')
    assert repo.check(capsys)[0] == 0


def _moved(tmp_path, monkeypatch, notes, standards=STANDARDS):
    repo = Repo(tmp_path, monkeypatch, notes=notes, standards=standards)
    write(tmp_path / "ts/rdf.md", "| ID | Claim |\n|---|---|\n| RDF-5 | **Five.** |\n")
    write(tmp_path / "ts/domain.toml", 'families = { RDF = { defined = "rdf.md", type = "standard" } }\n')
    moves = (f'\n[[projects.moves]]\nfamily = "STD"\nto = "ts"\nsource = "code:docs/standards.md"\ncommit = "{repo.head[:8]}"\n'
             'rows = { "STD-1" = "RDF-5", "STD-2" = "RDF-6" }\n')
    domains = f'[[domains]]\nname = "ts"\nvisibility = "public"\npath = "{tmp_path / "ts"}"\n'
    write(tmp_path / "config.toml", f'{domains}\n[[projects]]\nname = "proj"\ncode = "{repo.code}"\ndomains = ["ts"]\n\n[projects.families]\n{FAMILIES}{moves}')
    return repo


def test_a_moved_mention_resolves_through_the_domain_only_where_it_defines_it(tmp_path, monkeypatch, capsys):
    repo = _moved(tmp_path, monkeypatch, "STD-1 moved well and STD-2 moved badly.\n")
    code, out = repo.check(capsys)
    assert code == 1
    assert "ERROR: STD-2 (STD) is moved to ts:RDF-6, which defines nothing by that name: docs/notes.md:1" in out and "STD-1 (STD)" not in out


def test_a_moved_rows_copy_in_the_project_is_not_a_duplicate(tmp_path, monkeypatch, capsys):
    repo = _moved(tmp_path, monkeypatch, "STD-1 only.\n", standards="| ID | Claim |\n|---|---|\n| STD-1 | **One.** |\n| STD-1 | **Copy.** |\n")
    assert repo.check(capsys)[0] == 0
    write(repo.code / "docs/standards.md", STANDARDS + "| STD-3 | **Three.** |\n| STD-3 | **Three again.** |\n")
    commit(repo.code)
    assert "STD-3 (STD) is defined 2 times" in repo.check(capsys)[1]


def test_a_qualified_mention_resolves_in_the_scope_it_names(tmp_path, monkeypatch, capsys):
    repo = _moved(tmp_path, monkeypatch, "Cite ts:RDF-5 and ts:RDF-9.\n")
    code, out = repo.check(capsys)
    assert code == 1 and "ERROR: ts:RDF-9 (RDF) is mentioned but never defined: docs/notes.md:1" in out and "RDF-5" not in out


def test_the_exceptions_key_of_a_manifest_may_not_leave_its_folder(tmp_path, monkeypatch):
    repo = Repo(tmp_path, monkeypatch)
    write(tmp_path / "ts/domain.toml", 'families = { RDF = { defined = "rdf.md", exceptions = "../outside.txt" } }\n')
    repo.config(domains=f'[[domains]]\nname = "ts"\npath = "{tmp_path / "ts"}"\n', extra='domains = ["ts"]\n')
    config = load(tmp_path / "config.toml")
    assert "leaves the domain's folder" in "\n".join(config.set_aside["ts"]) and "families.RDF.exceptions" in "\n".join(config.set_aside["ts"])


# ---- defined_only ------------------------------------------------------------------------------

BOARD = "| Slice | Deliverable | State | Blocked on |\n|---|---|---|---|\n| WB-1 | **First.** | built 2026-11-03, building 2026-11-03 | |\n"
LOOSE = 'SL = { pattern = "[A-Z][A-Z0-9]*-[0-9][\\\\w.]*", defined = "docs:board.md", type = "slice"%s }\n'


def test_a_loose_pattern_reads_a_bare_match_only_where_its_identifier_is_defined(tmp_path, monkeypatch, capsys):
    repo = Repo(tmp_path, monkeypatch, notes="Encode as UTF-8, hash with SHA-256, see WB-1 and WB-9 now.\n", families=FAMILIES + LOOSE % "")
    write(repo.code / "docs/board.md", BOARD)
    commit(repo.code)
    code, report = repo.report(capsys)
    assert code == 1 and sorted(u["identifier"] for u in report["unresolved"]) == ["SHA-256", "UTF-8", "WB-9"]
    repo.config(FAMILIES + LOOSE % ", defined_only = true")
    code, report = repo.report(capsys)
    assert code == 1 and [u["identifier"] for u in report["unresolved"]] == ["WB-9"], "a mistyped slice is caught, and UTF-8 and SHA-256 are no mention"


def test_defined_only_applies_to_mentions_and_to_what_a_bare_identifier_names(tmp_path, monkeypatch):
    repo = Repo(tmp_path, monkeypatch, families=FAMILIES + 'TD = { defined = "docs:debt.md", type = "debt" }\n' + LOOSE % ", defined_only = true")
    write(repo.code / "docs/board.md", BOARD)
    write(repo.code / "docs/debt.md", "| ID | Debt |\n|---|---|\n| TD-1 | **One.** |\n")
    forget()
    config = load(repo.tmp / "config.toml")
    project = config.projects["proj"]
    assert mentions(config, "UTF-8, SHA-256, WB-1 and TD-1", project) == ["proj:WB-1", "proj:TD-1"]
    assert resolve(config, "TD-1", project) == "proj:TD-1", "TD-1 matches the loose pattern too, and is not defined by it"
    assert resolve(config, "WB-1", project) == "proj:WB-1"
    for loose in ("UTF-8", "proj:UTF-8"):
        with pytest.raises(Exception, match="matches no family"):
            resolve(config, loose, project)


def test_a_flag_that_is_not_true_or_false_is_refused(tmp_path, monkeypatch):
    repo = Repo(tmp_path, monkeypatch)
    repo.config('STD = { defined = "docs:standards.md", defined_only = "yes" }\n')
    with pytest.raises(ConfigError, match="removable and defined_only"):
        load(tmp_path / "config.toml")
