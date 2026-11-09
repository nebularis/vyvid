<!-- SPDX-License-Identifier: MIT -->

# Status: setup

**Status:** building 2026-11-09
**Plan:** [setup](../plans/setup.md)

## Board

| Slice | Deliverable | State | Blocked on |
|---|---|---|---|
| SU-1 | the refusal that prints the direct command, and the error for an unset `kb` | building 2026-11-09 | |
| SU-2 | `vyd setup` | planned | SU-1 |
| SU-3 | the guide, the register row and the release | planned | SU-2 |

## History

- 2026-11-09: the unit created on `main` at the maintainer's word, from a contributor's report that a first local setup has no documented path and that `vyd trust` looks hung under a task runner. The maintainer ruled that a task does not pass input through, and that the command prints the direct command to run. SU-1 marked building before any edit.
