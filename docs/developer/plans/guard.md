<!-- SPDX-License-Identifier: MIT -->

# Plan: a guard that keeps private terms out of public repositories

**Status:** built 2026-11-08, at the maintainer's request and with the design settled the same day.
**Prefix:** GD

## Scope

A person who works across public and private repositories keeps lists of what a public repository must never hold: names, phrases, paths. An agent that has not read those lists, or has not decided which repository it is in, publishes the name without meaning to. Reading a rule file does not stop that, so the guard checks the change at commit and at push.

The mechanism is public and holds no term. The lists are files in the user's own private domains, and the user's configuration names the domains:

```toml
[framework.guard]
domains = ["example-private"]
watch_owners = ["github.com/example-org"]
```

A guarded domain has a `guard` folder (a domain root also supplies `upstreams` and `private-upstreams`):

| File | Holds |
|---|---|
| `upstreams` | repositories that are public, as `host/owner/repository`, one per line |
| `private-upstreams` | repositories that are private and guarded for the terms that apply everywhere |
| `deny-terms` | one case-insensitive regular expression per line, applied to every guarded repository |
| `public-deny-terms` | the same, applied to public repositories alone |
| `warn-terms` | the same, applied to public repositories, and a match warns and does not block |
| `never-track` | path globs that no commit may add |
| `sensitive-paths` | `repository: glob` or a bare glob, where a commit must carry a `Placement:` trailer |
| `allow` | names of built-in patterns to switch off |

A line starting `!` in a terms file names a path glob to skip. A line starting `#` is a comment.

## Principles

| # | Principle |
|---|---|
| GD-P1 | The repository carries no term, no list and no private name. Its tests use invented terms |
| GD-P2 | A finding names the file, the line and the entry's number in its list, never the term, so a shared log does not repeat it |
| GD-P3 | The guard decides the repository's class from its remotes, so an agent cannot forget the check. A repository under a watched owner that is in neither list fails closed |
| GD-P4 | The maintainer can always override, with `VYD_GUARD_SKIP` and a reason, which is logged. A blocked agent reports the finding and proposes a conformant change, and never skips |
| GD-P5 | Hooks are installed by default for the user by `vyd install --client`, and do nothing where no guard is configured |
| GD-P6 | The hooks never brick git. Where `vyd` is missing they warn and pass |

## Slices

Estimates are in tokens, for agent work.

| Slice | Content | Depends on | Estimate |
|---|---|---|---|
| GD-1 | the configuration, the lists read from the user's domains, and the class of a repository | | 80k |
| GD-2 | the checks of added lines, messages and paths: terms, built-in patterns, never-track, the placement trailer and the skip log | GD-1 | 120k |
| GD-3 | the hooks for pre-commit, commit-msg and pre-push, their user-level install in `vyd install --client` and the chain to a repository's own hook | GD-2 | 100k |
| GD-4 | `vyd guard status`, `check` and `hook`, and the line in `vyd context` and `vyd config` | GD-3 | 50k |
| GD-5 | the guide, the register rows, the backlog entry for a similarity check, and the release | GD-4 | 50k |

## Out of scope

A check that compares staged text with the user's private repositories for copying. It is backlog BL-7.

## Validation

`mise run check`. The tests build real repositories in a temporary folder with invented terms, and write their own global git configuration.
