<!-- SPDX-License-Identifier: MIT -->

# Working documents

How Вивід is designed, planned and tracked. The layout follows LATTICE's `docs/developer/`, so the framework can index this repository as it indexes LATTICE, which is what slice VYD-11 makes true.

## Kinds of document

| Path | Holds | A unit's |
|---|---|---|
| `sketches/` | a design worked through before it is planned: the problem, measurements, options with their costs, and questions for the maintainer | why |
| `plans/` | a unit's scope, decisions and slices, each slice with what done looks like | what |
| `status/` | a unit's live state: its Status line and its slice board | where it is |
| [`INDEX.md`](INDEX.md) | every unit and every slice, one row each | all of the above at a glance |
| `../architecture/decisions/` | the decisions, `ADR-nnn` | what was decided |

## Registers

A register is a Markdown table whose header is its schema. Its rows are the source of truth, and the index is derived from them and never committed. An identifier is unique within its scope, this repository's being `vyvid`, so a bare `STD-3` here is `vyvid:STD-3`, and another scope's entry is cited in its qualified form, such as `lattice:STD-12` (VYD-Q1).

| Register | Prefix | Holds |
|---|---|---|
| [standards](standards.md) | `STD` | prescriptive rules for building Вивід, stratified from architectural to convention |
| [principles](principles.md) | `PRI` | durable design commitments, each grounded in a decision |
| [capabilities](capabilities.md) | `CAP` | what Вивід's own software can already do, so new work reuses it |
| [technical debt](technical-debt.md) | `TD` | a defect or shortfall in something that exists, with no planned home |
| [pending design decisions](pending-design-decisions.md) | `PDD` | a decision that matters and cannot be made yet |
| [backlog](backlog.md) | `BL` | an idea not yet planned |
| [facets](facets.md) | | the facet schemes every entry is tagged with |

A register's Scope column says which scope an entry belongs to, general, a domain or this project, so an entry can move to the scope it serves without changing its identifier (VYD-Q5). The signpost columns, Does not cover, Distinguished from, Narrowed by and Bears on, stand last and a row may leave them out.

## Lifecycle

A slice's state is written once, in its row on its unit's status board, as one of `planned`, `briefed`, `building`, `built`, `verified`, `merged`, `tagged`, with `blocked` and `dropped` aside, and the day it was reached from `building` on. An agent marks a slice `building` before its first edit. A question is named with its unit's prefix, VYD-Q1, and its answer is recorded in the plan or sketch that raised it.

## Writing

As in LATTICE: a paragraph or a list entry on one line, no semicolons, colons only to introduce a list, a table or a quotation, a thing said once and cross-referenced, and decisions written as the team's.
