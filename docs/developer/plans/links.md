<!-- SPDX-License-Identifier: MIT -->

# Plan: links between code and documents, and the index behind a protocol

**Status:** built 2026-11-10, at the maintainer's request.
**Prefix:** LK

## Scope

A comparison with a tool that keeps a graph of Markdown sections and source symbols showed what Вивід lacked. A document could name code by a pointer, and nothing in code named an entry in a way a check could hold. Nothing listed where an identifier is written. A prompt that names entries by identifier left the agent to look each one up. A client without a shell could not ask the index, which VYD-Q3 left for later, and a project could not run the checks in CI without installing the tool itself. A browser view of the graph is left out of this unit.

| Part | Does |
|---|---|
| a backlink | a comment in a tracked file that is not Markdown, holding `@vyd:` and identifiers separated by commas to the end of the line |
| `vyd check links [folder] [--require <family>]` | fails on a backlink no register defines, on a pointer of one of the project's own entries that names a file that is not there or a line past its end, and with `--require` on an entry of the family that no backlink names |
| `vyd refs <identifier>` | every tracked line that writes the identifier, as `defines`, `backlinks` or `mentions` |
| `vyd expand [words]` | the prompt, from the words or standard input, then the kind, status, claim and pointer of every identifier it mentions |
| `vyd mcp` | the tools `context`, `find`, `node`, `read`, `reaches`, `refs` and `expand` over standard input and output, by the Model Context Protocol |
| `action.yml` | a composite GitHub Action that installs `vyd` from the tag named, builds the index without vectors and runs the identifier and link checks |

## Rules

| # | Rule |
|---|---|
| LK-P1 | Only a marked line is a backlink. Code and its tests hold text that merely looks like an identifier, so an unmarked match in code is a mention that `refs` lists and no check fails |
| LK-P2 | Files are enumerated from `git ls-files`, never a folder walk, as the identifier check does, and what `identifiers.skip` names is left out |
| LK-P3 | A backlink resolves only where a register defines the identifier, since resolving alone says which scope an identifier would be in |
| LK-P4 | The server holds no state. Each call runs `vyd` as a process of its own, with every value a client gives after `--`, so none is read as an option |
| LK-P5 | No symbol enters the graph, as before. A backlink names a register entry, and a backlink to a symbol is not built |

## Slices

| Slice | Content | Depends on | Estimate |
|---|---|---|---|
| LK-1 | the backlink marker, `vyd check links` with `--require`, `vyd refs` and `vyd expand`, with tests | | 40k |
| LK-2 | `vyd mcp`, the server and its tools, with tests | LK-1 | 20k |
| LK-3 | the GitHub Action, the link check in `mise run check`, backlinks in this repository's own code, the guide, the register rows and the release | LK-2 | 30k |
| LK-4 | the tools of `vyd mcp` answer plain whatever the table and colour settings, and the guide follows the links release, tests first | LK-3 | 15k |

## Validation

`mise run check`, which runs the link check on this repository. The commands are also run against a second project with more registers and code than this one before the release. The action is not run by the suite, so its first run on GitHub is the maintainer's to watch.
