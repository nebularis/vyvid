<!-- SPDX-License-Identifier: MIT -->

# Plan: the test suite on Windows

**Status:** building 2026-11-07, autonomously at the maintainer's request. Each slice is committed on the branch and nothing is pushed. The board is in [the status record](../status/windows-tests.md).
**Prefix:** WT

## Scope

The whole suite, run on Windows 11 with Python 3.14 and Git for Windows, one file at a time and with `pytest-xdist`, fails 83 tests and writes into the real home folder. The suite should pass there, read and write only below its own temporary folders, and say what it could not test.

Measured on 2026-11-07 at `v0.2.16`, unelevated, without Developer Mode:

| Cause | Tests | Fault |
|---|---|---|
| a Windows path written into a TOML basic string, where `\U` is an escape | about 36 | the tests |
| `HOME` set without `USERPROFILE`, which is what Windows reads for `~`, so `vyd install` wrote to the real profile | 4 files | the tests |
| a symbolic link refused for want of the privilege, error 1314 | 19 | the tests, for want of a Windows form |
| the null device answers `isatty()`, so `vyd trust` asks a person who is not there | 4 | `vyd` |
| a SQLite `file:` URI made by percent-encoding a Windows path, which SQLite cannot open | 2 | `vyd` |
| a file name git gives that is not UTF-8 raises on Windows, where Python decodes names strictly | 1 | `vyd` |
| a local remote compared by its text, `/` against `\` | 2 | `vyd` |
| a rooted path such as `/abs` is not absolute to Windows, so `work.presence` lets it through | 1 | `vyd` |
| a time limit stops the command and not what it started | 1 | `vyd`, already noted in the code |
| owner-only modes, which Windows does not keep | 2 | the tests |
| a resume command quoted for a POSIX shell, glue's environment and one message | 5 | the tests, and the printed command |
| a name longer than Windows' 260 characters | 5 | the machine, where long paths are off |
| bytes of an argument that a Windows command line cannot carry | 1 | the tests |
| a path compared with `/`, a grant under `core.autocrlf` | 2 | to read |

## Decisions taken

| # | Decision | Date |
|---|---|---|
| 1 | a test that needs a symbolic link to a directory has a Windows form that makes a directory junction, which needs no privilege. A test that needs a symbolic link to a file skips where the machine refuses one, naming the privilege, since no link to a file can be made without it | 2026-11-07 |
| 2 | owner-only modes stay a POSIX test, and the Windows form checks what the file holds. Restricting a file with an access control list on Windows is PDD-1, not this unit's | 2026-11-07 |
| 3 | the resume command `vyd` prints is quoted for PowerShell on Windows and for a POSIX shell elsewhere | 2026-11-07 |
| 4 | a test that sets a locale with `LC_ALL` skips on Windows, which has no per-process locale. `PYTHONIOENCODING` already tests the streams there | 2026-11-07 |
| 5 | a skip names what the machine lacks, and a test that skips on Windows has a Windows form wherever one can be written | 2026-11-07 |

## Slices

| Slice | Delivers | Validation |
|---|---|---|
| **WT-0** | this plan, the status record, the unit in the index | `mise run check:writing`, `check:identifiers` |
| **WT-1** | the tests' home is their own on every platform, `USERPROFILE` and the platform's folders included, and a test fails if a child `vyd` would use the real ones. Paths are written into TOML in a form TOML reads on Windows. The machine's capabilities, a symbolic link, a junction and a long path, are probed once | the TOML and home failures pass, and nothing is written to the real home folder |
| **WT-2** | `vyd` fixed for the null device, the SQLite URI, a name that is not UTF-8, a local remote, a rooted path and the time limit's reach on Windows | each failing test passes unchanged |
| **WT-3** | the Windows forms: junctions for links to directories, the content of an owner-only file, the argument's bytes, a long name, the resume command and the rest | each skip on Windows has a form that runs, or a reason none can |
| **WT-4** | the whole suite on Windows in parallel and file by file, the manual test updated, notes recorded | `mise run check` on Windows |

## Done when

`mise run check` passes on Windows with every skip naming what the machine lacks, nothing is written to the real home folder, and the suite still passes on macOS and Linux, which this unit cannot run and hands back to the maintainer.
