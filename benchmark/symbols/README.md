<!-- SPDX-License-Identifier: MIT -->

# Symbol ranking

This benchmark scores the ways `vyd find --kind symbol` could rank a project's symbols, on questions written before any of them was run. It parses each corpus into a symbol store, embeds it each way from nothing, and asks every question of every way.

The ways are listed at the head of `bench.py`. They are word search alone, vectors over every symbol, vectors over functions, types, classes and methods only, the fusion of word search with those, the same with the doc before the signature in the text that is embedded, and a few that separate what the order gains from what a left-out kind costs.

After those, the default way is shown beside the chunks of documentation around the code (module headers, named sections and block comments, kind `doc`), embedded the same way in a file of their own. The ways of showing both are the symbols alone, the chunks alone, both in one list by cosine, both with at most two of five places for chunks, three symbols and then two chunks, and five symbols and then three chunks. Each is scored on what it shows, five places or eight for the last, and the report lists the questions where it loses a symbol the default found and the questions only a chunk answers.

`questions.json` holds the questions for each corpus, each with the symbols that should answer it, named as the symbol is under its module (`Owner.name` for a field or a constructor). A question may also have `expect_doc`, the file and lines where the source answers it, and is then answered by a symbol or by a chunk overlapping those lines. These were fixed from the source before any run. Some use a word that is in neither the name nor the doc of the symbol they want. Do not change a question after seeing a result. Add new ones and say so.

Three figures are printed for each way, for each corpus and for all the questions together, with the cold embedding time and bytes for the vectors a way needs.

| Figure | Meaning |
|---|---|
| hit@5 | the share of questions where an expected symbol is in the top five |
| MRR | the mean reciprocal rank of the first expected symbol in the top eight |
| ms per query | the mean time to answer one question with the model loaded, which for a way using vectors is mostly the time to embed the question |

Each way's questions with no expected symbol in the top five are then listed.

## What it needs

- A vyvid configuration that declares a project for each corpus the questions name, each with `[[projects.symbols]]`, and an `[embedding] cache` that holds the model.
- The checkouts those projects point at, which are only read.
- The extra `vyvid[symbols]`, which the task asks `uv` for.

The benchmark writes under `--out` alone, a temporary folder when none is given, and nothing under a checkout or this repository.

## Running it

```bash
mise run bench:symbols -- --config <configuration> [--out <folder>] [--questions <file>] [--only <corpus> ...]
```

`--only` scores some of the corpora, for a machine that holds only one of the checkouts.

It is not part of `mise run check`, since it needs the checkouts and the model and takes minutes.

## An example configuration

```toml
[embedding]
cache = "~/bench/vcache"

[[projects]]
name = "lat"
code = "~/work/lattice"

[[projects.symbols]]
language = "python"
paths = ["code:tools/knowledge/*.py"]

[[projects]]
name = "dp"
code = "~/work/distributed-process"

[[projects.symbols]]
language = "haskell"
paths = ["code:packages/*/src/**/*.hs"]
```
