<!-- SPDX-License-Identifier: MIT -->

# Security

Вивід puts text from other people's repositories in front of an AI agent that can run commands on your machine. Read this before adding a domain you did not write. Using Вивід does not make that safe, and this page says where the risk stays.

Вивід is young, and a control marked planned below is not built yet. Until it is, add only domains you wrote or have read in full.

## What can reach your machine

| Surface | What can go wrong | What limits it | What stays with you |
|---|---|---|---|
| **A domain's text** | A skill, rule or finding tells an agent to run a command or change its task. No code is needed, since an agent acts on what it reads | Planned: a domain's text is labelled as data, and only domains you mark as trusted install rules and skills | Text can still persuade an agent. Your client's permission settings are the last line of defence, and they are outside Вивід |
| **A domain's updates** | A domain you reviewed changes later, or its author's account is compromised | Planned: changes to rules and skills in a domain you did not write wait until you have seen them | Reviewing a diff helps only if someone reads it |
| **A domain's manifest** | It names files outside its folder, sets its own update policy, or declares a pattern that hangs a build | Every path stays inside the folder, even through a link. Only your configuration sets `git` and `remote`. A pattern runs under a time limit, and one that runs out of time disables its family for that run and is reported | A link inside a domain that leaves its folder is never read, and `vyd domain audit` lists it |
| **Glue** | A step in a project's recipe runs a command, which your client approves only as `vyd recipe run` | Domains cannot declare glue. Glue runs with a minimal environment. `vyd recipe run --dry-run` prints each step and each glue command without running any. With `glue = "stop"` in `[framework]`, or `--stop-at-glue`, Вивід runs no glue itself and prints each command for your client to run and approve | Set `glue = "stop"` to see each command. Otherwise avoid allowing `vyd recipe run` without a prompt |
| **Extractors and packages** | Code you install runs with your full privileges | Вивід installs nothing today. Planned: consent and a pinned hash for each package, and no install on a pull | A separate process is not a sandbox. Run what you do not trust in a container |
| **A cloned project** | Its configuration declares glue that runs when a recipe does | A project's configuration lives in your own configuration file today. Planned, before a project can declare its own: a folder must be trusted explicitly before its glue runs, and asked again when its configuration changes | |

## Credentials

Anything Вивід runs on your behalf can reach what you can reach.

- **The environment.** Tokens in environment variables and your SSH agent are the easiest to reach, since a command can use them to act as you. Glue is given only a short list of variables by exact name, such as `PATH` and `HOME`, and any its step names in `env`. Tokens, `SSH_AUTH_SOCK` and `VIRTUAL_ENV` are not passed unless a step names them. A command you run yourself when a recipe stops at glue has your whole environment.
- **Your files.** `~/.ssh`, cloud credentials and browser profiles cannot be protected without a sandbox, and Вивід has none that works on every platform.
- **What is printed.** A command's output goes to the agent, and so to your model provider and your transcript.
- **What is committed.** A domain under an automatic push publishes what is staged, so keep automatic push to domains you own.

Keep a credential out of your configuration by naming an environment variable or a keychain entry, and never write one into a domain.

## Reviewing a domain

`vyd domain audit <folder>` reads a folder and runs nothing from it. It lists links and where they point, files that are not text, executable files, paths leaving the folder, `git` or `remote` in the manifest, patterns that time out, invisible characters, HTML comments, long encoded blobs, URLs and lines shaped like commands. It states facts and decides nothing.

`vyd install` writes the core skill `vyvid-core-domain-review`, which has an agent review a quarantined clone with read and search tools only, where the client can restrict tools, and record its findings against the commit it read. Where a client cannot restrict tools, the skill is a request and not a limit. It is a safety net. The agent reading hostile text is also the target of that text, so a clean review is advice and grants no trust.

## Reporting a vulnerability

Please use GitHub's private vulnerability reporting on this repository rather than opening a public issue.
