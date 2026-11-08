<!-- SPDX-License-Identifier: MIT -->

# Status: project-reads

**Status:** built 2026-11-08, released as 0.2.20 awaiting the maintainer's tag
**Plan:** [project-reads](../plans/project-reads.md)

## Board

| Slice | Deliverable | State | Blocked on |
|---|---|---|---|
| RD-1 | the `reads` configuration and the visibility guard | built 2026-11-08 | |
| RD-2 | the snapshot of a pinned commit | built 2026-11-08 | |
| RD-3 | the read scope in the stack and the index | built 2026-11-08 | |
| RD-4 | `vyd reads status`, `pin` and `review` | built 2026-11-08 | |
| RD-5 | the guide, the sketch note and the release | built 2026-11-08 | |

## History

- 2026-11-08: the unit created on `reads-between-projects`, from `main` at `59bf573`, at the maintainer's request and with the work authorised in this checkout until the patch is done. The branch is for a private project to read LATTICE. RD-Q1 to RD-Q5 answered the same day. RD-1 marked building before any edit.
- 2026-11-08: the plan revised at the maintainer's word. Skills and recipes come by name under review at the pin (RD-P1, RD-Q5), the code that runs over a read is the reader's own (RD-P6, RD-Q2), BL-6 taken into the unit and BL-5 superseded by an extension domain for derived knowledge such as quanta. The maintainer authorised the unit through RD-5 on this branch, with a push, and a branch in the downstream project.
- 2026-11-08: RD-1 built. `reads` with allow-lists, the user's `reviewed_reads`, the guard in loading and in `--scope`, and the display in `vyd context`, with 9 tests in `tests/test_reads.py` and the whole suite passing. RD-2 marked building.
- 2026-11-08: RD-2 and RD-3 built together, since the snapshot is only tested through the stack. `reads.py` extracts the pinned commit with `git archive` into the base store by name and commit, with a record of its tree, and cuts the snapshot's `vyvid.toml` to knowledge. The read sits between the domains and the project, `built-for` names `name@commit`, a reviewed read brings the recipes and skills it is told to, a skill is composed under the read's own prefix, `(drop)` removes a section, and a read names which of the reader's domains run their extractors over it. 21 tests in `tests/test_reads.py`, the whole suite passing. RD-4 marked building.
- 2026-11-08: RD-4 and RD-5 built. `vyd reads status`, `pin` and `review`, with 26 tests in `tests/test_reads.py` and the whole suite passing. The guide section, CAP-30, SEC-38, the sketch note and the version 0.2.20. The tag `v0.2.20` and the push to `main` are the maintainer's.
