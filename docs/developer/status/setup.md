<!-- SPDX-License-Identifier: MIT -->

# Status: setup

**Status:** built 2026-11-09, released as 0.2.28
**Plan:** [setup](../plans/setup.md)

## Board

| Slice | Deliverable | State | Blocked on |
|---|---|---|---|
| SU-1 | the refusal that prints the direct command, and the error for an unset `kb` | built 2026-11-09 | |
| SU-2 | `vyd setup` | built 2026-11-09 | |
| SU-3 | the guide, the register row and the release | built 2026-11-09 | |
| SU-4 | the skills check skips and says why while a domain is unreviewed, and install removes no skill then | built 2026-11-09 | |
| SU-5 | `vyd setup` prints each cloned domain's review line, the guide and the release | built 2026-11-09 | |

## History

- 2026-11-09: the unit created on `main` at the maintainer's word, from a contributor's report that a first local setup has no documented path and that `vyd trust` looks hung under a task runner. The maintainer ruled that a task does not pass input through, and that the command prints the direct command to run. SU-1 marked building before any edit.
- 2026-11-09: SU-1 to SU-3 built together. `vyd trust` and `vyd kb accept` refuse at once where input or output is not a terminal and print the command to run, the error for an unset `kb` names the setting and `vyd setup`, and `vyd setup` sets `kb`, adds and clones the published domains a project names with trust `knowledge`, and prints the steps left. 11 tests in `tests/test_setup.py`, seven older assertions of the old message updated, a section of the guide and CAP-34. The whole suite passes. The version is 0.2.25.
- 2026-11-09: 0.2.25 was tagged before `vyd setup` was tried on a real project with an empty configuration. It bound the project through its `vyvid.toml`, and a project that names a domain nobody configured is set aside, which is the state setup is for, so it found no project. 0.2.26 reads the file as written and counts a delegation's and a move's domains, and holds back each edit's diff. Run for real against the published repositories from an empty configuration, it set `kb`, added and cloned the five domains that project names, and a second run changed nothing. 12 tests in `tests/test_setup.py`.
- 2026-11-09: SU-4 and SU-5 added at the maintainer's word, after a guide for a first local setup found that `vyd check skills` fails on a fresh configuration and advises the command that removes the committed skills (BL-11, BL-10). SU-4 marked building before any edit.
- 2026-11-09: SU-4 and SU-5 built. While a domain the project uses is at trust `knowledge`, or was reviewed at a commit its folder has left, `vyd check skills` exits 2 naming each domain and the line that reviews it, and `vyd install --project` writes what it can, deletes no generated skill and exits 1, saying why. `vyd setup` prints each cloned domain's folder and review line at the commit it cloned. 5 tests added to `tests/test_setup.py`, the guide and CAP-35, BL-10 and BL-11 built. The version is 0.2.27.

- 2026-11-09: 0.2.27 covered a domain that is not reviewed and not a read that lost its review when its pin moved, which a project that carries a read's skills meets at its next pin. The check and `vyd install --project` now treat that read the same way, naming `vyd reads review <name>`. One test in `tests/test_reads.py`. The version is 0.2.28.
