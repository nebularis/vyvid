# SPDX-License-Identifier: MIT
"""The work board: its parser, the join across branches, the generated regions, the hook check, presence, the
settings that name a project's levels, ladder and places, and a branch whose text is hostile. Each test that
reads git runs it in a temporary repository, and none touches the real home."""

from __future__ import annotations

import os
import shlex
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

from test_project_file import commit as commit_all, put, repo as project_repo
from vyvid import cli
from vyvid.config import ConfigError, load
from vyvid.resolve import bind_in
from vyvid.work import core, settings
from vyvid.work.core import Repo, Rules, Unit
from vyvid.work.settings import Work

DEV = Path("docs/developer")
A2 = "building 2026-10-30, briefed 2026-10-27"
ALPHA = f"""# Alpha: status

**Unit ID:** `alpha`
**Status:** building 2026-10-30. Slice AL-2 next.

## Position

| Slice | Deliverable | State | Blocked on |
|---|---|---|---|
| AL-1 | the parser | merged 2026-10-28, verified 2026-10-27, built 2026-10-25, briefed 2026-10-20 | |
| AL-2 | the join | {A2} | |
| AL-3 | the tool | planned | AL-2 |
"""
PLAN = "# Alpha\n\n**Unit type:** multi-slice unit, one tool\n**Prefix:** AL\n"
OLD_BOARD = """| # | Slice | Tranche | State | Blocked on |
|---|---|---|---|---|
| C9b3 | set comparisons | T1 | planned | |
| B2.1 (harden the harness) | harness | T1 | planned | |
| AOR-10, AOR-11 | the pair | T2 | planned | |
"""


def sh(cwd: Path, *args: str) -> str:
    return subprocess.run(list(args), cwd=cwd, capture_output=True, text=True, check=True).stdout.strip()


def identify(root: Path) -> None:
    sh(root, "git", "config", "user.email", "test@example.org")
    sh(root, "git", "config", "user.name", "Test")
    sh(root, "git", "config", "commit.gpgsign", "false")


def commit(root: Path, rel: str, text: str) -> str:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    sh(root, "git", "add", ".")
    sh(root, "git", "commit", "-q", "--no-verify", "-m", f"edit {rel}")
    return sh(root, "git", "rev-parse", "HEAD")


def on_branch(repo: Repo, name: str, rel: str, text: str, new: bool = True) -> str:
    """Commit one file on a branch, then return to main. Returns the new tip."""
    sh(repo.root, "git", "checkout", "-q", *(["-b", name] if new else [name]))
    tip = commit(repo.root, rel, text)
    sh(repo.root, "git", "checkout", "-q", "main")
    return tip


def work_for(root: Path, **kwargs) -> Work:
    return Work(status=root / DEV / "status", plans=root / DEV / "plans", index=root / DEV / "INDEX.md",
                roadmap=root / DEV / "ROADMAP.md", validation=root / DEV / "validation", **kwargs)


@pytest.fixture
def repo(tmp_path: Path) -> Repo:
    """A repository with main committed and pushed to a bare repository under two remote names."""
    root, bare = tmp_path / "work", tmp_path / "bare.git"
    root.mkdir()
    sh(root, "git", "init", "-q", "-b", "main")
    identify(root)
    commit(root, "README.md", "A file.\n")
    commit(root, (DEV / "status/alpha.md").as_posix(), ALPHA)
    commit(root, (DEV / "plans/alpha.md").as_posix(), PLAN)
    bare.mkdir()
    sh(bare, "git", "init", "-q", "--bare")
    sh(root, "git", "remote", "add", "origin", str(bare))
    sh(root, "git", "remote", "add", "origin-ssh", str(bare))
    sh(root, "git", "push", "-q", "origin", "main")
    sh(root, "git", "fetch", "-q", "--all")
    return Repo(root, work_for(root))


def with_a2(state: str, drop_a3: bool = False) -> str:
    text = ALPHA.replace(A2, state)
    return text.replace("| AL-3 | the tool | planned | AL-2 |\n", "") if drop_a3 else text


RULES = Rules(Work(status=Path("s"), plans=Path("p")))


def unit(text: str) -> dict[str, Unit]:
    return {"alpha": RULES.parse_unit("alpha", text)}


def section(text: str, start: str, end: str | None = None) -> str:
    tail = text.split(start)[1]
    return tail.split(end)[0] if end else tail


def cells_of(block: str, first: str) -> list[str]:
    return core.cells(next(line for line in block.splitlines() if line.startswith(f"| {first} |")))


# ---- the parser ----------------------------------------------------------------------------------

def test_parse_state_reads_the_trail() -> None:
    assert RULES.parse_state("merged 2026-10-28, verified 2026-10-27, built 2026-10-25") == (
        "merged", "2026-10-28", (("merged", "2026-10-28"), ("verified", "2026-10-27"), ("built", "2026-10-25")))
    assert RULES.parse_state("planned") == ("planned", "", (("planned", ""),))
    assert RULES.parse_state("building 2026-10-30, and a note")[2] == (("building", "2026-10-30"),)
    assert RULES.parse_state("Done (`6b2a577`)") == (None, "", ())
    assert RULES.parse_state("**done**, 2026-10-09") == (None, "", ())
    assert RULES.parse_state("blocked 2026-10-01 on the review") == ("blocked", "2026-10-01", (("blocked", "2026-10-01"),))


def test_find_board_reads_the_standard_board() -> None:
    board = RULES.find_board("alpha", ALPHA)
    lines = ALPHA.splitlines()
    assert board is not None
    assert board.line == lines.index("| Slice | Deliverable | State | Blocked on |") + 1
    assert [r.id for r in board.rows] == ["AL-1", "AL-2", "AL-3"]
    assert [r.deliverable for r in board.rows] == ["the parser", "the join", "the tool"]
    assert [r.blocked_on for r in board.rows] == ["", "", "AL-2"]
    assert [r.line for r in board.rows] == [next(i for i, l in enumerate(lines, 1) if l.startswith(f"| {r.id} |")) for r in board.rows]
    assert board.anchor == "#position"


def test_find_board_reads_the_older_board() -> None:
    board = RULES.find_board("old", OLD_BOARD)
    assert board is not None
    assert [r.id for r in board.rows] == ["C9b3", "B2.1", "AOR-10"]
    assert [r.deliverable for r in board.rows] == ["set comparisons", "harness", "the pair"]


def test_find_board_skips_tables_without_a_state_column() -> None:
    text = "| Name | Note |\n|---|---|\n| x | y |\n\n| Slice | State |\n|---|---|\n| AL-1 | planned |\n"
    board = RULES.find_board("u", text)
    assert board is not None and [r.id for r in board.rows] == ["AL-1"]
    assert RULES.find_board("u", "# No table here\n\nJust prose.\n") is None


def test_parse_unit_reads_state_kind_prefix_and_next() -> None:
    u = RULES.parse_unit("alpha", ALPHA, PLAN)
    assert (u.state, u.day, u.kind, u.prefix, u.next) == ("building", "2026-10-30", "multi-slice unit", "AL", "AL-2")
    bare = RULES.parse_unit("alpha", ALPHA)
    assert (bare.kind, bare.prefix) == ("unit", "")


def _rows(*states: str) -> list[core.Row]:
    text = "| Slice | Deliverable | State | Blocked on |\n|---|---|---|---|\n" + "".join(f"| X-{n} | d | {c} | |\n" for n, c in enumerate(states, 1))
    return list(RULES.find_board("x", text).rows)


def test_a_board_rolls_up_to_one_unit_state() -> None:
    assert RULES.rollup(_rows("built 2026-11-02", "building 2026-11-01", "building 2026-10-30")) == ("building", "2026-10-30"), "the day the work started"
    assert RULES.rollup(_rows("built 2026-10-09", "planned")) == ("built", "2026-10-09"), "a paused unit is not building"
    assert RULES.rollup(_rows("verified 2026-10-20", "built 2026-10-27", "merged 2026-10-30")) == ("built", "2026-10-30"), "the lowest word, the latest day"
    assert RULES.rollup(_rows("planned", "blocked")) == ("blocked", ""), "nothing moving and something blocked"
    assert RULES.rollup(_rows("planned", "briefed")) == ("briefed", "")
    assert RULES.rollup(_rows("merged 2026-10-30", "dropped")) == ("merged", "2026-10-30"), "a dropped row is set aside"
    assert RULES.rollup(_rows("dropped", "dropped")) == ("dropped", "")
    assert RULES.rollup(_rows("Done (abc)")) is None


def test_a_unit_state_shows_each_branch_further_on() -> None:
    def one(state: str, day: str = "") -> Unit:
        return Unit("u", "unit", state, day, "", None)
    boards = {"main": {"u": one("planned")}, "b1": {"u": one("built", "2026-11-02")}, "b2": {"u": one("building", "2026-11-01")},
              "b3": {"u": one("planned")}, "b4": {"u": Unit("u", "unit", None, "", "", None)}}
    assert RULES.unit_state("u", boards["main"]["u"], boards) == "planned · built 2026-11-02 on b1 · building 2026-11-01 on b2"
    assert RULES.unit_state("u", None, {"b1": boards["b1"]}) == "? · built 2026-11-02 on b1"


def test_join_picks_winner_and_marks_stale_and_moved() -> None:
    main, b, c = (unit(with_a2(s)) for s in ("built 2026-10-25", "verified 2026-10-27", "built 2026-10-25"))
    joined = RULES.join({"main": main, "b": b, "c": c})[("alpha", "AL-2")]
    assert joined.winner == ("b", b["alpha"].board.rows[1])
    assert joined.stale == [] and joined.moved == ["b"]
    merged = unit(with_a2("merged 2026-10-28"))
    assert RULES.join({"main": merged, "c": c})[("alpha", "AL-2")].stale == ["c"]
    claim_b, claim_c = unit(with_a2("building 2026-10-30")), unit(with_a2("building 2026-11-01"))
    assert RULES.join({"main": main, "b": claim_b, "c": claim_c})[("alpha", "AL-2")].claims == ["b", "c"]
    no_a3 = unit(with_a2("built 2026-10-25", drop_a3=True))
    assert RULES.join({"main": no_a3, "b": b})[("alpha", "AL-3")].moved == ["b"]
    first, second = RULES.join({"main": main, "b": b, "c": c}), RULES.join({"c": c, "b": b, "main": main})
    assert list(first) == list(second) and all(first[k].winner == second[k].winner for k in first)


OFF_ROWS = "| C9b3b | x | planned | |\n| 1. | x | planned | |\n| B1 | x | planned | |\n"
OLD_IDS = ALPHA.replace("AL-1", "C1").replace("AL-2", "C2").replace("AL-3", "C3")
ONLY = "| Slice | Deliverable | State | Blocked on |\n|---|---|---|---|\n| AL-1 | x | planned | |\n"


def test_join_leaves_out_rows_off_the_grammar_and_counts_them() -> None:
    board = ALPHA.replace("| AL-3 | the tool | planned | AL-2 |\n", OFF_ROWS).replace("| AL-2 |", "| AL-9 |")
    assert set(RULES.join({"main": unit(board)})) == {("alpha", "AL-1"), ("alpha", "AL-9")}
    assert set(RULES.join({"main": unit(ONLY + OFF_ROWS)})) == {("alpha", "AL-1")}
    assert RULES.off_grammar({"main": unit(ONLY + OFF_ROWS), "b": unit(ONLY)}) == {"main": 3, "b": 0}


def test_moves_text_names_ids_or_the_remedy() -> None:
    assert RULES.moves_text(["AL-2"], 0) == "AL-2"
    assert RULES.moves_text([], 5).startswith("board not on the grammar, 5 rows")
    assert "vyd work normalise" in RULES.moves_text([], 5)
    assert RULES.moves_text([], 0) == "no mark"
    assert "2 rows not on the grammar" in RULES.moves_text(["AL-2"], 2)


# ---- git ------------------------------------------------------------------------------------------

def test_read_blobs_returns_text_exact(repo: Repo) -> None:
    first, second = "café — dash\n", "second file\n"
    commit(repo.root, "docs/one.md", first)
    commit(repo.root, "docs/two.md", second)
    one, two = (sh(repo.root, "git", "rev-parse", f"HEAD:docs/{n}.md") for n in ("one", "two"))
    assert repo.read_blobs([one, two]) == {one: first, two: second}
    assert repo.read_blobs([]) == {}


def test_units_at_reads_a_tip_without_checkout(repo: Repo) -> None:
    main_tip = sh(repo.root, "git", "rev-parse", "main")
    edit_tip = on_branch(repo, "edit", (DEV / "status/alpha.md").as_posix(), with_a2("built 2026-11-01, " + A2))
    assert repo.units_at(edit_tip)["alpha"].board.rows[1].state == "built"
    old = repo.units_at(main_tip)["alpha"]
    assert old.board.rows[1].state == "building"
    assert (old.kind, old.prefix) == ("multi-slice unit", "AL")


def test_branches_fold_remotes_and_report_drift(repo: Repo, tmp_path: Path) -> None:
    root = repo.root
    on_branch(repo, "loc", "n/loc.txt", "x\n")
    on_branch(repo, "ahead", "n/ahead.txt", "x\n")
    on_branch(repo, "behind", "n/behind.txt", "x\n")
    sh(root, "git", "push", "-q", "origin", "ahead", "behind")
    ahead_tip = on_branch(repo, "ahead", "n/ahead2.txt", "y\n", new=False)
    clone = tmp_path / "clone2"
    sh(tmp_path, "git", "clone", "-q", str(tmp_path / "bare.git"), str(clone))
    identify(clone)
    sh(clone, "git", "checkout", "-q", "behind")
    behind_tip = commit(clone, "n/behind2.txt", "y\n")
    sh(clone, "git", "push", "-q", "origin", "behind")
    sh(clone, "git", "checkout", "-q", "-b", "remo", "origin/main")
    commit(clone, "n/remo.txt", "z\n")
    sh(clone, "git", "push", "-q", "origin", "remo")
    sh(root, "git", "fetch", "-q", "--all")
    found = repo.branches()
    assert [b.name for b in found] == ["ahead", "behind", "loc", "main", "remo"]
    by = {b.name: b for b in found}
    assert by["main"].drift == "pushed" and by["main"].ahead_of_main == 0
    assert by["loc"].drift == "local only" and by["loc"].ahead_of_main == 1
    assert (by["ahead"].drift, by["ahead"].tip, by["ahead"].ahead_of_main) == ("local ahead 1, not pushed", ahead_tip, 2)
    assert (by["behind"].drift, by["behind"].tip) == ("local behind 1, not pulled", behind_tip)
    assert by["remo"].drift == "remote only" and by["remo"].ahead_of_main == 1
    assert Path(by["main"].worktree).resolve() == root.resolve() and by["loc"].worktree == ""


def test_share_on_main_measures_content(repo: Repo) -> None:
    lines = [f"line{n}" for n in range(10)]
    tip = on_branch(repo, "feat", "data.txt", "\n".join(lines) + "\n")
    commit(repo.root, "data.txt", "\n".join(lines[:5]) + "\n")
    assert repo.share_on_main(tip) == "50% of 10"
    sh(repo.root, "git", "checkout", "-q", "-b", "empty")
    sh(repo.root, "git", "commit", "-q", "--no-verify", "--allow-empty", "-m", "nothing")
    empty = sh(repo.root, "git", "rev-parse", "HEAD")
    sh(repo.root, "git", "checkout", "-q", "main")
    assert repo.share_on_main(empty) == "nothing added"


def test_board_text_shows_what_differs_from_main(repo: Repo) -> None:
    record = (DEV / "status/alpha.md").as_posix()
    b_tip = on_branch(repo, "b", record, with_a2("built 2026-11-01, " + A2))
    on_branch(repo, "docs", "README.md", "Changed.\n")
    text = repo.board_text(False, False, False)
    work, branches = section(text, "## Work", "## Branches"), section(text, "## Branches")
    assert cells_of(work, "AL-2")[4] == "b"
    assert "| AL-1 |" not in work and "| AL-3 |" not in work
    assert cells_of(branches, "b")[5] == "AL-2" and cells_of(branches, "docs")[5] == "no mark"
    everything = section(repo.board_text(True, False, False), "## Work", "## Branches")
    assert all(f"| {s} |" in everything for s in ("AL-1", "AL-2", "AL-3"))
    with_commits = section(repo.board_text(False, False, True), "## Work", "## Branches")
    assert cells_of(with_commits, "AL-2")[4] == f"b at {sh(repo.root, 'git', 'rev-parse', '--short', b_tip)}"
    only = section(repo.board_text(True, False, False, state="built"), "## Work", "## Branches")
    assert "| AL-2 |" in only and "| AL-1 |" not in only


def test_a_branch_with_old_ids_is_named_not_listed(repo: Repo) -> None:
    on_branch(repo, "old", (DEV / "status/alpha.md").as_posix(), OLD_IDS.replace("| C3 | the tool | planned | C2 |\n", ""))
    sh(repo.root, "git", "push", "-q", "origin", "old")
    text = repo.board_text(False, False, False)
    assert "board not on the grammar, 2 rows" in cells_of(section(text, "## Branches"), "old")[5]
    assert "| C1 |" not in section(text, "## Work", "## Branches")


# ---- generated regions ------------------------------------------------------------------------------

def test_render_index_replaces_only_the_region() -> None:
    begin, end = RULES.work.markers["index_begin"], RULES.work.markers["index_end"]
    assert "`vyd work build`" in begin and "mise" not in begin
    appended = RULES.render_index("# Index\n", "new\n")
    assert appended.startswith("# Index\n") and begin in appended and appended.endswith(end + "\n")
    text = "intro\n\n" + begin + "\n\nold\n\n" + end + "\n\ntrailer\n"
    out = RULES.render_index(text, "new\n")
    assert out == "intro\n\n" + begin + "\n\nnew\n\n" + end + "\n\ntrailer\n"
    assert RULES.render_index(out, "new\n") == out and RULES.render_index(appended, "new\n") == appended


def test_build_checks_then_writes(repo: Repo, capsys: pytest.CaptureFixture[str]) -> None:
    index = repo.work.index
    assert repo.build(check=True) == 1
    assert "`vyd work build`" in capsys.readouterr().out and not index.exists()
    assert repo.build(check=False) == 0 and index.exists()
    assert repo.build(check=True) == 0
    region = repo.region_text()
    assert "| alpha | multi-slice unit | AL | building 2026-10-30 | AL-2 |" in region
    assert "docs/developer/status/alpha.md#position |" in region
    assert "| AL-2 | the join | alpha | building 2026-10-30 |" in region
    assert "[plan](plans/alpha.md), [status](status/alpha.md)" in region


def test_gantt_draws_one_bar_per_dated_slice() -> None:
    board = ("**Status:** building 2026-10-30.\n\n| Slice | Deliverable | State | Blocked on |\n|---|---|---|---|\n"
             "| AL-1 | the parser | merged 2026-10-28, verified 2026-10-27, built 2026-10-25, briefed 2026-10-20 | |\n"
             "| AL-2 | the join | building 2026-10-30, briefed 2026-10-27 | |\n| AL-3 | the tool | planned | |\n| AL-4 | the gate | blocked 2026-10-29 | |\n")
    joined = RULES.join({"main": {"alpha": RULES.parse_unit("alpha", board)}})
    lines = RULES.gantt_text(joined, "t")
    assert lines[:3] == ["```mermaid", core.GANTT_THEME, "gantt"] and lines[-1] == "```" and "    section alpha" in lines
    bars = [l for l in lines if ":done," in l or ":active," in l or ":crit," in l]
    assert len(bars) == 3
    assert any(l.endswith(":done, al1, 2026-10-20, 2026-10-28") for l in bars)
    assert any(l.endswith(":active, al2, 2026-10-27, 2026-10-30") for l in bars)
    assert any(l.endswith(":crit, al4, 2026-10-29, 2026-10-30") for l in bars)
    assert not any("AL-3" in l for l in lines)
    closed = "\n".join(RULES.gantt_text(joined, "t", None, True))
    assert " al1," in closed and " al2," not in closed and " al4," not in closed
    assert RULES.gantt_text(RULES.join({}), "t") == [] and 'K2["built or verified"]' in "\n".join(RULES.gantt_key())


@pytest.mark.parametrize("deliverable, label", [
    ("track D, the prover spike, the pack that covers FM-D0 to FM-D4", "track D the prover spike"),
    ("the evaluator and its compiled forms of the rules", "the evaluator and its compiled"),
    ("the evaluator and its compilers forms of the rules", "the evaluator and its"),
    ("a" * 40, "a" * 30),
    ("the parser", "the parser"),
])
def test_a_bars_label_is_cut_at_a_comma_then_a_word_then_the_limit(deliverable: str, label: str) -> None:
    board = f"**Status:** building 2026-10-30.\n\n| Slice | Deliverable | State | Blocked on |\n|---|---|---|---|\n| AL-2 | {deliverable} | building 2026-10-27 | |\n"
    bars = [l for l in RULES.gantt_text(RULES.join({"main": {"alpha": RULES.parse_unit("alpha", board)}}), "t") if ":active," in l]
    assert [b.split(" :")[0].strip() for b in bars] == [f"AL-2 {label}"]


def test_render_regions_appends_replaces_and_is_idempotent() -> None:
    regions = {"glance": "G\n", "branches": "B\n"}
    mark = {n: RULES.markers_for(n) for n in regions}
    appended = RULES.render_regions("# Roadmap\n", regions)
    assert appended.startswith("# Roadmap\n") and appended.endswith(mark["branches"][1] + "\n")
    old = ("top\n\n" + mark["glance"][0] + "\n\nold\n\n" + mark["glance"][1] + "\n\nmiddle\n\n" + mark["branches"][0] + "\n\nold\n\n" + mark["branches"][1] + "\n\nend\n")
    new = RULES.render_regions(old, regions)
    assert new == ("top\n\n" + mark["glance"][0] + "\n\nG\n\n" + mark["glance"][1] + "\n\nmiddle\n\n" + mark["branches"][0] + "\n\nB\n\n" + mark["branches"][1] + "\n\nend\n")
    assert RULES.render_regions(new, regions) == new and RULES.render_regions(appended, regions) == appended


def test_roadmap_regions_summarise_units_and_branches(repo: Repo) -> None:
    on_branch(repo, "b", (DEV / "status/alpha.md").as_posix(), with_a2("built 2026-11-01"))
    sh(repo.root, "git", "push", "-q", "origin", "b")
    regions = repo.roadmap_regions()
    row = cells_of(regions["glance"], "[alpha](plans/alpha.md)")
    assert "1 built" in row[4] and row[5] == "b" and "```mermaid" in regions["glance"]
    assert cells_of(regions["branches"], "`b`")[4] == "AL-2" and "| `main` |" not in regions["branches"]
    assert "One chart per unit with five dated slices or more" in regions["glance"]


def test_build_roadmap_checks_then_writes(repo: Repo, capsys: pytest.CaptureFixture[str]) -> None:
    path = repo.work.roadmap
    assert repo.build_roadmap(check=True) == 1
    assert "`vyd work roadmap`" in capsys.readouterr().out and not path.exists()
    assert repo.build_roadmap(check=False) == 0
    assert RULES.markers_for("glance")[0] in path.read_text(encoding="utf-8") and repo.build_roadmap(check=True) == 0


def test_the_decisions_region_reads_registers_by_family_type(repo: Repo) -> None:
    dev = repo.root / DEV
    (dev / "pending.md").write_text("| ID | Question |\n|---|---|\n| PDD-1 | **Which store?** and more | x |\n| PDD-2 | Other | y |\n", encoding="utf-8")
    (dev / "debt.md").write_text("| ID | Debt |\n|---|---|\n| TD-1 | one |\n", encoding="utf-8")
    decisions = repo.root / "docs/architecture/decisions"
    decisions.mkdir(parents=True)
    (decisions / "README.md").write_text("| ADR | Subject | Status |\n|---|---|---|\n| [D-1](D-1.md) | A choice | Proposed |\n| [ZED-2](ZED-2.md) | Done | Accepted |\n", encoding="utf-8")
    full = Repo(repo.root, work_for(repo.root, decisions=decisions, roadmap_section="9"), {"pending-decision": [dev / "pending.md"], "debt": [dev / "debt.md"]})
    text = full.decisions_text()
    assert "1 Proposed decisions, 2 pending design decisions, and 1 rows of [technical debt](debt.md)" in text
    assert "### 9.1 Proposed decisions" in text and "[D-1](../architecture/decisions/D-1.md)" in text and "ZED-2" not in text
    assert "| PDD-1 | Which store? |" in text
    assert "### Pending" not in repo.decisions_text() and "pending" not in repo.decisions_text().split("\n")[0]


# ---- the hook check ---------------------------------------------------------------------------------

def test_check_holds_records_to_the_ladder_the_grammar_and_the_region(repo: Repo) -> None:
    out: list[str] = []
    repo.build(check=False)
    assert repo.check(say=out.append) == 0 and out == []
    bad = (ALPHA.replace("| AL-2 | the join | " + A2, "| AL-2 | the join | building |").replace("| AL-3 |", "| old3 |")
           .replace("| AL-1 | the parser | merged", "| AL-1 | the parser | done, merged") .replace("**Status:** building 2026-10-30", "**Status:** planned"))
    (repo.work.status / "alpha.md").write_text(bad, encoding="utf-8")
    assert repo.check(say=out.append) == 1
    joined = "\n".join(out)
    assert "building needs the day it was reached, as `building YYYY-MM-DD`" in joined
    assert "old3: a slice id must match" in joined and "AL-1: the State cell opens with 'done, merged" in joined
    assert "the Status line reads 'planned'" in joined and "the work-board region is stale" in joined
    out.clear()
    assert repo.check(["README.md"], out.append) == 0 and out == [], "a file that is neither a record nor the index is not checked"
    assert repo.check([repo.rel(repo.work.status / "alpha.md")], out.append) == 1


# ---- presence ---------------------------------------------------------------------------------------

def _touch(path: Path, epoch: float) -> None:
    os.utime(path, (epoch, epoch))


def test_the_session_and_client_come_from_the_environment() -> None:
    assert core.session_from_environment({"CLAUDE_CODE_SESSION_ID": "abc", "AI_AGENT": "claude-code_2-1-309_agent"}) == ("abc", "claude-code_2-1-309_agent")
    assert core.session_from_environment({"CLAUDE_CODE_ENTRYPOINT": "cli"}) == ("", "cli")
    assert core.session_from_environment({"VYD_SESSION_ID": "s", "VYD_CLIENT": "c"}) == ("s", "c")
    assert core.session_from_environment({}) == ("", "")


def test_write_presence_keeps_the_first_since_and_quotes_what_it_writes(tmp_path: Path) -> None:
    directory = tmp_path / "agents"
    path = core.write_presence(directory, "abc", "client", "m", "build", ["X-1"], "2026-11-02T10:00:00Z")
    assert path == directory / "abc.toml"
    assert tomllib.loads(path.read_text(encoding="utf-8")) == {"session": "abc", "client": "client", "model": "m", "role": "build", "on": ["X-1"], "since": "2026-11-02T10:00:00Z"}
    core.write_presence(directory, "abc", "client", "m", "build", ["X-1"], "2026-11-02T11:00:00Z")
    assert tomllib.loads(path.read_text(encoding="utf-8"))["since"] == "2026-11-02T10:00:00Z"
    with pytest.raises(ValueError):
        core.write_presence(directory, "abc", "client", "m", "boss", [], "2026-11-02T10:00:00Z")
    assert core.write_presence(directory, "", "", "", "read", [], "2026-11-02T10:00:00Z").name == "unnamed.toml"
    hostile = core.write_presence(directory, "../../x", 'c"\nrole = "build', "m", "read", ['a"b'], "2026-11-02T10:00:00Z")
    assert hostile.parent == directory and tomllib.loads(hostile.read_text(encoding="utf-8"))["client"] == 'c"\nrole = "build'
    assert tomllib.loads(hostile.read_text(encoding="utf-8"))["role"] == "read"


def test_list_presence_ages_out_and_never_goes_negative(tmp_path: Path) -> None:
    directory = tmp_path / "agents"
    assert core.list_presence(directory, 1_000_000.0) == []
    now_epoch = 1_000_000.0
    for name, touched in (("fresh", now_epoch - 300), ("stale", now_epoch - core.PRESENCE_HOURS * 3600 - 60), ("future", now_epoch + 600)):
        _touch(core.write_presence(directory, name, "c", "m", "read", [], "2026-11-02T10:00:00Z"), touched)
    (directory / "broken.toml").write_text("not = [toml", encoding="utf-8")
    _touch(directory / "broken.toml", now_epoch)
    assert {f["session"]: f["touched"] for f in core.list_presence(directory, now_epoch)} == {"fresh": "5 min ago", "future": "0 min ago"}


def test_leave_presence_removes_the_file(tmp_path: Path) -> None:
    path = core.write_presence(tmp_path, "abc", "c", "m", "read", [], "2026-11-02T10:00:00Z")
    assert core.leave_presence(tmp_path, "abc") is True and not path.exists() and core.leave_presence(tmp_path, "abc") is False


def test_presence_text_warns_only_of_another_builder() -> None:
    def one(session: str, role: str) -> list[dict[str, str]]:
        return [{"session": session, "client": "c", "model": "m", "role": role, "on": "AL-1", "since": "s", "touched": "1 min ago"}]
    assert "nobody here" in core.presence_text([], "abc") and "`vyd here --role" in core.presence_text([], "abc")
    assert "another session is building here" in core.presence_text(one("zzz", "build"), "abc")
    mine = core.presence_text(one("abc", "build"), "abc")
    assert any(line.startswith("| you abc") for line in mine.splitlines()) and "another session" not in mine
    assert "another session" not in core.presence_text(one("zzz", "review"), "abc")


# ---- settings ---------------------------------------------------------------------------------------

def parsed(raw, **where) -> tuple[Work | None, list[str]]:
    problems: list[str] = []
    return settings.parse(raw, lambda v: Path("/p") / v.split(":", 1)[-1], "project 'x'", problems), problems


def test_an_empty_table_gives_the_defaults_and_no_table_gives_none() -> None:
    assert parsed(None) == (None, [])
    work, problems = parsed({})
    assert problems == [] and work.status == Path("/p/status") and work.plans == Path("/p/plans")
    assert (work.levels, work.main, work.index, work.roadmap, work.presence) == (("unit", "slice"), "main", None, None, "")
    assert (work.dated_from, work.done_from, work.closed_from) == ("building", "built", "merged")
    assert work.dated == {"building", "built", "verified", "merged", "tagged"} and work.closed == ("merged", "tagged", "dropped")
    assert work.markers["index_begin"].startswith("<!-- BEGIN GENERATED work-board. Written by `vyd work build`")


@pytest.mark.parametrize("raw, fragment", [
    ({"nonsense": 1}, "unknown keys nonsense"), ({"ladder": ["a"]}, "work.ladder"), ({"ladder": ["Planned", "x"]}, "work.ladder"),
    ({"aside": ["blocked", "planned"]}, "share planned"), ({"levels": ["unit"]}, "work.levels"), ({"main": "-x"}, "work.main"),
    ({"dated_from": "later"}, "must be a word of the ladder"), ({"presence": "../x"}, "work.presence"), ({"presence": ".git/x"}, "work.presence"),
    ({"presence": "/abs"}, "work.presence"), ({"slice_pattern": "(["}, "does not compile"), ({"markers": {"roadmap_begin": "x"}}, "must hold {name}"),
    ({"markers": {"index_begin": "a\nb"}}, "one line"), ({"commands": {"nope": "x"}}, "unknown key nope"), ({"status": 3}, "must be a path"),
    ({"chart_after": 0}, "chart_after"), ({"rename": [{"unit": "../x", "prefixes": ["A"]}]}, "work.rename needs a unit"),
    ({"rename": [{"unit": "u", "prefixes": ["A"], "patterns": ["(["]}]}, "does not compile"),
])
def test_a_bad_setting_is_reported_and_names_the_key(raw, fragment) -> None:
    _, problems = parsed(raw)
    assert any(fragment in p for p in problems), problems


def test_the_roadmap_names_only_branches_a_remote_knows_and_the_board_still_shows_the_rest(repo: Repo, capsys: pytest.CaptureFixture[str]) -> None:
    record = (DEV / "status/alpha.md").as_posix()
    on_branch(repo, "private-probe", record, with_a2("verified 2026-11-04, " + A2))
    on_branch(repo, "shared", record, with_a2("built 2026-11-01, " + A2))
    sh(repo.root, "git", "push", "-q", "origin", "shared")
    unpushed = on_branch(repo, "shared", record, with_a2("merged 2026-11-03, " + A2), new=False)
    assert sh(repo.root, "git", "rev-parse", "shared") == unpushed
    roadmap = "\n".join(repo.roadmap_regions().values())
    assert "private-probe" not in roadmap and "`shared`" in roadmap and "2026-11-04" not in roadmap and "2026-11-03" not in roadmap
    assert "on 2 branches" in roadmap and "1 merged, 1 built, 1 planned" in roadmap
    assert [b.name for b in repo.branches(published=True)] == ["main", "shared"] and not any(b.worktree for b in repo.branches(published=True))
    assert repo.build_roadmap(check=False) == 0
    assert "private-probe" not in repo.work.roadmap.read_text(encoding="utf-8")
    assert "| private-probe |" in repo.board_text(False, False, False)


def alpha_row(regions: dict[str, str]) -> list[str]:
    return cells_of(regions["glance"], "[alpha](plans/alpha.md)")


def test_a_local_only_current_branch_keeps_its_own_boards_and_its_name_stays_out(repo: Repo) -> None:
    record = (DEV / "status/alpha.md").as_posix()
    sh(repo.root, "git", "checkout", "-q", "-b", "wip-probe")
    commit(repo.root, record, with_a2("built 2026-11-01, " + A2))
    regions = repo.roadmap_regions()
    assert "1 merged, 1 built, 1 planned" in alpha_row(regions)[4]
    assert "wip-probe" not in "\n".join(regions.values()) and "on 1 branches" in regions["glance"]
    assert "| `wip-probe` |" not in regions["branches"]


def test_a_pushed_current_branch_shows_a_board_change_it_has_not_pushed(repo: Repo) -> None:
    record = (DEV / "status/alpha.md").as_posix()
    sh(repo.root, "git", "checkout", "-q", "-b", "cur")
    commit(repo.root, record, with_a2("built 2026-11-01, " + A2))
    sh(repo.root, "git", "push", "-q", "origin", "cur")
    commit(repo.root, record, with_a2("merged 2026-11-03, " + A2))
    regions = repo.roadmap_regions()
    assert "2 merged, 1 planned" in alpha_row(regions)[4] and alpha_row(regions)[5] == "cur"


def test_a_local_only_branch_stays_out_of_the_roadmap_when_another_branch_is_current(repo: Repo) -> None:
    record = (DEV / "status/alpha.md").as_posix()
    on_branch(repo, "private-probe", record, with_a2("verified 2026-11-04, " + A2))
    sh(repo.root, "git", "checkout", "-q", "-b", "shared")
    commit(repo.root, record, with_a2("built 2026-11-01, " + A2))
    sh(repo.root, "git", "push", "-q", "origin", "shared")
    regions = repo.roadmap_regions()
    assert "private-probe" not in "\n".join(regions.values()) and "2026-11-04" not in "\n".join(regions.values())
    assert "| private-probe |" in repo.board_text(False, False, False)


# ---- the command line, over a repository that declares its own project ------------------------------------

TOML = """[project]
name = "proj"
visibility = "public"
docs = "code:docs"

[project.work]
status = "docs:developer/status"
plans = "docs:developer/plans"
index = "docs:developer/INDEX.md"
roadmap = "docs:developer/ROADMAP.md"
"""


@pytest.fixture(autouse=True)
def no_configuration(tmp_path, monkeypatch):
    monkeypatch.setenv("VYVID_CONFIG", str(tmp_path / "absent.toml"))
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID", raising=False)


def project(tmp_path: Path, toml: str = TOML, files: dict | None = None) -> Path:
    root = project_repo(tmp_path, "proj", toml, {**{"docs/developer/status/alpha.md": ALPHA, "docs/developer/plans/alpha.md": PLAN}, **(files or {})})
    identify(root)
    return root


def run(args: list[str], capsys) -> tuple[int, str, str]:
    code = cli.main(args)
    out = capsys.readouterr()
    return code, out.out, out.err


def test_board_goes_across_branches_and_here_reads_the_one_checkout(tmp_path, capsys) -> None:
    root = project(tmp_path, TOML.replace("[project.work]", '[project.families]\nSL = { pattern = \'AL-\\d+\', defined = "docs:developer/INDEX.md", type = "slice" }\n\n[project.work]'),
                   {"docs/developer/INDEX.md": "| ID | Claim | State |\n|---|---|---|\n| AL-1 | the parser | merged |\n"})
    sh(root, "git", "checkout", "-q", "-b", "side")
    commit(root, "docs/developer/status/alpha.md", with_a2("built 2026-11-01, " + A2))
    sh(root, "git", "checkout", "-q", "main")
    code, out, _ = run(["board", str(root), "--all"], capsys)
    assert code == 0 and "# Work board, 2 branches" in out and "| AL-2 | alpha | the join | built 2026-11-01 | side |" in out
    code, out, _ = run(["board", str(root), "--all", "--state", "merged"], capsys)
    assert "| AL-1 |" in out and "| AL-2 | alpha |" not in out
    code, out, _ = run(["board", str(root), "--here"], capsys)
    assert code == 0 and "AL-1" in out and "the parser" in out and "# Work board" not in out


def test_a_project_without_work_settings_keeps_the_one_checkout_board(tmp_path, capsys) -> None:
    toml = '[project]\nname = "proj"\ndocs = "code:docs"\n\n[project.families]\nSL = { pattern = \'AL-\\d+\', defined = "docs:INDEX.md", type = "slice" }\n'
    root = project(tmp_path, toml, {"docs/INDEX.md": "| ID | Claim | State |\n|---|---|---|\n| AL-1 | the parser | merged |\n"})
    code, out, err = run(["board", str(root), "--all"], capsys)
    assert code == 0 and "the parser" in out and "declares no work settings" in err


def test_build_and_check_through_the_command_line(tmp_path, capsys) -> None:
    root = project(tmp_path)
    assert run(["work", "build", "--check", "--in", str(root)], capsys)[:2] == (1, f"docs/developer/INDEX.md: the work-board region is stale against the status records. Run `vyd work build`\n")
    assert run(["work", "build", "--in", str(root)], capsys)[0] == 0
    assert run(["work", "build", "--check", "--in", str(root)], capsys)[0] == 0
    assert run(["work", "check", "--in", str(root)], capsys) == (0, "", "")
    sh(root, "git", "add", "-A")
    assert run(["work", "check", "--staged", "--in", str(root)], capsys) == (0, "", "")
    (root / "docs/developer/status/alpha.md").write_text(ALPHA.replace("building 2026-10-30. Slice", "later. Slice"), encoding="utf-8")
    sh(root, "git", "add", "-A")
    code, out, _ = run(["work", "check", "--staged", "--in", str(root)], capsys)
    assert code == 1 and "the Status line opens with 'later." in out
    assert run(["work", "roadmap", "--in", str(root)], capsys)[0] == 0
    assert "work-board-glance" in (root / "docs/developer/ROADMAP.md").read_text(encoding="utf-8")
    assert run(["work", "parse", str(root / "docs/developer/status/alpha.md")], capsys)[1].splitlines()[2].startswith("| AL-1 | merged | 2026-10-28 |")


def test_here_writes_lists_and_leaves_in_the_git_directory(tmp_path, capsys, monkeypatch) -> None:
    root = project(tmp_path)
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "sess1")
    code, out, _ = run(["here", "--in", str(root), "--role", "review", "--model", "m", "--on", "AL-1", "--now", "2026-11-02T10:00:00+00:00"], capsys)
    assert code == 0 and "sess1" in out and "review" in out
    assert (root / ".git/vyd/agents/sess1.toml").exists() and sh(root, "git", "status", "--porcelain") == ""
    assert "left" in run(["here", "--in", str(root), "--leave"], capsys)[1]
    assert not (root / ".git/vyd/agents/sess1.toml").exists()


# ---- a project of its own words and places ----------------------------------------------------------------

CUSTOM = """[project]
name = "proj"
docs = "code:docs"

[project.work]
status = "docs:records"
plans = "docs:briefs"
index = "docs:everything.md"
levels = ["epic", "phase", "step"]
ladder = ["idea", "ready", "active", "review", "done"]
aside = ["parked"]
dated_from = "active"
done_from = "review"
closed_from = "done"
main = "trunk"
slice_pattern = 'P-\\d+'
presence = ".agents"
[project.work.markers]
index_begin = "<!-- BEGIN auto: {build} -->"
index_end = "<!-- END auto -->"
[project.work.commands]
build = "make board"
"""
PHASE = """# P

**Phase ID:** `p`
**Status:** active 2026-11-02

| Step | Deliverable | State | Blocked on |
|---|---|---|---|
| P-1 | first | done 2026-11-01, review 2026-10-31, active 2026-10-30 | |
| P-2 | second | active 2026-11-02 | |
| P-3 | third | idea | |
| P-4 | fourth | parked | P-2 |
"""


def custom(tmp_path: Path) -> Repo:
    root = project_repo(tmp_path, "custom", CUSTOM, {"docs/records/p.md": PHASE, "docs/briefs/p.md": "# P\n\n**Phase type:** epic, one\n"})
    sh(root, "git", "branch", "-m", "trunk")
    identify(root)
    config, scope = bind_in(load(), root)
    return Repo.open(scope.work)


def test_levels_ladder_places_and_markers_are_the_projects_own(tmp_path, capsys) -> None:
    repo = custom(tmp_path)
    w = repo.work
    assert (w.unit, w.piece, w.group, w.main, w.dated_from, w.aside) == ("phase", "step", "epic", "trunk", "active", ("parked",))
    assert w.dated == {"active", "review", "done"} and w.closed == ("done",) and w.open == ("idea", "ready", "active", "review", "parked")
    unit = repo.units_here()["p"]
    assert (unit.kind, unit.state, unit.day, unit.next) == ("epic", "active", "2026-11-02", "P-2")
    assert repo.rollup(unit.board.rows) == ("active", "2026-11-02")
    assert repo.findings("docs/records/p.md", PHASE) == []
    assert any("needs the day" in m for m in repo.findings("docs/records/p.md", PHASE.replace("active 2026-11-02", "active")))
    assert any("must match P-\\d+" in m for m in repo.findings("docs/records/p.md", PHASE.replace("P-3", "Q9")))
    text = repo.board_text(True, False, False)
    assert "## Phases" in text and "| Phase | Kind | State | Next | Moved on |" in text and "| Step | Phase | Deliverable |" in text
    assert "| P-4 | p | fourth | parked | trunk | P-2 |" in text
    code = repo.build(False)
    index = (repo.root / "docs/everything.md").read_text(encoding="utf-8")
    assert code == 0 and index.lstrip().startswith("<!-- BEGIN auto: make board -->") and "## Phases" in index and index.rstrip().endswith("<!-- END auto -->")
    assert "Every step on a board" in index and "docs/records/p.md#" in index
    assert repo.region_stale() == []
    (repo.root / "docs/everything.md").write_text("stale\n", encoding="utf-8")
    assert "Run `make board`" in repo.region_stale()[0]
    key = "\n".join(repo.gantt_key())
    assert 'K1["active"]' in key and 'K2["review"]' in key and 'K3["done"]' in key and 'K4["parked"]' in key


def test_a_projects_own_ladder_maps_the_historic_words(tmp_path) -> None:
    from vyvid.work import migrate

    repo = custom(tmp_path)
    assert migrate.map_state(repo, "Done (`abc`)", "")[:2] == ("review", "")
    assert migrate.map_state(repo, "in progress 2026-10-01", "")[:2] == ("active", "2026-10-01")
    assert migrate.map_state(repo, "waiting", "P-1")[0] == "parked"
    assert migrate.map_state(repo, "retired", "") is None, "the project has no dropped word"
    assert migrate.map_state(repo, "idea", "") is None


def test_a_project_with_only_status_and_plans_has_no_index_roadmap_or_validation(tmp_path, capsys) -> None:
    toml = '[project]\nname = "proj"\ndocs = "code:docs"\n\n[project.work]\n'
    root = project(tmp_path, toml, {"docs/status/alpha.md": ALPHA, "docs/plans/alpha.md": PLAN})
    config, scope = bind_in(load(), root)
    repo = Repo.open(scope.work)
    assert (scope.work.index, scope.work.roadmap, scope.work.validation, scope.work.decisions) == (None, None, None, None)
    assert repo.units_here()["alpha"].next == "AL-2"
    assert repo.build(False) == 0 and "no index" in capsys.readouterr().out
    assert repo.build_roadmap(True) == 0 and "no roadmap" in capsys.readouterr().out
    assert repo.check() == 0
    assert "| AL-2 | alpha |" in repo.board_text(True, False, False)
    assert repo.region_text().count("Validation Packs") == 0 and repo.presence_dir().as_posix().endswith(".git/vyd/agents")
    assert "no documents" not in repo.decisions_text() and repo.decisions_text().startswith("Read from the registers in this tree: 0 Proposed decisions.")
    assert run(["work", "build", "--check", "--in", str(root)], capsys)[:2] == (0, "no index\n".replace("no index", "this project declares no index, so there is no region to build"))


# ---- a branch's text is data ------------------------------------------------------------------------------

def test_a_branch_whose_text_attempts_shell_or_path_tricks_runs_and_reads_nothing_it_should_not(repo: Repo, tmp_path: Path) -> None:
    root = repo.root
    marker = tmp_path / "pwned"
    trick = f"$(touch {marker}); `touch {marker}` | rm -rf / ../../../etc/passwd"
    hostile = ALPHA.replace("| AL-3 | the tool | planned | AL-2 |", f"| AL-3 | {trick} | planned | {trick} |\n| AL-4 | x | merged 2026-11-01 | ../../x |")
    branch = "evil;touch${IFS}pwned"
    sh(root, "git", "checkout", "-q", "-b", branch)
    for name in ("alpha", "$(touch pwned)", "a b", "..", "x'y"):
        commit(root, (DEV / f"status/{name}.md").as_posix(), hostile)
    commit(root, (DEV / "status/nested/deep.md").as_posix(), hostile)
    os.symlink("/etc/hostname", root / DEV / "status/link.md")
    sh(root, "git", "add", ".")
    sh(root, "git", "commit", "-q", "--no-verify", "-m", "link")
    sh(root, "git", "checkout", "-q", "main")
    text = repo.board_text(True, True, True)
    assert not marker.exists() and not (root / "pwned").exists() and not Path("pwned").exists()
    assert branch in text and trick.replace("|", "\\|")[:60] in text.replace("  ", " ")
    assert "deep" not in text and "link" not in text.split("## Branches")[0].replace("unlinked", ""), "a nested file and a link are not records"
    assert "$(touch" in text, "the name is text, and a unit named like a command is only a name"
    assert not (root / "etc").exists() and not list(tmp_path.glob("*passwd*"))


def test_a_status_record_that_is_a_link_leaving_the_repository_is_not_read_here(repo: Repo, tmp_path: Path) -> None:
    outside = tmp_path / "outside.md"
    outside.write_text(ALPHA, encoding="utf-8")
    os.symlink(outside, repo.work.status / "linked.md")
    assert "linked" not in repo.units_here() and "alpha" in repo.units_here()


def test_the_module_writes_nothing_inside_a_git_directory(repo: Repo) -> None:
    hostile = Repo(repo.root, work_for(repo.root).__class__(status=repo.work.status, plans=repo.work.plans, index=repo.root / ".git/hooks/pre-commit"))
    with pytest.raises(PermissionError):
        hostile.build(False)
    assert not (repo.root / ".git/hooks/pre-commit").exists()


@pytest.mark.real_trust
def test_a_project_declared_by_a_file_nobody_trusted_writes_nothing(tmp_path, capsys, monkeypatch) -> None:
    root = project(tmp_path, TOML.replace("docs/developer/INDEX.md", ".git/hooks/pre-commit").replace("docs:developer/INDEX.md", "docs:../.git/hooks/pre-commit"))
    code, out, err = run(["work", "build", "--in", str(root)], capsys)
    assert code != 0 and not (root / ".git/hooks/pre-commit").exists()


@pytest.mark.real_trust
def test_untrusted_files_refuse_to_write_but_still_read(tmp_path, capsys) -> None:
    root = project(tmp_path)
    code, _, err = run(["work", "build", "--in", str(root)], capsys)
    assert code == 1 and "nobody has trusted" in err and not (root / "docs/developer/INDEX.md").exists()
    assert run(["work", "build", "--check", "--in", str(root)], capsys)[0] == 1
    assert run(["board", str(root), "--all"], capsys)[0] == 0
    assert run(["here", "--in", str(root), "--role", "read"], capsys)[0] == 1


def test_a_repository_file_may_name_only_paths_inside_the_repository(tmp_path, capsys) -> None:
    from vyvid.config import read_project_file

    root = project(tmp_path, TOML.replace('"docs:developer/INDEX.md"', '"docs:../../escape.md"'))
    _, problems = read_project_file(root / "vyvid.toml")
    assert any("work.index names 'docs:../../escape.md', which leaves the repository" in p for p in problems)
    assert run(["work", "check", "--in", str(root)], capsys)[0] == 2, "the project is set aside, so it declares no work settings"


# ---- a git hook exports GIT_DIR ----------------------------------------------------------------------

HOOK_PROGRAM = ("import sys\nfrom vyvid import config\nconfig.trusted = lambda c: True\nconfig.file_trusted = lambda p: True\n"
                "from vyvid.cli import main\nsys.exit(main(sys.argv[1:]))")
RECORD = "docs/developer/status/alpha.md"
BETA = "# Beta: status\n\n**Unit ID:** `beta`\n**Status:** later. Slice BE-1 next.\n\n| Slice | Deliverable | State | Blocked on |\n|---|---|---|---|\n| BE-1 | the thing | planned | |\n"


def committing(tmp_path: Path, monkeypatch, linked: bool) -> Path:
    """A project with its index built and committed, and a real pre-commit hook that runs the staged check, in the
    main checkout or in a linked worktree. Returns the folder to commit in."""
    root = project(tmp_path)
    assert cli.main(["work", "build", "--in", str(root)]) == 0
    sh(root, "git", "add", "-A")
    sh(root, "git", "commit", "-q", "--no-verify", "-m", "built")
    hook = Path(sh(root, "git", "rev-parse", "--path-format=absolute", "--git-common-dir")) / "hooks" / "pre-commit"
    hook.parent.mkdir(exist_ok=True)
    hook.write_text(f"#!/bin/sh\nexec {shlex.quote(sys.executable)} -c {shlex.quote(HOOK_PROGRAM)} work check --staged --in \"$PWD\"\n", encoding="utf-8")
    hook.chmod(0o755)
    if not linked:
        return root
    work = tmp_path / "linked"
    sh(root, "git", "worktree", "add", "-q", "-b", "side", str(work))
    return work


def attempt(folder: Path, *args: str) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    return subprocess.run(["git", "commit", "-q", "-m", "x", *args], cwd=folder, capture_output=True, text=True, env=env)


BOTH = pytest.mark.parametrize("linked", [False, True], ids=["main checkout", "linked worktree"])


@BOTH
def test_the_staged_check_does_not_crash_under_a_real_hook_and_picks_records_from_the_index(tmp_path, monkeypatch, linked) -> None:
    folder = committing(tmp_path, monkeypatch, linked)
    record = folder / RECORD
    record.write_text(ALPHA.replace("building 2026-10-30. Slice", "later. Slice"), encoding="utf-8")
    (folder / "note.txt").write_text("A note.\n", encoding="utf-8")
    sh(folder, "git", "add", "note.txt")
    assert attempt(folder).returncode == 0, "a record that is not staged is not checked"
    record.write_text(ALPHA.replace("building 2026-10-30. Slice", "later. Slice") + "\n", encoding="utf-8")
    sh(folder, "git", "add", RECORD)
    refused = attempt(folder)
    output = refused.stdout + refused.stderr
    assert refused.returncode != 0 and "the Status line opens with 'later." in output
    assert "Traceback" not in output and "ValueError" not in output
    record.write_text(ALPHA + "\nA note.\n", encoding="utf-8")
    sh(folder, "git", "add", RECORD)
    assert attempt(folder).returncode == 0


@BOTH
@pytest.mark.xfail(strict=True, reason="the check takes the names of the staged records from the index and reads their text from the working tree, the debt row TD-4")
def test_the_staged_check_reads_the_staged_text_of_a_record(tmp_path, monkeypatch, linked) -> None:
    folder = committing(tmp_path, monkeypatch, linked)
    record = folder / RECORD
    record.write_text(ALPHA.replace("building 2026-10-30. Slice", "later. Slice"), encoding="utf-8")
    sh(folder, "git", "add", RECORD)
    record.write_text(ALPHA, encoding="utf-8")
    assert attempt(folder).returncode != 0


@BOTH
def test_a_partial_commit_is_checked_against_its_temporary_index(tmp_path, monkeypatch, linked) -> None:
    folder = committing(tmp_path, monkeypatch, linked)
    beta = "docs/developer/status/beta.md"
    (folder / beta).write_text(BETA, encoding="utf-8")
    assert cli.main(["work", "build", "--in", str(folder)]) == 0
    sh(folder, "git", "add", beta)
    (folder / RECORD).write_text(ALPHA + "\nA note.\n", encoding="utf-8")
    done = attempt(folder, RECORD)
    assert done.returncode == 0, done.stdout + done.stderr
    assert sh(folder, "git", "diff", "--cached", "--name-only") == beta, "the other staged file is left staged"
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    checked = subprocess.run([sys.executable, "-c", HOOK_PROGRAM, "work", "check", "--staged", "--in", str(folder)], capture_output=True, text=True, env=env)
    assert checked.returncode == 1 and "beta.md" in checked.stdout, "the real index does hold the bad file, so the temporary index is what left it out"


@pytest.mark.real_trust
def test_rename_refuses_an_untrusted_project_only_when_it_will_write(tmp_path, capsys) -> None:
    root = project(tmp_path)
    assert run(["work", "rename", "--in", str(root)], capsys)[0] == 0
    code, _, err = run(["work", "rename", "--apply", "--in", str(root)], capsys)
    assert code == 1 and "nobody has trusted" in err
