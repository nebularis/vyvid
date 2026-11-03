# SPDX-License-Identifier: MIT
# From LATTICE's tools/knowledge/identifiers.py and extract.py, relicensed MIT by its author.
"""The names things have in the store.

A node is named by its scope and its normalised local identifier, so two scopes may both have an
``STD-1`` without meeting. Each scope's entries and terms sit in graphs of their own, and the
vocabulary and the facets are shared.
"""

from __future__ import annotations

import re

import pyoxigraph as ox

KI = "https://www.nebularis.org/vyvid/knowledge#"
RDF_TYPE = ox.NamedNode("http://www.w3.org/1999/02/22-rdf-syntax-ns#type")
RDFS_LABEL = ox.NamedNode("http://www.w3.org/2000/01/rdf-schema#label")
TBOX_GRAPH = ox.NamedNode(KI + "tbox")
FACETS_GRAPH = ox.NamedNode(KI + "facets")

SEPARATORS = re.compile(r"[-‑ _]+")
NOT_KEPT = re.compile(r"[^A-Z0-9.]+")


def normalise(identifier: str) -> str:
    """The key a mention and a definition are compared on: letters, digits and dots, upper case.

    ``ADR-A-C2``, ``ADR-AC2`` and ``ADR AC2`` all normalise to ``ADRAC2``, so one decision written
    three ways resolves once. ``ADR-A07`` and ``ADR-A07b`` stay distinct.

    **A dot is kept.** Dropping every separator merged ``AIR-6.6`` with ``AIR-66``, which are
    different slices, so only the separators that actually vary are removed: the hyphen, the
    non-breaking hyphen, the space that headings use, and the underscore.
    """
    return NOT_KEPT.sub("", SEPARATORS.sub("", identifier).upper())


def ki(local: str) -> ox.NamedNode:
    return ox.NamedNode(KI + local)


def node(scope_name: str, local: str) -> ox.NamedNode:
    return ox.NamedNode(KI + f"node/{scope_name}/{normalise(local)}")


def node_of(canonical: str) -> ox.NamedNode:
    """The node a canonical ``scope:LOCAL`` names."""
    scope_name, local = canonical.split(":", 1)
    return node(scope_name, local)


def term(scope_name: str, iri: str) -> ox.NamedNode:
    """The node the term summary gives a declared term, named by its IRI's last segment."""
    return ox.NamedNode(KI + f"term/{scope_name}/" + iri.rsplit("/", 1)[-1].replace("#", "."))


def index_graph(scope_name: str) -> ox.NamedNode:
    return ox.NamedNode(KI + f"index/{scope_name}")


def terms_graph(scope_name: str) -> ox.NamedNode:
    return ox.NamedNode(KI + f"terms/{scope_name}")


def document_graph(scope_name: str, rel: str) -> ox.NamedNode:
    """The graph of one ontology document of a scope, which holds its full axioms."""
    return ox.NamedNode(KI + f"graph/{scope_name}/{rel}")


def document(scope_name: str, rel: str) -> ox.NamedNode:
    """The document an entry is defined in."""
    return ox.NamedNode(KI + f"doc/{scope_name}/{rel}")
