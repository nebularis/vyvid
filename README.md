<!-- SPDX-License-Identifier: MIT -->

# Вивід · vyvid

**Вивід** (*vyvid*) is Ukrainian that can refer to inference, as in *виведи*, "derive it". The command line tool this project packages is `vyd`.

Вивід provides a simple framework for giving AI agents contextualised information from which to make decisions, set rules, record and recall findings and questions related to the projects it works on, and of the subjects those projects share, ranked by meaning and scoped to the folder the agent is in. Its indexes and embeddings are built from markdown sources, making it a type of spec-driven development toolkit.

## Components

- **Registers** are Markdown tables whose header is their schema: rules, findings, decisions, tech debt, questions, notes about a tool, etc. They are the source of truth, held and reviewed in git.
- **Facets** are closed sets of values, held as SKOS schemes, that tag every entry across as many dimensions as a subject needs, such as the activity, the quality at stake, and the technology.
- **Domains** group all the facets, registers, skills, and query recipes of a subject. Subjects are as diverse as a user may wish, e.g., OWL ontologies, triple stores, Haskell development, or tools a developer uses. Domains form a directed graph, and a domain can live in a project, in a shared knowledge base, or in a repository of its own.
- **Projects** are codebases with a contract of their own. A project uses domains and specialises them, so the same question asked in a project's folder gets the project's answer first, with the domain's beneath it.
- **The index** is derived from all of these on demand. It ranks entries by meaning with a local embedding model. Rules at a narrower scope override those at a wider scope. 

Вивід grew out of the knowledge index of [LATTICE](https://github.com/nebularis/lattice), which is its first project.

## Layout

| Path | Holds |
|---|---|
| `docs/developer/` | how Вивід is designed and built, for its developers |
| `docs/architecture/decisions/` | the decisions, `ADR-nnn`, listed in [the catalogue](docs/architecture/decisions/README.md) |
| `src/vyvid/` | the package: `config.py` the configuration, `resolve.py` binding, layers and identifiers, `cli.py` the `vyd` command |
| `tests/` | the test suite, `mise run check` |
| `examples/config.toml` | an example configuration with LATTICE and this repository as projects |
| `mise.toml` | the only task entry point |


## Using it

Each command below has a section with its form, what it is for, its options and what to watch for. [docs/GUIDE.md](docs/GUIDE.md) walks through the same commands in the order a project adopts them. Every command prints results on standard output and notes and problems on standard error, so a pipe carries only the results. Most commands take `--in <folder>` or a `folder` argument, which defaults to the folder you are in and decides which project's stack answers.

### Installing and global options

#### Installing `vyd`

```bash
uv tool install "git+https://github.com/nebularis/vyvid.git@<tag>"
uv tool install "vyvid[symbols] @ git+https://github.com/nebularis/vyvid.git@<tag>"
mise run install
```

The first line installs the tool at a released tag, and the second adds the grammars that source search needs. In a clone of this repository, `mise run install` installs it editable, so `vyd` runs that working tree.

- Вивід is not on PyPI, so install from the Git source.
- An editable install follows the working tree, so a branch you check out or a file you edit changes the `vyd` every project runs.
- Reinstalling with other extras needs `--force`.
- The same install provides `vyd-hook`, which the reminder hooks run, described at the end of this section.
- The first question downloads the embedding model into the platform cache, and everything after it runs locally.

#### Global options

```bash
vyd --version
vyd <command> ... --table plain|pretty|md|auto --colour auto|always|never
vyd table-demo
```

`--version` prints the name and the version, always ending in the bare version number. `--table` and `--colour` may stand anywhere on the line of any command that prints a table.

| Option | Meaning |
|---|---|
| `--table plain` | the default, columns separated by two spaces with a cell cut at 90 characters and an identifier never cut. This is the form an agent reads |
| `--table pretty` | columns fitted to the terminal, a long cell wrapped and never cut |
| `--table md` | a Markdown pipe table with every cell whole, to paste into a pull request |
| `--table auto` | `pretty` at a terminal and `plain` otherwise |
| `--colour auto\|always\|never` | whether a `pretty` table is painted. `--color` is accepted too |

- The flag wins, then `VYD_TABLE` or `VYD_COLOUR`, then `NO_COLOR` and `FORCE_COLOR` for colour, then `table` and `colour` in `[framework]`.
- `plain` and `md` are never painted, so no escape code reaches an agent or a document.
- `vyd table-demo`, which `--help` does not list, prints a sample in every style with the width and encoding of your terminal, to see what they look like there.
- Output keeps the encoding of the stream it goes to. A character the stream cannot hold is written as an escape such as `і` and never ends the command. Set `PYTHONIOENCODING=utf-8` when a program needs exact UTF-8.

### Setting up a machine

#### `vyd setup`

```bash
vyd setup [folder] [--no-clone] [--dry-run]
```

Writes a first configuration on a machine that has none. It sets `[framework] kb` to a folder in Вивід's data folder when it is not set, adds each published domain the folder's project names in its `vyvid.toml`, from `https://github.com/nebularis/vyvid-<name>.git` with trust `knowledge`, and clones them.

| Option | Meaning |
|---|---|
| `folder` | the repository whose `vyvid.toml` names the domains, the current folder by default |
| `--no-clone` | add the domains and leave the cloning to `vyd kb clone` |
| `--dry-run` | print the plan and write nothing |

- It knows only the published domains `lifecycle`, `tools`, `python`, `haskell`, `triple-stores` and `rdf-modelling`. Any other domain is listed for you to add with `vyd domain add`.
- Running it again changes nothing, and it never overwrites a `kb` or a domain you configured.
- Every domain it adds gives knowledge alone, so agents get no skills from it until you review it. It prints `vyd domain trust <name> reviewed --commit <hash>` for each, to run once you have read the domain.
- It ends by listing what is left for you, such as `vyd trust`, which a person runs in a terminal.

#### `vyd config`

```bash
vyd config [folder]
```

Says where the configuration is read from, whether it is sound, and what applies in the folder. It prints the configuration's path and whether it is trusted, the domains and projects, any domain set aside with the reason, the repositories listed in `trusted_repositories`, the project the folder binds to and whether its `vyvid.toml` is trusted, and whether what `vyd install` wrote is out of date.

- The configuration is the file `VYVID_CONFIG` names, else `config.toml` in the platform's configuration folder. Use the path this prints rather than guessing the folder.
- The `configuration trust:` line is about your configuration and the `project` line about the repository's `vyvid.toml`. They are separate standings.
- A file saved with a byte order mark or as UTF-16 is read all the same. A file in any other encoding is reported as a problem that names it.
- Run it first whenever `vyd context` shows only the general scope.

#### `vyd trust`

```bash
vyd trust [path]
```

A person trusts a configuration outside their own folder, or the `vyvid.toml` of the repository they stand in, by the hash of its bytes, so its glue and command extractors run and its contract and skills reach agents. It prints what the file declares that an agent would read or that would run as you, and records the trust only on a typed `yes`.

- It needs a terminal for its input and its output. Under a task runner that captures output, such as `mise run`, it refuses at once and prints the command to run yourself, for example `mise exec -- vyd trust`.
- Any change to the file lapses the trust, so trust again after editing it, after `vyd project set --file` or after `vyd reads pin`.
- Linked worktrees share the record while their file holds the same bytes. A worktree whose `vyvid.toml` differs replaces the record for the whole repository, so switching between them needs trusting again. Listing the repository in `[framework] trusted_repositories` avoids that.
- An agent must never answer it on a person's behalf.

#### `vyd install`

```bash
vyd install [--client claude-code|copilot] [--hooks] [--target folder] [--no-git-hooks] [--dry-run]
vyd install --project [--in folder] [--dry-run]
```

Without `--project` it sets up each agent client at user level. For each client it writes the skill that reviews a domain someone else wrote, and for Claude Code a rule file telling the agent to ask the index first and a read-only reviewer agent. It adds the skills of private domains and of domains whose entry says `user_skills = true`, and puts a domain's `always_rules` where Claude Code loads rules in every session. With `--project` it composes the folder's project's skills into its checkout, under each folder `skill_targets` names, to be committed, and registers the reminder hook for each client in `hook_clients`.

| Option | Meaning |
|---|---|
| `--client` | only this client. Without it every client whose folder exists, `~/.claude` and `~/.copilot` |
| `--hooks` | also register the reminder hook in the client's user-level settings, where the client documents a place for one |
| `--target folder` | write into this folder instead of the client's own, to inspect the result. Needs `--client` |
| `--no-git-hooks` | leave out the guard's git hooks, which are set up whenever a guard is configured |
| `--project` | compose the project's skills and hooks into its checkout |
| `--in folder` | with `--project`, the folder whose project is written |
| `--dry-run` | say what would be written and write nothing |

- With no client folder present it writes nothing and exits 1, so name one with `--client`.
- A file that `vyd install` did not write is never overwritten. It is reported and the command exits 1.
- Generated files whose source is gone are removed, except that `--project` removes none while a domain or a read the project uses is not reviewed, since their skills could not be composed. It then writes what it can, names each such domain with the line that reviews it, and exits 1.
- A skill with a placeholder nobody gives a value for is not written, and the command names the value and exits 1.
- A knowledge domain gives no skills, and a private domain's skills never go into a checkout.
- Copilot documents no user-level hook file, so `--hooks` with `--client copilot` writes nothing and exits 1. Register its hook with `--project`.
- Do not edit generated skills. Change their sources and run it again.

### Asking the index

#### `vyd context`

```bash
vyd context [folder] [--json] [--no-pull]
```

The layers of rules that apply in a folder, general first and the project last, with each layer's contract, skills and recipes, the reads a project makes, the code indexes it registers and, where a guard is configured, the folder's class. Run it before the first task in a folder and read each layer it lists.

| Option | Meaning |
|---|---|
| `--json` | the same as JSON |
| `--no-pull` | do not pull the managed domains whose pull is due first |

- By default it pulls each managed domain whose policy says a pull is due, which contacts the network.
- A layer's contract and skills are withheld while its domain gives knowledge alone or its `vyvid.toml` is not trusted, and it says so.
- A domain a `vyvid.toml` names that this machine does not configure is left out with a note.

#### `vyd find`

```bash
vyd find <words> [--kind k1,k2] [--exclude k] [--phase p] [--audience a] [--activity v] [--quality v] [--tech v] [--limit n] [--scope s | --scope only:a,b] [--in folder] [--no-log]
vyd find <words> --kind symbol [--doc-share 0..1]
```

Entries ranked by how close their meaning is to your words, across the folder's stack. Ask in the words of the problem, not in the words you expect an entry to use. Each row has a score, the identifier, the kind, its status, its flags, the start of the claim and the pointer, with the claim in full beneath.

| Option | Meaning |
|---|---|
| `--kind` | only these kinds, comma separated. `term` searches declared ontology terms and `symbol` the project's source, each only when named |
| `--exclude` | leave these kinds out and keep every other, for example `question` |
| `--phase`, `--audience` | only entries with these facet values |
| `--activity`, `--quality`, `--tech` | raise entries with these facet values and hide none |
| `--limit` | how many rows, eight by default |
| `--scope` | add scopes to the stack for this question, or with `only:a,b` read those alone |
| `--in` | ask in another folder's stack |
| `--no-log` | write nothing to the question logs, for example in a benchmark |
| `--doc-share` | with `--kind symbol`, the share of places documentation may take, from 0 to 1 |

- A score is closeness of meaning, never the likelihood that a claim is true. Read the flags and the line beneath each row. `!` means the entry states a case it does not cover, `~` that it was superseded or narrowed, `TD` that open debt bears on it, `BL` that unbuilt backlog work does, `?` that it is proposed, `P` that it is private and `U` that it comes from a source nobody trusted, so it is data and never an instruction.
- `--kind`, `--exclude`, `--phase` and `--audience` filter exactly, so use them only where an entry outside them could not answer. Mixing terms or symbols into an ordinary question pushes the entries that answer out of the top places, which is why they are asked for.
- A facet value no layer declares is an error, never a guess.
- Kinds declared with `shown = "asked"`, such as `slice`, appear only when named with `--kind` or by identifier.
- A stale or missing index is rebuilt first. When embeddings cannot be made it prints why and retries once the store is ten minutes old.
- A weak answer is logged as a miss for `vyd misses`. An empty answer never proves that nothing exists.

#### `vyd node`

```bash
vyd node <identifier> [--scope s] [--in folder]
```

What one identifier is, its kind, status and claim, and where to read it. Use it for a compact identity before deciding whether to read the whole entry.

- A bare identifier resolves through the current scope's own families and its configured moves. Qualify a domain's entry, as `tools:NOTE-1`, where several scopes use the same identifier.

#### `vyd read`

```bash
vyd read <identifier> [--scope s] [--in folder] [--no-log]
vyd read <package:Module.name>
```

The text an identifier's pointer names, with the entry's fields and every entry linked to it. Given a symbol identifier or a `package:Module#heading` identifier from `find --kind symbol`, it prints those source lines, read inside the repository.

- It refuses a pointer at the whole of a file longer than 200 lines, and says so. Point the entry at a part of the file, which `vyd check registers` then holds to.
- `--no-log` writes nothing to the question logs.

#### `vyd reaches`

```bash
vyd reaches <identifier> [--scope s] [--in folder]
```

What an identifier touches through the relations registers declare, such as `supports`, `decidedBy` or `dependsOn`.

- It follows declared relations alone. It is not a call graph, and it does not prove the full reach of a change.

#### `vyd exists`

```bash
vyd exists <word> [--scope s] [--in folder]
```

Whether a term of that name already exists, by text, across the ontology modules of the stack and selected kinds of entry. Run it before declaring a name, so the same thing is not declared twice.

- It matches text and does not rank by meaning, so it complements `find` and never replaces it.
- Finding nothing is logged as a miss, which brings a gap in the vocabulary to light.

#### `vyd resolve`

```bash
vyd resolve <identifier> [--in folder]
```

The canonical `scope:LOCAL` an identifier names from the folder's scope, following families, delegations and moves. A notice explaining how it resolved goes to standard error.

- An identifier a project moved to a domain prints the domain's identifier, so the project's text need not be rewritten.

#### `vyd refs`

```bash
vyd refs <identifier> [--in folder]
```

Every tracked line that writes an identifier, as `file:line`, and whether it `defines`, `backlinks` or `mentions` it. Use it to find where a standard is enforced or what cites an entry before you change it.

- A definition is found only in a register and a backlink only in code, in an `@vyd:` comment. Everywhere else is a mention.
- Only files `git ls-files` lists are read.

#### `vyd expand`

```bash
vyd expand [words] [--in folder]
```

A prompt, from the words or from standard input, followed by the kind, status, claim and pointer of every identifier it mentions, so an agent is handed what the identifiers mean and not only their names.

- Pipe a prepared prompt in, for example `vyd expand < prompt.md`.

#### `vyd sparql`

```bash
vyd sparql '<query>' [--scope s] [--in folder]
```

Runs a SPARQL query against the graphs of the folder's stack, for a question the other commands do not cover.

- It sees the stack's graphs, not every configured project.
- The store is derived, so fix a wrong fact in its source register and never in the store.

#### `vyd build`

```bash
vyd build [folder] [--all] [--no-embed]
```

Builds the index of the folder's project and its stack, parsing changed source symbols into the symbol store too. A question rebuilds a stale index by itself, so run this to see the build's notes or to build ahead of time.

| Option | Meaning |
|---|---|
| `--all` | every configured scope, not only the folder's stack |
| `--no-embed` | build the store without vectors, which is enough to inspect extraction and leaves semantic search unavailable |

- Read every note it prints, even when it exits 0. A note names a register cell it could not read, a claim cut at 200 characters or a pointer at a whole long file, and a usable partial index can hide them.
- The first build downloads the embedding model.
- A linked worktree gets a store of its own, so one checkout's code never answers in another.

#### `vyd mcp`

```bash
vyd mcp [--in folder]
```

Serves `context`, `find`, `node`, `read`, `reaches`, `refs` and `expand` as Model Context Protocol tools over standard input and output, for an editor or an agent client. Register it as a command, for example `claude mcp add vyvid -- vyd mcp`.

- Each call runs `vyd` as its own process in the folder the server started in, or the one `--in` names, so the server keeps no state and a stale index is rebuilt by the call that finds it.
- Every tool answers with the plain table, whatever your table and colour settings say.

#### `vyd handoff`

```bash
vyd handoff <name> [--module M] [--unit U] [--in folder]
```

The exact commands to ask a compiler's index that a project registers, printed and never run. Given a definition's name, with `--module` naming its module, it prints the commands that find its definition and references. Given a module, it prints the commands that list what that module calls, and `--unit` keeps those to units whose name starts with the text you give.

- `hiedb` is the only kind with command templates so far.
- It checks that the database exists and holds rows, and says when its sources are newer than it. It never builds the database.
- The registered build command is shown as text and withheld until the `vyvid.toml` is trusted.

### Recipes

#### `vyd recipe list`

```bash
vyd recipe list [--in folder]
```

The recipes of the folder's stack, each with its scope and when to use it. Check here for one that fits the work before assembling a briefing by hand.

- A recipe in a narrower scope replaces one of the same name in a wider scope, so the list shows which one runs.

#### `vyd recipe run`

```bash
vyd recipe run <name> "<question>" [--in folder] [--all] [--json] [--dry-run]
vyd recipe run <name> "<question>" --stop-at-glue
vyd recipe run --resume <state> --glue-output <file>
```

Runs a recipe, a named chain of `find`, `linked`, `include`, `take` and `glue` steps, for a question, and prints the briefing within the recipe's budget.

| Option | Meaning |
|---|---|
| `--in` | the folder whose stack the recipe comes from |
| `--all` | every entry, ignoring the budget |
| `--json` | the entries as JSON |
| `--dry-run` | print each step and each glue command with its folder, and run nothing |
| `--stop-at-glue` | stop at a glue step and print its command, folder, input and output files for your client to run |
| `--resume state` | carry on from the state file a stopped run printed |
| `--glue-output file` | with `--resume`, the file holding the glue command's output |

- The budget is an estimate at four characters a token, and the last entries are dropped when the briefing runs over it.
- A run that stops at glue exits 3, so automation must tell that apart from success. `[framework] glue = "stop"` makes every run stop at glue, so each command passes through your client's own permission checks.
- Glue runs only for a trusted project, in its code folder with a minimal environment and a time limit. A command you run yourself after a stop gets your shell's environment instead.
- Glue replaces the accumulated entries, so a faulty glue command can drop context as well as add it.

### Closing the knowledge loop

#### `vyd misses`

```bash
vyd misses [--limit n] [--near] [--in folder]
```

The questions the folder's project asked that were answered weakly or not at all, newest first, then the gaps recorded with `vyd gap`. With `--near` it also lists the questions answered between the weak and the near score. Report it at each handoff, with the column or edge that would have carried each answer.

- It first asks each logged question again and removes those the index now answers, so it loads the embedding model.
- Questions are logged per project, under `logs/<project>` in the store, so another project's misses never show.
- Nothing is logged with `[framework] logs = false`.
- `--limit` defaults to 20.

#### `vyd gap`

```bash
vyd gap "<what was found>" [<ID>] [<path:line>] [--in folder]
```

Records, as soon as you find it, what reading a file told you that the index did not, with the entry it qualifies and the line it was read from. The question asked just before is kept with it.

- An argument holding `/` or a line number is taken as the place, and anything else as an entry.
- Write the missing signpost into the register, then run `vyd close`.

#### `vyd close`

```bash
vyd close <ID> ... [--in folder]
```

Closes the gaps recorded against these entries once their signpost is written, and removes the related lines of the logs, the gap and the miss of the question asked before it.

- Rebuild and run `vyd check identifiers` before closing, so the signpost is in the index.

### Checks

Each check exits 0 when it passes and 1 when it fails. Where it could not run, it says so and exits 2, so a hook or a script can tell a check that did not run from one that passed.

#### `vyd check identifiers`

```bash
vyd check identifiers [folder] [--all] [--json]
```

Fails on an identifier that the tracked Markdown mentions and nothing defines, and on one a family defines twice.

| Option | Meaning |
|---|---|
| `--all` | also list each spelling variant, each removable entry no longer defined and each stale exception |
| `--json` | everything found, as JSON |

- It reads the files `git ls-files` lists and never walks folders, so an ignored file is not read.
- A passing run prints one line. What it reports and never fails is counted after "Reported, never failed".
- A family with `removable = true` reports its unresolved mentions without failing, `defined_only = true` stops a loose pattern reading ordinary text as identifiers, and an `exceptions` file lists identifiers defined nowhere on purpose, each with a reason.
- When an identifier is defined twice, the line committed first keeps the number.
- A mention covered by a move resolves only if the domain defines it. A symbol identifier the store no longer holds is reported as `symbol gone`.
- It exits 2 when the tracked files cannot be listed, and 1 when a pattern runs out of time.

#### `vyd check links`

```bash
vyd check links [folder] [--require FAMILY ...]
```

Fails on an `@vyd:` backlink in code that no register defines, and on a pointer of the project's own entries that names a missing file or a line past its end.

| Option | Meaning |
|---|---|
| `--require FAMILY` | also fail on an entry of this family that no backlink names. May be given more than once |

- A backlink is a comment holding `@vyd:` and identifiers separated by commas, in a tracked file that is not Markdown. Only those lines are read, since code and tests hold text that merely looks like an identifier.
- Renumbering or withdrawing an entry shows up here, in the code that named it.

#### `vyd check registers`

```bash
vyd check registers [folder]
```

Fails on a row of the project's own registers whose claim is over its limit, 200 characters by default, or whose pointer names the whole of a file longer than 200 lines, unless the baseline lists the row. The build only notes these, so this check makes them fail when the row is added.

- The baseline is the file `limits.baseline` names in a `register-types.toml`, with one `ID claim` or `ID pointer` per line and a reason after `#`.
- A baseline line that no longer matches a defect fails too, so the baseline only shrinks.
- A domain's rows are the domain's to fix and are not counted.
- It builds an index without vectors in a scratch folder, so it takes a few seconds. It exits 2 when the baseline cannot be read.

#### `vyd check skills`

```bash
vyd check skills [folder] [--from old/SKILL.md ...] [--map map.tsv]
```

Fails where a skill committed in the checkout differs from what its sources compose to, is missing, has no source any longer or lacks a placeholder value.

| Option | Meaning |
|---|---|
| `--from` | old skill files, each of whose lines must appear in a composed skill or in the map, so a move loses nothing |
| `--map` | with one `--from` file, a tab-separated file with `line` and `destination` columns that gives a line a home elsewhere |

- It exits 2, saying it did not run, where a domain or a read the project uses is not reviewed, a domain's sources are missing, no project claims the folder or its `vyvid.toml` is not trusted. It names each domain with the line that reviews it.
- A fresh machine leaves every domain at `knowledge`, so this is the answer until they are reviewed.
- After it fails, run `vyd install --project` and commit the regenerated skills with the change to their sources.

#### `vyd check citations`

```bash
vyd check citations --staged [--in folder]
vyd check citations --message <file> [--in folder]
vyd check citations <path> ... [--in folder]
```

Refuses lines of a public project that cite an entry of a private scope, or of the project's private documents, bare or qualified.

| Option | Meaning |
|---|---|
| `--staged` | the lines staged in the code repository, and in the documents repository when that is public |
| `--message file` | a commit message or pull request text, every line of which is checked |
| `paths` | files or folders whose every line is checked |

- It needs at least one of the three, and exits 2 otherwise.
- A private project may cite anything, so the check passes there at once.
- It resolves identifiers. It does not detect a paraphrase, a copied passage or a sensitive fact, which is what the guard and a review are for.

#### `vyd move check`

```bash
vyd move check [folder] [--ref <git ref>] [--json]
```

Compares the entries each move names, as the source stood at the move's commit, with the source in the working tree or at a ref, by identifier. Run it on each branch that matters before removing a project's copy of what it moved to a domain.

- It exits 1 on a difference and 2 when something cannot be read.
- A source file absent at the ref is reported as `file-absent`, which is not a difference.
- A move with `copy_removed = true` is reported as `copy-removed` where the source at the ref matches the working tree, so the answer holds after a squash merge. Where the ref differs, an entry it changed or added is still reported.

### Working with the board

These commands need the project's `[project.work]` settings, described in [The work board](#the-work-board).

#### `vyd board`

```bash
vyd board [folder] [--all] [--fetch] [--state word] [--measure] [--commits] [--here]
```

Where every status record and slice of the project stands, read from the tip of every local and remote branch without a checkout, with what differs from the trunk, which branches moved a slice and any slice claimed twice. Ask it before reading branches.

| Option | Meaning |
|---|---|
| `--all` | every row, not only what differs from the trunk |
| `--fetch` | fetch every remote first, pruning deleted branches |
| `--state word` | only slices whose state starts with this word, such as `building` |
| `--measure` | add each branch's share of content already on the trunk. This is the slow part |
| `--commits` | add the commit that set each printed row |
| `--here` | read the slice families in this one checkout |

- It reads committed tips, so an edit you have not committed is not on it. Read the record itself while preparing a change.
- A claim on another clone appears only after it was pushed and you fetched.
- `--measure` compares content, which is what counts after a squash merge. It is not proof that the work was merged correctly.
- Without work settings it falls back to the slice families of this checkout.

#### `vyd work build`

```bash
vyd work build [--check] [--in folder]
```

Writes the generated region of the project's work index from the status records in the working tree. Text outside the region stays yours.

- `--check` fails when the region is stale and writes nothing.
- Change the status records, never the generated rows.
- It refuses to write for a project whose `vyvid.toml` nobody has trusted.

#### `vyd work roadmap`

```bash
vyd work roadmap [--check] [--fetch] [--in folder]
```

Writes the generated regions of the roadmap, with programme summaries, branches, completed work and dated charts, from every branch a remote knows, read at its remote tip.

- A branch never pushed is left out, and so is a local commit not yet pushed, since the roadmap is committed. The tree being built supplies its own records, under `this checkout` when no remote knows its branch.
- Remotes that share one URL count as one. A second, private remote can still put the names of its branches into the roadmap.
- Use `--fetch` so remote tips are current. `--check` fails when the regions are stale and writes nothing.
- A unit gets a chart of its own once it has five dated slices, or the number `chart_after` sets.

#### `vyd work check`

```bash
vyd work check [--staged] [--in folder]
```

Holds the status records to the ladder and the identifier grammar, and the index's generated region to the records, as a hook runs it. It exits 1 when it has anything to report.

- `--staged` checks only the staged status records, and the region only when a record or the index is staged.
- It takes the names of staged records from the index but reads their text from the working tree, so an unstaged edit in a staged record is what it checks.

#### `vyd work parse`

```bash
vyd work parse <record> [--in folder]
```

Prints a status record's board as `vyd` reads it. Use it when a row does not appear on the board or appears with the wrong state.

#### `vyd work normalise`

```bash
vyd work normalise [--apply] [--in folder]
```

Rewrites every status record's board into the standard columns and state words, and updates a unit's rolled-up status. It reports the changes, and writes them only with `--apply`.

#### `vyd work rename`

```bash
vyd work rename [--apply] [--in folder]
```

Builds the crosswalk from historic slice identifiers and sweeps every mention onto the grammar, as `[[project.work.rename]]` declares. It reports, and writes only with `--apply`.

- It renames only what the project's rename rules declare. It is not a general renumbering tool.

#### `vyd work adopt`

```bash
vyd work adopt [--apply] [--in folder]
```

Brings onto a record's board the slices that its other tables, a Validation Pack or a plan name and the board lacks. It reports, and writes only with `--apply`.

- After applying any of the three, run `vyd work build`, `vyd work check` and `vyd check identifiers`.

#### `vyd here`

```bash
vyd here [--in folder]
vyd here --role build|review|read [--model name] [--on ID,ID] [--leave]
```

Without a role it lists the live sessions in this checkout. With `--role` it writes your presence, so a second session sees that one is already building there.

| Option | Meaning |
|---|---|
| `--role` | write your presence with this role |
| `--model` | the model you run on, written by hand since no client says it |
| `--on` | the slices you are on, separated by commas |
| `--leave` | remove your presence |
| `--now` | the clock as an ISO timestamp, for tests |

- Plain `vyd here` does not register you.
- Presence is advisory and not a lock. It lives for twelve hours after its file was last written, and writing your role again refreshes it.
- The session comes from `CLAUDE_CODE_SESSION_ID` or `AGENT_SESSION_ID`, else from `VYD_SESSION_ID` and `VYD_CLIENT`. Without a distinct identifier, sessions share one file and hide each other.
- The files live in the checkout's git directory unless `presence` names a folder, so git never tracks them and each worktree has its own.
- Writing presence is refused for a project whose `vyvid.toml` nobody has trusted.

### Domains and the knowledge base

#### `vyd domain new`

```bash
vyd domain new <name> [--registers <type>] [--path <folder>]
```

Writes a new domain folder with a manifest, a facet stub, one empty register and a skill stub, initialises git where the folder is not in a repository, and prints the lines that would add it to your configuration.

| Option | Meaning |
|---|---|
| `--registers type` | the register type of its first register, `note` by default |
| `--path folder` | the folder to write, `domains/<name>` under the knowledge base by default |

- It never changes your configuration. Add the domain with `vyd domain add` next.
- The destination must be empty.
- Despite the plural, `--registers` takes one type.

#### `vyd domain add`

```bash
vyd domain add <name> --path <folder> | --remote <url> [--trust own|reviewed|knowledge] [--commit <hash>] [--visibility public|private] [--dry-run]
```

Adds a domain to your configuration, keeping your comments and the order of your tables.

| Option | Meaning |
|---|---|
| `--path` | the domain's folder, `domains/<name>` under the knowledge base by default |
| `--remote` | the repository to clone it from |
| `--trust` | what it gives an agent, `knowledge` by default |
| `--commit` | with `--trust reviewed`, the commit you read |
| `--visibility` | private unless this says public |
| `--dry-run` | print the change and write nothing |

- It writes `trust = "knowledge"` unless you ask for more, so a folder an agent names never gains the standing of your own.
- `own` and `reviewed` need a person at a terminal, since they let the domain's rules and skills reach agents. `--dry-run` works without one.
- A remote is cloned later, by `vyd kb clone`, and the command prints that line.
- The whole new file is checked by the real loader first, and a problem writes nothing and exits 1. When `kb` is unset it says how to set it.

#### `vyd domain trust`

```bash
vyd domain trust <name> own|reviewed|knowledge [--commit <hash>] [--dry-run]
```

Changes the trust of a domain already in your configuration, keeping your comments, without removing and adding it again.

- Raising trust, and moving a reviewed domain to another commit, need a person at a terminal. Lowering it needs none, and moving from `own` to `reviewed` counts as lowering.
- `reviewed` needs `--commit`, 7 to 64 hexadecimal characters, which you name and which is never taken from the clone's head. Moving to `knowledge` removes the commit.
- A reviewed domain gives more than knowledge only while its folder is at that commit, so a pull that moves its head returns it to knowledge until you review again.
- After a raise, run `vyd install --project` in the projects that use it. After a lowering, their skills stay until the next `vyd install --project` removes them.
- It has no `--file`, since a repository's `vyvid.toml` may not set trust.

#### `vyd domain remove`

```bash
vyd domain remove <name> [--dry-run]
```

Takes a domain out of your configuration and says where its folder was left.

- It refuses while a configured project, the `vyvid.toml` of the repository you stand in, or another domain as a parent uses the domain.
- It never deletes the folder or the clone.

#### `vyd domain audit`

```bash
vyd domain audit <folder> [--json] [--allow <scope> ...]
```

Reports the links, file types, paths, command-shaped text, hidden characters and mentions of other scopes in a domain someone else wrote, and runs nothing from it. Use it with the review skill before trusting such a domain.

- It exits 1 when it reports anything, which is common and not a verdict. It states facts and does not certify a domain as safe.
- `--allow` names a scope the domain may cite, such as a parent, and may be repeated.

#### `vyd domain review-path`

```bash
vyd domain review-path <domain> <commit>
```

Prints where the review of a domain at a commit is recorded, a file in Вивід's data folder. The review skill writes its report there.

- A name or a commit that is not safe in a path is refused.

#### `vyd kb status`

```bash
vyd kb status
```

Each managed domain, a git clone of its remote under the knowledge base, with its clone, branch, commits ahead and behind, uncommitted changes, last pull and git policy.

#### `vyd kb clone`

```bash
vyd kb clone [domain ...]
```

Clones the named domains, or every managed domain whose folder is missing. Run it after `vyd domain add --remote` or on a new machine.

#### `vyd kb pull`

```bash
vyd kb pull [domain ...] [--due]
```

Pulls the named domains, or all of them, fast-forward only. `--due` pulls only those whose `pull` policy, `on-start`, `daily` or `manual`, says a pull is due.

- A diverged domain is never merged or stashed for you.
- In a domain you do not own, a pull that changes its rules, skills or manifest is held until a person runs `vyd kb accept`.

#### `vyd kb accept`

```bash
vyd kb accept <domain>
```

A person fast-forwards a domain whose pull was held, after reading the diff that was reported.

- It needs a terminal, and refuses under a task runner that captures output.
- It does not change the domain's trust or its reviewed commit, which stay separate decisions.

#### `vyd kb record`

```bash
vyd kb record <path> ... -m <message>
```

Stages changed register files in their managed domain, then commits and pushes as the domain's `commit` and `push` policy says, `manual` or `auto`.

- It stages nothing in a domain whose files hold what looks like a credential, using `gitleaks` as well where it is installed. That prevents accidents and guarantees nothing.
- `commit_trailers` in `[framework]` are added to every message it commits.
- Use `auto` only where an agent committing and pushing the domain is intended.

#### `vyd docs record`

```bash
vyd docs record <path> ... -m <message> [--in folder]
```

Stages paths in the project's documents folder, when that is a repository apart from the code, then commits and pushes as the project's `git.docs` policy says.

- The policy is set in your configuration, never in a `vyvid.toml`.
- It never touches the code repository.

### Projects and families

The commands below write your own configuration, or with `--file` the `vyvid.toml` of the repository you stand in. Each checks the whole file with the real loader first, keeps your comments and the order of your tables, and with `--dry-run` prints the change and writes nothing. A `vyvid.toml` may not hold a code folder, a remote or a path outside the repository, and changing it lapses its trust until a person runs `vyd trust` again.

#### `vyd project add`

```bash
vyd project add <name> [--code <folder>] [--docs <folder>] [--contract <path> ...] [--remote <url> ...] [--domain <name> ...] [--visibility public|private] [--file] [--dry-run]
```

Declares a project. Run in a git checkout, its code folder and remotes are read from it.

| Option | Meaning |
|---|---|
| `--code` | the code folder, the checkout you are in by default |
| `--docs` | the documents folder, when they are kept apart from the code |
| `--contract` | a rule file, such as `docs:CONTRACT.md`. Repeat for several |
| `--remote` | a remote that identifies the checkout. Repeat for several |
| `--domain` | a configured domain it uses. Repeat for several |
| `--visibility` | `private` by default, the cheaper one to loosen later |
| `--file` | write the repository's `vyvid.toml` instead |

- A remote carrying a password or a token is refused.
- Binding a domain whose trust is `own` or `reviewed` needs a person at a terminal, since its rules and extractors then run for this project.
- `--code` and `--remote` are refused with `--file`.

#### `vyd project set`

```bash
vyd project set <name> <key> <value> ... [--file] [--dry-run]
```

Sets a plain key of a project. A list key takes several values and replaces the list.

- The keys are `docs`, `code`, `visibility`, `docs_visibility`, `doc_share`, `skill_prefix`, `skill_additions`, `domains`, `contract`, `skills`, `facets`, `register_types`, `vocabulary`, `skill_targets`, `hook_clients` and `remote`.
- `skills`, `skill_additions`, `hook_clients` and `skill_targets` change what a client loads or runs, so they need a person at a terminal.
- `moves`, `extractors` and `recipes` are tables, edited by hand. `families` has its own commands.

#### `vyd project remove`

```bash
vyd project remove <name> [--dry-run]
```

Takes a project out of your configuration. Its index store, logs, code folder and documents are left alone.

- With `--file` it is refused, since a command never deletes a `vyvid.toml`. Delete the file yourself.

#### `vyd project scan`

```bash
vyd project scan <name> [--apply] [--file] [--dry-run]
```

Reads the tables in the project's documents and proposes an identifier family for each register, by the signs of the register types its header carries. With `--apply` it writes the proposed families.

- A table it cannot place is named with the reason and never guessed, for example one whose header fits no type or several.
- It proposes a `pattern` only when the identifiers do not fit the default `PREFIX-1`. Read it before applying, since a pattern is what could read ordinary prose as an identifier.
- A family the project already declares is left alone.

#### `vyd family add`

```bash
vyd family add <project> <name> --defined <path> --type <type> [--pattern <regex>] [--removable] [--file] [--dry-run]
```

Declares an identifier family and the register that defines it.

| Option | Meaning |
|---|---|
| `--defined` | the register, as `docs:` or `code:` and a path |
| `--type` | its register type, one the project's register types declare |
| `--pattern` | a regular expression for its identifiers where `PREFIX-1` is not their form |
| `--removable` | its entries are meant to disappear, so an unresolved mention is reported and never failed |

- A definition that leaves the project, by `..`, by a link or by a path outside, is refused.
- The pattern must compile.

#### `vyd family remove`

```bash
vyd family remove <project> <name> [--file] [--dry-run]
```

Removes a family from a project. Its register is left alone.

### Reading another project

A project can read another's knowledge at a pinned commit, in `[project.reads.<name>]` of its `vyvid.toml`. The guide's chapter on reads has the whole of it.

#### `vyd reads status`

```bash
vyd reads status [--in folder]
```

Each read's pin against the source's default branch, whether it gives knowledge alone or was reviewed, what skills, recipes and domains it may bring, and whether its snapshot was made. It exits 1 when a read could not be made, with the reason.

#### `vyd reads pin`

```bash
vyd reads pin <name> <ref> [--in folder] [--dry-run]
```

Resolves a tag, branch or abbreviated hash in your clone of the source to a full commit and writes it into the reader's `vyvid.toml`, keeping the file's comments.

- The commit must be on the source's default branch.
- The source must be a project of your configuration with a code folder.
- The file changed, so its trust lapses, and so does any review of the read.

#### `vyd reads review`

```bash
vyd reads review <name> [--in folder] [--dry-run]
```

A person records, in their own configuration, that they read what a read brings at its pin, so the skills and recipes it lists reach agents and its entries lose the `U` mark. It prints the snapshot's path for each skill, the steps of each recipe and, after an earlier review, the `git diff` command since then.

- It needs a terminal, and a repository can never award itself a review.
- A new pin lapses the review.
- A recipe with a glue step is never carried, and a library's rules, contract, hooks and commands never come with a read.

### The repository catalogue

These read the catalogue that `[project.catalogue]` names, so code and agents ask for a place by name instead of writing a path. Every answer is relative to the catalogue's root unless `--absolute` joins it to the root of the checkout you run in.

#### `vyd catalogue show`

```bash
vyd catalogue show [--in folder]
```

The catalogue's modules, areas and release.

#### `vyd catalogue dump`

```bash
vyd catalogue dump [--in folder]
```

All of the catalogue as JSON, every path relative to the root, for a script.

#### `vyd catalogue modules`

```bash
vyd catalogue modules [--kind <kind>] [--in folder]
```

The modules, one a line, optionally only those of one kind.

#### `vyd catalogue area`

```bash
vyd catalogue area <name> [--absolute] [--in folder]
```

The folder of a named root or documentation area, such as `developer`.

#### `vyd catalogue path`

```bash
vyd catalogue path <module> <role> [--absolute] [--in folder]
```

The folder of one role of a module, such as its `spec`.

#### `vyd catalogue paths`

```bash
vyd catalogue paths <module> <role> [--absolute] [--in folder]
```

The files a module's README generates for a role, in order.

### The guard

The guard keeps the terms of your private lists out of public repositories, at commit and at push. It is configured with `[framework.guard]`, and `vyd install` sets git's global `core.hooksPath` to its hooks. The guide's chapter on the guard has the lists and their formats.

#### `vyd guard status`

```bash
vyd guard status [--in folder]
```

The folder's class, `public`, `private`, `unclassified` or none, the lists in force and their sizes, and whether the git hooks are in place.

#### `vyd guard check`

```bash
vyd guard check [--all] [--in folder]
```

Checks the lines staged for commit against the lists, or with `--all` every tracked file, which finds what a new list leaves in existing text. It exits 1 on a blocking finding.

- A finding names the file, the line and the list entry's line number, and never the term, so a log you share does not repeat it.

#### `vyd guard hook`

```bash
vyd guard hook pre-commit|commit-msg|pre-push [args ...]
```

What the git hooks run. `pre-commit` reads the lines and paths a commit adds, `commit-msg` reads the message and, in a public repository, requires a `Placement:` trailer on a commit touching a sensitive path, and `pre-push` reads each commit the push carries that the destination does not already hold. Call it yourself only from hooks of your own, where another `core.hooksPath` is set.

- A repository under a watched owner that is in neither list stops until it is classified.
- `--no-verify` skips the commit hooks and not the push check.
- Only the maintainer overrides it, for one command, with `VYD_GUARD_SKIP="<reason>"`, which is logged with the reason. An agent that is stopped reports the findings by file and line and proposes a conforming change.
- What the destination holds is read from the remote-tracking refs of every remote that names that repository, as of the last fetch or push.

### Cloud environments and stores

#### `vyd cloud script`

```bash
vyd cloud script --output <file> [--domain name[=~/path] ...] [--grant host/owner/repository ...] [--run path] [--dry-run]
```

Writes the setup script for a cloud environment. It installs `vyd` at the running version, embeds the files of the private domains you name, clones the public domains, writes a configuration, runs `vyd install`, and with `--run` ends by running a setup script of the project's own from the session's checkout.

| Option | Meaning |
|---|---|
| `--output` | the file to write, readable by you alone |
| `--domain` | a private domain to embed, and after `=` where to write it under `~/` in the cloud. Repeat for several |
| `--grant` | a repository whose `vyvid.toml` the cloud trusts, in `trusted_repositories`. Repeat for several |
| `--run` | a setup script inside the project's repository, run last |
| `--dry-run` | say what would be written and write nothing |

- The script holds private text, so it is written to a file and never printed. The command prints only the path, the size against the 64 KB limit of a setup script, a fingerprint and a line for each domain.
- Only the domains you name are embedded, never every private domain. Each must be a git repository, and only the files git tracks are carried.
- Anyone who can use the environment can read its setup script, so paste it only into an environment nobody else uses, and paste it again after a domain changes.
- In the cloud, the skills of an embedded domain that declares no `always_rules` are always on, whatever they do on your own machine. A domain that declares `always_rules` keeps exactly those.
- `--run` takes a plain path of letters, digits, `.`, `_`, `-` and `/`, and the script says in setup's output when no checkout holds it.

#### `vyd store prune`

```bash
vyd store prune [--dry-run]
```

Removes the index stores of linked git worktrees that no longer exist. `--dry-run` lists them and removes nothing.

### `vyd-hook`

`vyd-hook` is the reminder hook that `vyd install --project` registers for each client in `hook_clients`, and you do not run it yourself. When an agent searches through a shell or a search tool before it has asked the index in that session, or after fifteen searches since it last asked, it reminds the agent to ask.

- It reminds and never refuses, and a failure inside it says nothing, since in some clients an error in a hook would deny the tool.
- It runs before a tool call in Claude Code and Codex, and after one in Copilot.
- Where `vyd-hook` is not installed, the registered command does nothing.

## Setting up without editing TOML

Everything the configuration holds can be written by hand, and a file edited by hand stays as it is. The commands in [Projects and families](#projects-and-families) and [Domains and the knowledge base](#domains-and-the-knowledge-base) write it for you when you would rather not. Each checks the whole file with the real loader before it writes, keeps your comments and the order of your tables, and takes `--dry-run`, which prints the change and the file it would write and writes nothing. They write your own configuration, or with `--file` the `vyvid.toml` of the repository you are in, which may not hold a code folder, a remote or a path outside the repository.

```bash
cd ~/work/some-project
vyd domain add tools --remote https://github.com/example/vyvid-tools
vyd kb clone tools
vyd project add some-project --docs ~/work/private-docs/some-project --contract docs:CONTRACT.md --domain tools
vyd project scan some-project --apply
vyd config
vyd build
```

`vyd domain trust tools own` raises a domain you added as knowledge, or `vyd domain trust tools reviewed --commit <hash>` for one you read, so you need not edit the file or add the domain again. A command never records trust and never deletes a folder, a clone or a store. Trust `own` or `reviewed`, and any change that reaches what a client loads or runs, needs a person at a terminal, as `vyd trust` does. [docs/GUIDE.md](docs/GUIDE.md) has the same steps in full.

## The work board

A project keeps one status record per unit of work, each with a board of slices whose state is a word of a ladder and the day it was reached. `vyd board` reads those boards at the tip of every local and remote branch without a checkout, joins them per slice, and prints where everything is, what differs from the trunk, which branches moved a slice, and any double claim. Another branch's files are read as data, and nothing in them is run or used as a path. `vyd work` writes the generated regions of a project's index and roadmap, the roadmap from the branches a remote knows at their remote tips and never from a local-only branch, checks the records for a hook, and moves older boards onto the standard shape. `vyd here` keeps one small file per session, in the checkout's git directory unless the project names a folder, so a second session sees that one is already building there. The session comes from `CLAUDE_CODE_SESSION_ID` or `AGENT_SESSION_ID`, and from `VYD_SESSION_ID` and `VYD_CLIENT` for a client that sets neither.

Every key of the `work` table is optional, and a project with the table gets a `status` and a `plans` folder under its documents.

```toml
[project.work]
status = "docs:work/records"         # default docs:status
plans = "docs:work/briefs"           # default docs:plans
index = "docs:work/board.md"        # the file holding the generated region
roadmap = "docs:work/programme.md"    # the file holding the generated regions
validation = "docs:work/packs" # also sketches, reviews, decisions, crosswalk and sweep
levels = ["epic", "unit", "slice"]       # largest first, and the last two name a record and a board row. Default unit, slice
ladder = ["planned", "briefed", "building", "built", "verified", "merged", "tagged"]
aside = ["blocked", "dropped"]           # a held word and a dropped word
main = "main"
presence = ".local/agents"               # default a folder in the checkout's git directory
slice_pattern = '[A-Z]{2,5}-\d+[a-z]?'    # what a slice identifier looks like
```

A word of the ladder is dated from `dated_from`, which is the third word unless the project names another, counts as done from `done_from` and as closed from `closed_from`. The text of the generated regions' markers is `markers`, and the commands the messages name are `commands`, both defaulting to `vyd work`. `[[project.work.rename]]` declares how a unit's historic identifiers cross to the grammar. A repository's own vyvid.toml may name only paths inside the repository, and a command that writes refuses a project declared by a vyvid.toml nobody has trusted with `vyd trust`.

## Skills that reach an agent

A domain ships `skills/<name>/SKILL.md`, the format Claude Code and VS Code both read. A project's `vyvid.toml` says what it uses, and `vyd install --project` composes each skill and writes it into the checkout, under `.claude/skills` unless `skill_targets` says otherwise, to be committed. Every clone and worktree then has its skills, and so does a contributor without `vyd`. `vyd check skills` fails when a committed skill differs from what its sources compose to.

A project adds to a domain's skill with `.vyvid/skills/<domain>/<skill>.md`. Text under `## A heading` joins the domain's section of that name, `## A heading (replace)` takes its place, and a new heading follows at the end. Its front matter may give its own `description`. `{{name}}` in a skill is filled from the project's `skill_values`, then the domain's, and a value nobody gives stops that skill being written. `skill_prefix` sets how the skills are named, and a project's own skills, in the folders its `skills` names, are composed the same way.

```toml
[project]
skill_prefix = "acme-"
skill_values = { status = "docs/status", ask = "vyd find" }
skill_targets = [".claude/skills", ".github/skills"]
hook_clients = ["claude-code", "copilot", "codex"]
```

Every generated skill opens on the same block, kept in one place, saying to ask the index before any decision and any search, and naming the registers to ask. A composed file names no folder of one machine, and a private domain's skills are never composed into a checkout, since they would be committed. They go to the user's folder. A client prefers a personal skill to a project's of the same name, so `vyd install --client` writes a skill to the user's folder only for a private domain or one whose entry says `user_skills = true`, whether or not a configured project uses it, and a public domain a project uses is left to that project's composed skills. `vyd check skills --from old/SKILL.md --map map.tsv` fails on any line of an old skill that is in no composed skill and no row of the map, so a move loses nothing.

`vyd install` with no options sets up every client whose folder exists, Claude Code's `~/.claude` and Copilot's `~/.copilot`, and is safe to run again. It writes the core skills, and the skills of each private domain and of each domain whose entry says `user_skills = true`. A public domain otherwise reaches an agent through the skills composed into a project, so it never sits beside them. A domain's `always_rules` go where a client loads rules in every session, in Claude Code's `rules` folder, and Copilot's documents give no such folder for a user. A domain's `skill_prefix = ""` keeps each skill's folder name. `vyd config` says when what is installed is out of date.

A machine lists the domains it has. A domain that is listed with no folder gives nothing and is named by `vyd config` and `vyd install`, and any skill already installed from it stays. A `vyvid.toml` naming a domain this machine does not configure leaves it out with a note. Since a private domain is never composed into a checkout, a machine without it gets the same committed skills. `vyd install --project` writes and removes nothing while a domain its project uses is missing, and `vyd check skills` then exits 2 and says it did not run. It exits 2 likewise where no project claims the folder or its `vyvid.toml` is not trusted, so a hook can tell a check that did not run from one that failed.

`vyd install --project` also registers `vyd-hook` with each client in `hook_clients`. It runs before a tool call in Claude Code and Codex, and after one in Copilot, whose documents give a hook no way to add context before one. When a search runs in a shell, Bash or PowerShell, or through a search tool, before any index question in that session, or after 15 searches since the last, it reminds the agent. It never refuses, and a failure in it says nothing. It has been run in Claude Code and in Copilot in VS Code, where the agent quoted the reminder after its search. Codex has not been run. Where `vyd-hook` is not installed, the registered command does nothing.

A domain gives knowledge alone unless its entry in your configuration says `trust = "own"`, or `trust = "reviewed"` with the `commit` you reviewed. A domain with a remote is knowledge by default and one with none is your own. A knowledge domain installs no rules or skills, its results are labelled as data, and a pull that changes its rules, skills or manifest is held until you run `vyd kb accept`. A configuration at a path other than your own, such as one named by `VYVID_CONFIG`, runs no glue and no command extractor until you run `vyd trust` in a terminal, and again after it changes.

A cloud session has no terminal for `vyd trust`. Listing a repository in `[framework] trusted_repositories` in your own configuration trusts that repository's committed `vyvid.toml` there, while its `origin` is the listed one and the file holds the committed bytes. No other file or environment variable can grant it, and an uncommitted edit lapses it. A hostile branch of a listed repository is trusted, so list only a repository you control, on a machine set up for that. The guide has a setup script for a cloud environment. When the automatic build cannot make embeddings it prints why on standard error, and a `find` retries it once the store is ten minutes old, unless the build was told not to embed.

A project specialises a domain by keeping a register of the domain's register type in its own documents, such as a `note` register for the Tools domain, and by naming the domain's row in a row's `Specialises` column, qualified with the domain, as `tools:NOTE-1`. In a folder of the project `vyd find` ranks the project's row above the domain's and shows the domain's beneath it, and a row the project `Overrides` is shown only when its scope is named. A `vyvid.toml` that names a domain you have not configured does not set its project aside. `vyd context` and `vyd build` print a note, the domain is left out of the stack for that run, and a `Specialises` cell naming it stays unresolved. A project entry in your own configuration that names an unknown domain is still an error.

A project can keep its code in one folder and its documents in another. When `docs` lies outside `code`, the documents are private unless the entry says `docs_visibility = "public"`. An entry defined in a file there is labelled private by `find`, and `vyd check citations` refuses a line of the code repository that cites it, bare or qualified, in a staged change or in a commit message or pull request text given with `--message`. Nothing is written into the code repository. `git = { docs = { commit = "manual", push = "manual" } }` in your configuration, and never in a `vyvid.toml`, sets what `vyd docs record` does with the documents. A linked worktree of the code repository is answered from its own code and the same documents.

A repository can declare its own project, with no entry in your configuration, in a `vyvid.toml` at its root. It holds what a `[[projects]]` entry holds, under `[project]`, and the repository's folder is the project's code folder.

```toml
[project]
name = "vyvid"
visibility = "public"
docs = "code:docs"
contract = "docs:contract.md"
register_types = ["docs:register-types.toml"]

[project.families]
STD = { defined = "docs:standards.md", type = "standard" }
```

The file is found at the git toplevel of a folder, or above it where the folder is not in git, and every checkout of the repository reads its own copy. It binds the folders inside it ahead of a remote, and a configured project that holds the folder more deeply still wins. An entry of the same name in your configuration overrides the file's keys one by one. It comes from whoever wrote the repository, so it may not set `code`, `git`, `remote`, `trust` or `match`, and every path it names must stay inside the repository, even through a link. A file that breaks this sets aside its project and gives the folder the general scope, and `vyd config` lists why. Until you run `vyd trust` in the repository, the project gives knowledge alone, as a knowledge domain does: its contract and skills are withheld, its entries are labelled as data and none of its glue or command extractors runs. To work on this repository, run `vyd trust` there, then `vyd context .` prints its contract.

A project that gave a family, or some rows of one, to a domain declares it with `[[projects.moves]]` in your configuration (see `examples/config.toml`). Its mentions then resolve through the domain with no rewriting of its text, `vyd resolve` prints the canonical target, and the project's copies leave the index. Once the project has removed its copy, a move may set `copy_removed = true`, and `vyd move check` then reports it as `copy-removed` instead of comparing it, whether with no ref or with a ref whose source file is identical to the working tree's. With a ref that differs, it still reports an entry the ref changed or added, and drops one the ref removed. A domain may cite itself, its ancestors and the general scope alone, and a build reports a domain that cites a project or any other domain.

`vyd check identifiers` reads the Markdown that `git ls-files` lists in the project's repository, never a folder walk, so an ignored folder is not read. A mention resolves on a normalised key, so another spelling of a defined identifier is a variant and is reported. A family with `removable = true` has its unresolved mentions reported and never failed. A family's `exceptions` file, or `identifiers.exceptions` for the project, lists identifiers mentioned and defined nowhere, one per line with a reason after `#`, and an entry nothing needs any longer is reported as stale. An identifier a family defines twice fails, and the line committed earlier keeps the number. A mention covered by a move resolves only if the domain defines it. A family with `defined_only = true` reads a bare match of its pattern as a mention only where its source defines the identifier, so a loose pattern does not read `UTF-8` as an entry. The exit code is 1 on an unresolved or twice-defined identifier and 0 otherwise, and `--json` prints everything found.

A register type declared with `shown = "asked"` is left out of `find` unless `--kind` names it or the question names an entry by its identifier, as declared terms are. The packaged `slice` type is one, and reads a board of `Slice`, `Deliverable`, `State` and `Blocked on`.

A backlink ties code to the entry it implements. It is a comment in a tracked file that is not Markdown, holding `@vyd:` and then identifiers separated by commas, to the end of the line, for example `# @vyd: STD-1, tools:TOOL-2`. `vyd check links` reads the files `git ls-files` lists and fails on a backlink that no register defines, and on a pointer of one of the project's own entries that names a file that is not there or a line past its end. Only a marked line is checked, since code and its tests hold text that merely looks like an identifier. `--require <family>` also fails on an entry of that family that no backlink names, so every capability, for example, can be held to a place in the code. `vyd refs <identifier>` lists every tracked line that writes an identifier and says whether it defines, backlinks or mentions it. `vyd expand` prints a prompt followed by the kind, status, claim and pointer of every identifier it mentions, so an agent is handed what the identifiers mean and not only their names.

`vyd mcp` serves the same questions to an editor or an agent client over standard input and output, as the Model Context Protocol tools `context`, `find`, `node`, `read`, `reaches`, `refs` and `expand`. Register it as a command, for example `claude mcp add vyvid -- vyd mcp`. Each call runs `vyd` as a process of its own in the folder the server was started in, or the one `--in` names.

The repository is also a GitHub Action that runs the identifier and link checks with no Python set up by you. It installs `vyd` from the tag you name, builds the index without vectors, and fails the job where a check fails.

```yaml
- uses: actions/checkout@v4
- uses: nebularis/vyvid@<tag>
  with:
    checks: identifiers links   # the default
    require: CAP                # optional, families whose every entry needs a backlink
```

## Code

A project asks for its source to be searched by declaring what to parse, in its entry or its `vyvid.toml`. The grammars are the optional extra `vyvid[symbols]` (`uv tool install "vyvid[symbols]"`), and without it `vyd` goes on and says so.

```toml
[[project.symbols]]
language = "haskell"   # python, haskell, java or typescript
paths = ["code:packages/*/src/**/*.hs"]
```

`vyd build` parses the files `git ls-files` lists, and only those whose content changed since the last build, into `symbols.sqlite` beside the index. Nothing in the clone runs, so symbols work before a `vyvid.toml` is trusted, and a symbol of an untrusted project is labelled as data like any other entry. No symbol enters the graph. `vyd find <words> --kind symbol` ranks every symbol by meaning, with a name written as camelCase or snake_case in the question first, and prints the identifier `package:Module.name`, its kind, module and `file:line`, with the signature and the first line of the doc beneath. It also searches the prose around the code, which is not on any symbol: a module header, a `-- $name` section or a `{- ... -}` block comment in Haskell, a module docstring or a run of `#` lines in Python, and a file's opening comment in Java and TypeScript. These are cut at `[Heading]` lines and into windows of about 900 characters, a licence and metadata lines are left out, and each is a row of kind `doc` with the identifier `package:Module#heading`, the heading and the start of its text beneath. At most two of five places go to them, so a symbol that answers is not pushed out. Plain `find` shows no symbol and no such text, and says in one line when symbols match strongly. A text may name a symbol by its identifier, and `vyd check identifiers` reports one that no longer exists without failing.

Documentation shares the places of an answer with symbols, by cosine and up to a cap. `doc_share` sets that cap, from 0 (symbols alone) to 1 (no cap), at 0.4 unless set. `--doc-share` on the question overrides `doc_share` in the project's entry, and that overrides `[framework]`.

Who calls a name is a question for a compiler's index, which Вивід does not build or run. A project registers the one it has, and `vyd handoff` prints the exact commands to ask it, after checking that its database exists and holds rows.

```toml
[[project.code_index]]
kind = "hiedb"                       # the only kind with commands so far
database = "code:.build/hie.db"
built_by = "mise run build:index"    # shown as text, and withheld until the vyvid.toml is trusted
sources = "code:packages/*/src"      # newer than the database means it may be stale
```

`vyd context` lists each registered index. The commands come from templates in Вивід, and the file supplies only a quoted path.

A project can bring its own extractor as a command, in any language, so each git worktree indexes with its own version and nothing is installed into Вивід. Only a project's entry in your own configuration, or a `vyvid.toml` you have trusted, declares one.

```toml
[[projects.extractors]]
kind = "my-extractor"
command = ["mise", "exec", "--", "python", "-m", "tools.my_extractor"]
paths = ["docs:notes/*.md"]   # the files it reads, which decide when the index is stale
code = ["code:tools/my_extractor.py"]   # its own files, which also decide when the index is stale
```

It runs in the checkout's root with a minimal environment, `seconds` (default 300) as its time limit and the variables `env` names. It reads one JSON request on standard input, with its settings, the expanded `paths`, an output folder and the two graph IRIs it may write to. It writes `quads.nq` (N-Quads in those graphs) and `result.json` (problems, findings, texts to embed, prefixes, counts, units and an optional version). `units` maps a name to the units it stands for, and an `Owner` or `Provided by` cell that names one becomes an edge to each, while a name no extractor declared is reported and kept as written. `unit_paths` maps a repository folder to a unit, so a term `owl-terms` finds under it is owned by that unit, the longest path winning, and otherwise by the folder of its document. All of this goes into the output folder. A failure is reported and costs only its own entries.

A managed domain is a domain whose folder lies under the knowledge base, and it is a git clone of its `remote`. Its `git` policy sets when it is pulled (`on-start`, `daily` or `manual`), and whether a recorded change is committed and pushed (`auto`) or left staged (`manual`), and `commit_trailers` in `[framework]` are added to every commit `vyd kb record` makes. A pull never merges or stashes, and `vyd context` pulls what is due before it answers unless given `--no-pull`. A project's own files are never committed or pushed by `vyd`. `vyd kb record` stages nothing in a domain whose files hold what looks like a credential, using `gitleaks` as well when it is installed, which is optional.

`vyd` writes the questions it is asked and cannot answer to logs beside the index, which `misses` and `gap` read. Set `logs = false` in `[framework]` to write none, or pass `--no-log` to `vyd find` or `vyd read` to write nothing for that call, as a benchmark does.

The configuration is read from `$VYVID_CONFIG`, or from the platform's configuration folder, which `vyd config` prints. [`examples/config.toml`](examples/config.toml) is a starting point.

## Licence

[MIT](LICENSE)
