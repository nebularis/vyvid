# SPDX-License-Identifier: MIT
# From LATTICE's tools/knowledge/extract.py, relicensed MIT by its author.
"""Build the knowledge index of a stack of scopes into an Oxigraph store, and embed its text.

The store holds the vocabulary, the merged facets, and for each scope its entries and its declared
ontology terms. The vectors sit beside it, and a stamp records when the build started, taken before
anything was read so a file edited while the build runs is caught the next time.

The ontology documents are written in one bulk write after being parsed one at a time, and the
store is optimised at the end. A write per document left over a thousand files that compaction did
not merge, and a read-only open that has to open them all exceeds macOS's default limit of 256.
"""

from __future__ import annotations

import shutil
import time
from importlib import resources
from pathlib import Path

import platformdirs
import pyoxigraph as ox

from . import embed as vectors
from . import facets, registers
from .config import Config, Scope
from .extract import Context, Extract, dangling, decisions, discoveries, load_ontologies, questions, register_rows, technology_words, term_summary
from .model import FACETS_GRAPH, KI, TBOX_GRAPH
from .resolve import layers

# The text of every node with a claim: an entry by its name, claim, problem shape and the case it does
# not cover, a decision's section by its own, and a declared term by its claim, which opens with its label.
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
  }} UNION {{
    GRAPH ?g {{ ?n ki:identifier ?id ; ki:claim ?c . }}
    FILTER (STRSTARTS(STR(?g), "{KI}terms/"))
  }}
}} GROUP BY ?n"""


def store_dir(config: Config) -> Path:
    """Where the index lives: the configured ``[framework] store``, else the platform's data folder."""
    return config.store or platformdirs.user_data_path("vyvid") / "index"


def open_store(path: Path) -> ox.Store:
    """The built store, opened read-only so a query never contends with a build."""
    return ox.Store.read_only(str(path))


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

    contexts = [Context(config, scope, out, types, taggable, words) for scope in stack]
    # Decisions first, since a register's Narrowed by names a decision's addendum.
    for ctx in contexts:
        decisions(ctx)
    for ctx in contexts:
        register_rows(ctx)
        discoveries(ctx)
        questions(ctx)
    store.bulk_extend(out.quads)
    with_terms = [s for s in stack if any(e["kind"] == "owl-terms" for e in s.extractors)]
    load_ontologies(store, with_terms, out)
    # After the documents are loaded, because the summary is derived by query over them.
    term_summary(store, with_terms, out)
    # After the terms, because a Bears on may name one.
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
