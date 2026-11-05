# SPDX-License-Identifier: MIT
"""The extractor plug-in interface.

An extractor reads the files of one kind into quads. A kind is an entry point of the group
``vyvid.extractors``, so only installed code runs and nothing executes a file merely because a cloned
domain contains it. An extractor is a callable ``extract(context, settings) -> Result``. Its
``settings`` are the domain's defaults updated by the project's own, with ``paths`` already expanded
to a list of globs.

A project can also bring its own extractor as a command, in any language, so each git worktree runs
its own version from its own environment and nothing is installed into Вивід. Only a project's entry
in the user's configuration declares one (``command``, with optional ``code``, ``seconds`` and
``env``), and a domain's manifest or entry that does is refused. A ``command`` kind takes precedence
over an installed kind of the same name for that project. Installed kinds keep running in process.

The command runs with the checkout's root as its working folder, under the environment glue is given
(``vyvid.config.GLUE_ENV``) and the variables ``env`` names. It is not sandboxed. Its standard input
is one JSON object::

    {"protocol": 1, "kind": ..., "scope": <name>, "root": <path>, "settings": {...},
     "paths": [<expanded globs>], "output": <folder>, "graphs": {"index": <iri>, "terms": <iri>}}

It writes two files into ``output``, a new temporary folder under the checkout's store folder that
``vyd`` removes afterwards, failure included. ``quads.nq`` holds N-Quads and may be absent. Every
quad must be in the ``index`` or ``terms`` graph, or the whole output is refused. ``result.json``
holds the fields of ``Result``::

    {"protocol": 1, "version": <optional string>, "problems": [...], "findings": [...],
     "texts": {<node iri>: <text>}, "prefixes": {...}, "counts": {...}, "units": {<name>: [<unit>, ...]}, "unit_paths": {<path>: <unit>}}

``units`` names the units of the project, such as its modules or tool packages, and the units each name
stands for, so an ``Owner`` or ``Provided by`` cell that names one is an edge to each, and a name that
names none is reported and kept as written. With no units declared, every such cell stays as written.
``unit_paths`` says which folder each unit sits in, so a term declared under one is owned by that unit, the
longest path winning, and the two meet. A term under no path keeps the folder of its document as its owner.
A ``texts`` key must be a subject of a quad it wrote. Exit zero is success. A non-zero exit, a
timeout (``seconds``, COMMAND_SECONDS if unset), a missing or malformed ``result.json``, an unknown
``protocol``, malformed or misplaced quads, or a command that cannot start is a problem naming the
kind. It costs only that extractor's entries. The ``version`` is reported as a finding. The files
named by ``paths`` and ``code`` decide whether the index is stale, so an edit to the extractor
rebuilds the index of the checkout it is in.
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
PROTOCOL = 1
COMMAND_SECONDS = 300


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
    reported by the build. ``units`` maps a name a register's module column may use to the units it stands for,
    and ``unit_paths`` a repository folder to the unit a term declared under it belongs to."""

    quads: list[ox.Quad] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)
    findings: list[str] = field(default_factory=list)
    texts: dict[str, str] = field(default_factory=dict)
    prefixes: dict[str, str] = field(default_factory=dict)
    counts: dict[str, int] = field(default_factory=dict)
    units: dict[str, list[str]] = field(default_factory=dict)
    unit_paths: dict[str, str] = field(default_factory=dict)

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
