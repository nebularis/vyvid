# User Guide

## Vyvid: from first setup to an agentic development lifecycle

Vyvid gives coding agents a searchable, project-scoped body of knowledge: rules, decisions, findings, questions, skills, and references into source code. Its command-line tool is **`vyd`**.

The essential division is:

- **Your source files are authoritative.** Registers, contracts, plans, skills, and code remain ordinary files that you review and version.
- **Vyvid derives context from those sources.** It resolves identifiers, builds indexes, ranks relevant entries, and composes instructions for agent clients.
- **Domains provide reusable knowledge and procedures.** A project selects domains and adds its own specialisations.
- **The lifecycle domain provides a development procedure.** Vyvid’s work-board commands support that procedure, but do not autonomously implement, verify, or deliver your software.

This guide describes the implementation at version **0.2.16**, inspected on **7 November 2026**. Examples use a fictional project named `example-service`. Replace its paths, commands, and identifiers with your own.

---

## 1. Understand the components

### Registers

A register is a Markdown table containing individually addressable entries.

For example:

```markdown
| ID | Claim | Problem shape | Activity | Ratified |
|---|---|---|---|---|
| STD-1 | **Reject invalid input before changing stored data.** | validating requests before persistence | api-and-contract-design, unit-testing | yes |
```

Here:

- `STD-1` identifies the entry.
- `Claim` states what the reader needs to know.
- `Problem shape` describes when the entry matters.
- `Activity` helps retrieve it for relevant tasks.
- `Ratified` distinguishes accepted guidance from proposals.

**The table header is its schema.** Columns must be declared by Vyvid’s packaged register types or by a domain or project extension. An arbitrary new column does not automatically acquire meaning.

### Facets

Facets are controlled vocabularies used to describe entries. Vyvid packages three schemes:

| Scheme | Describes | Search option |
|---|---|---|
| Activity | What someone is doing | `--activity` |
| Quality | What characteristic matters | `--quality` |
| Technology | What technology the entry concerns | `--tech` |

Facets are represented as SKOS concepts, including broader and related concepts. Domains and projects can extend the packaged vocabulary.

### Domains

A domain is a folder containing a `domain.toml` manifest and some combination of:

- Registers.
- Facet extensions.
- Rules.
- Skills.
- Query recipes.
- Register-type declarations.
- Vocabulary extensions.
- Declarations using installed extractors.

A domain can live in its own repository, inside another repository, or elsewhere on your machine.

Domains may declare parent domains. Together, they form a **directed acyclic graph**: parents are included before their children, and cycles are invalid.

### Projects

A project binds a codebase to its documents, contract, domains, identifier families, and optional work settings.

A project can be declared:

- In a repository-root `vyvid.toml`, so its public configuration travels with the repository.
- In your user configuration, for machine-specific paths and preferences.
- In both, with the matching user entry overriding the repository file’s keys one by one. A key the user entry sets replaces the file’s value for that key whole, so a `families` table in the user entry replaces every family the file declares instead of merging with them.

### The index

The index is derived data, not another source of truth.

It combines configured register entries, decisions, questions, facets, and extractor output. Optional symbol indexing supplies a separate source-code search surface.

**Vyvid does not automatically index every paragraph of every document in your repository.** You declare which sources define knowledge and how they should be extracted.

---

## 2. Install Vyvid

### Prerequisites

You need:

- Python **3.11 or later**.
- Git.
- `uv`, for the installation examples below.
- Network access to obtain dependencies and, on first semantic use, the embedding model.

The commands below assume a POSIX-style shell. Configuration is TOML on every platform, and on Windows you use the corresponding shell syntax for environment variables.

### Install from source

At the time this guide was checked, `vyvid` was not available from PyPI. Use its Git source rather than assuming `uv tool install vyvid` will work.

Install the command-line tool:

```bash
uv tool install "git+https://github.com/nebularis/vyvid.git"
```

For source-code symbol search, install the optional grammars:

```bash
uv tool install \
  "vyvid[symbols] @ git+https://github.com/nebularis/vyvid.git"
```

These are alternative installations of the same tool. If you already installed it and are changing the source or extras, reinstall with `--force`.

For reproducible environments, select a reviewed tag or commit:

```bash
uv tool install \
  "vyvid[symbols] @ git+https://github.com/nebularis/vyvid.git@<tag-or-commit>"
```

Replace `<tag-or-commit>` before running the command.

Check the installation:

```bash
vyd --version
vyd --help
```

If your shell cannot find `vyd`, check that uv’s tool executable directory is on `PATH`. The same installation provides a second command, `vyd-hook`, which the reminder hooks described later in this guide run. You do not call it yourself.

### Use an editable checkout

An editable installation is useful when developing Vyvid itself:

```bash
git clone https://github.com/nebularis/vyvid.git
cd vyvid
uv tool install --editable .
```

Or, with symbol support:

```bash
uv tool install --editable ".[symbols]"
```

An editable tool runs that working tree. Changing branches or editing its source changes the tool you are running.

### Understand the first model download

Semantic retrieval uses a local ONNX embedding model. The default is `BAAI/bge-small-en-v1.5`, pinned by revision and file hashes.

The model is downloaded into the platform cache on first use. Embedding and ranking then run locally, so Vyvid does not require a hosted embedding service.

To build the graph without producing embeddings:

```bash
vyd build --no-embed
```

This is useful for inspecting extraction problems, but it does **not** make semantic search available. Queries can also trigger a normal rebuild when the index is missing or stale.

---

## 3. Configure your knowledge base

### Find your configuration file

Run:

```bash
vyd config
```

Vyvid reads:

1. The file named by `VYVID_CONFIG`, if set.
2. Otherwise, `config.toml` in its platform-specific user configuration directory.

The file may be saved with a byte order mark or as UTF-16, as Windows editors and PowerShell often do, and `vyd` reads it all the same. A command that changes it writes UTF-8.

Use the path reported by the command rather than assuming a particular operating-system layout.

The file at that default path is your own configuration, and Vyvid trusts it as it stands. A configuration read from any other path, such as one named by `VYVID_CONFIG`, runs no glue and no command extractor until a person runs `vyd trust` in a terminal, and again after the file changes. The `configuration trust:` line of `vyd config` says which case applies.

The user configuration and a project’s `vyvid.toml` serve different purposes:

| File | Put here |
|---|---|
| User configuration | Knowledge-base location, domain remotes, trust, update policies, personal paths, private project bindings |
| Repository `vyvid.toml` | Portable project configuration, public domains used, register families, work settings, symbol paths, skill composition |

The `[framework]` table in the user configuration holds settings for Vyvid itself. This guide introduces `kb` here, `glue` with recipes, `logs` and `store` with the graph and its logs, `commit_trailers` with domain maintenance, and `doc_share` with source search.

### Understand text encodings and pipes

Output keeps the encoding of the stream it goes to, so a program that reads `vyd` in a code page gets text in that code page. Vyvid does not force UTF-8 on a redirected stream. What it changes is that a character the stream cannot hold, or an argument whose bytes do not decode, is written as an escape such as `\u0456` and never ends the command with a traceback. A program that needs exact UTF-8 asks for it with `PYTHONIOENCODING=utf-8`, and a person who chooses the error handling with `PYTHONIOENCODING=<encoding>:<errors>` keeps their choice.

The name prints as `Вивід` where the output can hold it and as `vyvid` where it cannot, for example in a Windows console on the code page 437 or in a pipe in code page 1252. `vyd --version` always ends in the bare version number.

What Vyvid reads is fixed, whatever the locale. Output from `git` and from the commands you register as glue or command extractors is read as UTF-8, and a byte that is not valid there is replaced rather than failing the command. The request sent to a command extractor is UTF-8. Your configuration, a `vyvid.toml`, a `domain.toml` and a register type file are read as UTF-8, with or without a byte order mark, or as UTF-16. A file in any other encoding, such as one saved in a Chinese, Japanese, Korean or Cyrillic code page, is reported as a problem that names the file. Save it as UTF-8, for example with `Set-Content -Encoding UTF8` in PowerShell. Standard input is read as UTF-8 by `vyd-hook`, which prints no decision and exits 0 for input it cannot use. A prompt that meets invalid bytes or the end of the input counts as no.

A program that stops reading, as `head` does, ends the command quietly with status 141 on a POSIX system and 1 elsewhere. Notes and problems go to standard error and results to standard output, so a pipe carries only the results.

### Configure the published domains

The following user configuration declares all the domains discussed in this guide:

```toml
[framework]
kb = "~/work/vyvid-kb"
glue = "stop"

[[domains]]
name = "lifecycle"
remote = "https://github.com/nebularis/vyvid-lifecycle.git"
trust = "knowledge"
git = { pull = "manual", commit = "manual", push = "manual" }

[[domains]]
name = "tools"
remote = "https://github.com/nebularis/vyvid-tools.git"
trust = "knowledge"
git = { pull = "manual", commit = "manual", push = "manual" }

[[domains]]
name = "rdf-modelling"
remote = "https://github.com/nebularis/vyvid-rdf-modelling.git"
trust = "knowledge"
git = { pull = "manual", commit = "manual", push = "manual" }

[[domains]]
name = "triple-stores"
remote = "https://github.com/nebularis/vyvid-triple-stores.git"
trust = "knowledge"
git = { pull = "manual", commit = "manual", push = "manual" }

[[domains]]
name = "python"
remote = "https://github.com/nebularis/vyvid-python.git"
trust = "knowledge"
git = { pull = "manual", commit = "manual", push = "manual" }

[[domains]]
name = "haskell"
remote = "https://github.com/nebularis/vyvid-haskell.git"
trust = "knowledge"
git = { pull = "manual", commit = "manual", push = "manual" }
```

You do not need every domain. Remove entries you do not intend to use.

Unless a domain entry supplies `path`, its folder is:

```text
<framework.kb>/domains/<domain-name>
```

Clone the missing managed domains:

```bash
vyd kb clone
vyd kb status
vyd config
```

Or clone selected ones:

```bash
vyd kb clone lifecycle tools
```

Declaring a domain is not the same as having its files locally, and having its files is not the same as trusting its instructions.

### Review before enabling instructions

Domains can influence an agent’s behaviour. A rule or skill is executable in the practical sense that an agent may act on it.

Vyvid distinguishes three trust modes:

| Mode | Meaning |
|---|---|
| `knowledge` | Searchable data, not trusted instructions |
| `reviewed` | Instructions enabled while the domain’s HEAD matches the reviewed commit |
| `own` | Your own domain, whose instructions you accept without a reviewed-commit restriction |

A domain with a remote defaults to `knowledge`. A domain without a remote defaults to `own`, though you should not rely on that default for someone else’s files.

Inspect a domain without running anything from it:

```bash
vyd domain audit ~/work/vyvid-kb/domains/lifecycle
git -C ~/work/vyvid-kb/domains/lifecycle rev-parse HEAD
```

Read its manifest, rules, skills, and other relevant files. The audit reports facts such as links, command-shaped text, hidden characters, paths, and mentions of other scopes, but it does not certify safety. `--json` prints the same facts as JSON, and `--allow <scope>` (repeated for several) names a scope, such as a parent, that the domain may cite.

After reviewing, change that domain’s existing configuration entry:

```toml
trust = "reviewed"
commit = "<the-commit-you-reviewed>"
```

Use a real commit hash, preferably the full hash. This is a change to the existing entry, not a second `[[domains]]` entry with the same name. `vyd domain trust` makes the same change for you, as the next section explains.

**Reviewed trust is not a checkout pin.** It enables instructions when HEAD matches the configured commit. If HEAD moves, the domain falls back to knowledge-only standing until you review the new revision and update your configuration.

### Add domains without editing the file

Every entry in this section can be written by hand, and a hand-edited configuration stays as valid as it ever was. The commands below exist for the moments when you would rather not remember each key, or when an agent is setting up a project for you and you want it to use a path that is checked before anything is written.

```bash
vyd domain add tools --remote https://github.com/example/vyvid-tools
```

**What it writes, and where.** One `[[domains]]` entry, appended to your user configuration, the file `vyd config` names. If the file does not exist yet, the command creates it, and the folder around it if that is missing, readable by you alone. The rest of the file is left as it was, comments and the order of your tables included. The command prints the lines it adds as a diff, and the path of the file it writes, before it writes them.

**Why it checks first.** The new text of the whole file is loaded by the same loader `vyd config` uses before anything reaches the disk. If that finds a problem, such as a name that exists, a parent that is no domain, a remote that carries a password, or a manifest in the folder that sets something only you may set, the command lists every problem, writes nothing, and exits with 1. The file is then replaced whole, in UTF-8 with no byte-order mark and `\n` line endings, and keeps the permissions it had.

| Option | Meaning |
|---|---|
| `--path <folder>` | The domain's folder. Without it, and with a knowledge base configured, the folder is `domains/<name>` under it |
| `--remote <url>` | The repository the domain is cloned from |
| `--trust own\|reviewed\|knowledge` | What the domain may give an agent. The default is `knowledge` |
| `--commit <hash>` | With `reviewed`, the commit you read |
| `--visibility public\|private` | A domain is private unless you say it is public |
| `--dry-run` | Print the change and write nothing |

**Trust is always written, and defaults to knowledge.** The loader gives a domain without a remote the standing `own`, since it assumes you wrote it. A command that wrote nothing about trust would hand that standing to any folder an agent named, so this one writes `trust = "knowledge"` unless you ask for more. A knowledge domain gives its entries to the index and nothing that instructs an agent, so `vyd install --project` leaves its skills out and prints a note saying so. When you want a domain's skills in a project, add it with `--trust reviewed --commit <hash>` once you have read it, or with `--trust own` if you wrote it. A domain already in your configuration does not need removing and adding again. Raise it later with `vyd domain trust`, as in `vyd domain trust tools own`.

**Raising trust needs a person.** `--trust own` and `--trust reviewed` make a domain's rules, skills and recipes reach agents, so they are refused unless standard input is a terminal, which is the check `vyd trust` makes. The message says that a person must run the command. This is a speed bump and not a proof, since an agent can be given a pseudo-terminal, and an agent that can run commands as you can also edit the file, so your client's permission settings remain the control that matters. `--dry-run` is not refused, so an agent can show you exactly what it would ask you to run.

**A remote is not cloned by this command.** Cloning contacts a network and then falls under the domain's git policy, which `vyd kb` manages. When the folder does not exist, the command prints the command that clones it, such as `vyd kb clone tools`, and stops there. A path given without a remote is a folder you made or cloned yourself, and the command says so if it is missing.

To change the trust of a domain that is already configured:

```bash
vyd domain trust tools own
vyd domain trust tools reviewed --commit 3f9c2ab
vyd domain trust tools knowledge
```

**Why it exists.** A domain added without a trust is a knowledge domain, and that gives no skills. Before this command the only ways to raise it were to edit the file by hand or to remove the domain and add it again, which is awkward when projects already use it, since `vyd domain remove` refuses while they do. The command changes the trust of the entry that is there.

**What it changes.** The `trust` line of that entry and, for `reviewed`, its `commit` line, and nothing else. Your comments and layout stay as they are. A `trust` line written in an unusual place stays where it is, and an entry with no `trust` line gets one. Moving to `knowledge` removes the `commit` line, since only a reviewed domain takes one. The whole file is loaded by the real loader before it is written, as for `domain add`, and a refusal writes nothing. When the domain already has that trust and commit, the command says so, writes nothing and exits 0.

**What needs a person.** Moving to `own` or `reviewed` from anything lower, and moving a `reviewed` domain to a different commit, make more of the domain reach agents, so they are refused unless standard input is a terminal, with the message `domain add --trust own` gives. `--dry-run` works without a terminal and says that a person must run it for real. Taking standing away needs no terminal, which covers moving to `knowledge` and moving `own` to `reviewed`. The second counts as lowering because a reviewed domain gives what an own domain gives only while its folder is at the commit you named, and gives knowledge alone at any other, so it can never give more than own does. Moving `reviewed` back to `own` is a raise.

**The commit is always yours to name.** `reviewed` needs `--commit`, in the form the loader requires, which is 7 to 64 hexadecimal characters. The command never takes it from the clone's current head, since the point of the record is that a person names what they read. When the folder is a git checkout, a refusal prints its current head as help. `--commit` with `own` or `knowledge` is refused.

**What it does not change.** The domain must be in your own configuration, and the command offers no `--file`, since a repository's `vyvid.toml` may not set trust. An unknown name is refused with the list of configured domains. After a change the command says what the domain now gives. For a raise, run `vyd install --project` in a project that uses it to compose its skills. For a lowering, a project already installed keeps the skills written for it until the next `vyd install --project`, which removes them.

To take a domain out:

```bash
vyd domain remove tools
```

The command refuses while a project of your configuration uses the domain, naming that project, and also while the repository you are standing in declares a project in its `vyvid.toml` that does, and while another domain lists it as a parent. Remove or change those first. It never deletes the domain's folder or its clone. It removes the entry, and says where the folder was left.

The command that writes a domain's folder, `vyd domain new`, does not add it to the configuration. `vyd domain add` is the next step.

---

## 4. Bind Vyvid to a project

### Create a repository configuration

At your project’s root, create `vyvid.toml`:

```toml
[project]
name = "example-service"
visibility = "public"
docs = "code:docs"
contract = "code:AGENTS.md"
domains = ["lifecycle", "tools"]
skill_targets = [".claude/skills", ".github/skills"]
hook_clients = ["claude-code", "copilot"]
```

This means:

- The repository is the project’s code root.
- Documents live under `docs/`.
- `AGENTS.md` is its contract.
- The project uses the lifecycle and tools domains.
- Composed skills should be written for both configured skill locations.
- Reminder hooks should be registered for the named clients.

A repository file selects domains by **configured domain name**. It does not configure their remotes or clone them for contributors.

If a repository file names an unavailable domain, Vyvid reports it and leaves that domain out of the retrieval stack. Project skill installation is stricter: it will not silently regenerate skills with a missing domain omitted.

### Understand path prefixes

Use explicit prefixes to make paths understandable:

| Prefix | Relative to |
|---|---|
| `code:` | The project’s code root |
| `docs:` | The project’s configured documents root |
| `kb:` | The configured knowledge-base root |
| `self:` | A domain’s root, in domain configuration |

For this project:

```text
code:AGENTS.md        -> <repository>/AGENTS.md
docs:standards.md     -> <repository>/docs/standards.md
```

A bare path is resolved from the relevant scope’s base, not simply from whichever directory the shell happens to be in.

A repository’s `vyvid.toml` must keep its paths inside the repository, including after resolving symlinks. It cannot set machine-level keys such as `code`, `git`, `remote`, `trust`, or `match`.

### Write a useful project contract

A small `AGENTS.md` can establish the project-specific authority and permission boundary:

```markdown
# Agent contract

Before starting work, run `vyd context` and read the applicable guidance.

Use the task-relevant composed skills. Ask the index before broad searches,
then verify important claims against their sources.

The project plan defines scope. The home status record holds live state.

Run the work-board and presence commands before implementation.
Do not edit alongside another active builder without maintainer approval.

Record which checks actually ran and their results.
Do not report an unrun check as passing.

Commit, push, merge and release only with maintainer authorisation.
```

Add your real build entry point, permitted validation, publication rules, and approval requirements. Vyvid does not infer those policies.

### Review and trust the project file

From the checkout:

```bash
vyd config
vyd context --no-pull
```

Before trust, the repository configuration supplies knowledge, but its contract and skills are withheld as instructions, and its command extractors and glue do not run. The commands that would write files for such a project, such as `vyd install --project`, `vyd work build` and `vyd here --role`, refuse and say why.

A person who has reviewed the configuration then runs:

```bash
vyd trust
```

This command requires an interactive terminal and confirmation. It first prints what the file declares that an agent would read or that would run with your privileges, such as its contract, its skill folders, its command extractors and glue, and the commands that build a registered code index. Only a typed `yes` records the trust. It is not a bootstrap step for an agent to approve on someone’s behalf.

Trust is recorded against the file’s contents. Changing `vyvid.toml` requires renewed trust. Linked worktrees of the same repository share the trust record when they contain the same configuration bytes.

Then inspect the active context:

```bash
vyd context
```

`vyd config` reports the two standings separately. The `configuration trust:` line concerns your user configuration, and a line beginning `project`, followed by the project’s name and the path of its `vyvid.toml`, says whether that file is trusted or gives knowledge alone.

### Work in a cloud session

A cloud agent session has no terminal, so `vyd trust` cannot run there, and a hash recorded ahead of time would go stale whenever a branch changed `vyvid.toml`. What a cloud environment does offer is a setup script that a person writes. It runs as root before the agent starts, and the filesystem it leaves is snapshotted and reused. A later session skips the script and gets a fresh checkout of the repository, newer than the snapshot, so anything the script put outside the checkout (the installed tool, your configuration, cloned domains and the model) is there already, and anything that depends on the current branch is not. A script that finishes within about five minutes stays cacheable. In sessions measured on Linux the whole setup took about 23 seconds, the first `find` took 68 seconds with the model download and embedding, `vyd build` with the vectors present took under five seconds and a `find` on a current index under two.

Your own configuration is trusted whatever it holds, and the script can write it. To trust a repository's `vyvid.toml` without a hash, list the repository in `[framework] trusted_repositories`, written as a remote is matched to a project, with no scheme, user or `.git` and in lower case:

```toml
[framework]
trusted_repositories = ["github.com/example/project"]
```

The project file is then trusted when all three of these hold. The list is read from your own configuration alone, never from a file `VYVID_CONFIG` names, a configuration given by path or a `vyvid.toml`, and no setting of its own in the environment grants it. Your own configuration is found through the platform's folders, though, so `XDG_CONFIG_HOME` or `HOME` decides which file that is, and whatever can set those can choose it. The checkout's `origin` is a listed repository, so a fork whose `upstream` is listed is not trusted. And the file holds the bytes committed at `HEAD`, so an uncommitted edit lapses the trust until it is committed. A hash recorded by `vyd trust` still counts first, and `vyd trust` still needs a terminal. `vyd config` lists the repositories, says on the project's line when the trust came from the list, and notes where the key is set in a file that is not your own, since it is ignored there. A list that is not strings, or an entry not already written in the normalised form, is a problem that `vyd config` reports.

The grant has limits. A hostile branch of a listed repository is trusted, since the committed bytes are all it checks. It adds little there, because that branch's hooks, instructions and skills already reach the agent. It is meant for a machine or a virtual machine set up for this purpose, and a repository you do not control should not be listed. Nothing in a repository can add itself to the list, and an agent that can edit your configuration can, as it can set `trust = "own"` (the permission settings of your client are the guard there). The grant covers public domains alone. A private domain's case is the next section.

A script like this one installs the tool at a tag, writes the configuration, clones the domains and builds in the checkout if the environment has one. It logs to a file and always exits 0, so a failing step never stops the session from starting. Replace the repository, the tag and the domains with yours:

```bash
#!/bin/bash
exec >/tmp/vyd-setup.log 2>&1
set -x
uv tool install "git+https://github.com/nebularis/vyvid.git@v0.2.16"
export PATH="$HOME/.local/bin:$PATH"
mkdir -p ~/.config/vyvid
cat > ~/.config/vyvid/config.toml <<'EOF2'
[framework]
kb = "~/vyvid-kb"
glue = "stop"
trusted_repositories = ["github.com/example/project"]

[[domains]]
name = "lifecycle"
remote = "https://github.com/nebularis/vyvid-lifecycle.git"
trust = "own"
git = { pull = "manual", commit = "manual", push = "manual" }

[[domains]]
name = "tools"
remote = "https://github.com/nebularis/vyvid-tools.git"
trust = "own"
git = { pull = "manual", commit = "manual", push = "manual" }
EOF2
vyd kb clone
vyd install --client claude-code
for d in /home/user/*/; do
  [ -f "$d/vyvid.toml" ] && (cd "$d" && vyd build)
done
exit 0
```

`vyd install` writes Вивід's general rules into `~/.claude`, which the snapshot keeps. A domain is `trust = "own"` here because nobody is at a terminal to review a pull or accept a held change, so you take responsibility for the domains when you write the script, and `pull = "manual"` keeps them where the script left them. The `vyd build` in the loop puts the embedding model and the vectors in the snapshot, when the environment holds a checkout as the script runs. A later session's checkout may be newer, and its first question then rebuilds the index itself, re-embedding only the text that changed. A step that must see the current branch belongs in a SessionStart hook in the repository instead, which runs in the fresh checkout. Avoid starting a build in the background from such a hook, since two builds at once write into the same folder.

The model comes from `huggingface.co`, which redirects to a download host that can differ between the setup script and the session, so the environment's network settings must allow both `huggingface.co` and `*.cdn.hf.co`. A setup script can find a host it cannot reach reported as a name that does not resolve. When the build cannot embed, the automatic build prints the reason on standard error beginning `no embeddings`, and `vyd build` shows it as a note. A `find` that cannot rank retries the build once the store is a minute old, so a failed download is tried again in the session and not on every question. A build made with `--no-embed` is left as it is.

### Private domains in a cloud session

A private domain is a repository the session cannot clone, and the rules and skills in it are what you most want the agent to follow. Four mechanisms can bring it, and each costs something.

- **Attach the repository to the session.** The session then ignores the first repository's `.claude/settings.json`, so its hooks and permissions stop applying, which is usually the price of the project you meant to work on.
- **Clone it in the setup script.** A private repository is refused during setup and in the session unless it is attached, and no secret can be attached to requests to the hosting service, so there is no credential to clone with.
- **Enable skills on your claude.ai account.** They load when the agent finds them relevant, which suits a procedure and does not suit a rule that must hold in every session.
- **Put the files in the setup script.** The script is the one place your private text can travel, and `vyd cloud script` writes it.

```bash
vyd cloud script --output ~/cloud-setup.sh --domain my-rules=~/.config/my-rules --domain my-boundaries --grant github.com/example/project
```

It writes the file and prints only its path, its size against the limit, a fingerprint and a line for each domain, saying whether the domain was embedded, with how many files, or cloned. It never prints the script, because the script holds your private text and an agent that ran the command would put that text into its transcript. The file is readable by you alone.

`--domain` names a domain of your configuration, and the script embeds only the domains you name, never every private domain, so a large one is not sent by accident. A private domain you did not name is left out and the output says so. Each named domain must be in a git repository, and the script carries the files git tracks, each as base64 so every byte arrives as it is. After `=` comes the folder to write it in, which starts with `~/`. Without it the domain's own folder is used when it lies under your home folder, and a folder outside it is refused until you give one. A link that leaves the domain's folder, a file over 256 KB and a name that would leave the folder are refused. `--grant` adds a repository to `trusted_repositories` in the cloud configuration, written as for the key itself.

The script installs `vyd` at the version that wrote it, writes a configuration for the cloud, runs `vyd kb clone` and `vyd install --client claude-code`, and ends by listing the configured domains in its log at `/tmp/vyd-cloud-setup.log`. The embedded domains are `trust = "own"` and private. Your public domains are cloned from their `remote`, or from the `origin` of their folder, with an ssh address written as the https address of the same repository, and trust as you configured it. Their git policy is `manual` throughout, so nothing pulls, commits or pushes there. A public domain with no remote is left out, and the output says so. The script always exits 0 and carries on past a failed step, saying so in the log, so a failure never stops the session from starting.

Anyone who can use the environment can read its setup script, so paste this one only into an environment that nobody else uses. The environment's snapshot is rebuilt when you paste again, so paste again after a domain changes. The script has a limit of about 64 KB, and the command warns above it, so name fewer domains or keep the large ones out. The fingerprint is the first 12 hex digits of the SHA-256 of everything after the header comments, and it is written in the header, so you can tell which version of the script an environment holds.

To copy the file to the clipboard, run `pbcopy < ~/cloud-setup.sh` on macOS, or `Get-Content ~/cloud-setup.sh -Raw | Set-Clipboard` in Windows PowerShell, and paste into the environment's setup script field.

### Use a user-level project binding instead

For a project you do not want to configure publicly:

```toml
[[projects]]
name = "example-service"
code = "~/work/example-service"
docs = "code:docs"
contract = "code:AGENTS.md"
domains = ["lifecycle", "tools"]
match = { remote = "github.com/example/example-service" }
```

The remote match can recognise other clones. Linked worktrees can also be recognised through their shared Git repository.

Project selection generally favours the most specific containing project folder. Repository declarations, shared worktrees, and remote matching provide additional binding mechanisms.

**Always check `vyd context` in the folder where you will work.** A working command that answers from the general scope alone is not evidence that your project is configured correctly.

### Declare a project from the command line

The project entries above can also be written by a command. The default target is your user configuration, because that is where a path of your own machine belongs.

```bash
cd ~/work/example-service
vyd project add example-service --domain lifecycle --domain tools
```

**What it fills in for you.** Run in a git checkout, `--code` is that checkout, and `--remote` is the checkout's own remotes, each written as the matcher expects, as `host/owner/repository` in lower case without a scheme, a user or `.git`. A remote that carries a password or a token is reported by its host and refused. The entry follows the shape of the example configuration, with `name`, `visibility`, `code`, `match`, `docs`, `contract` and `domains` in that order.

| Option | Meaning |
|---|---|
| `--code <folder>` | The code folder. The checkout you are in by default |
| `--docs <folder>` | The documents folder, when they are kept apart from the code |
| `--contract <path>` | A rule file, such as `docs:CONTRACT.md`. Repeat for several |
| `--remote <url>` | A remote that identifies the checkout. Repeat for several |
| `--domain <name>` | A configured domain the project uses. Repeat for several |
| `--visibility public\|private` | Private by default, since it is the cheaper one to loosen later |
| `--file` | Write the repository's `vyvid.toml` instead |
| `--dry-run` | Print the change and write nothing |

**What it refuses.** A name that is not a lower-case name, a name a project or a domain already has, and a domain nobody configured, each with the loader's own message. A path is written absolute, with `~` for your home folder, and `..` is resolved before it is written.

**Binding a domain that gives more than knowledge needs a person.** A domain whose trust is `own` or `reviewed` brings rules and extractors that run for every project that uses it. Naming one in `--domain`, or in `project set domains`, is therefore asked of a person at a terminal, like the trust itself. A knowledge domain can be bound by anyone.

To change a plain key afterwards:

```bash
vyd project set example-service docs ~/work/example-service-documents
vyd project set example-service domains lifecycle tools
vyd project set example-service visibility public
```

The keys are `docs`, `code`, `visibility`, `docs_visibility`, `doc_share`, `skill_prefix`, `skill_additions`, `domains`, `contract`, `skills`, `facets`, `register_types`, `vocabulary`, `skill_targets`, `hook_clients` and `remote`. A list key takes several values, and replaces the list. Anything else is refused with a reason. `families` has its own commands, in the next section. `moves`, `extractors` and `recipes` stay hand-edited, since each is a table whose meaning a one-line command would hide. `skills`, `skill_additions`, `hook_clients` and `skill_targets` change what a client loads or runs, so they need a person at a terminal.

```bash
vyd project remove example-service
```

This removes the entry. The project's index store, its logs, its code folder and its documents are left as they were, and the command says so.

**Writing the repository's file instead.** With `--file`, a command edits the `vyvid.toml` at the root of the repository you are in, and creates it if the repository has none. A file that is committed may not hold what is yours alone, so these are refused with `--file`:

- `--code` and `--remote`, which a `vyvid.toml` may not set at all
- a `--docs`, `--contract` or other path that is outside the repository. The message says that it belongs in your user configuration. Paths inside are written as `code:` paths, so they mean the same in every clone
- `project remove`, since removing the project of a `vyvid.toml` would leave an empty file, and a command never deletes a file. Delete it yourself

Changing a `vyvid.toml` changes the bytes you trusted. The command says that the trust it had lapses, and that `vyd trust`, run by a person in a terminal in that repository, restores it. No command here records trust.

---

## 5. Add your project’s knowledge

### Declare identifier families

An identifier family tells Vyvid where entries are defined and how to recognise their names.

Add to `vyvid.toml`:

```toml
[project.families]
STD = { defined = "docs:standards.md", type = "standard" }
TD = { defined = "docs:technical-debt.md", type = "debt", removable = true }
PDD = { defined = "docs:pending-design-decisions.md", type = "pending-decision" }
ADR = { defined = "docs:decisions", rule = "file", type = "decision" }
```

By default, family `STD` recognises identifiers shaped like `STD-1`, with an optional letter suffix.

A family’s `rule` identifies its definition format:

| Rule | Definition |
|---|---|
| `table` | An identifier in a Markdown table’s first cell |
| `file` | A file whose name starts with the identifier |
| `heading` | A heading beginning with the identifier |
| `question` | A recognised question lead or question table row |

Use an explicit `pattern` when your identifiers differ from the default. A family can also name further places that define its entries with `also`, after the one in `defined`.

### Let Vyvid propose your families

A register's header is its schema, so the tables of a documents folder already say which families it has. `vyd project scan` reads them.

```bash
vyd project scan example-service
```

It reads the Markdown files under the project's documents folder, skipping hidden folders, links that leave the folder and anything inside a code fence. For each table whose first column holds identifiers of one prefix and a number, such as `TD-3` or `SL-12`, it asks the register types which type the header belongs to. A register type may declare **signs**, the columns that only a register of that type has, such as `Debt` for a debt register, `Capability` for a capability register, `Stratum` for a standard, `Slice` for a board and `Tool` for a note. A table whose header carries the signs of exactly one type is proposed, with the file and the number of rows counted. The output is the block of families it would add, to read before anything is written:

```text
[projects.families]
SP = { defined = "docs:INDEX.md", type = "slice" }   # 1 row in INDEX.md
STD = { defined = "docs:standards.md", type = "standard" }   # 1 row in standards.md
TD = { defined = "docs:technical-debt.md", type = "debt" }   # 1 row in technical-debt.md
```

**What it does not guess.** A table is named, with the reason, and nothing is proposed for it, when its header carries the signs of no type or of several, when a column is neither declared nor on the unmapped list so that no register could read it, when its first column mixes identifiers with other text or several prefixes, or when two tables of one prefix differ in type or lie in different folders. A register with a header and no rows is named too, with the type its signs give if they give one and the `vyd family add` command to run, since its prefix cannot be told from no rows. A table with no identifiers is ignored. A family the project already declares is left alone and listed. If the files of a family lie in one folder and all share a type, the proposal is a glob such as `docs:status/*.md`.

**A pattern is proposed only when the default does not fit.** A family's default pattern is its name, a dash, digits and an optional letter. If an identifier of the table is of another shape, such as `SL-1.2`, the proposal carries a pattern for the prefix and says so, because a pattern is the one part of a proposal that could read ordinary prose as an identifier. Read it before you apply it.

With `--apply`, the families are written in one validated step, through the same path as `vyd family add`:

```bash
vyd project scan example-service --apply
```

To declare one family yourself, which is the right move for a table the scan named, or to remove one:

```bash
vyd family add example-service PRI --defined docs:principles.md --type principle
vyd family add example-service TD --defined docs:technical-debt.md --type debt --removable
vyd family remove example-service PRI
```

`--defined` is `docs:` or `code:` and a path, or a path that lies inside the documents or code folder, which is written in that form. A definition that leaves the project, by `..`, by a link or by a path outside, is refused, because the register it names is read into the index. The type must be one the project's register types declare, and the message lists them. `--pattern` is a regular expression and is checked to compile, `--removable` marks entries meant to disappear, and removing a family leaves its register as it is. Both take `--file`.

A scan covers registers only. Recipes, extractors and moves stay in the file you edit.

### Create a first register

Create `docs/standards.md`:

```markdown
# Standards

| ID | Claim | Problem shape | Activity | Enforced by | Ratified |
|---|---|---|---|---|---|
| STD-1 | **Reject invalid input before changing stored data.** | validating a request before persistence | api-and-contract-design, unit-testing | | yes |
```

The empty `Enforced by` cell does not establish that enforcement exists. Fill it with the relevant registered mechanism or other applicable entry when you have one.

Good entries have:

- One clear claim, preferably in a bold first sentence.
- A claim no longer than the configured limit, **200 characters by default**.
- Enough problem wording to match the questions users actually ask.
- Evidence and version boundaries for observations.
- Relations to the decisions, findings, or mechanisms that support them.
- Explicit non-coverage when a reader could overgeneralise.

Do not turn every paragraph into a register entry. Register durable answers that someone should find again.

An entry can name the part of a file that explains it in a `Pointer` column, as a path with a line range such as `docs/request-contract.md:40-60` or with a heading slug such as `docs/request-contract.md#partial-updates`. `vyd read` then prints that part beneath the row. A pointer at the whole of a file longer than 200 lines is a defect. The build reports it as a note and `read` declines to print the file, so point at a section instead.

### Use the packaged register types

Available types include:

```text
standard          principle         pattern
mechanism         capability        debt
pending-decision  backlog           slice
decision          discovery         question
note
```

The type determines the entry’s class. The columns determine which facts and relationships are extracted.

Useful relationship columns include:

| Column | Purpose |
|---|---|
| `Decided by` | Identify the decision behind an entry |
| `Evidenced by` | Identify supporting evidence |
| `Enforced by` | Identify an enforcement mechanism |
| `Supports` | State what an entry supports |
| `Waits for` | State a dependency |
| `Specialises` | Add a narrower interpretation of another entry |
| `Overrides` | Replace another entry within the active context |
| `Bears on` | Link to affected entries or declared terms |
| `Distinguished from` | Prevent confusion with a related entry |
| `Does not cover` | State the boundary of the claim |
| `Governs` | Name the things an entry governs. Each name becomes an edge to the node of that name |
| `Owner`, `Provided by` | Name the module or project unit an entry belongs to |

A link exists because the sources declare it. Semantic similarity does not automatically create a dependency or evidence edge.

Two of these columns read their cells as names rather than identifiers. A names column such as `Governs` makes an edge to the node of each name even when nothing has defined that node yet, because something derived may define it later and a check can then ask whether it exists. A module column such as `Owner` is read with its code quotes, any note in parentheses and any trailing slash removed, so `src/vyvid/` and `src/vyvid` name the same folder. The section on project-owned extractors explains how declared units turn those names into edges to real project units.

### Build and inspect

After adding or changing knowledge:

```bash
vyd build
vyd check identifiers
vyd find "validate a request before saving it"
vyd read STD-1
```

The first build may download the embedding model.

Build output matters, because a command can produce a usable partial index while reporting omitted or malformed sources. Do not ignore extraction problems merely because some queries work.

---

## 6. Retrieve context effectively

### Start with the active context

```bash
vyd context
```

The normal order is:

```text
general
  -> selected domains and their ancestors
    -> project
```

Parents precede children. For otherwise independent domains, the project’s declared order is preserved.

The project is the narrowest instruction layer. For retrieval, narrower scope helps resolve equal relevance, but **a project entry is not automatically more relevant than every domain entry**.

`vyd context` may pull managed domains whose policy says an update is due. To inspect without that pull:

```bash
vyd context --no-pull
```

### Ask in the words of the problem

```bash
vyd find "prevent malformed requests from changing stored data"
```

Start broad enough to find rules, decisions, and findings together. Use kind filters when you specifically need one class of answer:

```bash
vyd find "request validation" --kind standard
vyd find "request validation" --kind decision
vyd find "request validation" --kind standard,principle
```

When questions crowd out answers:

```bash
vyd find "request validation" --exclude question
```

The available kinds come from the active stack’s register-type declarations. Questions asked with `find` and `read` are logged so that weak answers can be reviewed later, as the section on misses describes, and `--no-log` skips the log for one call.

### Understand filters and boosts

These options filter candidates:

```bash
--kind
--exclude
--phase
--audience
```

These options **boost matching entries without excluding non-matches**:

```bash
--activity
--quality
--tech
```

For example:

```bash
vyd find "validate requests" \
  --activity api-and-contract-design,unit-testing
```

Facet matching expands through the configured broader and related concepts. It is a relevance hint, not a strict technology or activity restriction.

Use values your stack declares. A value no layer declares is an error, because `find` will not invent a tag from a word you typed. That does not close the list. A domain or a project can declare more values in a facet register of its own, and once it does, `find` accepts them and its entries can be tagged with them, as [Extend facets only where necessary](#extend-facets-only-where-necessary) explains.

### Read the result’s qualifications

Results include a claim, identifier, kind, source pointer, and sometimes flags:

| Flag | Meaning |
|---|---|
| `!` | The entry states something it does not cover |
| `~` | It has been superseded, reversed, or narrowed |
| `TD` | Open debt bears on it |
| `BL` | Related backlog work is not built |
| `?` | It is proposed rather than accepted |
| `P` | It is private |
| `U` | It comes from an untrusted knowledge-only source |

Read the text beneath the result. It explains the actual qualification.

A similarity score is **not a probability that the claim is true**. A high-ranking result may be proposed, version-limited, superseded, or merely the closest available answer.

### Follow identifiers to sources

```bash
vyd node STD-1
vyd read STD-1
vyd reaches STD-1
```

Use:

- `node` for a compact identity and source summary.
- `read` for the entry’s fields, related entries, and source text.
- `reaches` to inspect declared relationships around an entry.

`reaches` is not a compiler call graph or a proof of all downstream impact.

### Qualify identifiers from domains

A project and several domains may all contain `NOTE-1`. Use the scope to disambiguate:

```bash
vyd read tools:NOTE-1
vyd read python:NOTE-1
vyd resolve tools:NOTE-1
```

Bare identifiers resolve through the current scope’s own families and configured delegations or moves. Do not assume a bare domain identifier will be found just because that domain is in the retrieval stack.

### Ask another scope deliberately

Most index-question commands accept `--scope`:

```bash
vyd find "tool installation" --scope tools
vyd find "tool installation" --scope only:tools
```

The first adds a scope. The second restricts the question to the named scope.

For a different project folder:

```bash
vyd find "request validation" --in ~/work/example-service
```

Scope selection changes the query’s visibility. It does not grant instruction trust or permission to publish private knowledge.

### Search for existing concepts

```bash
vyd exists "validation"
```

`exists` performs textual lookup over declared ontology terms and selected kinds of existing project entries. It is useful for checking whether something already exists before introducing another name. An `exists` that finds nothing is logged as a miss, which is how a gap in the vocabulary or the registers comes to light.

It is not a substitute for semantic `find`.

### Remember what is intentionally hidden

Ordinary `find` does not mix every possible result surface together:

- Declared ontology terms are requested with `--kind term`.
- Source symbols are requested with `--kind symbol`, alone. Plain `find` shows none, and says in one line when symbols match the question strongly.
- Types declared with `shown = "asked"` appear only when requested or explicitly named.

The packaged `slice` type is shown only when asked:

```bash
vyd find "request validation" --kind slice
vyd find APP-1
```

---

## 7. Install skills into agent clients

### User installation and project installation are different

User-level installation:

```bash
vyd install --dry-run
vyd install
```

Without a client option, Vyvid installs for every supported client whose directory already exists, and running it again is safe. If no client directory exists it writes nothing, says so, and exits 1, so name a client with `--client`.

For each client it writes the core skill that reviews a domain someone else wrote. For Claude Code it also writes a rule file that tells an agent to ask the index first, and a reviewer agent definition limited to read and search tools. It then writes the skills of private domains and of any domain whose entry says `user_skills = true`, and the `always_rules` files a domain names go where Claude Code loads rules in every session. Generated files that no source produces any longer are removed. A file that was not generated by `vyd install` is never overwritten. It is left alone and reported, and the command exits 1. `vyd config` says when what is installed is out of date.

Explicitly target one:

```bash
vyd install --client claude-code
vyd install --client copilot
```

Two more options apply to a named client. `--target <folder>` writes into another folder instead of the client’s own, which is a way to inspect the result, and it needs `--client`. Vyvid refuses a target inside the folder of a configured project. With `--client claude-code`, `--hooks` also registers the reminder hook in Claude Code’s user-level settings. Copilot documents no user-level hook file, so for it `--hooks` writes nothing, says so, and names `vyd install --project` as the way to register the hook. That alone makes the command exit 1 with `--client copilot`, and without `--client` the other clients are installed as usual.

Project installation:

```bash
vyd install --project --dry-run
vyd install --project
vyd check skills
```

| Installation | Purpose |
|---|---|
| User | Core integration (the rule file, the review skill and the reviewer) and eligible personal domain skills |
| Project | Composed public skills and configured reminder hooks in the checkout |

Project-generated skills are intended to be committed so contributors and agents can read them without first installing Vyvid.

**Do not edit generated skills.** Edit the domain, project skill sources, additions, or configuration, then regenerate.

`vyd install --project` writes each skill into every folder that `skill_targets` names, which is `.claude/skills` unless you say otherwise, and removes generated skills that no source produces any longer. As at user level, it leaves a file it did not generate alone and reports it. A skill with a placeholder that nobody gives a value for is not written, and the command names the value and exits 1. It registers the reminder hook only after the skills were written cleanly.

### Know the current client boundaries

User-level installation supports:

- Claude Code, under `~/.claude`.
- Copilot, under `~/.copilot`.

Project skill destinations are configurable with `skill_targets`.

Reminder-hook configuration supports `claude-code`, `copilot`, and `codex`. This does not mean `vyd install --client codex` is supported.

Claude Code receives a user-level rule file. Copilot does not receive an equivalent always-on personal rule file from this integration, so put essential project guidance in the instruction file your client actually loads.

### Public and private domain skills

Trusted public domains normally reach agents through project composition.

Trusted private-domain skills are installed at user level, not copied into a checkout where they could be committed.

A public domain can request user-level installation with:

```toml
user_skills = true
```

Use this deliberately. Personal skills can take precedence over project skills with matching names.

### Understand the reminder hook

The reminder hook encourages an agent to ask the index before broad searching, and again after repeated searches without an index question. It is the command `vyd-hook`, which `vyd install --project` registers in the checkout for each client named in `hook_clients`. The list defaults to `claude-code` and may also name `copilot` and `codex`, and the registered files are `.claude/settings.json`, `.github/hooks/vyvid.json` and `.codex/hooks.json`. Existing settings are kept, and only the hook’s own earlier entry is replaced. The command the reminder tells the agent to run is the `ask` value of `skill_values`, which is `vyd find` unless you set it. Where `vyd-hook` is not installed, the registered command does nothing, so a contributor without Vyvid is not affected.

When a search runs in a shell, whether Bash or PowerShell, or through a search tool, and the session has not asked the index anything, the agent gets the reminder. Once the agent has asked, the hook stays quiet until fifteen further searches have passed, and then reminds again. A shell command that itself asks the index counts as asking. A failure inside the hook leaves the agent with no message at all, because in some clients an error in a hook would otherwise deny the tool.

The hook:

- Reminds rather than blocks.
- Runs before relevant tool calls in Claude Code and Codex.
- Runs after relevant tool calls in Copilot.
- Does not replace project instructions.
- Does not implement Git commit or merge gates.

The upstream documentation reports exercised integrations for Claude Code and Copilot, and Codex’s integration was not reported as exercised at the inspected revision.

### Handle missing sources honestly

If a required domain is missing, project skill installation does not silently write a reduced set.

`vyd check skills` has three outcomes, and a hook or a script can tell them apart. It exits **0** when every committed skill equals what its sources compose to. It exits **1** when it found a problem, such as a skill that is missing, differs from its sources, was generated and now has no source, or lacks a value. It exits **2** when it could not perform a meaningful check, including missing domain sources, an untrusted project file, or no project claiming the folder. That is not a passing comparison, and it says that it did not run.

When you move skills from older files, `vyd check skills --from old/SKILL.md` also fails on any line of an old skill that appears in no composed skill, so a move loses nothing. With a single `--from` file, `--map` names a tab-separated file with `line` and `destination` columns that gives such lines a home elsewhere.

A contributor may still read committed skills without the domain checkout, but regenerating or checking them requires the relevant sources.

---

## 8. Use the existing domains

Select domains according to the work a project actually performs. They provide different combinations of searchable knowledge and procedural skills.

### Tools

The `tools` domain contains evidence-backed notes about development tools, including `mise`, `uv`, and Haskell build tooling.

Its shipped skills are:

| Skill | Focus |
|---|---|
| `mise` | Project task and tool execution conventions |
| `constrained-environments` | Working under installation, network, or runtime constraints |
| `environment-lessons` | Recording and reusing environment findings |
| `windows` | Platform-specific working practices |

Its `NOTE` register records what was run and on which versions. Treat each note’s evidence boundary as part of the answer.

Use it when diagnosing setup problems or establishing reliable developer commands:

```bash
vyd find "editable tool installation" --scope only:tools
vyd read tools:NOTE-1
```

### RDF modelling

The `rdf-modelling` domain currently ships an `ontology-modelling` skill and no register.

It covers modelling practice such as:

- Looking for existing terms before introducing new ones.
- Modelling facts and reality before convenient classifications.
- Deriving judgements from facts.
- Open-world reasoning.
- Domain and range.
- Safe simplification.
- The runtime consequences of a modelling choice.

Because it is skill-only, its value primarily reaches the agent through trusted skill composition. It does not create searchable modelling-register entries that do not exist.

**It also does not automatically enable ontology extraction.** Configure an extractor separately, as shown later.

### Triple stores

The `triple-stores` domain combines findings, query standards, detailed explanations, and three skills:

| Skill | Focus |
|---|---|
| `probing` | Establishing what an engine or validator actually does |
| `query-writing` | Writing queries with explicit performance reasoning |
| `shacl-testing` | Testing SHACL behaviour and constraints |

Its identifier families include:

- `TSD-…`: findings.
- `TSD-Q…`: open questions.
- `RDF-…`: query standards.

For example:

```bash
vyd find "avoid expensive repeated query evaluation" \
  --scope only:triple-stores

vyd read triple-stores:RDF-1
```

Read evidence labels and engine versions. The domain distinguishes findings based on source inspection, observation, documentation, and reasoning. A measured engine-specific result is not automatically a universal SPARQL rule.

### Python

The `python` domain is currently focused on what can be learned about Python code and development behaviour, not a comprehensive Python language handbook.

Its notes cover subjects including:

- `tree-sitter-python` and `ast`.
- Symbol extraction.
- `jedi` and `scip-python`.
- Whether particular `uv` operations execute cloned code.

Its `testing` skill covers diagnosing and improving Python test suites, including parallelism, memory, and repository-wide scans.

Adding this domain does not install optional symbol grammars or configure project source paths. Those are separate setup steps.

### Haskell

The `haskell` domain contains notes about compiler-derived answers from:

- GHC.
- Cabal.
- `.hie` files.
- `hiedb`.
- SQLite.

Its `haskell` skill supplies related working procedures.

Use it when you need exact compiler-index answers rather than semantic similarity. Adding the domain does not build `.hie` files, install a compiler, or create a `hiedb` database.

### Lifecycle

The `lifecycle` domain ships four procedural skills:

```text
lifecycle
design
branching
publication-hygiene
```

It currently has no register. Its use is described in the next section.

### Avoid recipe-name surprises

The tools, Python, and Haskell domains each declare a recipe named `how-do-i`.

Recipes are selected by name across the active stack, and a later declaration replaces an earlier one with the same name, so they do not all run together.

Check the effective recipe:

```bash
vyd recipe list
```

For a project using several such domains, define clearly named project recipes such as `python-symbol-brief` or `compiler-index-brief` rather than assuming `how-do-i` means the same thing everywhere.

---

## 9. Run an agentic lifecycle with `vyvid-lifecycle`

The [lifecycle domain](https://github.com/nebularis/vyvid-lifecycle) supplies a detailed procedure for designing, planning, implementing, reviewing, and delivering work.

It is **not an autonomous runner**. Skills tell agents how to behave, work commands read and maintain records, and your client, maintainers, and project tooling control execution and permissions.

### 9.1 Enable the domain and work settings

First ensure:

1. The lifecycle domain is configured and present.
2. A person has reviewed it and enabled its instructions.
3. Your project includes `"lifecycle"` in `domains`.
4. Your project configuration is trusted.

Then add:

```toml
[project.work]
status = "docs:status"
plans = "docs:plans"
sketches = "docs:sketches"
reviews = "docs:review"
validation = "docs:validation"
decisions = "docs:decisions"
index = "docs:INDEX.md"
roadmap = "docs:ROADMAP.md"
main = "main"
```

Only declaring an empty work table is enough to enable default status and plan locations:

```toml
[project.work]
```

However, no generated index or roadmap is implied until you configure those files. The table is also what switches the work commands on. Without it, `vyd work` and `vyd here` say that the project declares no work settings and do nothing, and `vyd board` falls back to the checkout-local view.

Do not confuse the two builds:

| Command | Derives |
|---|---|
| `vyd build` | The searchable knowledge index |
| `vyd work build` | A generated Markdown work-index region |
| `vyd work roadmap` | Generated roadmap regions |

### 9.2 Configure the lifecycle’s project-specific language

Add project values where its defaults are not accurate:

```toml
[project.skill_values]
maintainer = "the maintainer"
contract = "AGENTS.md"
review = "docs/review"
pending = "docs/pending-design-decisions.md"
debt = "docs/technical-debt.md"
visibility = "public"
production_text = "the published documentation, examples and release notes"
```

The composition engine derives several location values from `project.work`, including plans, status, sketches, validation, decisions, index, and roadmap.

Some values need explicit attention:

- Work configuration uses `reviews`, while the skill placeholder is `review`.
- Pending-decision and debt registers are not work-table paths.
- Hook installation, full checks, merge checks, and publication checks are project-supplied commands, not facilities created merely by adopting the domain.

Read the generated skills before committing them. Replace generic command descriptions with your project’s real commands.

After configuration changes, a person re-trusts `vyvid.toml`, then:

```bash
vyd install --project
vyd check skills
```

### 9.3 Keep one plan and one status record per unit

The core record pair is:

| Record | Purpose |
|---|---|
| Plan | Scope, dependencies, decisions, slices, and intended validation |
| Status | Current state, next action, blockers, results, history, and handoffs |

A plan is not a progress journal. A status record is not a second design specification.

Sketches, review requests, and separate validation documents support the process. The domain identifies plans and status records as the mandatory unit documents, and its default slice-delivery procedure additionally calls for a Validation Pack. If you adopt a lighter evidence format, explicitly adapt that procedure rather than silently dropping it.

### 9.4 Create a plan

Create `docs/plans/request-validation.md`:

```markdown
# Request validation

**Unit ID:** request-validation
**Prefix:** APP
**Unit type:** unit

## Scope

Reject invalid requests before writing data.

## Dependencies

- The accepted request contract.
- The existing persistence boundary.

## Slices

| Slice | Deliverable |
|---|---|
| APP-1 | Validate requests and cover rejection paths |

## Validation

Run the request-validation suite.
Invalid requests must produce the documented error and cause no write.

## Non-coverage

This unit does not change authorisation or storage retries.
```

The prefix identifies the unit’s slice namespace.

Use globally distinct slice identifiers within the project. If another unit already owns the `APP` series, choose another prefix or maintain an explicitly non-overlapping allocation.

Plans and status records do not need branch names. The board derives where work exists from Git.

### 9.5 Create its home status record

Create `docs/status/request-validation.md`:

```markdown
# Request validation status

**Unit ID:** request-validation
**Status:** planned

## Slice board

| Slice | Deliverable | State | Blocked on |
|---|---|---|---|
| APP-1 | Validate requests and cover rejection paths | planned | |

## Next action

Agree the invalid-input examples.

## History

- 2026-11-05: Plan and status record created.
```

**A slice’s state belongs in exactly one home board.**

If another unit adopts or implements that slice, it updates the home record on its branch. Its own history may explain the adoption, but it does not create a second authoritative slice row.

### 9.6 Make slices and questions addressable

Work-board settings let the board read status records. Identifier families separately make those rows available to retrieval and identifier checking.

Add:

```toml
[project.families]
APP = { pattern = 'APP-\d+[a-z]?(?:\.\d+[a-z]?)*', defined = "docs:status/*.md", type = "slice" }
APPQ = { pattern = 'APP-Q\d+', defined = ["docs:plans", "docs:sketches"], rule = "question", type = "question" }
```

Each family is written on one line because TOML does not allow an inline table to span lines. Merge these into your existing family table rather than duplicating the table declaration.

The numeric slice pattern intentionally does not overlap the question pattern.

A recognised design question can be written as:

```markdown
**APP-Q1. Should an invalid request return one error or all errors?**

The current contract leaves this unspecified.
```

This makes the question an index entry. Ordinary narrative in a plan or status record does not thereby become fully searchable.

After creating the records:

```bash
vyd work build
vyd work check
vyd build
vyd check identifiers
```

### 9.7 Understand the default state ladder

The default ladder is:

```text
planned -> briefed -> building -> built -> verified -> merged -> tagged
```

With two aside states:

```text
blocked
dropped
```

| State | Meaning in the default procedure |
|---|---|
| `planned` | The slice exists in the agreed scope |
| `briefed` | It has been prepared sufficiently for the next implementation decision |
| `building` | Work has been claimed and implementation is underway |
| `built` | The implementation and handoff evidence are ready |
| `verified` | Verification has been completed |
| `merged` | Delivery has reached the configured trunk |
| `tagged` | The relevant release tagging has occurred |

From `building` onward, states require dates by default:

```markdown
| APP-1 | Validate requests | building 2026-11-05, briefed 2026-11-04 | |
```

The newest state comes first, and the cell preserves the state trail while Git supplies commit history.

The board does not infer `verified` from a successful test process or `merged` merely from a branch merge. Update records through the agreed workflow.

### 9.8 Orient before editing

Start with:

```bash
vyd context
vyd board --fetch
vyd here
```

These answer different questions:

- What guidance applies?
- Where does the work stand across known branches?
- Who has recently declared presence in this checkout?

**Plain `vyd here` lists presence and does not register you.**

Register an actual role:

```bash
vyd here --role build --on APP-1
```

Other roles are `review` and `read`. Because no client names the model it runs on, add `--model <name>` to record it, and `--on` takes the slices you are working on, separated by commas.

If your client supplies neither `CLAUDE_CODE_SESSION_ID` nor `AGENT_SESSION_ID`, configure a distinct, stable `VYD_SESSION_ID` for that session. `VYD_CLIENT` can identify the client.

Without a distinct session identifier, sessions can share the fallback presence filename and conceal one another.

Presence is:

- Checkout-local. The files live in the checkout’s git directory unless the project’s `presence` setting names a folder in the checkout, so Git never tracks them and each linked worktree has its own.
- Advisory, not a lock.
- Considered live for twelve hours after its file was touched.
- Refreshed by writing your role again.

If another live builder is present, follow the contract’s coordination gate before writing. Prefer separate worktrees for concurrent implementation.

### 9.9 Settle design before implementation

The design skill asks the agent to:

1. Read the current relevant sources and accepted decisions.
2. State the actual problem and constraints.
3. Present meaningful options.
4. Explain consequences, costs, and trade-offs.
5. Give a reasoned leaning.
6. Wait for the maintainer’s decision where approval is required.

It also requires durable answers to become durable knowledge. If a design-question answer establishes a rule later work must follow, promote that rule into the appropriate standard, mechanism, or decision record.

An agent drafts decision records as **Proposed**. Adopting the lifecycle does not authorise the agent to accept them.

### 9.10 Mark work before implementation

Before implementation edits:

1. Change the home slice row to `building <date>`.
2. Add a history entry.
3. Regenerate the work index.
4. Commit the claim separately through the authorised actor.

For example:

```markdown
| APP-1 | Validate requests and cover rejection paths | building 2026-11-05, briefed 2026-11-04 | |
```

Then:

```bash
vyd work normalise --apply
vyd work build
vyd work check
```

Normalisation can update the unit’s rolled-up status.

The domain’s separate claim-commit convention is **not blanket permission for an agent to commit**. If the contract reserves commits for a maintainer, the maintainer makes that commit before implementation proceeds.

A cross-branch board reads committed branch tips. A claim is visible to another clone only after it has been published and fetched.

### 9.11 Build a reviewable slice

The default procedure favours a small, independently reviewable work package with:

- Implementation.
- Relevant tests and examples.
- Documentation changes in the same slice.
- A Validation Pack.
- Updated home status and generated index.

A useful Validation Pack contains:

```markdown
# Request-validation evidence

## Invariant

Invalid requests cannot reach the persistence write.

## Cases

| Case | Given / When / Then | Level | Pass criterion |
|---|---|---|---|
| Missing field | Missing required field / submit / reject | L1 | Error returned, no write |
| Valid request | Valid fields / submit / accept | L3 | Documented result, one write |

## Command

<one project command that runs the agreed validation>

## Artefacts to inspect

- Test result output.
- The persistence-boundary assertion.

## Deliberate non-coverage

Authorisation is unchanged.

## Results

Not yet run.
```

Replace the command placeholder with an actual command and explicit pass criteria before handing off.

The domain’s validation scale is:

```text
L0 build smoke
L1 unit
L2 property and determinism
L3 contract
L4 component integration
L5 system end-to-end
L6 UI end-to-end
L7 non-functional
L8 hostile and security
```

Project-specific validation policy still governs what the agent may execute. The lifecycle does not impose a universal ban on agent-run tests or a universal grant to run expensive suites.

### 9.12 Hand off without overstating readiness

At implementation handoff:

- Move the slice to `built <date>`.
- Record actual validation results.
- State unrun checks and why.
- Identify deviations, blockers, and unresolved decisions.
- Give exact next commands and pass criteria.
- Regenerate the work index.

```bash
vyd work normalise --apply
vyd work build
vyd work check
vyd misses --near
```

The lifecycle’s default verification gate includes maintainer review of the Validation Pack, execution and inspection, and an adversarial probe demonstrating that a relevant test detects a deliberate implementation break.

`built` is not `verified`. A passing fast check is not a passing full suite.

### 9.13 Merge and release through explicit gates

The default procedure calls for:

- Maintainer-authorised delivery.
- Relevant suites before merge.
- Quick hook checks rather than full suites inside hooks.
- Rebuilt derived indexes after merges.
- Version changes at the agreed merge boundary.
- Tags on trunk commits, after merge.

Vyvid does not install all the Git hooks described by the branching skill. Your project must implement and configure its own commit, merge, and rebuild integration.

Update delivered slices to `merged` and, where applicable, `tagged`. Do not advance every row merely because some work from the unit was delivered.

Leave presence when finished:

```bash
vyd here --leave
```

### 9.14 Close the knowledge loop

During the work, record important retrieval gaps immediately:

```bash
vyd gap \
  "The validation standard does not explain partial updates" \
  STD-1 \
  docs/request-contract.md:42
```

When the answer is known:

1. Add it to the correct register or skill source.
2. Preserve its evidence and boundaries.
3. Rebuild and check references.
4. Close the gap against the relevant entry.

```bash
vyd build
vyd check identifiers
vyd close STD-1
```

A learning that applies across projects belongs in the relevant domain. A project-only rule belongs in the project’s register or skill additions.

---

## 10. Operate and extend the work board

### Choose the correct view

```bash
vyd board
vyd board --all
vyd board --fetch
vyd board --state building
vyd board --commits
vyd board --measure
vyd board --here
```

| Option | Use |
|---|---|
| Default | Focus on work that differs from trunk and noteworthy branch state |
| `--all` | Include unchanged rows |
| `--fetch` | Fetch every remote, pruning deleted branches, before reading |
| `--state` | Restrict displayed work to slices whose state starts with the word you give |
| `--commits` | Show the commit associated with the row’s state |
| `--measure` | Compare branch-added content with trunk |
| `--here` | Read configured slice families in this checkout |

With work settings, the live board reads status records at local and remote branch tips without checking those branches out. It can expose double claims and branches behind trunk’s recorded state.

Without work settings, the simpler checkout-local board uses configured slice families.

**The cross-branch board does not display uncommitted edits as if they were branch-tip state.** Use the local records and generated work index while preparing a change.

The live board reads local branches as well as remote ones. A branch that was never pushed still appears on it, and where a local branch and its remote disagree the board reads the tip that is further on and says how they differ. The roadmap below deliberately reads less.

### Understand branch measurement

`--measure` compares branch-added content with what is present on trunk. This is useful after squash merges, where ancestry alone can mislead.

It is a content-overlap measure, not proof of semantic equivalence, correct integration, or successful verification.

### Generate the local work index

```bash
vyd work build
vyd work build --check
```

The command maintains a marked region in the configured index file. Text outside the generated region remains yours.

Do not edit generated rows manually. Change their status-record sources.

### Generate the roadmap

```bash
vyd work roadmap --fetch
vyd work roadmap --check
```

The roadmap can include programme summaries, branch information, completed work, decision information, and dated charts.

The roadmap is a committed file, so apart from the tree being built it is built only from what a remote knows. Other branches are read from their remote-tracking refs at their remote tips, which is why `--fetch` matters. A branch that was never pushed is left out, and so is any local commit that has not been pushed. Every remote under `refs/remotes` counts, with remotes that share one URL treated as a single remote. A reader who has a second, private remote should therefore know that the names of its branches could be written into the roadmap.

The tree being built also supplies its own records, because they are committed with it. When the current branch is not known to any remote, its records are read under the label `this checkout` instead of its name, so the name of an unpushed branch is never written. Its slices are also left out of the “Moved on” column. `vyd board` still shows local branches, because its output is read by one person and is not committed.

Generated charts derive from recorded dates, and they are not forecasts invented for undated planned work. By default a unit needs five dated slices to get a chart of its own, and `chart_after` changes that number. A bar is labelled with its slice identifier and the start of its deliverable, cut after the last comma within thirty characters or, where there is none, at the last whole word that fits, and a single word longer than thirty characters is cut at thirty.

### Inspect and repair records

Inspect parsing:

```bash
vyd work parse docs/status/request-validation.md
```

Check records and the generated index:

```bash
vyd work check
vyd work check --staged
```

The check exits 1 when it has anything to report. With `--staged` it looks only at the status records that are staged, and it checks the index’s generated region only when a staged file is a status record or the index itself. It takes the names of the staged records from the index but reads their text from the working tree, so while unstaged edits remain in a staged record it checks those edits and not the staged snapshot.

For migration:

```bash
vyd work normalise
vyd work rename
vyd work adopt
```

These report proposed changes without `--apply`.

Apply after reviewing:

```bash
vyd work normalise --apply
vyd work rename --apply
vyd work adopt --apply
vyd work build
vyd work check
vyd check identifiers
```

Their roles differ:

- `normalise`: standardise historic boards and state wording.
- `rename`: map historic slice identifiers and references.
- `adopt`: bring slices mentioned elsewhere onto their home boards.

Identifier renaming needs the relevant project rename configuration. Do not treat it as an unrestricted automatic renumbering tool.

### Customise through configuration first

The work table supports:

- Record and output paths.
- Hierarchy level names.
- State ladder and aside states.
- Dating, done, and closed thresholds.
- Slice grammar.
- Trunk name.
- Presence location.
- Generated-region markers.
- Diagnostic command names.
- Migration rules and sweep paths.
- The number that numbers the roadmap’s decision headings, and the chart threshold.

For example, a shorter ladder could be:

```toml
[project.work]
ladder = ["planned", "ready", "building", "review", "done"]
aside = ["blocked", "dropped"]
dated_from = "building"
done_from = "review"
closed_from = "done"
```

This is an alternative to the default work table settings, not a second table to append.

**Changing the parser’s ladder does not rewrite the lifecycle skill’s literal prose.** Adapt the corresponding skill sections, record templates, checks, and team conventions together.

Similarly, configuring `levels` is more than renaming a display label: ensure your document headers and project procedure match the hierarchy being parsed.

### Keep your project task interface

You can wrap Vyvid rather than forcing everyone to adopt new command names immediately.

For example, in `mise.toml`:

```toml
[tasks."work:board"]
run = "vyd board"

[tasks."work:here"]
run = "vyd here"

[tasks."build:work"]
run = "vyd work build"

[tasks."check:work"]
run = "vyd work check"

[tasks."build:roadmap"]
run = "vyd work roadmap"
```

Then align the generated messages:

```toml
[project.work.commands]
build = "mise run build:work"
roadmap = "mise run build:roadmap"
here = "mise run work:here"
```

And align the skill’s instructions:

```toml
[project.skill_values]
board = "mise run work:board"
here = "mise run work:here"
build_work = "mise run build:work"
check_work = "mise run check:work"
```

Merge these values into existing tables.

These command settings have different effects:

- Work command strings tell generated messages which task names to recommend.
- Skill values tell the agent which commands the procedure names.
- The task definitions determine what actually executes.

Changing a string does not create a task or replace a command implementation.

### Add a project-specific board extension

For capabilities beyond configuration—such as issue-tracker links, deployment readiness, portfolio summaries, or organisation-specific checks—keep a thin project-owned layer.

A reliable design is:

```text
home status records
   |-- Vyvid live board
   |-- generated work index
   |-- project-specific report
   `-- project-specific checks
```

Preserve these invariants:

1. A slice still has one home state row.
2. New views derive from that row.
3. Generated output is not edited as another state store.
4. Project-only policy stays outside the reusable domain.
5. The project contract and composed skills name the actual commands.

The current board command has no documented JSON output switch or general board-plugin registration mechanism. Do not assume its terminal table is a stable machine interface.

If you depend on internal Python work-board APIs, pin and test the Vyvid version. Otherwise, make the project-specific source-reading contract explicit and test it against representative records.

---

## 11. Extend domain skills without forking them

### Add project-specific instructions by heading

Create:

```text
.vyvid/skills/<domain>/<skill>.md
```

For example:

```text
.vyvid/skills/lifecycle/lifecycle.md
```

With:

```markdown
## Picking up and finishing

Use a separate worktree for concurrent builders.

## Reporting

Include the request-validation command and its actual result in every handoff.
```

The folder defaults to `.vyvid/skills` and is set by the project’s `skill_additions` key. During composition:

- A matching `##` heading appends to that section.
- A new heading is added at the end.
- A heading ending in `(replace)` replaces the matching section.
- Text before the first heading joins the skill’s opening.

An addition may also begin with front matter that gives its own `description`, which then replaces the domain skill’s. An addition that names no skill of a trusted domain is reported as a note and read by nothing, which is how a misspelt file name shows itself.

For an intentional procedural replacement:

```markdown
## Building a slice (replace)

Use the project's approved delivery procedure described here.

Record scope, checks, results and the next verification gate in the
home status record.
```

Replacing a section is powerful. Preserve the safeguards you still need, and make the behavioural change explicit.

### Supply placeholder values

Domain skills can contain placeholders such as:

```text
{{maintainer}}
{{status}}
{{board}}
```

Composition resolves values from:

1. Vyvid’s built-in defaults.
2. The domain’s values.
3. Derived project work paths.
4. Explicit project `skill_values`.

A missing required value prevents that skill from being written, and `vyd install --project` names the value and exits 1.

Use checkout-relative human-readable paths in skill values, such as `docs/status`, rather than machine-specific absolute paths. A composed skill is committed and read on other machines, so Vyvid writes none of your folders into it. Every composed skill also opens with the same short block, written once by Vyvid, that tells an agent to ask the index before any decision or search and names the registers it can ask.

### Add project-owned skills

Store project skill sources separately from generated destinations:

```toml
[project]
skills = ["code:.vyvid/project-skills"]
```

For example:

```text
.vyvid/project-skills/release-check/SKILL.md
```

Do not point source skills at a destination that composition is supposed to regenerate.

### Control names and destinations carefully

You can configure:

```toml
[project]
skill_prefix = "example-"
skill_targets = [".claude/skills", ".github/skills"]
```

Without a project prefix, domain-qualified naming helps distinguish skills from different domains. A skill named `design` in the `lifecycle` domain is installed as `lifecycle-design`, while the skill named `lifecycle` keeps its name.

A project prefix changes naming rules, so two domains with the same short skill name can then collide. With the prefix above, the skills named `design` and `lifecycle` become `example-design` and `example-lifecycle`, and the domain’s name no longer separates them from a skill of the same name in another domain. A short name that itself starts with its domain’s name loses that part before the prefix is added. Inspect the generated set rather than assuming prefixing always increases uniqueness. A domain can also set its own `skill_prefix`, which names its skills in the user’s folder, and an empty one keeps each skill’s folder name. Each folder in `skill_targets` must stay inside the checkout.

After any source or configuration change:

```bash
vyd install --project
vyd check skills
```

---

## 12. Specialise shared knowledge for a project

A project should not copy a domain register merely to add one local condition.

Instead, define a project register of the same type and refer to the domain entry in `Specialises`.

Suppose your project has a note register declared as:

```toml
[project.families]
TOOL = { defined = "docs:tool-notes.md", type = "note" }
```

A local note can identify the shared entry it specialises:

```markdown
| ID | Claim | Specialises |
|---|---|---|
| TOOL-1 | **Use the repository's approved installation task for this checkout.** | tools:NOTE-1 |
```

This is an example of the mechanism, so choose a domain entry whose actual meaning is appropriate before creating the relationship.

In project retrieval, a specialising entry is presented with its domain guidance beneath it.

Use `Overrides` when the project intentionally replaces an entry rather than adding detail. The overridden entry is normally hidden in that context unless its scope is explicitly named.

**Specialisation and override are not synonyms.** Prefer specialisation when the shared claim remains valid but needs local detail.

For convenient bare references, a project can explicitly delegate a family:

```toml
[project.delegates]
RDF = "triple-stores"
```

Only do this where the family is unambiguous. Do not delegate `NOTE` to several domains.

---

## 13. Create a new domain

### Choose the domain boundary

A useful domain owns a coherent subject that more than one project can reuse.

Ask:

- Does this knowledge hold outside one codebase?
- What evidence bounds each finding?
- Which procedures are reusable?
- Which details must remain project-specific?
- Does the domain need registers, skills, or both?

A domain can be skill-only. Do not manufacture a register merely to make the folder look complete.

### Scaffold a domain

```bash
vyd domain new api-design --registers standard
```

With `--registers standard`, this creates:

```text
<kb>/domains/api-design/
  domain.toml
  facets.md
  standards.md
  skills/
    api-design/
      SKILL.md
```

Or choose a location:

```bash
vyd domain new api-design \
  --registers standard \
  --path ~/work/vyvid-api-design
```

The command:

- Requires a suitable empty destination.
- Creates one initial register of the selected type.
- Creates facet and skill stubs.
- Initialises Git if the folder is not already inside a repository.
- Prints configuration to add.
- **Does not edit your user configuration.**

Despite the plural option name, `--registers` currently selects one initial register type, and without it the first register is a `note` register in `notes.md`.

The command that adds the new domain to your configuration is `vyd domain add api-design --path ~/work/vyvid-api-design`, described in section 3.

### Edit the manifest

The scaffold starts private. Make visibility an intentional decision.

For example, after replacing the generated family and recipe definitions:

```toml
name = "api-design"
description = "Reusable standards for designing and evolving API contracts"
visibility = "public"
rules = []
parents = ["tools"]

[families]
API = { defined = "standards.md", type = "standard" }

[[recipes]]
name = "api-contract-brief"
description = "Before designing or changing an API contract"
budget = 1200
steps = [
  { step = "find", words = "{question}", kind = "standard", limit = 6 },
  { step = "linked", edges = ["decidedBy", "evidencedBy"], direction = "out" },
  { step = "take", n = 4 },
]
```

A parent must be configured on the machine. Declaring `parents` does not download or configure it.

The scaffold wrote a family named after the register type, `STANDARD` here, and a recipe called `how-do-i`. That recipe name is already declared by the tools, Python and Haskell domains, so rename it before the domain is used beside them.

Manifest paths must remain inside the domain. A manifest cannot grant itself trust or set its remote or Git update policy, because those belong in the user configuration.

### Add useful entries

In `standards.md`:

```markdown
# API standards

| ID | Claim | Problem shape | Activity | Ratified |
|---|---|---|---|---|
| API-1 | **Define retry behaviour before exposing a state-changing operation.** | retries after an uncertain response | api-and-contract-design | no |
```

This example is explicitly proposed. Do not mark a policy accepted merely because a scaffold or agent wrote it.

For observational notes, add evidence naming what was run, the version, platform, and limits of the result.

### Extend facets only where necessary

Reuse existing values before adding new ones.

A domain facet extension can add a value under an existing scheme:

```markdown
## Activity

| ID | Label | Broader | Related | Group | Definition | Scope note | Ratified |
|---|---|---|---|---|---|---|---|
| api-contract-audit | API contract audit | api-and-contract-design | | | Reviewing a wire contract for compatibility and retry semantics. | | yes |
```

Use the exact facet-column order.

Important rules:

- Slugs must be unique across the merged stack.
- Broader values must exist in the same scheme.
- Related values must exist.
- Group concepts organise other concepts and are not entry tags.
- Defining a new value does not automatically tag existing entries.

Custom schemes are possible, but the standard `find` facet options remain Activity, Quality, and Technology.

A project can do the same when a value means something only there, so it need not make a domain to hold one word. Write the same table in a file of the project, for example `docs/facets.md`, under the heading of the scheme it extends, and name the file in the project's `facets` key, by hand or with a command:

```bash
vyd project set example-service facets docs:facets.md
```

Registers are merged in the order of the stack, general first and the project last, so a project's value can name a domain's value as broader or related. A value is seen only by the stacks that hold its register, so a project's value means nothing to another project, and a domain's reaches every project using that domain. Rebuild with `vyd build`, and `--tech`, `--activity` or `--quality` then accept the new value. A slug that some other layer already defines stops the build with exit code 2, naming both places, since two meanings cannot share one slug. A project that adds nothing needs no file, and `facets = []` says so outright.

### Write a task-triggered skill

In `skills/api-design/SKILL.md`:

```markdown
---
name: api-design
description: Use when designing, reviewing or changing an API contract.
---

# API design

Run `vyd recipe run api-contract-brief "<the proposed change>"`.

Read the relevant entries before proposing a contract.
Record unresolved compatibility and retry questions before implementation.
```

Use the skill for procedure and judgement. Keep independently retrievable factual claims in registers rather than duplicating them in several skill sections.

### Add custom register types when needed

A domain may provide `register-types.toml`:

```toml
[values.severity]
low = "Low"
high = "High"

[columns]
"Severity" = { property = "severity", kind = "controlled", values = "severity" }

[types.risk]
class = "Risk"
```

Then declare a family:

```toml
[families]
RISK = { defined = "risks.md", type = "risk" }
```

The default domain location for register-type declarations is `register-types.toml`, and you can also name files explicitly with `register_types`. TOML does not allow an inline table to span lines, so each column is written on one line.

A column’s `kind` says how its cell is read.

| Kind | The cell is read as |
|---|---|
| `id` | The row’s identifier, matched against its family |
| `claim` | The bold lead of the cell, or the whole cell, within the claim limit |
| `label` | The entry’s name |
| `text` | The cell as written |
| `ids` | Identifiers of other entries, resolved in the register’s scope |
| `targets` | Identifiers, or prefixed names of declared terms |
| `addenda` | Decision addenda that narrow the entry |
| `names` | Names of derived things, each an edge to the node of that name |
| `module` | A module or tool package the entry belongs to |
| `controlled` | One or more values of a closed set declared under `[values]` |
| `facet` | One or more values of a facet scheme |
| `status` | A ratified flag, yes or no |

Use custom types and vocabulary where they change retrieval or checking. Avoid introducing distinctions with no consumer.

### Register and exercise the domain

For a domain you authored:

```toml
[[domains]]
name = "api-design"
path = "~/work/vyvid-api-design"
trust = "own"
```

Add it to the project’s `domains`, then review and re-trust the changed project configuration.

Exercise it:

```bash
vyd config
vyd context
vyd build
vyd find "retry a request after losing its response"
vyd recipe list
vyd recipe run api-contract-brief "add a state-changing endpoint"
vyd install --project
vyd check skills
vyd check identifiers
```

A domain may cite itself, its ancestors, and the general scope. It must not depend on downstream project knowledge or arbitrary sibling domains. If a shared dependency is real, model it as a parent.

Before publication, audit the domain and check that reusable text contains no private paths, credentials, or downstream-only instructions.

---

## 14. Build task-specific briefings with recipes

A recipe is a named sequence that gathers and narrows context. It is not a natural-language prompt that can perform arbitrary actions.

### Define a project recipe

Add:

```toml
[[project.recipes]]
name = "design-brief"
description = "Before designing or changing a component"
budget = 1200
steps = [
  { step = "find", words = "{question}", kind = ["standard", "principle", "decision"], limit = 6 },
  { step = "linked", edges = ["decidedBy", "supports", "enforcedBy"], direction = "both" },
  { step = "take", n = 4, per_kind = true },
]
```

Run:

```bash
vyd recipe list
vyd recipe run design-brief "change request validation"
```

Additional forms:

```bash
vyd recipe run design-brief "change request validation" --dry-run
vyd recipe run design-brief "change request validation" --json
vyd recipe run design-brief "change request validation" --all
```

The budget is an approximate token budget, estimated at four characters a token, and the briefing drops its last entries when it runs over. `--all` disables output trimming, `--dry-run` prints each step and each glue command with its folder and runs nothing, and `--json` prints the entries as JSON.

### Understand the step types

| Step | Effect |
|---|---|
| `find` | Add ranked entries using query words and optional filters |
| `linked` | Follow selected declared relationships |
| `include` | Add explicitly named entries |
| `take` | Keep the first entries, optionally per kind |
| `glue` | Run project-owned code that transforms the accumulated entries |

Normal gathering steps deduplicate entries. A `take` step narrows what has accumulated.

A `find` step takes the filters of `vyd find` as keys, namely `kind`, `exclude`, `phase`, `audience`, `activity`, `quality` and `tech`, together with a `scope` to add or restrict and a `limit` that is eight when omitted. A `linked` step follows `supports`, `refines`, `decidedBy`, `evidencedBy`, `enforcedBy`, `dependsOn`, `waitsOn`, `distinguishedFrom`, `bearsOn`, `answers` or `supersededBy`, outwards, inwards or both ways. A recipe of a narrower scope replaces a recipe of the same name in a wider one.

Use `include` for mandatory context that should not depend on semantic rank:

```toml
{ step = "include", ids = ["STD-1"] }
```

Those identifiers resolve in the recipe’s declaring scope.

### Add project glue deliberately

Only project recipes can declare glue:

```toml
{ step = "glue", command = ["python", "tools/enrich_briefing.py"], seconds = 30 }
```

This assumes you implement `tools/enrich_briefing.py`.

Its contract is:

- Read a JSON list of entries from standard input.
- Write a JSON list to standard output.
- Give every returned entry a string `id`.
- Exit non-zero on failure.
- Keep diagnostics on standard error.

Useful entry fields include `kind`, `scope`, `claim`, `pointer`, and `signposts`.

The command runs in the project’s code folder, within `seconds` (30 when omitted), with a minimal environment plus any variables the step names in `env`. It needs the project to be trusted. Otherwise the run refuses and suggests stopping at glue, so that your client can approve the command instead.

Glue replaces the accumulated result, so it can discard context as well as enrich it. Test both inclusion and accidental-loss cases.

### Keep command execution visible

With:

```toml
[framework]
glue = "stop"
```

Vyvid stops before each glue command rather than running it itself.

Or stop for one run:

```bash
vyd recipe run design-brief "change request validation" --stop-at-glue
```

At a glue step, Vyvid prints the command, working folder, input file, output file, and resume command. After approving and running that exact command, resume with:

```bash
vyd recipe run \
  --resume <state-file> \
  --glue-output <output-file>
```

Stopping at glue returns exit code **3**. Automation must distinguish that from completion.

A command you run yourself receives your shell’s environment. That differs from the minimal environment supplied when Vyvid runs glue.

---

## 15. Search source code and declared ontology terms

### Configure source-symbol extraction

Install the `symbols` extra, then add project source paths:

```toml
[[project.symbols]]
language = "python"
paths = ["code:src/**/*.py"]
```

Supported languages are:

```text
python
haskell
java
typescript
```

A project can declare multiple symbol specifications.

Build and query:

```bash
vyd build
vyd find "validate incoming request fields" --kind symbol
```

Read the identifier returned:

```bash
vyd read <symbol-identifier>
```

Symbol identifiers have forms such as:

```text
package:Module.name
```

The symbol search also retrieves selected prose around source code, such as module documentation and comments. Prose results can use identifiers shaped like:

```text
package:Module#heading
```

Use the exact returned identifier rather than constructing one from an assumed package name.

### Know the limits of symbol search

Symbol extraction:

- Reads Git-tracked matching files.
- Parses source rather than executing project code.
- Reuses unchanged extraction results.
- Stores symbols separately from the knowledge graph.
- Does not provide compiler-resolved call or reference relationships.

New source files must be tracked before they participate. Because nothing in the clone runs, symbol search works before the project file is trusted, although its results are labelled as data until then.

Control the maximum share of documentation results for a query:

```bash
vyd find "request validation" --kind symbol --doc-share 0.2
```

The default cap is `0.4`. It can also be configured on the project or framework.

Do not combine `symbol` with other kinds in the same query. Ask the knowledge and source questions separately.

### Hand off exact compiler questions

For Haskell, register an existing compiler index:

```toml
[[project.code_index]]
kind = "hiedb"
database = "code:.build/hie.db"
built_by = "mise run build:index"
sources = "code:src"
```

Here `built_by` is shown to agents as text and withheld until the project file is trusted, and `sources` lets Vyvid say that the database may be stale when those files are newer than it. Then:

```bash
vyd handoff validateRequest --module Example.Validation
```

Vyvid checks that the registered database exists and holds rows, and prints commands from its known templates. It does not build the database or run those commands. Given a module name instead of a definition, `vyd handoff` lists what that module calls, and `--unit` keeps that list to the units whose names start with the text you give. `vyd context` lists each registered index.

At the inspected revision, `hiedb` is the kind with implemented command templates.

Use semantic symbol retrieval to locate likely code, and use the compiler index for exact definition and reference questions.

### Configure ontology extraction separately

The packaged `owl-terms` extractor can be used directly:

```toml
[[project.extractors]]
kind = "owl-terms"
paths = ["code:ontology/**/*.ttl"]
```

Then:

```bash
vyd build
vyd find "a retained record" --kind term
vyd exists "retention"
```

The extractor derives declared RDF/OWL terms and associated summaries from configured ontology files.

The RDF-modelling domain supplies modelling procedure but does not currently declare this extractor for you. Do not assume a configuration path such as `uses.rdf-modelling.owl-terms` is valid unless that domain actually declares the extractor.

---

## 16. Add project-owned extractors

An extractor is appropriate when your project has structured knowledge that should become indexed facts: a module catalogue, ownership register, service inventory, or other domain-specific source.

Prefer an extractor over copying the same information into another manually maintained register.

### Declare a command extractor

```toml
[[project.extractors]]
kind = "service-catalogue"
command = ["python", "tools/extract_service_catalogue.py"]
paths = ["docs:service-catalogue.md"]
code = ["code:tools/extract_service_catalogue.py"]
seconds = 300
```

This assumes you implement the named script.

- `paths` declares input sources for staleness tracking.
- `code` declares implementation files whose changes also invalidate the index.
- `seconds` bounds command execution and is 300 when omitted.
- `env` can explicitly name additional environment variables.

The command runs in the checkout root. It requires the trust applicable to its configuration source.

### Implement the protocol

The command receives one JSON request on standard input, including:

```json
{
  "protocol": 1,
  "kind": "service-catalogue",
  "scope": "example-service",
  "root": "<checkout-root>",
  "settings": {},
  "paths": ["<configured-input-path>"],
  "output": "<temporary-output-folder>",
  "graphs": {
    "index": "<permitted-index-graph>",
    "terms": "<permitted-terms-graph>"
  }
}
```

It writes into the supplied output folder:

```text
result.json
quads.nq
```

`quads.nq` is optional if there are no quads. If present, every quad must use one of the two supplied graph names.

A result can include:

```json
{
  "protocol": 1,
  "version": "1",
  "problems": [],
  "findings": [],
  "texts": {},
  "prefixes": {},
  "counts": {},
  "units": {},
  "unit_paths": {}
}
```

Important fields:

| Field | Purpose |
|---|---|
| `texts` | Text to embed, keyed by node IRI |
| `prefixes` | Declared prefixes for term references |
| `counts` | Reported extraction counts |
| `units` | Names and the project units they represent |
| `unit_paths` | Repository folders mapped to the units that own the terms declared under them |
| `problems` | Explicit failures or omissions |
| `findings` | Informational extraction results |

A text key must identify a subject the extractor actually emitted in its quads.

Declared units allow register ownership columns to link to real project units.

By default a term is owned by the folder of the document that declares it. When the result declares `unit_paths`, a term declared under one of those folders is owned by the mapped unit instead, and where several paths contain a term the longest one wins. A trailing slash on a path is ignored. A term under none of the paths keeps the folder of its document, so a project that declares no paths keeps folder ownership and is not forced to keep a unit catalogue. A path that names a unit which no extractor’s `units` declare is reported as a problem.

### Handle failure honestly

Malformed output, timeouts, an unknown protocol, or quads outside the permitted graphs cause the extractor’s output to be refused.

The build reports the problem and can continue without that extractor’s entries. Your CI or build policy should decide whether that omission is acceptable.

### Know the extension boundary

Reusable installed extractors use the `vyvid.extractors` Python entry-point group and an `extract(context, settings) -> Result` interface.

A domain can declare an installed extractor kind and defaults. A project can override supported settings through `uses`.

A domain cannot supply a command extractor merely by placing a script in its clone. Command execution must come from an appropriate project declaration.

**Neither command extractors nor glue are sandboxed.** A minimal environment and restricted output graphs do not prevent the process from reading or modifying files it has permission to access.

---

## 17. Maintain domains, identifiers, and private knowledge

### Choose a managed-domain Git policy

A managed domain lives beneath the configured knowledge base and is a clone of its configured remote.

Supported policies are:

| Setting | Values |
|---|---|
| `pull` | `on-start`, `daily`, `manual` |
| `commit` | `manual`, `auto` |
| `push` | `manual`, `auto` |

Without explicit policy, the defaults are:

```toml
git = { pull = "on-start", commit = "manual", push = "manual" }
```

Use explicit manual policies when you want predictable, review-driven updates.

```bash
vyd kb status
vyd kb pull tools
vyd kb pull --due
```

Pulls fast-forward only, and Vyvid does not merge or stash a diverged domain for you. `vyd context` pulls what is due before it answers unless it is given `--no-pull`.

For a domain not marked `own`, updates to instruction-bearing files can be held for review. After reading the reported diff, a person can run:

```bash
vyd kb accept tools
```

Accepting the update does not update `trust` or the reviewed commit. Those remain separate decisions.

### Record a domain change

For a managed domain you are authorised to update:

```bash
vyd kb record \
  ~/work/vyvid-kb/domains/tools/notes.md \
  -m "Document the observed tool behaviour"
```

The policy determines whether this stages, commits, or also pushes. A `commit_trailers` list in `[framework]` appends fixed lines, such as a co-author trailer, to every message that `vyd kb record` commits.

Vyvid scans candidate files for recognised credential formats and can also use `gitleaks` when installed. This is accident prevention, not a guarantee that a file contains no sensitive information.

Automatic commit and push are consequential. Reserve them for domains and workflows where that authority is intentional.

### Check identifiers

```bash
vyd check identifiers
vyd check identifiers --all
vyd check identifiers --json
```

The check reads tracked Markdown, not an unrestricted filesystem walk.

It fails on unresolved references and duplicate definitions, and it reports spelling variants without failing them. Normalisation tolerates several separator and case differences while preserving meaningful dots.

A passing check prints a single summary line. Its counts of identifiers, unresolved references and duplicate definitions come first. After the words “Reported, never failed” it counts what is reported but cannot fail the check, namely spelling variants, references to removable entries that are no longer defined, and stale exceptions. Plain output lists none of those, and `--all` lists each of them. If the project builds symbols, a mention of a symbol identifier that the symbol store no longer holds is also listed as `symbol gone` and never fails. The exit code is 1 on an unresolved or twice-defined identifier, or on a pattern that ran out of time, 2 when the tracked files cannot be listed, and 0 otherwise. `--json` prints everything found.

Useful family controls include:

- `removable = true`: report references to removed entries without failing them.
- `defined_only = true`: avoid treating every match of a loose pattern as a reference.
- `exceptions`: explicitly baseline otherwise undefined identifiers with reasons, one per line with the reason after a `#`. An exception that nothing needs any longer is reported as stale. The project can name one baseline for every family with `identifiers.exceptions`.
- Project skip and generated-region rules. `identifiers.skip` lists globs of tracked files to leave out, matched against the path or the file name, and `identifiers.generated` is a pattern that marks a file as a generated copy when its first 200 characters match it.

Current defaults already recognise standard generated regions beginning with `<!-- BEGIN GENERATED` and ending with `<!-- END GENERATED`. Do not suppress an entire roadmap merely because an older integration lacked region handling.

Duplicate register identifiers must be resolved, not hidden. The check reports definition sites and can identify the earlier committed row that keeps its identifier.

### Move reusable knowledge into a domain

A project can declare that an existing family or selected rows moved to a domain:

```toml
[[project.moves]]
family = "STD"
to = "api-design"
source = "docs:standards.md"
commit = "<source-commit>"
rows = { "STD-12" = "API-1" }
```

This preserves resolution of historic project references without requiring every mention to be rewritten. In your user configuration, the same table is written `[[projects.moves]]` under the project’s entry.

Check relevant branches before removing the old source:

```bash
vyd move check
vyd move check --ref <branch-or-ref>
```

The command compares the entries a move names, as the source stood at the move’s `commit`, with the source in the working tree or at the ref, by identifier. It exits 1 when anything differs, 2 when something cannot be read, and 0 otherwise, and `--json` prints the differences as JSON. A source file that is absent at the ref is reported on one line as `file-absent` and is not counted as a difference, because the project removed it. The domain a move names must be in the project’s stack of domains.

Once the project has removed its own copy, say so on the move:

```toml
[[project.moves]]
family = "STD"
to = "api-design"
source = "docs:standards.md"
commit = "<source-commit>"
copy_removed = true
```

`vyd move check` then stops comparing the copy and reports the move as `copy-removed`, which is not a difference either. With no ref this is the whole answer. With a ref, the move is reported as `copy-removed` where the source at the ref is byte-identical to the working tree’s, since the ref then carries the removal, and no ancestry is read, so the answer still holds after a squash merge. Where the source at the ref differs, its entries are still compared, so an entry the ref changed or added is reported, except that an entry the ref has removed since the move is dropped, because that removal loses nothing.

Plan public links and relocation notes separately. Identifier resolution does not repair external URLs to moved documents.

### Keep private documents outside public code

A user-level project entry can place documents elsewhere:

```toml
[[projects]]
name = "contribution"
code = "~/work/contribution"
docs = "~/work/contribution-documents"
contract = "docs:CONTRACT.md"
domains = ["tools"]
git = { docs = { commit = "manual", push = "manual" } }
```

Documents outside the code root are private by default. Setting `docs_visibility = "public"` on the project entry makes them public.

Entries defined there are marked private, and `find` labels them so. Check publication material before sending it, since the citation check refuses a line of the code repository that cites one of them, bare or qualified:

```bash
vyd check citations --staged
vyd check citations --message /path/to/proposed-message.md
```

The second command can check prepared commit or pull-request text. Files or folders given as arguments are checked line by line, and `--in` names the folder whose project is checked.

This is an identifier-based guard. It does not detect every paraphrase, copied passage, or sensitive fact.

To stage external document changes under their configured policy:

```bash
vyd docs record \
  ~/work/contribution-documents/notes.md \
  -m "Update the contribution notes"
```

This applies to a separate documents repository, not a way to bypass the code repository’s commit policy.

### Set up a project whose documents live in another repository

This guide has described the pieces of a project whose documents are kept apart from its code. Take the case where the code is in `~/work/some-project`, a repository you do not own or one whose history should not hold your plans, and your plans, standards and debts are in `~/work/private-docs/some-project`, a repository of your own. These commands take you from a configuration that names only the knowledge base to a working project, and each can be run with `--dry-run` first. In the output below, `<config>` stands for the path `vyd config` prints.

Start in the code checkout, so that it can be read:

```bash
cd ~/work/some-project
```

Add the shared tools domain. It is a knowledge domain, and its clone is made later:

```bash
vyd domain add tools --remote https://github.com/example/vyvid-tools
```

```text
writing <config>
--- <config>
+++ after
@@ -1,2 +1,7 @@
 [framework]
 kb = "~/work/vyvid-kb"
+
+[[domains]]
+name = "tools"
+remote = "https://github.com/example/vyvid-tools"
+trust = "knowledge"
wrote <config>
~/work/vyvid-kb/domains/tools does not exist yet. Clone it with: vyd kb clone tools
```

Clone it with the command it names:

```bash
vyd kb clone tools
```

Declare the project. Its code folder and its remotes are read from the checkout, and its documents are in the other repository:

```bash
vyd project add some-project \
  --docs ~/work/private-docs/some-project \
  --contract docs:CONTRACT.md \
  --domain tools
```

```text
+[[projects]]
+name = "some-project"
+visibility = "private"
+code = "~/work/some-project"
+match = { remote = ["github.com/example/some-project"] }
+docs = "~/work/private-docs/some-project"
+contract = "docs:CONTRACT.md"
+domains = ["tools"]
```

The documents folder is outside the code folder, so the project's entries are private, and the citation check refuses a line of the code repository that cites one. Now let the scan read the tables of the documents folder:

```bash
vyd project scan some-project
```

```text
project some-project: scanned ~/work/private-docs/some-project
Proposed, to read before it is written to <config>:
[projects.families]
SP = { defined = "docs:INDEX.md", type = "slice" }   # 1 row in INDEX.md
STD = { defined = "docs:standards.md", type = "standard" }   # 1 row in standards.md
TD = { defined = "docs:technical-debt.md", type = "debt" }   # 1 row in technical-debt.md
Write them with: vyd project scan some-project --apply
```

If the proposal is right, write it. If a table was named as not placed, declare its family yourself with `vyd family add` once you know its type:

```bash
vyd project scan some-project --apply
```

Check the result, build the index, and ask it something:

```bash
vyd config
vyd build
vyd find "how do we keep the export fast" --in ~/work/some-project
```

`vyd config` lists the domain and the project and reports every problem with the same loader that checked each write. `vyd build` indexes the registers of the other repository under the project's name, and `vyd find` answers from them in the folder of the code checkout. To change the project later, `vyd project set some-project docs <folder>` moves its documents, and `vyd family remove` drops a family. Nothing here records trust, deletes a folder or touches the other repository, and the configuration you now hold reads exactly as one you wrote by hand.

---

## 18. Inspect the graph and improve retrieval

### Query the active graph directly

For questions not covered by the convenience commands:

```bash
vyd sparql '
PREFIX ki: <https://www.nebularis.org/vyvid/knowledge#>

SELECT ?id ?claim WHERE {
  GRAPH ?g {
    ?entry ki:identifier ?id ;
           ki:claim ?claim .
  }
}
LIMIT 20
'
```

Queries see the selected stack’s graphs, not every configured project indiscriminately.

Use graph inspection to investigate extracted facts and relationships. Do not modify the derived store as a substitute for fixing sources.

### Use misses as a maintenance queue

```bash
vyd misses
vyd misses --near
```

Vyvid records unanswered or weak questions, near answers, and explicitly recorded gaps. The misses command can recheck earlier questions and remove ones that now have adequate answers. It shows only the questions of the project whose folder you are in, as the next section explains.

When retrieval fails, determine whether the problem is:

- A missing entry.
- A poor claim or problem description.
- A missing facet.
- A missing relationship.
- An omitted or malformed source.
- The wrong project or scope.
- An over-restrictive filter.
- A question that belongs to a different tool.

Do not immediately tune the model to compensate for missing knowledge.

### Configure logging and storage deliberately

Question logs live beside the index, in a `logs/<project>` folder of the store for each project. A question asked where no project claims the folder is logged under `general`. This keeps one project’s questions out of another’s report, because asking again removes the questions the index now answers and a project’s misses are neither another index’s to answer nor another project’s to report. A linked worktree writes under the base store, so its gaps outlive the worktree. Logs written before the per-project folders existed are left where they were, directly in the store folder, and nothing reads them. Delete or keep them according to your own retention policy.

To disable the creation of logs:

```toml
[framework]
logs = false
```

Changing this setting stops new logging. Handle existing local logs according to your own retention policy.

To write nothing to the logs for a single call, pass `--no-log` to `vyd find` or `vyd read`, for example when a benchmark asks many questions that should not read as a project’s misses. The other question commands have no such option.

The framework can also set a custom index store:

```toml
[framework]
store = "~/work/vyvid-index"
```

Linked worktrees receive separate derived stores so one checkout’s code does not become another checkout’s symbol or document answer.

Remove stores belonging to deleted worktrees with:

```bash
vyd store prune --dry-run
vyd store prune
```

### Change embeddings only with evidence

An `[embedding]` section can configure the model, revision, file hashes, cache, query prefix, thresholds, and facet boost.

A different model needs a pinned revision and expected file hashes. Its vectors must not be mixed with vectors from another model.

The weak and near thresholds are model-specific retrieval settings. Evaluate representative project questions before changing them.

---

## 19. Add checks to your project workflow

A useful baseline is:

```bash
vyd check identifiers
vyd check skills
vyd work check
```

For publication and staged work:

```bash
vyd check citations --staged
vyd work check --staged
```

Keep their meanings distinct:

| Check | Establishes |
|---|---|
| `check identifiers` | Tracked Markdown references and definitions are consistent |
| `check skills` | Committed generated skills match their available sources |
| `work check` | Status records follow configured grammar and the generated work index agrees |
| `check citations` | Supplied public text does not cite recognised private entries |
| Project tests | The relevant software behaviour actually works |

These checks do not replace one another.

`work check --staged` selects touched records using staged paths, but reads record contents from the working tree. Avoid assuming it independently validates an exact staged snapshot while unstaged edits remain in those files.

`vyd` works when Git runs it from a hook. Git exports `GIT_DIR` and `GIT_WORK_TREE` to a hook, and under them a request for the repository’s top level answers with the folder itself, so `vyd` clears both when it starts and finds the repository from the folder it is given. It keeps `GIT_INDEX_FILE`, because a partial commit gives the hook a temporary index and `--staged` should read that one. Only the names of the staged records come from it, as the previous paragraph says.

For CI, supply all required domain sources at the intended revisions. For local hook integration, ensure generated files and their source changes are reviewed and staged together.

A lifecycle skill describing a hook does not mean the hook exists. Implement project Git hooks and CI gates explicitly, and distinguish a skipped or unavailable check from a successful one.

---

## 20. Troubleshooting

| Symptom | Likely explanation and action |
|---|---|
| `vyd` is not found | Check the tool installation and uv executable path |
| `uv tool install vyvid` fails | Use the Git-source installation, since PyPI availability must not be assumed |
| Context shows only general scope | Check the working folder, project binding, and `vyd config` |
| A domain contributes nothing | Check its local folder, manifest, set-aside diagnostics, and project selection |
| A skill-only domain has no search results | Its procedure reaches agents through skills, and it has no register to retrieve |
| Contract or skills are withheld | Review trust standing, since a person may need to trust the project file or review the current domain commit |
| A domain update is held | Read the reported diff, then have a person accept it if appropriate |
| Semantic search cannot rank | Check model availability and build diagnostics, and use direct source reading or textual `exists` while resolving it |
| A high-ranked entry is wrong for the task | Read its status, evidence, flags, and non-coverage, because similarity is not authority |
| Source symbols are missing | Check the symbols extra, language declaration, paths, and Git tracking |
| Ordinary search omits slices or terms | Request `--kind slice` or `--kind term` |
| The board misses a fresh edit | The cross-branch view reads committed tips, so inspect the local record or use the checkout-local view |
| Plain `vyd here` does not show you | Register with `--role` and ensure the session identifier is distinct |
| A work index is stale | Update source records, run `vyd work build`, and include the generated change |
| Skill checking exits 1 | It found a problem. Run `vyd install --project` and commit the regenerated skills, or fix a missing placeholder value |
| `vyd install` writes nothing | No client folder exists. Name a client with `--client` |
| `vyd misses` shows nothing from before an upgrade | Questions are logged per project under `logs/<project>` now, and older shared logs are no longer read |
| A configuration works but its glue and extractors do not run | A configuration at a path other than your own, or a `vyvid.toml` nobody has trusted, needs `vyd trust` run in a terminal |
| Skill checking exits 2 | The comparison did not run meaningfully, so fix missing sources, binding, or trust |
| The wrong `how-do-i` recipe runs | Inspect `vyd recipe list`, because same-name recipes replace one another |
| A custom extractor is absent | Inspect trust, command failure, protocol, and graph-validation diagnostics |
| A public-text check passes despite sensitive prose | Citation checking is not a general confidentiality detector |

---

## Daily operating pattern

For ordinary project work:

```bash
vyd context
vyd find "the change in your own words"
vyd recipe list
```

For lifecycle-managed implementation:

```bash
vyd board --fetch
vyd here --role build --on <slice-id>
```

Read the plan and home status record, satisfy the approval gates, and mark the work before implementation.

After changing knowledge or records:

```bash
vyd work normalise --apply
vyd work build
vyd work check
vyd build
vyd check identifiers
```

After changing skill sources:

```bash
vyd install --project
vyd check skills
```

At handoff, report the actual implementation state, actual validation results, remaining gates, and retrieval gaps:

```bash
vyd misses --near
vyd here --leave
```

The governing principle is simple: **record knowledge once, derive its views, retrieve it in the right scope, and keep implementation claims separate from verified results.**