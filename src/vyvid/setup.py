# SPDX-License-Identifier: MIT
"""``vyd setup``: a first local configuration that a person can follow.

A contributor who has installed ``vyd`` has no configuration, and the first thing a project asks for is its domains, which
live under a knowledge base that no command used to set. This sets ``[framework] kb`` where it is not set, adds each published
domain the folder's project names and the configuration lacks, clones them, and says what is left for a person: trusting the
project's ``vyvid.toml``, which asks a question and so is run directly, and reviewing a domain to give its skills to an agent.
A domain is added with trust ``knowledge``, which gives an index and a board and no skills.
"""

from __future__ import annotations

import contextlib
import io
import sys
from pathlib import Path
from typing import Callable

import platformdirs

from . import configure, kb
from .config import ConfigError, load, read_project_file
from .resolve import bind_in, project_file

PUBLISHED = ("lifecycle", "tools", "python", "haskell", "triple-stores", "rdf-modelling")
REMOTE = "https://github.com/nebularis/vyvid-{name}.git"


def default_kb() -> Path:
    return platformdirs.user_data_path("vyvid") / "kb"


def quietly(call, *args) -> int:
    """A configuration edit with its diff held back, shown only if it failed, since setup says its own line for each."""
    held = io.StringIO()
    with contextlib.redirect_stdout(held):
        code = call(*args)
    if code != 0:
        print(held.getvalue(), end="")
    return code


def named_domains(config, folder: Path) -> tuple[list[str], str | None]:
    """The domains a folder's project names, and the project's name. They come from its ``vyvid.toml`` as written, since a project
    that names a domain nobody has configured is set aside, which is the state this is run to mend. A domain that a delegation or a
    move points at counts too."""
    file = project_file(folder)
    if file is not None:
        table, problems = read_project_file(file)
        if not problems or isinstance(table.get("name"), str):
            named = [d for d in table.get("domains", []) if isinstance(d, str)]
            named += [v for v in (table.get("delegates") or {}).values() if isinstance(v, str)]
            named += [m.get("to") for m in table.get("moves", []) if isinstance(m, dict) and isinstance(m.get("to"), str)]
            return list(dict.fromkeys(named)), str(table.get("name", file.parent.name))
    _, project = bind_in(config, folder)
    if project is None:
        return [], None
    return list(dict.fromkeys([*project.domains, *project.dropped])), project.name


def run(folder: Path, clone: bool, dry_run: bool, person: Callable[[], bool]) -> int:
    try:
        config = load()
    except ConfigError as error:
        print("vyd: the configuration cannot be used, so nothing was set up:", file=sys.stderr)
        for problem in error.problems:
            print(f"  {problem}", file=sys.stderr)
        return 1
    named, label = named_domains(config, folder)
    if label is None:
        print(f"vyd: no project claims {folder}, so there are no domains to set up. Run it in a repository with a vyvid.toml", file=sys.stderr)
        return 1
    missing = [n for n in named if n not in config.domains and n not in config.set_aside]
    published = [n for n in missing if n in PUBLISHED]
    others = [n for n in missing if n not in PUBLISHED]
    needs_kb = config.kb is None and bool(published)
    kb_path = default_kb()
    if not published and not others:
        print(f"nothing to set up: every domain project {label} names is configured")
    if dry_run:
        if needs_kb:
            print(f"would set [framework] kb = {configure.place(str(kb_path))}")
        for name in published:
            print(f"would add the domain {name} from {REMOTE.format(name=name)}, with trust knowledge" + (", and clone it" if clone else ""))
    else:
        if needs_kb:
            if quietly(configure.framework_set, "kb", configure.place(str(kb_path)), False, person) != 0:
                return 1
            print(f"set [framework] kb = {configure.place(str(kb_path))}")
        for name in published:
            if quietly(configure.domain_add, name, None, REMOTE.format(name=name), "knowledge", None, "public", False, False, person) != 0:
                return 1
            print(f"added the domain {name} from {REMOTE.format(name=name)}, with trust knowledge")
    for name in others:
        print(f"{name}: not a published domain, so add it yourself with vyd domain add {name} --path <folder> or --remote <repository>")
    failed = 0
    if published and clone and not dry_run:
        config = load()
        for name in published:
            result = kb.clone(config, config.domains[name])
            print(f"{name}: {result.text}")
            failed |= not result.ok
    elif published and not clone and not dry_run:
        print("the domains' folders are not cloned yet. Clone them with: vyd kb clone")
    print("\nNext, yourself, in a terminal:")
    print("  vyd trust                  asks a question, so run it directly and not through a task runner (or: mise exec -- vyd trust)")
    print("  vyd build                  builds the index")
    print("  vyd context                lists every layer of rules that applies here")
    print("Domains were added with trust knowledge, which gives an index and a board and no skills. To give a domain's skills to your agents, "
          "read it, then run: vyd domain trust <name> reviewed --commit <hash>")
    return 1 if failed else 0
