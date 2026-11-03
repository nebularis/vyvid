# SPDX-License-Identifier: MIT
"""Score vyvid's find against LATTICE's own on LATTICE's bake-off questions, with the same model.

    mise run bench:lattice -- --config <configuration> [--lattice <checkout>] [--out <folder>]

Both sides answer every question through their own find, with no kind filter and the question's
facets as given (a value the index does not know is stripped, and a kind in the facets file is
ignored, as the original scoring did). LATTICE runs in its own interpreter, from its checkout, with its
logs redirected into the output folder. Vyvid runs through ``vyvid.ask.find`` over the configuration,
which must declare the checkout as a project with its families and its term extractor, and its index
must be built with embeddings on.

Questions without an ``expect`` list (the negative ones) are not scored. The metric:

``hit@5``
    the share of questions where any ``expect`` id is in the top five
``MRR``
    the mean reciprocal rank of the first ``expect`` or ``accept`` id in the top eight, 0 when none is

The two sets are the 47 questions and the 5 held-out ones. The report prints both side by side and
every question whose top five differ, with both top fives.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
FLAGS = {"activity": "Activity", "quality": "Quality", "tech": "Technology"}
SETS = (("questions", "questions.yaml"), ("held-out", "questions-heldout.yaml"))


# ---- Questions ---------------------------------------------------------------------------------


def parse_questions(text: str, which: str) -> list[dict]:
    """The flat list the question files use: ``- id:``, then ``ask:``, ``kind:``, ``expect: [..]`` and
    ``accept: [..]``. Read here so the benchmark needs no YAML library on either side."""
    out: list[dict] = []
    for line in text.splitlines():
        if line.lstrip().startswith("#") or not line.strip():
            continue
        match = re.match(r"^(?:- |  )(\w+):\s*(.*)$", line)
        if not match:
            continue
        key, value = match.groups()
        if key == "id":
            out.append({"id": value.strip(), "set": which, "text": "", "expect": [], "accept": []})
        elif key == "ask":
            out[-1]["text"] = value.strip()
        elif key in ("expect", "accept"):
            out[-1][key] = [v.strip() for v in value.strip("[] ").split(",") if v.strip()]
    return out


def load_questions() -> list[dict]:
    facets: dict[str, dict] = {}
    for line in (HERE / "question-facets.tsv").read_text(encoding="utf-8").splitlines():
        cells = (line.split("\t") + ["", "", "", ""])[:4]
        facets[cells[0]] = {k: [v.strip() for v in c.split(",") if v.strip()] for k, c in zip(FLAGS, cells[1:])}
    out = []
    for which, name in SETS:
        for q in parse_questions((HERE / name).read_text(encoding="utf-8"), which):
            if q["expect"]:
                out.append({**q, "facets": facets.get(q["id"], {})})
    return out


def table_ids(out: str) -> list[str]:
    """The id column of the table find printed, read by the columns its dashes mark."""
    lines = out.splitlines()
    at = next((i for i, line in enumerate(lines) if line.startswith("---")), None)
    if at is None:
        return []
    spans, column = [], 0
    for dashes in lines[at].split("  "):
        spans.append((column, column + len(dashes)))
        column += len(dashes) + 2
    ids = []
    for line in lines[at + 1 :]:
        if not line.strip():
            break
        if not line.startswith(" "):
            ids.append(line[spans[1][0] : spans[1][1]].strip())
    return ids


def given_of(question: dict, known: dict) -> dict[str, list[str]]:
    return {scheme: [v for v in question["facets"].get(flag, []) if v in known.get(scheme, {})] for flag, scheme in FLAGS.items()}


def key(q: dict) -> str:
    return f"{q['set']}|{q['id']}"


# ---- The two sides -----------------------------------------------------------------------------


def run_lattice(checkout: Path, questions: list[dict], out: Path) -> dict:
    """Runs in LATTICE's interpreter, from its checkout. Its store is opened read-only and its logs
    are redirected, so nothing under the checkout is written."""
    sys.path.insert(0, str(checkout / "tools" / "knowledge"))
    import ask
    import embed
    import pyoxigraph as ox

    ask.ASK_LOG, ask.MISS_LOG = out / "lattice-asks.log", out / "lattice-misses.log"
    shared = embed.Model()
    embed.Model = lambda: shared
    db = ox.Store.read_only(str(ask.STORE_PATH))
    known = ask.facet_values(db)
    results = {}
    for q in questions:
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            ask.find(db, q["text"], set(), set(), set(), 8, ask.expand(db, given_of(q, known)))
        results[key(q)] = table_ids(buffer.getvalue())
    return results


def run_vyvid(checkout: Path, config_path: Path, questions: list[dict], out: Path) -> dict:
    from vyvid import ask, embed
    from vyvid.config import load

    config = load(config_path)
    a = ask.open_stack(config, checkout, model=embed.Model(config.embedding))
    known = ask.facet_values(a)
    results = {}
    for q in questions:
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            ask.find(a, q["text"], set(), set(), set(), 8, ask.expand(a, given_of(q, known)))
        results[key(q)] = table_ids(buffer.getvalue())
    return results


# ---- Scoring -----------------------------------------------------------------------------------


def score(questions: list[dict], results: dict, which: str) -> tuple[float, float, int]:
    chosen = [q for q in questions if q["set"] == which]
    hits, reciprocal = 0, 0.0
    for q in chosen:
        ids = results[key(q)]
        hits += any(i in ids[:5] for i in q["expect"])
        rank = next((n for n, i in enumerate(ids[:8], 1) if i in q["expect"] or i in q["accept"]), None)
        reciprocal += 1 / rank if rank else 0
    return hits / len(chosen), reciprocal / len(chosen), len(chosen)


def report(questions: list[dict], lattice: dict, vyvid: dict) -> None:
    print(f"{'set':<12}{'n':>4}   {'hit@5 L':>8}{'hit@5 V':>9}   {'MRR L':>7}{'MRR V':>7}")
    for which, _ in SETS:
        lh, lm, n = score(questions, lattice, which)
        vh, vm, _ = score(questions, vyvid, which)
        print(f"{which:<12}{n:>4}   {lh:>8.3f}{vh:>9.3f}   {lm:>7.3f}{vm:>7.3f}")
    differ = [q for q in questions if lattice[key(q)][:5] != vyvid[key(q)][:5]]
    print(f"\ntop five differ in {len(differ)} of {len(questions)} questions")
    for q in differ:
        print(f"\n[{q['set']}] {q['id']}  expect {q['expect']}  facets {q['facets']}\n  {q['text'][:110]}")
        print("  L:", lattice[key(q)][:5])
        print("  V:", vyvid[key(q)][:5])


def main() -> int:
    p = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    p.add_argument("--lattice", type=Path, default=Path("~/work/lattice"), help="the LATTICE checkout, with its index built")
    p.add_argument("--config", type=Path, help="a vyvid configuration declaring the checkout as a project")
    p.add_argument("--out", type=Path, default=Path("bench-out"), help="the folder for the JSON results and LATTICE's redirected logs")
    p.add_argument("--side", choices=("lattice",), help=argparse.SUPPRESS)
    p.add_argument("--questions", type=Path, help=argparse.SUPPRESS)
    a = p.parse_args()
    checkout, out = a.lattice.expanduser().resolve(), a.out.expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)

    if a.side == "lattice":
        questions = json.loads(a.questions.read_text(encoding="utf-8"))
        (out / "lattice.json").write_text(json.dumps(run_lattice(checkout, questions, out), indent=1), encoding="utf-8")
        return 0
    if a.config is None:
        p.error("--config is required")

    questions = load_questions()
    (out / "questions.json").write_text(json.dumps(questions, indent=1), encoding="utf-8")
    env = {k: v for k, v in os.environ.items() if k != "VIRTUAL_ENV"}
    subprocess.run(["mise", "exec", "--", "python", str(Path(__file__).resolve()), "--side", "lattice", "--lattice", str(checkout),
                    "--questions", str(out / "questions.json"), "--out", str(out)], cwd=checkout, env=env, check=True)
    lattice = json.loads((out / "lattice.json").read_text(encoding="utf-8"))
    vyvid = run_vyvid(checkout, a.config.expanduser(), questions, out)
    (out / "vyvid.json").write_text(json.dumps(vyvid, indent=1), encoding="utf-8")
    report(questions, lattice, vyvid)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
