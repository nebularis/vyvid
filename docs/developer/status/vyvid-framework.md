<!-- SPDX-License-Identifier: MIT -->

# Status: vyvid-framework

**Status:** building 2026-11-03
**Plan:** [vyvid-framework](../plans/vyvid-framework.md)
**Sketch:** [vyvid-framework](../sketches/vyvid-framework.md)

## Board

| Slice | Deliverable | State | Blocked on |
|---|---|---|---|
| VYD-0 | the temporal reasoning spike | planned | |
| VYD-0b | symbol indexing research | planned | |
| VYD-1 | configuration, binding and `vyd context` | built 2026-11-03, building 2026-11-03 | |
| VYD-2 | the index core extracted from LATTICE | building 2026-11-03 | |
| VYD-3 | domains, their graph and register types | planned | VYD-0b, VYD-2 |
| VYD-4 | managed assets and git policy | planned | VYD-1 |
| VYD-5 | the store across scopes | planned | VYD-0, VYD-3 |
| VYD-6 | recipes and contracts | planned | VYD-5 |
| VYD-7 | the triple-store domain | planned | VYD-5 |
| VYD-8 | the Tools and Haskell domains | planned | VYD-3, VYD-5 |
| VYD-9 | a project with private docs | planned | VYD-6 |
| VYD-10 | an overlay as a domain | planned | VYD-6 |
| VYD-11 | vyvid's own contract | planned | VYD-6 |

## History

- 2026-11-03. The sketch and the plan moved here from LATTICE's working notes, where they were drafted. Questions VYD-Q1 to VYD-Q9, VYD-Q11 and VYD-Q12 answered by the maintainer. VYD-Q10 open.
- 2026-11-03. VYD-Q1 revised: identifiers are unique within their scope, families are configured per scope, and `scope:LOCAL` is canonical across scopes, so this repository's registers use plain families under the scope `vyvid`. VYD-Q13 answered: content moving out of LATTICE moves under the MIT licence.
- 2026-11-03. VYD-Q10 answered provisionally: the spike runs outside any repository, to be revisited when VYD-0 starts.
- 2026-11-03. VYD-1 built: the `vyvid` package, installable with `uv tool install` and run as `vyd`, the configuration of scopes, domains, projects and identifier families with its checks, binding by folder and by remote, `vyd context`, `vyd resolve` and `vyd config`, 21 tests, and `examples/config.toml`. CAP-1 to CAP-3 recorded, unratified.
- 2026-11-03. VYD-2 begun, in steps. The first: `vyvid.anchors`, copied from LATTICE unchanged, and `vyvid.embed`, which takes each node's text from its caller rather than from LATTICE's graph, reads its model, revision, file digests, query prefix and thresholds from the configuration's `[embedding]`, and caches the model per model and revision in the platform's cache folder. On LATTICE's model its vectors equal LATTICE's exactly. Next: the facet register reader, register types declared rather than built in, the extractors, and `find`.
- 2026-11-03. VYD-2's second step: `vyvid.facets` reads any number of facet registers, merged in scope order with any schemes a register declares, a later register extending an earlier one's schemes and refused for a slug defined twice or a broader value defined nowhere. LATTICE's facet values ship in the package as the general scope's default, relicensed MIT, and in LATTICE's namespace give exactly the Turtle LATTICE generates. A scope's facet registers are configured, a domain's `facets.md` by default. Next: register types declared rather than built in.
- 2026-11-03. VYD-2's third step: register types are declarations, not code. The packaged `register-types.toml` holds LATTICE's columns, value sets and types, relicensed MIT, a scope's configuration adds its own files merged in scope order, and a family names the type of the register that defines it. `vyvid.registers` reads a register by them. Read through `vyvid`, LATTICE's 767 register rows match LATTICE's own index in identifier, class, claim and status, and its problems match LATTICE's build notes, less LATTICE's check that an owner names a catalogue unit, which is LATTICE's own. The reader found CAP-1's claim over the limit, now shortened. Next: the extractors and the store.
- 2026-11-03. Sketched [agent coordination](../sketches/agent-coordination.md): claims taken atomically in a coordination store outside every repository, with leases, an event log and identifier allocation, beside the branch marks. Questions VYD-Q14 to VYD-Q19 open.
