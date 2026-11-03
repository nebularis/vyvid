# SPDX-License-Identifier: MIT
"""VYD-2, first step: pointer anchors, and the embedding model and its vectors, with nothing of LATTICE's."""

from __future__ import annotations

import numpy as np
import pytest

from vyvid import anchors, embed
from vyvid.config import ConfigError, load


class Words:
    """A stand-in model: a text's vector counts four words, so closeness is checkable by eye."""

    AXES = ("ledger", "minting", "slow", "graph")

    def __init__(self):
        self.calls = []

    def embed(self, texts):
        self.calls.append(len(texts))
        v = np.array([[t.lower().count(a) + 0.01 for a in self.AXES] for t in texts], dtype=np.float32)
        return v / np.linalg.norm(v, axis=1, keepdims=True)

    def question(self, text):
        return self.embed([text])[0]


SPEC = embed.ModelSpec()


def test_a_rebuild_embeds_only_changed_text(tmp_path):
    model = Words()
    entries = {"a": "a ledger account", "b": "minting in Java"}
    assert embed.build(entries, tmp_path, SPEC, model) == 2
    assert embed.build(entries, tmp_path, SPEC, model) == 0
    assert embed.build({**entries, "a": "a ledger posting"}, tmp_path, SPEC, model) == 1
    nodes, vectors = embed.load(tmp_path, SPEC)
    assert nodes == ["a", "b"] and vectors.shape == (2, 4)


def test_vectors_from_another_revision_are_refused_and_rebuilt(tmp_path):
    model = Words()
    embed.build({"a": "ledger"}, tmp_path, SPEC, model)
    other = embed.ModelSpec(revision="another")
    with pytest.raises(embed.Unavailable, match="another model revision"):
        embed.load(tmp_path, other)
    assert embed.build({"a": "ledger"}, tmp_path, other, model) == 1


def test_an_unavailable_model_leaves_no_stale_vectors(tmp_path, monkeypatch):
    embed.build({"a": "ledger"}, tmp_path, SPEC, Words())

    def unavailable(spec):
        raise embed.Unavailable("no network")

    monkeypatch.setattr(embed, "Model", unavailable)
    with pytest.raises(embed.Unavailable):
        embed.build({"a": "a changed text"}, tmp_path, SPEC)
    assert not (tmp_path / embed.VECTORS).exists()


def test_the_model_is_cached_per_model_and_revision(tmp_path):
    spec = embed.ModelSpec(cache=tmp_path)
    assert spec.directory == tmp_path / "BAAI--bge-small-en-v1.5" / spec.revision


def test_join_text_keeps_each_part_once_in_order():
    assert embed.join_text(["**Keyed** accounts", "One account per key.", None, "Keyed accounts"]) == "Keyed accounts. One account per key."


def test_the_embedding_is_configured_and_an_unpinned_model_refused(tmp_path, monkeypatch):
    config = tmp_path / "c.toml"
    config.write_text('[embedding]\nweak = 0.6\nnear = 0.7\ncache = "/tmp/m"\n', encoding="utf-8")
    monkeypatch.setenv("VYVID_CONFIG", str(config))
    spec = load().embedding
    assert (spec.weak, spec.near, spec.repo) == (0.6, 0.7, "BAAI/bge-small-en-v1.5")
    config.write_text('[embedding]\nmodel = "some/other-model"\n', encoding="utf-8")
    with pytest.raises(ConfigError, match="needs its revision"):
        load()


def test_a_section_anchor_resolves_to_its_current_lines(tmp_path):
    (tmp_path / "doc.md").write_text("# Title\n\ntext\n\n## A section\n\nbody\n\n## Next\n", encoding="utf-8")
    assert anchors.resolve_part(tmp_path, "doc.md#a-section") == "doc.md:5-8"


def test_a_repeated_heading_is_suffixed_as_github_does(tmp_path):
    (tmp_path / "doc.md").write_text("## Notes\n\none\n\n## Notes\n\ntwo\n", encoding="utf-8")
    assert anchors.resolve_part(tmp_path, "doc.md#notes-1") == "doc.md:5-7"


def test_a_line_number_is_refused_as_a_pointer(tmp_path):
    (tmp_path / "doc.md").write_text("text\n", encoding="utf-8")
    with pytest.raises(anchors.Unresolved, match="line number"):
        anchors.resolve_part(tmp_path, "doc.md:1-3")


def test_a_python_definition_resolves_to_its_span(tmp_path):
    (tmp_path / "m.py").write_text('"""Doc."""\n\n\ndef f():\n    return 1\n\n\nclass C:\n    pass\n', encoding="utf-8")
    assert anchors.resolve_part(tmp_path, "m.py::f") == "m.py:4-5"
    assert anchors.resolve_part(tmp_path, "m.py::C") == "m.py:8-9"
