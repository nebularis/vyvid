<!-- SPDX-License-Identifier: MIT -->

# Status: setup

**Status:** built 2026-11-09, released as 0.2.25
**Plan:** [setup](../plans/setup.md)

## Board

| Slice | Deliverable | State | Blocked on |
|---|---|---|---|
| SU-1 | the refusal that prints the direct command, and the error for an unset `kb` | built 2026-11-09 | |
| SU-2 | `vyd setup` | built 2026-11-09 | |
| SU-3 | the guide, the register row and the release | built 2026-11-09 | |

## History

- 2026-11-09: the unit created on `main` at the maintainer's word, from a contributor's report that a first local setup has no documented path and that `vyd trust` looks hung under a task runner. The maintainer ruled that a task does not pass input through, and that the command prints the direct command to run. SU-1 marked building before any edit.
- 2026-11-09: SU-1 to SU-3 built together. `vyd trust` and `vyd kb accept` refuse at once where input or output is not a terminal and print the command to run, the error for an unset `kb` names the setting and `vyd setup`, and `vyd setup` sets `kb`, adds and clones the published domains a project names with trust `knowledge`, and prints the steps left. 11 tests in `tests/test_setup.py`, seven older assertions of the old message updated, a section of the guide and CAP-34. The whole suite passes. The version is 0.2.25.
