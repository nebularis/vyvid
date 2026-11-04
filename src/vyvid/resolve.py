# SPDX-License-Identifier: MIT
"""Which project a folder belongs to, the layers of rules that apply there, and what an identifier names.

A folder belongs to the project whose code or documents folder holds it, the deepest such folder
winning, and otherwise to the project whose remote its git repository has. The layers are the
general scope, then the domains the project uses with all their ancestors, parents before children,
then the project, so a later layer overrides an earlier one. A folder no project claims gets the
general scope alone.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import replace
from pathlib import Path

from .config import Config, Family, Scope
from .model import normalise

QUALIFIED_RE = re.compile(r"^(?P<scope>[a-z][a-z0-9-]*):(?P<local>.+)$")


class Unresolved(Exception):
    """An identifier names nothing the configuration knows, or names more than one thing."""


def normalise_remote(url: str) -> str:
    """A remote URL as host/owner/repository, lower case: no scheme, no user, no .git."""
    url = re.sub(r"^[a-z+]+://", "", url.strip())
    url = re.sub(r"^[^@/]+@", "", url)
    url = re.sub(r"^([^/:]+):(?!\d)", r"\1/", url)
    return re.sub(r"(\.git)?/*$", "", url).lower()


def remotes(folder: Path) -> list[str]:
    """The normalised remote URLs of the git repository holding ``folder``, if any."""
    found = subprocess.run(
        ["git", "-C", str(folder), "config", "--get-regexp", r"^remote\..*\.url$"],
        capture_output=True, text=True,
    )
    return [normalise_remote(line.split(None, 1)[1]) for line in found.stdout.splitlines() if " " in line]


def bind(config: Config, folder: Path) -> Scope | None:
    """The project a folder belongs to, by the deepest code or documents folder holding it, then by the
    git repository it shares with a project's code folder, so a worktree may be anywhere, then by remote."""
    folder = folder.expanduser().resolve()
    best, depth = None, -1
    for project in config.projects.values():
        for root in (project.code, project.docs):
            if root is None:
                continue
            root = root.resolve()
            if (folder == root or root in folder.parents) and len(root.parts) > depth:
                best, depth = project, len(root.parts)
    if best is not None:
        return best
    common = _common(folder) if folder.exists() else None
    if common is not None:
        for project in config.projects.values():
            if project.code is not None and project.code.exists() and _common(project.code.resolve()) == common:
                return project
    found = set(remotes(folder)) if folder.exists() else set()
    for project in config.projects.values():
        if found & {normalise_remote(r) for r in project.remotes}:
            return project
    return None


def _git(folder: Path, *args: str) -> str | None:
    done = subprocess.run(["git", "-C", str(folder), *args], capture_output=True, text=True)
    return done.stdout.strip() if done.returncode == 0 and done.stdout.strip() else None


def _common(folder: Path) -> Path | None:
    out = _git(folder, "rev-parse", "--git-common-dir")
    return (folder / out).resolve() if out else None


def checkout_of(project: Scope, folder: Path) -> Path | None:
    """The root of the linked checkout of the project that holds ``folder``, else None.

    It is a checkout when its git root is not the code folder and it shares the code folder's git common
    directory, or, with a code folder that is missing or no repository, a normalised remote. A different
    repository nested in the code folder, a folder outside git, and a code folder that is only part of a
    repository keep the project as configured."""
    folder = folder.expanduser().resolve()
    top = _git(folder, "rev-parse", "--show-toplevel") if folder.exists() else None
    if top is None or project.code is None:
        return None
    root, code = Path(top).resolve(), project.code.resolve()
    if root == code:
        return None
    code_top = _git(code, "rev-parse", "--show-toplevel") if code.exists() else None
    if code_top is None:
        return root if set(remotes(root)) & {normalise_remote(r) for r in project.remotes} else None
    return root if Path(code_top).resolve() == code and _common(root) == _common(code) else None


def rebase(config: Config, project: Scope, root: Path) -> Config:
    """``config`` with ``project`` answered from the checkout at ``root``: its code folder, and every
    path it holds inside the code folder, moved there. A documents folder outside the code folder stays."""
    old = project.code

    def move(path: Path | None) -> Path | None:
        try:
            return root / path.relative_to(old) if path is not None else None
        except ValueError:
            return path

    def family(f: Family) -> Family:
        return replace(f, defined=move(f.defined), also=tuple(move(p) for p in f.also))

    moved = replace(
        project, code=root, docs=move(project.docs), checkout=root,
        rules=[move(p) for p in project.rules], skills=[move(p) for p in project.skills],
        facets=[move(p) for p in project.facets], register_types=[move(p) for p in project.register_types],
        vocabulary=[move(p) for p in project.vocabulary], specialises={k: move(p) for k, p in project.specialises.items()},
        families={k: family(f) for k, f in project.families.items()})
    return replace(config, projects={**config.projects, project.name: moved})


def bind_in(config: Config, folder: Path) -> tuple[Config, Scope | None]:
    """The configuration to answer ``folder`` from and its project: ``bind``, with the project rebased
    onto the folder's checkout when it is a linked one. Binding the result again changes nothing."""
    project = bind(config, folder)
    if project is not None and (root := checkout_of(project, folder)) is not None:
        config = rebase(config, project, root)
        project = config.projects[project.name]
    return config, project


def layers(config: Config, project: Scope | None) -> list[Scope]:
    """General, then every domain the project uses and their ancestors, parents first, then the project.

    Of two domains with no order between them, the one named first in the project comes first, so the
    order is the same on every run."""
    if project is None:
        return [config.general]
    return [config.general, *(config.domains[n] for n in config.domain_order(project)), project]


def resolve(config: Config, mention: str, scope: Scope) -> str:
    """The canonical ``scope:LOCAL`` an identifier names, written in ``scope``.

    A qualified mention names its own scope. A bare one means the scope it is written in, through a
    family that scope declares, or one it delegates to another scope. A mention no family matches,
    or more than one does, is refused rather than guessed."""
    if (q := QUALIFIED_RE.match(mention)) is not None:
        target = config.scope(q.group("scope"))
        if target is None:
            raise Unresolved(f"'{mention}' names the scope '{q.group('scope')}', which is not configured")
        return _within(config, q.group("local"), target, seen=set())
    return _within(config, mention, scope, seen=set())


def _within(config: Config, local: str, scope: Scope, seen: set[str]) -> str:
    if scope.name in seen:
        raise Unresolved(f"'{local}' is delegated in a circle through '{scope.name}'")
    seen.add(scope.name)
    own = [f for f in scope.families.values() if f.pattern.fullmatch(local)]
    delegated = []
    for family, target in scope.delegates.items():
        other = config.scope(target)
        if other is not None and family in other.families and other.families[family].pattern.fullmatch(local):
            delegated.append(other)
    if len(own) + len(delegated) > 1:
        names = [f.name for f in own] + [f"{o.name} by delegation" for o in delegated]
        raise Unresolved(f"'{local}' in '{scope.name}' matches more than one family: {', '.join(names)}")
    if own:
        return f"{scope.name}:{local}"
    if delegated:
        return _within(config, local, delegated[0], seen)
    raise Unresolved(f"'{local}' matches no family of '{scope.name}'")


def visible_families(config: Config, scope: Scope) -> list:
    """The families a bare mention in ``scope`` can mean: its own and the ones it delegates."""
    out = list(scope.families.values())
    for family, target in scope.delegates.items():
        other = config.scope(target)
        if other is not None and family in other.families:
            out.append(other.families[family])
    return out


def mentions(config: Config, text: str, scope: Scope) -> list[str]:
    """Every identifier written in ``text``, as canonical ``scope:LOCAL``, once each, in order.

    A qualified mention names a configured scope, ``other:STD-1``, and a bare one matches a family
    ``scope`` declares or delegates. A mention that resolves to nothing, or to more than one thing,
    is skipped here, never raised, since a cell of prose may hold text that only looks like one.
    Two spellings of one identifier count once, under the first."""
    found: list[tuple[int, int, str]] = []
    qualified: list[tuple[int, int]] = []
    for target in [config.general, *config.domains.values(), *config.projects.values()]:
        for family in visible_families(config, target):
            qualified_form = family.pattern.derive(lambda p: rf"(?<![\w-]){re.escape(target.name)}:(?:{p})(?![\w-])")
            for m in qualified_form.finditer(text):
                found.append((m.start(), m.end(), m.group(0)))
                qualified.append((m.start(), m.end()))
    for family in visible_families(config, scope):
        for m in family.pattern.derive(lambda p: rf"(?<![\w-])(?:{p})(?![\w-])").finditer(text):
            if not any(a <= m.start() and m.end() <= b for a, b in qualified):
                found.append((m.start(), m.end(), m.group(0)))
    out: dict[tuple[str, str], str] = {}
    for _, _, mention in sorted(found):
        try:
            canonical = resolve(config, mention, scope)
        except Unresolved:
            continue
        name, local = canonical.split(":", 1)
        out.setdefault((name, normalise(local)), canonical)
    return list(out.values())
