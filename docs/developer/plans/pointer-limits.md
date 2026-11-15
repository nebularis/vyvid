<!-- SPDX-License-Identifier: MIT -->

# Plan: pointer and claim limits that bite when a row is added

**Status:** building 2026-11-15, at the maintainer's request.
**Prefix:** PL

## Scope

A build of LATTICE printed notes for thirteen claims over the limit and sixteen pointers at a whole file that read refuses. Both were found only after a branch was in flight, because nothing stops a row that breaks them from being added. Turtle has no anchor shorter than the whole file, so a pointer into a long vocabulary can never satisfy the limit.

| Part | Does |
|---|---|
| a Turtle term anchor | `path.ttl::Name`, with `Name` a local name or a prefixed name, resolves to the lines of the statement that describes that term |
| a hint | the note for a whole-file pointer names an anchor the file offers, a section, a top-level name or a term |
| `vyd check registers` | fails on a claim over the limit or a pointer at a whole file, for an entry that the baseline `limits.baseline` of `register-types.toml` does not list |

## Rules

| # | Rule |
|---|---|
| PL-P1 | The limits stay as they are. The check makes them bite and offers no way to raise them silently, since `limits.claim` is already the project's to set |
| PL-P2 | The baseline lists an identifier and the kind of defect, one per line, with a reason after a `#`. An entry already over a limit is listed once, and the check fails on any other |
| PL-P3 | A baseline line that no longer matches a defect is reported, so the baseline only shrinks |

## Slices

| Slice | Content | Depends on | Estimate |
|---|---|---|---|
| PL-1 | the Turtle term anchor, with tests | | 15k |
| PL-2 | the anchor hint on the whole-file note, with tests | PL-1 | 8k |
| PL-3 | `vyd check registers` with the baseline, the check in `mise run check`, with tests | PL-2 | 20k |
| PL-4 | the guide, the register rows and the baseline of this repository | PL-3 | 8k |

## Validation

`mise run check`, and the new check run against LATTICE's registers before the next release.
