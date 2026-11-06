<!-- SPDX-License-Identifier: MIT -->

# Sketch: agents in cloud sessions with no terminal

**Status:** sketch, 2026-11-06. The maintainer chose option A on 2026-11-06, so it is built for public domains as slice VYD-21. Private domains wait for VYD-10.
**Unit:** vyvid-framework
**Questions:** VYD-Q42, VYD-Q43

## 1. The problem

A person sets an agent up in a cloud environment by writing a setup script. We measured what that gives in Claude Code cloud sessions on Linux on 2026-11-06.

- The script runs as root, with the home folder of root, before the client starts. The filesystem is snapshotted and reused. A later session skips the script and gets a fresh checkout newer than the snapshot, at a path under the user's home, for up to about seven days. A script stays cacheable if it finishes within about five minutes.
- No terminal exists, so `vyd trust` cannot run. A hash recorded in the script would go stale whenever a branch changes `vyvid.toml`.
- A configuration written straight into the platform's configuration folder with `trust = "own"` domains already works, and `vyd kb clone` clones public domains.
- Timings: the whole setup about 23 seconds, the first `find` with the model download and embedding 68 seconds, `vyd build` with the vectors present 4.7 seconds, and a `find` on a current index 1.8 seconds.
- `origin` reads as a plain `https://` URL for the hosting service there.
- During setup the automatic build's embedding failed and `find` said it found no vectors and that the build says why, with no reason shown. A later `find` at the same commit did not rebuild, so it stayed in that state.

Without a grant, a project's own standards, skills and contract are marked as data there, and nothing it declares runs.

## 2. The options

| Option | What it is | Cost |
|---|---|---|
| A. A repository named in the user's own configuration | `[framework] trusted_repositories` lists normalised remotes. A `vyvid.toml` is trusted while the checkout's `origin` is listed and the file equals the blob committed at `HEAD`. Read from the user's own configuration alone | A hostile branch of a listed repository is trusted. An agent able to edit the configuration can list a repository |
| B. A hash in the setup script | `vyd trust` run from the script against the checkout | Stale on every change to `vyvid.toml`, and the checkout the script sees is older than the session's |
| C. An environment variable | A variable names the repositories | Rejected. A repository can set environment variables through its own client settings and task runner configuration, so a hostile branch could grant itself |
| D. No change | A project's own standards stay marked as data | Safe, and the project's contract and skills never reach the agent through `vyd` |

A is chosen. The first three conditions below decide what it is. The rest keep it small.

- Only `origin` counts, so a fork whose `upstream` is a listed repository is not trusted.
- An uncommitted edit lapses the trust, and committing it restores the trust.
- The recorded hash is checked first and still wins, so `vyd trust` is unchanged, and it is the only thing that writes a hash.
- No command writes the key. Anything that could write it would give an agent a way to grant trust.
- A malformed or unreadable configuration grants nothing.

Two smaller changes came from the same sessions. The automatic build now prints on standard error the reason it made no embeddings, and a `find`, `misses` or recipe that ranks rebuilds a store that has no vectors once its last build is ten minutes old. A build told not to embed leaves a marker, so that retry does not undo it. The time limit keeps a failing download from costing a rebuild on every question.

## 3. Questions

- **VYD-Q42. Why does embedding fail during setup?** Open. Not yet known. One hypothesis is that the environment's network allows the setup script less than the session, or the model host is not reachable from where the script runs. Another is memory or time pressure while the script runs. Neither is confirmed, and the reason is now printed so the next session shows it.
- **VYD-Q43. How does a cloud session get a private domain?** Open, waiting for VYD-10. A private domain needs a credential to clone, which a setup script should not hold, and a trust decision that nobody is at a terminal to make.

## 4. What it costs

About 60 lines in the configuration module, a few lines in the command that prints the configuration, the build and the question path, and tests that run the real command with no terminal. It adds one git call to a project file's trust check when a list is set, and none otherwise.
