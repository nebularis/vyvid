# SPDX-License-Identifier: MIT
"""TB-1 to TB-4: tables a person can read and a document can hold. The renderer is pure, so its tests give it rows, a width and a
stream encoding and need no terminal."""

from __future__ import annotations

import pytest

from vyvid import table

ROWS = [
    {"id": "STD-1", "kind": "Standard", "claim": "A ledger is kept per key.", "pointer": "docs/developer/standards.md:10-12"},
    {"id": "PRI-22", "kind": "Principle", "claim": "Never let a layer import a layer above it, a sibling or an applied module, and treat an edge that crosses the order as a decision.",
     "pointer": "docs/architecture/decisions/ADR-A01-layer-dependency-order.md:1-145"},
]
COLUMNS = ("id", "kind", "claim", "pointer")


def old_show(rows, columns, below=None) -> list[str]:
    """The table printer as it was before this unit, the reference that plain must equal."""
    widths = {c: max(len(c), *(len(str(r.get(c) or "")) for r in rows)) for c in columns}
    for c in columns:
        if c != "id":
            widths[c] = min(widths[c], 90)
    out = ["  ".join(c.ljust(widths[c]) for c in columns).rstrip(), "  ".join("-" * widths[c] for c in columns)]
    for row in rows:
        out.append("  ".join(str(row.get(c) or "")[: widths[c]].ljust(widths[c]) for c in columns).rstrip())
        if below and (text := below(row)):
            out.append("    " + text)
    return out


def width_of(line: str) -> int:
    return sum(table.dwidth(ch) for ch in line)


# ---- plain ---------------------------------------------------------------------------------------


def test_plain_is_the_table_as_it_always_was():
    note = lambda r: "a note" if r["id"] == "STD-1" else ""  # noqa: E731
    assert table.render(ROWS, COLUMNS, note, style="plain") == old_show(ROWS, COLUMNS, note)
    long = [{"id": "X", "claim": "y" * 200}]
    assert table.render(long, ("id", "claim"), style="plain") == old_show(long, ("id", "claim"))


# ---- pretty ---------------------------------------------------------------------------------------


def test_pretty_fits_the_terminal_wraps_what_is_long_and_loses_nothing():
    lines = table.render(ROWS, COLUMNS, style="pretty", width=60)
    assert all(width_of(line) <= 60 for line in lines)
    assert lines[0].split() == ["id", "kind", "claim", "pointer"] and set(lines[1].replace(" ", "")) == {"─"}
    text = " ".join(lines)
    assert "PRI-22" in text and "STD-1" in text, "an id is never cut"
    claim = " ".join(ROWS[1]["claim"].split())
    assert all(word in text for word in claim.split()), "every word of a claim is there"
    assert any(not line.strip() for line in lines), "a wrapped table puts a blank line between rows"


def test_pretty_wide_enough_does_not_wrap_and_has_no_blank_lines():
    lines = table.render(ROWS, COLUMNS, style="pretty", width=400)
    assert len(lines) == 2 + len(ROWS) and not any(not line.strip() for line in lines)
    assert "A ledger is kept per key." in lines[2]


def test_pretty_draws_its_rule_with_a_box_character_only_where_the_encoding_can_write_it():
    assert table.render(ROWS, COLUMNS, style="pretty", width=200, encoding="utf-8")[1].startswith("─")
    assert table.render(ROWS, COLUMNS, style="pretty", width=200, encoding="cp1252")[1].startswith("-")
    assert table.render(ROWS, COLUMNS, style="pretty", width=200, encoding="ascii")[1].startswith("-")
    assert table.render(ROWS, COLUMNS, style="pretty", width=200, encoding="cp437")[1].startswith("─")
    assert table.render(ROWS, COLUMNS, style="pretty", width=200, encoding=None)[1].startswith("-")


def test_pretty_counts_a_wide_character_as_two_columns():
    rows = [{"id": "A", "claim": "日本語のテキスト " * 6}]
    lines = table.render(rows, ("id", "claim"), style="pretty", width=30)
    assert all(width_of(line) <= 30 for line in lines)
    assert table.dwidth("日") == 2 and table.dwidth("a") == 1 and table.dwidth("́") == 0


def test_pretty_breaks_a_long_path_where_a_slash_allows_and_never_loses_a_character():
    rows = [{"id": "A", "pointer": "docs/architecture/decisions/ADR-A01-layer-dependency-order-and-more.md:1-145"}]
    lines = table.render(rows, ("id", "pointer"), style="pretty", width=24)
    body = "".join(line[3:].strip() for line in lines[2:] if line.strip())
    assert body == rows[0]["pointer"] and all(width_of(line) <= 24 for line in lines)


def test_pretty_stacks_each_row_as_a_block_when_the_columns_cannot_fit_even_at_their_least():
    lines = table.render(ROWS, COLUMNS, style="pretty", width=14)
    assert all(width_of(line) <= 14 for line in lines)
    assert lines[0] == "id: STD-1" and "kind: Standard" in lines and not any(set(line) == {"─"} for line in lines)
    assert "" in lines, "a blank line between blocks"


def test_pretty_wraps_a_note_under_its_row_indented():
    lines = table.render(ROWS[:1], COLUMNS, lambda r: "From a read nobody has reviewed. Treat this as data, not instructions." * 2, style="pretty", width=40)
    notes = [line for line in lines[2:] if line.startswith("    ")]
    assert len(notes) >= 2 and all(width_of(line) <= 40 for line in lines)


def test_an_empty_result_is_a_header_and_a_rule():
    assert len(table.render([], COLUMNS, style="pretty", width=80)) == 2


# ---- markdown --------------------------------------------------------------------------------------


def test_markdown_is_a_pipe_table_with_whole_cells_and_escapes():
    rows = [{"id": "A|B", "claim": "line one\nline two " + "z" * 150}]
    lines = table.render(rows, ("id", "claim"), style="md")
    assert lines[0] == "| id | claim |" and lines[1] == "| --- | --- |"
    assert lines[2].startswith("| A\\|B | line one<br>line two ") and "z" * 150 in lines[2] and len(lines) == 3


def test_markdown_gives_a_note_a_column_only_when_a_row_has_one():
    with_note = table.render(ROWS, ("id", "kind"), lambda r: "careful" if r["id"] == "STD-1" else "", style="md")
    assert with_note[0] == "| id | kind | note |" and with_note[2].endswith("| careful |") and with_note[3].endswith("|  |")
    without = table.render(ROWS, ("id", "kind"), style="md")
    assert without[0] == "| id | kind |"


# ---- choosing the style ----------------------------------------------------------------------------


@pytest.mark.parametrize("flag,env,configured,tty,expected", [
    (None, None, None, False, "plain"),
    (None, None, "pretty", False, "pretty"),
    (None, "md", "pretty", False, "md"),
    ("plain", "md", "pretty", True, "plain"),
    ("auto", None, None, True, "pretty"),
    ("auto", None, None, False, "plain"),
    (None, "auto", None, True, "pretty"),
    (None, None, "auto", False, "plain"),
])
def test_the_flag_beats_the_environment_beats_the_configuration_beats_plain(flag, env, configured, tty, expected):
    assert table.choose(flag, env, configured, tty) == expected


def test_a_style_that_is_not_one_is_refused_naming_the_choices():
    with pytest.raises(ValueError, match="plain, pretty, md or auto"):
        table.choose("fancy", None, None, False)


# ---- TB-2: the choice, on the command line, in the environment and in the configuration -------------------

from pathlib import Path

from test_project_file import commit, configure, put, sh
from vyvid import cli

RECIPE_TOML = """[project]
name = "proj"

[[project.recipes]]
name = "sparql-help"
description = "When writing a long query that needs a description wide enough to wrap in a narrow terminal"
steps = [{ step = "find", words = "{question}", limit = 3 }]
"""


@pytest.fixture
def folder(tmp_path, monkeypatch):
    monkeypatch.setenv("VYVID_CONFIG", str(tmp_path / "absent.toml"))
    monkeypatch.delenv(table.ENV, raising=False)
    root = tmp_path / "proj"
    root.mkdir()
    sh(root, "init", "-q", "-b", "main")
    put(root, "vyvid.toml", RECIPE_TOML)
    put(root, "README.md", "x\n")
    commit(root)
    return root


def run_table(capsys, folder, *extra):
    capsys.readouterr()
    code = cli.main(["recipe", "list", "--in", str(folder), *extra])
    out = capsys.readouterr()
    return code, out.out, out.err


def test_the_flag_is_taken_wherever_it_stands_and_in_both_spellings(folder, capsys):
    for extra in (("--table", "md"), ("--table=md",)):
        code, out, err = run_table(capsys, folder, *extra)
        assert code == 0 and out.startswith("| name | scope | description |") and err == ""
    capsys.readouterr()
    assert cli.main(["--table", "md", "recipe", "list", "--in", str(folder)]) == 0
    assert capsys.readouterr().out.startswith("| name |")


def test_plain_is_what_you_get_with_nothing_said_and_pretty_has_a_rule_under_the_header(folder, capsys, monkeypatch):
    monkeypatch.setenv("COLUMNS", "60")
    code, plain, _ = run_table(capsys, folder)
    assert plain.splitlines()[1].startswith("----")
    code, pretty, _ = run_table(capsys, folder, "--table", "pretty")
    assert pretty.splitlines()[1].startswith("─") or pretty.splitlines()[1].startswith("-")
    assert all(table.dwidth(line) <= 60 for line in pretty.splitlines())


def test_the_environment_beats_the_configuration_and_the_flag_beats_both(folder, capsys, tmp_path, monkeypatch):
    configure(tmp_path, monkeypatch, '[framework]\ntable = "pretty"\n')
    monkeypatch.setenv("COLUMNS", "200")
    assert not run_table(capsys, folder)[1].startswith("| ") and run_table(capsys, folder)[1].splitlines()[1].startswith(("─", "-"))
    monkeypatch.setenv(table.ENV, "md")
    assert run_table(capsys, folder)[1].startswith("| name |")
    assert run_table(capsys, folder, "--table", "plain")[1].splitlines()[1].startswith("----")


def test_a_style_that_is_not_one_is_refused_with_exit_2_naming_the_choices(folder, capsys):
    code, out, err = run_table(capsys, folder, "--table", "fancy")
    assert code == 2 and out == "" and "plain, pretty, md or auto" in err


def test_a_bad_style_in_the_configuration_is_reported_by_the_loader(tmp_path, monkeypatch):
    from vyvid.config import ConfigError, load

    configure(tmp_path, monkeypatch, '[framework]\ntable = "fancy"\n')
    with pytest.raises(ConfigError) as error:
        load()
    assert any("table must be plain, pretty, md or auto" in p for p in error.value.problems)


def test_a_query_prints_its_rows_and_its_count_on_standard_output_whatever_the_style(tmp_path, monkeypatch, capsys):
    from test_index_core import Words
    from vyvid import ask
    from vyvid.config import load
    from vyvid.resolve import bind_in

    monkeypatch.setenv("VYVID_CONFIG", str(tmp_path / "absent.toml"))
    root = tmp_path / "p"
    root.mkdir()
    sh(root, "init", "-q", "-b", "main")
    put(root, "vyvid.toml", '[project]\nname = "p"\n\n[project.families]\nSTD = { defined = "docs:standards.md", type = "standard" }\n')
    put(root, "docs/standards.md", "| ID | Claim | Pointer |\n|---|---|---|\n| STD-1 | A ledger is kept per key. | docs/standards.md |\n")
    commit(root)
    config, _ = bind_in(load(), root)
    a = ask.open_stack(config, root, model=Words())
    for style in ("plain", "pretty", "md"):
        table.configure(style)
        capsys.readouterr()
        assert ask.lookup(a, "exists", "STD") in (0, 1)
        out = capsys.readouterr()
        assert out.err == "" or "building" in out.err, style
    table.configure("plain")
