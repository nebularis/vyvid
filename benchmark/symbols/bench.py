# SPDX-License-Identifier: MIT
"""Score the ways `vyd find --kind symbol` could rank a project's symbols, on questions fixed in advance.

    mise run bench:symbols -- --config <configuration> [--out <folder>] [--questions <file>]

The configuration declares one project for each corpus the questions name, each with ``[[projects.symbols]]``, and an
``[embedding] cache`` that holds the model. Each project's symbols are parsed into a store under ``--out``, and
the repository the project points at is only read.

The ways, each ranking the same symbols:

``word``
    FTS5 with BM25 over name, signature and doc, the name weighing most
``all``
    vectors over every symbol
``kinds``
    vectors over functions, types, classes and methods only. Instances, constructors and fields are not embedded
``fused``
    reciprocal rank fusion of ``word`` and ``kinds``
``docs``, ``docs+word``
    ``kinds`` and ``fused`` with the doc before the signature in the text that is embedded
``word+all``
    ``word`` fused with ``all``, to see what leaving a kind out costs
``all-docs``
    ``all`` with the doc before the signature, to separate what the order gains from what the kinds cost

Each is scored by ``hit@5``, the share of questions where an expected symbol is in the top five, and ``MRR``, the mean
reciprocal rank of the first expected symbol in the top eight, per corpus and over all questions together. An expected
symbol is named as the symbol is under its module, ``Owner.name`` for a field or a constructor. Every
embedding is made from nothing, in a folder of its own, so the time and the bytes are those of a cold build.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
import time
from pathlib import Path

import numpy as np

from vyvid import embed
from vyvid.config import load
from vyvid.symbols import store

HERE = Path(__file__).resolve().parent
# The kinds embedded when instances, constructors and fields are left out.
KINDS = frozenset({"function", "method", "data", "newtype", "type", "class", "interface", "enum", "record", "annotation", "data-family", "type-family"})
TOP, DEPTH = 5, 8
METHODS = ("word", "all", "kinds", "fused", "docs", "docs+word", "word+all", "all-docs")


def qual(row: dict) -> str:
    return row["id"].removeprefix(f"{row['package']}:{row['module']}.")


def embedded(rows: list[dict], directory: Path, spec, model, kinds, docs_first: bool = False) -> dict:
    """Embed the chosen rows from nothing and read the vectors back. Returns the rowids, the matrix, the seconds and the bytes."""
    entries = {str(r["rowid"]): store.vector_text(r, docs_first) for r in rows if kinds is None or r["kind"] in kinds}
    directory.mkdir(parents=True, exist_ok=True)
    start = time.perf_counter()
    embed.build(entries, directory, spec, model, name=store.VECTORS)
    seconds = time.perf_counter() - start
    ids, matrix = store.load_vectors(directory, spec)
    return {"ids": ids, "matrix": matrix, "seconds": seconds, "bytes": (directory / store.VECTORS).stat().st_size, "count": len(ids)}


def rankings(db, words: str, question: np.ndarray, sets: dict) -> dict[str, list[int]]:
    """Each way's rowids for one question, best first."""
    word = store.word_rank(db, words)
    meaning = {k: [i for i, _ in store.meaning_rank(v["ids"], v["matrix"], question)] for k, v in sets.items()}
    return {"word": word, "all": meaning["all"], "kinds": meaning["kinds"], "fused": [i for i, _ in store.fuse(word, meaning["kinds"])],
            "docs": meaning["docs"], "docs+word": [i for i, _ in store.fuse(word, meaning["docs"])],
            "word+all": [i for i, _ in store.fuse(word, meaning["all"])], "all-docs": meaning["alldocs"]}


def timed(sets: dict, db, model, texts: list[str]) -> dict[str, float]:
    """Milliseconds per question for each way, over every question, the model already loaded."""
    out = {m: 0.0 for m in METHODS}
    for words in texts:
        start = time.perf_counter()
        store.word_rank(db, words)
        out["word"] += time.perf_counter() - start
        start = time.perf_counter()
        question = model.question(words)
        encode = time.perf_counter() - start
        for key, method in (("all", "all"), ("kinds", "kinds"), ("docs", "docs"), ("alldocs", "all-docs")):
            start = time.perf_counter()
            store.meaning_rank(sets[key]["ids"], sets[key]["matrix"], question)
            out[method] += encode + time.perf_counter() - start
        for method, key in (("fused", "kinds"), ("docs+word", "docs"), ("word+all", "all")):
            start = time.perf_counter()
            store.fuse(store.word_rank(db, words), [i for i, _ in store.meaning_rank(sets[key]["ids"], sets[key]["matrix"], question)])
            out[method] += encode + time.perf_counter() - start
    return {m: 1000 * t / len(texts) for m, t in out.items()}


def corpus(name: str, project, questions: list[dict], spec, model, out: Path) -> dict:
    directory = out / name
    start = time.perf_counter()
    counts, problems = store.build(project, directory)
    parse_seconds = time.perf_counter() - start
    db = store.connect(directory / store.DB)
    rows = store.rows(db)
    by_rowid = {r["rowid"]: r for r in rows}
    sets = {"all": embedded(rows, directory / "v-all", spec, model, None), "kinds": embedded(rows, directory / "v-kinds", spec, model, KINDS),
            "docs": embedded(rows, directory / "v-docs", spec, model, KINDS, docs_first=True),
            "alldocs": embedded(rows, directory / "v-alldocs", spec, model, None, docs_first=True)}
    results: dict[str, list[dict]] = {m: [] for m in METHODS}
    for q in questions:
        ranked = rankings(db, q["q"], model.question(q["q"]), sets)
        for method, rowids in ranked.items():
            names = [qual(by_rowid[i]) for i in rowids[:DEPTH]]
            place = next((n for n, x in enumerate(names, 1) if x in q["expect"]), None)
            results[method].append({"q": q["q"], "hit": place is not None and place <= TOP, "rr": 1 / place if place else 0.0, "top": names[:TOP]})
    ms = timed(sets, db, model, [q["q"] for q in questions])
    db.close()
    return {"files": counts["parsed"], "symbols": counts["symbols"], "parse_seconds": parse_seconds, "problems": problems, "results": results, "ms": ms,
            "embedding": {k: {f: v[f] for f in ("count", "seconds", "bytes")} for k, v in sets.items()}}


def report(done: dict[str, dict]) -> None:
    for name, c in done.items():
        n = len(c["results"]["word"])
        print(f"\n== {name}: {c['files']} files, {c['symbols']} symbols, parsed in {c['parse_seconds']:.2f} s, {n} questions, {len(c['problems'])} problems")
        for key, e in c["embedding"].items():
            print(f"   vectors {key:<6} {e['count']:>6} embedded in {e['seconds']:6.1f} s, {e['bytes']:>9,} bytes")
    print(f"\n{'method':<11}" + "".join(f"{name + ' hit@5':>12}{name + ' MRR':>10}" for name in done) + f"{'all hit@5':>12}{'all MRR':>10}{'ms/query':>10}")
    for method in METHODS:
        line, hits, rr, total = f"{method:<11}", 0, 0.0, 0
        for c in done.values():
            r = c["results"][method]
            line += f"{sum(x['hit'] for x in r) / len(r):>12.3f}{sum(x['rr'] for x in r) / len(r):>10.3f}"
            hits, rr, total = hits + sum(x["hit"] for x in r), rr + sum(x["rr"] for x in r), total + len(r)
        ms = sum(c["ms"][method] for c in done.values()) / len(done)
        print(line + f"{hits / total:>12.3f}{rr / total:>10.3f}{ms:>10.1f}")
    print("\nquestions with no expected symbol in the top five")
    for method in METHODS:
        lost = [(name, x["q"]) for name, c in done.items() for x in c["results"][method] if not x["hit"]]
        print(f"  {method}: {len(lost)}" + "".join(f"\n    [{name}] {q}" for name, q in lost))


def main() -> int:
    p = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    p.add_argument("--config", type=Path, required=True, help="a vyvid configuration declaring a project with symbols for each corpus")
    p.add_argument("--questions", type=Path, default=HERE / "questions.json")
    p.add_argument("--out", type=Path, help="the folder for the stores, the vectors and results.json, a temporary one by default")
    a = p.parse_args()
    config = load(a.config.expanduser())
    out = (a.out.expanduser() if a.out else Path(tempfile.mkdtemp(prefix="vyvid-symbols-"))).resolve()
    out.mkdir(parents=True, exist_ok=True)
    corpora = json.loads(a.questions.read_text(encoding="utf-8"))["corpora"]
    if missing := [n for n in corpora if n not in config.projects or not config.projects[n].symbols]:
        p.error(f"the configuration needs a project with symbols for {', '.join(missing)}")
    model = embed.Model(config.embedding)
    done = {name: corpus(name, config.projects[name], questions, config.embedding, model, out) for name, questions in corpora.items()}
    report(done)
    (out / "results.json").write_text(json.dumps(done, indent=1), encoding="utf-8")
    print(f"\nwritten to {out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
