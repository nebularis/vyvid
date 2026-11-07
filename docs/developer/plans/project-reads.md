<!-- SPDX-License-Identifier: MIT -->

# Plan: one project reading another's knowledge

**Status:** building 2026-11-08. RD-1 picked up at the maintainer's request, with the design questions below answered the same day.
**Prefix:** RD
**Sketch:** [code intelligence](../sketches/code-intelligence.md), VYD-Q32, answered 2026-11-04 as "a project may name other projects it reads, for their knowledge". This plan builds it.

## Scope

A project that is downstream of another needs the other's index beside its own. MERIDIAN is private and builds on LATTICE, which is public, and an agent in MERIDIAN should find LATTICE's decisions, mechanisms and standards by the same `find`. Today the only way is `--scope`, which is per question, and which names a configured scope without saying where it stands.

A project declares what it reads in its `vyvid.toml`:

```toml
[project.reads.lattice]
commit = "<full commit>"
```

What is read is a snapshot of that commit, not a checkout, so the index is reproducible and a change of pin is a visible, deliberate rebuild.

**Out of scope.** Rules, skills, recipes, a contract and hooks of the read project, which are never inherited. Transitive reads, since a read project's own domains and reads are not pulled in. Command extractors of a read project, which do not run in version one (backlog BL-5). Sharing a read project's recipes (BL-6).

## Principles

| # | Principle |
|---|---|
| RD-P1 | A read project gives knowledge and nothing else. Its rules, skills, recipes, contract and hooks never reach the reader |
| RD-P2 | The reader's entries win. The stack runs general, domains, the read project, then the reader. An entry of the reader overrides one of the read project only where it says `Overrides` or `Specialises`, as across any two scopes |
| RD-P3 | A pin is a full commit, and a change to it, a different snapshot or a snapshot whose tree does not match its record makes the index stale |
| RD-P4 | A public project never reads a private one, by declaration, by `--scope` or by a cycle. The refusal is hard, in configuration loading and in `--scope`, and costs no graph work |
| RD-P5 | No transitive reads. What a read project uses is declared again by the reader if the reader wants it |
| RD-P6 | No command extractor of a read project runs. The built-in extractors, which are `vyd`'s own code, do |

## Slices

Estimates are in tokens, for agent work.

| Slice | Content | Depends on | Estimate |
|---|---|---|---|
| RD-1 | the configuration: `reads` parsed, validated and shown by `vyd config` and `vyd context`, with the visibility guard in loading and in `--scope`, tests first | | 120k |
| RD-2 | the snapshot: `git archive` of the pinned commit from the source checkout into a cache keyed by the commit, with a tree record, rebased as the read project's code and docs | RD-1 | 120k |
| RD-3 | the stack and the index: the read scope in the stack under RD-P2, its graphs built and queried, `built-for` naming `name@commit`, no rules, no recipes, no command extractors | RD-2 | 140k |
| RD-4 | `vyd reads status` and `vyd reads pin`, the drift report and the pin that resolves a ref to a full commit reachable from the default branch | RD-2 | 80k |
| RD-5 | the guide section, the sketch note closing VYD-Q32, and the release | RD-3, RD-4 | 60k |

## Where each piece lives

| Piece | Place |
|---|---|
| the `reads` key, its parsing and the guard | `config.py`, and `ask.py` for `--scope` |
| the snapshot and its tree record | a new `reads.py`, with `git archive` |
| the stack with read scopes | `resolve.py`, kept apart from `layers()` so rules are unchanged |
| the pin and the drift report | `cli.py`, as `vyd reads` |

## Questions RD-Q1 to RD-Q5

Answered 2026-11-08, by the maintainer.

**RD-Q1. What is the pin?** Answered 2026-11-08, a full commit. A tag or branch is accepted only as input to `vyd reads pin`, which resolves it and refuses a commit not reachable from the source's default branch.

**RD-Q2. Do command extractors of a read project run?** Answered 2026-11-08, not in version one. The opt-in is BL-5.

**RD-Q3. What does the visibility guard cover?** Answered 2026-11-08, project scopes only. A domain named by `--scope` behaves as it does today.

**RD-Q4. Is a public project reading a private one refused?** Answered 2026-11-08, yes, hard.

**RD-Q5. Are recipes shared?** Answered 2026-11-08, not in version one. The opt-in is BL-6.

## Validation

`mise run check:tests` and `mise run check:writing`. The tests are written before the code in each slice.
