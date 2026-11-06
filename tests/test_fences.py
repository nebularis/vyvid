# SPDX-License-Identifier: MIT
"""A code fence as CommonMark has it, wherever a document is read for its structure."""

from vyvid import anchors, extract, skills


def slugs(*lines: str) -> list[str]:
    return [slug for _, _, slug in anchors.headings(list(lines))]


def test_an_inline_code_span_at_the_start_of_a_line_opens_no_fence():
    assert slugs("```` ```turtle-example ```` is illustrative", "## After") == ["after"]


def test_a_heading_inside_a_real_fence_is_not_a_heading():
    assert slugs("```bash", "# a comment", "```", "## After") == ["after"]


def test_a_shorter_fence_does_not_close_a_longer_one():
    assert slugs("````markdown", "```", "# inside", "```", "````", "## After") == ["after"]


def test_a_line_with_text_after_the_marks_does_not_close_a_fence():
    assert slugs("```", "```bash", "# inside", "```", "## After") == ["after"]


def test_the_other_mark_does_not_close_a_fence():
    assert slugs("~~~", "```", "# inside", "~~~", "## After") == ["after"]


def test_a_tilde_fence_may_hold_backticks_in_its_info_string():
    assert slugs("~~~ `info`", "# inside", "~~~", "## After") == ["after"]


def test_a_skill_keeps_its_headings_after_an_inline_code_span():
    _, parts = skills.sections("Intro\n\n```` ```x ```` text\n\n## One\n\nBody\n\n## Two\n\nMore\n")
    assert [heading for heading, _ in parts] == ["One", "Two"]


def test_decision_numbers_are_read_after_an_inline_code_span():
    lines = ["```` ```x ```` text", "1. One", "```", "2. Inside", "```", "3. Three"]
    assert extract.section_numbers(lines, 1, len(lines)) == [1, 3]
