<!-- SPDX-License-Identifier: MIT -->

# Plan: architectural quanta as a built-in extractor

**Status:** built 2026-11-08, at the maintainer's request.
**Prefix:** QU

## Scope

An architectural quantum is the smallest set that must change and be released together because of its coupling. One project derives its quanta with a command extractor of its own, which a project that reads it cannot run (a read never runs a command). A project that depends on another needs to know the other's quanta, since its own change is bounded by them. So the derivation becomes a built-in kind, `quanta`, which a read runs because it is Вивід's own code.

The kind takes its modules as data, so it needs no catalogue:

```toml
[[project.extractors]]
kind = "quanta"
paths = ["code:ontology/**/*.ttl", "code:deployment/**/docker-compose.yml"]

[[project.extractors.modules]]
name = "foundation"
path = "ontology/foundation"
kind = "substrate"
release = true
```

A module of the core kind (default `substrate`) forms one quantum with every module the core imports, and any other module is its own. Compose files give the software view: a shared store or a synchronous call binds components, and a broker does not. PyYAML joins the dependencies for the compose files.

## Slices

| Slice | Content | Depends on | Estimate |
|---|---|---|---|
| QU-1 | the kind: the derivation, the modules as settings, the imports read from the ontology documents, the compose files, and the entries as the project's own extractor wrote them, tests first | | 90k |
| QU-2 | a project that reads another gets its quanta, the guide, the register row and the release | QU-1 | 40k |

## Validation

`mise run check`. The tests build projects and a read in a temporary folder.
