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

import hashlib
import shutil
import time
from importlib import resources
from pathlib import Path

import platformdirs
import pyoxigraph as ox

from . import embed as vectors
from . import config as cfg
from . import extractors, facets, registers
from .extractors import command
from .config import Config, Scope, extractor_runs, refusals, timeouts
from .credentials import private_dir
from .extract import Context, Extract, dangling, decisions, discoveries, questions, register_rows, technology_words
from .model import FACETS_GRAPH, KI, TBOX_GRAPH
from .citations import domain_citations
from .resolve import forget, layers

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


CHECKOUTS = "checkouts"
ROOT_FILE = "checkout-root"


def store_dir(config: Config, project: Scope | None = None) -> Path:
    """Where the index lives: the configured ``[framework] store``, else the platform's data folder.

    A project answered from a linked checkout has a folder of its own under ``checkouts``, named by the
    checkout's folder and a digest of its resolved root. Everything else, a project's main checkout
    included, uses the base."""
    base = config.store or platformdirs.user_data_path("vyvid") / "index"
    if project is None or project.checkout is None:
        return base
    root = project.checkout.resolve()
    return base / CHECKOUTS / f"{root.name}-{hashlib.sha256(str(root).encode('utf-8')).hexdigest()[:12]}"


def prune(config: Config, dry_run: bool = False) -> list[tuple[Path, Path]]:
    """Remove the stores of checkouts whose root no longer exists, returning each store and its root.
    Only a folder under ``checkouts`` that records a root is considered, and nothing else is touched."""
    base, gone = store_dir(config) / CHECKOUTS, []
    for folder in sorted(base.iterdir()) if base.is_dir() else []:
        marker = folder / ROOT_FILE
        if marker.is_file() and not (root := Path(marker.read_text(encoding="utf-8").strip())).exists():
            gone.append((folder, root))
            if not dry_run:
                shutil.rmtree(folder)
    return gone


def open_store(path: Path) -> ox.Store:
    """The built store, opened read-only so a query never contends with a build."""
    return ox.Store.read_only(str(path))


def load_vocabulary(store: ox.Store, stack: list[Scope], out: Extract) -> None:
    """The vocabulary files the stack's scopes name, general first, into the T-Box graph after the
    packaged vocabulary. A file that is missing or does not parse is reported and loses only itself."""
    for scope in stack:
        for path in scope.readable(scope.vocabulary):
            try:
                store.extend([ox.Quad(q.subject, q.predicate, q.object, TBOX_GRAPH)
                              for q in ox.parse(path=str(path), format=ox.RdfFormat.TURTLE)])
                out.bump("vocabulary-file")
            except (OSError, SyntaxError, ValueError) as error:
                out.problems.append(f"{path}: vocabulary of '{scope.name}' does not load, so its terms are absent ({error.__class__.__name__})")


def run_extractors(config: Config, stack: list[Scope], store: ox.Store, taggable: dict[str, set[str]],
                   out: Extract, folder: Path) -> tuple[dict[str, dict[str, str]], dict[str, str]]:
    """Run each extractor each project of the stack runs, its output belonging to the project.

    A project's command extractor writes under ``folder``. Returns the prefixes the extractors found,
    by scope, and the text to embed of the nodes they made."""
    prefixes: dict[str, dict[str, str]] = {}
    texts: dict[str, str] = {}
    for scope in (s for s in stack if s.kind == "project"):
        for run in extractor_runs(config, scope):
            context = extractors.Context(scope, scope.code or scope.path or Path.cwd(), config, taggable, store)
            if "command" in run.settings and not cfg.may_run(config, scope, "extractors"):
                result = extractors.Result(problems=[f"extractor '{run.kind}' of project '{scope.name}' is a command, and {cfg.not_trusted(config, scope, 'extractors')}, "
                                                     "so its entries are absent. Run vyd trust in a terminal, then vyd build"])
            else:
                result = command.extract(run, context, folder) if "command" in run.settings else extractors.load(run.kind)(context, run.settings)
            out.quads += result.quads
            out.problems += result.problems
            out.findings += result.findings
            for key, count in result.counts.items():
                out.bump(key, count)
            texts.update(result.texts)
            for name, listed in result.units.items():
                out.units.setdefault(scope.name, {}).setdefault(name, listed)
            for prefix, namespace in result.prefixes.items():
                prefixes.setdefault(scope.name, {}).setdefault(prefix, namespace)
    return prefixes, texts


def build(config: Config, project: Scope | None = None, store_path: Path | None = None, embed: bool = True,
          model=None, scopes: list[Scope] | None = None) -> Extract:
    """Build the index of ``project``'s stack of layers, or of every configured scope when there is
    no project, into ``store_path`` (default: the store of ``store_dir`` for the project). ``scopes`` names the stack
    outright. Returns what was extracted, with its counts, problems and findings."""
    out = Extract()
    forget()
    start = time.perf_counter()
    built_from = time.time()
    if store_path is None:  # the store's own folders are owner-only, the base and a checkout's
        store_path = store_dir(config, project) / "store"
        for owned in (store_dir(config), store_path.parent):
            private_dir(owned)
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
    prefixes, texts = run_extractors(config, stack, store, taggable, out, store_path.parent)

    contexts = [Context(config, scope, out, types, taggable, words, prefixes.get(scope.name, {})) for scope in stack]
    # Decisions first, since a register's Narrowed by names a decision's addendum.
    for ctx in contexts:
        decisions(ctx)
    for ctx in contexts:
        register_rows(ctx)
        discoveries(ctx)
        questions(ctx)
    out.problems += refusals(stack) + timeouts(stack)
    for key in [k for k in out.counts if k.startswith("moved:")]:
        name, to = key.removeprefix("moved:").split(">")
        out.problems.append(f"{out.counts[key]} entries of '{name}' moved to '{to}', which answers for them, so the copies in '{name}' are not indexed")
    for domain in (s for s in stack if s.kind == "domain"):
        out.problems += domain_citations(config, domain)
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
            out.counts["embedded"] = vectors.build(entries, directory, config.embedding, model, warm=None if store_dir(config) == directory else store_dir(config))
        except vectors.Unavailable as error:
            out.problems.append(f"no embeddings, so nothing can be ranked by meaning: {error}")
            out.bump("embeddings-unavailable")
    if project is not None and project.checkout is not None:  # so `vyd store prune` can tell when it is gone
        (directory / ROOT_FILE).write_text(f"{project.checkout.resolve()}\n", encoding="utf-8", newline="\n")
    (directory / "built-from").write_text(f"{built_from}\n", encoding="utf-8", newline="\n")
    # The scopes the store holds, so a question in a folder bound to another stack knows to rebuild.
    (directory / "built-for").write_text("".join(f"{s.name}\n" for s in sorted(stack, key=lambda s: s.name)), encoding="utf-8", newline="\n")
    out.counts["seconds"] = round(time.perf_counter() - start, 2)
    return out
