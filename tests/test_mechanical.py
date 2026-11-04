# SPDX-License-Identifier: MIT
"""The generator of benchmark/symbols/mechanical.py: questions drawn from ast with a fixed seed, and the words of a name removed from a docstring's sentence."""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

spec = importlib.util.spec_from_file_location("mechanical", Path(__file__).parents[1] / "benchmark" / "symbols" / "mechanical.py")
mech = sys.modules["mechanical"] = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mech)


def source(n: int) -> str:
    return f'''"""Module {n} keeps the ledgers of one customer between runs."""


def post_entry_{n}(ledger):
    """Post an entry to the ledger once, whatever the retries."""


def undocumented_{n}():
    return 1


class Ledger{n}:
    """A ledger kept per key, which counts every posted entry."""

    def reopen(self):
        """Reopen the ledger when it was closed. It does nothing otherwise."""
'''


def corpus(tmp_path: Path, modules: int = 12):
    files = []
    for n in range(modules):
        name = f"pkg/tests/test_m{n}.py" if n % 3 == 0 else f"pkg/m{n}.py"
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source(n), encoding="utf-8")
        files.append(name)
    symbols, docs = mech.parsed(tmp_path, files)
    rows = [{"rowid": i, "file": s["file"], "line": s["line"], "name": s["name"], "kind": "function"} for i, s in enumerate(symbols, 1)]
    return symbols, docs, rows


def test_a_fixed_seed_gives_the_same_questions_and_another_seed_gives_others(tmp_path):
    symbols, modules, rows = corpus(tmp_path)
    a = mech.questions(symbols, modules, rows, seed=7, count=10)
    assert a == mech.questions(symbols, modules, rows, seed=7, count=10)
    assert a != mech.questions(symbols, modules, rows, seed=8, count=10)
    assert {m: len(qs) for m, qs in a.items()} == {"name": 10, "meaning": 10, "module": 10}


def test_only_documented_symbols_are_asked_about(tmp_path):
    symbols, modules, rows = corpus(tmp_path)
    asked = {q["name"] for q in mech.questions(symbols, modules, rows, seed=1, count=100)["name"]}
    assert asked and not any(name.startswith("undocumented") for name in asked)
    assert len(asked) == 2 * 12 + 1  # a post and a ledger for each module, and the one method name they share


def test_the_words_of_a_name_are_removed_from_the_sentence_with_their_endings():
    assert mech.without_name("Post an entry to the ledger once, whatever the retries", "post_entry") == "an to the ledger once, whatever the retries"
    assert mech.without_name("Reopens the ledger when it was closed", "reopenLedger") == "the when it was closed"
    assert mech.without_name("Retried writes are retrying", "retry") == "writes are"
    assert mech.without_name("Posting is not postal", "post") == "is not postal"


def test_a_meaning_question_shares_no_word_with_its_name_and_is_not_empty(tmp_path):
    symbols, modules, rows = corpus(tmp_path)
    for q in mech.questions(symbols, modules, rows, seed=3, count=100)["meaning"]:
        assert mech.words_in(q["q"]) >= mech.MIN_WORDS
        for word in mech.name_words(q["name"]):
            assert not re.search(rf"\b{re.escape(word)}\b", q["q"], re.I)


def test_the_first_sentence_is_one_line_without_markup_or_a_closing_stop():
    assert mech.first_sentence("Rank the ``symbols``\nby meaning. Then fuse them.\n\nMore.") == "Rank the symbols by meaning"
    assert mech.first_sentence("No full stop here") == "No full stop here"


def test_a_question_without_test_files_leaves_them_out(tmp_path):
    symbols, modules, rows = corpus(tmp_path)
    made = mech.questions(symbols, modules, rows, seed=2, count=100, only="code")
    assert made["name"] and not any(mech.is_test(q["file"]) for qs in made.values() for q in qs)
    assert mech.is_test("a/tests/x.py") and mech.is_test("a/test_x.py") and mech.is_test("a/conftest.py") and not mech.is_test("a/latest.py")


def test_a_module_question_is_answered_by_any_result_of_its_file():
    q = {"file": "a.py", "rowid": None}
    assert mech.answered("module", q, [{"file": "b.py", "rowid": 1}, {"file": "a.py", "rowid": 2}]) == 2
    assert mech.answered("name", {"rowid": 5}, [{"file": "a.py", "rowid": 4}]) is None
