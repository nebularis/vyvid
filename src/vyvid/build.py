# SPDX-License-Identifier: MIT
# From LATTICE's tools/knowledge/extract.py, relicensed MIT by its author.
"""Build the knowledge index of a stack of scopes into an Oxigraph store, and embed its text.

The store holds the vocabulary, the merged facets, and for each scope its entries and what its
extractors found, such as declared ontology terms. The vectors sit beside it, and a stamp records
when the build started, taken before anything was read so a file edited while the build runs is
caught the next time.

The store is optimised at the end. A write per ontology document left over a thousand files that
compaction did not merge, and a read-only open that has to open them all exceeds macOS's default
limit of 256.
"""

from __future__ import annotations

import shutil
import time
from importlib import resources
from pathlib import Path

import platformdirs
import pyoxigraph as ox

from . import embed as vectors
from . import extractors, facets, registers
from .config import Config, Scope, extractor_runs
from .extract import Context, Extract, dangling, decisions, discoveries, questions, register_rows, technology_words
from .model import FACETS_GRAPH, KI, TBOX_GRAPH
from .resolve import layers

# The text of every node with a claim: an entry by its name, claim, problem shape and the case it does
# not cover, and a decision's section by its own. An extractor gives the text of its own nodes.
TEXTS = f"""
PREFIX ki: <{KI}>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT ?n (SAMPLE(?l) AS ?label) (SAMPLE(?c) AS ?claim) (SAMPLE(?ps) AS ?shape) (SAMPLE(?dn) AS ?uncovered) WHERE {{
  {{
    GRAPH ?g {{
      ?n ki:claim ?c .
      {{ ?n ki:identifier ?id }} UNION {{ ?n ki:sectionOf ?parent }}
      OPTIONAL {{ ?n rdfs:label ?l }}
      OPTIONAL {{ ?n ki:problemShape ?ps }}
      OPTIONAL {{ ?n ki:doesNotCover ?dn }}
    }}
    FILTER (STRSTARTS(STR(?g), "{KI}index/"))
  }}
}} GROUP BY ?n"""


def store_dir(config: Config) -> Path:
    """Where the index lives: the configured ``[framework] store``, else the platform's data folder."""
    return config.store or platformdirs.user_data_path("vyvid") / "index"


def open_store(path: Path) -> ox.Store:
    """The built store, opened read-only so a query never contends with a build."""
    return ox.Store.read_only(str(path))


def load_vocabulary(store: ox.Store, stack: list[Scope], out: Extract) -> None:
    """The vocabulary files the stack's scopes name, general first, into the T-Box graph after the
    packaged vocabulary. A file that is missing or does not parse is reported and loses only itself."""
    for scope in stack:
        for path in scope.vocabulary:
            try:
                store.extend([ox.Quad(q.subject, q.predicate, q.object, TBOX_GRAPH)
                              for q in ox.parse(path=str(path), format=ox.RdfFormat.TURTLE)])
                out.bump("vocabulary-file")
            except (OSError, SyntaxError, ValueError) as error:
                out.problems.append(f"{path}: vocabulary of '{scope.name}' does not load, so its terms are absent ({error.__class__.__name__})")


def run_extractors(config: Config, stack: list[Scope], store: ox.Store, taggable: dict[str, set[str]],
                   out: Extract) -> tuple[dict[str, dict[str, str]], dict[str, str]]:
    """Run each extractor each project of the stack runs, its output belonging to the project.

    Returns the prefixes the extractors found, by scope, and the text to embed of the nodes they made."""
    prefixes: dict[str, dict[str, str]] = {}
    texts: dict[str, str] = {}
    for scope in (s for s in stack if s.kind == "project"):
        for run in extractor_runs(config, scope):
            context = extractors.Context(scope, scope.code or scope.path or Path.cwd(), config, taggable, store)
            result = extractors.load(run.kind)(context, run.settings)
            out.quads += result.quads
            out.problems += result.problems
            out.findings += result.findings
            for key, count in result.counts.items():
                out.bump(key, count)
            texts.update(result.texts)
            for prefix, namespace in result.prefixes.items():
                prefixes.setdefault(scope.name, {}).setdefault(prefix, namespace)
    return prefixes, texts


def build(config: Config, project: Scope | None = None, store_path: Path | None = None, embed: bool = True,
          model=None, scopes: list[Scope] | None = None) -> Extract:
    """Build the index of ``project``'s stack of layers, or of every configured scope when there is
    no project, into ``store_path`` (default: the store of ``store_dir``). ``scopes`` names the stack
    outright. Returns what was extracted, with its counts, problems and findings."""
    out = Extract()
    start = time.perf_counter()
    built_from = time.time()
    store_path = store_path or store_dir(config) / "store"
    stack = scopes or (layers(config, project) if project else [config.general, *config.domains.values(), *config.projects.values()])
    schemes, values = facets.merge(facets.registers([config.general, *(s for s in stack if s is not config.general)]))
    taggable = facets.taggable(values)
    types = registers.types_for(stack)
    words = technology_words(values)

    if store_path.exists():
        shutil.rmtree(store_path)
    store_path.parent.mkdir(parents=True, exist_ok=True)
    store = ox.Store(str(store_path))
    store.bulk_load(input=resources.files("vyvid").joinpath("data/knowledge.ttl").read_bytes(), format=ox.RdfFormat.TURTLE, to_graph=TBOX_GRAPH)
    store.bulk_load(input=facets.turtle(schemes, values).encode("utf-8"), format=ox.RdfFormat.TURTLE, to_graph=FACETS_GRAPH)

    load_vocabulary(store, stack, out)
    # Before the entries, because a Bears on may name a term by a prefix an extractor found.
    prefixes, texts = run_extractors(config, stack, store, taggable, out)

    contexts = [Context(config, scope, out, types, taggable, words, prefixes.get(scope.name, {})) for scope in stack]
    # Decisions first, since a register's Narrowed by names a decision's addendum.
    for ctx in contexts:
        decisions(ctx)
    for ctx in contexts:
        register_rows(ctx)
        discoveries(ctx)
        questions(ctx)
    store.bulk_extend(out.quads)
    # After the extractors, because a Bears on may name a term.
    dangling(store, out)
    store.flush()
    store.optimize()
    out.counts["quads"] = len(store)

    directory = store_path.parent
    target = directory / vectors.VECTORS
    if not embed:
        target.unlink(missing_ok=True)
        out.problems.append("no embeddings, because the build was told not to make them")
        out.bump("embeddings-unavailable")
    else:
        entries = {str(r["n"].value): vectors.join_text([r["label"] and r["label"].value, r["claim"].value,
                                                         r["shape"] and r["shape"].value, r["uncovered"] and r["uncovered"].value])
                   for r in store.query(TEXTS)}
        entries.update({iri: vectors.join_text([text]) for iri, text in texts.items()})
        try:
            out.counts["embedded"] = vectors.build(entries, directory, config.embedding, model)
        except vectors.Unavailable as error:
            out.problems.append(f"no embeddings, so nothing can be ranked by meaning: {error}")
            out.bump("embeddings-unavailable")
    (directory / "built-from").write_text(f"{built_from}\n", encoding="utf-8", newline="\n")
    # The scopes the store holds, so a question in a folder bound to another stack knows to rebuild.
    (directory / "built-for").write_text("".join(f"{s.name}\n" for s in sorted(stack, key=lambda s: s.name)), encoding="utf-8", newline="\n")
    out.counts["seconds"] = round(time.perf_counter() - start, 2)
    return out
