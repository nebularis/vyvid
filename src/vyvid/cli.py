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
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .config import ConfigError, config_path, load
from .facets import RegisterError
from .registers import DeclarationError
from .resolve import Unresolved, bind, layers, resolve


def _layer(scope) -> dict:
    out = {"scope": scope.name, "kind": scope.kind}
    for key in ("rules", "skills"):
        out[key] = [{"path": str(p), "exists": p.exists()} for p in getattr(scope, key)]
    if scope.kind == "project":
        out["code"] = str(scope.code)
        out["docs"] = str(scope.docs)
        out["specialises"] = {d: {"path": str(p), "exists": p.exists()} for d, p in scope.specialises.items()}
    return out


def context(folder: Path, as_json: bool) -> int:
    config = load()
    project = bind(config, folder)
    stack = [_layer(s) for s in layers(config, project)]
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
