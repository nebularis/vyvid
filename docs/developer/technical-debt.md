<!-- SPDX-License-Identifier: MIT -->

# Technical debt register

**Unit type:** Register

A defect or shortfall in something that exists, with no planned home. A design decision not yet made goes in the pending design decisions register, and outstanding work goes in its unit's plan. 

| # | Debt | Spotted | Cost while it stays | Likely home | Bears on |
|---|---|---|---|---|---|
| TD-1 | **A term's module is the folder of the document that declares it, such as ontology/persistence/spec, where LATTICE names the module, persistence.** The OWL extractor knows no project's layout of modules, so it takes the folder. | 2026-11-03, comparing `vyd find --kind term` with LATTICE's | a term's row says where its document sits rather than which module owns it | an `owl-terms` setting naming the folder whose subfolders are modules, and the segments, such as `applied`, that nest one level deeper | CAP-1 |
| TD-2 | **This repository cites LATTICE's identifiers, the wrong direction for a citation.** 18 rows of the standards register and 3 of the principles register name their origin as `lattice:` in `Derived from`, and the agent coordination, work-tracking and framework sketches and the developer README cite `lattice:` entries, so their meaning depends on LATTICE keeping those identifiers stable. | 2026-11-04, reviewing which way citations may point | a reader needs LATTICE's register to follow a citation, and a renumbering there breaks it silently | VYD-2b, when LATTICE runs on `vyvid`: replace each with one line saying where the content came from | PRI-4, VYD-2b |
| TD-3 | **The `regex` package and its time limit are proven on macOS only.** A family pattern's time limit is what keeps a hostile pattern from hanging a build, and neither its wheel nor its limit has been run on Windows. | 2026-11-04, choosing how to keep regular expressions in a manifest | a Windows user may have no wheel to install, or a limit that does not fire | VYD-14 | VYD-6b, VYD-14 |
| TD-4 | **A worktree reads its main checkout's files.** A folder bound by its remote takes the project's configured `code` folder as its root, and one store holds one copy of a scope, so an agent in a LATTICE worktree on a branch is answered from the main checkout's files, and its own registers go unread. | 2026-11-04, asking how an extractor runs in a worktree | an agent on a branch gets the wrong answers without being told | a slice before VYD-2b, as LATTICE works in several worktrees at once | VYD-2b |
