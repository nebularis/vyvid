<!-- SPDX-License-Identifier: MIT -->

# Plan: tables a person can read, and tables a document can hold

**Status:** built 2026-11-09, at the maintainer's request.
**Prefix:** TB

## Scope

A command that gives a table to a person prints plain columns separated by two spaces, with a cell cut at 90 characters, which suits an agent and is hard on a human. The default stays as it is. Two more ways to print the same table are chosen with `--table`.

| Value | Prints |
|---|---|
| `plain` | the table as it is now, byte for byte. The default |
| `pretty` | columns fitted to the terminal, a long cell wrapped onto continuation lines and never cut, a header and one rule under it, and no box |
| `md` | a Markdown pipe table, every cell whole, with `\|` escaped, a newline written as `<br>`, and a note column where a row has a note |

`auto` is also accepted wherever a choice is made, and means `pretty` at a terminal and `plain` otherwise. The choice is the `--table` flag, anywhere on the command line, then the `VYD_TABLE` environment variable, then `[framework] table` in the user's configuration, then `plain`.

## Rules

| # | Rule |
|---|---|
| TB-P1 | `plain` is never changed by this unit. Every existing assertion on a table holds |
| TB-P2 | Everything a table command prints stays on standard output, the table, its notes and its row count. Standard error is for errors alone |
| TB-P3 | An `id` is never cut or wrapped, since it is what an agent passes to `read` |
| TB-P4 | `pretty` draws its rule with a box-drawing character only where the stream's encoding can write it, else with `-`. Width is counted in display columns, so a wide character takes two |
| TB-P5 | Where the columns cannot fit the terminal even at their least width, `pretty` prints each row as a block of `column: value` lines |

## Slices

| Slice | Content | Depends on | Estimate |
|---|---|---|---|
| TB-1 | the renderer: plain, pretty and md, the width, wrapping, the encoding fallback and the stacked layout, tests first | | 50k |
| TB-2 | the choice (`--table`, the environment, the configuration) and every table that goes through `show` | TB-1 | 30k |
| TB-3 | the status-style commands as tables: `config`, `guard status`, `reads status`, `catalogue show` and `modules`, `kb status` | TB-2 | 40k |
| TB-4 | `vyd table-demo` for looking at the three styles, the guide, the register row and the release | TB-3 | 25k |

## Validation

`mise run check`. The renderer is tested on invented rows with a width and a fake stream encoding given, so the tests need no terminal. How it looks on Windows is the maintainer's to try with `vyd table-demo`.
