<!-- SPDX-License-Identifier: MIT -->

# Status: windows-tests

**Status:** building 2026-11-07
**Plan:** [windows-tests](../plans/windows-tests.md)
**Mode:** autonomous, at the maintainer's request on 2026-11-07. Each slice is committed on the branch and nothing is pushed. Nothing may be written to the real home folder of the machine it runs on.

## Board

| Slice | Deliverable | State | Blocked on |
|---|---|---|---|
| WT-0 | plan, status record and index | built 2026-11-07, building 2026-11-07 | |
| WT-1 | the tests' own home, paths in TOML, the machine's capabilities | built 2026-11-07, building 2026-11-07 | |
| WT-2 | `vyd` fixes found on Windows | built 2026-11-07, building 2026-11-07 | |
| WT-3 | Windows forms of the tests that cannot run there as written | built 2026-11-07, building 2026-11-07 | |
| WT-4 | the whole suite on Windows, and the records | built 2026-11-07, building 2026-11-07 | |

## History

- 2026-11-07: the suite at `v0.2.16`, run on Windows 11 with Python 3.14.7 one file at a time, failed 83 tests and passed about 1,100. Four tests set `HOME` and not `USERPROFILE`, so `vyd install` wrote a rule file, an agent, a skill and a hook into the real `.claude` and `.copilot` folders. They were deleted. Every run since goes through a driver that deletes what a run creates in the home folder's watched places and restores a watched file it changes.
- 2026-11-07: WT-1 and WT-3 built together, since the support each test needed served both. Every test's own home now covers `USERPROFILE` and the `WIN_PD_OVERRIDE` folders, and `tests/test_isolation.py` fails if this process, or a child with either environment, would reach a folder outside the temporary one. Paths go into TOML with forward slashes, and text a test commits is written with `\n`, since a blob committed with CRLF is not converted by `core.autocrlf`. A link to a folder is a junction where no symbolic link can be made, the audit, containment, symbol and skill tests gained junction forms, and a link to a file skips naming the privilege. Owner-only modes stay POSIX tests, which is PDD-1. A locale set with `LC_ALL` and a path over 260 characters skip on Windows with the reason.
- 2026-11-07: WT-2 built. `vyd` asks the Windows console itself before it takes standard input for a person, writes the SQLite URI with forward slashes, reads a git name that is not UTF-8 without a traceback, treats `C:\x` and `C:/x` as the same local remote, refuses a rooted path such as `/abs` that Windows calls relative, ends a timed-out command's whole tree with `taskkill /T`, reports a junction in a domain as a link and does not read through it, and quotes a command it prints for PowerShell on Windows.
- 2026-11-07: run one file at a time under the home folder guard, the whole suite passed on Windows 11 with Python 3.14.7, unelevated and without Developer Mode, after two fixes to `tests/test_work.py` found by that run. The guard found nothing written to the home folder, apart from the registry's own log, which Windows writes.
- 2026-11-07: WT-4 built. In parallel with `pytest-xdist` the whole suite gave 1,134 passed, 197 skipped and 2 expected failures in 354 s, on 16 logical processors, with nothing written to the home folder. The manual test now names what the suite has run on Windows. `mise run check` itself was not run, since `uv` would rewrite this machine's `uv.lock`, so its parts were run directly. The suite still has to pass on macOS and Linux, which this machine cannot run, and that goes back to the maintainer.
- 2026-11-07: TD-3 retired at the maintainer's word. The `regex` wheel installs on Windows 11 with Python 3.14, and the tests that a backtracking pattern stops within its time limit and is reported pass there. The suite's slowness on Windows is BL-4.
