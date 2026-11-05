# SPDX-License-Identifier: MIT
"""``vyd board``, ``vyd work`` and ``vyd here``: the work board on the command line.

The commands read the project's ``work`` settings. A command that writes a file refuses when the project is
declared by a vyvid.toml nobody has trusted, since that file comes from whoever wrote the repository.
"""

from __future__ import annotations

import datetime
import os
import subprocess
import sys
from pathlib import Path

from .. import board as one_checkout
from ..config import Config, Scope
from . import core, migrate
from .settings import Work


def settings(project: Scope | None) -> Work | None:
    return project.work if project is not None else None


def open_repo(project: Scope) -> core.Repo:
    """The repository holding the project's status records, with the registers its families of type
    ``pending-decision`` and ``debt`` define and the exceptions baseline its identifiers name."""
    registers: dict[str, list[Path]] = {}
    for family in project.families.values():
        if family.type in ("pending-decision", "debt") and family.defined is not None and family.defined.is_file():
            registers.setdefault(family.type, []).append(family.defined)
    baselines = [p for p in (project.identifiers.exceptions, *(f.exceptions for f in project.families.values())) if p is not None]
    return core.Repo.open(project.work, registers=registers, exceptions=list(dict.fromkeys(baselines)))


def fetch(repo: core.Repo) -> None:
    subprocess.run(["git", "fetch", "--all", "--prune", "--quiet"], cwd=repo.root, capture_output=True, env={**os.environ, "GIT_TERMINAL_PROMPT": "0"})


def refuse_untrusted(project: Scope) -> bool:
    if project.trusted:
        return False
    print(f"project {project.name} is declared by a vyvid.toml nobody has trusted, so this command writes nothing. A person runs vyd trust in a terminal, in that repository, after reading it", file=sys.stderr)
    return True


def board(config: Config, project: Scope | None, arguments) -> int:
    """``vyd board``: the work board across every branch where the project declares ``work``, else, or with
    ``--here``, the slices of its families of type slice in the one checkout."""
    work = settings(project)
    if arguments.here or work is None:
        if work is None and (arguments.all or arguments.fetch or arguments.measure or arguments.commits):
            print("this project declares no work settings, so the board is read from the one checkout", file=sys.stderr)
        return one_checkout.command(config, project, arguments.state)
    try:
        repo = open_repo(project)
        if arguments.fetch:
            fetch(repo)
        sys.stdout.write(repo.board_text(arguments.all, arguments.measure, arguments.commits, arguments.state))
    except core.NotARepository as error:
        print(f"{error}, so only vyd board --here can read it", file=sys.stderr)
        return 2
    return 0


def require(project: Scope | None) -> Work | None:
    if project is None or project.work is None:
        print("this folder's project declares no work settings. Add a [project.work] table to its vyvid.toml or entry", file=sys.stderr)
        return None
    return project.work


def work(config: Config, project: Scope | None, arguments) -> int:
    command = arguments.work_command
    if command == "parse":
        rules = core.Rules(settings(project) or Work(status=Path("."), plans=Path(".")))
        unit = rules.parse_unit(arguments.record.stem, arguments.record.read_text(encoding="utf-8"))
        if not unit.board:
            print(f"{arguments.record}: no board. Unit state {unit.state or '?'} {unit.day}".strip())
            return 0
        print("\n".join(core.table((rules.piece, "State", "Day", "Trail", "Blocked on"),
                                   ((r.id, r.state or "?", r.day, ", ".join(f"{s} {d}".strip() for s, d in r.trail), r.blocked_on)
                                    for r in unit.board.rows))))
        return 0
    if require(project) is None:
        return 2
    writes = {"build": not getattr(arguments, "check", True), "roadmap": not getattr(arguments, "check", True), "rename": getattr(arguments, "apply", False),
              "normalise": getattr(arguments, "apply", False), "adopt": getattr(arguments, "apply", False)}.get(command, False)
    if writes and refuse_untrusted(project):
        return 1
    try:
        repo = open_repo(project)
        if command == "build":
            return repo.build(arguments.check)
        if command == "roadmap":
            if arguments.fetch:
                fetch(repo)
            return repo.build_roadmap(arguments.check)
        if command == "check":
            touched = None
            if arguments.staged:
                touched = [p for p in repo.git("diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z").split("\0") if p]
            return repo.check(touched)
        lines = {"rename": lambda: migrate.rename(repo, arguments.apply), "normalise": lambda: migrate.normalise(repo, arguments.apply),
                 "adopt": lambda: migrate.adopt(repo, arguments.apply) + migrate.regroup_exceptions(repo, arguments.apply)}[command]()
        print("\n".join(lines))
        return 0
    except core.NotARepository as error:
        print(error, file=sys.stderr)
        return 2
    except PermissionError as error:
        print(error, file=sys.stderr)
        return 1


def here(config: Config, project: Scope | None, arguments) -> int:
    """``vyd here``: write this session's presence in the checkout, or list the live sessions, or leave."""
    if require(project) is None:
        return 2
    try:
        repo = open_repo(project)
        directory = repo.presence_dir()
        if arguments.role or arguments.leave:
            if refuse_untrusted(project):
                return 1
            if project.work.presence and not repo.writable(directory):
                print(f"{directory} is outside the repository or inside its git directory, so nothing is written", file=sys.stderr)
                return 1
        session, client = core.session_from_environment(dict(os.environ))
        now = datetime.datetime.fromisoformat(arguments.now) if arguments.now else datetime.datetime.now(datetime.timezone.utc)
        if now.tzinfo is None:
            now = now.replace(tzinfo=datetime.timezone.utc)
        if arguments.leave:
            print("left" if core.leave_presence(directory, session) else "no presence to leave")
            return 0
        if arguments.role:
            core.write_presence(directory, session, client, arguments.model, arguments.role,
                                [s.strip() for s in arguments.on.split(",") if s.strip()], now.strftime("%Y-%m-%dT%H:%M:%SZ"))
        sys.stdout.write(core.presence_text(core.list_presence(directory, now.timestamp()), session, project.work.commands["here"]))
        return 0
    except core.NotARepository as error:
        print(error, file=sys.stderr)
        return 2
