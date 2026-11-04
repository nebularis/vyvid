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

Then the default way, vectors over every symbol with the doc first, is shown beside the chunks of documentation around the code (module
headers, named sections and block comments), embedded the same way in a file of their own:

``symbols``
    the symbols alone, today's default
``docs``
    the chunks alone, with only the best window of a section kept
``mixed``
    both in one list, by raw cosine
``capped``
    ``mixed`` with at most two of five places going to a chunk
``fit``
    three symbols and then two chunks, each by its own cosine
``split``
    five symbols and then three chunks, each by its own cosine, so eight are shown

A question may name ``expect_doc``, the file and lines where the source answers it, and is then answered by a symbol or by a chunk
overlapping those lines. These were fixed from the source before any run. Each way is scored by what it shows, five places, or eight for
``split``, and the questions where it loses a symbol the default found, or finds an answer only a chunk gives, are listed.

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
WITH_DOCS = ("symbols", "docs", "mixed", "capped", "fit", "split")


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


def overlaps(row: dict, expected: list[dict]) -> bool:
    return any(row["file"].endswith(e["file"]) and row["line"] <= e["lines"][1] and row["end_line"] >= e["lines"][0] for e in expected)


def with_docs(db, question: np.ndarray, sets: dict, by_rowid: dict, q: dict) -> dict[str, dict]:
    """For each way of showing the symbols and the chunks together, what it shows for one question and where an expected symbol or chunk is."""
    symbols = store.meaning_rank(sets["alldocs"]["ids"], sets["alldocs"]["matrix"], question)
    docs = store.collapse(db, store.meaning_rank(sets["written"]["ids"], sets["written"]["matrix"], question)) if sets["written"]["count"] else []
    out = {}
    for method in WITH_DOCS:
        shown = store.combine(method, symbols, docs, TOP)
        rows = [by_rowid[i] for i in shown]
        hit_symbol = next((n for n, r in enumerate(rows, 1) if r["kind"] != "doc" and qual(r) in q["expect"]), None)
        hit_doc = next((n for n, r in enumerate(rows, 1) if r["kind"] == "doc" and overlaps(r, q.get("expect_doc", []))), None)
        first = min((n for n in (hit_symbol, hit_doc) if n), default=None)
        out[method] = {"symbol": hit_symbol is not None, "doc": hit_doc is not None, "any": first is not None, "rr": 1 / first if first else 0.0,
                       "top": [qual(r) if r["kind"] != "doc" else f"#{r['name']} {r['file'].rsplit('/', 1)[-1]}:{r['line']}" for r in rows]}
    return out


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


def timed_docs(sets: dict, db, model, texts: list[str]) -> dict[str, float]:
    """Milliseconds per question for each way of showing documentation, the model already loaded, the question embedded once."""
    out = {m: 0.0 for m in WITH_DOCS}
    for words in texts:
        question = model.question(words)
        for method in WITH_DOCS:
            start = time.perf_counter()
            symbols = store.meaning_rank(sets["alldocs"]["ids"], sets["alldocs"]["matrix"], question)
            docs = store.collapse(db, store.meaning_rank(sets["written"]["ids"], sets["written"]["matrix"], question)) if sets["written"]["count"] else []
            store.combine(method, symbols, docs, TOP)
            out[method] += time.perf_counter() - start
    return {f"doc:{m}": 1000 * t / len(texts) for m, t in out.items()}


def corpus(name: str, project, questions: list[dict], spec, model, out: Path) -> dict:
    directory = out / name
    start = time.perf_counter()
    counts, problems = store.build(project, directory)
    parse_seconds = time.perf_counter() - start
    db = store.connect(directory / store.DB)
    everything = store.rows(db)
    by_rowid = {r["rowid"]: r for r in everything}
    rows = [r for r in everything if r["kind"] != "doc"]
    sets = {"all": embedded(rows, directory / "v-all", spec, model, None), "kinds": embedded(rows, directory / "v-kinds", spec, model, KINDS),
            "docs": embedded(rows, directory / "v-docs", spec, model, KINDS, docs_first=True),
            "alldocs": embedded(rows, directory / "v-alldocs", spec, model, None, docs_first=True),
            "written": embedded([r for r in everything if r["kind"] == "doc"], directory / "v-written", spec, model, None)}
    results: dict[str, list[dict]] = {m: [] for m in METHODS}
    for q in questions:
        ranked = rankings(db, q["q"], model.question(q["q"]), sets)
        for method, rowids in ranked.items():
            names = [qual(by_rowid[i]) for i in rowids[:DEPTH]]
            place = next((n for n, x in enumerate(names, 1) if x in q["expect"]), None)
            results[method].append({"q": q["q"], "hit": place is not None and place <= TOP, "rr": 1 / place if place else 0.0, "top": names[:TOP]})
    around = {m: [] for m in WITH_DOCS}
    for q in questions:
        for method, got in with_docs(db, model.question(q["q"]), sets, by_rowid, q).items():
            around[method].append({"q": q["q"], **got})
    ms = timed(sets, db, model, [q["q"] for q in questions])
    ms.update(timed_docs(sets, db, model, [q["q"] for q in questions]))
    db.close()
    return {"files": counts["parsed"], "symbols": counts["symbols"], "docs": counts["docs"], "around": around, "expect_doc": [bool(q.get("expect_doc")) for q in questions], "parse_seconds": parse_seconds, "problems": problems, "results": results, "ms": ms,
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


def report_docs(done: dict[str, dict]) -> None:
    """Each way of showing documentation beside symbols: answers by symbol alone, by chunk too, and what it displaces and gains against the default."""
    for name, c in done.items():
        n = len(c["around"]["symbols"])
        print(f"\n== {name}: {c['docs']} chunks of documentation, {n} questions, {sum(c['expect_doc'])} with an expected section")
    print(f"\n{'way':<9}{'shown':>6}{'symbol hit':>12}{'any hit':>9}{'MRR':>8}{'lost':>6}{'gained':>8}{'ms':>7}")
    for method in WITH_DOCS:
        hits = anys = lost = gained = total = 0
        rr = ms = 0.0
        for c in done.values():
            base = c["around"]["symbols"]
            for x, b in zip(c["around"][method], base):
                total += 1
                hits, anys, rr = hits + x["symbol"], anys + x["any"], rr + x["rr"]
                lost += b["symbol"] and not x["symbol"]
                gained += x["any"] and not b["any"]
            ms += c["ms"][f"doc:{method}"] / len(done)
        print(f"{method:<9}{8 if method == 'split' else 5:>6}{hits:>9}/{total:<2}{anys:>6}/{total:<2}{rr / total:>8.3f}{lost:>6}{gained:>8}{ms:>7.1f}")
    for method in WITH_DOCS[1:]:
        print(f"\n{method}: symbols found by the default and no longer shown")
        for name, c in done.items():
            for x, b in zip(c["around"][method], c["around"]["symbols"]):
                if b["symbol"] and not x["symbol"]:
                    print(f"  [{name}] {x['q'][:70]}  now answered by a chunk: {x['doc']}")
        print(f"{method}: answers found only because of a chunk")
        for name, c in done.items():
            for x, b in zip(c["around"][method], c["around"]["symbols"]):
                if x["any"] and not b["any"]:
                    print(f"  [{name}] {x['q'][:70]}")
    print("\nwhat each way shows for the questions that name expect_doc")
    for name, c in done.items():
        for k, b in enumerate(c["around"]["symbols"]):
            if c["expect_doc"][k]:
                print(f"  [{name}] {b['q'][:80]}")
                for method in WITH_DOCS:
                    x = c["around"][method][k]
                    print(f"     {method:<8} {'S' if x['symbol'] else '-'}{'D' if x['doc'] else '-'} {x['top']}")


def main() -> int:
    p = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    p.add_argument("--config", type=Path, required=True, help="a vyvid configuration declaring a project with symbols for each corpus")
    p.add_argument("--questions", type=Path, default=HERE / "questions.json")
    p.add_argument("--only", nargs="*", help="the corpora to score, all those the questions name by default")
    p.add_argument("--out", type=Path, help="the folder for the stores, the vectors and results.json, a temporary one by default")
    a = p.parse_args()
    config = load(a.config.expanduser())
    out = (a.out.expanduser() if a.out else Path(tempfile.mkdtemp(prefix="vyvid-symbols-"))).resolve()
    out.mkdir(parents=True, exist_ok=True)
    corpora = {n: qs for n, qs in json.loads(a.questions.read_text(encoding="utf-8"))["corpora"].items() if not a.only or n in a.only}
    if missing := [n for n in corpora if n not in config.projects or not config.projects[n].symbols]:
        p.error(f"the configuration needs a project with symbols for {', '.join(missing)}")
    model = embed.Model(config.embedding)
    done = {name: corpus(name, config.projects[name], questions, config.embedding, model, out) for name, questions in corpora.items()}
    report(done)
    report_docs(done)
    (out / "results.json").write_text(json.dumps(done, indent=1), encoding="utf-8")
    print(f"\nwritten to {out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
