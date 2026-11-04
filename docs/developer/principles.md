<!-- SPDX-License-Identifier: MIT -->

# Principle register

**Unit type:** Register

Durable design commitments of Вивід, each pointing at the decision behind it. The rows of scope general came from LATTICE's registers, which their Derived from column names, relicensed MIT.

| ID | Name | Claim | Problem shape | Decided by | Evidenced by | Audience | Phase | Activity | Quality | Technology | Pointer | Ratified | Scope | Does not cover | Distinguished from | Narrowed by | Derived from |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| PRI-1 | Write plainly, once | **Write concisely, say a thing once and point other mentions at it, and show structure with metadata a tool reads.** | writing documents, comments and messages that stay correct as the repository changes |  |  | internal | development | documentation | readability, consistency |  | docs/developer/README.md#writing | yes | general |  |  |  | lattice:PRI-68 |
| PRI-2 | User-facing documents cite only published decisions (P7-6) | **Cite only accepted decisions from user-facing text, and a working document only in a decision's closing Provenance section.** | what a user-facing document may cite |  |  | published | authoring, runtime | documentation, licensing-and-ip | consistency |  | docs/developer/README.md#what-is-published | yes | general |  |  |  | lattice:PRI-20 |
| PRI-3 | Report only what ran | **Report a check as passed only when it ran and passed, and say what was not run.** | reporting the result of a change to the maintainer |  |  | internal | development | testing | auditability |  | docs/developer/contract.md#reporting | yes | general |  |  |  | lattice:PRI-69 |
| PRI-4 | Citations point from a project to a domain | **A project may cite a domain's published entries and maintains its own link to them. A domain never cites a project, since it cannot depend on a project keeping its identifiers stable.** | knowledge in a domain that means nothing without the project it came from | | | published | authoring | | | | docs/developer/sketches/vyvid-framework.md#6-moving-a-register-or-a-domain | yes | general | | | | |
