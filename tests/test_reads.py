# SPDX-License-Identifier: MIT
"""RD-1 to RD-4: a project reads another's knowledge from a pinned commit, and skills and recipes come only by name
under review. Real git repositories under a temporary folder, a stand-in model, no network."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from test_checkouts import quiet_git  # noqa: F401  an autouse fixture
from test_index_core import Words
from test_project_file import commit, configure, put, sh
from vyvid import ask
from vyvid import build as builder
from vyvid import config as configuration
from vyvid.config import ConfigError, load
from vyvid.resolve import bind_in

PIN = "a" * 40
STANDARDS = "| ID | Claim | Pointer |\n|---|---|---|\n| STD-1 | A ledger is kept per key. | docs/standards.md |\n"
SKILL = "---\nname: architecture\ndescription: How the layers fit\n---\n\n# Architecture\n\n## Layers\n\nThree of them.\n"
UPSTREAM = """[project]
name = "up"
visibility = "VIS"
skills = ["code:own"]
skill_prefix = "up-"
contract = "docs:contract.md"

[project.families]
STD = { defined = "docs:standards.md", type = "standard" }

[[project.recipes]]
name = "r"
description = "Use r"
steps = [{ step = "find", words = "{question}", limit = 3 }]

[[project.recipes]]
name = "other"
description = "Another"
steps = [{ step = "find", words = "{question}", limit = 3 }]

[[project.recipes]]
name = "g"
description = "With glue"
steps = [{ step = "glue", command = ["python", "tools/glue.py"] }]

[[project.extractors]]
kind = "cmd"
command = ["python", "tools/ex.py"]
paths = ["code:docs/*.md"]
"""
DOWN = """[project]
name = "down"
visibility = "VIS"
EXTRA
[project.reads.up]
commit = "COMMIT"
READ
"""


def upstream(tmp_path: Path, visibility: str = "public") -> tuple[Path, str]:
    """A repository of project ``up`` with a standard, a contract, a skill and two recipes, and its commit."""
    root = tmp_path / "up"
    root.mkdir(parents=True)
    sh(root, "init", "-b", "main")
    put(root, "vyvid.toml", UPSTREAM.replace("VIS", visibility))
    put(root, "docs/standards.md", STANDARDS)
    put(root, "docs/contract.md", "# Rules of up\n")
    put(root, "own/architecture/SKILL.md", SKILL)
    commit(root)
    head = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    return root, head


def downstream(tmp_path: Path, pin: str, visibility: str = "public", extra: str = "", read: str = "") -> Path:
    root = tmp_path / "down"
    root.mkdir(parents=True)
    sh(root, "init", "-b", "main")
    put(root, "vyvid.toml", DOWN.replace("VIS", visibility).replace("COMMIT", pin).replace("EXTRA", extra).replace("READ", read))
    put(root, "docs/notes.md", "# Notes\n")
    commit(root)
    return root


@pytest.fixture(autouse=True)
def no_configuration(tmp_path, monkeypatch):
    monkeypatch.setenv("VYVID_CONFIG", str(tmp_path / "absent.toml"))


# ---- RD-1: the configuration ---------------------------------------------------------------------


def test_a_read_is_parsed_with_its_pin_and_allow_lists(tmp_path, monkeypatch):
    up, head = upstream(tmp_path)
    down = downstream(tmp_path, head, read='skills = ["architecture"]\nrecipes = ["r"]\n')
    configure(tmp_path, monkeypatch, f'[[projects]]\nname = "up"\ncode = "{up.as_posix()}"\n')
    config, project = bind_in(load(), down)
    read = project.reads["up"]
    assert (read.name, read.commit, read.skills, read.recipes) == ("up", head, ("architecture",), ("r",))
    assert project.unread == [] and not config.files_aside


def test_a_read_needs_a_full_commit_and_known_keys(tmp_path, monkeypatch):
    up, head = upstream(tmp_path)
    configure(tmp_path, monkeypatch, f'[[projects]]\nname = "up"\ncode = "{up.as_posix()}"\n')
    for pin, text in (("abc1234", "full commit"), ("main", "full commit")):
        config, project = bind_in(load(), downstream(tmp_path / pin, pin))
        assert project is None and any(text in p for ps in config.files_aside.values() for p in ps), pin
    config, project = bind_in(load(), downstream(tmp_path / "keys", head, read="colour = 1\n"))
    assert project is None and any("colour" in p for ps in config.files_aside.values() for p in ps)
    config, project = bind_in(load(), downstream(tmp_path / "list", head, read="skills = \"architecture\"\n"))
    assert project is None and any("skills" in p and "list" in p for ps in config.files_aside.values() for p in ps)


def test_a_project_does_not_read_itself(tmp_path, monkeypatch):
    up, head = upstream(tmp_path)
    put(up, "vyvid.toml", UPSTREAM.replace("VIS", "public") + f'\n[project.reads.up]\ncommit = "{head}"\n')
    config, project = bind_in(load(), up)
    assert project is None and any("itself" in p for ps in config.files_aside.values() for p in ps)


def test_a_read_of_a_project_that_is_not_configured_is_noted_and_skipped(tmp_path, monkeypatch):
    up, head = upstream(tmp_path)
    down = downstream(tmp_path, head)
    config, project = bind_in(load(), down)
    assert project.name == "down" and project.reads == {} and project.unread == ["up"] and not config.files_aside


def test_the_review_is_the_users_alone_and_stands_only_at_the_pin(tmp_path, monkeypatch):
    up, head = upstream(tmp_path)
    down = downstream(tmp_path, head, extra='reviewed_reads = { up = "ABC" }\n')
    configure(tmp_path, monkeypatch, f'[[projects]]\nname = "up"\ncode = "{up.as_posix()}"\n')
    config, project = bind_in(load(), down)
    assert project is None and any("reviewed_reads" in p and "only the user's configuration" in p for ps in config.files_aside.values() for p in ps)
    plain = downstream(tmp_path / "plain", head)
    for recorded, standing in ((head, "reviewed"), (head[:10], "reviewed"), ("b" * 40, "knowledge"), ("", "knowledge")):
        text = f'[[projects]]\nname = "up"\ncode = "{up.as_posix()}"\n[[projects]]\nname = "down"\ncode = "{plain.as_posix()}"\n'
        if recorded:
            text += f'[projects.reviewed_reads]\nup = "{recorded}"\n'
        configure(tmp_path, monkeypatch, text)
        project = bind_in(load(), plain)[1]
        assert project.reads["up"].standing(project) == standing, recorded


def test_a_public_project_never_reads_a_private_one(tmp_path, monkeypatch):
    up, head = upstream(tmp_path, "private")
    down = downstream(tmp_path, head)
    configure(tmp_path, monkeypatch, f'[[projects]]\nname = "up"\ncode = "{up.as_posix()}"\nvisibility = "private"\n')
    config, project = bind_in(load(), down)
    assert project is None
    assert any("public" in p and "private" in p and "up" in p for ps in config.files_aside.values() for p in ps)
    # A private project may read a private one, and a private or public one a public one.
    assert bind_in(load(), downstream(tmp_path / "p", head, "private"))[1].reads["up"].commit == head


def test_the_guard_holds_in_the_users_own_entry(tmp_path, monkeypatch):
    up, head = upstream(tmp_path, "private")
    down = tmp_path / "plain"
    down.mkdir()
    configure(tmp_path, monkeypatch, f'[[projects]]\nname = "up"\ncode = "{up.as_posix()}"\nvisibility = "private"\n'
                                    f'[[projects]]\nname = "down"\ncode = "{down.as_posix()}"\n[projects.reads.up]\ncommit = "{head}"\n')
    with pytest.raises(ConfigError) as error:
        load()
    assert any("public" in p and "private" in p for p in error.value.problems)


def test_scope_refuses_a_private_project_for_a_public_one_and_leaves_domains_as_they_were(tmp_path, monkeypatch):
    pub, priv = tmp_path / "pub", tmp_path / "priv"
    for r in (pub, priv):
        r.mkdir()
    dom = tmp_path / "dom"
    (dom / "knowledge").mkdir(parents=True)
    configure(tmp_path, monkeypatch, f'[[domains]]\nname = "secret"\npath = "{dom.as_posix()}"\nvisibility = "private"\n'
                                    f'[[projects]]\nname = "pub"\ncode = "{pub.as_posix()}"\n'
                                    f'[[projects]]\nname = "priv"\ncode = "{priv.as_posix()}"\nvisibility = "private"\n')
    config, project = bind_in(load(), pub)
    a = ask.Asker(config, project, [config.general, project], tmp_path / "store")
    with pytest.raises(ValueError, match="private"):
        a.choose("priv")
    with pytest.raises(ValueError, match="private"):
        a.choose("only:priv,pub")
    a.choose("secret")
    assert [s.name for s in a.visible][-1] == "secret"
    config, project = bind_in(load(), priv)
    ask.Asker(config, project, [config.general, project], tmp_path / "store").choose("pub")


def test_context_shows_what_a_project_reads_and_says_what_it_cannot(tmp_path, monkeypatch, capsys):
    import json

    from vyvid import cli

    up, head = upstream(tmp_path)
    down = downstream(tmp_path, head, read='skills = ["architecture"]\n')
    configure(tmp_path, monkeypatch, f'[[projects]]\nname = "up"\ncode = "{up.as_posix()}"\n')
    assert cli.main(["context", str(down), "--no-pull", "--json"]) == 0
    layer = json.loads(capsys.readouterr().out)["layers"][-1]
    assert layer["reads"] == [{"name": "up", "commit": head, "standing": "knowledge", "skills": ["architecture"], "recipes": []}]
    assert cli.main(["context", str(down), "--no-pull"]) == 0
    assert f"reads up at {head[:12]}, knowledge alone" in capsys.readouterr().out
    configure(tmp_path, monkeypatch, "")
    assert cli.main(["context", str(down), "--no-pull"]) == 0
    assert "NOTE: reads up, which is not configured here" in capsys.readouterr().err


# ---- RD-2: the snapshot --------------------------------------------------------------------------


def read_of(tmp_path, monkeypatch, up, head, review="", **kw):
    down = downstream(tmp_path, head, **kw)
    text = f'[[projects]]\nname = "up"\ncode = "{up.as_posix()}"\n[[projects]]\nname = "down"\ncode = "{down.as_posix()}"\n'
    configure(tmp_path, monkeypatch, text + (f'[projects.reviewed_reads]\nup = "{review}"\n' if review else ""))
    config, project = bind_in(load(), down)
    return down, config, project


def test_the_snapshot_is_the_pinned_commit_and_not_the_checkout(tmp_path, monkeypatch):
    up, head = upstream(tmp_path)
    put(up, "docs/standards.md", STANDARDS + "| STD-2 | Added after the pin. | docs/standards.md |\n")
    commit(up, "later")
    _, config, project = read_of(tmp_path, monkeypatch, up, head)
    scope = config.projects["up"]
    assert scope.read_of == "down" and scope.read_commit == head and scope.kind == "project"
    assert "STD-2" not in (scope.code / "docs" / "standards.md").read_text() and (up / "docs" / "standards.md").read_text().count("STD-") == 2
    assert head in scope.code.parts, "kept by the commit"
    assert project.read_notes == []


def test_the_snapshot_is_kept_by_commit_and_extracted_again_when_it_no_longer_matches_its_record(tmp_path, monkeypatch):
    up, head = upstream(tmp_path)
    down, config, project = read_of(tmp_path, monkeypatch, up, head)
    standards = config.projects["up"].code / "docs" / "standards.md"
    before = standards.stat().st_mtime_ns
    assert bind_in(load(), down)[1].read_notes == [] and standards.stat().st_mtime_ns == before, "an unchanged snapshot is left as it is"
    standards.write_text("tampered\n")
    again = bind_in(load(), down)
    assert any("did not match its record" in n for n in again[1].read_notes) and "tampered" not in standards.read_text()


def test_a_commit_the_source_does_not_hold_is_noted_and_the_read_left_out(tmp_path, monkeypatch):
    up, head = upstream(tmp_path)
    _, config, project = read_of(tmp_path, monkeypatch, up, "b" * 40)
    assert project.reads == {} and config.projects["up"].read_of is None
    assert any("is not in" in n and "b" * 12 in n for n in project.read_notes)


def test_the_read_scope_is_cut_to_knowledge(tmp_path, monkeypatch):
    up, head = upstream(tmp_path)
    _, config, _ = read_of(tmp_path, monkeypatch, up, head)
    scope = config.projects["up"]
    assert list(scope.families) == ["STD"] and scope.rules == [] and scope.recipes == [] and scope.remotes == []
    assert scope.extractors == [], "a command extractor of the read project never runs"
    assert scope.standing == "knowledge" and not scope.trusted


def test_a_reviewed_read_brings_the_recipes_named_and_never_one_with_glue(tmp_path, monkeypatch):
    up, head = upstream(tmp_path)
    _, config, _ = read_of(tmp_path, monkeypatch, up, head, review=head, read='recipes = ["r", "g"]\n')
    scope = config.projects["up"]
    assert scope.standing == "reviewed" and [r.name for r in scope.recipes] == ["r"], "other is not named, and g runs a command"
    assert scope.recipes[0].scope == "up"


# ---- RD-3: the stack and the index ---------------------------------------------------------------


def test_the_read_sits_between_the_domains_and_the_project(tmp_path, monkeypatch):
    from vyvid.resolve import layers

    up, head = upstream(tmp_path)
    _, config, project = read_of(tmp_path, monkeypatch, up, head)
    assert [s.name for s in layers(config, project)] == ["general", "up", "down"]


def ask_ids(down):
    config, project = bind_in(load(), down)
    a = ask.open_stack(config, down, model=Words())
    return a, {r["id"] for r in ask.candidates(a, set(), set(), set())}


def test_the_index_holds_the_pinned_knowledge_and_is_stale_when_the_pin_moves(tmp_path, monkeypatch):
    up, head = upstream(tmp_path)
    put(up, "docs/standards.md", STANDARDS.replace("A ledger is kept per key.", "A ledger is kept per account."))
    commit(up, "later")
    later = subprocess.run(["git", "-C", str(up), "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    down, config, project = read_of(tmp_path, monkeypatch, up, head)
    a, found = ask_ids(down)
    assert any(i.endswith("STD-1") for i in found)
    built_for = (a.directory / "built-for").read_text().split()
    assert f"up@{head}" in built_for and "down" in built_for and not ask.stale(a)
    put(down, "vyvid.toml", (down / "vyvid.toml").read_text().replace(head, later))
    config, project = bind_in(load(), down)
    assert ask.stale(ask.open_stack(config, down, model=Words(), need_store=False)), "a new pin is a rebuild"


def test_a_domain_of_the_reader_runs_its_extractors_over_the_read_with_the_settings_the_read_gives(tmp_path, monkeypatch):
    up, head = upstream(tmp_path)
    put(up, "vyvid.toml", (up / "vyvid.toml").read_text() + '\n[project.uses.onto.owl-terms]\npaths = ["code:ontology/*.ttl"]\n')
    put(up, "ontology/o.ttl", '@prefix owl: <http://www.w3.org/2002/07/owl#> .\n@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .\n'
                              '<https://example.org/o#Thing> a owl:Class ; rdfs:label "Thing" .\n')
    commit(up, "ontology")
    head = subprocess.run(["git", "-C", str(up), "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    dom = tmp_path / "onto"
    put(dom, "domain.toml", 'name = "onto"\nextractors = [{ kind = "owl-terms" }]\n')
    outcomes = {}
    for label, read in (("named", 'domains = ["onto"]\n'), ("unnamed", "")):
        down = downstream(tmp_path / label, head, extra='domains = ["onto"]\n', read=read)
        configure(tmp_path, monkeypatch, f'[[domains]]\nname = "onto"\npath = "{dom.as_posix()}"\n[[projects]]\nname = "up"\ncode = "{up.as_posix()}"\n')
        config, project = bind_in(load(), down)
        outcomes[label] = builder.build(config, project, embed=False).counts.get("term", 0)
    assert outcomes == {"named": 1, "unnamed": 0}, "the reader's domain runs over a read only where the read is told to"


# ---- RD-3: skills by name under review, and the (drop) marker ------------------------------------


def test_a_heading_ending_drop_removes_that_section_of_a_skill():
    from vyvid.skills import merge

    base = "# Skill\n\nOpening.\n\n## A\n\nalpha\n\n## B\n\nbeta\n"
    out = merge(base, "## A (drop)\n\n## C\n\ngamma\n")
    assert "## A" not in out and "alpha" not in out and "beta" in out and "## C" in out and "gamma" in out
    assert merge(base, "## Missing (drop)\n") == merge(base, ""), "dropping a section that is not there changes nothing"


def composed(tmp_path, monkeypatch, review="", read='skills = ["architecture"]\n', additions=None):
    from vyvid import skills

    up, head = upstream(tmp_path)
    down, config, project = read_of(tmp_path, monkeypatch, up, head, review=head if review else "", read=read)
    for name, text in (additions or {}).items():
        put(down, f".vyvid/skills/up/{name}.md", text)
    config, project = bind_in(load(), down)
    return skills.for_project(config, project)


def test_a_skill_of_a_read_comes_by_name_under_its_own_prefix_and_only_once_reviewed(tmp_path, monkeypatch):
    written, notes = composed(tmp_path, monkeypatch)
    assert written == [] and any("without a review" in n and "up" in n for n in notes)
    written, notes = composed(tmp_path / "r", monkeypatch, review="yes")
    assert [w.name for w in written] == ["up-architecture"] and "Three of them." in written[0].text and not written[0].problems
    assert "entries of project up" in written[0].text
    written, notes = composed(tmp_path / "n", monkeypatch, review="yes", read='skills = ["nonesuch"]\n')
    assert written == [] and any("nonesuch" in n for n in notes)
    written, _ = composed(tmp_path / "x", monkeypatch, review="yes", read="")
    assert written == [], "a skill not named is not carried"


def test_the_reader_changes_a_carried_skill_with_additions_and_may_drop_a_section(tmp_path, monkeypatch):
    written, notes = composed(tmp_path, monkeypatch, review="yes",
                              additions={"architecture": "## Layers (drop)\n\n## Down's layers\n\nFour of ours.\n"})
    text = written[0].text
    assert "Three of them." not in text and "Four of ours." in text and not any("adds to no skill" in n for n in notes)


def test_context_lists_the_read_as_a_layer_between_general_and_the_project(tmp_path, monkeypatch, capsys):
    import json

    from vyvid import cli

    up, head = upstream(tmp_path)
    down, _, _ = read_of(tmp_path, monkeypatch, up, head)
    assert cli.main(["context", str(down), "--no-pull", "--json"]) == 0
    layers = json.loads(capsys.readouterr().out)["layers"]
    assert [x["scope"] for x in layers] == ["general", "up", "down"] and layers[1]["read"] == {"by": "down", "commit": head, "standing": "knowledge"}
    assert cli.main(["context", str(down), "--no-pull"]) == 0
    assert f"a snapshot of commit {head[:12]}, read by down: knowledge alone" in capsys.readouterr().out
