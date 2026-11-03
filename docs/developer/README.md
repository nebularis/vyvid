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

Every piece of text, in documents, code comments, commit messages and replies (PRI-1):

- a paragraph or a list entry on one line, with newlines only between paragraphs, and an edit to a wrapped one joins it (STD-3)
- no semicolons. Use periods or commas (STD-4)
- colons sparingly, never to join two clauses or to lead into an explanation. A colon may introduce a list, a table or a quotation (STD-5)
- concise, a thing said once and cross-referenced (STD-6)
- no superlatives for emphasis, no "it's not X, it's Y" reframes, no formulaic transitions and no meta-commentary (STD-7)
- an example introduced as one, "for example" or "e.g.", never by a colon (STD-8)
- few rhetorical questions, emphatic short sentences and metaphors (STD-9)
- structure shown with metadata a tool reads, and a meaning stated once where it is defined (STD-1)
- a thing named by the term this repository already uses for it (STD-2)
- written as the team, "we decided", "accepted 2026-11-03", with AI involvement marked only in the commit trailer (STD-10)

## What is published

This repository is public. User-facing text is the README, every document outside `docs/developer/`, and the command's output and help.

- User-facing text never refers to a working document, a sketch, a plan, a status record, a register or this index, in text, links or comments, and cites only accepted decisions, except a decision's closing Provenance section (PRI-2, STD-14).
- User-facing text never names a slice, phase, question, debt or other delivery identifier, or uses delivery phrasing (STD-15).
- Nothing identifies a person outside what the project itself names (STD-11), and nothing holds a credential, a private hostname or a private repository path (STD-12). A note true of one machine or one person belongs in their own configuration, never here (STD-13).

## The contract

- A check is reported as passed only when it ran and passed, and what was not run is said (PRI-3).
- Each kind of document keeps its role: a sketch changes freely, a plan only when the plan changes, a status record after every material action (STD-16).
- When two standards conflict for a change, we stop and ask the maintainer, and record the conflict in the pending design decisions, so a conflict that recurs shows which standards to rework (STD-18).
