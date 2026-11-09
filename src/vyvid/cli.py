# SPDX-License-Identifier: MIT
"""``vyd``, the command line.

``vyd context [folder] [--json] [--no-pull]``
    the contract that applies in a folder: each layer's rules and skills, general first and the
    project last, which an agent reads before its first task. It first pulls the managed domains of
    the folder's stack that are due, and prints a line for each pull that failed
``vyd resolve <identifier> [--in folder]``
    the canonical ``scope:LOCAL`` an identifier names, written in that folder's project
``vyd config [folder]``
    where the configuration is read from, whether it is sound and trusted, the domains set aside, and the
    folder's own vyvid.toml
``vyd trust [path]``
    trust a configuration outside your own folder, or a repository's vyvid.toml (run in the repository, or
    given its folder or the file), by its hash, so glue and command extractors in it run. It asks a person
    at a terminal to confirm
``vyd build [folder] [--all] [--no-embed]``
    build the knowledge index for the folder's project stack, or for every scope, and print what it
    found and every problem. A project that declares symbols has them parsed too, into a store of their own
``vyd handoff <name> [--module M] [--unit U] [--in folder]``
    the exact commands for the compiler index the folder's project registers, which are printed and never run
``vyd find <words> [--kind symbol] | read <id> | node <id> | reaches <id> | exists <text> | sparql <query>``
    ask the index of the folder's stack a question, rebuilding it first when a file it reads changed
``vyd misses | gap <text> | close <id>``
    the questions the index answered weakly, the gaps found by reading, and closing them
``vyd check citations [--staged] [--message file] [paths ...] [--in folder]``
    refuse the lines a public project adds, staged, in the paths or in a commit message or pull request text,
    that cite an entry of a private scope or of the project's private documents
``vyd docs record <path> ... -m <message> [--in folder]``
    stage paths in the project's private documents folder, then commit and push them by its ``git.docs`` policy
``vyd board [folder] [--all] [--fetch] [--measure] [--commits] [--here] [--state word]``
    where every record and slice of the folder's project is, across every local and remote branch, from the slice boards of its
    status records, where the project declares ``work`` settings. ``--here`` reads the slices of its families of type slice in the one
    checkout, as a project without those settings always is
``vyd work build | roadmap | check | parse | rename | normalise | adopt`` and ``vyd here``
    the generated regions of the project's index and roadmap (the roadmap from the branches a remote knows, never a local-only one), the check a hook runs, a record's board as read, the moves of older
    boards and identifiers onto the board's shape, and who else is working in this checkout
``vyd check identifiers [--json] [--all] [folder]``
    fail on an identifier the folder's tracked Markdown mentions and nothing defines, or that a family defines twice
``vyd move check [--ref <git ref>] [--json] [folder]``
    compare, by identifier, what the folder's project moved to a domain as it stood at the move's commit
    with the source file at the ref, the working tree by default. Exits 1 when something differs, 2 when a
    rev or the file cannot be read
``vyd recipe list [--in folder]`` and ``vyd recipe run <name> "<question>" [--in folder] [--all] [--json] [--stop-at-glue]``
    the named chains of queries the folder's stack declares, and one run as a briefing within its budget.
    A run that stops at a glue step exits 3, and ``vyd recipe run --resume <state> --glue-output <file>`` goes on
``vyd store prune [--dry-run]``
    remove the index stores of linked checkouts that no longer exist
``vyd domain new <name> [--registers <type>] [--path <folder>]``
    write a domain folder and print the lines to add to your configuration, which it leaves alone
``vyd domain add <name> --path <folder> | --remote <url> [--trust own|reviewed|knowledge]``, ``vyd domain remove <name>`` and ``vyd domain trust <name> own|reviewed|knowledge [--commit <hash>]``
    add a domain to your configuration, take it out, or change its trust, keeping your comments. Setting trust own or reviewed, or a new reviewed commit, needs a person at a terminal
``vyd project add <name> | set <name> <key> <value> | remove <name> | scan <name> [--apply]`` and ``vyd family add | remove``
    declare a project, change one of its keys, register the families its documents hold, in your configuration or with --file in the
    repository's vyvid.toml. Each takes --dry-run, which prints the change and writes nothing
``vyd domain audit <folder> [--json]`` and ``vyd domain review-path <domain> <commit>``
    the facts about a folder someone else wrote, read and never run, and where its review is recorded
``vyd install --client claude-code [--target folder] [--dry-run]``
    write the client's user-level rule file and one skill per configured domain

``vyd cloud script --output <file> [--domain name[=~/path]] [--grant remote] [--run path] [--dry-run]``
    write the setup script for a cloud environment: the private domains named are embedded, the public ones cloned. The script holds private text and is never printed

``vyd kb status | clone [domain ...] | pull [domain ...] [--due] | record <path> ... -m <message> | accept <domain>``
    the domains under the knowledge base, each a git clone of its remote, kept by its git policy. A pull of
    a domain that is not your own holds changes to its manifest, rules or skills until a person accepts them

Each question takes ``--in <folder>``, the folder whose stack it is asked in, the current one by default,
and ``--scope a,b`` to add scopes to that stack or ``--scope only:a,b`` to read those alone.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import replace
from pathlib import Path

from . import __version__, ask, audit, board, catalogue, citations, cloud, configure, guard, setup as first_setup, handoff, identifiers, install, kb, moves, newdomain, reads, recipes, skills, streams
from . import config as configuration
from .config import ConfigError, command_line, config_path, extractor_runs, load, timeouts
from .facets import RegisterError
from .registers import DeclarationError
from .resolve import Unresolved, bind_in, file_scope, layers, project_file, resolve
from .work import command as work_command


cf_trusts = configuration.TRUSTS
cf_visibilities = configuration.VISIBILITIES


def _writes(parser, hidden_file: bool = False) -> None:
    """The options every command that changes a configuration takes."""
    parser.add_argument("--file", action="store_true", help=argparse.SUPPRESS if hidden_file else "change the repository's vyvid.toml, not your configuration")
    parser.add_argument("--dry-run", action="store_true", help="print the change and write nothing")


QUESTIONS = ("find", "read", "node", "reaches", "exists", "sparql", "misses", "gap", "close")


def _person() -> bool:
    """Whether a person is at a terminal. A speed bump for an agent, and no proof, since one can be given a pseudo-terminal.
    On Windows the null device answers ``isatty()`` too, so there the console itself is asked."""
    try:
        if sys.stdin is None or not sys.stdin.isatty():
            return False
    except ValueError:  # closed
        return False
    return os.name != "nt" or _windows_console(sys.stdin.fileno())


def _windows_console(fd: int) -> bool:
    """Whether ``fd`` is a Windows console, which answers GetConsoleMode where a file or the null device does not."""
    import ctypes
    import msvcrt

    try:
        handle = msvcrt.get_osfhandle(fd)
    except OSError:
        return False
    return bool(ctypes.windll.kernel32.GetConsoleMode(handle, ctypes.byref(ctypes.c_uint32())))


def _set_aside(config) -> None:
    """Say on standard error which domains were set aside, since a command's standard output may be parsed."""
    for name, why in config.set_aside.items():
        print(f"vyd: domain {name} is set aside and read by nothing", file=sys.stderr)
        for problem in why:
            print(f"  {problem}", file=sys.stderr)
    for file, why in config.files_aside.items():
        print(f"vyd: the project declared in {file} is set aside, so the folder gets the general scope", file=sys.stderr)
        for problem in why:
            print(f"  {problem}", file=sys.stderr)


def _dropped(project) -> None:
    """Say which domains a repository's vyvid.toml names that this user has not configured. It is a note, since a clone's reader will not have them."""
    for name in project.dropped if project else []:
        print(f"NOTE: domain {name} is named by {project.file.name} and is not configured here, so it is left out of the stack for this run", file=sys.stderr)
    for name in project.unread if project else []:
        print(f"NOTE: reads {name}, which is not configured here, so it is left out of the stack for this run", file=sys.stderr)


def _layer(config, scope) -> dict:
    out = {"scope": scope.name, "kind": scope.kind, "visibility": scope.visibility}
    withheld = not scope.trusted
    for key in ("rules", "skills"):
        out[key] = [] if withheld else [{"path": str(p), "exists": p.exists()} for p in getattr(scope, key)]
    out["recipes"] = [{"name": r.name, "description": None if withheld else r.description} for r in scope.recipes]
    if withheld:
        why = (f"a read of commit {scope.read_commit[:12]} that no person has reviewed" if scope.read_of else "a vyvid.toml nobody has trusted" if scope.kind == "project" else scope.trust if scope.trust != "reviewed"
               else f"reviewed at {scope.commit}, which HEAD has moved past")
        out["withheld"] = {"trust": why, "rules": [str(p) for p in scope.rules], "skills": [str(p) for p in scope.skills], "recipes": [r.name for r in scope.recipes]}
    if scope.kind == "domain":
        out["brings"] = [e["kind"] for e in scope.extractors]
    if scope.read_of:
        out["read"] = {"by": scope.read_of, "commit": scope.read_commit, "standing": scope.standing}
    if scope.kind == "project":
        out["file"] = str(scope.file) if scope.file else None
        out["runs"] = [{"kind": r.kind, "domain": r.domain, "settings": {k: [str(p) for p in v] if k == "paths" else v for k, v in r.settings.items()},
                        "sources": r.sources} for r in extractor_runs(config, scope)]
        out["code"] = str(scope.code)
        out["docs"] = str(scope.docs)
        out["reads"] = [{"name": r.name, "commit": r.commit, "standing": r.standing(scope), "skills": list(r.skills), "recipes": list(r.recipes)}
                        for r in scope.reads.values()]
        out["specialises"] = {d: {"path": str(p), "exists": p.exists()} for d, p in scope.specialises.items()}
        out["symbols"] = [{"language": x.language, "paths": [str(p) for p in x.paths]} for x in scope.symbols]
        out["code_index"] = [{"kind": handoff.clean(i.kind), "database": str(i.database), "exists": i.database.is_file(), "sources": str(i.sources) if i.sources else None,
                              "built_by": None if withheld else (handoff.clean(i.built_by) or None), "known": i.kind in handoff.KNOWN} for i in scope.code_index]
    return out


def _guard_hooks(config, arguments) -> int:
    """Set up the guard's git hooks where a guard is configured, unless told not to."""
    if arguments.no_git_hooks or not config.guard.on:
        return 0
    return guard.install_hooks(arguments.dry_run)


def catalogue_command(arguments) -> int:
    _, project = bind_in(load(), Path(arguments.folder))
    try:
        known = catalogue.for_scope(project)
    except catalogue.CatalogueError as error:
        print(f"vyd: {error}", file=sys.stderr)
        return 1
    if known is None:
        print(f"vyd: {'this folder belongs to no project' if project is None else 'project ' + project.name + ' declares no catalogue'}. Add [project.catalogue] with a file to its vyvid.toml", file=sys.stderr)
        return 1
    command = arguments.catalogue_command
    show = (lambda p: str(known.root / p)) if getattr(arguments, "absolute", False) else (lambda p: Path(p).as_posix())
    try:
        if command == "dump":
            print(json.dumps(catalogue.dump(known), indent=2))
        elif command == "area":
            print(show(known.area(arguments.name)))
        elif command == "path":
            print(show(known.module(arguments.module).directory(arguments.role)))
        elif command == "paths":
            for path in known.module(arguments.module).files(arguments.role):
                print(show(path))
        elif command == "modules":
            for m in known.modules.values():
                if arguments.kind is None or m.kind == arguments.kind:
                    print(f"{m.name}  {m.kind}  {m.path.as_posix()}")
        else:
            release = f", release {known.release_version} of {len(known.release_members())} module(s)" if known.release_version else ""
            print(f"{known.file}: {len(known.modules)} module(s), {len(known.roots) + len(known.docs)} area(s), {len(known.tools)} tool package(s){release}")
    except catalogue.CatalogueError as error:
        print(f"vyd: {error}", file=sys.stderr)
        return 1
    return 0


def guard_command(arguments) -> int:
    config = load()
    folder = Path(getattr(arguments, "folder", "."))
    if arguments.guard_command == "hook":
        text = sys.stdin.read() if arguments.name == "pre-push" and not sys.stdin.isatty() else ""
        return guard.run_hook(config, arguments.name, arguments.args, text, Path.cwd())
    if arguments.guard_command == "status":
        if not config.guard.on:
            print("no guard is configured. Name domains in [framework.guard] to guard repositories")
            return 0
        lists = guard.read_lists(config)
        verdict = guard.classify(config, lists, folder)
        print(f"{folder.resolve()}: {verdict.kind}" + (f" ({verdict.repo})" if verdict.repo else ""))
        print(f"lists: {len(lists.public)} public and {len(lists.private)} private repositories, {len(lists.deny)} terms for all, "
              f"{len(lists.public_deny)} for public, {len(lists.warn)} warnings, {len(lists.never_track)} never-track and {len(lists.sensitive)} sensitive paths")
        print(f"git hooks: {guard.hooks_state()}")
        for line in guard.status_lines(config, folder):
            print(line)
        return 0
    if arguments.all:
        verdict, findings = guard.check_tree(config, folder)
    else:
        lists = guard.read_lists(config)
        verdict = guard.classify(config, lists, folder)
        lines, paths = guard.staged(folder) if verdict.kind in ("public", "private") else ([], [])
        findings = guard.check_lines(lists, verdict.kind, lines) + guard.check_paths(lists, verdict.kind, verdict.repo, paths, None)
    for f in findings:
        print(f)
    blocking = [f for f in findings if not f.warn]
    print(f"guard check ({verdict.kind}): {len(blocking)} finding(s), {len(findings) - len(blocking)} warning(s)")
    return 1 if blocking else 0


def reads_command(arguments) -> int:
    config, project = bind_in(load(), Path(arguments.folder))
    if project is None:
        print("vyd: this folder belongs to no project", file=sys.stderr)
        return 1
    if arguments.reads_command == "status":
        return reads.status(config, project)
    name = arguments.name
    if name not in project.reads:
        print(f"vyd: project {project.name} does not read {name}" + (f". {'; '.join(project.read_notes)}" if project.read_notes else ""), file=sys.stderr)
        return 1
    if arguments.reads_command == "pin":
        source = reads.source_of(config, name)
        commit, why = reads.resolve_pin(source, arguments.ref) if source is not None else (None, f"{name} has no configured code folder")
        if commit is None:
            print(f"vyd: {why}", file=sys.stderr)
            return 1
        return configure.reads_pin(project, name, commit, arguments.dry_run, _person)
    if not arguments.dry_run and not _person():
        print("vyd: a person must review a read, in a terminal", file=sys.stderr)
        return 1
    for line in reads.review_text(config, project, name):
        print(line)
    return configure.reads_review(project.name, name, project.reads[name].commit, arguments.dry_run, _person)


def context(folder: Path, as_json: bool, pull: bool = True) -> int:
    configured = load()
    config, project = bind_in(configured, folder)
    _set_aside(config)
    _dropped(project)
    if pull:
        for result in kb.pull_due(config, layers(config, project)):
            if not result.ok:
                print(f"vyd: pull of {result.name} failed: {result.text}", file=sys.stderr)
    stack = [_layer(config, s) for s in layers(config, project)]
    if as_json:
        print(json.dumps({"folder": str(folder.resolve()), "project": project and project.name,
                          "checkout": str(project.checkout) if project and project.checkout else None, "layers": stack}, indent=2))
        return 0
    print(f"{streams.display_name()} {__version__}: the contract for {folder.resolve()}")
    print(f"project: {project.name if project else 'none, so the general scope alone'}")
    for line in guard.status_lines(configured, folder):
        print(line)
    if project and project.checkout:
        entry = configured.projects.get(project.name)  # a project a vyvid.toml declares alone has no configured folder
        print(f"checkout: answering from {project.checkout}" + (f", not the configured code folder {entry.code}" if entry is not None else ""))
    print("Read each layer's rules in this order. A later layer overrides an earlier one, and the project's is last.\n")
    for n, layer in enumerate(stack, 1):
        print((f"{n}. {layer['scope']}" if layer["kind"] == layer["scope"] else f"{n}. {layer['kind']} {layer['scope']}") + f" ({layer['visibility']})")
        if "read" in layer:
            print(f"   a snapshot of commit {layer['read']['commit'][:12]}, read by {layer['read']['by']}: knowledge" + (", with the skills and recipes it names" if layer["read"]["standing"] == "reviewed" else " alone"))
        for key in ("rules", "skills"):
            for item in layer[key]:
                print(f"   {key[:-1]:<5} {item['path']}" + ("" if item["exists"] else "   (missing)"))
        if "withheld" in layer:
            w = layer["withheld"]
            since = (f"project {layer['read']['by']}'s read of {layer['scope']} has not been reviewed" if "read" in layer
                     else f"the vyvid.toml of project {layer['scope']} is not trusted" if layer["kind"] == "project"
                     else f"domain {layer['scope']} has trust {w['trust']}")
            print(f"   withheld: {len(w['rules'])} rule file(s), {len(w['skills'])} skill path(s) and {len(w['recipes'])} recipe description(s), "
                  f"since {since}, which gives knowledge alone")
            if layer["kind"] == "project" and "read" not in layer:
                print(f"   no glue or command extractor of {layer['file']} runs. A person runs vyd trust in a terminal, in that repository, after reading what it declares")
        for recipe in layer["recipes"]:
            print(f"   recipe {recipe['name']}  {recipe['description'] or '(description withheld)'}")
        for kind in layer.get("brings", []):
            print(f"   brings extractor {kind}")
        for run in layer.get("runs", []):
            print(f"   runs extractor {run['kind']}" + (f" of domain {run['domain']}" if run["domain"] else ""))
            for key, value in run["settings"].items():
                print(f"      {key} = {value}   ({run['sources'][key]})")
        for item in layer.get("reads", []):
            taken = f"; takes skills {', '.join(item['skills']) or 'none'} and recipes {', '.join(item['recipes']) or 'none'}" if item["standing"] == "reviewed" else ""
            print(f"   reads {item['name']} at {item['commit'][:12]}, {'reviewed' if item['standing'] == 'reviewed' else 'knowledge alone'}{taken}")
        for domain, item in layer.get("specialises", {}).items():
            print(f"   specialises {domain} in {item['path']}" + ("" if item["exists"] else "   (missing)"))
        for item in layer.get("symbols", []):
            print(f"   symbols of {item['language']} parsed from {', '.join(item['paths'])}")
        for item in layer.get("code_index", []):
            built = ", built_by withheld" if "withheld" in layer else (f", built by {item['built_by']}" if item["built_by"] else "")
            print(f"   code index {item['kind']}: {item['database']}" + ("" if item["exists"] else " (missing)") + built
                  + (". vyd handoff <name> prints its commands and runs none" if item["known"] else ", a kind vyd knows no commands for"))
    return 0


def _report(results: list[kb.Result]) -> int:
    for r in results:
        print(f"{r.name}: {r.text}" if r.ok else f"{r.name}: FAILED: {r.text}")
    return 0 if all(r.ok for r in results) else 1


def kb_status(config) -> int:
    for scope in kb.managed(config):
        s = kb.inspect(config, scope)
        print(f"{s.name}  {s.folder}")
        if not s.exists:
            print(f"   missing, run vyd kb clone {s.name}")
        elif not s.clone:
            print(f"   exists and is not a clone of {s.remote or 'a remote (none is configured)'}")
        else:
            upstream = "no upstream" if s.ahead is None else f"ahead {s.ahead} behind {s.behind}"
            pulled = time.strftime("%Y-%m-%d %H:%M", time.localtime(s.last_pull)) if s.last_pull else "never"
            print(f"   clone of {s.remote}, branch {s.branch or 'detached'}, {upstream}, "
                  f"{f'{s.changes} uncommitted' if s.changes else 'clean'}, last pulled {pulled}")
        print(f"   policy pull={s.policy.pull} commit={s.policy.commit} push={s.policy.push}, trust {scope.trust}")
        if s.held:
            read = command_line(["git", "-C", str(s.folder), "diff", "HEAD...@{u}"])
            print(f"   held: {', '.join(s.held)} changed upstream and nothing was merged. Read {read}, then a person runs vyd kb accept {s.name}")
    return 0


def _output_terminal() -> bool:
    try:
        return sys.stdout is not None and sys.stdout.isatty()
    except ValueError:  # closed
        return False


def _can_ask(command: str) -> bool:
    """Whether a question can be put to a person: they are at a terminal and the question will be seen there. A task runner that
    captures output holds the question until the command ends, so the task looks hung. Where it cannot, say at once what to run."""
    if _person() and _output_terminal():
        return True
    print(f"vyd: {command} asks a question, so it needs a person at a terminal with its output on that terminal. A task runner that "
          f"captures output, such as mise run, would hide the question and look hung. Run it yourself: {command}, "
          f"or, where mise supplies vyd, mise exec -- {command}", file=sys.stderr)
    return False


def kb_accept(config, name: str) -> int:
    """Fast-forward a held domain, once a person has seen what changed and typed its name."""
    if not _can_ask(f"vyd kb accept {name}"):
        return 1
    try:
        [scope] = kb.select(config, [name])
    except kb.KbError as error:
        print(f"vyd: {error}", file=sys.stderr)
        return 1
    if not kb.held(scope):
        print(f"{name}: nothing is held")
        return 0
    print(f"{name}: these files changed upstream, and the instruction-bearing ones held the pull:")
    held = set(kb.held(scope))
    for file in kb.changed(scope):
        print(f"  {file}" + ("   (instruction-bearing)" if file in held else ""))
    print("Read it with " + command_line(["git", "-C", str(scope.path), "diff", "HEAD...@{u}"]))
    if _typed(f"Type {name} to accept these changes: ") != name:
        print("not accepted")
        return 1
    return _report([kb.accept(config, scope)])


def kb_command(arguments) -> int:
    config = load()
    action = arguments.kb_command
    if action == "status":
        return kb_status(config)
    if action == "accept":
        return kb_accept(config, arguments.domain)
    if action == "record":
        return _report(kb.record(config, arguments.paths, arguments.message))
    try:
        scopes = kb.select(config, arguments.domains)
    except kb.KbError as error:
        print(f"vyd: {error}", file=sys.stderr)
        return 1
    if action == "clone":
        if not arguments.domains:
            scopes = [s for s in scopes if not s.path.exists()]
        return _report([kb.clone(config, s) for s in scopes])
    return _report(kb.pull(config, scopes, due=arguments.due))


def _typed(prompt: str) -> str:
    """What a person typed, empty when the input ends first, which is no agreement."""
    try:
        return input(prompt).strip()
    except (EOFError, UnicodeError, OSError, ValueError):
        return ""


def trust_command(path: Path | None) -> int:
    """Record the hash of a configuration, or of a repository's vyvid.toml, once a person has seen what it
    runs and typed yes. With no path it is the vyvid.toml of the current folder's repository if there is one."""
    if not _can_ask("vyd trust"):
        return 1
    file = None
    if path is None or path.is_dir() or path.name == configuration.PROJECT_FILE:
        file = project_file(path or Path("."))
        if file is None and path is not None:
            print(f"vyd: no {configuration.PROJECT_FILE} at or above {path}", file=sys.stderr)
            return 1
    path = file or path or configuration.config_path()
    if not path.exists():
        print(f"vyd: {path} does not exist, so there is nothing to trust", file=sys.stderr)
        return 1
    config = load(None if file else path)
    if file:
        scope, problems = file_scope(config, file)
        if scope is None:
            print(f"vyd: {file} cannot be used, so there is nothing to trust:", file=sys.stderr)
            for problem in problems:
                print(f"  {problem}", file=sys.stderr)
            return 1
        lines = [*configuration.declared([scope]), *(f"project {scope.name}, contract: {p}" for p in scope.rules),
                 *(f"project {scope.name}, skills: {p}" for p in scope.skills),
                 *(f"project {scope.name}, code index {handoff.clean(i.kind)}, shown to agents as text and never run, built by: {handoff.clean(i.built_by)}" for i in scope.code_index if i.built_by)]
    else:
        lines = configuration.declared(config.projects.values())
    says = ("these, which an agent reads or which run with your privileges:", "no glue, no command extractor, no contract and no skills.") if file else \
           ("these, which run with your privileges:", "no glue and no command extractor.")
    print(f"{path.resolve()} declares " + says[not lines])
    for line in lines:
        print(f"  {line}")
    if _typed("Type yes to trust this file as it is now: ") != "yes":
        print("not trusted")
        return 1
    (configuration.record_file_trust if file else configuration.record_trust)(path)
    print(f"trusted {path.resolve()}, until it changes")
    return 0


def build_index(folder: Path, everything: bool, embed: bool) -> int:
    from .build import build, store_dir

    config, project = bind_in(load(), folder)
    if not everything and project is None:
        print("no project claims this folder, so the general scope alone is built. Use --all for every scope")
    _set_aside(config)
    _dropped(project)
    out = build(config, None if everything else project, embed=embed, scopes=None if everything or project else [config.general])
    for key in sorted(out.counts):
        print(f"  {key:<28} {out.counts[key]}")
    for problem in out.problems:
        print(f"NOTE: {problem}")
    for finding in out.findings:
        print(f"FINDING: {finding}")
    print(f"knowledge index built at {store_dir(config, None if everything else project) / 'store'}")
    return 0


def check_citations(arguments) -> int:
    """Refuse the lines a public project adds that cite an entry of a private scope."""
    config, project = bind_in(load(), Path(arguments.folder))
    if project is None:
        print("no project claims this folder, so there is no public text to check")
        return 0
    if project.visibility != "public":
        print(f"project {project.name} is private, so its text may cite any entry")
        return 0
    if not (arguments.staged or arguments.paths or arguments.message):
        print("vyd: name the paths to check, or use --staged or --message", file=sys.stderr)
        return 2
    if arguments.message and not Path(arguments.message).is_file():
        print(f"vyd: {arguments.message} is not a file", file=sys.stderr)
        return 2
    try:
        lines = (citations.staged_lines(project) if arguments.staged else []) + citations.file_lines([Path(p) for p in [*arguments.paths, *([arguments.message] if arguments.message else [])]])
    except citations.GitError as error:
        print(f"vyd: {error}", file=sys.stderr)
        return 2
    refused = citations.private_citations(config, project, lines)
    for line in refused:
        print(line)
    if not refused:
        print(f"{len(lines)} line(s) checked, and none cites an entry of a private scope")
    return 1 if refused else 0


def docs_record(arguments) -> int:
    """Keep paths of the folder's project's private documents by its ``git.docs`` policy."""
    config, project = bind_in(load(), Path(arguments.folder))
    if project is None or project.docs is None:
        print("vyd: no project claims this folder, so there are no documents to record", file=sys.stderr)
        return 1
    return _report(kb.docs_record(project, config, arguments.paths, arguments.message))


def recipe_command(arguments, parser) -> int:
    """List the recipes of the folder's stack, or run one as a briefing, or resume a run stopped at glue."""
    config = load()
    folder = Path(arguments.folder)
    resuming = arguments.recipe_command == "run" and arguments.resume is not None
    state = None
    if resuming:
        if arguments.name or arguments.question or not arguments.glue_output:
            parser.error("--resume takes --glue-output and no recipe name or question")
        try:
            state = recipes.read_state(Path(arguments.resume))
        except recipes.RecipeError as error:
            print(f"vyd: {error}", file=sys.stderr)
            return 1
        folder = Path(state["folder"])
    config, project = bind_in(config, folder)
    found = recipes.available(layers(config, project))
    if arguments.recipe_command == "list":
        if found:
            ask.show([{"name": r.name, "scope": r.scope, "description": r.description if config.scope(r.scope).trusted else "(withheld)"} for r in found.values()],
                     ("name", "scope", "description"))
        else:
            print("no recipe is declared in this folder's stack")
        return 0
    if not resuming and not (arguments.name and arguments.question):
        parser.error("a recipe name and a question are needed, or --resume with --glue-output")
    name = state["recipe"] if state else arguments.name
    recipe = found.get(name)
    if recipe is None and not resuming:
        print(f"vyd: no recipe '{name}' in this folder's stack, which has {', '.join(found) or 'none'}", file=sys.stderr)
        return 1
    if arguments.dry_run and not resuming:
        print(recipes.dry_run(recipe, config.scope(recipe.scope)))
        return 0
    question, entries, start = arguments.question, None, 0
    try:
        if state:
            step = recipes.resumed_step(state, recipe)
            recipe = replace(recipe, budget=state["budget"])
            question, start = state["question"], state["next"]
            entries = recipes.glue_output(Path(arguments.glue_output), step)
        a = ask.open_stack(config, folder, scope=recipes.extra_scopes(recipe), ranking=True)
        entries = recipes.run(a, recipe, question, entries, start, stop=resuming or arguments.stop_at_glue)
    except ValueError as error:
        parser.error(str(error))
    except recipes.GlueStop as stopped:
        print(recipes.stop_at(a, recipe, question, folder, stopped))
        if state:
            recipes.finish(Path(arguments.resume))
        return recipes.STOPPED
    except recipes.RecipeError as error:
        print(f"vyd: recipe {name}: {error}", file=sys.stderr)
        return 1
    if state:
        recipes.finish(Path(arguments.resume))
    text, size, dropped = recipes.briefing(recipe, question, entries, arguments.all)
    if arguments.json:
        shown = entries[: len(entries) - dropped]
        print(json.dumps({"recipe": recipe.name, "scope": recipe.scope, "question": question, "budget": recipe.budget,
                          "estimated_tokens": size, "dropped": dropped, "entries": shown}, indent=2, ensure_ascii=False))
    else:
        print(text)
        print(f"\n(about {size} tokens)")
    return 0


def store_command(arguments) -> int:
    """Remove the stores of linked checkouts that are gone."""
    from .build import prune

    gone = prune(load(), arguments.dry_run)
    for folder, root in gone:
        print(f"{'would remove' if arguments.dry_run else 'removed'} {folder}  (checkout {root} no longer exists)")
    if not gone:
        print("no checkout store is left behind")
    return 0


def _question(arguments, parser) -> int:
    """Run one of the questions in ``ask`` for the stack of the folder named by ``--in``."""
    config = load()
    command = arguments.command
    folder = Path(arguments.folder)
    if command in ("gap", "close"):
        a = ask.open_stack(config, folder, need_store=False)
        return ask.gap(a, arguments.text, arguments.extras) if command == "gap" else ask.close(a, arguments.ids)
    try:
        a = ask.open_stack(config, folder, scope=getattr(arguments, "scope", ""), ranking=command in ("find", "misses"))
    except ValueError as error:
        parser.error(str(error))
    a.logging = not getattr(arguments, "no_log", False)
    if command == "misses":
        return ask.misses(a, arguments.limit, arguments.near, again=True)
    if command == "find":
        try:
            chosen = ask.filters(a, arguments.kind, arguments.exclude, arguments.phase, arguments.audience,
                                 activity=arguments.activity, quality=arguments.quality, tech=arguments.tech)
        except ValueError as error:
            parser.error(str(error))
        if arguments.doc_share is not None and "Symbol" not in chosen[0]:
            parser.error("--doc-share goes with --kind symbol, since it says how symbols and documentation share places")
        if "Symbol" in chosen[0]:
            if chosen[0] != {"Symbol"}:
                parser.error("--kind symbol is asked alone, since symbols are ranked apart from the entries")
            from .symbols.find import find_symbols

            return find_symbols(a, " ".join(arguments.words), arguments.limit, arguments.doc_share)
        return ask.find(a, " ".join(arguments.words), *chosen[:3], arguments.limit, chosen[3])
    if command == "read":
        return ask.read(a, arguments.argument)
    return ask.lookup(a, command, arguments.argument)


def _questions(sub) -> None:
    """The subcommands that ask the index something."""

    def asking(name: str, helptext: str):
        p = sub.add_parser(name, help=helptext)
        p.add_argument("--in", dest="folder", default=".", help="the folder whose stack the question is asked in")
        if name not in ("misses", "gap", "close"):
            p.add_argument("--scope", default="", help="scopes to add to the stack for this question, or only:a,b to read those alone")
        if name in ("find", "read"):
            p.add_argument("--no-log", action="store_true", help="write nothing to the ask and miss logs for this call, such as for a benchmark")
        return p

    p = asking("find", "entries ranked by how close their meaning is to your words")
    p.add_argument("words", nargs="+")
    p.add_argument("--kind", default="", help="comma-separated kinds the stack declares. Declared ontology terms are searched only when term is named, and the project's symbols only when symbol is, alone")
    p.add_argument("--exclude", default="", help="comma-separated kinds to leave out and keep every other, such as question")
    p.add_argument("--phase", default="", help="comma-separated phases")
    p.add_argument("--audience", default="", help="comma-separated audiences")
    for flag, (scheme, _) in ask.FACET_FLAGS.items():
        p.add_argument(f"--{flag}", default="", help=f"comma-separated values of the {scheme} facet, which raise matching entries and hide none")
    p.add_argument("--limit", type=int, default=8)
    p.add_argument("--doc-share", type=_doc_share, default=None, help="with --kind symbol, the share of places documentation may take, from 0 to 1. Overrides doc_share in the configuration")
    for name, helptext in (
        ("exists", "does a term for this already exist in any ontology module of the stack"),
        ("node", "what one identifier is, and where to read it"),
        ("read", "the text of the section or definition an identifier's pointer names"),
        ("reaches", "what an identifier touches, by declared relations"),
        ("sparql", "run a SPARQL query against the stack's graphs"),
    ):
        asking(name, helptext).add_argument("argument")
    p = asking("misses", "the questions answered weakly or not at all, newest first, and the gaps recorded")
    p.add_argument("--limit", type=int, default=20)
    p.add_argument("--near", action="store_true", help="also the questions answered from the weak score to under the near score")
    p = asking("gap", "record what reading found that the index did not say, as you find it")
    p.add_argument("text", help="what was found, in a sentence")
    p.add_argument("extras", nargs="*", help="the entry it qualifies, and the path:line it was read from")
    asking("close", "close the gaps recorded against entries whose signpost is now written").add_argument("ids", nargs="+")


def _project_hooks(project, dry_run: bool) -> int:
    """Register the reminder hook in the checkout, which the composed skills' values name the command for."""
    ask = project.skill_values.get("ask", skills.DEFAULT_VALUES["ask"])
    return install.install_hooks(project.code, project.hook_clients, ask, dry_run)


def _doc_share(text: str) -> float:
    value = float(text)
    if not 0 <= value <= 1:
        raise argparse.ArgumentTypeError(f"{text} is not from 0 to 1")
    return value


def main(argv: list[str] | None = None) -> int:
    # A git hook exports these, and under them `git -C <folder> rev-parse --show-toplevel` answers the folder itself. GIT_INDEX_FILE stays, as a partial commit's temporary index is what --staged reads.
    for name in ("GIT_DIR", "GIT_WORK_TREE"):
        os.environ.pop(name, None)
    parser = argparse.ArgumentParser(prog="vyd", description=f"{streams.display_name()}: the contract and knowledge for the folder an agent is in")
    parser.add_argument("--version", action="version", version=f"{streams.version_text()} {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)
    c = sub.add_parser("context", help="the contract that applies in a folder, general first and the project last")
    c.add_argument("folder", nargs="?", default=".")
    c.add_argument("--json", action="store_true")
    c.add_argument("--no-pull", action="store_true", help="do not pull the managed domains that are due first")
    k = sub.add_parser("kb", help="the managed domains under the knowledge base: status, clone, pull and record").add_subparsers(dest="kb_command", required=True)
    k.add_parser("accept", help="a person fast-forwards a domain whose pull was held, after reading what changed").add_argument("domain")
    k.add_parser("status", help="each managed domain's clone, branch, ahead and behind, changes, last pull and policy")
    k.add_parser("clone", help="clone the named domains, or every managed domain whose folder is missing").add_argument("domains", nargs="*")
    p = k.add_parser("pull", help="git pull --ff-only in the named domains, or all of them")
    p.add_argument("domains", nargs="*")
    p.add_argument("--due", action="store_true", help="only the domains whose pull policy says one is due")
    p = k.add_parser("record", help="stage changed paths in their managed domain, then commit and push by its policy")
    p.add_argument("paths", nargs="+")
    p.add_argument("-m", "--message", required=True)
    p = sub.add_parser("docs", help="the private documents of a project").add_subparsers(dest="docs_command", required=True)
    p = p.add_parser("record", help="stage paths in the project's documents folder, then commit and push by its git.docs policy")
    p.add_argument("paths", nargs="+")
    p.add_argument("-m", "--message", required=True)
    p.add_argument("--in", dest="folder", default=".", help="the folder whose project's documents are kept")
    p = sub.add_parser("board", help="where every record and slice of a folder's project is, across every branch where it declares work settings")
    p.add_argument("folder", nargs="?", default=".")
    p.add_argument("--state", help="only the slices whose state starts with this word")
    p.add_argument("--all", action="store_true", help="every row, not only what differs from the trunk")
    p.add_argument("--fetch", action="store_true", help="fetch every remote first")
    p.add_argument("--measure", action="store_true", help="add each branch's content share on the trunk, the slow part")
    p.add_argument("--commits", action="store_true", help="add the commit that set each printed row")
    p.add_argument("--here", action="store_true", help="read the slices of the project's families of type slice in this one checkout")
    w = sub.add_parser("work", help="the generated regions, the hook check and the migrations of a project's work board").add_subparsers(dest="work_command", required=True)
    for name, helptext in (("build", "write the index's generated region from the status records in the working tree"),
                           ("roadmap", "write the roadmap's generated regions from every branch")):
        p = w.add_parser(name, help=helptext)
        p.add_argument("--check", action="store_true", help="fail if the region is stale and write nothing")
        if name == "roadmap":
            p.add_argument("--fetch", action="store_true", help="fetch every remote first")
    p = w.add_parser("check", help="hold the status records to the ladder and the grammar and the index's region to the records, as a hook runs it")
    p.add_argument("--staged", action="store_true", help="only the status records staged, and the region when one or the index is")
    p = w.add_parser("parse", help="print a status record's board as read")
    p.add_argument("record", type=Path)
    for name, helptext in (("rename", "build the crosswalk from historic ids and sweep every mention onto the grammar"),
                           ("normalise", "rewrite every status record's board into the standard columns and state words"),
                           ("adopt", "bring the slices a record's other tables, a Validation Pack or a plan name onto its board")):
        p = w.add_parser(name, help=helptext + ". Reports without --apply")
        p.add_argument("--apply", action="store_true", help="write the changes")
    for p in w.choices.values():
        p.add_argument("--in", dest="folder", default=".", help="the folder whose project is read")
    p = sub.add_parser("here", help="who is in this checkout: write your presence, or list the live sessions")
    p.add_argument("--in", dest="folder", default=".", help="the folder whose project is read")
    p.add_argument("--role", choices=("build", "review", "read"), help="write your presence with this role")
    p.add_argument("--model", default="", help="the model you run on, stated by hand since no client names it")
    p.add_argument("--on", default="", help="the slices you are on, comma separated")
    p.add_argument("--leave", action="store_true", help="remove your presence")
    p.add_argument("--now", default="", help="the clock, as an ISO timestamp, for tests. The wall clock otherwise")
    r = sub.add_parser("resolve", help="the canonical scope:LOCAL an identifier names")
    r.add_argument("identifier")
    r.add_argument("--in", dest="folder", default=".")
    b = sub.add_parser("build", help="build the knowledge index for a folder's project, or for every scope")
    b.add_argument("folder", nargs="?", default=".")
    b.add_argument("--all", action="store_true", help="every configured scope, not the folder's stack")
    b.add_argument("--no-embed", action="store_true", help="build the store and write no vectors")
    c = sub.add_parser("check", help="checks of a folder's text").add_subparsers(dest="check_command", required=True)
    p = c.add_parser("citations", help="refuse added lines of a public project that cite an entry of a private scope")
    p.add_argument("paths", nargs="*", help="files or folders whose every line is checked")
    p.add_argument("--staged", action="store_true", help="the lines staged in the project's code repository, and its documents repository when those are public")
    p.add_argument("--message", metavar="FILE", help="a commit message or pull request text, every line of which is checked")
    p.add_argument("--in", dest="folder", default=".", help="the folder whose project is checked")
    p = c.add_parser("skills", help="fail where a project's committed skills differ from their sources, or a line of a file named by --from has no home")
    p.add_argument("folder", nargs="?", default=".")
    p.add_argument("--from", dest="sources", type=Path, nargs="*", default=[], help="old skill files, each of whose lines must be in a composed skill or in --map")
    p.add_argument("--map", type=Path, help="with one --from file, a tab-separated map with line and destination columns")
    p = c.add_parser("identifiers", help="fail on a mentioned identifier nothing defines, or one a family defines twice")
    p.add_argument("folder", nargs="?", default=".")
    p.add_argument("--json", action="store_true")
    p.add_argument("--all", action="store_true", help="also list each variant, each removable entry no longer defined and each stale exception")
    p = sub.add_parser("move", help="what a project moved to a domain").add_subparsers(dest="move_command", required=True)
    p = p.add_parser("check", help="compare each moved source file at its commit with a ref, by identifier")
    p.add_argument("folder", nargs="?", default=".")
    p.add_argument("--ref", help="a git ref, the working tree by default")
    p.add_argument("--json", action="store_true")
    rd = sub.add_parser("reads", help="the projects a folder's project reads for their knowledge: status, pin and review").add_subparsers(dest="reads_command", required=True)
    rd.add_parser("status", help="each read's pin against its source, its standing and what it may bring").add_argument("--in", dest="folder", default=".")
    p = rd.add_parser("pin", help="pin a read to the full commit a ref names, which must be on the source's default branch")
    p.add_argument("name")
    p.add_argument("ref")
    p.add_argument("--in", dest="folder", default=".")
    p.add_argument("--dry-run", action="store_true")
    p = rd.add_parser("review", help="a person records that they read what a read may bring at its pin, so its skills and recipes count")
    p.add_argument("name")
    p.add_argument("--in", dest="folder", default=".")
    p.add_argument("--dry-run", action="store_true")
    p = sub.add_parser("recipe", help="the named chains of queries of a folder's stack").add_subparsers(dest="recipe_command", required=True)
    p.add_parser("list", help="each recipe of the stack, its scope and when to use it").add_argument("--in", dest="folder", default=".")
    r = p.add_parser("run", help="run one recipe for a question and print its briefing")
    r.add_argument("name", nargs="?")
    r.add_argument("question", nargs="?")
    r.add_argument("--in", dest="folder", default=".", help="the folder whose stack the recipe is read from")
    r.add_argument("--all", action="store_true", help="every entry, ignoring the recipe's budget")
    r.add_argument("--json", action="store_true")
    r.add_argument("--dry-run", action="store_true", help="print each step and each glue command with its folder, and run nothing")
    r.add_argument("--stop-at-glue", action="store_true", help="stop at a glue step and print its command for you to run, then resume")
    r.add_argument("--resume", metavar="STATE", help="go on from the state file a stopped run printed")
    r.add_argument("--glue-output", metavar="FILE", help="with --resume, the file holding the glue command's output")
    st = sub.add_parser("store", help="the index stores").add_subparsers(dest="store_command", required=True)
    st.add_parser("prune", help="remove the stores of linked checkouts that no longer exist").add_argument(
        "--dry-run", action="store_true", help="print what would be removed and remove nothing")
    d = sub.add_parser("domain", help="make a domain folder, or report the facts about one someone else wrote").add_subparsers(dest="domain_command", required=True)
    p = d.add_parser("new", help="write a domain folder with a manifest, a facet stub, an empty register and a skill stub, and print the lines to add to your configuration")
    p.add_argument("name")
    p.add_argument("--registers", default="note", metavar="TYPE", help="the register type of its first register, note by default")
    p.add_argument("--path", type=Path, help="the folder to write, the knowledge base's domains/<name> by default")
    p = d.add_parser("add", help="add a domain to your configuration")
    p.add_argument("name")
    p.add_argument("--path", help="the domain's folder, the knowledge base's domains/<name> by default")
    p.add_argument("--remote", help="the repository to clone it from, cloned later with vyd kb clone")
    p.add_argument("--trust", choices=cf_trusts, default="knowledge", help="what it gives an agent. knowledge by default. own and reviewed need a person at a terminal")
    p.add_argument("--commit", help="with --trust reviewed, the commit that was reviewed")
    p.add_argument("--visibility", choices=cf_visibilities, help="private unless this says public")
    _writes(p, hidden_file=True)
    p = d.add_parser("trust", help="change the trust of a configured domain. Raising it needs a person at a terminal")
    p.add_argument("name")
    p.add_argument("trust", choices=cf_trusts)
    p.add_argument("--commit", help="with reviewed, the commit you read")
    p.add_argument("--dry-run", action="store_true", help="print the change and write nothing")
    p = d.add_parser("remove", help="take a domain out of your configuration, refused while a project uses it. Its folder is left alone")
    p.add_argument("name")
    _writes(p, hidden_file=True)
    pr = sub.add_parser("project", help="declare a project, change it, remove it, or find the registers in its documents").add_subparsers(dest="project_command", required=True)
    p = pr.add_parser("add", help="declare a project. In a git checkout, its code folder and remotes are read from it")
    p.add_argument("name")
    p.add_argument("--code", help="its code folder, the git checkout you are in by default")
    p.add_argument("--docs", help="its documents folder, when they are kept apart from the code")
    p.add_argument("--contract", action="append", default=[], help="a rule file, such as docs:CONTRACT.md. Repeat for several")
    p.add_argument("--remote", action="append", default=[], help="a remote that identifies the checkout, the checkout's own remotes by default. Repeat for several")
    p.add_argument("--domain", action="append", default=[], help="a configured domain it uses. Repeat for several")
    p.add_argument("--visibility", choices=cf_visibilities, default="private", help="private by default")
    _writes(p)
    p = pr.add_parser("set", help="set a plain key of a project, such as docs, visibility or domains")
    p.add_argument("name")
    p.add_argument("key")
    p.add_argument("value", nargs="+", help="one value, or several for a list key")
    _writes(p)
    p = pr.add_parser("remove", help="take a project out of your configuration. Its index store, logs and folders are left alone")
    p.add_argument("name")
    _writes(p)
    p = pr.add_parser("scan", help="find the registers in a project's documents and propose a family for each, writing them with --apply")
    p.add_argument("name")
    p.add_argument("--apply", action="store_true", help="write the proposed families")
    _writes(p)
    fa = sub.add_parser("family", help="declare or remove an identifier family of a project").add_subparsers(dest="family_command", required=True)
    p = fa.add_parser("add", help="declare a family and the register that defines it")
    p.add_argument("project")
    p.add_argument("name")
    p.add_argument("--defined", required=True, help="the register, such as docs:standards.md")
    p.add_argument("--type", required=True, help="its register type, such as standard or debt")
    p.add_argument("--pattern", help="a regular expression for its identifiers, where PREFIX-1 is not their form")
    p.add_argument("--removable", action="store_true", help="its entries are meant to disappear, so an unresolved mention is reported and never failed")
    _writes(p)
    p = fa.add_parser("remove", help="remove a family from a project. Its register is left alone")
    p.add_argument("project")
    p.add_argument("name")
    _writes(p)
    p = d.add_parser("audit", help="report links, file types, paths, patterns, hidden text and commands in a folder, and run nothing from it")
    p.add_argument("folder", type=Path)
    p.add_argument("--json", action="store_true")
    p.add_argument("--allow", action="append", default=[], metavar="SCOPE", help="a scope the domain may cite, such as a parent. Repeat for several")
    p = d.add_parser("review-path", help="where the review of a domain at a commit is recorded")
    p.add_argument("domain")
    p.add_argument("commit")
    p = sub.add_parser("handoff", help="the exact commands for the code index a project registers, printed and never run")
    p.add_argument("name", help="a name to find the definition and references of, or a module the index holds, for what it calls")
    p.add_argument("--module", help="the module the name is defined in, or a module to list the calls of")
    p.add_argument("--unit", help="with a module, keep what it calls to the units whose name starts with this")
    p.add_argument("--in", dest="folder", default=".", help="the folder whose project's code index is used")
    i = sub.add_parser("install", help="write a client's user-level rule file and one skill per configured domain")
    i.add_argument("--client", choices=sorted(install.CLIENTS), help="only this client. Every client whose folder exists, without it")
    i.add_argument("--project", action="store_true", help="compose this folder's project's skills and hooks into its checkout, to be committed")
    i.add_argument("--in", dest="folder", default=".", help="with --project, the folder whose project is written")
    i.add_argument("--hooks", action="store_true", help="also register the reminder hook in the client's user-level settings, for a client that documents a place for one")
    i.add_argument("--target", type=Path, help="the folder to write into, instead of the client's own")
    i.add_argument("--no-git-hooks", action="store_true", help="do not set up the guard's git hooks, which are set up when a guard is configured")
    i.add_argument("--dry-run", action="store_true", help="say what would be written and write nothing")
    ct = sub.add_parser("catalogue", help="where things live in the folder's project, from its repository catalogue: areas, modules and their roles").add_subparsers(dest="catalogue_command", required=True)
    for name, helptext in (("show", "the catalogue's modules, areas and release"), ("dump", "all of it as JSON, every path relative to the root"), ("modules", "the modules, one a line, optionally of one kind")):
        p = ct.add_parser(name, help=helptext)
        p.add_argument("--in", dest="folder", default=".")
        if name == "modules":
            p.add_argument("--kind")
    p = ct.add_parser("area", help="the folder of a named root or documentation area")
    p.add_argument("name")
    p.add_argument("--in", dest="folder", default=".")
    p.add_argument("--absolute", action="store_true", help="join the answer to the root of this checkout")
    for name, helptext in (("path", "the folder of one role of a module"), ("paths", "the files a module's README generates for a role, in order")):
        p = ct.add_parser(name, help=helptext)
        p.add_argument("module")
        p.add_argument("role")
        p.add_argument("--in", dest="folder", default=".")
        p.add_argument("--absolute", action="store_true", help="join each answer to the root of this checkout")
    s = sub.add_parser("setup", help="set up a first local configuration: the knowledge base, and the published domains the folder's project names")
    s.add_argument("folder", nargs="?", default=".")
    s.add_argument("--no-clone", action="store_true", help="add the domains and leave their folders to vyd kb clone")
    s.add_argument("--dry-run", action="store_true", help="say what would be done and write nothing")
    g = sub.add_parser("guard", help="keep the private terms of a user out of public repositories: status, check, and the hook the git hooks run").add_subparsers(dest="guard_command", required=True)
    g.add_parser("status", help="the folder's class, the lists in force and whether the git hooks are in place").add_argument("--in", dest="folder", default=".")
    p = g.add_parser("check", help="the lines staged for commit, or with --all every tracked file, against the lists")
    p.add_argument("--in", dest="folder", default=".")
    p.add_argument("--all", action="store_true", help="every tracked file, to find what a new list leaves in existing text")
    p = g.add_parser("hook", help="run by the git hooks: pre-commit, commit-msg or pre-push")
    p.add_argument("name", choices=guard.GUARDED_HOOKS)
    p.add_argument("args", nargs="*")
    c = sub.add_parser("cloud", help="set up a cloud environment").add_subparsers(dest="cloud_command", required=True)
    p = c.add_parser("script", help="write the setup script for a cloud environment, holding the private domains you name and cloning the public ones")
    p.add_argument("--output", required=True, help="the file to write, owner-only. The script holds private text, so it is never printed")
    p.add_argument("--domain", action="append", default=[], metavar="NAME[=PATH]", help="a private domain to embed, and where to write it in the cloud, under ~/. Repeat for several")
    p.add_argument("--grant", action="append", default=[], metavar="REMOTE", help="a repository whose vyvid.toml the cloud trusts, written as host/owner/repository. Repeat for several")
    p.add_argument("--run", metavar="PATH", help="a setup script of the project's own, as a path inside its repository, run from the session's checkout after the rest")
    p.add_argument("--dry-run", action="store_true", help="say what would be written and write nothing")
    sub.add_parser("config", help="where the configuration is read from, whether it is sound and trusted, the domains set aside, and the folder's vyvid.toml").add_argument("folder", nargs="?", default=".")
    sub.add_parser("trust", help="a person trusts a configuration outside their own folder, or a repository's vyvid.toml, by its hash").add_argument("path", nargs="?", type=Path)
    _questions(sub)
    arguments = parser.parse_args(argv)
    streams.clean_arguments(arguments)
    try:
        if arguments.command == "context":
            return context(Path(arguments.folder), arguments.json, not arguments.no_pull)
        if arguments.command == "kb":
            return kb_command(arguments)
        if arguments.command == "docs":
            return docs_record(arguments)
        if arguments.command == "board":
            config, project = bind_in(load(), Path(arguments.folder))
            return work_command.board(config, project, arguments)
        if arguments.command in ("work", "here"):
            config, project = bind_in(load(), Path(arguments.folder))
            return (work_command.work if arguments.command == "work" else work_command.here)(config, project, arguments)
        if arguments.command == "resolve":
            config = load()
            scope = bind_in(config, Path(arguments.folder))[1] or config.general
            how: list[str] = []
            try:
                print(resolve(config, arguments.identifier, scope, how))
            finally:
                for line in how:
                    print(f"vyd: {line}", file=sys.stderr)
                for line in timeouts([config.general, *config.domains.values(), *config.projects.values()]):
                    print(f"vyd: {line}", file=sys.stderr)
            return 0
        if arguments.command == "build":
            return build_index(Path(arguments.folder), arguments.all, not arguments.no_embed)
        if arguments.command == "check" and arguments.check_command == "skills":
            config, project = bind_in(load(), Path(arguments.folder))
            if project is None:
                print(f"vyd: no project claims {arguments.folder}, so there are no skills to check")
                return 2
            return skills.check(config, project, arguments.sources, arguments.map)
        if arguments.command == "check":
            if arguments.check_command == "identifiers":
                config, project = bind_in(load(), Path(arguments.folder))
                return identifiers.command(config, project, arguments.json, arguments.all)
            return check_citations(arguments)
        if arguments.command == "move":
            config, project = bind_in(load(), Path(arguments.folder))
            return moves.command(config, project, arguments.ref, arguments.json)
        if arguments.command == "reads":
            return reads_command(arguments)
        if arguments.command == "recipe":
            return recipe_command(arguments, parser)
        if arguments.command == "store":
            return store_command(arguments)
        if arguments.command == "cloud":
            return cloud.command(arguments.output, arguments.domain, arguments.grant, arguments.dry_run, arguments.run)
        if arguments.command == "domain":
            if arguments.domain_command == "add":
                return configure.domain_add(arguments.name, arguments.path, arguments.remote, arguments.trust, arguments.commit, arguments.visibility,
                                            arguments.file, arguments.dry_run, _person)
            if arguments.domain_command == "trust":
                return configure.domain_trust(arguments.name, arguments.trust, arguments.commit, arguments.dry_run, _person)
            if arguments.domain_command == "remove":
                return configure.domain_remove(arguments.name, arguments.file, arguments.dry_run, _person)
            if arguments.domain_command == "new":
                return newdomain.new(arguments.name, arguments.registers, arguments.path)
            if arguments.domain_command == "audit":
                return audit.command(arguments.folder, arguments.json, tuple(arguments.allow))
            try:
                print(audit.review_path(arguments.domain, arguments.commit))
            except ValueError as error:
                parser.error(str(error))
            return 0
        if arguments.command == "project":
            c = arguments.project_command
            if c == "add":
                return configure.project_add(arguments.name, arguments.code, arguments.docs, arguments.contract, arguments.remote, arguments.domain,
                                             arguments.visibility, arguments.file, arguments.dry_run, _person)
            if c == "set":
                return configure.project_set(arguments.name, arguments.key, arguments.value, arguments.file, arguments.dry_run, _person)
            if c == "remove":
                return configure.project_remove(arguments.name, arguments.file, arguments.dry_run, _person)
            return configure.project_scan(arguments.name, arguments.apply, arguments.file, arguments.dry_run, _person)
        if arguments.command == "family":
            if arguments.family_command == "add":
                return configure.family_add(arguments.project, arguments.name, arguments.defined, arguments.type, arguments.pattern, arguments.removable,
                                            arguments.file, arguments.dry_run, _person)
            return configure.family_remove(arguments.project, arguments.name, arguments.file, arguments.dry_run, _person)
        if arguments.command == "handoff":
            from .build import store_dir

            config, project = bind_in(load(), Path(arguments.folder))
            return handoff.command(project, store_dir(config, project), arguments.name, arguments.module, arguments.unit)
        if arguments.command == "setup":
            return first_setup.run(Path(arguments.folder), not arguments.no_clone, arguments.dry_run, _person)
        if arguments.command == "guard":
            return guard_command(arguments)
        if arguments.command == "catalogue":
            return catalogue_command(arguments)
        if arguments.command == "install":
            if arguments.project:
                config, project = bind_in(load(), Path(arguments.folder))
                if project is None:
                    print(f"vyd: no project claims {arguments.folder}, so there is nothing to compose")
                    return 1
                return skills.install_project(config, project, arguments.dry_run) or _project_hooks(project, arguments.dry_run)
            if not arguments.client:
                if arguments.target:
                    parser.error("--target needs --client")
                configured = load()
                return max(install.install_all(configured, arguments.dry_run, arguments.hooks), _guard_hooks(configured, arguments))
            configured = load()
            done = install.install(configured, arguments.client, arguments.target, arguments.dry_run)
            if arguments.hooks:
                done = done or install.user_hook(arguments.client, arguments.target, arguments.dry_run)
            return max(done, _guard_hooks(configured, arguments)) if not arguments.target else done
        if arguments.command in QUESTIONS:
            return _question(arguments, parser)
        if arguments.command == "trust":
            return trust_command(arguments.path)
        configured = load()
        config, project = bind_in(configured, Path(arguments.folder))
        print(f"configuration: {config.source or config_path()}" + ("" if config.source else " (absent, so the general scope alone)"))
        print("configuration trust: " + ("trusted" if configuration.trusted(config) else "not trusted, so no glue or command extractor runs. A person runs vyd trust in a terminal"))
        for line in install.missing(config):
            print(f"NOTE: {line}")
        for line in install.out_of_date(config):
            print(line)
        if config.trusted_repositories:
            own = config.source is not None and config.source.resolve() == configuration.own_config().resolve()
            print(f"trusted repositories: {', '.join(config.trusted_repositories)}")
            if not own:
                print("NOTE: trusted_repositories is ignored here, since only the user's own configuration "
                      f"at {configuration.own_config()} may grant it")
        print(f"domains: {', '.join(config.domains) or 'none'}")
        print(f"projects: {', '.join(config.projects) or 'none'}")
        for name, why in config.set_aside.items():
            print(f"set aside: {name}")
            for problem in why:
                print(f"  {problem}")
        file = project_file(Path(arguments.folder))
        if file is not None:
            print(f"project file: {file}")
        for path, why in config.files_aside.items():
            print(f"set aside: the project declared in {path}")
            for problem in why:
                print(f"  {problem}")
        if project is not None and project.work is not None:
            w = project.work
            print(f"work: records in {w.status}, plans in {w.plans}, levels {' > '.join(w.levels)}, ladder {' > '.join(w.ladder)}, aside {', '.join(w.aside)}, trunk {w.main}"
                  + "".join(f", {k} {getattr(w, k)}" for k in ("index", "roadmap") if getattr(w, k) is not None))
        if project is not None and project.file is not None:
            print(f"project {project.name} is declared in {project.file}, which is " + (("trusted" if configuration.file_recorded(project.file) else "trusted through trusted_repositories, as it is committed at HEAD") if project.trusted
                                                                                     else "not trusted, so it gives knowledge alone and runs nothing. A person runs vyd trust in a terminal, in that repository, or lists the repository's origin in trusted_repositories and commits the file"))
        return 1 if config.set_aside or config.files_aside else 0
    except ConfigError as error:
        print(f"the configuration at {config_path()} cannot be used:", file=sys.stderr)
        for problem in error.problems:
            print(f"  {problem}", file=sys.stderr)
        return 2
    except (RegisterError, DeclarationError) as error:
        print("the registers cannot be read:", file=sys.stderr)
        for problem in error.problems:
            print(f"  {problem}", file=sys.stderr)
        return 2
    except Unresolved as error:
        print(f"unresolved: {error}", file=sys.stderr)
        return 1


def run() -> None:
    """The ``vyd`` console script."""
    sys.exit(streams.guarded(main))


if __name__ == "__main__":
    run()
