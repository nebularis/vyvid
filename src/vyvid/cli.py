# SPDX-License-Identifier: MIT
"""``vyd``, the command line.

``vyd context [folder] [--json]``
    the contract that applies in a folder: each layer's rules and skills, general first and the
    project last, which an agent reads before its first task
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

Each question takes ``--in <folder>``, the folder whose stack it is asked in, the current one by default.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__, ask
from .config import ConfigError, config_path, extractor_runs, load
from .facets import RegisterError
from .registers import DeclarationError
from .resolve import Unresolved, bind, layers, resolve


QUESTIONS = ("find", "read", "node", "reaches", "exists", "sparql", "misses", "gap", "close")


def _layer(config, scope) -> dict:
    out = {"scope": scope.name, "kind": scope.kind}
    for key in ("rules", "skills"):
        out[key] = [{"path": str(p), "exists": p.exists()} for p in getattr(scope, key)]
    if scope.kind == "domain":
        out["brings"] = [e["kind"] for e in scope.extractors]
    if scope.kind == "project":
        out["runs"] = [{"kind": r.kind, "domain": r.domain, "settings": {k: [str(p) for p in v] if k == "paths" else v for k, v in r.settings.items()},
                        "sources": r.sources} for r in extractor_runs(config, scope)]
        out["code"] = str(scope.code)
        out["docs"] = str(scope.docs)
        out["specialises"] = {d: {"path": str(p), "exists": p.exists()} for d, p in scope.specialises.items()}
    return out


def context(folder: Path, as_json: bool) -> int:
    config = load()
    project = bind(config, folder)
    stack = [_layer(config, s) for s in layers(config, project)]
    if as_json:
        print(json.dumps({"folder": str(folder.resolve()), "project": project and project.name, "layers": stack}, indent=2))
        return 0
    print(f"Вивід {__version__}: the contract for {folder.resolve()}")
    print(f"project: {project.name if project else 'none, so the general scope alone'}")
    print("Read each layer's rules in this order. A later layer overrides an earlier one, and the project's is last.\n")
    for n, layer in enumerate(stack, 1):
        print(f"{n}. {layer['scope']}" if layer["kind"] == layer["scope"] else f"{n}. {layer['kind']} {layer['scope']}")
        for key in ("rules", "skills"):
            for item in layer[key]:
                print(f"   {key[:-1]:<5} {item['path']}" + ("" if item["exists"] else "   (missing)"))
        for kind in layer.get("brings", []):
            print(f"   brings extractor {kind}")
        for run in layer.get("runs", []):
            print(f"   runs extractor {run['kind']}" + (f" of domain {run['domain']}" if run["domain"] else ""))
            for key, value in run["settings"].items():
                print(f"      {key} = {value}   ({run['sources'][key]})")
        for domain, item in layer.get("specialises", {}).items():
            print(f"   specialises {domain} in {item['path']}" + ("" if item["exists"] else "   (missing)"))
    return 0


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


def _question(arguments, parser) -> int:
    """Run one of the questions in ``ask`` for the stack of the folder named by ``--in``."""
    config = load()
    command = arguments.command
    folder = Path(arguments.folder)
    if command in ("gap", "close"):
        a = ask.open_stack(config, folder, need_store=False)
        return ask.gap(a, arguments.text, arguments.extras) if command == "gap" else ask.close(a, arguments.ids)
    a = ask.open_stack(config, folder)
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
    r = sub.add_parser("resolve", help="the canonical scope:LOCAL an identifier names")
    r.add_argument("identifier")
    r.add_argument("--in", dest="folder", default=".")
    b = sub.add_parser("build", help="build the knowledge index for a folder's project, or for every scope")
    b.add_argument("folder", nargs="?", default=".")
    b.add_argument("--all", action="store_true", help="every configured scope, not the folder's stack")
    b.add_argument("--no-embed", action="store_true", help="build the store and write no vectors")
    sub.add_parser("config", help="where the configuration is read from, and whether it is sound")
    _questions(sub)
    arguments = parser.parse_args(argv)
    try:
        if arguments.command == "context":
            return context(Path(arguments.folder), arguments.json)
        if arguments.command == "resolve":
            config = load()
            scope = bind(config, Path(arguments.folder)) or config.general
            print(resolve(config, arguments.identifier, scope))
            return 0
        if arguments.command == "build":
            return build_index(Path(arguments.folder), arguments.all, not arguments.no_embed)
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
