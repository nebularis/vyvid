<!-- SPDX-License-Identifier: MIT -->

# Status: tables

**Status:** built 2026-11-09, released as 0.2.31, awaiting the maintainer's try on Windows
**Plan:** [tables](../plans/tables.md)

## Board

| Slice | Deliverable | State | Blocked on |
|---|---|---|---|
| TB-1 | the renderer | built 2026-11-09 | |
| TB-2 | the choice and every table through `show` | built 2026-11-09 | |
| TB-3 | the status-style commands as tables | built 2026-11-09 | |
| TB-4 | `vyd table-demo`, the guide and the release | built 2026-11-09 | |

## History

- 2026-11-09: the unit created on `main` at the maintainer's word, with no other session building here. The maintainer chose the flag `--table`, a header rule and no box for `pretty`, every note of the Markdown form on standard output, and the status-style commands in the same unit. TB-1 marked building before any edit.
- 2026-11-09: TB-1 and TB-2 built. `table.py` renders plain, pretty and md, `--table` is taken wherever it stands, then `VYD_TABLE`, then `[framework] table`, and every table through `show` follows it. The whole suite passes with plain unchanged, 26 tests in `tests/test_table.py`. TB-3 marked building.
- 2026-11-09: TB-3 and TB-4 built. `config`, `guard status` and `check`, `reads status`, `catalogue show` and `modules` and `kb status` print rows on request, and their lines are unchanged otherwise. `vyd table-demo` prints one sample in every style with the width and encoding. A row that took several lines is set apart by a blank line, and the others are not. 12 more tests in `tests/test_table.py`, a section of the guide and CAP-36. The whole suite passes. The version is 0.2.30. Not seen on Windows, which the maintainer is to try.
- 2026-11-09: 0.2.30 was tried on a real `find` and squeezed the claim and the pointer to slivers of about 12 columns at 80, and printed each claim again under its row. 0.2.31 never squeezes a text column below 24 columns and stacks the rows instead, and `find` prints the signposts alone under a row where the claim is whole in its column. Two more tests in `tests/test_table.py`.
