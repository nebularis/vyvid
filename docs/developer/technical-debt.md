<!-- SPDX-License-Identifier: MIT -->

# Technical debt register

**Unit type:** Register

A defect or shortfall in something that exists, with no planned home. A design decision not yet made goes in the pending design decisions register, and outstanding work goes in its unit's plan. 

| # | Debt | Spotted | Cost while it stays | Likely home | Bears on |
|---|---|---|---|---|---|
| TD-1 | **A term's module is the folder of the document that declares it, such as ontology/persistence/spec, where LATTICE names the module, persistence.** The OWL extractor knows no project's layout of modules, so it takes the folder. | 2026-11-03, comparing `vyd find --kind term` with LATTICE's | a term's row says where its document sits rather than which module owns it | an `owl-terms` setting naming the folder whose subfolders are modules, and the segments, such as `applied`, that nest one level deeper | CAP-1 |
