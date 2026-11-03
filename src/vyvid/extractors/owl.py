# SPDX-License-Identifier: MIT
# From LATTICE's tools/knowledge/extract.py, relicensed MIT by its author.
"""The OWL term extractor, kind ``owl-terms``.

Loads each ontology document of the scope into a graph of its own, then derives every declared
class, property, concept and individual from the loaded documents, with its label, kind, owner and a
claim. The load is per document and reports what failed. One fixture holding an IRI with two
fragment separators, which rdflib accepts and Oxigraph refuses, would otherwise lose a whole corpus
to one bad file.

The documents are written to the store in one bulk write after being parsed one at a time. A write
per document left over a thousand files that compaction did not merge, and a read-only open that has
to open them all exceeds macOS's default limit of 256.
"""

from __future__ import annotations

import glob
import re
import subprocess
from pathlib import Path

import pyoxigraph as ox

from ..model import KI, RDF_TYPE, RDFS_LABEL, document_graph, ki, term
from ..registers import shorten
from . import Context, Result

PREFIX_RE = re.compile(r"^\s*@prefix\s+(?P<prefix>[\w-]*):\s*<(?P<iri>[^>]+)>", re.M)
DECLARES_RE = re.compile(
    r"^(?P<term>[a-z][\w.-]*:[A-Za-z][\w-]*)\s+(?:a|rdf:type)\s+"
    r"(?P<kind>owl:Class|owl:ObjectProperty|owl:DatatypeProperty|skos:Concept|skos:ConceptScheme"
    r"|owl:NamedIndividual|[a-z][\w-]*:[A-Z][\w-]*)"
)

# Enough of a term's definition to say what it is, which a 512-token model reads whole.
TERM_LIMIT = 300


def tracked(root: Path) -> set[Path] | None:
    """The files git tracks under ``root``, or None where ``root`` is no git checkout.

    A checkout can hold ignored directories, such as generated output or confidential third-party
    material, so ontology documents are enumerated from git and never from a filesystem walk alone."""
    if not (root / ".git").exists():
        return None
    try:
        listing = subprocess.run(["git", "-C", str(root), "ls-files", "-z"], capture_output=True, text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return None
    return {(root / name).resolve() for name in listing.split("\0") if name}


def ontology_files(checkout: Path | None, paths: list[Path]) -> list[Path]:
    """The ontology documents the globs ``paths`` name, in the order they name them, each pattern's
    files sorted by path and only those git tracks where the scope is a ``checkout``."""
    kept = tracked(checkout) if checkout else None
    found: list[Path] = []
    for place in paths:
        found += [p for p in sorted(Path(n) for n in glob.glob(str(place), recursive=True))
                  if p.is_file() and p not in found and (kept is None or p.resolve() in kept)]
    return found


def source_lines(files: list[Path], root: Path) -> dict[str, list[str]]:
    """Best-effort map from a declared term's local name to the ``path:line`` places that declare it.

    A query over the loaded graphs gives the complete term set and every label, but an RDF graph has
    no line numbers, and a pointer an agent cannot jump to is worth much less. So the authoritative
    facts come from the query and the line number is grafted on from a line-wise pass, which
    misses some declarations and is therefore never the source of the term set itself.
    """
    found: dict[str, list[str]] = {}
    for path in files:
        rel = _rel(path, root)
        for number, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            if (declared := DECLARES_RE.match(line)) is not None:
                found.setdefault(declared.group("term").rsplit(":", 1)[-1], []).append(f"{rel}:{number}")
    return found


def _rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def prefixes(files: list[Path]) -> dict[str, str]:
    """Every prefix the documents declare. The first declaration of a prefix wins."""
    found: dict[str, str] = {}
    for path in files:
        for match in PREFIX_RE.finditer(path.read_text(encoding="utf-8", errors="replace")):
            found.setdefault(match.group("prefix"), match.group("iri"))
    return found


def _term_text(scope_name: str) -> str:
    return f"""
PREFIX owl: <http://www.w3.org/2002/07/owl#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
PREFIX sh: <http://www.w3.org/ns/shacl#>
SELECT ?s (SAMPLE(?l) AS ?label) (SAMPLE(?d) AS ?definition) (SAMPLE(?f) AS ?functional)
       (GROUP_CONCAT(DISTINCT ?dom) AS ?domains) (GROUP_CONCAT(DISTINCT ?ran) AS ?ranges) (MIN(?max) AS ?most)
       (GROUP_CONCAT(DISTINCT ?cls) AS ?classes) WHERE {{
  {{
    GRAPH ?g {{ ?s a ?kind . FILTER (?kind IN (owl:Class, owl:ObjectProperty, owl:DatatypeProperty, skos:Concept, skos:ConceptScheme)) }}
  }} UNION {{
    GRAPH ?g {{ ?s a ?type . FILTER (?type = owl:NamedIndividual || EXISTS {{ GRAPH ?h {{ ?type a owl:Class }} }}) }}
    FILTER (!REGEX(STR(?g), "/(examples|tests?)/"))
    FILTER (?type != owl:NamedIndividual)
    BIND (REPLACE(STR(?type), "^.*[#/]", "") AS ?cls)
  }}
  FILTER (STRSTARTS(STR(?g), "{KI}graph/{scope_name}/") && isIRI(?s))
  OPTIONAL {{ GRAPH ?g1 {{ ?s rdfs:label|skos:prefLabel ?l }} }}
  OPTIONAL {{ GRAPH ?g2 {{ ?s rdfs:comment|skos:definition ?d }} }}
  OPTIONAL {{ GRAPH ?g3 {{ ?s a owl:FunctionalProperty }} BIND ("functional" AS ?f) }}
  OPTIONAL {{ GRAPH ?g4 {{ ?s rdfs:domain ?dm FILTER isIRI(?dm) }} BIND (REPLACE(STR(?dm), "^.*[#/]", "") AS ?dom) }}
  OPTIONAL {{ GRAPH ?g5 {{ ?s rdfs:range ?rn FILTER isIRI(?rn) }} BIND (REPLACE(STR(?rn), "^.*[#/]", "") AS ?ran) }}
  OPTIONAL {{ GRAPH ?g6 {{ ?shape sh:path ?s ; sh:maxCount ?max }} }}
}} GROUP BY ?s"""


def term_texts(store: ox.Store, scope_name: str) -> dict[str, str]:
    """Each declared term's claim, from its own document: its label, its comment or definition cut
    at TERM_LIMIT, and the restrictions stated for it, functional, domain, range and the least
    maximum count a shape gives its path. A term with no comment still has its name and
    restrictions, which is what a question about it names."""
    texts: dict[str, str] = {}
    for row in store.query(_term_text(scope_name)):
        iri = str(row["s"].value)
        name = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", iri.rsplit("#", 1)[-1].rsplit("/", 1)[-1])
        parts = [str(row["label"].value) if row["label"] else name]
        if row["definition"]:
            parts.append(shorten(str(row["definition"].value), TERM_LIMIT))
        facts = [str(row["functional"].value)] if row["functional"] else []
        if row["classes"] and row["classes"].value:
            facts.append("an individual of " + row["classes"].value)
        if row["domains"] and row["domains"].value:
            facts.append("domain " + row["domains"].value)
        if row["ranges"] and row["ranges"].value:
            facts.append("range " + row["ranges"].value)
        if row["most"] is not None:
            facts.append(f"at most {row['most'].value}")
        if facts:
            parts.append(", ".join(facts))
        texts[iri] = ". ".join(p.rstrip(".") for p in parts) + "."
    return texts


def load_ontologies(store: ox.Store, scope_name: str, root: Path, files: list[Path], out: Result) -> None:
    """Every ontology document in a graph of its own, parsed one at a time so one bad file loses only
    itself, then written to the store in a single bulk write."""
    quads: list[ox.Quad] = []
    for path in files:
        rel = _rel(path, root)
        graph = document_graph(scope_name, rel)
        try:
            # Parsed in full before anything is kept, so a document failing part-way contributes nothing.
            # Blank nodes are renamed so each document's stay its own, as a per-document load kept them.
            parsed = [ox.Quad(q.subject, q.predicate, q.object, graph)
                      for q in ox.parse(path=str(path), format=ox.RdfFormat.TURTLE, rename_blank_nodes=True)]
        except (SyntaxError, ValueError) as error:
            out.problems.append(f"{rel}: does not parse, so its axioms are absent ({error.__class__.__name__})")
            out.bump("ontology-document-failed")
            continue
        quads += parsed
        out.bump("ontology-document")
    store.bulk_extend(quads)


TERMS = """
PREFIX owl: <http://www.w3.org/2002/07/owl#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
SELECT ?g ?s ?kind ?label WHERE {
  {
    GRAPH ?g {
      ?s a ?kind .
      FILTER (?kind IN (owl:Class, owl:ObjectProperty, owl:DatatypeProperty, skos:Concept, skos:ConceptScheme))
      OPTIONAL { ?s rdfs:label ?label }
    }
  } UNION {
    # An individual a module declares, such as a value of an enumeration, so a question whether a
    # value or a concept already exists finds it. Example and test data declare nothing.
    GRAPH ?g { ?s a ?type . OPTIONAL { ?s rdfs:label ?label } }
    FILTER (?type = owl:NamedIndividual || EXISTS { GRAPH ?h { ?type a owl:Class } })
    FILTER NOT EXISTS { GRAPH ?any { ?s a ?declared FILTER (?declared IN (owl:Class, owl:ObjectProperty,
                        owl:DatatypeProperty, skos:Concept, skos:ConceptScheme)) } }
    FILTER (!REGEX(STR(?g), "/(examples|tests?)/"))
    BIND (owl:NamedIndividual AS ?kind)
  }
  FILTER (STRSTARTS(STR(?g), "%s"))
}"""


def term_summary(store: ox.Store, context: Context, files: list[Path], out: Result) -> None:
    """Every term the scope's ontology documents declare, with its label, kind and owner.

    Derived by query over the documents already loaded, which is both complete and robust: a
    line-wise read of the Turtle found 2,204 of the terms and only 279 of their labels, and labels
    are what a recall query matches on. The owner is the folder of the document, which comes from the
    graph IRI, so the fact still has exactly one source. Each claim is also the text to embed."""
    scope_name = context.scope.name
    lines = source_lines(files, context.root)
    texts = term_texts(store, scope_name)
    prefix = f"{KI}graph/{scope_name}/"
    graph_of = context.terms_graph
    seen: set[str] = set()
    # In graph and subject order, so a term declared in several documents is owned by the same one on every run.
    for row in sorted(store.query(TERMS % prefix), key=lambda r: (str(r["g"].value), str(r["s"].value))):
        graph, subject, kind, label = row["g"], row["s"], row["kind"], row["label"]
        if not isinstance(subject, ox.NamedNode):
            continue
        rel = str(graph.value).removeprefix(prefix)
        name = str(subject.value)
        node_iri = term(scope_name, name)
        if name not in seen:
            seen.add(name)
            out.quads.append(ox.Quad(node_iri, RDF_TYPE, ki("Term"), graph_of))
            out.quads.append(ox.Quad(node_iri, ki("identifier"), ox.Literal(name), graph_of))
            owner = "/".join(rel.split("/")[:-1])
            if owner:
                out.quads.append(ox.Quad(node_iri, ki("ownedBy"), ox.NamedNode(f"{KI}module/{scope_name}/{owner}"), graph_of))
            out.quads.append(ox.Quad(node_iri, ki("declaredAs"), ox.Literal(str(kind.value).rsplit("#", 1)[-1]), graph_of))
            short = name.rsplit("#", 1)[-1].rsplit("/", 1)[-1]
            # A declaration in the term's own document first, since another document may declare a
            # term of the same local name.
            places = lines.get(short, [])
            pointer = next((v for v in places if v.startswith(rel + ":")), places[0] if places else rel)
            out.quads.append(ox.Quad(node_iri, ki("pointer"), ox.Literal(pointer), graph_of))
            if name in texts:
                out.quads.append(ox.Quad(node_iri, ki("claim"), ox.Literal(texts[name]), graph_of))
                out.texts[node_iri.value] = texts[name]
                out.bump("term-claim")
            out.bump("term")
        if label is not None:
            out.quads.append(ox.Quad(node_iri, RDFS_LABEL, ox.Literal(str(label.value)), graph_of))
            out.bump("term-label")


def extract(context: Context, settings: dict) -> Result:
    """The terms of the ontology documents the ``paths`` setting names."""
    out = Result()
    files = ontology_files(context.scope.code, settings.get("paths", []))
    out.prefixes = prefixes(files)
    load_ontologies(context.store, context.scope.name, context.root, files, out)
    # After the documents are loaded, because the summary is derived by query over them.
    term_summary(context.store, context, files, out)
    return out
