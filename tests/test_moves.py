# SPDX-License-Identifier: MIT
"""Moves: what a project declares it gave to a domain, how its identifiers resolve after, the check of an
older branch against the moved source, and a domain that cites no project."""

from __future__ import annotations

import json
import re
import subprocess

import pytest

from vyvid import audit, cli, resolve as resolver
from vyvid import build as builder
from vyvid.citations import domain_citations
from vyvid.config import ConfigError, load
from vyvid.resolve import resolve

STANDARDS = "| ID | Claim |\n|---|---|\n| STD-029 | **Stays.** |\n| STD-030 | **Moves.** |\n| STD-031 | **Moves too.** |\n"
RECORD = "# Record\n\n## TSD-1. First\n\nBody one.\n\n## TSD-2. Second\n\nBody two.\n\n### Detail\n\nUnder two.\n\n## Other\n\nNone.\n"
RDF = "| ID | Claim |\n|---|---|\n| RDF-5 | **Rule five.** |\n| RDF-6 | **Rule six.** |\n"


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def git(folder, *args):
    subprocess.run(["git", "-C", str(folder), "-c", "user.name=t", "-c", "user.email=t@example.com", *args], check=True, capture_output=True)


def commit(folder, message="c"):
    git(folder, "add", "-A")
    git(folder, "commit", "-q", "-m", message)
    return subprocess.run(["git", "-C", str(folder), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()


class World:
    """A project in a git repository that moved TSD whole and two STD rows to the domain triple-stores."""

    def __init__(self, tmp_path, keep=True):
        self.tmp, self.code = tmp_path, tmp_path / "code"
        write(self.code / "docs/standards.md", STANDARDS)
        write(self.code / "docs/record.md", RECORD)
        git(self.code, "init", "-q", "-b", "main")
        self.commit = commit(self.code)
        write(tmp_path / "ts/rdf.md", RDF)
        write(tmp_path / "ts/domain.toml", 'families = { RDF = { defined = "rdf.md", type = "standard" }, TSD = { rule = "heading", pattern = \'TSD-\\d+\' } }\n')
        self.write_config(keep)

    def write_config(self, keep=True, extra=""):
        text = f"""
[[domains]]
name = "triple-stores"
path = "{(self.tmp / 'ts').as_posix()}"

[[projects]]
name = "lattice"
code = "{self.code.as_posix()}"
domains = ["triple-stores"]
families = {{ STD = {{ defined = "docs:standards.md", type = "standard" }}{', TSD = { rule = "heading", pattern = \'TSD-\\d+\', defined = "docs:record.md" }' if keep else ''} }}

[[projects.moves]]
family = "TSD"
to = "triple-stores"
source = "code:docs/record.md"
commit = "{self.commit[:8]}"

[[projects.moves]]
family = "STD"
to = "triple-stores"
source = "code:docs/standards.md"
commit = "{self.commit[:8]}"
rows = {{ "STD-030" = "RDF-5", "STD-031" = "RDF-6" }}
{extra}"""
        write(self.tmp / "config.toml", text)
        self.config = load(self.tmp / "config.toml")
        self.project = self.config.projects["lattice"]


@pytest.fixture
def world(tmp_path):
    return World(tmp_path)


def test_a_whole_family_and_some_rows_resolve_through_the_domain(world):
    c, p = world.config, world.project
    assert resolve(c, "TSD-1", p) == "triple-stores:TSD-1"
    assert resolve(c, "STD-030", p) == "triple-stores:RDF-5"
    assert resolve(c, "lattice:STD-031", p) == "triple-stores:RDF-6"
    assert resolve(c, "STD-029", p) == "lattice:STD-029"
    how: list[str] = []
    resolve(c, "STD-030", p, how)
    assert len(how) == 1 and "triple-stores:RDF-5" in how[0] and world.commit[:8] in how[0]
    assert resolver.mentions(c, "See STD-030, STD-029 and TSD-2.", p) == ["triple-stores:RDF-5", "lattice:STD-029", "triple-stores:TSD-2"]


def test_a_moved_family_needs_no_family_of_the_projects_own(tmp_path):
    w = World(tmp_path, keep=False)
    assert resolve(w.config, "TSD-9", w.project) == "triple-stores:TSD-9"


def test_each_problem_in_a_move_is_a_configuration_problem(world):
    for extra, expected in (
        ('\n[[projects.moves]]\nfamily = "A"\nto = "nowhere"\nsource = "code:x"\ncommit = "abcdef1"\nrows = { "A-1" = "RDF-5" }\n', "not in its stack"),
        ('\n[[projects.moves]]\nfamily = "A"\nto = "triple-stores"\nsource = "code:x"\ncommit = "abc"\nrows = { "A-1" = "RDF-5" }\n', "hexadecimal"),
        ('\n[[projects.moves]]\nfamily = "A"\nto = "triple-stores"\nsource = "code:x"\ncommit = "abcdef1"\nrows = { "A-1" = "NOPE-5" }\n', "no family of 'triple-stores' matches"),
        ('\n[[projects.moves]]\nfamily = "A"\nto = "triple-stores"\ncommit = "abcdef1"\n', "'source'"),
        ('\n[[projects.moves]]\nfamily = "STD"\nto = "triple-stores"\nsource = "code:x"\ncommit = "abcdef1"\n', "declared twice"),
    ):
        with pytest.raises(ConfigError) as error:
            world.write_config(extra=extra)
        assert expected in "\n".join(error.value.problems)


def test_a_move_to_a_set_aside_domain_is_dropped(world):
    write(world.tmp / "ts/domain.toml", 'visibility = "secret"\n')
    world.write_config()
    assert world.config.set_aside and world.project.moves == []


def test_the_build_leaves_out_what_a_domain_answers_for(world):
    out = builder.build(world.config, world.project, world.tmp / "s" / "store", embed=False)
    assert out.counts["moved:lattice>triple-stores"] == 4  # two rows, two findings
    assert any("4 entries of 'lattice' moved to 'triple-stores'" in p for p in out.problems)
    store = builder.open_store(world.tmp / "s" / "store")
    ids = {str(r["id"].value) for r in store.query('SELECT ?id WHERE { GRAPH ?g { ?s <https://www.nebularis.org/vyvid/knowledge#identifier> ?id } }')}
    assert ids == {"STD-029", "RDF-5", "RDF-6"}


def test_resolve_prints_the_target_and_says_how(world, monkeypatch, capsys):
    monkeypatch.setenv("VYVID_CONFIG", str(world.tmp / "config.toml"))
    assert cli.main(["resolve", "STD-030", "--in", str(world.code)]) == 0
    captured = capsys.readouterr()
    assert captured.out.strip() == "triple-stores:RDF-5" and "moved to triple-stores:RDF-5" in captured.err


# ---- vyd move check ---------------------------------------------------------------------------


def check(world, *args, capsys):
    code = cli.main(["move", "check", str(world.code), *args])
    return code, capsys.readouterr()


@pytest.fixture
def configured(world, monkeypatch):
    monkeypatch.setenv("VYVID_CONFIG", str(world.tmp / "config.toml"))
    return world


def test_nothing_changed_exits_zero(configured, capsys):
    assert check(configured, capsys=capsys)[0] == 0
    assert check(configured, "--ref", "main", capsys=capsys)[0] == 0


def test_a_branch_that_edits_adds_and_removes(configured, capsys):
    w = configured
    git(w.code, "checkout", "-q", "-b", "old")
    write(w.code / "docs/standards.md", STANDARDS.replace("**Moves.**", "**Changed.**").replace("| STD-031 | **Moves too.** |\n", "") + "| STD-032 | **New.** |\n")
    write(w.code / "docs/record.md", RECORD.replace("Under two.", "Edited.").replace("## Other", "## TSD-3. Third\n\nNew.\n\n## Other"))
    commit(w.code)
    git(w.code, "checkout", "-q", "main")
    code, out = check(w, "--ref", "old", capsys=capsys)
    lines = out.out.splitlines()
    assert code == 1
    # a row move compares its own rows alone, so the new STD-032 is not reported
    assert [l for l in lines if l.startswith("STD")] == ["STD STD-030 changed", "STD STD-031 removed"]
    assert [l for l in lines if l.startswith("TSD")] == ["TSD TSD-2 changed", "TSD TSD-3 added"]
    code, out = check(w, "--ref", "old", "--json", capsys=capsys)
    assert {"family": "TSD", "id": "TSD-3", "state": "added"} in json.loads(out.out)


def test_a_working_tree_edit_is_seen(configured, capsys):
    write(configured.code / "docs/record.md", RECORD.replace("Body one.", "Body 1."))
    code, out = check(configured, capsys=capsys)
    assert code == 1 and out.out.splitlines() == ["TSD TSD-1 changed"]


def test_a_bad_ref_or_commit_exits_two(configured, capsys):
    code, out = check(configured, "--ref", "nonesuch", capsys=capsys)
    assert code == 2 and "nonesuch" in out.err
    configured.write_config()
    text = (configured.tmp / "config.toml").read_text(encoding="utf-8").replace(configured.commit[:8], "deadbee")
    (configured.tmp / "config.toml").write_text(text, encoding="utf-8")
    assert check(configured, capsys=capsys)[0] == 2


def test_a_file_the_project_removed_is_one_line_and_no_difference(configured, capsys):
    w = configured
    git(w.code, "checkout", "-q", "-b", "old")
    git(w.code, "checkout", "-q", "main")
    (w.code / "docs/record.md").unlink()
    commit(w.code)
    code, out = check(w, "--ref", "main", capsys=capsys)
    assert out.out.splitlines() == ["TSD - file-absent"] and code == 0
    code, out = check(w, "--ref", "old", capsys=capsys)
    assert out.out.strip() == "nothing differs" and code == 0  # the branch still has it, unchanged


# ---- a domain cites no project ----------------------------------------------------------------


def test_a_domain_citing_a_project_or_a_stranger_is_refused_in_the_build(world):
    write(world.tmp / "ts/rdf.md", RDF + "\nSee lattice:STD-30, general:STD-1, triple-stores:RDF-5, https://x.org:8080/a and xsd:long.\n")
    write(world.tmp / "ts/notes.md", "")
    out = builder.build(world.config, world.project, world.tmp / "s" / "store", embed=False)
    cited = [p for p in out.problems if "cites" in p]
    assert len(cited) == 1 and "rdf.md:" in cited[0] and "project 'lattice'" in cited[0]


def test_a_domain_may_cite_its_ancestors_and_no_other_domain(tmp_path):
    write(tmp_path / "a/rules.md", "Cite b:B-1 and a:A-1.\n")
    write(tmp_path / "b/rules.md", "Cite a:A-1 and b:B-1.\n")
    write(tmp_path / "config.toml", f'''
[[domains]]
name = "a"
path = "{(tmp_path / 'a').as_posix()}"
families = {{ A = {{}} }}
rules = "rules.md"
[[domains]]
name = "b"
path = "{(tmp_path / 'b').as_posix()}"
parents = ["a"]
families = {{ B = {{}} }}
rules = "rules.md"
[[projects]]
name = "p"
code = "{tmp_path.as_posix()}"
domains = ["b"]
''')
    config = load(tmp_path / "config.toml")
    assert domain_citations(config, config.domains["b"]) == []
    [refused] = domain_citations(config, config.domains["a"])
    assert "rules.md:1" in refused and "domain 'b'" in refused


def test_audit_reports_a_qualified_mention_of_another_scope_and_not_lookalikes(tmp_path):
    folder = tmp_path / "triple-stores"
    write(folder / "a.md", "Own triple-stores:RDF-1, parent owl:OWL-2, other lattice:STD-30, https://x.org:8080/p, xsd:long, ex:foo, a:B-C.\n")
    found = [f for f in audit.audit(folder, ("owl",)) if f.kind == "qualified-mention"]
    assert [f.text.split(" ")[0] for f in found] == ["lattice:STD-30"]
    assert [f.text.split(" ")[0] for f in audit.audit(folder) if f.kind == "qualified-mention"] == ["owl:OWL-2", "lattice:STD-30"]
    write(folder / "domain.toml", 'name = "owl"\n')
    assert [f.text.split(" ")[0] for f in audit.audit(folder) if f.kind == "qualified-mention"] == ["triple-stores:RDF-1", "lattice:STD-30"]


def test_a_branch_older_than_the_move_answers_only_for_what_it_changed(configured, capsys):
    """Main moved on after the branch forked, and the move is taken at main's later commit. The branch
    is not blamed for main's edit, a row it edited is reported, and a row it edited to main's text is not."""
    w = configured
    git(w.code, "checkout", "-q", "-b", "old")
    write(w.code / "docs/record.md", RECORD.replace("Under two.", "Edited."))
    write(w.code / "docs/standards.md", STANDARDS.replace("**Moves too", "**Moved alike"))
    commit(w.code)
    git(w.code, "checkout", "-q", "main")
    write(w.code / "docs/standards.md", STANDARDS.replace("**Moves.**", "**Changed on main.**").replace("**Moves too", "**Moved alike"))
    commit(w.code)
    head = subprocess.check_output(["git", "-C", str(w.code), "rev-parse", "HEAD"], text=True).strip()
    config = w.tmp / "config.toml"
    config.write_text(re.sub(r'commit = "[0-9a-f]+"', f'commit = "{head}"', config.read_text(encoding="utf-8")), encoding="utf-8")
    code, out = check(w, "--ref", "old", capsys=capsys)
    assert code == 1 and out.out.splitlines() == ["TSD TSD-2 changed"]



# ---- copy_removed -----------------------------------------------------------------------------


def removed(world):
    """Both moves declare that the project removed its copy, which is trimmed to the headings and to the row that stays."""
    config = world.tmp / "config.toml"
    config.write_text(config.read_text(encoding="utf-8").replace(f'commit = "{world.commit[:8]}"', f'commit = "{world.commit[:8]}"\ncopy_removed = true'), encoding="utf-8")
    world.config = load(config)
    assert all(m.copy_removed for m in world.config.projects["lattice"].moves)


TRIMMED_STD = "| ID | Claim |\n|---|---|\n| STD-029 | **Stays.** |\n"
TRIMMED_RECORD = "# Record\n\n## TSD-1. First\n\n## TSD-2. Second\n\n### Detail\n\n## Other\n"


def trim(w):
    write(w.code / "docs/standards.md", TRIMMED_STD)
    write(w.code / "docs/record.md", TRIMMED_RECORD)


def test_a_removed_copy_is_one_line_and_no_difference(configured, capsys):
    w = configured
    trim(w)
    assert check(w, capsys=capsys)[0] == 1, "without the key the trimmed copy differs"
    removed(w)
    code, out = check(w, capsys=capsys)
    assert code == 0 and out.out.splitlines() == ["TSD - copy-removed", "STD - copy-removed"]
    code, out = check(w, "--json", capsys=capsys)
    assert code == 0 and json.loads(out.out) == [{"family": "TSD", "id": "-", "state": "copy-removed"}, {"family": "STD", "id": "-", "state": "copy-removed"}]


def test_a_ref_carrying_the_removal_reports_it_without_ancestry(configured, capsys):
    w = configured
    removed(w)
    git(w.code, "checkout", "-q", "-b", "squashed")
    trim(w)
    commit(w.code)
    git(w.code, "checkout", "-q", "main")
    trim(w)  # an uncommitted copy of the same text, so the branch is not an ancestor of the tree
    code, out = check(w, "--ref", "squashed", capsys=capsys)
    assert code == 0 and out.out.splitlines() == ["TSD - copy-removed", "STD - copy-removed"]


def test_an_older_branch_that_edited_a_moved_entry_is_still_caught(configured, capsys):
    w = configured
    removed(w)
    git(w.code, "checkout", "-q", "-b", "old")
    write(w.code / "docs/standards.md", STANDARDS.replace("**Moves.**", "**Changed.**").replace("| STD-031 | **Moves too.** |\n", ""))
    write(w.code / "docs/record.md", RECORD.replace("Body two.", "Edited.").replace("## Other", "## TSD-3. Third\n\nNew.\n\n## Other").replace("## TSD-1. First\n\nBody one.\n\n", ""))
    commit(w.code)
    git(w.code, "checkout", "-q", "main")
    trim(w)
    code, out = check(w, "--ref", "old", capsys=capsys)
    # the branch's removals of STD-031 and TSD-1 lose nothing, its edit and its addition do
    assert code == 1 and out.out.splitlines() == ["TSD TSD-2 changed", "TSD TSD-3 added", "STD STD-030 changed"]


def test_a_removed_copy_whose_file_is_absent_at_the_ref_is_file_absent(configured, capsys):
    w = configured
    removed(w)
    (w.code / "docs/record.md").unlink()
    commit(w.code)
    code, out = check(w, "--ref", "main", capsys=capsys)
    assert code == 0 and out.out.splitlines() == ["TSD - file-absent", "STD - copy-removed"]


def test_copy_removed_must_be_a_boolean(world):
    with pytest.raises(ConfigError) as error:
        world.write_config(extra='\n[[projects.moves]]\nfamily = "A"\nto = "triple-stores"\nsource = "code:x"\ncommit = "abcdef1"\ncopy_removed = "yes"\n')
    assert "copy_removed" in "\n".join(error.value.problems)
