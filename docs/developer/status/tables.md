<!-- SPDX-License-Identifier: MIT -->

# Status: tables

**Status:** building 2026-11-09
**Plan:** [tables](../plans/tables.md)

## Board

| Slice | Deliverable | State | Blocked on |
|---|---|---|---|
| TB-1 | the renderer | built 2026-11-09 | |
| TB-2 | the choice and every table through `show` | built 2026-11-09 | |
| TB-3 | the status-style commands as tables | building 2026-11-09 | |
| TB-4 | `vyd table-demo`, the guide and the release | planned | TB-3 |

## History

- 2026-11-09: the unit created on `main` at the maintainer's word, with no other session building here. The maintainer chose the flag `--table`, a header rule and no box for `pretty`, every note of the Markdown form on standard output, and the status-style commands in the same unit. TB-1 marked building before any edit.
- 2026-11-09: TB-1 and TB-2 built. `table.py` renders plain, pretty and md, `--table` is taken wherever it stands, then `VYD_TABLE`, then `[framework] table`, and every table through `show` follows it. The whole suite passes with plain unchanged, 26 tests in `tests/test_table.py`. TB-3 marked building.
