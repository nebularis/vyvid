# SPDX-License-Identifier: MIT
"""The ``[project.work]`` table: where a project keeps its status records and plans, and the words it uses.

Every key is optional. A project that declares the table gets the defaults, which suit a project with a
``status`` and a ``plans`` folder under its documents and nothing else. A path takes the scope's usual
tokens (``docs:``, ``code:``), and a repository's own vyvid.toml may name only paths inside the repository.

The state words are a ladder of positions. A word is dated from ``dated_from`` on, counts as done from
``done_from`` on and as closed from ``closed_from`` on, by position, so a project's own ladder keeps the rules.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field, replace
from functools import cached_property
from pathlib import Path
from typing import Callable

import regex

from ..patterns import Pattern

DEFAULT_LADDER = ("planned", "briefed", "building", "built", "verified", "merged", "tagged")
DEFAULT_ASIDE = ("blocked", "dropped")
DEFAULT_SLICE = r"[A-Z]{2,5}-[A-Z]*\d+[a-z]?(?:\.[A-Z]*\d+[a-z]?)*"
DEFAULT_HEADING = "# Slices a plan names"
# The keys that name a place, and the one that names several.
PATH_KEYS = ("status", "plans", "sketches", "validation", "reviews", "decisions", "index", "roadmap", "crosswalk")
LIST_PATH_KEYS = ("sweep",)
KEYS = {*PATH_KEYS, *LIST_PATH_KEYS, "levels", "ladder", "aside", "dated_from", "done_from", "closed_from", "main", "presence",
        "slice_pattern", "markers", "commands", "roadmap_section", "exceptions_heading", "chart_after", "adopt_skip", "rename"}
MARKER_KEYS = ("index_begin", "index_end", "roadmap_begin", "roadmap_end")
COMMAND_KEYS = ("build", "roadmap", "normalise", "rename", "here")
WORD_RE = re.compile(r"^[a-z][a-z-]*$")
UNIT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")  # a record's file stem, so it names no other folder
BRANCH_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]*$")
NUMBER_WORDS = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven", 8: "eight", 9: "nine", 10: "ten"}


@dataclass(frozen=True)
class RenameRule:
    """How one record's historic identifiers read. ``patterns`` match a whole identifier and give its body, and
    ``packs`` match a Validation Pack's file stem and give the body the same way. ``bare`` ids are bare numbers,
    read in the board's id cell only."""

    unit: str
    prefixes: tuple[str, ...]
    patterns: tuple[str, ...] = ()
    packs: tuple[str, ...] = ()
    bare: bool = False
    spelled: str = ""  # the letter a pack's own spelling puts before the body, so H gives FMH-H1.1 for FMH-1.1


@dataclass(frozen=True)
class Work:
    status: Path
    plans: Path
    sketches: Path | None = None
    validation: Path | None = None
    reviews: Path | None = None
    decisions: Path | None = None
    index: Path | None = None
    roadmap: Path | None = None
    crosswalk: Path | None = None
    sweep: tuple[Path, ...] = ()
    levels: tuple[str, ...] = ("unit", "slice")
    ladder: tuple[str, ...] = DEFAULT_LADDER
    aside: tuple[str, ...] = DEFAULT_ASIDE
    dated_from: str = ""
    done_from: str = ""
    closed_from: str = ""
    main: str = "main"
    presence: str = ""  # relative to the checkout, else a folder in its git directory
    slice_pattern: str = DEFAULT_SLICE
    markers: dict[str, str] = field(default_factory=dict)
    commands: dict[str, str] = field(default_factory=dict)
    roadmap_section: str = ""  # the number the roadmap's decisions section has, "9" giving 9.1 and 9.2
    exceptions_heading: str = DEFAULT_HEADING
    chart_after: int = 5  # dated slices a record outside a group needs for a chart of its own
    adopt_skip: str = r"[A-Z]{2,5}-[QD]\d"  # identifiers ``adopt`` leaves alone, which name questions and decisions
    rename: tuple[RenameRule, ...] = ()

    def __post_init__(self) -> None:
        def at(word: str, position: int) -> str:
            return word or self.ladder[min(position, len(self.ladder) - 1)]

        for key, position in (("dated_from", 2), ("done_from", 3), ("closed_from", 5)):
            object.__setattr__(self, key, at(getattr(self, key), position))
        defaults = {"index_begin": "<!-- BEGIN GENERATED work-board. Written by `{build}` from the status records. Edit a status record, never this region. -->",
                    "index_end": "<!-- END GENERATED work-board -->",
                    "roadmap_begin": "<!-- BEGIN GENERATED work-board-{name}. Written by `{roadmap}` from the status records on every branch. Edit a status record, never this region. -->",
                    "roadmap_end": "<!-- END GENERATED work-board-{name} -->"}
        commands = {"build": "vyd work build", "roadmap": "vyd work roadmap", "normalise": "vyd work normalise --apply",
                    "rename": "vyd work rename --apply", "here": "vyd here", **self.commands}
        object.__setattr__(self, "commands", commands)
        object.__setattr__(self, "markers", {k: v.replace("{build}", commands["build"]).replace("{roadmap}", commands["roadmap"])
                                             for k, v in {**defaults, **self.markers}.items()})

    @cached_property
    def states(self) -> tuple[str, ...]:
        return (*self.ladder, *self.aside)

    @cached_property
    def rank(self) -> dict[str, int]:
        """The ladder by position. A held word ranks beside the second word, and a dropped one below every other."""
        out = {state: n for n, state in enumerate(self.ladder)}
        out[self.aside[0]] = min(1, len(self.ladder) - 1)
        if len(self.aside) > 1:
            out[self.aside[1]] = -1
        return out

    @cached_property
    def dated(self) -> frozenset[str]:
        return frozenset(self.ladder[self.ladder.index(self.dated_from):])

    @cached_property
    def done(self) -> tuple[str, ...]:
        return self.ladder[self.ladder.index(self.done_from):]

    @cached_property
    def closed(self) -> tuple[str, ...]:
        """The words of work that is finished: the ladder from ``closed_from``, and the dropped word."""
        return (*self.ladder[self.ladder.index(self.closed_from):], *self.aside[1:])

    @cached_property
    def open(self) -> tuple[str, ...]:
        """The words of work still to do: what is not closed, and the held word."""
        return (*[s for s in self.ladder if s not in self.closed], self.aside[0])

    @cached_property
    def slice_id(self) -> Pattern:
        return Pattern(self.slice_pattern)

    @property
    def unit(self) -> str:
        """The name of the level a status record describes, and ``slice`` the level its board rows are."""
        return self.levels[-2]

    @property
    def piece(self) -> str:
        return self.levels[-1]

    @property
    def group(self) -> str | None:
        """The level above the records that groups them, when the project names one."""
        return self.levels[0] if len(self.levels) > 2 else None

    def moved(self, move: Callable[[Path | None], Path | None]) -> "Work":
        """The settings with every path moved, for a project answered from another checkout."""
        changes = {k: move(getattr(self, k)) for k in PATH_KEYS if getattr(self, k) is not None}
        return replace(self, **changes, sweep=tuple(move(p) for p in self.sweep))

    def paths(self) -> list[tuple[str, Path]]:
        return [(k, getattr(self, k)) for k in PATH_KEYS if getattr(self, k) is not None] + [("sweep", p) for p in self.sweep]


def _words(raw, key: str, where: str, problems: list[str], low: int = 1, high: int = 99) -> tuple[str, ...] | None:
    if not isinstance(raw, list) or not all(isinstance(w, str) and WORD_RE.match(w) for w in raw) or not low <= len(raw) <= high or len(set(raw)) != len(raw):
        problems.append(f"{where}: work.{key} must be {low} to {high} distinct lower-case words" if high < 99 else
                        f"{where}: work.{key} must be a list of at least {low} distinct lower-case words")
        return None
    return tuple(raw)


def _text(raw: dict, key: str, allowed: tuple[str, ...], where: str, problems: list[str], needs: tuple[str, ...] = ()) -> dict[str, str]:
    """A table of one-line texts. A key outside ``allowed`` is refused, and a text must hold each of ``needs``."""
    if not isinstance(raw, dict):
        problems.append(f"{where}: work.{key} must be a table")
        return {}
    out = {}
    for name, value in raw.items():
        if name not in allowed:
            problems.append(f"{where}: work.{key} has the unknown key {name}, not one of {', '.join(allowed)}")
        elif not isinstance(value, str) or not value.strip() or "\n" in value or "\r" in value:
            problems.append(f"{where}: work.{key}.{name} must be one line of text")
        elif name in ("roadmap_begin", "roadmap_end") and "{name}" not in value:
            problems.append(f"{where}: work.{key}.{name} must hold {{name}}, which the region's name replaces")
        else:
            out[name] = value
    return out


def _rules(raw, where: str, problems: list[str]) -> tuple[RenameRule, ...]:
    if not isinstance(raw, list) or not all(isinstance(r, dict) for r in raw):
        problems.append(f"{where}: work.rename must be an array of tables")
        return ()
    out = []
    for item in raw:
        unit, prefixes = item.get("unit"), item.get("prefixes")
        lists = {k: item.get(k, []) for k in ("patterns", "packs")}
        if unknown := sorted(set(item) - {"unit", "prefixes", "patterns", "packs", "bare", "spelled"}):
            problems.append(f"{where}: work.rename has unknown keys {', '.join(unknown)}")
        elif not isinstance(unit, str) or not UNIT_RE.match(unit) or not isinstance(prefixes, list) or not prefixes or not all(isinstance(p, str) and p for p in prefixes):
            problems.append(f"{where}: work.rename needs a unit, a file stem, and prefixes, a non-empty list of strings")
        elif not all(isinstance(v, list) and all(isinstance(s, str) for s in v) for v in lists.values()) or not isinstance(item.get("bare", False), bool) or not isinstance(item.get("spelled", ""), str):
            problems.append(f"{where}: work.rename of {unit} takes patterns and packs as lists of strings and bare as true or false")
        else:
            try:
                for source in (*lists["patterns"], *lists["packs"]):
                    regex.compile(source)
            except regex.error as error:
                problems.append(f"{where}: work.rename of {unit} has a pattern that does not compile: {error}")
                continue
            out.append(RenameRule(unit, tuple(prefixes), tuple(lists["patterns"]), tuple(lists["packs"]), item.get("bare", False), item.get("spelled", "")))
    return tuple(out)


def parse(raw, expand: Callable[[str], Path | None], where: str, problems: list[str]) -> Work | None:
    """The ``work`` table of a project, or None where it declares none. Each problem is reported and the key left at its default."""
    if raw is None:
        return None
    if not isinstance(raw, dict):
        problems.append(f"{where}: work must be a table")
        return None
    if unknown := sorted(set(raw) - KEYS):
        problems.append(f"{where}: work has unknown keys {', '.join(unknown)}")
    found: dict = {}
    for key in PATH_KEYS:
        value = raw.get(key, {"status": "docs:status", "plans": "docs:plans"}.get(key))
        if value is None:
            continue
        if not isinstance(value, str):
            problems.append(f"{where}: work.{key} must be a path")
        elif (path := expand(value)) is not None:
            found[key] = path
    sweep = raw.get("sweep", [])
    if not isinstance(sweep, list) or not all(isinstance(s, str) for s in sweep):
        problems.append(f"{where}: work.sweep must be a list of paths")
    else:
        found["sweep"] = tuple(p for s in sweep if (p := expand(s)) is not None)
    if "levels" in raw and (levels := _words(raw["levels"], "levels", where, problems, low=2)):
        found["levels"] = levels
    ladder = DEFAULT_LADDER
    if "ladder" in raw and (words := _words(raw["ladder"], "ladder", where, problems, low=2)):
        ladder = found["ladder"] = words
    aside = DEFAULT_ASIDE
    if "aside" in raw and (words := _words(raw["aside"], "aside", where, problems, low=1, high=2)):
        aside = found["aside"] = words
    if overlap := sorted(set(ladder) & set(aside)):
        problems.append(f"{where}: work.ladder and work.aside share {', '.join(overlap)}")
        found["ladder"], found["aside"], ladder, aside = DEFAULT_LADDER, DEFAULT_ASIDE, DEFAULT_LADDER, DEFAULT_ASIDE
    for key in ("dated_from", "done_from", "closed_from"):
        if key in raw:
            if raw[key] in ladder:
                found[key] = raw[key]
            else:
                problems.append(f"{where}: work.{key} must be a word of the ladder, not {raw[key]!r}")
    if "main" in raw:
        if isinstance(raw["main"], str) and BRANCH_RE.match(raw["main"]):
            found["main"] = raw["main"]
        else:
            problems.append(f"{where}: work.main must be a branch name")
    if "presence" in raw:
        value = raw["presence"]
        if isinstance(value, str) and value and not os.path.isabs(value) and not value.startswith(("/", "\\")) \
                and ".." not in Path(value.replace("\\", "/")).parts \
                and ".git" not in Path(value.replace("\\", "/")).parts and not re.match(r"[A-Za-z][\w-]*:|~", value):
            found["presence"] = value
        else:
            problems.append(f"{where}: work.presence must be a relative folder inside the checkout, outside .git")
    if "slice_pattern" in raw:
        try:
            if not isinstance(raw["slice_pattern"], str):
                raise TypeError("not a string")
            regex.compile(raw["slice_pattern"])
            found["slice_pattern"] = raw["slice_pattern"]
        except (regex.error, TypeError) as error:
            problems.append(f"{where}: work.slice_pattern does not compile: {error}")
    if "markers" in raw:
        found["markers"] = _text(raw["markers"], "markers", MARKER_KEYS, where, problems)
    if "commands" in raw:
        found["commands"] = _text(raw["commands"], "commands", COMMAND_KEYS, where, problems)
    for key in ("roadmap_section", "exceptions_heading"):
        if key in raw:
            if isinstance(raw[key], str) and "\n" not in raw[key]:
                found[key] = raw[key]
            else:
                problems.append(f"{where}: work.{key} must be one line of text")
    if "chart_after" in raw:
        if isinstance(raw["chart_after"], int) and not isinstance(raw["chart_after"], bool) and raw["chart_after"] > 0:
            found["chart_after"] = raw["chart_after"]
        else:
            problems.append(f"{where}: work.chart_after must be a whole number above zero")
    if "adopt_skip" in raw:
        try:
            regex.compile(raw["adopt_skip"])
            found["adopt_skip"] = raw["adopt_skip"]
        except (regex.error, TypeError) as error:
            problems.append(f"{where}: work.adopt_skip does not compile: {error}")
    if "rename" in raw:
        found["rename"] = _rules(raw["rename"], where, problems)
    if "status" not in found or "plans" not in found:
        return None
    return Work(**found)
