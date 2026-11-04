<!-- SPDX-License-Identifier: MIT -->

# Security

Вивід puts text from other people's repositories in front of an AI agent that can run commands on your machine. Read this before adding a domain you did not write. Using Вивід does not make that safe, and this page says where the risk stays.

Вивід is young, and the one control marked planned below is not built yet. Until it is, read a domain before you give it trust, and install nothing on its say.

## Trust

Three levels of trust are set on a domain's entry in your own configuration, and a domain's manifest that sets `trust` or `commit` is refused.

- `own`: you wrote it. Its rules, skills and recipes reach agents.
- `reviewed`, with `commit = "<hash>"`, at least 7 hexadecimal characters: you read it at that commit. It counts as your own only while its HEAD is that commit, and gives knowledge alone once HEAD moves.
- `knowledge`: its entries are searchable and nothing else. `vyd install` writes no skill for it and removes a generated one, `vyd context` lists its rules, skills and recipe descriptions as withheld, and every entry of it that `find`, `read`, `node` or a recipe's briefing returns is labelled as data, with its text between begin and end lines.

A domain with a `remote` is `knowledge` unless you say otherwise, and one with none is `own`.

Two commands grant trust and are for a person. `vyd kb accept <domain>` fast-forwards a domain whose pull was held, after it lists the changed files and you type the domain's name. `vyd trust [path]` records the hash of a configuration, after it lists every glue command and command extractor in it and you type `yes`. Each refuses unless standard input is a terminal. That check is a speed bump and not a proof, since an agent given a pseudo-terminal could pass it. An agent that can run commands as you can also edit your configuration, so keep your client's permission settings strict. Accepting an update changes neither `trust` nor `commit`.

## What can reach your machine

| Surface | What can go wrong | What limits it | What stays with you |
|---|---|---|---|
| **A domain's text** | A skill, rule or finding tells an agent to run a command or change its task. No code is needed, since an agent acts on what it reads | A domain's results are labelled as data unless it is `own` or `reviewed` at its commit, and only those install rules and skills. A label also names invisible characters and HTML comments in the text | Text can still persuade an agent. Your client's permission settings are the last line of defence, and they are outside Вивід |
| **A domain's updates** | A domain you reviewed changes later, or its author's account is compromised | A pull of a domain that is not your own fetches first, and merges nothing if the manifest, a file the domain names as rules, skills, register types, facets or vocabulary, or a `SKILL.md` changed. It names the files and the `git diff` to read, and a person runs `vyd kb accept` | Reviewing a diff helps only if someone reads it |
| **A domain's manifest** | It names files outside its folder, sets its own update policy, or declares a pattern that hangs a build | Every path stays inside the folder, even through a link. Only your configuration sets `git`, `remote`, `trust` and `commit`. A refused manifest sets aside only its domain and the domains that descend from it, and `vyd config` lists them and exits non-zero. A pattern runs under a time limit, and one that runs out of time disables its family for that run and is reported | A link inside a domain that leaves its folder is never read, and `vyd domain audit` lists it |
| **Glue** | A step in a project's recipe runs a command, which your client approves only as `vyd recipe run` | Domains cannot declare glue. Glue runs with a minimal environment. `vyd recipe run --dry-run` prints each step and each glue command without running any. With `glue = "stop"` in `[framework]`, or `--stop-at-glue`, Вивід runs no glue itself and prints each command for your client to run and approve | Set `glue = "stop"` to see each command. Otherwise avoid allowing `vyd recipe run` without a prompt |
| **Extractors and packages** | Code you install runs with your full privileges, and so does a command a project's extractor names | Вивід installs nothing today. A command extractor runs only if a project's entry in your own configuration declares it, never a domain's manifest or entry, and it gets a minimal environment and the checkout as its working folder. It can write only to the project's own graphs. Planned: consent and a pinned hash for each package, and no install on a pull | A separate process is not a sandbox, and a command can still read your files. Run what you do not trust in a container |
| **A cloned project** | Its configuration declares glue that runs when a recipe does | A configuration at any path but your own, such as one named by `VYVID_CONFIG`, is trusted only by the hash of its bytes, which `vyd trust` records. Until then it runs no glue and no command extractor, a recipe that stops at glue still stops, and a changed file is untrusted again | A person must run `vyd trust`, and it is only as careful as the terminal check above |

## Credentials

Anything Вивід runs on your behalf can reach what you can reach.

- **The environment.** Tokens in environment variables and your SSH agent are the easiest to reach, since a command can use them to act as you. Glue is given only a short list of variables by exact name, such as `PATH` and `HOME`, and any its step names in `env`. Tokens, `SSH_AUTH_SOCK` and `VIRTUAL_ENV` are not passed unless a step names them. A command you run yourself when a recipe stops at glue has your whole environment.
- **Your files.** `~/.ssh`, cloud credentials and browser profiles cannot be protected without a sandbox, and Вивід has none that works on every platform.
- **What is printed.** A command's output goes to the agent, and so to your model provider and your transcript. Text that matches a known credential format, such as a GitHub, GitLab, AWS, Slack or Anthropic token, a private key block or a bearer token, is replaced with `[redacted]` in the output of glue and of a command extractor, and in their error text.
- **What is committed.** A domain under an automatic push publishes what is staged, so keep automatic push to domains you own. `vyd kb record` scans each file it is about to stage for the same formats, and when it finds one it stages nothing in that domain and says which file, which line and which rule, never the text. It has no option to skip the scan, since an agent chooses its options. A false positive is yours to stage with git. Where `gitleaks` is installed it is run over each file as well, and when it cannot run you are told and the built-in scan goes on alone.
- **What your configuration holds.** A remote URL with a password, with a user part on http or https, or with a query or fragment is refused, and the message names the host and not the URL. A setting named `credential`, `credentials`, `token`, `password`, `secret` or `api_key`, or ending `_token`, `_password`, `_secret` or `_key`, must start with `env:` or `keychain:`.
- **What is kept on disk.** The index folder is readable by you alone. So are the logs of questions, and `logs = false` in `[framework]` stops them being written.

Scanning catches an accident. It looks for known formats and for nothing else, so it does not catch a secret in an unknown format, and it cannot stop someone who encodes a secret to get past it.

Keep a credential out of your configuration by naming an environment variable or a keychain entry, and never write one into a domain.

## Reviewing a domain

`vyd domain audit <folder>` reads a folder and runs nothing from it. It lists links and where they point, files that are not text, executable files, paths leaving the folder, `git` or `remote` in the manifest, patterns that time out, invisible characters, HTML comments, long encoded blobs, URLs and lines shaped like commands. It states facts and decides nothing.

`vyd install` writes the core skill `vyvid-core-domain-review`, which has an agent review a quarantined clone with read and search tools only, where the client can restrict tools, and record its findings against the commit it read. Where a client cannot restrict tools, the skill is a request and not a limit. It is a safety net. The agent reading hostile text is also the target of that text, so a clean review is advice and grants no trust.

## Reporting a vulnerability

Please use GitHub's private vulnerability reporting on this repository rather than opening a public issue.
