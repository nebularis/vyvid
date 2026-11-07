<!-- SPDX-License-Identifier: MIT -->

# Pending design decisions

**Unit type:** Register

A decision that matters and cannot be made yet, because the evidence is missing, a dependency is undecided or no unit owns it. A question a unit already owns stays in its sketch or plan.

| # | Decision | Raised | Cost of deferring | Options known | Waits for | Bears on |
|---|---|---|---|---|---|---|
| PDD-1 | **Whether a file `vyd` writes owner-only on POSIX is restricted on Windows too.** The configuration, the trust record and a cloud script are written with mode 0o600 and their folders 0o700, which Windows ignores, so there they keep the access the folder gives, usually the user's own profile alone. | 2026-11-07, running the suite on Windows | a file in a folder others may read is readable by them on Windows | leave it to the folder's access list, set an access list with `icacls`, or call the Windows security API through `ctypes` | a Windows user whose profile others may read | WT-3 |
