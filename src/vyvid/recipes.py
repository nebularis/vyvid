# SPDX-License-Identifier: MIT
"""Recipes: a named chain of steps that narrows an answer until it is specific to the work.

A domain declares its recipes in its manifest, as ``[[recipes]]``, and a project in its
configuration, as ``[[projects.recipes]]``. Each has a name, a description saying when to use it, a
list of steps and an optional budget in tokens. The steps build one result, a list of entries:

``find``
    ranks the index as ``vyd find`` does. ``words`` is a template in which ``{question}`` is the
    question the recipe is run with, and the filters of ``vyd find`` are keys of the step
``linked``
    follows the declared ``edges`` from the entries so far, ``out``, ``in`` or ``both`` ways
``include``
    adds named entries, their identifiers resolved in the scope that declares the recipe
``take``
    keeps the first ``n`` entries, or the first ``n`` of each kind with ``per_kind``
``glue``
    runs ``command`` with the result as JSON on its standard input and replaces the result with the
    JSON on its standard output. Only a project's recipe may have one, and it runs in the project's
    code folder

Every step adds the entries it reaches after those already there, once each. The briefing prints the
entries compactly and drops the last ones when it is over the budget, estimated at four characters a
token.
"""

from __future__ import annotations

import json
import subprocess
from collections import Counter

import pyoxigraph as ox

from . import ask, embed
from .config import Recipe, Scope
from .model import node_of
from .resolve import Unresolved, resolve

GLUE_SECONDS = 30
CHARACTERS_PER_TOKEN = 4


class RecipeError(Exception):
    """A recipe cannot be run, with the reason."""


def available(stack: list[Scope]) -> dict[str, Recipe]:
    """The recipes of a stack by name. A narrower scope's recipe replaces a wider one's of the same name."""
    return {r.name: r for scope in stack for r in scope.recipes}


def extra_scopes(recipe: Recipe) -> str:
    """The scopes the recipe's find steps name, as ``--scope`` takes them, so the index is built for them."""
    names = {n.strip() for s in recipe.steps for n in s.get("scope", "").removeprefix("only:").split(",") if n.strip()}
    return ",".join(sorted(names))


def run(a: ask.Asker, recipe: Recipe, question: str) -> list[dict]:
    """The entries the recipe's steps reach for the question. Raises RecipeError."""
    declaring = a.config.scope(recipe.scope)
    result: list[dict] = []
    pool: dict[str, dict] = {}
    a.choose("")
    for step in recipe.steps:
        kind = step["step"]
        if kind == "find":
            new = _find(a, step, question)
        elif kind == "linked":
            pool = pool or _pool(a)
            new = _linked(a, result, step, pool)
        elif kind == "include":
            pool = pool or _pool(a)
            new = [_include(a, declaring, i, pool) for i in step["ids"]]
        elif kind == "take":
            result = _take(result, step["n"], step.get("per_kind", False))
            continue
        else:
            result = _glue(result, step, declaring)
            continue
        for entry in new:
            if _key(entry) not in {_key(e) for e in result}:
                result.append(entry)
    return result


def _key(entry: dict) -> str:
    return entry.get("node") or entry["id"]


def _entry(a: ask.Asker, r: dict) -> dict:
    """A row of the index as an entry: its signposts are the notes find prints under it."""
    r = {k: v for k, v in r.items() if k != "section"}
    r["private"] = ask.private_note(a) if r["scope"] in a.private else ""
    return {"node": r["n"], "id": a.label(r["scope"], r["id"]), "kind": r["kind"], "scope": r["scope"],
            "claim": r["claim"].strip(), "pointer": r.get("pointer") or "", "signposts": ask.notes(r)}


def _find(a: ask.Asker, step: dict, question: str) -> list[dict]:
    words = step["words"].replace("{question}", question)
    try:
        a.choose(step.get("scope", ""))
        kinds, phases, audiences, facets = ask.filters(
            a, step.get("kind", ""), step.get("exclude", ""), step.get("phase", ""), step.get("audience", ""),
            activity=step.get("activity", ""), quality=step.get("quality", ""), tech=step.get("tech", ""))
        rows, best = ask.rank(a, words, kinds, phases, audiences, facets)
        rows = ask.fold(a, rows)[: step.get("limit", 8)]
    except (ValueError, embed.Unavailable) as error:
        raise RecipeError(f"find cannot run for '{words}'. {error}") from error
    finally:
        a.choose("")
    ask.log_ask(a, "find", words, best, [a.label(r["scope"], r["id"]) for r in rows])
    if best < a.config.embedding.weak:
        ask.log_miss(a, f"find {words}")
    return [_entry(a, r) for r in rows]


def _pool(a: ask.Asker) -> dict[str, dict]:
    """Every entry of the stack by node, with what reversed or narrowed its first section."""
    rows = {r["n"]: r for r in ask.candidates(a, set(), set(), set())}
    for s in a.rows(ask.SECTIONS):
        if s["s"].endswith("/section-1") and s["n"] in rows:
            rows[s["n"]]["reversed"], rows[s["n"]]["narrowed"] = s["reversed"], s["narrowed"] or rows[s["n"]].get("narrowed")
    return rows


def _linked(a: ask.Asker, result: list[dict], step: dict, pool: dict[str, dict]) -> list[dict]:
    edges, direction = set(step["edges"]), step.get("direction", "out")
    hidden = ask.overridden(a)
    reached: list[dict] = []
    for entry in result:
        if not entry.get("node"):
            continue
        for r in a.rows(ask.LINKED, subject=ox.NamedNode(entry["node"])):
            if r["edge"] in edges and direction in ("both", r["direction"]) and r["o"] in pool \
                    and (r["o"] not in hidden or pool[r["o"]]["scope"] in a.named):
                reached.append(_entry(a, pool[r["o"]]))
    return reached


def _include(a: ask.Asker, declaring: Scope, identifier: str, pool: dict[str, dict]) -> dict:
    try:
        canonical = resolve(a.config, identifier, declaring)
    except Unresolved as error:
        raise RecipeError(f"include cannot resolve {identifier} in {declaring.name}. {error}") from error
    row = pool.get(node_of(canonical).value)
    if row is None:
        raise RecipeError(f"include names {canonical}, which the index of this stack does not hold")
    return _entry(a, row)


def _take(result: list[dict], n: int, per_kind: bool) -> list[dict]:
    if not per_kind:
        return result[:n]
    seen: Counter = Counter()
    kept = []
    for entry in result:
        seen[entry["kind"]] += 1
        if seen[entry["kind"]] <= n:
            kept.append(entry)
    return kept


def _glue(result: list[dict], step: dict, declaring: Scope) -> list[dict]:
    """Run the command in the project's code folder, as an argument list and never a shell string."""
    if declaring.kind != "project" or declaring.code is None:
        raise RecipeError("a glue step runs only in a project's recipe")
    command = step["command"]
    shown = " ".join(command)
    try:
        done = subprocess.run(command, input=json.dumps(result), capture_output=True, text=True,
                              cwd=declaring.code, timeout=GLUE_SECONDS, check=False)
    except subprocess.TimeoutExpired as error:
        raise RecipeError(f"glue {shown} did not finish within {GLUE_SECONDS} seconds") from error
    except OSError as error:
        raise RecipeError(f"glue {shown} cannot run. {error}") from error
    if done.returncode:
        raise RecipeError(f"glue {shown} exited {done.returncode}. {done.stderr.strip()}")
    try:
        replaced = json.loads(done.stdout)
    except json.JSONDecodeError as error:
        raise RecipeError(f"glue {shown} did not print JSON. {error}") from error
    if not isinstance(replaced, list) or not all(isinstance(e, dict) and isinstance(e.get("id"), str) for e in replaced):
        raise RecipeError(f"glue {shown} must print a list of entries, each with an id")
    return [{"node": "", "kind": "", "scope": "", "claim": "", "pointer": "", "signposts": [], **e} for e in replaced]


def render(recipe: Recipe, question: str, entries: list[dict], dropped: int = 0) -> str:
    """The briefing: a heading, then for each entry its id, kind and pointer, and its claim with its
    signposts on the next line, then a line saying how many were dropped."""
    lines = [f'Recipe {recipe.name}, for "{question}"']
    for e in entries:
        lines.append(f"{e['id']}  {e['kind']}  {e['pointer']}".rstrip())
        lines.append("  " + " ".join([e["claim"], *e["signposts"]]).rstrip())
    if dropped:
        lines.append(f"{dropped} more entries not shown, to stay within {recipe.budget} tokens. Run with --all to see every one.")
    return "\n".join(lines)


def estimate(text: str) -> int:
    """The size in tokens, as characters divided by four, rounded up."""
    return -(-len(text) // CHARACTERS_PER_TOKEN)


def briefing(recipe: Recipe, question: str, entries: list[dict], everything: bool = False) -> tuple[str, int, int]:
    """The briefing text, its estimated size and the number of entries dropped to fit the budget.
    The first entry is always kept, since a briefing with none would say nothing."""
    keep = len(entries)
    while not everything and keep > 1 and estimate(render(recipe, question, entries[:keep], len(entries) - keep)) > recipe.budget:
        keep -= 1
    text = render(recipe, question, entries[:keep], len(entries) - keep)
    return text, estimate(text), len(entries) - keep
