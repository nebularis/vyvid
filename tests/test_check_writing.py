# SPDX-License-Identifier: MIT
"""The writing and publication check: what fails, what warns, and which files are user-facing."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

spec = importlib.util.spec_from_file_location("check_writing", Path(__file__).parents[1] / "tools" / "check_writing.py")
check = sys.modules["check_writing"] = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check)


def ids(tmp_path):
    (tmp_path / "docs/developer").mkdir(parents=True)
    (tmp_path / "docs/developer/INDEX.md").write_text("| Unit | Prefix |\n|---|---|\n| vyvid-framework | VYD |\n", encoding="utf-8")
    return check.delivery_ids(tmp_path)


def rules(path, text, pattern=None):
    return [(f.line, f.rule.split(" (")[0], f.blocking) for f in check.check_file(path, text, pattern)]


def test_a_semicolon_in_prose_fails_and_one_in_code_does_not():
    text = "A clause; another.\n\n```\nx = 1; y = 2\n```\n\nSee `a; b` here.\n"
    assert rules("docs/developer/x.md", text) == [(1, "a semicolon in prose. Use a period or a comma", True)]


def test_a_hard_wrapped_paragraph_warns():
    assert rules("docs/developer/x.md", "One line of a paragraph\ncontinued here.\n") == [
        (2, "a hard-wrapped line. Keep a paragraph or a list entry on one line", False)]


def test_user_facing_text_may_not_name_a_working_document_or_a_slice(tmp_path):
    pattern = ids(tmp_path)
    text = "See [the plan](docs/developer/plans/x.md).\n\nBuilt in VYD-2.\n\nThe `docs/developer/` folder, as answered.\n"
    failures = [(line, rule) for line, rule, blocking in rules("README.md", text, pattern) if blocking]
    assert failures == [(1, "user-facing text refers to a working document"), (3, "user-facing text names the delivery identifier VYD-2")]
    assert rules("src/vyvid/cli.py", "help='as VYD-Q10 decided'\n", pattern) == [
        (1, "user-facing text names the delivery identifier VYD-Q10", True)]


def test_a_working_document_may_name_its_own_slices(tmp_path):
    assert rules("docs/developer/status/x.md", "VYD-2 is building, see plans/x.md.\n", ids(tmp_path)) == []
