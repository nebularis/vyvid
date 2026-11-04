<!-- SPDX-License-Identifier: MIT -->

# Security findings

**Unit type:** Register

What we have found that could harm a person using Вивід, how we know, and what closes it. `SECURITY.md` tells users the threat surface, and this register holds the findings behind it. A row is promoted to a security domain once one exists.

**Evidence** says how far a finding was proven: tested on a hostile domain, read from the code, or designed but not yet built. A row is open until its `Fixed in` cell is filled.

| ID | Finding | Severity | Surface | Evidence | Remediation | Fixed in |
|---|---|---|---|---|---|---|
| SEC-1 | **A manifest's `rules` may name any file, whose text is copied word for word into a generated skill.** | high | manifest, install | tested 2026-11-04, a fake secret outside the domain reached `SKILL.md` | every path a manifest names stays inside the domain's folder | 2026-11-04 |
| SEC-2 | **A manifest's family may be defined by a file outside the domain, whose rows are indexed and shown to an agent.** | high | manifest, index | tested 2026-11-04, `find` printed a row from outside the domain | as SEC-1 | 2026-11-04 |
| SEC-3 | **A symlink in a domain may lead a read outside its folder.** | medium | clone, index | not proven, one test was inconclusive and `read_text` follows links | refuse a link that leaves the folder | 2026-11-04 |
| SEC-4 | **A manifest sets its own git policy, so a domain's author may choose to be pulled at every start and pushed automatically.** | high | manifest, update | tested 2026-11-04, `pull=on-start` and `push=auto` were accepted | only the user's configuration sets `git` and `remote` | 2026-11-04 |
| SEC-5 | **A manifest's family pattern can hang a build by catastrophic backtracking.** | medium | manifest, index | tested 2026-11-04 on Python's `re`, `(C+)+$` ran past 4 seconds, and a manifest's pattern reaches `re.compile` unchecked | the `regex` package with a time limit, which disables the family and reports it | 2026-11-04 |
| SEC-6 | **A domain named `domain-review` could overwrite a core skill of that name.** | high | install | read from the code | a domain's skill and a core skill have separate prefixes | 2026-11-04 |
| SEC-7 | **A later push to a domain reaches agents with no review, since a pull changes the rules and skills they read.** | high | update | read from the code | hold changes to rules and skills of a domain the user did not write until the diff has been seen | |
| SEC-8 | **`vyd install` turns a domain's rules into agent instructions with no review.** | high | install | read from the code | install rules and skills only from domains the user's configuration marks as trusted | |
| SEC-9 | **A finding's text reaches an agent like any other text, so it can carry instructions.** | medium | results | read from the code, and no control removes this wholly | label results as data from a named domain, and flag invisible Unicode and HTML comments | |
| SEC-10 | **A client approves `vyd recipe run` and never sees the glue command inside it.** | medium | glue | read from the code | `--dry-run` shows each command, and a form that stops at glue so the agent runs it through its own shell is a later choice | |
| SEC-11 | **Glue inherits the whole environment, including tokens and the SSH agent socket, with which it can act as the user.** | high | glue, credentials | read from the code, `subprocess.run` is given no `env` | a minimal environment, with variables passed only when a step names them | |
| SEC-12 | **Glue, an extractor and an installed package run with the user's full privileges, and can read `~/.ssh`, `~/.aws` and any other file.** | high | code, credentials | inherent, no cross-platform sandbox exists to apply | state it to users, and run what is not trusted in a container | |
| SEC-13 | **A folder-local configuration would let a cloned repository declare glue that runs when a recipe does.** | high | glue, configuration | designed, not built | an explicit trust step per folder, re-asked when the configuration changes | |
| SEC-14 | **`VYVID_CONFIG` redirects the whole configuration, so whatever sets the environment chooses what glue exists.** | medium | configuration | read from the code, and not tested with a project's environment file | apply the trust step to any configuration outside the user's own folder | |
| SEC-15 | **Glue's output and error text go to the agent, and so to the model's provider and the transcript.** | medium | glue, credentials | read from the code | cap the error text, and redact what looks like a credential | |
| SEC-16 | **`vyd kb record` under an automatic push can publish a secret, since nothing scans what it stages.** | high | update, credentials | read from the code | refuse to stage what looks like a credential | |
| SEC-17 | **A remote URL holding a token is stored in the configuration and printed by `vyd kb`.** | low | configuration, credentials | read from the code | refuse a remote URL that holds a credential | |
| SEC-18 | **The index and the question logs are plain files under the user's default permissions, and a question may hold something sensitive.** | low | store, credentials | read from the code | owner-only permissions, and a setting that turns the logs off | |
| SEC-19 | **An extractor's package would be installed with no pinned hash.** | high | code | designed, not built | a pinned hash, explicit consent, and no install on a pull | |
