<!-- SPDX-License-Identifier: MIT -->

# Status: links

**Status:** building 2026-11-10
**Plan:** [links](../plans/links.md)

## Board

| Slice | Deliverable | State | Blocked on |
|---|---|---|---|
| LK-1 | backlinks, `vyd check links`, `vyd refs` and `vyd expand` | built 2026-11-10 | |
| LK-2 | `vyd mcp` | built 2026-11-10 | |
| LK-3 | the GitHub Action, the link check in `mise run check`, the guide, the register rows and the release | built 2026-11-10 | |
| LK-4 | the tools of `vyd mcp` answer plain, and the guide follows the links release | building 2026-11-10 | |

## History

- 2026-11-10: the unit created on `main` at the maintainer's word, from a comparison with another tool's links between documents and code. The maintainer set a browser view aside. The first code of LK-1 and LK-2 and a draft of the action were written in the working tree, uncommitted, before this record existed, since the maintainer asked for a first cut against the clock. The slices are marked building here before any of it is committed.
- 2026-11-10: LK-1, LK-2 and LK-3 built. `links.py` holds the backlink marker, `vyd check links` with `--require`, `vyd refs`, `vyd expand` and `vyd mcp`, and `action.yml` at the root is the action. `refs` reads only the files that can hold the identifier's spelling, and the link check says how many pointers it read. The build already refuses a pointer it cannot resolve, so the pointer half of the check finds what went missing after a build. Five tests in `tests/test_links.py`, sections of the guide and the README, CAP-37 to CAP-41, `check:links` in `mise run check`, and five backlinks in this repository's own code, which the check reads with 258 pointers. Run against LATTICE's checkout, which was left unchanged, the link check read 2084 files and 3155 pointers and found no backlink and nothing broken, `refs` listed the 8 lines that write one standard in under 2 s, `expand` printed two entries, and a server session answered `refs`, `find` and `read`. The three questions this unit's design asked the index and found weak are now answered by CAP-38, CAP-39 and CAP-40 at 0.83 or above. The version is 0.2.33. The action has not run on GitHub, and a backlink to a symbol is not built.

- 2026-11-10: LK-4 added at the maintainer's word, after a check of the guide against the release found that a tool of `vyd mcp` runs `vyd` with the user's own environment and configuration, so a user who sets `table = "pretty"` or `colour = "always"` hands an agent wrapped, painted tables. LK-4 marked building before any edit.
