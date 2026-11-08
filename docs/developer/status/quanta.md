<!-- SPDX-License-Identifier: MIT -->

# Status: quanta

**Status:** built 2026-11-08, released as 0.2.22 awaiting the maintainer's tag
**Plan:** [quanta](../plans/quanta.md)

## Board

| Slice | Deliverable | State | Blocked on |
|---|---|---|---|
| QU-1 | the built-in kind `quanta` | built 2026-11-08 | |
| QU-2 | quanta over a read, the guide and the release | built 2026-11-08 | |

## History

- 2026-11-08: the unit created on `reads-between-projects`, after the guard, at the maintainer's request. The design was settled in chat, with the modules inline in the project's `vyvid.toml` and the catalogue to follow as its own unit. QU-1 marked building before any edit.
- 2026-11-08: QU-1 and QU-2 built. The kind `quanta` in `extractors/quanta.py`, PyYAML as a dependency for compose files, a section of the guide, CAP-32 and the version 0.2.22. A project that reads another gets the other's quanta with no review, since the kind is built in. 10 tests in `tests/test_quanta.py`, the whole suite passing.
