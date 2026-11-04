<!-- SPDX-License-Identifier: MIT -->

# Symbol indexing: research for VYD-0b

**Unit:** vyvid-framework. **Questions:** VYD-Q28 and VYD-Q29, below.

How existing tools collect a codebase's symbols and index them, so that `--kind term` can answer for Haskell, Java, Python or TypeScript as it answers for OWL. The prototype was measured on 2026-11-04 on an 8-core arm64 Mac, in a scratch folder, and reading LATTICE and `distributed-process` only.

## The recommendation

**A general tree-sitter extractor, with a query and a small block of code per language.** A reader of GHC's `.hie` files can follow for Haskell, only if a question needs what parsing cannot give, and only from files a person built, never built by `vyd`. No existing tool is adopted as the base, since none met the safety line below and none was measured.

| Test | Result |
|---|---|
| Python against `ast`, 412 files of `lattice/tools` and `platform` | 8,884 of 8,884 symbols by name, 2,073 of 2,073 docstrings, none missed and none wrong, and rerun independently |
| Haskell against a hand count, `Control.Distributed.Process.Internal.Types`, 891 lines | 240 of 240 symbols, 68 of 68 export names, 190 of 190 exported symbols, 75 of 75 Haddock blocks on the right symbol |
| Java and TypeScript | no hand count. Java spot-checked on one file, TypeScript a 7-line smoke test |
| Time | 7.4 ms per 1,000 lines of Python, 13.6 of Java, 11.7 of Haskell. Embedding is the cost, 30 s for 3,415 terms |
| `find --kind term`, 12 questions on single modules | each found at least one expected symbol, and 8 of the 12 found all of them |
| The same 6 questions over a wider corpus | 5 found at least one. At 3,415 Haskell terms a question lost its expected symbols, to terms the prototype did not read |
| Glue | 10 to 30 lines of query per language, and 50 to 150 lines of code for signature, doc and owner. Haskell's Haddock attachment is the hardest |

**The safety line decides more than the measurements.** Parsing runs nothing from a clone. A `.hie` file, `scip-java`, `scip-typescript`, Kythe, CodeQL and the Haskell language server each need a build or an install, and building runs the clone's code: its Template Haskell, a custom `Setup.hs`, preprocessors, annotation processors or npm scripts. The prototype's `.hie` build took 24 s and ran the compile-time code of two Template Haskell modules. A `vyvid.toml` is hostile until trusted, so an extractor that builds cannot be the default.

**What parsing cannot give.** It knows names and no more. 26% of the export names in `distributed-process` (453 of 1,767) are re-exports it cannot follow, it cannot see derived instances, 118 against the 50 written in the module measured, and it has no inferred types, though only 3 of 2,040 functions there lack a signature, and no callers.

**What would change this.** A need to answer "who calls this", "what re-exports this" or "all instances of this class", a grammar that proves unreliable, since parse errors were not measured, or retrieval that stays poor at scale. Instances filling the top five suggests the next cheap test, keeping an instance as a term but embedding no text for it.

## Measured: what to embed

Measured 2026-11-04 on an 8-core arm64 Mac with `benchmark/symbols`, which answers VYD-Q34. The corpora are the 108 Haskell files of `packages/*/src` in a public Haskell library (34,310 lines, 3,415 symbols, parsed in 0.48 s) and the 14 files of `tools/knowledge/*.py` in LATTICE (447 symbols, 0.12 s). The 16 questions were written before any was run, 3 of Python and 3 of Haskell from the research and 4 and 6 new. The new ones are in a developer's words, and some use a word in neither the name nor the doc of the symbol wanted, such as stopping a process for `kill`. A question counts as answered when an expected symbol is in the top five. MRR is over the top eight. Every way is embedded from nothing, so the time and bytes are cold ones.

| Way | Python hit@5 | Python MRR | Haskell hit@5 | Haskell MRR | All hit@5 | All MRR | Embed, Haskell | Vectors, Haskell | Per query |
|---|---|---|---|---|---|---|---|---|---|
| word search alone | 1.000 | 0.857 | 0.111 | 0.051 | 0.500 | 0.404 | none | none | 0.4 ms |
| vectors over every symbol | 1.000 | 0.857 | 0.333 | 0.310 | 0.625 | 0.549 | 29.5 s | 6.2 MB | 4.7 ms |
| vectors over functions, types, classes and methods only | 1.000 | 0.857 | 0.333 | 0.236 | 0.625 | 0.508 | 20.3 s | 3.7 MB | 4.6 ms |
| those, fused with word search | 1.000 | 0.929 | 0.444 | 0.226 | 0.688 | 0.533 | 20.3 s | 3.7 MB | 5.2 ms |
| those, with the doc before the signature | 1.000 | 1.000 | 0.444 | 0.274 | 0.688 | 0.592 | 19.8 s | 3.7 MB | 4.6 ms |
| those with the doc first, fused with word search | 1.000 | 1.000 | 0.444 | 0.226 | 0.688 | 0.565 | 19.8 s | 3.7 MB | 5.1 ms |
| every symbol fused with word search | 1.000 | 0.929 | 0.444 | 0.189 | 0.688 | 0.512 | 29.5 s | 6.2 MB | 5.1 ms |
| **vectors over every symbol, the doc before the signature** | 1.000 | 1.000 | 0.444 | 0.330 | 0.688 | 0.623 | 29.6 s | 6.2 MB | 4.7 ms |

The per-query time is mostly embedding the question (about 4.5 ms). Fusion adds about 0.5 ms. Python had 7 questions and Haskell 9, so one question is 0.143 and 0.111 of its corpus and 0.063 of all. The same run twice gave the same figures.

**Which questions each way loses** (no expected symbol in the top five). Every way answered all seven Python questions, so the losses are Haskell's alone.

| Way | Loses |
|---|---|
| word search alone | the node of a process or port, wrapping a value without serialising, stopping a process, waiting with a time limit, being told when a process goes down, a channel for typed messages, starting a process remotely, sending by a registered name |
| every symbol, and the kinds only | wrapping, stopping, waiting, the channel, starting remotely, sending by name |
| the kinds fused, and every symbol fused | stopping, waiting, the channel, starting remotely, sending by name |
| the kinds with the doc first | wrapping, stopping, the channel, starting remotely, sending by name |
| every symbol with the doc first | wrapping, stopping, the channel, starting remotely, sending by name |

**What leaving out instances, constructors and fields loses.** The question about the node of a process or port wants the field `processNodeId`. Every symbol ranks it first (reciprocal rank 1.00) and the kinds alone cannot return it, giving 0.33 for `nodeOf` third, or 0.50 with the doc first. That is the whole of the MRR gap in Haskell (0.310 against 0.236), and no hit@5 changed. The kinds saved 40% of the bytes and 31% of the time.

**What the doc first gains.** With the doc before the signature MRR rose in both corpora and for both sets of kinds, from 0.857 to 1.000 in Python and from 0.236 to 0.274 and 0.310 to 0.330 in Haskell, and no hit@5 fell.

**Fusion helped nothing that vectors had not.** Word search with reciprocal rank fusion never beat its vector-only twin on MRR, 0.592 against 0.565 and 0.549 against 0.512, and in Haskell it raised hit@5 of the two sets with the signature first from 0.333 to 0.444, which putting the doc first reached without it.

**The default** is vectors over every symbol with the doc before the signature. It ties four other ways for the best hit@5 (0.688, 11 of 16) and has the best MRR (0.623), at 6.2 MB and 29.6 s on the Haskell. The kinds-only way with the doc first is a fair choice at 0.592 and 40% less, and the question it loses is a field. Hit@5 cannot tell the best five apart, since they differ by one question, so the MRR order is the only separation and it rests on 16 questions in two languages, written by us. Word search is used where there are no vectors, and a name written in the question as camelCase or snake_case is ranked first, which these questions did not test.

**The one-line hint** under a plain `find` appears when the best symbol scores the model's `near` score (0.74) or more. The best scores of the 16 questions were 0.666 to 0.834 and 11 of them reached it, and 5 questions about nothing in the code scored 0.487 to 0.693 and none did.

## Measured: documentation beside symbols

Measured 2026-11-04 on the same arm64 Mac with `benchmark/symbols`, on the Haskell corpus alone. The Python corpus was not run, since its checkout was not to be read on that day, so what follows says nothing of Python. The corpus is the 108 files and 3,415 symbols above, and 274 chunks of documentation, which are the module headers, the `[Heading]` sections of them, `-- $name` sections, block comments and runs of three or more `--` lines at the left margin, cut at `[Heading]` lines and into windows of about 900 characters with 150 of overlap. A licence and the `Copyright`, `License`, `Maintainer`, `Stability`, `Portability` and `Module` lines are dropped, and so is a chunk under 80 characters.

The 19 Haskell questions are the 9 above and the 10 the maintainer wrote. For 9 of the 10, the file and lines where the source answers it were written into `questions.json` as `expect_doc` before the first run, by reading the source, and the tenth has none, since its answer is a symbol. A question counts as answered when an expected symbol or a chunk overlapping an expected range is among the places shown. Part of the `expect_doc` of three questions is the doc of a symbol, which is no chunk, so only a module header, a section or a note can meet the rest.

| Way | Places | Answered by a symbol | Answered by either | MRR | Lost | Gained | Per query beyond the question |
|---|---|---|---|---|---|---|---|
| symbols alone, the default until now | 5 | 10 of 19 | 10 of 19 | 0.344 | 0 | 0 | 0.6 ms |
| chunks alone | 5 | 0 | 6 of 19 | 0.281 | 10 | 2 | 0.5 ms |
| both in one list by cosine | 5 | 8 of 19 | 12 of 19 | 0.458 | 2 | 2 | 0.5 ms |
| **both, at most two of five places for chunks** | 5 | 10 of 19 | 12 of 19 | 0.458 | 0 | 2 | 0.4 ms |
| three symbols, then two chunks | 5 | 9 of 19 | 11 of 19 | 0.360 | 1 | 2 | 0.4 ms |
| five symbols, then three chunks | 8 | 10 of 19 | 12 of 19 | 0.361 | 0 | 2 | 0.4 ms |

Lost is a symbol the default found that the way no longer shows, and gained is a question answered only because of a chunk. The question embedding costs about 5 ms more for every way. The chunks cost 12.0 s to embed cold and 496,556 bytes, against 31.5 s and 6,175,484 for the symbols, and the parse took 0.59 s with them against 0.48 s before.

**Where the losses are.** Chunks alone lose ten symbol answers, and they answer six questions only. The one list by cosine loses two, the ordering guarantees and the strict variants, and in both a chunk takes the place and also answers. Three symbols and two chunks loses the question about waiting with a time limit, whose symbol was fifth. The cap and the eight-place list lose none, so all ten symbol answers kept their places, four of the first nine and six of the maintainer's.

**Where the gains are.** Two of the maintainer's questions are answered only by a chunk in every combined way, starting a prioritised process and how a prioritised mailbox orders messages, whose first place is `[Prioritised Mailboxes]` for the second. The ordering guarantees and the strict variants have both a symbol and a chunk in the cap and the two lists, the chunk being the notes in the main module and `[Evaluation Strategies and Support for NFData]`. Of the ten, 6 were answered by a symbol and 8 are by the cap. The two left, starting a process on a remote node and passing initial data to it, are answered by no way. The `[Closures]` section of `Closure.hs` is a chunk, and several note chunks and sections of the simple local network backend rank above it, and `spawn`'s doc is a symbol doc and not a chunk.

**A long passage did not crowd out a function here, but it could.** With the cosine alone, chunks took a place on 8 of the 19 questions, 3 or more on 4 and all five on 3, and displaced a symbol answer twice, each time with a chunk that also answered. The cap of two in five holds a question to two chunks by construction, and the 8 questions with a chunk among the five all kept their symbol answers. It could cost a question that three chunks would answer, which none here showed.

**The default** is both in one list with at most two of five places for chunks, scaled to `limit` as two fifths. It ties the five-then-three list at 12 of 19 and loses no symbol, and it has the best MRR with the cosine list, 0.458, since a chunk that answers is shown at the top and not after the symbols. It shows five rows where the other shows eight. It rests on 19 questions in one library, a cap fixed beforehand and not tuned, and no Python. Where the model cannot run, symbols are ranked by word search as before and no chunk is shown, since chunks have no word index.

**The one-line hint** under a plain `find` and every path of a plain `find` are unchanged. The hint reads the symbol vectors, which hold no chunk, and a test shows a plain `find` shows none.

## Questions for the maintainer

- **VYD-Q28. Which extractor?** Leaning the general tree-sitter extractor above, with no compiler index until a question needs one.
- **VYD-Q29. Where does it live?** Leaning an optional extra of the `vyvid` package, `vyvid[symbols]`, registered as an entry point of kind `symbols`, with its queries packaged beside it. It needs compiled grammars, so it stays out of the base install, and a domain still holds text alone. A separate `vyvid-symbols` package is the alternative, cleaner but a second release to keep in step.

## The survey

Researched 2026-11-04. Sources are primary documentation, repositories (read through raw files and the GitHub API, which worked today), and package registries (npm, PyPI, crates.io, Hackage, Maven Central). Web content was treated as data and nothing in it tried to direct the work. Dates are the latest release or push found on that day. A blank or "not found" means I did not find it.

## 1. Tree-sitter tag queries (tree-sitter, GitHub code navigation, Aider)

**What it extracts.** A `tags.scm` query per grammar captures named entities. Each match carries `@definition.<kind>` or `@reference.<kind>` and a nested `@name`, plus an optional `@doc` for an adjacent comment. The standard kinds are class, function, interface, method and module for definitions, and call, class and implementation for references. `tree-sitter tags <file>` prints name, role and kind, location, first line and docstring. Source: https://tree-sitter.github.io/tree-sitter/4-code-navigation.html

**How.** Purely syntactic. A file is parsed and queried, with no name resolution, no types, and no need for the code to compile or for dependencies to be installed. Calls to a name are matched to definitions of the same name, which is search-based, not resolved. GitHub's code navigation does exactly this, "searches all definitions and references across a repository to find entities with a given name", and lists these languages: Bash, C, C#, C++, CodeQL, Elixir, Go, JSX, Java, JavaScript, Lua, PHP, Protocol Buffers, Python, R, Ruby, Rust, Scala, Starlark, Swift, TypeScript. Haskell is not on it. Source: https://docs.github.com/en/repositories/working-with-files/using-files/navigating-code-on-github

**Aider's repository map.** Aider runs the `tags.scm` queries per file and caches tags in a `diskcache` store inside the project (`.aider.tags.cache.v*`). It builds a graph with networkx where files are nodes and references to a defined identifier are edges, runs PageRank personalised toward files in the chat, and renders the top definitions into a token budget (default 1k, `--map-tokens`). It uses no embeddings. Sources: https://aider.chat/docs/repomap.html and https://raw.githubusercontent.com/Aider-AI/aider/main/aider/repomap.py

**Store.** None by design. `tree-sitter tags` writes to stdout and the `tree-sitter-tags` crate (0.27.1, 2026-10-08) returns tags in memory. A consumer chooses the store. Aider uses a local disk cache.

**Languages and queries.**
- Java, Python and TypeScript each ship `queries/tags.scm` in their own grammar repository (HTTP 200 on raw files, 2026-11-04). The Python query also captures module-level constants and calls. The TypeScript query captures function signatures among others.
- **Haskell: tree-sitter-haskell 0.24.1 (crate, 2026-09-30) ships `highlights.scm`, `injections.scm` and `locals.scm` and no `tags.scm`.** I read the crate archive. The npm package 0.23.1 (2024-11-10) is older.
- Aider vendors its own Haskell query, `queries/tree-sitter-languages/haskell-tags.scm`, three lines capturing `(function (variable))` and `(bind (variable))` as functions and `(signature (variable))` as a type. It captures no data types, classes or modules and no comments, so it is a weak starting point. Aider's newer `tree-sitter-language-pack` directory has no Haskell file. Source: https://raw.githubusercontent.com/Aider-AI/aider/main/aider/queries/tree-sitter-languages/haskell-tags.scm
- Writing a Haskell `tags.scm` ourselves is feasible (the grammar exposes `module`, `function`, `bind`, `signature`, data and class declarations) but the grammar's `_`-prefixed rules are hidden from queries, and I did not write or test one.

**Licence.** tree-sitter CLI and runtime MIT (npm `tree-sitter-cli` 0.27.1, 2026-10-08). tree-sitter-haskell MIT. Aider Apache-2.0, last push 2026-05-22, latest PyPI 0.86.2 (2026-02-12). Aider's vendored queries are adapted from MIT and Apache-2.0 grammars (its README lists them) and its language-pack queries defer to Goldziher/tree-sitter-language-pack for licences, which I did not follow up. Vendoring queries from the tree-sitter grammar repositories into an MIT project is fine if the copyright notice travels with them.

**Compile / offline / install / cost.** No compile. Fully offline. `cargo install tree-sitter-cli` or npm, or a binding such as the `tree-sitter` Python package, plus one grammar per language. No cost figures published for `tags`. Aider publishes none for map building.

**Maintained.** Yes. tree-sitter 0.27.1 on 2026-10-08.

**Safety on an untrusted clone.** Parsing executes nothing in the target repository. The risk sits in the grammar and query files we choose, which come from us, not from the clone. Do not load `tree-sitter.json` or query files found inside the clone.

**Fit for Вивід.** The closest analogue to the OWL path, since it yields name, kind, line and an adjacent comment per definition with no daemon. It gives no module-qualified identity and no types.

## 2. Language servers and compiler indexes

### 2a. SCIP and LSIF (Sourcegraph)

**What.** LSIF is a JSON graph of vertices (documents, ranges, result sets) and edges that replays LSP requests such as `documentSymbol`, `hover`, `definition` and `references`. Source: https://microsoft.github.io/language-server-protocol/specifications/lsif/0.6.0/specification/ . SCIP is a protobuf schema (`scip.proto`) of documents with occurrences, symbols and symbol information (documentation, relationships). The SCIP repository now lives at https://github.com/scip-code/scip (the old `sourcegraph/scip` URL answers 301). I did not read the LSIF specification's status text about SCIP, so I cannot confirm from it that LSIF is deprecated.

**Indexers listed** (README, Apache-2.0): scip-java (Java, Scala, Kotlin), scip-typescript (TypeScript, JavaScript, Svelte), scip-python, rust-analyzer, scip-clang, scip-ruby, scip-dotnet, scip-dart, scip-php. Haskell is not listed. Source: https://github.com/sourcegraph/scip

**Release dates.**
- scip v0.10.0, 2026-09-03.
- scip-java v0.14.0, 2026-11-04 (https://github.com/scip-code/scip-java). Maven Central's `scip-java_2.13` still shows 0.10.4 from 2025-03-05, so the newer line may publish under another coordinate. I did not resolve this.
- scip-typescript v0.6.1, 2026-11-03.
- scip-python 0.6.8, 2026-10-22 (npm, licence MIT).

**How each indexes.**
- scip-java is a javac compiler plugin (`-Xplugin`), run through the Gradle or Maven plugin, so **it needs the project to build and it runs inside the build, including custom annotation processors**. Source: https://github.com/scip-code/scip-java/blob/main/docs/design.md
- scip-typescript runs from the directory with `tsconfig.json` after `npm install` or `yarn install`. Dependencies must be installed. A `svelte-kit sync` step is needed for SvelteKit. Source: https://github.com/sourcegraph/scip-typescript
- scip-python is built on Pyright. I did not read its page, so how it resolves imports is unconfirmed.

**Haskell.** No official indexer. A community `soulomoon/scip-haskell` converts GHC `HieFile` to SCIP, Apache-2.0, last push 2024-04-13, 0 stars, README is one line. Treat as abandoned. The Hackage `scip` package (0.8.1) holds generated protobuf bindings only, not an indexer, and its page reported failed builds as of 2026-06-04. Sources: https://hackage.haskell.org/package/scip and https://github.com/soulomoon/scip-haskell

**Store.** One `index.scip` protobuf file per run. Reading it needs only a protobuf library, so it loads into an embedded store with no server. Official bindings exist for Rust, Go, TypeScript, Haskell and others. Symbol information carries documentation strings, so a "claim or comment" can be filled from it.

**Cost.** No published figures found.

### 2b. universal-ctags

**What.** Tags (name, kind, file, line, scope, signature depending on the parser) from per-language parsers, some hand-written C, some regex-based optlib. Output formats include JSON when built with libjansson (`--output-format=json`). Source: https://docs.ctags.io/en/latest/man/ctags.1.html

**Haskell.** There is a C parser, `parsers/haskell.c`, copyright 2003, which says it does not handle operators or infix definitions such as ``a `f` b``. Source: https://raw.githubusercontent.com/universal-ctags/ctags/master/parsers/haskell.c . Java, Python and TypeScript parsers exist but I did not read their pages.

**Licence.** GPL-2.0 (GitHub API, the haskell.c header says GPL v2 or later). **An MIT project can run it as a separate process the user installs, but should not vendor or link it.** Output is data and carries no licence obligation I could identify, though I am not a lawyer.

**Compile / offline / install.** No compile, offline, binary from package managers. Release 6.2.1 on 2025-10-25. Repository push 2026-11-03, so maintained.

**Safety.** The manual says ctags reads `.ctags.d/*.ctags` and `ctags.d/*.ctags` automatically, and the entries are relative paths, which I read as the current directory but the page does not say so outright. Option files can define parsers and regexes. Run with `--options=NONE` as the first argument to stop automatic config reading. I did not find a feature that executes code from scanned files, and I did not examine the `--_xformat` or external-command (xcmd) paths.

### 2c. GHC `.hi`, `.hie`, HieDb, HLS

**`.hie` contents.** GHC's extended interface files hold a simplified AST with source positions and types, identifiers annotated with scope, and the raw bytes of the original source. They are written with `-fwrite-ide-info` and redirected with `-hiedir`. Not every expression node carries a type. Source: https://downloads.haskell.org/ghc/latest/docs/users_guide/separate_compilation.html

**Format version.** The users guide gives no version number. The file header stores `hieVersion` and the GHC version string, and the reader `readHieFileWithVersion` returns the failing header on mismatch (GHC `compiler/GHC/Iface/Ext/Binary.hs`). So a reader must be linked against a GHC library compatible with the one that wrote the files. I did not find a table mapping `hieVersion` to GHC releases.

**HieDb** (https://hackage.haskell.org/package/hiedb, repository `haskell/HieDb`). 0.8.0.0 uploaded 2026-01-21, BSD-3-Clause, repository push 2026-08-05. Tested with GHC 9.0.2 through 9.14.1 (listing 9.2.8, 9.4.8, 9.6.7, 9.8.4, 9.10.3, 9.12.2) and the `ghc` bound is >=8.6 and <9.15. It is a library and CLI: `hiedb -D <db> index <hiedir>`, then `name-refs`, `type-refs`, `point-refs`. The result is a plain SQLite database with `refs` and `defs` tables, so **it can be read from any SQLite client with no server**. Whether `defs` holds doc comments or line spans, I did not confirm. Cost, from one informal run on all of Hackage under GHC 9.4.7 with `--skip-types`: 1021 s to index and 5.2 GB. Source: https://simonmar.github.io/posts/2025-05-22-Glean-Haskell.html (single experiment, not a benchmark). Note the cost is on top of compiling every package to produce the `.hie` files. HieDb needs the code to have been compiled by GHC.

**HLS** (https://github.com/haskell/haskell-language-server). 2.15.0.0 released 2026-09-03, Apache-2.0, pushed 2026-11-04. Full support for GHC 9.14.1, 9.12.4, 9.12.2, 9.10.3, 9.8.4 and 9.6.7. 9.12.3 and 9.12.1 unsupported. Everything older is deprecated with a last-supporting version listed. Source: https://haskell-language-server.readthedocs.io/en/latest/support/ghc-version-support.html . **Headless use works but is not a symbol exporter.** The binary can be run from the command line and loads a given file or all project files (troubleshooting page), but I found no command that dumps symbols. It is an LSP server and the useful route would be `textDocument/documentSymbol`, which is a daemon-shaped interaction. It loads the project through a cradle (cabal, stack, or ghc), so it runs build tools and, by the documentation, preprocessors, and typechecks Template Haskell. For multi-component stack projects the project must be built first.

**Other compiler indexes.**
- `jdeps` reads compiled `.class` files, JARs or directories and reports package, class or module dependencies, with DOT output. It lists dependencies only and extracts no symbol names, docs or lines, and it needs compiled classes. Source: https://docs.oracle.com/en/java/javase/21/docs/specs/man/jdeps.html . Its licence is the JDK's and I did not check it.
- The javac Tree API (`com.sun.source`) parses sources without compiling and exposes declarations. I did not read its documentation or test it, and annotation processing is a separate phase that a pure parse need not run.
- Glean (Meta) can read SCIP, and its Haskell indexer was an unmerged pull request at the time of the post above. Not pursued, since it needs folly and RocksDB.

**Safety on an untrusted clone (all of 2a to 2c that compile).** Producing a `.hie`, a scip-java index or an HLS session runs a build. For Haskell that means `cabal` or `stack` invocations, custom `Setup.hs`, preprocessors and Template Haskell splices, all arbitrary code. scip-java adds annotation processors, scip-typescript needs `npm install`, which can run install scripts. None should run on a clone before a person trusts it. Reading an index file that someone else produced is a separate question and is only a parser-safety matter.

## 3. Code-graph builders

### 3a. Kythe

**What.** A language-agnostic graph. Nodes (26 kinds, including anchor, file, function, record, variable) are identified by a five-part VName (language, corpus, root, path, signature) and edges include `defines/binding`, `ref`, `childof`, `extends`, `overrides`, `typed`. Reverse edges are built in post-processing. Source: https://kythe.io/docs/schema/

**Languages.** The repository says indexers exist for C++, Go and Java, and the schema page covers those plus protobuf and Lisp. No TypeScript, Python or Haskell indexer was found in the sources I read. Source: https://github.com/kythe/kythe

**How.** Extractors capture build actions (javac, Maven, cmake, Go, Bazel are listed) and indexers run over the captured compilation units, so **a build environment is required**. I inferred this from the extractor list. The page does not state it.

**Store.** The documentation I read does not describe serving storage.

**Licence and currency.** Apache-2.0. Latest release v0.0.76, 2026-07-16, pushed 2026-09-18.

**Verdict.** Heavy, a build-integrated pipeline, and none of our four languages is fully covered. Not a fit.

### 3b. GitHub stack graphs

Declarative name-resolution rules written per language in a Rust implementation over tree-sitter, to give precise navigation without a build. **The repository was archived on 2025-09-09 and is read-only and unsupported** (https://github.com/github/stack-graphs), last push 2025-09-09. Licence Apache-2.0 or MIT, at the user's choice. Which languages were supported, and the storage format, were not shown on the page I fetched. Not a basis for new work.

### 3c. CodeQL

Databases are built by extraction, which for Java is tied to the build (the supported-languages page lists compilers javac and ECJ and says builds that execute are analysed). Languages relevant here: Java 7 to 26, Python 2.7 and 3.5 to 3.14, JavaScript and TypeScript up to TypeScript 7.0. **Haskell is not supported.** Source: https://codeql.github.com/docs/codeql-overview/supported-languages-and-frameworks/ . CLI v2.27.4 on 2026-11-02. **Licence is restrictive.** The CLI terms authorise use on open-source code, research and demonstrations, and bar generating databases for automated analysis or CI on non-open-source code without a GitHub Advanced Security licence. They also prohibit redistribution and hosting as a service. So the CLI cannot be bundled or depended on by an MIT project and cannot be run on a user's private code. Source: https://github.com/github/codeql-cli-binaries/blob/main/LICENSE.md . The queries are separately licensed (MIT in the standard library repository, not checked). Not a fit.

## 4. Code embedding retrieval

**What.** Source is split into chunks (functions, files or windows), each is embedded, and a query is embedded and matched by nearest neighbour. This answers "which function retries a failed write" by meaning, not by identifier, which tag-based tools cannot do. It needs a tag or symbol layer to know what to chunk.

**Models checked** (Hugging Face API records, read 2026-11-04):
- `nomic-ai/CodeRankEmbed`, MIT, 136,731,648 parameters, last modified 2025-06-24. This licence allows redistribution and local use.
- `jinaai/jina-code-embeddings-0.5b`, **CC BY-NC 4.0**, about 494 million parameters, last modified 2025-10-02. Non-commercial, which conflicts with an MIT project shipping or defaulting to it.

I did not check voyage-code, OpenAI, Cohere, or Jina's older code model, nor a model's language coverage or benchmark scores. Hosted APIs fail the offline requirement.

**Coding assistants.** Cursor's documentation page I could reach describes only a local Instant Grep index and says Cursor does not store embeddings of the codebase for search or upload paths and code to build that index. That is narrower than my brief and I could not confirm how Cursor's semantic indexing works, where its vectors live or what is sent. Source: https://cursor.com/docs/context/codebase-indexing . Aider uses no embeddings (section 1). I did not survey Continue, Cody, Zed or Copilot.

**Store, offline, cost.** An embedded vector store such as sqlite-vec or LanceDB, the shape temporal_reasoning's roadmap names too, keeps this daemon-free. A local model runs offline. No cost figures were found. Вивід already embeds OWL term nodes, so this stage reuses that machinery once tag extraction yields term-like records.

## 5. Agent memory: `temporal_reasoning` (project-minigraf)

**What.** An MIT-licensed bi-temporal Datalog memory for coding agents, built on the `minigraf` engine through its Python binding (minigraf 2.0.11 on PyPI, 2026-10-26, MIT OR Apache-2.0). Hand-written entity types are decision, preference, constraint and dependency. Git ingestion adds module, function, class, variable, field, commit and ingestion, eleven in total. A sidecar SQLite FTS5 file holds a full-text fact index. Sources: https://github.com/project-minigraf/temporal_reasoning and its ROADMAP.md.

**Git ingestion.** Releases: `temporal-reasoning` 0.9.0 on PyPI (2026-10-02, MIT, Python 3.10 or later), repository push 2026-10-25. The design spec describes: `git log --reverse` from a watermark, `git diff-tree` per commit for changed files, and tree-sitter parsing of only the changed files by file extension, extracting functions and classes with file path, imports as `:depends-on` edges and call expressions as best-effort `:calls` edges. Writes carry the commit time as valid-time. Idents are slugged as `:function/<path>-<name>`. So it does not extract doc comments or signatures, and the spec text I read records only name and file path. Source: https://raw.githubusercontent.com/project-minigraf/temporal_reasoning/master/docs/superpowers/specs/2026-05-26-phase5-git-ingestion-design.md

**Languages.** The extension table in the spec shows Python, JavaScript, TypeScript, TSX, Rust, Go, Java, C, C++, C#, Ruby and PHP, then an ellipsis. **Haskell is not in the visible part and I did not read the implementation.** Grammars come from the `tree-sitter-languages` package (the spec's choice, which may have changed).

**Cost and maturity.** The latest recorded at-scale run ingested 847 commits in 1526 s on minigraf 2.0.0 (the roadmap says 2026-09-02 and the numbers live in `evals/at_scale/benchmark.md`, which I did not read). The roadmap states plainly that production viability at the 52,948-commit scale that motivated the hardening is not re-validated. Install is `uvx temporal-reasoning[git-ingestion]` or a cloned installer. Without the `git-ingestion` extra extraction silently does nothing. Offline for default extraction, with an optional LLM strategy needing API keys.

**Single-store check.** It keeps one `memory.graph` file plus an FTS sqlite file, and only one handle may be open per process, so it is embedded and daemon-free for the CLI path, though the MCP server holds the handle while it runs.

**Safety.** The spec describes reading blobs through git commands and parsing with tree-sitter, not checking out or building, so I would expect it to be safe on a hostile clone. I did not audit the implementation, including whether git hooks, filters or `.gitattributes` in the clone can run (a clone's `core.fsmonitor` or `diff` drivers are configurable by repository config, so run git with a clean config).

**Fit.** Its entity set and idents show the shape Вивід needs (module, function, class, with a path and a name) but it holds no comments and its Haskell coverage is unconfirmed. Its commit-time modelling answers a question Вивід has not asked.

## Summary table

| Approach | Extracts | How | Store | Languages (Hs, Java, Py, TS) | Licence | Needs compile | Offline | Install | Cost found | Maintained (latest) |
|---|---|---|---|---|---|---|---|---|---|---|
| tree-sitter `tags.scm` | definitions and references with kind, name, line, optional doc | parse and query, name-matching only | none, stdout or in memory | Hs no `tags.scm` (highlights, injections, locals only). Java, Py, TS yes | MIT | no | yes | `cargo` or npm, plus grammars | none published | yes, 0.27.1, 2026-10-08. tree-sitter-haskell 0.24.1, 2026-09-30 |
| GitHub code navigation | same, search-based | tree-sitter | GitHub-side | Hs no. Java, Py, TS yes | service | no | no (hosted) | none | n/a | service |
| Aider repo map | tags ranked by PageRank into a token budget | tags queries plus networkx | `diskcache` in project | Hs yes (3-line query). Java, Py, TS yes | Apache-2.0 | no | yes | `pip` | none | yes, push 2026-05-22 (release 0.86.2, 2026-02-12) |
| SCIP | symbols, occurrences, docs, relationships, references resolved | compiler or type-checker backed indexers | one protobuf file | Hs no official (community scip-haskell stale). Java, Py, TS yes | Apache-2.0 (scip-python MIT) | yes (Java via build, TS needs installed deps) | yes | per-language CLI or build plugin | none found | yes, scip 0.10.0 2026-09-03, scip-java 0.14.0 2026-11-04, scip-typescript 0.6.1 2026-11-03 |
| LSIF | LSP results graph | language server dump | JSON | per server | MIT spec (not checked) | depends | yes | per server | none | superseded by SCIP, unconfirmed from spec |
| universal-ctags | tags (name, kind, line, scope) | own parsers | tags file or JSON | Hs yes (limited), Java, Py, TS yes | GPL-2.0 | no | yes | package manager | none | yes, 6.2.1 2025-10-25, push 2026-11-03 |
| GHC `.hie` plus HieDb | resolved names, types, scopes, source bytes | GHC writes during compile, hiedb indexes | SQLite | Hs only | BSD-3-Clause (hiedb) | yes, by GHC | yes | `cabal install hiedb`, GHC | 1021 s and 5.2 GB for all Hackage under GHC 9.4.7 | yes, hiedb 0.8.0.0 2026-01-21, push 2026-08-05 |
| HLS | LSP answers | cradle loads project, GHC typechecks | none (server memory) | Hs only | Apache-2.0 | yes | yes | ghcup | none | yes, 2.15.0.0, 2026-09-03 |
| jdeps | dependencies between class files | reads bytecode | stdout, DOT | Java only | JDK licence, not checked | yes (class files) | yes | in JDK | none | with JDK |
| Kythe | semantic graph | build extractors then indexers | not confirmed | C++, Go, Java (TS, Py, Hs none found) | Apache-2.0 | yes | yes | build from source | none | yes, v0.0.76, 2026-07-16 |
| GitHub stack graphs | precise name resolution via declarative rules | tree-sitter plus rules | not confirmed | not confirmed | Apache-2.0 or MIT | no | yes | Rust crates | none | archived 2025-09-09 |
| CodeQL | relational database of code | build-integrated extraction | CodeQL database | Hs no. Java, Py, TS yes | restrictive CLI terms, no redistribution | yes (Java) | yes | CLI download | none | yes, v2.27.4, 2026-11-02 |
| Code embeddings | vector per chunk | embed chunks and queries | vector store (sqlite-vec, LanceDB) | any | model-specific (CodeRankEmbed MIT, jina-code-embeddings-0.5b CC BY-NC 4.0) | no | yes with a local model | model download | none found | CodeRankEmbed last modified 2025-06-24 |
| temporal_reasoning git ingestion | module, function, class, import and call edges per commit | git plumbing plus tree-sitter on changed files | minigraf file plus FTS5 sqlite | Hs not confirmed. Java, Py, TS yes | MIT | no | yes by default | `uvx temporal-reasoning[git-ingestion]` | 847 commits in 1526 s | yes, 0.9.0 2026-10-02, push 2026-10-25 |

## Not confirmed

- Whether any maintained, working Haskell indexer produces SCIP. Only a 2024 community converter was found and I did not run or read its code.
- A mapping from `.hie` `hieVersion` to GHC releases. I only confirmed the header carries both values and the reader rejects mismatches.
- Whether `hiedb`'s `defs` table stores doc comments or end positions. Reading a `.hie` file directly with the GHC API gives the source bytes, so docs could be recovered from there.
- Whether HLS has any batch symbol dump. I found only LSP and the load-and-check CLI.
- Whether tree-sitter-haskell's `queries/` directory on GitHub master contains a `tags.scm` newer than the 0.24.1 crate.
- Haskell support in temporal_reasoning, and whether its implementation matches its design spec, including how it invokes git.
- The LSIF specification's own statement on SCIP. Kythe's storage format, and whether it needs a build (inferred). Stack graphs' language list and storage format.
- Whether the `scip-java` 0.14.0 line is published to Maven Central. Whether scip-python needs installed packages.
- The ctags `.ctags.d` search being relative to the current directory, and whether any ctags option executes external commands.
- The licence of `jdeps` as a standalone tool, of the Tree API, and of the CodeQL query packs.
- How Cursor, Continue, Cody, Zed or Copilot build embedding indexes, which embedding models beat CodeRankEmbed on Haskell, and any cost per chunk.
- Licence of the queries in `Goldziher/tree-sitter-language-pack`.
- The numbers in temporal_reasoning's `evals/at_scale/benchmark.md`.
