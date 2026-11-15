"""PL-3: the limits on a claim and on a pointer bite for a row the baseline does not list."""

from __future__ import annotations

from vyvid import limits

PROBLEMS = [
    "docs/a.md:20: NOTE-10 has a claim of 203 characters, which is cut at 200",
    "docs/m.md:75: MEC-63 has a pointer at the whole of tools/x.py, 295 lines, which read refuses. Name a part, for example tools/x.py::f",
    "docs/m.md:75: MEC-63 has a pointer at the whole of docs/y.md, 298 lines, which read refuses",
    "docs/m.md:12: MEC-1 has Pointer 'nowhere.md': nowhere.md is not a file",
]


def test_only_the_two_limits_are_defects_and_a_row_counts_once_per_kind():
    assert limits.defects(PROBLEMS) == {("NOTE-10", "claim"): "docs/a.md:20", ("MEC-63", "pointer"): "docs/m.md:75"}


def test_a_baseline_line_is_an_identifier_a_kind_and_a_reason():
    text = "# the old ones\nNOTE-10 claim  # TD-1\n\nMEC-63 pointer\n"
    assert limits.baseline(text) == {("NOTE-10", "claim"), ("MEC-63", "pointer")}


def test_a_defect_the_baseline_lacks_is_new():
    new, stale = limits.compare(limits.defects(PROBLEMS), {("NOTE-10", "claim")})
    assert new == [("MEC-63", "pointer", "docs/m.md:75")] and stale == []


def test_a_baseline_line_with_no_defect_is_stale():
    new, stale = limits.compare(limits.defects(PROBLEMS), {("NOTE-10", "claim"), ("MEC-63", "pointer"), ("TD-9", "claim")})
    assert new == [] and stale == [("TD-9", "claim")]
