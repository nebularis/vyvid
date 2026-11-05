# SPDX-License-Identifier: MIT
"""A project's extractor run as a command in its own checkout. The contract is in ``vyvid.extractors``.

The command's output becomes a ``Result``, so the build treats it as it does an installed kind's.
"""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

import pyoxigraph as ox

from ..config import COMMAND_KEYS, Run, glue_env, run_limited
from ..credentials import redact
from . import COMMAND_SECONDS, PROTOCOL, Context, Result

STDERR = 2000  # the most of a command's standard error a problem keeps
# The fields of result.json: a list of strings, or a mapping of one type to another.
SHAPES = {"problems": [str], "findings": [str], "texts": {str: str}, "prefixes": {str: str}, "counts": {str: int}, "units": {str: [str]}, "unit_paths": {str: str}}


class Failed(Exception):
    """The command's output cannot be used, with the reason."""


def extract(run: Run, context: Context, folder: Path) -> Result:
    """Run the command, its output folder a new one under ``folder`` that is removed afterwards.
    A failure is a problem and a result with nothing else in it."""
    folder.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=folder, prefix="extract-") as output:
        try:
            return _collect(run, context, Path(output))
        except Failed as error:
            return Result(problems=[f"extractor '{run.kind}' {error}, so its entries are absent"])


def _collect(run: Run, context: Context, output: Path) -> Result:
    settings = run.settings
    seconds = settings.get("seconds", COMMAND_SECONDS)
    allowed = (context.index_graph, context.terms_graph)
    request = {"protocol": PROTOCOL, "kind": run.kind, "scope": context.scope.name, "root": str(context.root),
               "settings": {k: v for k, v in settings.items() if k not in ("paths", *COMMAND_KEYS)},
               "paths": [str(p) for p in settings["paths"]], "output": str(output),
               "graphs": {"index": allowed[0].value, "terms": allowed[1].value}}
    try:
        done = run_limited(settings["command"], json.dumps(request, default=str), context.root, glue_env(settings), seconds)
    except subprocess.TimeoutExpired as error:
        raise Failed(f"did not finish within {seconds} seconds") from error
    except OSError as error:
        raise Failed(f"cannot run. {error}") from error
    if done.returncode:
        raise Failed(f"exited {done.returncode}. {redact(done.stderr.strip())[:STDERR]}")
    data = _result(output / "result.json")
    quads = _quads(output / "quads.nq", allowed)
    out = Result(quads, **{k: data[k] for k in SHAPES if k != "texts"})
    out.problems, out.findings = [redact(p) for p in out.problems], [redact(f) for f in out.findings]
    subjects = {q.subject.value for q in quads if isinstance(q.subject, ox.NamedNode)}
    out.texts = {k: v for k, v in data["texts"].items() if k in subjects}
    out.problems += [f"extractor '{run.kind}' gave a text for {k}, which it wrote no quad about, so it is not embedded" for k in data["texts"] if k not in subjects]
    if data.get("version"):
        out.findings.append(f"extractor '{run.kind}' ran version {data['version']}")
    return out


def _result(path: Path) -> dict:
    """``result.json`` read and checked, each missing field empty."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise Failed(f"wrote no readable result.json ({error.__class__.__name__})") from error
    if not isinstance(data, dict) or data.get("protocol") != PROTOCOL or isinstance(data.get("protocol"), bool):
        raise Failed(f"wrote a result.json that is not protocol {PROTOCOL}")
    data = {**{k: type(shape)() for k, shape in SHAPES.items()}, **data}
    for key, shape in SHAPES.items():
        if not _typed(data[key], shape):
            raise Failed(f"wrote a result.json whose {key} are malformed")
    if not isinstance(data.get("version", ""), str):
        raise Failed("wrote a result.json whose version is not a string")
    return data


def _typed(value, shape) -> bool:
    if isinstance(shape, list):
        return isinstance(value, list) and all(_typed(v, shape[0]) for v in value)
    if isinstance(shape, dict):
        [(key, item)] = shape.items()
        return isinstance(value, dict) and all(type(k) is key and _typed(v, item) for k, v in value.items())
    return type(value) is shape


def _quads(path: Path, allowed: tuple) -> list[ox.Quad]:
    """The quads of ``quads.nq``, none where it is absent. Parsed in full and checked before any is kept."""
    if not path.exists():
        return []
    try:
        quads = list(ox.parse(path=str(path), format=ox.RdfFormat.N_QUADS))
    except (OSError, SyntaxError, ValueError) as error:
        raise Failed(f"wrote a quads.nq that does not parse ({error.__class__.__name__})") from error
    if outside := sum(q.graph_name not in allowed for q in quads):
        raise Failed(f"wrote {outside} quads outside its own graphs, so all its output is refused")
    return quads
