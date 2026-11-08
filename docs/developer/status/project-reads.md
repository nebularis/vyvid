<!-- SPDX-License-Identifier: MIT -->

# Status: project-reads

**Status:** building 2026-11-08
**Plan:** [project-reads](../plans/project-reads.md)

## Board

| Slice | Deliverable | State | Blocked on |
|---|---|---|---|
| RD-1 | the `reads` configuration and the visibility guard | built 2026-11-08 | |
| RD-2 | the snapshot of a pinned commit | building 2026-11-08 | |
| RD-3 | the read scope in the stack and the index | planned | RD-2 |
| RD-4 | `vyd reads status` and `vyd reads pin` | planned | RD-2 |
| RD-5 | the guide, the sketch note and the release | planned | RD-3, RD-4 |

## History

- 2026-11-08: the unit created on `reads-between-projects`, from `main` at `59bf573`, at the maintainer's request and with the work authorised in this checkout until the patch is done. The branch is for MERIDIAN to read LATTICE. RD-Q1 to RD-Q5 answered the same day. RD-1 marked building before any edit.
- 2026-11-08: the plan revised at the maintainer's word. Skills and recipes come by name under review at the pin (RD-P1, RD-Q5), the code that runs over a read is the reader's own (RD-P6, RD-Q2), BL-6 taken into the unit and BL-5 superseded by an extension domain for derived knowledge such as quanta. The maintainer authorised the unit through RD-5 on this branch, with a push, and a branch in MERIDIAN.
- 2026-11-08: RD-1 built. `reads` with allow-lists, the user's `reviewed_reads`, the guard in loading and in `--scope`, and the display in `vyd context`, with 9 tests in `tests/test_reads.py` and the whole suite passing. RD-2 marked building.
