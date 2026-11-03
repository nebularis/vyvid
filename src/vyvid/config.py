# SPDX-License-Identifier: MIT
"""The configuration: the general scope, the domains and their graph, the projects, and each scope's
identifier families.

One TOML file, found at ``$VYVID_CONFIG`` or in the platform's user configuration folder. A path in
it may start with a token: ``kb:`` the knowledge base, ``code:`` a project's code folder, ``docs:``
a project's documents folder, ``self:`` a domain's own folder, or ``~``. A configuration that names
something it does not define, or whose domains form a cycle, is refused with every problem listed,
never loaded in part.

A domain is a folder, and its ``domain.toml`` may declare what the configuration's entry for it
declares. A key the configuration sets replaces the manifest's, so a user can override a domain
locally. A domain brings extractors by kind, and each project that uses the domain runs them over
its own files (``extractor_runs``).
"""

from __future__ import annotations

import glob
import os
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

import platformdirs

from . import extractors
from .embed import ModelSpec

NAME_RE = re.compile(r"^[a-z][a-z0-9-]*$")
FAMILY_RE = re.compile(r"^[A-Za-z#][A-Za-z0-9#]*$")
# How a family's identifiers are defined: a table row of a register, a file named by the identifier,
# a heading that opens with it, or a bold lead or table row of a plan or sketch that raises a question.
RULES = ("table", "file", "heading", "question")
# The keys a domain may declare, in its manifest or in the configuration.
DOMAIN_KEYS = {"parents", "families", "delegates", "facets", "register_types", "rules", "skills", "vocabulary", "extractors"}


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
    defined: Path | None = None  # a file, a folder of Markdown files, or a glob
    type: str | None = None  # the register type of the register that defines it
    rule: str = "table"  # one of RULES
    also: tuple[Path, ...] = ()  # more places it is defined, after ``defined``

    def paths(self) -> list[Path]:
        """The files that define this family, in the order they were named. A glob is expanded and a
        folder stands for its Markdown files, each sorted, so a plan's definition comes before a sketch's."""
        found: list[Path] = []
        for place in [self.defined, *self.also]:
            if place is None:
                continue
            if glob.has_magic(str(place)):
                names = sorted(glob.glob(str(place), recursive=True), key=Path)
            elif place.is_dir():
                names = sorted(map(str, place.glob("*.md")), key=Path)
            else:
                names = [str(place)]
            found += [p for n in names if (p := Path(n)).is_file() and p not in found]
        return found


@dataclass
class Scope:
    """A layer of rules: the general scope, a domain or a project."""

    name: str
    kind: str  # general, domain or project
    rules: list[Path] = field(default_factory=list)
    skills: list[Path] = field(default_factory=list)
    facets: list[Path] = field(default_factory=list)
    register_types: list[Path] = field(default_factory=list)
    families: dict[str, Family] = field(default_factory=dict)
    delegates: dict[str, str] = field(default_factory=dict)
    parents: list[str] = field(default_factory=list)  # domains only
    path: Path | None = None
    vocabulary: list[Path] = field(default_factory=list)  # Turtle, loaded into the T-Box graph
    # Each a kind and its settings, ``paths`` unexpanded. A domain's are the kinds it brings and their
    # defaults, a project's the extractors it declares itself.
    extractors: list[dict] = field(default_factory=list)
    # projects only
    uses: dict[str, dict[str, dict]] = field(default_factory=dict)  # domain -> kind -> the project's settings
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
    store: Path | None = None  # where the index is built, else the platform's data folder

    def scope(self, name: str) -> Scope | None:
        if name == self.general.name:
            return self.general
        return self.domains.get(name) or self.projects.get(name)

    def domain_order(self, project: Scope) -> list[str]:
        """The domains a project uses and their ancestors, parents first.

        Of two domains with no order between them, the one named first in the project comes first, so
        the order is the same on every run. The graph must be acyclic, as ``load`` ensures."""
        ordered: list[str] = []

        def visit(name: str) -> None:
            if name in ordered:
                return
            for parent in self.domains[name].parents:
                visit(parent)
            ordered.append(name)

        for name in project.domains:
            visit(name)
        return ordered


@dataclass(frozen=True)
class Run:
    """One extractor run for a project: the kind, its settings with ``paths`` expanded to a list, the
    domain that brings it (None for the project's own), and where each setting came from."""

    kind: str
    settings: dict
    domain: str | None
    sources: dict[str, str]


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


def _families(raw: dict, where: str, problems: list[str], bases: dict[str, Path | None] | None = None) -> dict[str, Family]:
    out = {}
    for name, spec in (raw or {}).items():
        spec = spec if isinstance(spec, dict) else {}
        if not FAMILY_RE.match(name):
            problems.append(f"{where}: family '{name}' is not a family name")
            continue
        pattern = spec.get("pattern", rf"{re.escape(name)}-\d+[a-z]?")
        rule = spec.get("rule", "table")
        if rule not in RULES:
            problems.append(f"{where}: family '{name}' has the rule '{rule}', not one of {', '.join(RULES)}")
            continue
        try:
            places = _paths(spec.get("defined"), bases or {}, where, problems)
            out[name] = Family(name, re.compile(pattern), places[0] if places else None, spec.get("type"), rule, tuple(places[1:]))
        except re.error as error:
            problems.append(f"{where}: family '{name}' has a pattern that does not compile: {error}")
    return out


def _paths(values, bases, where, problems) -> list[Path]:
    values = [values] if isinstance(values, str) else (values or [])
    return [p for v in values if (p := _expand(v, bases, where, problems)) is not None]


def _extractors(raw, where, problems) -> list[dict]:
    """Each extractor as ``{"kind": ..., "settings": {...}}``, its kind installed."""
    out = []
    for item in raw or []:
        if item.get("kind") not in extractors.kinds():
            problems.append(f"{where}: an extractor needs an installed kind of {', '.join(extractors.kinds()) or 'none installed'}, not '{item.get('kind')}'")
        else:
            out.append({"kind": item["kind"], "settings": {k: v for k, v in item.items() if k != "kind"}})
    return out


def _manifest(root: Path | None, name: str, where: str, problems: list[str]) -> dict:
    """A domain's ``domain.toml``. A missing one is no error, since the configuration may say it all."""
    if root is None or not (root / "domain.toml").is_file():
        return {}
    try:
        manifest = tomllib.loads((root / "domain.toml").read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as error:
        problems.append(f"{where}: domain.toml does not parse ({error})")
        return {}
    if manifest.get("name", name) != name:
        problems.append(f"{where}: domain.toml names the domain '{manifest['name']}'")
    return {k: v for k, v in manifest.items() if k != "name"}


def extractor_runs(config: Config, project: Scope) -> list[Run]:
    """The extractors a project runs, in order: each the domains of its stack bring, parents first,
    then its own. A domain's settings are its defaults updated by the project's
    ``[projects.uses.<domain>.<kind>]``. An extractor left with no ``paths`` has nothing to read and
    is skipped. Raises ConfigError for a ``uses`` that names a domain outside the project's stack or
    a kind the domain does not bring."""
    problems: list[str] = []
    where = f"project '{project.name}'"
    bases = {"code": project.code, "docs": project.docs, "kb": config.kb}
    order = config.domain_order(project)
    runs: list[Run] = []
    for domain, kinds in project.uses.items():
        if domain not in order:
            problems.append(f"{where}: uses '{domain}', which is not in its stack of domains")
        else:
            problems += [f"{where}: uses {domain}.{k}, and {domain} brings no such extractor"
                         for k in kinds if k not in {e["kind"] for e in config.domains[domain].extractors}]

    def run(kind: str, settings: dict, sources: dict[str, str], domain: str | None, self_path: Path | None) -> None:
        # A path comes from the domain's defaults, which may start with self:, or from the project.
        mine = {**bases, "self": self_path} if sources.get("paths", "").startswith("domain") else bases
        paths = _paths(settings.get("paths"), mine, where, problems)
        if paths:
            runs.append(Run(kind, {**settings, "paths": paths}, domain, sources))

    for domain in order:
        for brought in config.domains[domain].extractors:
            kind = brought["kind"]
            settings = dict(brought["settings"])
            sources = {k: f"domain '{domain}'" for k in settings}
            for key, value in project.uses.get(domain, {}).get(kind, {}).items():
                settings[key], sources[key] = value, f"project '{project.name}', uses.{domain}.{kind}"
            run(kind, settings, sources, domain, config.domains[domain].path)
    for own in project.extractors:
        run(own["kind"], dict(own["settings"]), {k: f"project '{project.name}', extractors" for k in own["settings"]}, None, None)
    if problems:
        raise ConfigError(problems)
    return runs


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
        register_types=_paths(g.get("register_types"), {"kb": kb}, "[general]", problems),
        vocabulary=_paths(g.get("vocabulary"), {"kb": kb}, "[general]", problems),
        families=_families(g.get("families"), "[general]", problems, {"kb": kb}),
    )

    domains: dict[str, Scope] = {}
    for d in raw.get("domains", []):
        name = d.get("name", "")
        where = f"domain '{name}'"
        if not NAME_RE.match(name) or name in domains or name == "general":
            problems.append(f"{where}: a domain needs a unique lower-case name")
            continue
        root = _expand(d.get("path", f"kb:domains/{name}"), {"kb": kb}, where, problems)
        # The configuration's keys replace the manifest's, so a user can override a domain locally.
        merged = {**_manifest(root, name, where, problems), **{k: v for k, v in d.items() if k not in ("name", "path")}}
        if unknown := sorted(set(merged) - DOMAIN_KEYS):
            problems.append(f"{where}: unknown keys {', '.join(unknown)}")
        bases = {"kb": kb, "self": root}
        domains[name] = Scope(
            name, "domain", path=root, parents=list(merged.get("parents", [])),
            rules=_paths(merged.get("rules", "self:rules.md"), bases, where, problems),
            skills=_paths(merged.get("skills", "self:skills"), bases, where, problems),
            facets=_paths(merged.get("facets", "self:facets.md"), bases, where, problems),
            register_types=_paths(merged.get("register_types", "self:register-types.toml"), bases, where, problems),
            vocabulary=_paths(merged.get("vocabulary"), bases, where, problems),
            families=_families(merged.get("families"), where, problems, bases),
            delegates=dict(merged.get("delegates", {})),
            extractors=_extractors(merged.get("extractors"), where, problems),
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
            register_types=_paths(p.get("register_types"), bases, where, problems),
            vocabulary=_paths(p.get("vocabulary"), bases, where, problems),
            families=_families(p.get("families"), where, problems, bases),
            delegates=dict(p.get("delegates", {})),
            extractors=_extractors(p.get("extractors"), where, problems),
            uses={d: {k: dict(v) for k, v in kinds.items()} for d, kinds in p.get("uses", {}).items()},
            specialises={k: v for k, s in p.get("specialises", {}).items()
                         if (v := _expand(s, bases, where, problems)) is not None},
        )

    config = Config(path if path.exists() else None, kb, general, domains, projects, _embedding(raw.get("embedding", {}), problems),
                    Path(framework["store"]).expanduser() if "store" in framework else None)
    problems += _check(config)
    if not problems:  # the stacks are only walked once the graph is known to be acyclic
        for project in projects.values():
            try:
                extractor_runs(config, project)
            except ConfigError as error:
                problems += error.problems
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
