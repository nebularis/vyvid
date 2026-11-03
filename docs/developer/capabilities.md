<!-- SPDX-License-Identifier: MIT -->

# Capability register

**Unit type:** Register

What Вивід's own software can already do, so new work reuses it. Each row names its entry point and the code that provides it.

| ID | Capability | Problem shape | Entry point | Audience | Phase | Activity | Quality | Technology | Fitness scope | Cadence | Pointer | Ratified | Scope | Bears on |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| CAP-1 | **Print the contract that applies in a folder: the general scope, the domains the folder's project uses with their ancestors, parents first, then the project last, each layer's rules and skills marked where missing.** | an agent starting work in a folder and needing to know which rules apply there | `vyd context [folder] [--json]` | published | development | | | python | | | src/vyvid/cli.py::context | no | vyvid | |
| CAP-2 | **Resolve an identifier to its canonical scope:LOCAL, a bare one in the scope it is written in, through that scope's families or its delegations, refusing one that names nothing or several things.** | an identifier cited across projects or moved with its register | `vyd resolve <identifier> [--in folder]` | published | development | | | python | | | src/vyvid/resolve.py::resolve | no | vyvid | |
| CAP-3 | **Load the configuration of scopes, domains and projects and refuse it whole, every problem listed, when a reference names nothing or the domains form a cycle.** | a configuration edited by hand | `vyd config` | published | development | | | python | | | src/vyvid/config.py::load | no | vyvid | |
