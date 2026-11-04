<!-- SPDX-License-Identifier: MIT -->

# Backlog

**Unit type:** Register

An idea we want and have not planned. It moves into a plan when a unit takes it on.

| ID | Idea | Raised | Why we want it | What exists | Status | Waits for | Bears on |
|---|---|---|---|---|---|---|---|
| BL-1 | **An optional `vyvid_interface` package for a project's own environment, giving a command extractor a scratch store, the contract's files written, and a `Context` without `Config` or `Scope`.** | 2026-11-04 | A command extractor in Python would otherwise repeat the request parsing, the quad and result writing and the scratch store, and today's `Context` hands an extractor the whole configuration | CAP-13 defines the contract, and a command extractor writes the two files itself | Open | | CAP-13 |
