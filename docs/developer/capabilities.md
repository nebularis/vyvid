<!-- SPDX-License-Identifier: MIT -->

# Capability register

**Unit type:** Register

What Вивід's own software can already do, so new work reuses it. Each row names its entry point and the code that provides it.

| ID | Capability | Problem shape | Entry point | Audience | Phase | Activity | Quality | Technology | Fitness scope | Cadence | Pointer | Ratified | Scope | Bears on |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| CAP-1 | **Print the contract that applies in a folder, the general scope, its project's domains with their ancestors, parents first, and the project last, marking each missing rule or skill.** | an agent starting work in a folder and needing to know which rules apply there | `vyd context [folder] [--json]` | published | development | | | python | | | src/vyvid/cli.py::context | no | vyvid | |
| CAP-2 | **Resolve an identifier to its canonical scope:LOCAL, a bare one in the scope it is written in, through that scope's families or its delegations, refusing one that names nothing or several things.** | an identifier cited across projects or moved with its register | `vyd resolve <identifier> [--in folder]` | published | development | | | python | | | src/vyvid/resolve.py::resolve | no | vyvid | |
| CAP-3 | **Load the configuration of scopes, domains and projects and refuse it whole, every problem listed, when a reference names nothing or the domains form a cycle.** | a configuration edited by hand | `vyd config` | published | development | | | python | | | src/vyvid/config.py::load | no | vyvid | |
| CAP-4 | **Check this repository's text: a semicolon in prose fails and a hard-wrapped line warns on every Markdown file, and on user-facing text a working document or a delivery identifier fails.** | text that breaks the writing or publication rules | `mise run check:writing` | internal | development | | | python | atomic | triggered | tools/check_writing.py::main | no | vyvid | |
| CAP-5 | **Clone, pull and record the managed domains of the knowledge base by each domain's git policy, pulling only by fast-forward and never committing or pushing a project's files.** | a register in a shared domain changed by an agent | `vyd kb status`, `vyd kb clone`, `vyd kb pull`, `vyd kb record` | published | development | | | git | | | src/vyvid/kb.py::record | no | vyvid | |
| CAP-6 | **Refuse a public project's change whose added lines cite an entry of a private scope, qualified or bare through a delegated family, from the staged diff or given files.** | private knowledge reaching a public repository | `vyd check citations [--staged] [paths]` | published | development | | | git | atomic | triggered | src/vyvid/citations.py | no | vyvid | |
