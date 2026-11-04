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
    JSON on its standard output, within ``seconds`` (GLUE_SECONDS if the step sets none). Only a
    project's recipe may have one, and it runs in the project's code folder, with the environment
    variables of GLUE_ENV and those the step names in ``env``, and no others

Every step adds the entries it reaches after those already there, once each. The briefing prints the
entries compactly and drops the last ones when it is over the budget, estimated at four characters a
token.

A run can stop at a glue step instead of running it (``stop``, or ``[framework] glue = "stop"``, which
nothing overrides). ``vyd`` then writes the entries so far and a state file, prints the command for the
client to run through its own shell, and ``resume`` continues from the output the client wrote.
"""

from __future__ import annotations

import json
import shlex
import subprocess
import tempfile
from collections import Counter
from pathlib import Path

import pyoxigraph as ox

from . import ask, embed
from . import config as cfg
from .config import GLUE_ENV, Recipe, Scope, glue_env, run_limited  # noqa: F401  GLUE_ENV stays importable from here
from .build import store_dir
from .credentials import private_dir, redact
from .model import node_of
from .resolve import Unresolved, resolve

GLUE_SECONDS = 30
GLUE_STDERR = 2000
CHARACTERS_PER_TOKEN = 4
STOPPED = 3  # the exit code of a run that stopped at a glue step


class RecipeError(Exception):
    """A recipe cannot be run, with the reason."""


class GlueStop(Exception):
    """A run reached the glue step at ``index`` and may not run it. ``result`` is the entries so far."""

    def __init__(self, index: int, result: list[dict]):
        super().__init__(f"stopped at step {index + 1}")
        self.index, self.result = index, result


def available(stack: list[Scope]) -> dict[str, Recipe]:
    """The recipes of a stack by name. A narrower scope's recipe replaces a wider one's of the same name."""
    return {r.name: r for scope in stack for r in scope.recipes}


def extra_scopes(recipe: Recipe) -> str:
    """The scopes the recipe's find steps name, as ``--scope`` takes them, so the index is built for them."""
    names = {n.strip() for s in recipe.steps for n in s.get("scope", "").removeprefix("only:").split(",") if n.strip()}
    return ",".join(sorted(names))


def run(a: ask.Asker, recipe: Recipe, question: str, result: list[dict] | None = None, start: int = 0,
        stop: bool = False) -> list[dict]:
    """The entries the recipe's steps reach for the question, from step ``start`` with ``result`` so far.

    Raises RecipeError, and GlueStop at a glue step when ``stop`` is set or the configuration says
    ``glue = "stop"``, in which case no glue is run."""
    stop = stop or a.config.glue == "stop"
    declaring = a.config.scope(recipe.scope)
    result = list(result or [])
    pool: dict[str, dict] = {}
    a.choose("")
    for index in range(start, len(recipe.steps)):
        step = recipe.steps[index]
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
            _check_glue(declaring)
            if stop:
                raise GlueStop(index, result)
            if not cfg.trusted(a.config):
                raise RecipeError("this configuration is not trusted, so vyd runs no glue from it. Run vyd trust in a terminal to trust it, or stop at glue and run the command yourself")
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
    r["data"] = ask.data_note(a, r["scope"], r["claim"])
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


def _check_glue(declaring: Scope) -> None:
    if declaring.kind != "project" or declaring.code is None:
        raise RecipeError("a glue step runs only in a project's recipe")


def _entries(text: str, what: str) -> list[dict]:
    """The entries a glue command printed, each filled in. Raises RecipeError for text that is not a list of them."""
    try:
        replaced = json.loads(redact(text))
    except json.JSONDecodeError as error:
        raise RecipeError(f"{what} did not print JSON. {error}") from error
    if not isinstance(replaced, list) or not all(isinstance(e, dict) and isinstance(e.get("id"), str) for e in replaced):
        raise RecipeError(f"{what} must print a list of entries, each with an id")
    return [{"node": "", "kind": "", "scope": "", "claim": "", "pointer": "", "signposts": [], **e} for e in replaced]


def _glue(result: list[dict], step: dict, declaring: Scope) -> list[dict]:
    """Run the command in the project's code folder, as an argument list and never a shell string."""
    _check_glue(declaring)
    command, seconds = step["command"], step.get("seconds", GLUE_SECONDS)
    shown = " ".join(command)
    try:
        done = run_limited(command, json.dumps(result), declaring.code, glue_env(step), seconds)
    except subprocess.TimeoutExpired as error:
        raise RecipeError(f"glue {shown} did not finish within {seconds} seconds") from error
    except OSError as error:
        raise RecipeError(f"glue {shown} cannot run. {error}") from error
    if done.returncode:
        raise RecipeError(f"glue {shown} exited {done.returncode}. {redact(done.stderr.strip())[:GLUE_STDERR]}")
    return _entries(done.stdout, f"glue {shown}")


def stop_at(a: ask.Asker, recipe: Recipe, question: str, folder: Path, stopped: GlueStop) -> str:
    """Write the entries so far and the state of the run under the store base, and say what to run and how to resume."""
    step, base = recipe.steps[stopped.index], store_dir(a.config) / "glue"
    private_dir(base)
    where = Path(tempfile.mkdtemp(prefix=f"{recipe.name}-", dir=base))
    given, output, state = where / "input.json", where / "output.json", where / "state.json"
    given.write_text(json.dumps(stopped.result, ensure_ascii=False), encoding="utf-8", newline="\n")
    state.write_text(json.dumps({"recipe": recipe.name, "question": question, "next": stopped.index + 1, "budget": recipe.budget,
                                 "folder": str(folder.resolve())}, indent=2) + "\n", encoding="utf-8", newline="\n")
    resume = shlex.join(["vyd", "recipe", "run", "--resume", str(state), "--glue-output", str(output)])
    untrusted = [] if cfg.trusted(a.config) else ["This configuration is not trusted, so vyd would not run this glue itself. Your client approves the command."]
    return "\n".join([
        f"Recipe {recipe.name} stopped at step {stopped.index + 1} of {len(recipe.steps)}, a glue step. vyd runs no glue in this form.",
        f"command: {shlex.join(step['command'])}",
        f"folder: {a.config.scope(recipe.scope).code}",
        f"input: {given}   (pass it on the command's standard input)",
        f"output: {output}   (write the command's standard output here, a JSON list of entries each with an id)",
        f"seconds: {step.get('seconds', GLUE_SECONDS)}",
        "The command sees your own environment, not the minimal one vyd gives glue it runs itself.", *untrusted,
        f"Then resume: {resume}"])


def read_state(path: Path) -> dict:
    """The state of a stopped run. Raises RecipeError for a file that is missing or is not one."""
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RecipeError(f"{path} is not the state of a stopped run. {error}") from error
    kinds = {"recipe": str, "question": str, "next": int, "budget": int, "folder": str}
    if not isinstance(state, dict) or not all(isinstance(state.get(k), t) and not isinstance(state.get(k), bool) for k, t in kinds.items()):
        raise RecipeError(f"{path} is not the state of a stopped run, which holds {', '.join(kinds)}")
    return state


def resumed_step(state: dict, recipe: Recipe | None) -> dict:
    """The glue step a state stopped at. Raises RecipeError if its recipe is gone or that step is not glue."""
    if recipe is None:
        raise RecipeError(f"the recipe {state['recipe']} of this state no longer exists")
    if not 1 <= state["next"] <= len(recipe.steps) or recipe.steps[state["next"] - 1]["step"] != "glue":
        raise RecipeError(f"step {state['next']} of recipe {recipe.name} is not a glue step, so the recipe changed since it stopped")
    return recipe.steps[state["next"] - 1]


def glue_output(path: Path, step: dict) -> list[dict]:
    """The entries the client's glue command wrote to ``path``, checked as ``_glue`` checks its own."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as error:
        raise RecipeError(f"the glue output cannot be read. {error}") from error
    return _entries(text, f"glue {shlex.join(step['command'])} (output {path})")


def finish(state_file: Path) -> None:
    """Remove a state file and the input beside it, and their folder when nothing else is in it."""
    for name in (state_file, state_file.with_name("input.json")):
        name.unlink(missing_ok=True)
    try:
        state_file.parent.rmdir()
    except OSError:
        pass


def dry_run(recipe: Recipe, declaring: Scope) -> str:
    """Each step of the recipe, a glue step's command as an argument list with the folder it would run in
    and its time limit. Nothing is run, and the text says so."""
    lines = [f"Recipe {recipe.name}, dry run"]
    for n, step in enumerate(recipe.steps, 1):
        if step["step"] == "glue":
            lines.append(f"{n}. glue {json.dumps(step['command'], ensure_ascii=False)} in {declaring.code}, within {step.get('seconds', GLUE_SECONDS)} seconds")
        else:
            lines.append(f"{n}. {step['step']} " + ", ".join(f"{k}={v}" for k, v in step.items() if k != "step"))
    return "\n".join([*lines, "", "Nothing was run."])


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
