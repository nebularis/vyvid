<!-- SPDX-License-Identifier: MIT -->

# Sketch: setting up configuration from the command line

**Status:** sketch, 2026-11-05. The maintainer asked for it to be built on 2026-11-05, so its questions go as leaned. It is slice VYD-23.
**Unit:** vyvid-framework
**Questions:** VYD-Q35 to VYD-Q41

## 1. The problem

A person sets up Вивід by editing TOML by hand. `vyd domain new` writes a new domain folder and `vyd install` writes a client's files, but no command adds a domain to the configuration, declares a project or registers a family. Each of these today means opening `config.toml` or `vyvid.toml`, knowing the keys, and writing a family's pattern and type correctly.

A project whose documents live apart from its code shows the cost. Binding one takes a project entry with its code folder, documents folder, contract, remote and domains, and a family for each register in the documents folder. A person works out each family by reading the documents' tables. A command could read those tables itself, since a register's header is its schema.

## 2. The proposal

Commands for each thing a person now writes by hand, each printing what it will change, and writing only what `vyd config` then loads cleanly.

```text
vyd domain add <name> --path <folder> | --remote <url> [--trust own|reviewed|knowledge] [--dry-run]
vyd domain remove <name> [--dry-run]

vyd project add <name> [--code <folder>] [--docs <folder>] [--contract <path>] [--remote <url>]... [--domain <name>]... [--visibility public|private] [--dry-run]
vyd project set <name> <key> <value> [--dry-run]
vyd project remove <name> [--dry-run]
vyd project scan <name> [--apply]

vyd family add <project> <name> --defined <path> --type <type> [--pattern <regex>] [--removable] [--dry-run]
vyd family remove <project> <name> [--dry-run]

vyd init [--file]
```

- **`vyd project add`** fills in what it can see. Run in a checkout, `--code` is that checkout and `--remote` its remotes.
- **`vyd project scan`** reads the documents folder for tables whose first column holds identifiers, proposes a family and a type for each from the header and the register types, and prints the block. With `--apply` it writes it. A table it cannot place is named, never guessed.
- **`vyd init`** asks the same questions in turn at a terminal, and offers `vyvid.toml` with `--file` or the user's configuration otherwise.

For example, a project with its documents in a folder of a private repository would be set up like this.

```text
cd ~/work/some-project
vyd domain add tools --remote https://github.com/example/vyvid-tools
vyd project add some-project --docs ~/work/private-docs/some-project --contract docs:CONTRACT.md --domain tools
vyd project scan some-project --apply
vyd config
vyd build
```

### What must hold

- **Every write is validated before it lands.** The new text is parsed and loaded as the whole configuration, and on a problem nothing is written and each problem is listed, as `vyd config` lists it.
- **A person's comments and layout survive.** The configuration is theirs, and many keep notes in it.
- **A command widens no trust an agent could not already widen by editing the file, and refuses to where it can.** An agent that runs commands as the user can already edit the configuration (SEC-22). A command still should not make that easier, so `--trust own`, or anything else that raises what runs, needs a terminal, as `vyd trust` does (SEC-21). `vyd trust` stays the only way to record a `vyvid.toml` as trusted.
- **Editing `vyvid.toml` says that it lapses trust,** and which command restores it.
- **A private domain's or documents folder's path never reaches a `vyvid.toml`,** since that file is committed. A path outside the repository goes to the user's configuration, and the command says so.

## 3. Questions

- **VYD-Q35. How is TOML edited with its comments kept?** Leaning `tomlkit`, a small pure-Python library, as a new dependency, since an edit to a nested table in text is where a hand-written splice goes wrong. The alternative is the standard library, appending whole blocks and removing a table by its span, which adds no dependency and cannot edit in place.
- **VYD-Q36. Which file does a command write when both could hold the setting?** Leaning that the user's configuration is the default, `--file` writes the repository's `vyvid.toml`, and a command refuses `--file` for what a `vyvid.toml` may not set.
- **VYD-Q37. Should the verbs be nested under `vyd config`, or stand as nouns?** Leaning nouns, `vyd project add`, since `vyd domain` already exists and the other verbs read as actions on a thing.
- **VYD-Q38. How far does `vyd project scan` go?** Leaning registers only, leaving recipes, extractors and moves to hand. A generated pattern is a further question, since it could read ordinary prose as an identifier, so a pattern is proposed only where the default does not fit, and is shown for a person to read.
- **VYD-Q39. Does `vyd init` belong in the first cut?** Leaning later, since an interactive flow is the most code to test and the commands above serve a person and an agent alike.
- **VYD-Q40. May an agent run these at all?** Leaning yes for what binds knowledge, as an agent setting up a project is a real use, with the terminal check on whatever raises trust. A client's permission settings remain the real control (SEC-22).
- **VYD-Q41. What does a remove do to what depends on it?** Leaning that removing a domain a project uses is refused, naming the project, and that a remove never deletes a clone or a store.

## 4. What it costs

About 400 lines and their tests, plus one dependency if VYD-Q35 goes as leaned. The commands read and write configuration only, so they touch no index, and each can be proven on a scratch `VYVID_CONFIG`, including on Windows.
