<!-- SPDX-License-Identifier: MIT -->

# Вивід · vyvid

**Вивід** (*vyvid*) is Ukrainian that can refer to inference, as in *виведи*, "derive it". The command line tool this project packages is `vyd`.

Вивід provides a simple framework for giving AI agents contextualised information from which to make decisions, set rules, record and recall findings and questions related to the projects it works on, and of the subjects those projects share, ranked by meaning and scoped to the folder the agent is in. Its indexes and embeddings are built from markdown sources, making it a type of spec-driven development toolkit.

## Components

- **Registers** are Markdown tables whose header is their schema: rules, findings, decisions, tech debt, questions, notes about a tool, etc. They are the source of truth, held and reviewed in git.
- **Facets** are closed sets of values, held as SKOS schemes, that tag every entry across as many dimensions as a subject needs, such as the activity, the quality at stake, and the technology.
- **Domains** group all the facets, registers, skills, and query recipes of a subject. Subjects are as diverse as a user may wish, e.g., OWL ontologies, triple stores, Haskell development, or tools a developer uses. Domains form a directed graph, and a domain can live in a project, in a shared knowledge base, or in a repository of its own.
- **Projects** are codebases with a contract of their own. A project uses domains and specialises them, so the same question asked in a project's folder gets the project's answer first, with the domain's beneath it.
- **The index** is derived from all of these on demand. It ranks entries by meaning with a local embedding model. Rules at a narrower scope override those at a wider scope. 

Вивід grew out of the knowledge index of [LATTICE](https://github.com/nebularis/lattice), which is its first project.

## Layout

| Path | Holds |
|---|---|
| `docs/developer/` | how Вивід is designed and built, for its developers |
| `docs/architecture/decisions/` | the decisions, `ADR-nnn`, listed in [the catalogue](docs/architecture/decisions/README.md) |
| `src/vyvid/` | the package: `config.py` the configuration, `resolve.py` binding, layers and identifiers, `cli.py` the `vyd` command |
| `tests/` | the test suite, `mise run check` |
| `examples/config.toml` | an example configuration with LATTICE and this repository as projects |
| `mise.toml` | the only task entry point |


## Using it

```bash
mise run install                       # uv tool install --editable, so vyd runs this working tree
vyd config [folder]                    # where the configuration is read from, whether it is sound, and the folder's own vyvid.toml
vyd context ~/work/lattice             # the layers of rules that apply there, the project's last
vyd resolve TSD-41 --in ~/work/lattice # the canonical scope:LOCAL an identifier names
vyd kb status                          # each managed domain: clone, branch, ahead and behind, changes, last pull, policy
vyd kb clone [domain ...]              # clone the named domains, or every managed one whose folder is missing
vyd kb pull [domain ...] [--due]       # fast-forward pull, only the domains whose policy says one is due with --due
vyd kb record <path> ... -m <message>  # stage changed register files, then commit and push as the domain's policy says
vyd check citations [--staged] [paths ...] # refuse lines a public project adds that cite an entry of a private scope
vyd check identifiers [--json] [--all] [folder] # fail on an identifier the tracked Markdown mentions and nothing defines, or one a family defines twice
vyd recipe list [--in folder]          # the recipes of the folder's stack, with when to use each
vyd recipe run <name> "<question>" [--in folder] [--all] [--json] # run a recipe and print its briefing, within its budget unless --all
vyd recipe run <name> "<question>" --stop-at-glue # stop at each glue step and print its command for your client to run, then vyd recipe run --resume <state> --glue-output <file>
vyd kb accept <domain>                 # a person fast-forwards a domain whose pull was held, after reading what changed
vyd trust [path]                       # a person trusts a configuration outside their own folder, or this repository's vyvid.toml, by its hash, so its glue and command extractors run
vyd store prune [--dry-run]            # remove the index stores of linked git worktrees that no longer exist
vyd install --client claude-code [--target folder] [--dry-run] # write the user-level rule file and one skill per domain
vyd domain new <name> [--registers <type>] [--path <folder>] # write a new domain folder with a manifest, a facet stub, an empty register and a skill stub, and print the lines to add to your configuration, which it does not change
vyd domain audit <folder> [--json] [--allow <scope>] # list the links, files, paths, hidden text, commands and qualified mentions of other scopes in a domain you did not write, running nothing from it
vyd find <words> --kind symbol [--in folder] # the project's functions, types and classes ranked by meaning, from source parsed apart from the graph. Needs vyvid[symbols]
vyd read <package:Module.name>         # the source lines of a symbol, read inside the repository
vyd handoff <name> [--module M] [--unit U] [--in folder] # the exact commands for the compiler index a project registers, printed and never run
vyd move check [--ref <git ref>] [--json] [folder] # compare what the project moved to a domain, as it stood at the move's commit, with the source at a ref, by identifier. Exits 1 on a difference
```

A domain gives knowledge alone unless its entry in your configuration says `trust = "own"`, or `trust = "reviewed"` with the `commit` you reviewed. A domain with a remote is knowledge by default and one with none is your own. A knowledge domain installs no rules or skills, its results are labelled as data, and a pull that changes its rules, skills or manifest is held until you run `vyd kb accept`. A configuration at a path other than your own, such as one named by `VYVID_CONFIG`, runs no glue and no command extractor until you run `vyd trust` in a terminal, and again after it changes.

A project specialises a domain by keeping a register of the domain's register type in its own documents, such as a `note` register for the Tools domain, and by naming the domain's row in a row's `Specialises` column, qualified with the domain, as `tools:NOTE-1`. In a folder of the project `vyd find` ranks the project's row above the domain's and shows the domain's beneath it, and a row the project `Overrides` is shown only when its scope is named. A `vyvid.toml` that names a domain you have not configured does not set its project aside. `vyd context` and `vyd build` print a note, the domain is left out of the stack for that run, and a `Specialises` cell naming it stays unresolved. A project entry in your own configuration that names an unknown domain is still an error.

A repository can declare its own project, with no entry in your configuration, in a `vyvid.toml` at its root. It holds what a `[[projects]]` entry holds, under `[project]`, and the repository's folder is the project's code folder.

```toml
[project]
name = "vyvid"
visibility = "public"
docs = "code:docs"
contract = "docs:contract.md"
register_types = ["docs:register-types.toml"]

[project.families]
STD = { defined = "docs:standards.md", type = "standard" }
```

The file is found at the git toplevel of a folder, or above it where the folder is not in git, and every checkout of the repository reads its own copy. It binds the folders inside it ahead of a remote, and a configured project that holds the folder more deeply still wins. An entry of the same name in your configuration overrides the file's keys one by one. It comes from whoever wrote the repository, so it may not set `code`, `git`, `remote`, `trust` or `match`, and every path it names must stay inside the repository, even through a link. A file that breaks this sets aside its project and gives the folder the general scope, and `vyd config` lists why. Until you run `vyd trust` in the repository, the project gives knowledge alone, as a knowledge domain does: its contract and skills are withheld, its entries are labelled as data and none of its glue or command extractors runs. To work on this repository, run `vyd trust` there, then `vyd context .` prints its contract.

A project that gave a family, or some rows of one, to a domain declares it with `[[projects.moves]]` in your configuration (see `examples/config.toml`). Its mentions then resolve through the domain with no rewriting of its text, `vyd resolve` prints the canonical target, and the project's copies leave the index. A domain may cite itself, its ancestors and the general scope alone, and a build reports a domain that cites a project or any other domain.

`vyd check identifiers` reads the Markdown that `git ls-files` lists in the project's repository, never a folder walk, so an ignored folder is not read. A mention resolves on a normalised key, so another spelling of a defined identifier is a variant and is reported. A family with `removable = true` has its unresolved mentions reported and never failed. A family's `exceptions` file, or `identifiers.exceptions` for the project, lists identifiers mentioned and defined nowhere, one per line with a reason after `#`, and an entry nothing needs any longer is reported as stale. An identifier a family defines twice fails, and the line committed earlier keeps the number. A mention covered by a move resolves only if the domain defines it. A family with `defined_only = true` reads a bare match of its pattern as a mention only where its source defines the identifier, so a loose pattern does not read `UTF-8` as an entry. The exit code is 1 on an unresolved or twice-defined identifier and 0 otherwise, and `--json` prints everything found.

A register type declared with `shown = "asked"` is left out of `find` unless `--kind` names it or the question names an entry by its identifier, as declared terms are. The packaged `slice` type is one, and reads a board of `Slice`, `Deliverable`, `State` and `Blocked on`.

## Code

A project asks for its source to be searched by declaring what to parse, in its entry or its `vyvid.toml`. The grammars are the optional extra `vyvid[symbols]` (`uv tool install "vyvid[symbols]"`), and without it `vyd` goes on and says so.

```toml
[[project.symbols]]
language = "haskell"   # python, haskell, java or typescript
paths = ["code:packages/*/src/**/*.hs"]
```

`vyd build` parses the files `git ls-files` lists, and only those whose content changed since the last build, into `symbols.sqlite` beside the index. Nothing in the clone runs, so symbols work before a `vyvid.toml` is trusted, and a symbol of an untrusted project is labelled as data like any other entry. No symbol enters the graph. `vyd find <words> --kind symbol` ranks every symbol by meaning, with a name written as camelCase or snake_case in the question first, and prints the identifier `package:Module.name`, its kind, module and `file:line`, with the signature and the first line of the doc beneath. Plain `find` shows no symbol and says in one line when some match strongly. A text may name a symbol by its identifier, and `vyd check identifiers` reports one that no longer exists without failing.

Who calls a name is a question for a compiler's index, which Вивід does not build or run. A project registers the one it has, and `vyd handoff` prints the exact commands to ask it, after checking that its database exists and holds rows.

```toml
[[project.code_index]]
kind = "hiedb"                       # the only kind with commands so far
database = "code:.build/hie.db"
built_by = "mise run build:index"    # shown as text, and withheld until the vyvid.toml is trusted
sources = "code:packages/*/src"      # newer than the database means it may be stale
```

`vyd context` lists each registered index. The commands come from templates in Вивід, and the file supplies only a quoted path.

A project can bring its own extractor as a command, in any language, so each git worktree indexes with its own version and nothing is installed into Вивід. Only a project's entry in your own configuration, or a `vyvid.toml` you have trusted, declares one.

```toml
[[projects.extractors]]
kind = "my-extractor"
command = ["mise", "exec", "--", "python", "-m", "tools.my_extractor"]
paths = ["docs:notes/*.md"]   # the files it reads, which decide when the index is stale
code = ["code:tools/my_extractor.py"]   # its own files, which also decide when the index is stale
```

It runs in the checkout's root with a minimal environment, `seconds` (default 300) as its time limit and the variables `env` names. It reads one JSON request on standard input, with its settings, the expanded `paths`, an output folder and the two graph IRIs it may write to. It writes `quads.nq` (N-Quads in those graphs) and `result.json` (problems, findings, texts to embed, prefixes, counts, units and an optional version). `units` maps a name to the units it stands for, and an `Owner` or `Provided by` cell that names one becomes an edge to each, while a name no extractor declared is reported and kept as written into the output folder. A failure is reported and costs only its own entries.

A managed domain is a domain whose folder lies under the knowledge base, and it is a git clone of its `remote`. Its `git` policy sets when it is pulled (`on-start`, `daily` or `manual`), and whether a recorded change is committed and pushed (`auto`) or left staged (`manual`), and `commit_trailers` in `[framework]` are added to every commit `vyd kb record` makes. A pull never merges or stashes, and `vyd context` pulls what is due before it answers unless given `--no-pull`. A project's own files are never committed or pushed by `vyd`. `vyd kb record` stages nothing in a domain whose files hold what looks like a credential, using `gitleaks` as well when it is installed, which is optional.

`vyd` writes the questions it is asked and cannot answer to logs beside the index, which `misses` and `gap` read. Set `logs = false` in `[framework]` to write none.

The configuration is read from `$VYVID_CONFIG`, or from the platform's configuration folder, which `vyd config` prints. [`examples/config.toml`](examples/config.toml) is a starting point.

## Licence

[MIT](LICENSE)
