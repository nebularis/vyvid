# SPDX-License-Identifier: MIT
"""Questions generated from Python's ``ast`` for a project's symbols, and how ``vyd find --kind symbol`` answers them.

    mise run bench:mechanical -- --config <configuration> [--out <folder>] [--seed N] [--count N] [--only <project> ...]

Each project of the configuration that declares Python symbols is a corpus. Its symbols are parsed into a store under ``--out``, embedded from
nothing, and every question is asked through ``find.ranked``, the function ``vyd find --kind symbol`` calls, so the figures are those of the
default way. The questions come from the same tracked files the store parsed, with a fixed ``--seed``, and only from symbols that have a docstring.

``name``
    the symbol's exact name, the symbol expected first
``meaning``
    the first sentence of its docstring with the words of its name removed (each with its plural, past or ``-ing`` form), expected in the top
    five. A mechanical stand-in for a question that does not share its name. A sentence left with under three words is not used
``module``
    the first sentence of a module docstring, answered when any symbol or chunk of documentation of that file is in the top five

Each is scored by ``hit@1``, ``hit@5`` and ``MRR``, the mean reciprocal rank of the expected result in the top five that ``find`` shows. A name that
several symbols share has no one symbol to find, so ``name`` also reports the share of questions whose first result bears the name. The symbols that lose are
counted by kind, by test file, by a name shared with others and by a first sentence shared with others. Then the questions drawn from symbols outside test files alone
are asked of the full index and of an index that leaves test files out, to see what the test files cost, and how many places of the top five they take.
"""

from __future__ import annotations

import argparse
import ast
import dataclasses
import json
import random
import re
import statistics
import sys
import tempfile
import time
import warnings
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

from vyvid import embed
from vyvid.config import SymbolSpec, load
from vyvid.symbols import find, store

SEED, COUNT, TOP = 20261104, 300, 5
MIN_WORDS = 3
MODES = ("name", "meaning", "module")
SENTENCE_END = re.compile(r"(?<=[.!?])\s+(?=[A-Z`\"'(])")


def is_test(file: str) -> bool:
    """Whether a path is a test file: under a ``test`` or ``tests`` folder, or named ``test_*``, ``*_test.py`` or ``conftest.py``."""
    parts = file.split("/")
    return any(p in ("test", "tests") for p in parts[:-1]) or parts[-1].startswith("test_") or parts[-1].endswith("_test.py") or parts[-1] == "conftest.py"


def first_sentence(doc: str) -> str:
    """The first sentence of a docstring's first paragraph, on one line and without backticks or a closing full stop."""
    paragraph = re.sub(r"\s+", " ", doc.strip().split("\n\n")[0].replace("`", "")).strip()
    return SENTENCE_END.split(paragraph)[0].rstrip(" .")


def name_words(name: str) -> list[str]:
    """The words of a name (``read_symbol`` and ``readSymbol`` are ``read`` and ``symbol``) and the whole name, longest first."""
    words = {w for w in store.split_words(name).split() if w} | {name.strip("_")}
    return sorted((w for w in words if w), key=lambda w: (-len(w), w))


def without_name(sentence: str, name: str) -> str:
    """The sentence with every word of the name removed, a word being taken with a plural, past or ``-ing`` ending."""
    for word in name_words(name):
        stems = [re.escape(word) + r"(?:s|es|ed|d|ing)?"] + ([re.escape(word[:-1]) + r"(?:ies|ied)"] if word.endswith("y") else [])
        sentence = re.sub(rf"(?<![A-Za-z0-9_])(?:{'|'.join(stems)})(?![A-Za-z0-9_])", " ", sentence, flags=re.I)
    return re.sub(r"\s+", " ", sentence).strip(" ,;:-")


def words_in(text: str) -> int:
    return len(re.findall(r"[A-Za-z]{2,}", text))


def parsed(code: Path, files: list[str]) -> tuple[list[dict], list[dict]]:
    """The documented classes, functions and methods of the files, and their documented modules, from ``ast``, each with its file and line."""
    symbols, modules = [], []
    for file in files:
        tree = ast.parse((code / file).read_bytes(), filename=file)
        if doc := ast.get_docstring(tree):
            modules.append({"file": file, "doc": doc})

        def walk(node: ast.AST) -> None:
            for child in ast.iter_child_nodes(node):
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    if doc := ast.get_docstring(child):
                        symbols.append({"file": file, "line": child.lineno, "name": child.name, "doc": doc})
                walk(child)

        walk(tree)
    return symbols, modules


def questions(symbols: list[dict], modules: list[dict], rows: list[dict], seed: int, count: int, only: str = "all") -> dict[str, list[dict]]:
    """The questions of each mode for the documented symbols and modules that the store holds, drawn with ``seed``, at most ``count`` of each mode.
    ``only`` is ``all`` or ``code``, which leaves test files out. Each question names the ``rowid`` of its symbol, or the ``file`` of its module."""
    by_place = {(r["file"], r["line"], r["name"]): r for r in rows if r["kind"] != "doc"}
    pool = sorted((s for s in symbols if (s["file"], s["line"], s["name"]) in by_place and (only == "all" or not is_test(s["file"]))), key=lambda s: (s["file"], s["line"], s["name"]))
    made: dict[str, list[dict]] = {"name": [], "meaning": [], "module": []}
    for mode, offset in (("name", 0), ("meaning", 1)):
        usable = pool if mode == "name" else [s for s in pool if words_in(without_name(first_sentence(s["doc"]), s["name"])) >= MIN_WORDS]
        for s in random.Random(seed + offset).sample(usable, min(count, len(usable))):
            row = by_place[(s["file"], s["line"], s["name"])]
            made[mode].append({"q": s["name"] if mode == "name" else without_name(first_sentence(s["doc"]), s["name"]), "rowid": row["rowid"], "name": s["name"],
                               "file": s["file"], "kind": row["kind"], "first": first_sentence(s["doc"])})
    files = {r["file"] for r in rows}
    mods = sorted((m for m in modules if m["file"] in files and (only == "all" or not is_test(m["file"])) and words_in(first_sentence(m["doc"])) >= MIN_WORDS + 1), key=lambda m: m["file"])
    for m in random.Random(seed + 2).sample(mods, min(count, len(mods))):
        made["module"].append({"q": first_sentence(m["doc"]), "file": m["file"], "name": m["file"], "kind": "module", "first": first_sentence(m["doc"])})
    return made


def answered(mode: str, q: dict, shown: list[dict]) -> int | None:
    """The place, from 1, of the expected result among the rows shown, or None."""
    for place, row in enumerate(shown, 1):
        if mode == "module" and row["file"] == q["file"] or mode != "module" and row["rowid"] == q["rowid"]:
            return place
    return None


def ask(a, db, mode: str, qs: list[dict]) -> list[dict]:
    """Ask every question through ``find.ranked`` and record where the expected result came, the rows shown, and the milliseconds taken."""
    out = []
    for q in qs:
        start = time.perf_counter()
        shown, _, _ = find.ranked(a, db, q["q"], TOP)
        ms = 1000 * (time.perf_counter() - start)
        place = answered(mode, q, shown)
        out.append({**q, "place": place, "ms": ms, "tests_shown": sum(is_test(r["file"]) for r in shown), "bears_name": bool(shown) and mode == "name" and shown[0]["name"] == q["name"],
                    "top": [f"{r['id']} [{r['kind']}]" for r in shown]})
    return out


def figures(results: list[dict]) -> dict:
    n = len(results)
    if not n:
        return {"n": 0, "hit1": 0.0, "hit5": 0.0, "mrr": 0.0}
    return {"n": n, "hit1": sum(r["place"] == 1 for r in results) / n, "hit5": sum(r["place"] is not None for r in results) / n,
            "mrr": sum(1 / r["place"] for r in results if r["place"]) / n}


def build(project, directory: Path, spec, model) -> dict:
    """Parse and embed a project from nothing, timing each, and say how big it is."""
    start = time.perf_counter()
    counts, problems = store.build(project, directory)
    parse = time.perf_counter() - start
    start = time.perf_counter()
    embedded = store.embed_all(directory, spec, model)
    seconds = time.perf_counter() - start
    return {"files": counts["parsed"], "symbols": counts["symbols"], "chunks": counts["docs"], "failed": counts["failed"], "problems": problems, "parse_seconds": parse, "embed_seconds": seconds,
            "embedded": embedded, "bytes": {name: (directory / name).stat().st_size for name in (store.DB, store.VECTORS, store.DOC_VECTORS)}}


def corpus(name: str, project, config, model, out: Path, seed: int, count: int) -> dict:
    spec = config.embedding
    full = out / name / "full"
    size = build(project, full, spec, model)
    db = store.connect(full / store.DB)
    rows = store.rows(db)
    files, _ = store.listed(project)
    symbols, modules = parsed(project.code, [f for f, _ in files])
    a = SimpleNamespace(project=project, directory=full, config=config, model=model)
    qs = questions(symbols, modules, rows, seed, count)
    names, firsts = Counter(r["name"] for r in rows if r["kind"] != "doc"), Counter(first_sentence(s["doc"]) for s in symbols)
    results = {mode: ask(a, db, mode, qs[mode]) for mode in MODES}
    for mode in ("name", "meaning"):
        for r in results[mode]:
            r.update(test=is_test(r["file"]), shared_name=names[r["name"]] > 1, shared_doc=firsts[r["first"]] > 1, private=r["name"].startswith("_"))
    db.close()
    # The test files' cost: questions from symbols outside test files, asked of the full index and of one without them.
    code_qs = questions(symbols, modules, rows, seed + 10, count, only="code")
    kept = [f for f, _ in files if not is_test(f)]
    bare = dataclasses.replace(project, symbols=[SymbolSpec("python", tuple(project.code / f for f in kept))])
    little = out / name / "no-tests"
    small = build(bare, little, spec, model)
    db, db_little = store.connect(full / store.DB), store.connect(little / store.DB)
    b = SimpleNamespace(project=bare, directory=little, config=config, model=model)
    # The rowids differ between the two stores, so a question is carried over by the place it names.
    little_rows = {(r["file"], r["line"], r["name"]): r["rowid"] for r in store.rows(db_little) if r["kind"] != "doc"}
    full_rows = {r["rowid"]: (r["file"], r["line"], r["name"]) for r in store.rows(db) if r["kind"] != "doc"}
    code_results = {"full": {}, "no-tests": {}}
    for mode in MODES:
        code_results["full"][mode] = ask(a, db, mode, code_qs[mode])
        moved = [{**q, "rowid": little_rows[full_rows[q["rowid"]]]} if mode != "module" else q for q in code_qs[mode]]
        code_results["no-tests"][mode] = ask(b, db_little, mode, moved)
    db.close()
    db_little.close()
    return {"size": size, "no_tests_size": small, "questions": {m: len(qs[m]) for m in MODES}, "results": results, "code_results": code_results,
            "documented": {"symbols": len(symbols), "modules": len(modules)}}


def percent(x: float) -> str:
    return f"{x:.3f}"


def report(done: dict[str, dict]) -> None:
    for name, c in done.items():
        s, t = c["size"], c["no_tests_size"]
        print(f"\n== {name}: {s['files']} files, {s['symbols']} symbols, {s['chunks']} chunks of documentation, {c['documented']['symbols']} documented symbols, {c['documented']['modules']} documented modules,"
              f" {s['failed']} files failed, {len(s['problems'])} problems")
        print(f"   parsed in {s['parse_seconds']:.2f} s, embedded {s['embedded']} texts in {s['embed_seconds']:.1f} s, bytes {s['bytes']}")
        print(f"   without test files: {t['files']} files, {t['symbols']} symbols, {t['chunks']} chunks, embedded in {t['embed_seconds']:.1f} s, bytes {t['bytes']}")
    print(f"\n{'corpus':<9}{'mode':<9}{'n':>5}{'hit@1':>8}{'hit@5':>8}{'MRR':>8}{'ms':>8}{'median':>8}{'p95':>8}")
    for name, c in done.items():
        for mode in MODES:
            r = c["results"][mode]
            f = figures(r)
            ms = sorted(x["ms"] for x in r)
            print(f"{name:<9}{mode:<9}{f['n']:>5}{percent(f['hit1']):>8}{percent(f['hit5']):>8}{percent(f['mrr']):>8}{statistics.fmean(ms):>8.1f}{statistics.median(ms):>8.1f}{ms[int(0.95 * (len(ms) - 1))]:>8.1f}")
    print("\nname: share of questions whose first result bears the name asked")
    for name, c in done.items():
        r = c["results"]["name"]
        print(f"  {name}: {sum(x['bears_name'] for x in r)}/{len(r)}")
    print("\nwhich symbols lose, hit@5 (and hit@1 for name) by kind of symbol, in a test file or not, a name shared with another, a first sentence shared with another, and a private name")
    for name, c in done.items():
        for mode in ("name", "meaning"):
            r = c["results"][mode]
            line = []
            for label, pick in (("class", lambda x: x["kind"] == "class"), ("function", lambda x: x["kind"] == "function"), ("method", lambda x: x["kind"] == "method"),
                                ("test file", lambda x: x["test"]), ("not test", lambda x: not x["test"]), ("shared name", lambda x: x["shared_name"]), ("unique name", lambda x: not x["shared_name"]),
                                ("shared doc", lambda x: x["shared_doc"]), ("unique doc", lambda x: not x["shared_doc"]), ("private", lambda x: x["private"])):
                part = [x for x in r if pick(x)]
                if part:
                    line.append(f"{label} {sum(x['place'] is not None for x in part)}/{len(part)} ({sum(x['place'] == 1 for x in part)} first)")
            print(f"  [{name}] {mode}: " + ", ".join(line))
    print("\nexamples of misses (the first five of each mode)")
    for name, c in done.items():
        for mode in MODES:
            for x in [x for x in c["results"][mode] if x["place"] is None][:5]:
                print(f"  [{name}] {mode}: {x['q'][:90]!r} wanted {x['file']}:{x.get('name', '')} got {x['top'][:3]}")
    print("\nthe test files' cost: questions from symbols outside test files, asked of the full index and of one without test files")
    print(f"{'corpus':<9}{'mode':<9}{'index':<10}{'n':>5}{'hit@1':>8}{'hit@5':>8}{'MRR':>8}{'test places of 5':>18}")
    for name, c in done.items():
        for mode in MODES:
            for index in ("full", "no-tests"):
                r = c["code_results"][index][mode]
                f = figures(r)
                shown = statistics.fmean(x["tests_shown"] for x in r) if r else 0.0
                print(f"{name:<9}{mode:<9}{index:<10}{f['n']:>5}{percent(f['hit1']):>8}{percent(f['hit5']):>8}{percent(f['mrr']):>8}{shown:>18.2f}")


def main() -> int:
    p = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    p.add_argument("--config", type=Path, required=True, help="a vyvid configuration declaring a project with Python symbols for each corpus")
    p.add_argument("--only", nargs="*", help="the projects to score, all those with Python symbols by default")
    p.add_argument("--seed", type=int, default=SEED)
    p.add_argument("--count", type=int, default=COUNT, help="the most questions of each mode")
    p.add_argument("--out", type=Path, help="the folder for the stores, the vectors and results.json, a temporary one by default")
    a = p.parse_args()
    warnings.simplefilter("ignore", SyntaxWarning)  # ast.parse says so of an invalid escape in a corpus
    config = load(a.config.expanduser())
    out = (a.out.expanduser() if a.out else Path(tempfile.mkdtemp(prefix="vyvid-mechanical-"))).resolve()
    out.mkdir(parents=True, exist_ok=True)
    projects = [n for n, pr in config.projects.items() if any(s.language == "python" for s in pr.symbols) and (not a.only or n in a.only)]
    if not projects:
        p.error("the configuration needs a project with Python symbols")
    model = embed.Model(config.embedding)
    done = {name: corpus(name, config.projects[name], config, model, out, a.seed, a.count) for name in projects}
    report(done)
    (out / "mechanical.json").write_text(json.dumps({"seed": a.seed, "count": a.count, "corpora": done}, indent=1), encoding="utf-8")
    print(f"\nwritten to {out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
