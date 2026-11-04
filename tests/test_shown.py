# SPDX-License-Identifier: MIT
"""A register type shown only when asked for: ``shown = "asked"``, as slices are, and as terms are."""

from __future__ import annotations

import pyoxigraph as ox
import pytest

from test_identifiers import commit, git, write
from test_index_core import Words
from vyvid import ask, registers
from vyvid import build as builder
from vyvid.config import load
from vyvid.model import KI, node
from vyvid.registers import DeclarationError

STANDARDS = "| ID | Claim |\n|---|---|\n| STD-1 | **A ledger is kept per key.** |\n"
BOARD = ("| Slice | Deliverable | State | Blocked on |\n|---|---|---|---|\n"
         "| WB-1 | the ledger board | built 2026-11-03, building 2026-11-03 | |\n"
         "| WB-2 | the ledger sweep | planned | WB-1 |\n")
CONFIG = """[framework]
store = "{store}"

[[projects]]
name = "proj"
code = "{code}"

[projects.families]
STD = {{ defined = "docs:standards.md", type = "standard" }}
WB = {{ pattern = 'WB-\\d+', defined = "docs:board.md", type = "slice" }}
"""


@pytest.fixture
def world(tmp_path):
    code = tmp_path / "code"
    write(code / "docs/standards.md", STANDARDS)
    write(code / "docs/board.md", BOARD)
    git(code, "init", "-q", "-b", "main")
    commit(code)
    write(tmp_path / "config.toml", CONFIG.format(store=(tmp_path / "idx").as_posix(), code=code.as_posix()))
    config = load(tmp_path / "config.toml")
    out = builder.build(config, config.projects["proj"], model=Words())
    return config, code, out


def ids(a, kinds=frozenset(), named=frozenset()):
    return sorted(r["id"] for r in ask.candidates(a, set(kinds), set(), set(), named))


def test_a_slice_board_is_read_as_written_and_a_slice_waits_on_what_blocks_it(world):
    config, code, out = world
    assert not [p for p in out.problems if "WB-" in p or "State" in p], "a State of several words is not refused"
    store = builder.open_store(builder.store_dir(config, config.projects["proj"]) / "store")
    states = {r["id"].value: r["state"].value for r in store.query(
        f"SELECT ?id ?state WHERE {{ GRAPH ?g {{ ?n <{KI}identifier> ?id ; <{KI}state> ?state }} }}")}
    assert states == {"WB-1": "built 2026-11-03, building 2026-11-03", "WB-2": "planned"}
    assert list(store.quads_for_pattern(node("proj", "WB-2"), ox.NamedNode(KI + "waitsOn"), node("proj", "WB-1"), None))


def test_find_leaves_out_a_type_shown_only_when_asked_for_unless_kind_or_the_question_names_it(world):
    a = ask.open_stack(world[0], world[1], model=Words())
    assert ids(a) == ["STD-1"]
    assert ids(a, {"Slice"}) == ["WB-1", "WB-2"]
    assert ids(a, named=frozenset({"WB2"})) == ["STD-1", "WB-2"]
    assert ids(a, named=frozenset({"PROJWB2"})) == ["STD-1", "WB-2"], "a qualified spelling names it too"
    assert ids(a, named=frozenset({"WB9"})) == ["STD-1"]


def test_exclude_keeps_such_a_type_out_as_it_keeps_terms_out(world):
    a = ask.open_stack(world[0], world[1], model=Words())
    kinds = ask.filters(a, exclude="standard")[0]
    assert "Slice" not in kinds and "Term" not in kinds and "Standard" not in kinds and "Question" in kinds
    assert ask.filters(a, kind="slice")[0] == {"Slice"}
    assert ask.filters(a, kind="slice,term", exclude="slice")[0] == {"Term"}
    assert ask.asked_for(a) == {"Term", "Slice"}


def test_find_shows_a_named_slice_first_and_no_slice_otherwise(world, capsys):
    a = ask.open_stack(world[0], world[1], model=Words())
    ask.find(a, "ledger", set(), set(), set(), 10)
    plain = capsys.readouterr().out
    assert "STD-1" in plain and "WB-" not in plain
    ask.find(a, "WB-2 ledger", set(), set(), set(), 10)
    named = capsys.readouterr().out
    assert [l.split()[1] for l in named.splitlines()[2:] if l[:1].isdigit()][0] == "WB-2" and "STD-1" in named
    ask.find(a, "ledger", {"Slice"}, set(), set(), 10)
    assert "STD-1" not in capsys.readouterr().out


def test_a_value_other_than_asked_or_always_is_a_problem():
    with pytest.raises(DeclarationError, match="type 'x' is shown 'never', not one of always, asked"):
        registers.declarations([("t", '[types.x]\nclass = "X"\nshown = "never"\n')])
    types = registers.types_for([])
    assert types.asked == {"Slice"} and types.types["slice"] == "Slice"
    later = registers.declarations([("a", '[types.x]\nclass = "X"\nshown = "asked"\n'), ("b", '[types.x]\nclass = "X"\n')])
    assert later.asked == set(), "a later declaration of a type replaces an earlier one"
