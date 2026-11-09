<!-- SPDX-License-Identifier: MIT -->

# Plan: a first local setup that a person can follow

**Status:** built 2026-11-09, at the maintainer's request, from a contributor's report of setting up on a Windows laptop.
**Prefix:** SU

## Scope

A contributor installs `vyd` and finds the next step undocumented and its first command refused. `vyd domain add` writes nothing until the configuration's `[framework]` table sets `kb`, which no command sets and whose error does not say how. A command that asks a question, such as `vyd trust`, looks hung when a task runner captures its output, since the question is held in the capture.

| Change | Decision |
|---|---|
| A command that asks a question | `vyd trust` and `vyd kb accept` need a person at a terminal with their output on that terminal. Otherwise they refuse at once and print the command to run directly, `vyd trust`, or `mise exec -- vyd trust` where mise supplies `vyd`. A task is not made to pass input through |
| The error for an unset `kb` | says to set `[framework] kb` in the configuration file it names, or to run `vyd setup` |
| `vyd setup [folder] [--no-clone] [--dry-run]` | sets `kb` to a folder under Вивід's data folder where none is set, adds each published domain that the folder's `vyvid.toml` names and the configuration lacks, with trust `knowledge`, clones them, and prints the next steps |

The published domains are `lifecycle`, `tools`, `python`, `haskell`, `triple-stores` and `rdf-modelling`, each cloned from `https://github.com/nebularis/vyvid-<name>.git`. A name that is not one of them is listed for the person to add. A domain given trust `knowledge` gives an index and a board and no skills until a person reviews it, which the last step says.

## Slices

| Slice | Content | Depends on | Estimate |
|---|---|---|---|
| SU-1 | the refusal that prints the direct command, and the error for an unset `kb`, tests first | | 40k |
| SU-2 | `vyd setup` | SU-1 | 70k |
| SU-3 | the guide, the register row and the release | SU-2 | 30k |
| SU-4 | the skills check skips and says why while a domain is unreviewed, and `vyd install --project` removes no skill then, tests first | SU-3 | 50k |
| SU-5 | `vyd setup` prints each cloned domain's review line, the guide and the release | SU-4 | 20k |

## Validation

`mise run check`. The tests write their own configuration and git configuration under a temporary folder and clone from local repositories, never the network.

## Added 2026-11-09

A first local setup leaves every domain at trust `knowledge`, so the skills a project commits cannot be composed. `vyd check skills` then reported each committed skill as one no source makes, and advised `vyd install --project`, which removes them. While a domain the project uses is not reviewed, or was reviewed at a commit its folder has left, the check exits 2 as it does for an untrusted `vyvid.toml`, naming each such domain and the line that reviews it, and `vyd install --project` still writes the skills it can compose and removes none, saying why. `vyd setup` prints that line for each domain it cloned.
