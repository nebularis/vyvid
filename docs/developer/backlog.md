<!-- SPDX-License-Identifier: MIT -->

# Backlog

**Unit type:** Register

An idea we want and have not planned. It moves into a plan when a unit takes it on.

| ID | Idea | Raised | Why we want it | What exists | Status | Waits for | Bears on |
|---|---|---|---|---|---|---|---|
| BL-1 | **An optional `vyvid_interface` package for a project's own environment, giving a command extractor a scratch store, the contract's files written, and a `Context` without `Config` or `Scope`.** | 2026-11-04 | A command extractor in Python would otherwise repeat the request parsing, the quad and result writing and the scratch store, and today's `Context` hands an extractor the whole configuration | CAP-13 defines the contract, and a command extractor writes the two files itself | Open | | CAP-13 |
| BL-2 | **A `work` setting naming the remote that publishes, so the roadmap reads only that remote's branches.** | 2026-11-05 | `vyd work roadmap` reads every remote under `refs/remotes`, so a project with a second, private remote could have that remote's branch names written into its committed roadmap | CAP-26 reads every remote's branches and no setting limits them | Open | | CAP-26 |
| BL-3 | **A GitHub Actions run of `mise run check` on Windows, Linux and macOS for every push and pull request.** | 2026-11-07, the maintainer | a change that holds on macOS can fail on Windows unseen, as encodings have, and today only a person on a Windows machine finds out. A narrow code page is worth a step of its own, with `PYTHONIOENCODING` set to `cp936`, `cp932` and `cp1252` | no workflow in this repository. `tests/test_output_encoding.py` on the branch `fix/windows-utf8-output` and `docs/developer/windows-manual-test.md` show what to exercise. A contributor's full run on Windows on 2026-11-06 gave 57 failed, 17 errors and 674 passed, and reported invalid TOML escapes in fixtures, symlink privileges and a POSIX file mode among the causes. They were there before their change, so a Windows job starts red and needs those fixed first. Whether a hosted Windows runner can change its system code page is not known, since that normally takes a restart | Idea |  | VYD-14, TD-3 |
