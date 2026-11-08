<!-- SPDX-License-Identifier: MIT -->

# Status: guard

**Status:** built 2026-11-08, released as 0.2.21 awaiting the maintainer's tag
**Plan:** [guard](../plans/guard.md)

## Board

| Slice | Deliverable | State | Blocked on |
|---|---|---|---|
| GD-1 | the configuration, the lists and the class of a repository | built 2026-11-08 | |
| GD-2 | the checks | built 2026-11-08 | GD-1 |
| GD-3 | the hooks and their install | built 2026-11-08 | GD-2 |
| GD-4 | `vyd guard` and the context line | built 2026-11-08 | GD-3 |
| GD-5 | the guide, the registers and the release | built 2026-11-08 | GD-4 |

## History

- 2026-11-08: the unit created on `reads-between-projects`, at the maintainer's request, after a public repository's documents named a private project. The design was settled in chat the same day. GD-1 marked building before any edit.
- 2026-11-08: GD-1 to GD-4 built together, since the hooks are only tested through the checks. `guard.py` reads the lists from the user's domains, classifies a repository by its remotes, checks added lines, messages and paths, and runs as pre-commit, commit-msg and pre-push hooks that `vyd install` sets up through git's global hooksPath and chains to a repository's own. `vyd guard status`, `check` and `hook`, and a line in `vyd context`. 33 tests in `tests/test_guard.py` run real commits and pushes, and the whole suite passes. GD-5 marked building.
- 2026-11-08: GD-5 built. A chapter of the guide, CAP-31, SEC-39, BL-7 for a similarity check by embeddings, and the version 0.2.21. Run against the user's real lists in a scratch repository, a commit of a listed name, a message with one and an unlisted repository under a watched owner each stopped, and a clean commit went through. The hooks are not yet set on the maintainer's machine, since a dozen repositories under the watched owners are unclassified and would stop at once.
