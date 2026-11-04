# SPDX-License-Identifier: MIT
"""``vyd``, the command line.

``vyd context [folder] [--json] [--no-pull]``
    the contract that applies in a folder: each layer's rules and skills, general first and the
    project last, which an agent reads before its first task. It first pulls the managed domains of
    the folder's stack that are due, and prints a line for each pull that failed
``vyd resolve <identifier> [--in folder]``
    the canonical ``scope:LOCAL`` an identifier names, written in that folder's project
``vyd config``
    where the configuration is read from, and whether it is sound
``vyd build [folder] [--all] [--no-embed]``
    build the knowledge index for the folder's project stack, or for every scope, and print what it
    found and every problem
``vyd find <words> | read <id> | node <id> | reaches <id> | exists <text> | sparql <query>``
    ask the index of the folder's stack a question, rebuilding it first when a file it reads changed
``vyd misses | gap <text> | close <id>``
    the questions the index answered weakly, the gaps found by reading, and closing them
``vyd check citations [--staged] [paths ...] [--in folder]``
    refuse the lines a public project adds, staged or in the paths, that cite an entry of a private scope
``vyd recipe list [--in folder]`` and ``vyd recipe run <name> "<question>" [--in folder] [--all] [--json]``
    the named chains of queries the folder's stack declares, and one run as a briefing within its budget
``vyd install --client claude-code [--target folder] [--dry-run]``
    write the client's user-level rule file and one skill per configured domain

``vyd kb status | clone [domain ...] | pull [domain ...] [--due] | record <path> ... -m <message>``
    the domains under the knowledge base, each a git clone of its remote, kept by its git policy

Each question takes ``--in <folder>``, the folder whose stack it is asked in, the current one by default,
and ``--scope a,b`` to add scopes to that stack or ``--scope only:a,b`` to read those alone.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from . import __version__, ask, citations, install, kb, recipes
from .config import ConfigError, config_path, extractor_runs, load
from .facets import RegisterError
from .registers import DeclarationError
from .resolve import Unresolved, bind, layers, resolve


QUESTIONS = ("find", "read", "node", "reaches", "exists", "sparql", "misses", "gap", "close")


def _layer(config, scope) -> dict:
    out = {"scope": scope.name, "kind": scope.kind, "visibility": scope.visibility}
    for key in ("rules", "skills"):
        out[key] = [{"path": str(p), "exists": p.exists()} for p in getattr(scope, key)]
    out["recipes"] = [{"name": r.name, "description": r.description} for r in scope.recipes]
    if scope.kind == "domain":
        out["brings"] = [e["kind"] for e in scope.extractors]
    if scope.kind == "project":
        out["runs"] = [{"kind": r.kind, "domain": r.domain, "settings": {k: [str(p) for p in v] if k == "paths" else v for k, v in r.settings.items()},
                        "sources": r.sources} for r in extractor_runs(config, scope)]
        out["code"] = str(scope.code)
        out["docs"] = str(scope.docs)
        out["specialises"] = {d: {"path": str(p), "exists": p.exists()} for d, p in scope.specialises.items()}
    return out


def context(folder: Path, as_json: bool, pull: bool = True) -> int:
    config = load()
    project = bind(config, folder)
    if pull:
        for result in kb.pull_due(config, layers(config, project)):
            if not result.ok:
                print(f"vyd: pull of {result.name} failed: {result.text}", file=sys.stderr)
    stack = [_layer(config, s) for s in layers(config, project)]
    if as_json:
        print(json.dumps({"folder": str(folder.resolve()), "project": project and project.name, "layers": stack}, indent=2))
        return 0
    print(f"Вивід {__version__}: the contract for {folder.resolve()}")
    print(f"project: {project.name if project else 'none, so the general scope alone'}")
    print("Read each layer's rules in this order. A later layer overrides an earlier one, and the project's is last.\n")
    for n, layer in enumerate(stack, 1):
        print((f"{n}. {layer['scope']}" if layer["kind"] == layer["scope"] else f"{n}. {layer['kind']} {layer['scope']}") + f" ({layer['visibility']})")
        for key in ("rules", "skills"):
            for item in layer[key]:
                print(f"   {key[:-1]:<5} {item['path']}" + ("" if item["exists"] else "   (missing)"))
        for recipe in layer["recipes"]:
            print(f"   recipe {recipe['name']}  {recipe['description']}")
        for kind in layer.get("brings", []):
            print(f"   brings extractor {kind}")
        for run in layer.get("runs", []):
            print(f"   runs extractor {run['kind']}" + (f" of domain {run['domain']}" if run["domain"] else ""))
            for key, value in run["settings"].items():
                print(f"      {key} = {value}   ({run['sources'][key]})")
        for domain, item in layer.get("specialises", {}).items():
            print(f"   specialises {domain} in {item['path']}" + ("" if item["exists"] else "   (missing)"))
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
        print(f"   policy pull={s.policy.pull} commit={s.policy.commit} push={s.policy.push}")
    return 0


def kb_command(arguments) -> int:
    config = load()
    action = arguments.kb_command
    if action == "status":
        return kb_status(config)
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


def build_index(folder: Path, everything: bool, embed: bool) -> int:
    from .build import build, store_dir

    config = load()
    project = bind(config, folder)
    if not everything and project is None:
        print("no project claims this folder, so the general scope alone is built. Use --all for every scope")
    out = build(config, None if everything else project, embed=embed, scopes=None if everything or project else [config.general])
    for key in sorted(out.counts):
        print(f"  {key:<28} {out.counts[key]}")
    for problem in out.problems:
        print(f"NOTE: {problem}")
    for finding in out.findings:
        print(f"FINDING: {finding}")
    print(f"knowledge index built at {store_dir(config) / 'store'}")
    return 0


def check_citations(arguments) -> int:
    """Refuse the lines a public project adds that cite an entry of a private scope."""
    config = load()
    project = bind(config, Path(arguments.folder))
    if project is None:
        print("no project claims this folder, so there is no public text to check")
        return 0
    if project.visibility != "public":
        print(f"project {project.name} is private, so its text may cite any entry")
        return 0
    if not arguments.staged and not arguments.paths:
        print("vyd: name the paths to check, or use --staged", file=sys.stderr)
        return 2
    try:
        lines = citations.staged_lines(project) if arguments.staged else citations.file_lines([Path(p) for p in arguments.paths])
    except citations.GitError as error:
        print(f"vyd: {error}", file=sys.stderr)
        return 2
    refused = citations.private_citations(config, project, lines)
    for line in refused:
        print(line)
    if not refused:
        print(f"{len(lines)} line(s) checked, and none cites an entry of a private scope")
    return 1 if refused else 0


def recipe_command(arguments, parser) -> int:
    """List the recipes of the folder's stack, or run one as a briefing."""
    config = load()
    folder = Path(arguments.folder)
    stack = layers(config, bind(config, folder))
    found = recipes.available(stack)
    if arguments.recipe_command == "list":
        if found:
            ask.show([{"name": r.name, "scope": r.scope, "description": r.description} for r in found.values()], ("name", "scope", "description"))
        else:
            print("no recipe is declared in this folder's stack")
        return 0
    recipe = found.get(arguments.name)
    if recipe is None:
        print(f"vyd: no recipe '{arguments.name}' in this folder's stack, which has {', '.join(found) or 'none'}", file=sys.stderr)
        return 1
    try:
        a = ask.open_stack(config, folder, scope=recipes.extra_scopes(recipe))
        entries = recipes.run(a, recipe, arguments.question)
    except ValueError as error:
        parser.error(str(error))
    except recipes.RecipeError as error:
        print(f"vyd: recipe {recipe.name}: {error}", file=sys.stderr)
        return 1
    text, size, dropped = recipes.briefing(recipe, arguments.question, entries, arguments.all)
    if arguments.json:
        shown = entries[: len(entries) - dropped]
        print(json.dumps({"recipe": recipe.name, "scope": recipe.scope, "question": arguments.question, "budget": recipe.budget,
                          "estimated_tokens": size, "dropped": dropped, "entries": shown}, indent=2, ensure_ascii=False))
    else:
        print(text)
        print(f"\n(about {size} tokens)")
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
        a = ask.open_stack(config, folder, scope=getattr(arguments, "scope", ""))
    except ValueError as error:
        parser.error(str(error))
    if command == "misses":
        return ask.misses(a, arguments.limit, arguments.near, again=True)
    if command == "find":
        try:
            chosen = ask.filters(a, arguments.kind, arguments.exclude, arguments.phase, arguments.audience,
                                 activity=arguments.activity, quality=arguments.quality, tech=arguments.tech)
        except ValueError as error:
            parser.error(str(error))
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
        return p

    p = asking("find", "entries ranked by how close their meaning is to your words")
    p.add_argument("words", nargs="+")
    p.add_argument("--kind", default="", help="comma-separated kinds the stack declares. Declared ontology terms are searched only when term is named")
    p.add_argument("--exclude", default="", help="comma-separated kinds to leave out and keep every other, such as question")
    p.add_argument("--phase", default="", help="comma-separated phases")
    p.add_argument("--audience", default="", help="comma-separated audiences")
    for flag, (scheme, _) in ask.FACET_FLAGS.items():
        p.add_argument(f"--{flag}", default="", help=f"comma-separated values of the {scheme} facet, which raise matching entries and hide none")
    p.add_argument("--limit", type=int, default=8)
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="vyd", description="Вивід: the contract and knowledge for the folder an agent is in")
    parser.add_argument("--version", action="version", version=f"Вивід (vyvid) {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)
    c = sub.add_parser("context", help="the contract that applies in a folder, general first and the project last")
    c.add_argument("folder", nargs="?", default=".")
    c.add_argument("--json", action="store_true")
    c.add_argument("--no-pull", action="store_true", help="do not pull the managed domains that are due first")
    k = sub.add_parser("kb", help="the managed domains under the knowledge base: status, clone, pull and record").add_subparsers(dest="kb_command", required=True)
    k.add_parser("status", help="each managed domain's clone, branch, ahead and behind, changes, last pull and policy")
    k.add_parser("clone", help="clone the named domains, or every managed domain whose folder is missing").add_argument("domains", nargs="*")
    p = k.add_parser("pull", help="git pull --ff-only in the named domains, or all of them")
    p.add_argument("domains", nargs="*")
    p.add_argument("--due", action="store_true", help="only the domains whose pull policy says one is due")
    p = k.add_parser("record", help="stage changed paths in their managed domain, then commit and push by its policy")
    p.add_argument("paths", nargs="+")
    p.add_argument("-m", "--message", required=True)
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
    p.add_argument("--staged", action="store_true", help="the lines staged in the project's code and documents repositories")
    p.add_argument("--in", dest="folder", default=".", help="the folder whose project is checked")
    p = sub.add_parser("recipe", help="the named chains of queries of a folder's stack").add_subparsers(dest="recipe_command", required=True)
    p.add_parser("list", help="each recipe of the stack, its scope and when to use it").add_argument("--in", dest="folder", default=".")
    r = p.add_parser("run", help="run one recipe for a question and print its briefing")
    r.add_argument("name")
    r.add_argument("question")
    r.add_argument("--in", dest="folder", default=".", help="the folder whose stack the recipe is read from")
    r.add_argument("--all", action="store_true", help="every entry, ignoring the recipe's budget")
    r.add_argument("--json", action="store_true")
    i = sub.add_parser("install", help="write a client's user-level rule file and one skill per configured domain")
    i.add_argument("--client", required=True, choices=sorted(install.CLIENTS))
    i.add_argument("--target", type=Path, help="the folder to write into, instead of the client's own")
    i.add_argument("--dry-run", action="store_true", help="say what would be written and write nothing")
    sub.add_parser("config", help="where the configuration is read from, and whether it is sound")
    _questions(sub)
    arguments = parser.parse_args(argv)
    try:
        if arguments.command == "context":
            return context(Path(arguments.folder), arguments.json, not arguments.no_pull)
        if arguments.command == "kb":
            return kb_command(arguments)
        if arguments.command == "resolve":
            config = load()
            scope = bind(config, Path(arguments.folder)) or config.general
            print(resolve(config, arguments.identifier, scope))
            return 0
        if arguments.command == "build":
            return build_index(Path(arguments.folder), arguments.all, not arguments.no_embed)
        if arguments.command == "check":
            return check_citations(arguments)
        if arguments.command == "recipe":
            return recipe_command(arguments, parser)
        if arguments.command == "install":
            return install.install(load(), arguments.client, arguments.target, arguments.dry_run)
        if arguments.command in QUESTIONS:
            return _question(arguments, parser)
        config = load()
        print(f"configuration: {config.source or config_path()}" + ("" if config.source else " (absent, so the general scope alone)"))
        print(f"domains: {', '.join(config.domains) or 'none'}")
        print(f"projects: {', '.join(config.projects) or 'none'}")
        return 0
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
