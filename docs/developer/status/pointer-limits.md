<!-- SPDX-License-Identifier: MIT -->

# Status: pointer limits

**Status:** built 2026-11-15, not yet released
**Plan:** [pointer-limits](../plans/pointer-limits.md)

## Board

| Slice | Deliverable | State | Blocked on |
|---|---|---|---|
| PL-1 | the Turtle term anchor | built 2026-11-15 | |
| PL-2 | the anchor hint on the whole-file note | built 2026-11-15 | PL-1 |
| PL-3 | `vyd check registers` with the baseline | built 2026-11-15 | PL-2 |
| PL-4 | the guide, the register rows and this repository's baseline | built 2026-11-15 | PL-3 |

## History

- 2026-11-15: the unit created on `main` at the maintainer's word, from a report of notes on LATTICE's registers. Option 2 chosen: fix the rows and make the limits bite at commit time.
- 2026-11-15: PL-1 to PL-4 built. `path.ttl::Name` resolves a Turtle term, the whole-file note names an anchor, and `vyd check registers` fails on a row not in the baseline or a baseline line that matches nothing. This repository's baseline lists 20 rows. Its own CAP-42 claim was 241 characters and was shortened, so it is not in the baseline. The containment tests failed once under `-n auto` and passed alone, so they look load-sensitive. Not tagged, since a release is the maintainer's word.
