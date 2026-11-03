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

## Status

Design. Nothing is built yet. The [sketch](docs/developer/sketches/vyvid-framework.md) sets out the model and its decisions, the [plan](docs/developer/plans/vyvid-framework.md) its slices, and the [status record](docs/developer/status/vyvid-framework.md) where each slice is.

## Layout

| Path | Holds |
|---|---|
| `docs/developer/` | the working documents: sketches, plans, status records, and the registers, laid out as in LATTICE ([its README](docs/developer/README.md)) |
| `docs/architecture/decisions/` | the decisions, `ADR-nnn`, listed in [the catalogue](docs/architecture/decisions/README.md) |
| `mise.toml` | the only task entry point |

The code arrives with slice VYD-1, and with VYD-11 this repository is worked under a contract that Вивід itself resolves.

## Licence

MIT, as [LICENSE](LICENSE) states. AI-assisted contributions are disclosed in their commit trailers.
