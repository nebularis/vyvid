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

## Questions generated from `ast`

`mechanical.py` scores `find --kind symbol` on questions it generates from Python's `ast`, so a corpus needs no questions written by hand. It reads the same tracked files the symbol store parsed, draws with a fixed seed (`--seed`, 20261104 by default) and only from symbols that have a docstring, and asks each question through `find.ranked`, the function `find` calls, so the figures are those of the default way.

| Mode | Question | Answered when |
|---|---|---|
| `name` | the symbol's exact name | the symbol is among the results. `hit@1` is the first |
| `meaning` | the first sentence of its docstring, with the words of its name removed together with their plural, past and `-ing` forms | the symbol is among the results |
| `module` | the first sentence of a module docstring | a symbol or a chunk of documentation of that file is among the results |

A sentence left with under three words is not used, and `--count` (300 by default) is the most questions of each mode, so a project with fewer documented symbols or modules is asked fewer. The word removal is mechanical and leaves other words of the doc that only the symbol would use, so `meaning` is a stand-in for a question that does not share the name, not a measure of one. A name that several symbols share has no one symbol to find, so `name` also prints the share of questions whose first result bears the name.

The report gives the size of each corpus in files, symbols and chunks, the cold parse and embedding time and bytes, `hit@1`, `hit@5` and `MRR` over the five places `find` shows, and the time of a query with the model loaded (mean, median and 95th percentile, mostly the question's embedding). It then counts the hits by kind of symbol, by a test file or not, by a name shared with another symbol, by a first sentence shared with another, and by a private name. Last it draws questions again from symbols outside test files alone and asks them of the full index and of an index built without test files (`test` or `tests` folders, `test_*.py`, `*_test.py` and `conftest.py`), and prints how many of the five places test files took.

```bash
mise run bench:mechanical -- --config <configuration> [--out <folder>] [--only <project> ...] [--seed N] [--count N]
```

It scores each project of the configuration that declares Python symbols and writes `mechanical.json` under `--out`, with every question, its place and its results. It is not part of `mise run check`, and `tests/test_mechanical.py` holds the tests of the generator.

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
