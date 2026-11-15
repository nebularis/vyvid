# SPDX-License-Identifier: MIT
"""``vyd check registers``: a claim over the limit or a pointer at a whole long file fails for a row the baseline does not list.

The build only notes these two defects, and a row that breaks one is found after a branch is in flight. This check makes
them bite when the row is added. A baseline, named by ``limits.baseline`` in a ``register-types.toml``, lists the rows already
over a limit, as ``ID claim`` or ``ID pointer`` with a reason after a ``#``. A baseline line that no longer matches a defect
fails too, so the baseline only shrinks."""

from __future__ import annotations

import re
import sys
import tempfile
from pathlib import Path

CLAIM_RE = re.compile(r"^(?P<where>\S+): (?P<id>\S+) has a claim of \d+ characters, which is cut at \d+")
WHOLE_RE = re.compile(r"^(?P<where>\S+): (?P<id>\S+) has a pointer at the whole of ")
KINDS = {"claim", "pointer"}


def defects(problems: list[str]) -> dict[tuple[str, str], str]:
    """The ``(identifier, kind)`` of each row with a claim over the limit or a pointer at a whole file, with where it is written."""
    found: dict[tuple[str, str], str] = {}
    for line in problems:
        for kind, pattern in (("claim", CLAIM_RE), ("pointer", WHOLE_RE)):
            if match := pattern.match(line):
                found.setdefault((match["id"], kind), match["where"])
    return found


def baseline(text: str) -> set[tuple[str, str]]:
    out = set()
    for line in text.splitlines():
        words = line.split("#", 1)[0].split()
        if len(words) == 2 and words[1] in KINDS:
            out.add((words[0], words[1]))
    return out


def compare(found: dict[tuple[str, str], str], listed: set[tuple[str, str]]) -> tuple[list[tuple[str, str, str]], list[tuple[str, str]]]:
    """The defects the baseline does not list, and the baseline lines that match no defect."""
    new = [(i, k, where) for (i, k), where in sorted(found.items()) if (i, k) not in listed]
    stale = sorted(listed - set(found))
    return new, stale


# @vyd: CAP-43
def check(config, project, folder: Path) -> int:
    from . import registers
    from .build import build
    from .resolve import layers

    if project is None:
        print("no project claims this folder, so there are no registers to check")
        return 0
    types = registers.types_for(layers(config, project))
    with tempfile.TemporaryDirectory() as scratch:
        out = build(config, project, store_path=Path(scratch) / "store", embed=False)
    listed: set[tuple[str, str]] = set()
    for path in types.baselines:
        try:
            listed |= baseline(path.read_text(encoding="utf-8"))
        except OSError as error:
            print(f"vyd: cannot read the baseline {path}: {error}", file=sys.stderr)
            return 2
    # A domain's rows are the domain's to fix, so only a file of this project's own counts.
    root = project.code or project.path or folder
    found = {key: where for key, where in defects(out.problems).items() if (root / where.rsplit(":", 1)[0]).is_file()}
    new, stale = compare(found, listed)
    for identifier, kind, where in new:
        print(f"ERROR: {where}: {identifier} has a {kind} over its limit and the baseline does not list it")
    for identifier, kind in stale:
        print(f"ERROR: the baseline lists {identifier} {kind}, which is no longer a defect. Remove the line")
    print(f"register check {'failed' if new or stale else 'passed'}: {len(found)} defects, {len(listed)} in the baseline, {len(new)} new, {len(stale)} stale")
    return int(bool(new or stale))
