<!-- SPDX-License-Identifier: MIT -->

# LATTICE bake-off

This benchmark checks that `vyd find` ranks as well as the knowledge index it was extracted from. It asks LATTICE's own `find` and vyvid's `find` the same questions with the same embedding model, and compares the answers.

The questions are the 47 of the original bake-off and the 5 held-out ones, with each question's facets. A question without an `expect` list is a negative one and is not scored, which leaves 43 and 5. Both sides ask with no kind filter and the facets as given, and a facet value the index does not know is stripped.

Two figures are printed for each set, for LATTICE and for vyvid.

| Figure | Meaning |
|---|---|
| hit@5 | the share of questions where any `expect` id is in the top five |
| MRR | the mean reciprocal rank of the first `expect` or `accept` id in the top eight |

Every question whose top five differ is then listed with both top fives. A difference is read against the two indexes first, since LATTICE extracts kinds of entry that a configuration may not declare, and those can fill a top five that vyvid cannot.

## What it needs

- A LATTICE checkout with its own index built, so that `.build/knowledge/store` and its vectors exist, and with the embedding model in place under `.build/knowledge/model`.
- A vyvid configuration that declares the checkout as a project, with its families and its `owl-terms` extractor, and an `[embedding] cache` that holds the same model.
- That configuration's index built with embeddings on, by `vyd build <checkout>`.

The benchmark never writes under the checkout. LATTICE's store is opened read-only and its logs are redirected into the output folder.

## Running it

```bash
mise run bench:lattice -- --config <configuration> [--lattice <checkout>] [--out <folder>]
```

`--lattice` defaults to `~/work/lattice` and `--out` to `bench-out`, which receives `questions.json`, `lattice.json`, `vyvid.json` and LATTICE's logs. It is not part of `mise run check`, since it needs a built checkout and the model and takes minutes.

## An example configuration

The model is fetched into a cache folder laid out as `<cache>/BAAI--bge-small-en-v1.5/<revision>`. Pointing `cache` at a folder that links to LATTICE's model avoids a second download.

```toml
[framework]
store = "~/bench/vstore"

[embedding]
cache = "~/bench/vcache"

[[projects]]
name = "lattice"
code = "~/work/lattice"
docs = "code:docs"

[projects.families]
STD = { defined = "docs:developer/standards.md", type = "standard" }
PRI = { defined = "docs:developer/principles.md", type = "principle" }
PAT = { defined = "docs:developer/patterns.md", type = "pattern" }
MEC = { defined = "docs:developer/mechanisms.md", type = "mechanism" }
CAP = { defined = "docs:developer/capabilities.md", type = "capability" }
TD = { defined = "docs:developer/technical-debt.md", type = "debt" }
PDD = { defined = "docs:developer/pending-design-decisions.md", type = "pending-decision" }
BL = { defined = "docs:developer/backlog.md", type = "backlog" }
ADR = { pattern = 'ADR-A-?[A-Za-z]{0,4}-?\d+[a-z]?', rule = "file", type = "decision", defined = "docs:architecture/decisions/*.md" }
TSD = { pattern = 'TSD-\d+[a-z]?', rule = "heading", type = "discovery", defined = "docs:architecture/triple-store-discovery.md" }
LGQ = { pattern = '(?!TSD-)[A-Z]{1,4}\d*[a-z]?-Q\d+', rule = "question", type = "question", defined = ["docs:developer/plans/*.md", "docs:developer/sketches/*.md"] }

[[projects.extractors]]
kind = "owl-terms"
paths = ["code:ontology/**/*.ttl"]
```
