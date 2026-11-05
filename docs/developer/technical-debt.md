<!-- SPDX-License-Identifier: MIT -->

# Technical debt register

**Unit type:** Register

A defect or shortfall in something that exists, with no planned home. A design decision not yet made goes in the pending design decisions register, and outstanding work goes in its unit's plan. 

| # | Debt | Spotted | Cost while it stays | Likely home | Bears on |
|---|---|---|---|---|---|
| TD-2 | **This repository cites LATTICE's identifiers, the wrong direction for a citation.** 18 rows of the standards register and 3 of the principles register name their origin as `lattice:` in `Derived from`, and the agent coordination, work-tracking and framework sketches and the developer README cite `lattice:` entries, so their meaning depends on LATTICE keeping those identifiers stable. | 2026-11-04, reviewing which way citations may point | a reader needs LATTICE's register to follow a citation, and a renumbering there breaks it silently | VYD-2b, when LATTICE runs on `vyvid`: replace each with one line saying where the content came from | PRI-4, VYD-2b |
| TD-3 | **The `regex` package and its time limit are proven on macOS only.** A family pattern's time limit is what keeps a hostile pattern from hanging a build, and neither its wheel nor its limit has been run on Windows. | 2026-11-04, choosing how to keep regular expressions in a manifest | a Windows user may have no wheel to install, or a limit that does not fire | VYD-14 | VYD-6b, VYD-14 |
