<!-- SPDX-License-Identifier: MIT -->

# Plan: tables a person can read, and tables a document can hold

**Status:** built 2026-11-09, at the maintainer's request, and extended the same day with colour.
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

## Colour

Added 2026-11-09 at the maintainer's request. Colour is for `pretty` alone. `plain` is what an agent reads and `md` is a document, so neither ever holds an escape code. It is chosen apart from the style.

| Choice | Rule |
|---|---|
| `--colour auto\|always\|never` (also `--color`) | anywhere on the line, then the `VYD_COLOUR` variable, then `NO_COLOR` (off) or `FORCE_COLOR` (on), then `[framework] colour`, then `auto` |
| `auto` | on when standard output is a terminal, `TERM` is not `dumb`, and on Windows the console accepts virtual terminal sequences |
| roles | `header`, `rule`, `id`, `item` (the first column of a status table), `note`. The defaults are bold, dim, cyan, bold and dim |
| `[framework.colours]` | a role set to a spec of attributes (`bold`, `dim`, `italic`, `underline`, `reverse`), a colour (`red`, `bright_blue`, `color208`), a background (`on_yellow`, `on_color17`) or `none` |

Widths are counted on the text and the escape codes are added after, so a coloured table lines up as an uncoloured one.

| Slice | Content | Depends on | Estimate |
|---|---|---|---|
| TB-5 | the palette, the spec grammar, painting the roles in `pretty`, and the width left unchanged, tests first | TB-4 | 40k |
| TB-6 | the choice (flag, environment, configuration), the roles in the configuration, enabling virtual terminal sequences on Windows, the guide and the release | TB-5 | 40k |

## Validation

`mise run check`. The renderer is tested on invented rows with a width and a fake stream encoding given, so the tests need no terminal. How it looks on Windows is the maintainer's to try with `vyd table-demo`.
