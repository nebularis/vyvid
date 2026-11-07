<!-- SPDX-License-Identifier: MIT -->

# Status: windows-tests

**Status:** building 2026-11-07
**Plan:** [windows-tests](../plans/windows-tests.md)
**Mode:** autonomous, at the maintainer's request on 2026-11-07. Each slice is committed on the branch and nothing is pushed. Nothing may be written to the real home folder of the machine it runs on.

## Board

| Slice | Deliverable | State | Blocked on |
|---|---|---|---|
| WT-0 | plan, status record and index | built 2026-11-07, building 2026-11-07 | |
| WT-1 | the tests' own home, paths in TOML, the machine's capabilities | planned | |
| WT-2 | `vyd` fixes found on Windows | planned | |
| WT-3 | Windows forms of the tests that cannot run there as written | planned | |
| WT-4 | the whole suite on Windows, and the records | planned | |

## History

- 2026-11-07: the suite at `v0.2.16`, run on Windows 11 with Python 3.14.7 one file at a time, failed 83 tests and passed about 1,100. Four tests set `HOME` and not `USERPROFILE`, so `vyd install` wrote a rule file, an agent, a skill and a hook into the real `.claude` and `.copilot` folders. They were deleted. Every run since goes through a driver that deletes what a run creates in the home folder's watched places and restores a watched file it changes.
