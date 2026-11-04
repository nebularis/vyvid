# SPDX-License-Identifier: MIT
"""VYD-2, third step: registers read by declared register types."""

from __future__ import annotations

from pathlib import Path

import pytest

from vyvid import facets, registers
from vyvid.config import load
from vyvid.patterns import Pattern
from vyvid.resolve import bind, layers

TYPES = registers.declarations([("default", registers.default_declarations())])
TAGGABLE = facets.taggable(facets.merge([("default", facets.default_register())])[1])
STD = Pattern(r"STD-\d+")


def read(tmp_path, header, *rows, rtype="standard"):
    table = f"{header}\n|{'---|' * (header.count('|') - 1)}\n" + "\n".join(rows) + "\n"
    (tmp_path / "r.md").write_text(table, encoding="utf-8")
    return registers.read(tmp_path / "r.md", "r.md", STD, rtype, TYPES, TAGGABLE, tmp_path)


def test_a_row_is_read_by_its_columns(tmp_path):
    rows, problems = read(tmp_path, "| ID | Name | Claim | Audience | Activity | Ratified |",
                          "| STD-1 | a rule | **The rule is this.** Then more. | published | query-writing, documentation | no, added 2026-11-03 |")
    assert not problems
    (row,) = rows
    assert (row.identifier, row.cls, row.label, row.claim, row.status) == ("STD-1", "Standard", "a rule", "The rule is this.", "Proposed")
    assert row.values == {"audience": ["PublishedUse"], "activity": ["query-writing", "documentation"]}
    assert row.pointer == ["r.md:3-3"], "a row with no Pointer points at itself"


@pytest.mark.parametrize("header, row, message", [
    ("| ID | Claim | Audiance |", "| STD-1 | **A claim.** | published |", "column 'Audiance' is neither declared"),
    ("| ID | Claim | Audience |", "| STD-1 | **A claim.** | public |", "Audience 'public', which is not one of"),
    ("| ID | Claim | Technology |", "| STD-1 | **A claim.** | cobol-74 |", "a taggable value of the Technology facet"),
    ("| ID | Claim | Ratified |", "| STD-1 | **A claim.** | perhaps |", "Ratified 'perhaps'"),
    ("| ID | Claim | Does not cover |", f"| STD-1 | **A claim.** | {'x' * 121} |", "Does not cover of 121 characters"),
    ("| ID | Claim |", f"| STD-1 | **{'y' * 201}** |", "a claim of 201 characters, which is cut at 200"),
    ("| ID | Claim | Audience |", "| STD-1 | **A claim.** | published | extra |", "3 cells under 2 headers" if False else "4 cells under 3 headers"),
    ("| ID | Name |", "| STD-1 | a name |", "has no claim"),
])
def test_what_cannot_be_read_is_reported_and_never_stored(tmp_path, header, row, message):
    rows, problems = read(tmp_path, header, row)
    assert any(message in p for p in problems), problems


def test_trailing_signpost_columns_may_be_left_out(tmp_path):
    rows, problems = read(tmp_path, "| ID | Claim | Does not cover | Distinguished from |",
                          "| STD-1 | **A claim.** |", "| STD-2 | **Another.** | the reinstatement credit |")
    assert not problems and rows[1].values == {"doesNotCover": ["the reinstatement credit"]}


def test_a_filled_answered_by_column_answers_the_row(tmp_path):
    rows, _ = read(tmp_path, "| ID | Question | Answered by |", "| STD-1 | **Which?** | ADR-001 |")
    assert rows[0].status == "Answered"


def test_a_later_declaration_adds_and_replaces():
    types = registers.declarations([("default", registers.default_declarations()), ("domain", """
[values.severity]
low = "Low"
high = "High"
[columns]
"Severity" = { property = "severity", kind = "controlled", values = "severity" }
"Cost" = { property = "costNote", kind = "text" }
[types.finding]
class = "Finding"
""")])
    assert types.types["finding"] == "Finding" and types.columns["Cost"].property == "costNote"
    assert types.columns["Severity"].values == "severity"


def test_a_declaration_naming_an_undeclared_value_set_is_refused():
    with pytest.raises(registers.DeclarationError, match="declared nowhere"):
        registers.declarations([("d", '[columns]\n"Mood" = { property = "mood", kind = "controlled", values = "moods" }\n')])


def test_this_repositorys_own_registers_read_without_a_problem(tmp_path, monkeypatch):
    root = Path(__file__).resolve().parents[1]
    families = "\n".join(f'{f} = {{ defined = "docs:developer/{r}.md", type = "{t}" }}' for f, r, t in (
        ("STD", "standards", "standard"), ("PRI", "principles", "principle"), ("CAP", "capabilities", "capability"),
        ("TD", "technical-debt", "debt"), ("PDD", "pending-design-decisions", "pending-decision"), ("BL", "backlog", "backlog")))
    config = tmp_path / "c.toml"
    config.write_text(f'[[projects]]\nname = "vyvid"\ncode = "{root.as_posix()}"\n\n[projects.families]\n{families}\n', encoding="utf-8")
    monkeypatch.setenv("VYVID_CONFIG", str(config))
    c = load()
    project = c.projects["vyvid"]
    rows, problems = registers.read_scope(project, registers.types_for(layers(c, project)), TAGGABLE)
    assert not problems, problems
    assert {r.identifier for r in rows} >= {"STD-1", "STD-18", "PRI-1", "CAP-4"}
