# SPDX-License-Identifier: MIT
"""The extractor plug-in interface.

An extractor reads the files of one kind into quads. A kind is an entry point of the group
``vyvid.extractors``, so only installed code runs and nothing executes a file merely because a cloned
domain contains it. An extractor is a callable ``extract(context, settings) -> Result``. Its
``settings`` are the domain's defaults updated by the project's own, with ``paths`` already expanded
to a list of globs.
"""

from __future__ import annotations

import importlib.metadata
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Callable

import pyoxigraph as ox

from ..model import index_graph, terms_graph

if TYPE_CHECKING:
    from ..config import Config, Scope

GROUP = "vyvid.extractors"


@dataclass
class Context:
    """What an extractor reads from: the scope its output belongs to, that scope's root, the
    configuration, the merged taggable facet values, and the store, which holds the documents an
    extractor loads into it and queries."""

    scope: Scope
    root: Path
    config: Config
    facets: dict[str, set[str]]
    store: ox.Store

    @property
    def terms_graph(self) -> ox.NamedNode:
        return terms_graph(self.scope.name)

    @property
    def index_graph(self) -> ox.NamedNode:
        return index_graph(self.scope.name)


@dataclass
class Result:
    """What an extractor found. ``texts`` maps a node's IRI to the text to embed, ``prefixes`` maps a
    CURIE prefix to its namespace so a ``targets`` cell may name a term by it, and ``counts`` are
    reported by the build."""

    quads: list[ox.Quad] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)
    findings: list[str] = field(default_factory=list)
    texts: dict[str, str] = field(default_factory=dict)
    prefixes: dict[str, str] = field(default_factory=dict)
    counts: dict[str, int] = field(default_factory=dict)

    def bump(self, key: str, by: int = 1) -> None:
        self.counts[key] = self.counts.get(key, 0) + by


def _entry_points():
    return importlib.metadata.entry_points(group=GROUP)


def kinds() -> list[str]:
    """The extractor kinds installed, sorted."""
    return sorted({e.name for e in _entry_points()})


def load(kind: str) -> Callable[[Context, dict], Result]:
    """The ``extract`` callable of an installed kind."""
    for entry in _entry_points():
        if entry.name == kind:
            return entry.load()
    raise KeyError(kind)
