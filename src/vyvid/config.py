# SPDX-License-Identifier: MIT
"""The configuration: the general scope, the domains and their graph, the projects, and each scope's
identifier families.

One TOML file, found at ``$VYVID_CONFIG`` or in the platform's user configuration folder. A path in
it may start with a token: ``kb:`` the knowledge base, ``code:`` a project's code folder, ``docs:``
a project's documents folder, or ``~``. A configuration that names something it does not define, or
whose domains form a cycle, is refused with every problem listed, never loaded in part.
"""

from __future__ import annotations

import os
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

import platformdirs

from .embed import ModelSpec

NAME_RE = re.compile(r"^[a-z][a-z0-9-]*$")
FAMILY_RE = re.compile(r"^[A-Za-z#][A-Za-z0-9#]*$")


class ConfigError(Exception):
    """The configuration cannot be used, with every reason found."""

    def __init__(self, problems: list[str]):
        super().__init__("\n".join(problems))
        self.problems = problems


@dataclass(frozen=True)
class Family:
    """An identifier family of one scope: how its local identifiers are written, and where defined."""

    name: str
    pattern: re.Pattern[str]
    defined: str | None = None


@dataclass
class Scope:
    """A layer of rules: the general scope, a domain or a project."""

    name: str
    kind: str  # general, domain or project
    rules: list[Path] = field(default_factory=list)
    skills: list[Path] = field(default_factory=list)
    facets: list[Path] = field(default_factory=list)
    families: dict[str, Family] = field(default_factory=dict)
    delegates: dict[str, str] = field(default_factory=dict)
    parents: list[str] = field(default_factory=list)  # domains only
    path: Path | None = None
    # projects only
    code: Path | None = None
    docs: Path | None = None
    remotes: list[str] = field(default_factory=list)
    domains: list[str] = field(default_factory=list)
    specialises: dict[str, Path] = field(default_factory=dict)


@dataclass
class Config:
    source: Path | None
    kb: Path | None
    general: Scope
    domains: dict[str, Scope]
    projects: dict[str, Scope]
    embedding: ModelSpec = field(default_factory=ModelSpec)

    def scope(self, name: str) -> Scope | None:
        if name == self.general.name:
            return self.general
        return self.domains.get(name) or self.projects.get(name)


def config_path() -> Path:
    """Where the configuration is read from: ``$VYVID_CONFIG``, or the platform's folder for it."""
    if env := os.environ.get("VYVID_CONFIG"):
        return Path(env).expanduser()
    return platformdirs.user_config_path("vyvid") / "config.toml"


def _expand(value: str, bases: dict[str, Path | None], where: str, problems: list[str]) -> Path | None:
    for token, base in bases.items():
        if value.startswith(token + ":"):
            if base is None:
                problems.append(f"{where}: '{value}' needs '{token}', which is not set")
                return None
            return (base / value[len(token) + 1 :]).expanduser()
    return Path(value).expanduser()


def _families(raw: dict, where: str, problems: list[str]) -> dict[str, Family]:
    out = {}
    for name, spec in (raw or {}).items():
        spec = spec if isinstance(spec, dict) else {}
        if not FAMILY_RE.match(name):
            problems.append(f"{where}: family '{name}' is not a family name")
            continue
        pattern = spec.get("pattern", rf"{re.escape(name)}-\d+[a-z]?")
        try:
            out[name] = Family(name, re.compile(pattern), spec.get("defined"))
        except re.error as error:
            problems.append(f"{where}: family '{name}' has a pattern that does not compile: {error}")
    return out


def _paths(values, bases, where, problems) -> list[Path]:
    values = [values] if isinstance(values, str) else (values or [])
    return [p for v in values if (p := _expand(v, bases, where, problems)) is not None]


def load(path: Path | None = None) -> Config:
    """The configuration at ``path``, or at ``config_path()``. A missing file is an empty
    configuration with only the general scope, so an unconfigured machine still answers."""
    path = path or config_path()
    raw = tomllib.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    problems: list[str] = []
    framework = raw.get("framework", {})
    kb = Path(framework["kb"]).expanduser() if "kb" in framework else None

    g = raw.get("general", {})
    general = Scope(
        "general", "general",
        rules=_paths(g.get("rules"), {"kb": kb}, "[general]", problems),
        skills=_paths(g.get("skills"), {"kb": kb}, "[general]", problems),
        facets=_paths(g.get("facets"), {"kb": kb}, "[general]", problems),
        families=_families(g.get("families"), "[general]", problems),
    )

    domains: dict[str, Scope] = {}
    for d in raw.get("domains", []):
        name = d.get("name", "")
        where = f"domain '{name}'"
        if not NAME_RE.match(name) or name in domains or name == "general":
            problems.append(f"{where}: a domain needs a unique lower-case name")
            continue
        root = _expand(d.get("path", f"kb:domains/{name}"), {"kb": kb}, where, problems)
        bases = {"kb": kb, "self": root}
        domains[name] = Scope(
            name, "domain", path=root, parents=list(d.get("parents", [])),
            rules=_paths(d.get("rules", "self:rules.md"), bases, where, problems),
            skills=_paths(d.get("skills", "self:skills"), bases, where, problems),
            facets=_paths(d.get("facets", "self:facets.md"), bases, where, problems),
            families=_families(d.get("families"), where, problems),
            delegates=dict(d.get("delegates", {})),
        )

    projects: dict[str, Scope] = {}
    for p in raw.get("projects", []):
        name = p.get("name", "")
        where = f"project '{name}'"
        if not NAME_RE.match(name) or name in projects or name in domains or name == "general":
            problems.append(f"{where}: a project needs a unique lower-case name, distinct from every domain")
            continue
        if "code" not in p:
            problems.append(f"{where}: a project needs a code folder")
            continue
        code = Path(p["code"]).expanduser()
        docs = _expand(p.get("docs", "code:docs"), {"code": code, "kb": kb}, where, problems)
        bases = {"code": code, "docs": docs, "kb": kb}
        match = p.get("match", {})
        remotes = match.get("remote", [])
        projects[name] = Scope(
            name, "project", code=code, docs=docs,
            remotes=[remotes] if isinstance(remotes, str) else list(remotes),
            domains=list(p.get("domains", [])),
            rules=_paths(p.get("contract"), bases, where, problems),
            skills=_paths(p.get("skills"), bases, where, problems),
            facets=_paths(p.get("facets"), bases, where, problems),
            families=_families(p.get("families"), where, problems),
            delegates=dict(p.get("delegates", {})),
            specialises={k: v for k, s in p.get("specialises", {}).items()
                         if (v := _expand(s, bases, where, problems)) is not None},
        )

    config = Config(path if path.exists() else None, kb, general, domains, projects, _embedding(raw.get("embedding", {}), problems))
    problems += _check(config)
    if problems:
        raise ConfigError(problems)
    return config


def _embedding(raw: dict, problems: list[str]) -> ModelSpec:
    """The ``[embedding]`` table as a model spec. A model other than the default must be pinned by
    its revision and the SHA-256 of each file, since an unpinned model can change under the vectors."""
    if not raw:
        return ModelSpec()
    known = {"model", "revision", "files", "query_prefix", "weak", "near", "facet_boost", "cache"}
    if unknown := sorted(set(raw) - known):
        problems.append(f"[embedding]: unknown keys {', '.join(unknown)}")
    default = ModelSpec()
    if raw.get("model", default.repo) != default.repo and not (raw.get("revision") and raw.get("files")):
        problems.append("[embedding]: a model other than the default needs its revision and the SHA-256 of each file")
    kwargs = {k: raw[k] for k in ("revision", "files", "query_prefix", "weak", "near", "facet_boost") if k in raw}
    if "model" in raw:
        kwargs["repo"] = raw["model"]
    if "cache" in raw:
        kwargs["cache"] = Path(raw["cache"]).expanduser()
    return ModelSpec(**kwargs)


def _check(config: Config) -> list[str]:
    """Every reference names something defined, and the domains form a directed acyclic graph."""
    problems = []
    for d in config.domains.values():
        problems += [f"domain '{d.name}': parent '{p}' is no domain" for p in d.parents if p not in config.domains]
    for p in config.projects.values():
        problems += [f"project '{p.name}': domain '{d}' is not configured" for d in p.domains if d not in config.domains]
        problems += [f"project '{p.name}': specialises '{d}', which it does not use" for d in p.specialises if d not in p.domains]
    for s in [config.general, *config.domains.values(), *config.projects.values()]:
        for family, target in s.delegates.items():
            other = config.scope(target)
            if other is None:
                problems.append(f"{s.kind} '{s.name}': delegates '{family}' to '{target}', which is no scope")
            elif family not in other.families:
                problems.append(f"{s.kind} '{s.name}': delegates '{family}' to '{target}', which declares no such family")
            if family in s.families:
                problems.append(f"{s.kind} '{s.name}': both declares and delegates '{family}'")
    # A cycle among domains is refused: depth-first, colouring each domain as it is entered and left.
    state: dict[str, int] = {}

    def visit(name: str, trail: list[str]) -> None:
        if state.get(name) == 2 or name not in config.domains:
            return
        if state.get(name) == 1:
            problems.append("domains form a cycle: " + " -> ".join(trail[trail.index(name):] + [name]))
            return
        state[name] = 1
        for parent in config.domains[name].parents:
            visit(parent, trail + [name])
        state[name] = 2

    for name in sorted(config.domains):
        visit(name, [])
    return problems
