<!-- SPDX-License-Identifier: MIT -->

# Status: quanta

**Status:** built 2026-11-09, released as 0.2.29
**Plan:** [quanta](../plans/quanta.md)

## Board

| Slice | Deliverable | State | Blocked on |
|---|---|---|---|
| QU-1 | the built-in kind `quanta` | built 2026-11-08 | |
| QU-2 | quanta over a read, the guide and the release | built 2026-11-08 | |
| QU-3 | `vyd read` and `vyd node` print a quantum, and `--kind quantum` filters to quanta | built 2026-11-09 | |

## History

- 2026-11-08: the unit created on `reads-between-projects`, after the guard, at the maintainer's request. The design was settled in chat, with the modules inline in the project's `vyvid.toml` and the catalogue to follow as its own unit. QU-1 marked building before any edit.
- 2026-11-08: QU-1 and QU-2 built. The kind `quanta` in `extractors/quanta.py`, PyYAML as a dependency for compose files, a section of the guide, CAP-32 and the version 0.2.22. A project that reads another gets the other's quanta with no review, since the kind is built in. 10 tests in `tests/test_quanta.py`, the whole suite passing.
- 2026-11-08: checked against one project's own extractor on two checkouts of different content, reading its catalogue. The kind produced the same 15 and 16 entries, with the same claims, pointers, parts, findings and units, once `skip_kinds` named the scaffold kind and the core's pointer was the catalogue. Both settings were added for it.
- 2026-11-09: QU-3 added at the maintainer's word, after `vyd read lattice:software/compose/workspace` answered nothing from a project that reads another (BL-9). QU-3 marked building before any edit.
- 2026-11-09: QU-3 built. `vyd read` and `vyd node` find a quantum by its identifier when no register family resolves it, bare in the project or as `scope:data/x` for a read, and `read` prints its claim, view, deployment, parts and pointer, fenced as data while its scope is unreviewed. `--kind quantum` filters to quanta. 5 tests in `tests/test_quanta.py`, the guide and BL-9 built. The version is 0.2.29.
