<!-- SPDX-License-Identifier: MIT -->

# Вивід · vyvid

**Вивід** (*vyvid*, said VY-vid) is Ukrainian for an inference, the noun of *виведи*, "derive it". In logic, *логічний вивід* is logical inference. The tool is `vyvid`, and its command is `vyd`.

Вивід gives a coding agent what it needs to know before it acts: the decisions, rules, findings and open questions of the projects it works on, and of the subjects those projects share, ranked by meaning and scoped to the folder the agent is in. It answers from what the team has written down and reviewed, which is more current than anything the agent remembers.

## The name

The name was drawn from five Ukrainian phrases. Each names a way of reasoning, and each corresponds to something the tool does.

| Phrase | Transliterated | In English | The reasoning | What Вивід does |
|---|---|---|---|---|
| Виведи це | *Vyvedy tse* | Derive it | deduction | `vyd find` derives, from the registers, the rule that applies to the task at hand |
| Зроби з цього висновок | *Zroby z tsoho vysnovok* | Draw a conclusion from this | conclusion | decisions are entries, each with the decisions that reversed or narrowed it beside it |
| Припусти це | *Prypusty tse* | Suppose it | abduction | the questions a plan raises are entries, open until answered, so what was supposed and not yet settled is found too |
| Додумайся до цього | *Dodumaisia do tsoho* | Figure it out | working it through | recipes chain queries until the answer is specific to the work |
| Зрозумій це з контексту | *Zrozumii tse z kontekstu* | Understand it from context | inference from context | `vyd context` reads the folder an agent is in and resolves which rules apply there, the project's last |

The Cyrillic name is the tool's label. The repository, the package, the command and every identifier in the code use the Latin form, transliterated by Ukraine's official system of 2010, so nothing depends on a terminal or a filesystem that can show Cyrillic.

## What it is

- **Registers** are Markdown tables whose header is their schema: rules, findings, decisions, debts, questions, notes about a tool. They are the source of truth, reviewed in git.
- **Facets** are closed sets of values, held as SKOS schemes, that tag every entry across as many dimensions as a subject needs, such as the activity, the quality at stake and the technology.
- **Domains** group the facets, registers, skills and query recipes of a subject, such as OWL ontologies, triple stores, Haskell or the tools a developer uses. Domains form a directed graph, and a domain can live in a project, in a shared knowledge base, or in a repository of its own.
- **Projects** are codebases with a contract of their own. A project uses domains and specialises them, so the same question asked in a project's folder gets the project's answer first, with the domain's beneath it.
- **The index** is derived from all of these, never committed, and ranks entries by meaning with a local embedding model. A rule at a narrower scope overrides one at a wider scope, the project's last.

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
```

A managed domain is a domain whose folder lies under the knowledge base, and it is a git clone of its `remote`. Its `git` policy sets when it is pulled (`on-start`, `daily` or `manual`), and whether a recorded change is committed and pushed (`auto`) or left staged (`manual`), and `commit_trailers` in `[framework]` are added to every commit `vyd kb record` makes. A pull never merges or stashes, and `vyd context` pulls what is due before it answers unless given `--no-pull`. A project's own files are never committed or pushed by `vyd`.

The configuration is read from `$VYVID_CONFIG`, or from the platform's configuration folder, which `vyd config` prints. [`examples/config.toml`](examples/config.toml) is a starting point.

## Licence

[MIT](LICENSE)
