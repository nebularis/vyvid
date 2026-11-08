<!-- SPDX-License-Identifier: MIT -->

# Plan: one project reading another's knowledge

**Status:** building 2026-11-08. RD-1 picked up at the maintainer's request, with the design questions below answered the same day. Revised the same day to carry skills and recipes by name under review, and to run an extension domain's extractors over a read.
**Prefix:** RD
**Sketch:** [code intelligence](../sketches/code-intelligence.md), VYD-Q32, answered 2026-11-04 as "a project may name other projects it reads, for their knowledge". This plan builds it.

## Scope

A project that is downstream of another needs the other's index beside its own. A private project can build on a public one such as LATTICE, and an agent in it should find LATTICE's decisions, mechanisms and standards by the same `find`. Today the only way is `--scope`, which is per question, and which names a configured scope without saying where it stands.

A project declares what it reads in its `vyvid.toml`:

```toml
[project.reads.lattice]
commit = "<full commit>"
skills = ["architecture"]
recipes = ["sparql-for-studio"]
```

What is read is a snapshot of that commit, not a checkout, so the index is reproducible and a change of pin is a visible, deliberate rebuild. Knowledge comes by default. A skill or a recipe comes only when named in the allow-list and when a person has reviewed the read at the pinned commit.

**Review.** The standing of a read is `knowledge` or `reviewed`, as a domain's is. A person records it in their own configuration, in the project's entry as `reviewed_reads`, with `vyd reads review <name>`, which needs a terminal and refuses a commit other than the pin. A new pin lapses the standing until it is reviewed again.

**Out of scope.** Rules, a contract and hooks of the read project, which are never carried. Transitive reads, since a read project's own domains and reads are not pulled in. Command extractors of a read project, which never run. The quanta of a read project are indexed by an extension domain that the reader also uses, planned apart in LATTICE.

## Principles

| # | Principle |
|---|---|
| RD-P1 | A read project gives knowledge. Skills and recipes come only by name in the reader's allow-list and only once a person has reviewed the read at its pin. Rules, a contract and hooks never reach the reader |
| RD-P2 | The reader's entries win. The stack runs general, domains, the read project, then the reader. An entry of the reader overrides one of the read project only where it says `Overrides` or `Specialises`, as across any two scopes |
| RD-P3 | A pin is a full commit, and a change to it, a different snapshot or a snapshot whose tree does not match its record makes the index stale |
| RD-P4 | A public project never reads a private one, by declaration, by `--scope` or by a cycle. The refusal is hard, in configuration loading and in `--scope`, and costs no graph work |
| RD-P5 | No transitive reads. What a read project uses is declared again by the reader if the reader wants it |
| RD-P6 | The code that runs over a read is only ever the reader's own and trusted: `vyd`'s built-in extractors, and the extractors of a domain the reader uses. No command of the read project runs |

## Slices

Estimates are in tokens, for agent work.

| Slice | Content | Depends on | Estimate |
|---|---|---|---|
| RD-1 | the configuration: `reads` with its allow-lists parsed, validated and shown by `vyd config` and `vyd context`, the review record, and the visibility guard in loading and in `--scope`, tests first | | 140k |
| RD-2 | the snapshot: `git archive` of the pinned commit from the source checkout into a cache keyed by the commit, with a tree record, and the read scope built from the snapshot's own `vyvid.toml` cut down to knowledge | RD-1 | 120k |
| RD-3 | the stack and the index: the read scope in the stack under RD-P2, `built-for` naming `name@commit`, allow-listed recipes and skills under review, the `(drop)` marker, and a domain's extractors over a read | RD-2 | 180k |
| RD-4 | `vyd reads status`, `pin` and `review`, the drift report, the pin that resolves a ref to a full commit reachable from the default branch, and the review that records a commit | RD-2 | 100k |
| RD-5 | the guide section, the sketch note closing VYD-Q32, and the release | RD-3, RD-4 | 60k |

## Where each piece lives

| Piece | Place |
|---|---|
| the `reads` key, its parsing, the review record and the guard | `config.py`, and `ask.py` for `--scope` |
| the snapshot and its tree record | a new `reads.py`, with `git archive` |
| the stack with read scopes | `resolve.py`, kept apart from `layers()` so rules are unchanged |
| the pin and the drift report | `cli.py`, as `vyd reads` |

## Questions RD-Q1 to RD-Q5

Answered 2026-11-08, by the maintainer.

**RD-Q1. What is the pin?** Answered 2026-11-08, a full commit. A tag or branch is accepted only as input to `vyd reads pin`, which resolves it and refuses a commit not reachable from the source's default branch.

**RD-Q2. Do command extractors of a read project run?** Answered 2026-11-08, never. What indexes a read project's derived knowledge, such as its architectural quanta, is an extension domain the reader also uses, whose extractors run over the read (RD-P6). The first answer, not in version one with an opt-in as BL-5, was revised the same day.

**RD-Q3. What does the visibility guard cover?** Answered 2026-11-08, project scopes only. A domain named by `--scope` behaves as it does today.

**RD-Q4. Is a public project reading a private one refused?** Answered 2026-11-08, yes, hard.

**RD-Q5. Are recipes and skills shared?** Answered 2026-11-08, by name in an allow-list, and only under review at the pin. This took in BL-6. A skill is composed under the read's own prefix and the reader changes it with additions, as for a domain's, which gain a `(drop)` marker that removes a section.

## Validation

`mise run check:tests` and `mise run check:writing`. The tests are written before the code in each slice.
