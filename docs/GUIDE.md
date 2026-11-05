# User Guide

## Vyvid: from first setup to an agentic development lifecycle

Vyvid gives coding agents a searchable, project-scoped body of knowledge: rules, decisions, findings, questions, skills, and references into source code. Its command-line tool is **`vyd`**.

The essential division is:

- **Your source files are authoritative.** Registers, contracts, plans, skills, and code remain ordinary files that you review and version.
- **Vyvid derives context from those sources.** It resolves identifiers, builds indexes, ranks relevant entries, and composes instructions for agent clients.
- **Domains provide reusable knowledge and procedures.** A project selects domains and adds its own specialisations.
- **The lifecycle domain provides a development procedure.** Vyvid’s work-board commands support that procedure, but do not autonomously implement, verify, or deliver your software.

This guide describes the implementation at version **0.2.7**, inspected on **5 November 2026**. Examples use a fictional project named `example-service`. Replace its paths, commands, and identifiers with your own.

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
- In both, with the matching user entry overriding the repository file’s keys.

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

The commands below assume a POSIX-style shell. Configuration is TOML on every platform. Use the corresponding shell syntax for environment variables on Windows.

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

If your shell cannot find `vyd`, check that uv’s tool executable directory is on `PATH`.

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

The model is downloaded into the platform cache on first use. Embedding and ranking then run locally. Vyvid does not require a hosted embedding service.

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

Use the path reported by the command rather than assuming a particular operating-system layout.

The user configuration and a project’s `vyvid.toml` serve different purposes:

| File | Put here |
|---|---|
| User configuration | Knowledge-base location, domain remotes, trust, update policies, personal paths, private project bindings |
| Repository `vyvid.toml` | Portable project configuration, public domains used, register families, work settings, symbol paths, skill composition |

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

A domain with a remote defaults to `knowledge`. A domain without a remote defaults to `own`. Do not rely on that default for someone else’s files.

Inspect a domain without running anything from it:

```bash
vyd domain audit ~/work/vyvid-kb/domains/lifecycle
git -C ~/work/vyvid-kb/domains/lifecycle rev-parse HEAD
```

Read its manifest, rules, skills, and other relevant files. The audit reports facts such as links, command-shaped text, hidden characters, and paths. It does not certify safety.

After reviewing, change that domain’s existing configuration entry:

```toml
trust = "reviewed"
commit = "<the-commit-you-reviewed>"
```

Use a real commit hash, preferably the full hash. This is a change to the existing entry, not a second `[[domains]]` entry with the same name.

**Reviewed trust is not a checkout pin.** It enables instructions when HEAD matches the configured commit. If HEAD moves, the domain falls back to knowledge-only standing until you review the new revision and update your configuration.

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

Before trust, the repository configuration supplies knowledge, but its contract and skills are withheld as instructions, and its command extractors and glue do not run.

A person who has reviewed the configuration then runs:

```bash
vyd trust
```

This command requires an interactive terminal and confirmation. It is not a bootstrap step for an agent to approve on someone’s behalf.

Trust is recorded against the file’s contents. Changing `vyvid.toml` requires renewed trust. Linked worktrees of the same repository share the trust record when they contain the same configuration bytes.

Then inspect the active context:

```bash
vyd context
```

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

Use an explicit `pattern` when your identifiers differ from the default.

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

A link exists because the sources declare it. Semantic similarity does not automatically create a dependency or evidence edge.

### Build and inspect

After adding or changing knowledge:

```bash
vyd build
vyd check identifiers
vyd find "validate a request before saving it"
vyd read STD-1
```

The first build may download the embedding model.

Build output matters: a command can produce a usable partial index while reporting omitted or malformed sources. Do not ignore extraction problems merely because some queries work.

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

The available kinds come from the active stack’s register-type declarations.

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

Use declared values. An unknown value is an error, not a request for Vyvid to invent a new tag.

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

`exists` performs textual lookup over declared ontology terms and selected kinds of existing project entries. It is useful for checking whether something already exists before introducing another name.

It is not a substitute for semantic `find`.

### Remember what is intentionally hidden

Ordinary `find` does not mix every possible result surface together:

- Declared ontology terms are requested with `--kind term`.
- Source symbols are requested with `--kind symbol`, alone.
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

Without a client option, Vyvid installs for supported clients whose directories already exist.

Explicitly target one:

```bash
vyd install --client claude-code
vyd install --client copilot
```

Project installation:

```bash
vyd install --project --dry-run
vyd install --project
vyd check skills
```

| Installation | Purpose |
|---|---|
| User | Core integration and eligible personal domain skills |
| Project | Composed public skills and configured reminder hooks in the checkout |

Project-generated skills are intended to be committed so contributors and agents can read them without first installing Vyvid.

**Do not edit generated skills.** Edit the domain, project skill sources, additions, or configuration, then regenerate.

### Know the current client boundaries

User-level installation supports:

- Claude Code, under `~/.claude`.
- Copilot, under `~/.copilot`.

Project skill destinations are configurable with `skill_targets`.

Reminder-hook configuration supports `claude-code`, `copilot`, and `codex`. This does not mean `vyd install --client codex` is supported.

Claude Code receives a user-level rule file. Copilot does not receive an equivalent always-on personal rule file from this integration. Put essential project guidance in the instruction file your client actually loads.

### Public and private domain skills

Trusted public domains normally reach agents through project composition.

Trusted private-domain skills are installed at user level, not copied into a checkout where they could be committed.

A public domain can request user-level installation with:

```toml
user_skills = true
```

Use this deliberately. Personal skills can take precedence over project skills with matching names.

### Understand the reminder hook

The reminder hook encourages an agent to ask the index before broad searching, and again after repeated searches without an index question.

It:

- Reminds rather than blocks.
- Runs before relevant tool calls in Claude Code and Codex.
- Runs after relevant tool calls in Copilot.
- Does not replace project instructions.
- Does not implement Git commit or merge gates.

The upstream documentation reports exercised integrations for Claude Code and Copilot. Codex’s integration was not reported as exercised at the inspected revision.

### Handle missing sources honestly

If a required domain is missing, project skill installation does not silently write a reduced set.

`vyd check skills` uses exit code **2** when it cannot perform a meaningful check, including missing domain sources or an untrusted project file. That is not a passing comparison.

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

Recipes are selected by name across the active stack. A later declaration replaces an earlier one with the same name. They do not all run together.

Check the effective recipe:

```bash
vyd recipe list
```

For a project using several such domains, define clearly named project recipes such as `python-symbol-brief` or `compiler-index-brief` rather than assuming `how-do-i` means the same thing everywhere.

---

## 9. Run an agentic lifecycle with `vyvid-lifecycle`

The [lifecycle domain](https://github.com/nebularis/vyvid-lifecycle) supplies a detailed procedure for designing, planning, implementing, reviewing, and delivering work.

It is **not an autonomous runner**. Skills tell agents how to behave. Work commands read and maintain records. Your client, maintainers, and project tooling control execution and permissions.

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

However, no generated index or roadmap is implied until you configure those files.

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

The composition engine derives several location values from `project.work`, including plans, status, sketches, validation, decisions, and index.

Some values need explicit attention:

- Work configuration uses `reviews`. The skill placeholder is `review`.
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

Sketches, review requests, and separate validation documents support the process. The domain identifies plans and status records as the mandatory unit documents. Its default slice-delivery procedure additionally calls for a Validation Pack. If you adopt a lighter evidence format, explicitly adapt that procedure rather than silently dropping it.

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
APP = {
  pattern = 'APP-\d+[a-z]?(?:\.\d+[a-z]?)*',
  defined = "docs:status/*.md",
  type = "slice"
}
APPQ = {
  pattern = 'APP-Q\d+',
  defined = ["docs:plans", "docs:sketches"],
  rule = "question",
  type = "question"
}
```

Merge these into your existing family table. Do not duplicate the table declaration.

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

The newest state comes first. The cell preserves the state trail. Git supplies commit history.

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

**Plain `vyd here` lists presence. It does not register you.**

Register an actual role:

```bash
vyd here --role build --on APP-1
```

Other roles are `review` and `read`.

If your client supplies neither `CLAUDE_CODE_SESSION_ID` nor `AGENT_SESSION_ID`, configure a distinct, stable `VYD_SESSION_ID` for that session. `VYD_CLIENT` can identify the client.

Without a distinct session identifier, sessions can share the fallback presence filename and conceal one another.

Presence is:

- Checkout-local.
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
| `--fetch` | Refresh remote refs before reading |
| `--state` | Restrict displayed work by state |
| `--commits` | Show the commit associated with the row’s state |
| `--measure` | Compare branch-added content with trunk |
| `--here` | Read configured slice families in this checkout |

With work settings, the live board reads status records at local and remote branch tips without checking those branches out. It can expose double claims and branches behind trunk’s recorded state.

Without work settings, the simpler checkout-local board uses configured slice families.

**The cross-branch board does not display uncommitted edits as if they were branch-tip state.** Use the local records and generated work index while preparing a change.

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

Its branch inputs use remote-known branches at their remote tips, rather than indiscriminately publishing every local branch. The current working tree also supplies its own records. An unpushed current branch can contribute under an anonymous checkout label without publishing its branch name.

Generated charts derive from recorded dates. They are not forecasts invented for undated planned work.

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

During composition:

- A matching `##` heading appends to that section.
- A new heading is added.
- A heading ending in `(replace)` replaces the matching section.

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

A missing required value prevents that skill from being written.

Use checkout-relative human-readable paths in skill values, such as `docs/status`, rather than machine-specific absolute paths.

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

Without a project prefix, domain-qualified naming helps distinguish skills from different domains.

A project prefix changes naming rules. Two domains with the same short skill name can then collide. Inspect the generated set rather than assuming prefixing always increases uniqueness.

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

This is an example of the mechanism. Choose a domain entry whose actual meaning is appropriate before creating the relationship.

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

By default, this creates:

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

Despite the plural option name, `--registers` currently selects one initial register type.

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

Manifest paths must remain inside the domain. A manifest cannot grant itself trust or set its remote or Git update policy. Those belong in the user configuration.

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
"Severity" = {
  property = "severity",
  kind = "controlled",
  values = "severity"
}

[types.risk]
class = "Risk"
```

Then declare a family:

```toml
[families]
RISK = { defined = "risks.md", type = "risk" }
```

The default domain location for register-type declarations is `register-types.toml`. You can also name files explicitly with `register_types`.

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

The budget is an approximate token budget, estimated from character count. `--all` disables output trimming.

### Understand the step types

| Step | Effect |
|---|---|
| `find` | Add ranked entries using query words and optional filters |
| `linked` | Follow selected declared relationships |
| `include` | Add explicitly named entries |
| `take` | Keep the first entries, optionally per kind |
| `glue` | Run project-owned code that transforms the accumulated entries |

Normal gathering steps deduplicate entries. A `take` step narrows what has accumulated.

Use `include` for mandatory context that should not depend on semantic rank:

```toml
{ step = "include", ids = ["STD-1"] }
```

Those identifiers resolve in the recipe’s declaring scope.

### Add project glue deliberately

Only project recipes can declare glue:

```toml
{
  step = "glue",
  command = ["python", "tools/enrich_briefing.py"],
  seconds = 30
}
```

This assumes you implement `tools/enrich_briefing.py`.

Its contract is:

- Read a JSON list of entries from standard input.
- Write a JSON list to standard output.
- Give every returned entry a string `id`.
- Exit non-zero on failure.
- Keep diagnostics on standard error.

Useful entry fields include `kind`, `scope`, `claim`, `pointer`, and `signposts`.

Glue replaces the accumulated result. It can therefore discard context as well as enrich it. Test both inclusion and accidental-loss cases.

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

New source files must be tracked before they participate.

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

Then:

```bash
vyd handoff validateRequest --module Example.Validation
```

Vyvid checks the registered database and prints commands from its known templates. It does not build the database or run those commands.

At the inspected revision, `hiedb` is the kind with implemented command templates.

Use semantic symbol retrieval to locate likely code. Use the compiler index for exact definition and reference questions.

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

The RDF-modelling domain supplies modelling procedure. It does not currently declare this extractor for you. Do not assume a configuration path such as `uses.rdf-modelling.owl-terms` is valid unless that domain actually declares the extractor.

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
- `seconds` bounds command execution.
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
| `unit_paths` | Repository folders mapped to owning units |
| `problems` | Explicit failures or omissions |
| `findings` | Informational extraction results |

A text key must identify a subject the extractor actually emitted in its quads.

Declared units allow register ownership columns to link to real project units. `unit_paths` also lets ontology terms inherit ownership from the longest matching folder path.

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

Pulls fast-forward. Vyvid does not merge or stash a diverged domain for you.

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

The policy determines whether this stages, commits, or also pushes.

Vyvid scans candidate files for recognised credential formats and can also use `gitleaks` when installed. This is accident prevention, not a guarantee that a file contains no sensitive information.

Automatic commit and push are consequential. Reserve them for domains and workflows where that authority is intentional.

### Check identifiers

```bash
vyd check identifiers
vyd check identifiers --all
vyd check identifiers --json
```

The check reads tracked Markdown, not an unrestricted filesystem walk.

It detects unresolved references, duplicate definitions, and spelling variants. Normalisation tolerates several separator and case differences while preserving meaningful dots.

Useful family controls include:

- `removable = true`: report references to removed entries without failing them.
- `defined_only = true`: avoid treating every match of a loose pattern as a reference.
- `exceptions`: explicitly baseline otherwise undefined identifiers with reasons.
- Project skip and generated-region rules.

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

This preserves resolution of historic project references without requiring every mention to be rewritten.

Check relevant branches before removing the old source:

```bash
vyd move check
vyd move check --ref <branch-or-ref>
```

The command compares moved source entries against the declared source commit. A difference exits non-zero.

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

Documents outside the code root are private by default unless explicitly configured otherwise.

Entries defined there are marked private. Check publication material before sending it:

```bash
vyd check citations --staged
vyd check citations --message /path/to/proposed-message.md
```

The second command can check prepared commit or pull-request text.

This is an identifier-based guard. It does not detect every paraphrase, copied passage, or sensitive fact.

To stage external document changes under their configured policy:

```bash
vyd docs record \
  ~/work/contribution-documents/notes.md \
  -m "Update the contribution notes"
```

This applies to a separate documents repository, not a way to bypass the code repository’s commit policy.

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

Vyvid records unanswered or weak questions, near answers, and explicitly recorded gaps. The misses command can recheck earlier questions and remove ones that now have adequate answers.

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

Question logs live beside the index. To disable their creation:

```toml
[framework]
logs = false
```

Changing this setting stops new logging. Handle existing local logs according to your own retention policy.

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

For CI, supply all required domain sources at the intended revisions. For local hook integration, ensure generated files and their source changes are reviewed and staged together.

A lifecycle skill describing a hook does not mean the hook exists. Implement project Git hooks and CI gates explicitly, and distinguish a skipped or unavailable check from a successful one.

---

## 20. Troubleshooting

| Symptom | Likely explanation and action |
|---|---|
| `vyd` is not found | Check the tool installation and uv executable path |
| `uv tool install vyvid` fails | Use the Git-source installation. PyPI availability must not be assumed |
| Context shows only general scope | Check the working folder, project binding, and `vyd config` |
| A domain contributes nothing | Check its local folder, manifest, set-aside diagnostics, and project selection |
| A skill-only domain has no search results | Its procedure reaches agents through skills. It has no register to retrieve |
| Contract or skills are withheld | Review trust standing. A person may need to trust the project file or review the current domain commit |
| A domain update is held | Read the reported diff, then have a person accept it if appropriate |
| Semantic search cannot rank | Check model availability and build diagnostics. Use direct source reading or textual `exists` while resolving it |
| A high-ranked entry is wrong for the task | Read its status, evidence, flags, and non-coverage. Similarity is not authority |
| Source symbols are missing | Check the symbols extra, language declaration, paths, and Git tracking |
| Ordinary search omits slices or terms | Request `--kind slice` or `--kind term` |
| The board misses a fresh edit | The cross-branch view reads committed tips. Inspect the local record or use the checkout-local view |
| Plain `vyd here` does not show you | Register with `--role` and ensure the session identifier is distinct |
| A work index is stale | Update source records, run `vyd work build`, and include the generated change |
| Skill checking exits 2 | The comparison did not run meaningfully. Fix missing sources, binding, or trust |
| The wrong `how-do-i` recipe runs | Inspect `vyd recipe list`. Same-name recipes replace one another |
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