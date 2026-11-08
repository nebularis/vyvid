<!-- SPDX-License-Identifier: MIT -->

# Status: catalogue

**Status:** built 2026-11-08, released as 0.2.23 awaiting the maintainer's tag
**Plan:** [catalogue](../plans/catalogue.md)

## Board

| Slice | Deliverable | State | Blocked on |
|---|---|---|---|
| CT-1 | the catalogue reader | built 2026-11-08 | |
| CT-2 | the project setting, `vyd catalogue`, quanta from the catalogue and the release | built 2026-11-08 | |

## History

- 2026-11-08: the unit created on `reads-between-projects`, after the quanta kind, at the maintainer's request. CT-1 marked building before any edit.
- 2026-11-08: CT-1 and CT-2 built. `catalogue.py` reads the blocks, modules, areas, tools and conventions, keeps what it does not know, and agreed with one project's own reader on the modules, kinds, roles, imports, extracts, areas, release members and tools of its catalogue on two checkouts of different content. `[project.catalogue]`, `vyd catalogue`, quanta from the catalogue, a read's catalogue from its snapshot, a chapter of the guide, CAP-33 and the version 0.2.23. 21 tests in `tests/test_catalogue.py`.
