"""PL-1 and PL-2: a Turtle term anchor, and the hint a whole-file pointer's note gives."""

from __future__ import annotations

import pytest

from vyvid import anchors

TTL = """@prefix mork: <http://example.org/mork#> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .

mork:Bottom a owl:Class .

mork:Chaining a owl:Class ;
    rdfs:comment "A composition." ;
    owl:disjointWith mork:Collection .

# a comment between statements
mork:Collection a owl:Class ;
    rdfs:label "collection" .

other:Bottom a owl:Class .
"""


@pytest.fixture
def root(tmp_path):
    (tmp_path / "m.ttl").write_text(TTL, encoding="utf-8")
    return tmp_path


def test_a_prefixed_name_resolves_to_its_statement(root):
    assert anchors.resolve_part(root, "m.ttl::mork:Chaining") == "m.ttl:6-8"


def test_the_range_stops_before_a_comment_and_a_blank_line(root):
    assert anchors.resolve_part(root, "m.ttl::mork:Collection") == "m.ttl:11-12"


def test_a_local_name_matches_when_one_subject_has_it(root):
    assert anchors.resolve_part(root, "m.ttl::Chaining") == "m.ttl:6-8"


def test_a_local_name_two_subjects_share_is_ambiguous(root):
    with pytest.raises(anchors.Unresolved, match="more than once"):
        anchors.resolve_part(root, "m.ttl::Bottom")


def test_a_term_the_file_does_not_describe_is_an_error(root):
    with pytest.raises(anchors.Unresolved, match="no statement"):
        anchors.resolve_part(root, "m.ttl::mork:Missing")


def test_a_term_is_not_found_in_an_object_position(root):
    with pytest.raises(anchors.Unresolved):
        anchors.resolve_part(root, "m.ttl::mork:Composition")


def test_the_hint_for_a_long_markdown_file_names_its_first_section(tmp_path):
    (tmp_path / "a.md").write_text("# Title\n\n## First part\n" + "text\n" * 250, encoding="utf-8")
    assert "a.md#first-part" in anchors.hint(tmp_path, "a.md")


def test_the_hint_for_a_long_python_file_names_a_top_level_name(tmp_path):
    (tmp_path / "a.py").write_text("def build():\n    pass\n" + "# x\n" * 250, encoding="utf-8")
    assert "a.py::build" in anchors.hint(tmp_path, "a.py")


def test_the_hint_for_a_long_turtle_file_names_a_term(tmp_path):
    (tmp_path / "a.ttl").write_text("mork:Bottom a owl:Class .\n" + "# x\n" * 250, encoding="utf-8")
    assert "a.ttl::mork:Bottom" in anchors.hint(tmp_path, "a.ttl")


def test_a_file_with_nothing_to_name_has_no_hint(tmp_path):
    (tmp_path / "a.txt").write_text("x\n" * 250, encoding="utf-8")
    assert anchors.hint(tmp_path, "a.txt") == ""
