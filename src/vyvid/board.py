# SPDX-License-Identifier: MIT
"""``vyd board``: the slices of a project, read from the registers of its families whose type is ``slice``.

It reads one set of documents, the checkout the folder is in, and never other branches.
"""

from __future__ import annotations

import re
import sys
from dataclasses import replace

from . import registers
from .ask import show
from .config import Config, Scope
from .resolve import layers


def slices(config: Config, project: Scope, state: str | None = None) -> tuple[list[dict], list[str]]:
    """The slices as rows of ``id``, ``deliverable``, ``state`` and ``blocked``, in the order they appear, and the
    problems the reader found. ``state`` keeps those whose state starts with that word."""
    only = replace(project, families={k: f for k, f in project.families.items() if f.type == "slice"})
    found, problems = registers.read_scope(only, registers.types_for(layers(config, project)), {})
    rows = [{"id": r.identifier, "deliverable": r.claim, "state": " ".join(r.values.get("state", [])), "blocked": " ".join(r.values.get("waitsOn", []))} for r in found]
    word = re.compile(rf"{re.escape(state or '')}\b", re.I)
    return [r for r in rows if state is None or word.match(r["state"])], problems


def command(config: Config, project: Scope | None, state: str | None) -> int:
    if project is None:
        print("no project claims this folder, so there is no board")
        return 0
    if not any(f.type == "slice" for f in project.families.values()):
        print(f"project {project.name} declares no family of type slice, so it has no board")
        return 0
    rows, problems = slices(config, project, state)
    for problem in problems:
        print(f"NOTE: {problem}", file=sys.stderr)
    if rows:
        show(rows, ("id", "deliverable", "state", "blocked"))
    else:
        print(f"no slice of project {project.name}" + (f" is in state {state}" if state else ""))
    return 0
