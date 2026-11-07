<!-- SPDX-License-Identifier: MIT -->

# Technical debt register

**Unit type:** Register

A defect or shortfall in something that exists, with no planned home. A design decision not yet made goes in the pending design decisions register, and outstanding work goes in its unit's plan. 

| # | Debt | Spotted | Cost while it stays | Likely home | Bears on |
|---|---|---|---|---|---|
| TD-4 | **`vyd work check --staged` takes the record names from the index but reads their text from the working tree.** A bad record that is staged and then fixed only in the working tree passes the check. | 2026-11-05, testing the check under a real hook | a commit can carry a board the check never read | read the staged text with `git show :<path>` | CAP-26 |
| TD-5 | **A question recorded under an `Answered <date>:` heading stays Open in the index, because the index marks a question answered only when its own text says so.** Several questions in `docs/developer/sketches/work-tracking-domains.md` read as Open though answered. | 2026-11-05, answering VYD-Q35 to VYD-Q41 | a person or an agent asking `find --kind question` is told answered decisions are open, and may reopen them | the question extractor, which could read an `Answered <date>:` line above a list as answering the bullets under it, or those sketches' bullets gain the word | CAP-26 |
