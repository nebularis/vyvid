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
vyd config                             # where the configuration is read from, and whether it is sound
vyd context ~/work/lattice             # the layers of rules that apply there, the project's last
vyd resolve TSD-41 --in ~/work/lattice # the canonical scope:LOCAL an identifier names
vyd kb status                          # each managed domain: clone, branch, ahead and behind, changes, last pull, policy
vyd kb clone [domain ...]              # clone the named domains, or every managed one whose folder is missing
vyd kb pull [domain ...] [--due]       # fast-forward pull, only the domains whose policy says one is due with --due
vyd kb record <path> ... -m <message>  # stage changed register files, then commit and push as the domain's policy says
vyd check citations [--staged] [paths ...] # refuse lines a public project adds that cite an entry of a private scope
vyd recipe list [--in folder]          # the recipes of the folder's stack, with when to use each
vyd recipe run <name> "<question>" [--in folder] [--all] [--json] # run a recipe and print its briefing, within its budget unless --all
vyd recipe run <name> "<question>" --stop-at-glue # stop at each glue step and print its command for your client to run, then vyd recipe run --resume <state> --glue-output <file>
vyd store prune [--dry-run]            # remove the index stores of linked git worktrees that no longer exist
vyd install --client claude-code [--target folder] [--dry-run] # write the user-level rule file and one skill per domain
vyd domain audit <folder> [--json]     # list the links, files, paths, hidden text and commands in a domain you did not write, running nothing from it
```

A project can bring its own extractor as a command, in any language, so each git worktree indexes with its own version and nothing is installed into Вивід. Only your own configuration declares one.

```toml
[[projects.extractors]]
kind = "my-extractor"
command = ["mise", "exec", "--", "python", "-m", "tools.my_extractor"]
paths = ["docs:notes/*.md"]   # the files it reads, which decide when the index is stale
code = ["code:tools/my_extractor.py"]   # its own files, which also decide when the index is stale
```

It runs in the checkout's root with a minimal environment, `seconds` (default 300) as its time limit and the variables `env` names. It reads one JSON request on standard input, with its settings, the expanded `paths`, an output folder and the two graph IRIs it may write to. It writes `quads.nq` (N-Quads in those graphs) and `result.json` (problems, findings, texts to embed, prefixes, counts and an optional version) into the output folder. A failure is reported and costs only its own entries.

A managed domain is a domain whose folder lies under the knowledge base, and it is a git clone of its `remote`. Its `git` policy sets when it is pulled (`on-start`, `daily` or `manual`), and whether a recorded change is committed and pushed (`auto`) or left staged (`manual`), and `commit_trailers` in `[framework]` are added to every commit `vyd kb record` makes. A pull never merges or stashes, and `vyd context` pulls what is due before it answers unless given `--no-pull`. A project's own files are never committed or pushed by `vyd`. `vyd kb record` stages nothing in a domain whose files hold what looks like a credential, using `gitleaks` as well when it is installed, which is optional.

`vyd` writes the questions it is asked and cannot answer to logs beside the index, which `misses` and `gap` read. Set `logs = false` in `[framework]` to write none.

The configuration is read from `$VYVID_CONFIG`, or from the platform's configuration folder, which `vyd config` prints. [`examples/config.toml`](examples/config.toml) is a starting point.

## Licence

[MIT](LICENSE)
