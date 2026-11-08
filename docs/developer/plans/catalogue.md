<!-- SPDX-License-Identifier: MIT -->

# Plan: a repository catalogue that Вивід reads

**Status:** building 2026-11-08, at the maintainer's request.
**Prefix:** CT

## Scope

Code that finds a file by a relative path or an absolute one breaks in another checkout, another worktree or another working folder. A repository can instead say once where things live, in a catalogue that its tools read through one reader, and ask the reader for a place by name. One project keeps such a catalogue and its own reader. This unit gives Вивід a generic reader, so any project can have one, a project that reads another can see its modules, and the quanta kind needs no module list written twice.

A project names its catalogue in its `vyvid.toml`:

```toml
[project.catalogue]
file = "code:repository-catalogue.md"
module_root = "ontology"
```

The file is Markdown. Fenced blocks tagged `toml repository-catalogue` hold the data and any other fence is text. The blocks merge, and a key defined twice is refused. They hold:

| Block | Holds |
|---|---|
| `[conventions]` | `roles`, `kinds` (a name and its meaning) and `[conventions.release]` with a `version` and the `kinds` released together |
| `[catalogue] modules` | the modules, by name |
| `[[roots]]`, `[[docs]]` | named areas of the repository, with a `path` |
| `[[tools]]` | tool packages, with a `name` and a `path` |
| `[generated] paths` | paths a check may find missing |

Each module has a README at `<module_root>/<name>/README.md` with a `[module]` block holding `kind`, `roles`, `imports` and `extract`. The reader keeps every key it does not know, so a project may add its own checks on top of the shared reader.

The reader answers `area(name)`, `module(name).directory(role)`, `modules_of_kind(kind)` and `release_members()`, always as a path relative to the root, and `vyd catalogue` prints the same.

## Slices

| Slice | Content | Depends on | Estimate |
|---|---|---|---|
| CT-1 | the reader: the blocks, the merge, the modules, areas, tools and conventions, and errors that name the file and the key, tests first | | 90k |
| CT-2 | the project setting, `vyd catalogue`, the quanta kind reading its modules from the catalogue, the guide, the register row and the release | CT-1 | 80k |

## Out of scope

The checks of one project's catalogue against its tree, which stay with that project, and a `cat:` token for paths in a `vyvid.toml`.

## Validation

`mise run check`. The tests build a catalogue in a temporary folder, and one run reads a real project's catalogue to compare answers with its own reader.
