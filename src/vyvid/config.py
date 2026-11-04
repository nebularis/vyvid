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

A manifest comes from whoever wrote the domain, so it is held to its folder. Every path it names must
stay inside the folder after symlinks are resolved, and it may not set ``git`` or ``remote``. The same
keys in the user's configuration are the user's own and stay free. A file under a domain's folder that
is a symlink leaving it is never read (``escapes``).
"""

from __future__ import annotations

import glob
import os
import re
import signal
import subprocess
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

import platformdirs
import regex

from . import extractors
from .embed import ModelSpec
from .patterns import SECONDS as PATTERN_SECONDS, Pattern

NAME_RE = re.compile(r"^[a-z][a-z0-9-]*$")
FAMILY_RE = re.compile(r"^[A-Za-z#][A-Za-z0-9#]*$")
# How a family's identifiers are defined: a table row of a register, a file named by the identifier,
# a heading that opens with it, or a bold lead or table row of a plan or sketch that raises a question.
RULES = ("table", "file", "heading", "question")
# The keys a domain may declare, in its manifest or in the configuration.
DOMAIN_KEYS = {"description", "visibility", "parents", "families", "delegates", "facets", "register_types", "rules", "skills", "vocabulary", "extractors", "remote", "git", "recipes"}
# Whether a scope's entries may be cited in a public project's text. A domain is private until its author says otherwise.
VISIBILITIES = ("public", "private")
# What a manifest may not set, since only the user decides where a domain comes from and how it is kept.
MANIFEST_REFUSED = ("git", "remote")
# The keys of a manifest whose value is a path or a list of them.
MANIFEST_PATHS = ("rules", "skills", "facets", "register_types", "vocabulary")
# What each key of a managed domain's git policy may be, the first being the default.
GIT_CHOICES = {"pull": ("on-start", "daily", "manual"), "commit": ("manual", "auto"), "push": ("manual", "auto")}
# The edges a recipe's linked step may follow, which the index stores between entries.
LINK_EDGES = ("supports", "refines", "decidedBy", "evidencedBy", "enforcedBy", "dependsOn", "waitsOn",
              "distinguishedFrom", "bearsOn", "answers", "supersededBy")
DIRECTIONS = ("out", "in", "both")
FILTER_KEYS = ("kind", "exclude", "activity", "quality", "tech", "phase", "audience", "scope")
# The steps of a recipe, each with the keys it requires and the keys it may also take.
STEPS = {
    "find": (("words",), (*FILTER_KEYS, "limit")),
    "linked": (("edges",), ("direction",)),
    "include": (("ids",), ()),
    "take": (("n",), ("per_kind",)),
    "glue": (("command",), ("seconds", "env")),
}
EXPECTS = {"words": "a string", "limit": "a whole number above zero", "n": "a whole number above zero",
           "edges": f"a list of {', '.join(LINK_EDGES)}", "ids": "a list of identifiers", "command": "a non-empty list of strings", "code": "a list of strings", "env": "a list of variable names",
           "direction": f"one of {', '.join(DIRECTIONS)}", "per_kind": "true or false", "seconds": "a number of seconds above zero",
           **dict.fromkeys(FILTER_KEYS, "a string or a list of strings")}
DEFAULT_BUDGET = 1000
GLUE_CHOICES = ("run", "stop")
# What only a project's own entry may set on an extractor, which makes it run as a command.
COMMAND_KEYS = ("command", "code", "seconds", "env")
# The variables glue and a command extractor are given, by exact name. A prefix would let in MISE_GITHUB_TOKEN,
# so none is matched, and SSH_AUTH_SOCK and VIRTUAL_ENV are left out on purpose.
GLUE_ENV = frozenset((
    "PATH", "HOME", "USER", "LOGNAME", "LANG", "LC_ALL", "LC_CTYPE", "TZ", "TMPDIR", "TEMP", "TMP", "TERM",
    "SYSTEMROOT", "WINDIR", "COMSPEC", "PATHEXT", "USERPROFILE", "HOMEDRIVE", "HOMEPATH", "APPDATA", "LOCALAPPDATA",
    "PROGRAMDATA", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME", "XDG_STATE_HOME"))


class ConfigError(Exception):
    """The configuration cannot be used, with every reason found."""

    def __init__(self, problems: list[str]):
        super().__init__("\n".join(problems))
        self.problems = problems


@dataclass(frozen=True)
class GitPolicy:
    """When Вивід pulls, commits and pushes a managed domain. The defaults change nothing unasked."""

    pull: str = "on-start"
    commit: str = "manual"
    push: str = "manual"


@dataclass(frozen=True)
class Family:
    """An identifier family of one scope: how its local identifiers are written, and where defined."""

    name: str
    pattern: Pattern
    defined: Path | None = None  # a file, a folder of Markdown files, or a glob
    type: str | None = None  # the register type of the register that defines it
    rule: str = "table"  # one of RULES
    also: tuple[Path, ...] = ()  # more places it is defined, after ``defined``
    root: Path | None = None  # the folder of the domain that declares it, whose links may not leave it

    def paths(self) -> list[Path]:
        """The files that define this family, minus any that escape its domain's folder (``refused``)."""
        return [p for p in self._listed() if not escapes(p, self.root)]

    def refused(self) -> list[Path]:
        """The files that define this family and are links leaving its domain's folder."""
        return [p for p in self._listed() if escapes(p, self.root)]

    def _listed(self) -> list[Path]:
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


@dataclass(frozen=True)
class Recipe:
    """A named chain of steps that narrows an answer to the work, declared by a domain or a project.
    Each step is a table with a ``step`` key, its values checked at load. The budget is in tokens."""

    name: str
    description: str
    steps: tuple[dict, ...]
    budget: int = DEFAULT_BUDGET
    scope: str = ""  # the scope that declares it, in which its identifiers are resolved


@dataclass
class Scope:
    """A layer of rules: the general scope, a domain or a project."""

    name: str
    kind: str  # general, domain or project
    visibility: str = "public"  # one of VISIBILITIES
    rules: list[Path] = field(default_factory=list)
    skills: list[Path] = field(default_factory=list)
    facets: list[Path] = field(default_factory=list)
    register_types: list[Path] = field(default_factory=list)
    families: dict[str, Family] = field(default_factory=dict)
    delegates: dict[str, str] = field(default_factory=dict)
    parents: list[str] = field(default_factory=list)  # domains only
    description: str = ""  # domains only: when to use the domain, for the skill generated from it
    recipes: list[Recipe] = field(default_factory=list)
    remote: str | None = None  # domains only: the repository a managed domain is a clone of
    git: GitPolicy = field(default_factory=GitPolicy)  # domains only
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
    checkout: Path | None = None  # set by ``resolve.rebase``: the linked checkout this project is answered from

    def readable(self, files: list[Path]) -> list[Path]:
        """The files that may be read, which leaves out any that escape this domain's folder."""
        return [p for p in files if not escapes(p, self.path if self.kind == "domain" else None)]

    def refused(self) -> list[Path]:
        """Every file this domain reads that is a link leaving its folder, once each."""
        if self.kind != "domain":
            return []
        named = [*self.rules, *self.skills, *self.facets, *self.register_types, *self.vocabulary]
        return [*(p for p in named if escapes(p, self.path)), *(p for f in self.families.values() for p in f.refused())]


@dataclass
class Config:
    source: Path | None
    kb: Path | None
    general: Scope
    domains: dict[str, Scope]
    projects: dict[str, Scope]
    embedding: ModelSpec = field(default_factory=ModelSpec)
    store: Path | None = None  # where the index is built, else the platform's data folder
    commit_trailers: tuple[str, ...] = ()  # appended to every message ``vyd kb record`` commits
    glue: str = "run"  # ``stop`` means vyd never runs glue itself, one of GLUE_CHOICES

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


def run_limited(command: list[str], request: str, folder: Path, env: dict[str, str], seconds: float) -> subprocess.CompletedProcess:
    """Run a command in a session of its own, so a time limit also stops what it started, such as the
    program a wrapper like ``mise exec`` runs. Raises ``subprocess.TimeoutExpired`` at the limit."""
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                               errors="replace", cwd=folder, env=env, start_new_session=True)
    try:
        out, err = process.communicate(request, timeout=seconds)
    except subprocess.TimeoutExpired:
        # ponytail: on Windows only the direct child is stopped, to be settled when the suite runs there.
        if hasattr(os, "killpg"):
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        process.kill()
        process.wait()
        raise
    return subprocess.CompletedProcess(command, process.returncode, out, err)


def glue_env(step: dict) -> dict[str, str]:
    """The environment glue or a command extractor is given: GLUE_ENV and the variables ``env`` names, those that are set."""
    allowed = GLUE_ENV | set(step.get("env", ()))
    return {k: v for k, v in os.environ.items() if k in allowed}


def config_path() -> Path:
    """Where the configuration is read from: ``$VYVID_CONFIG``, or the platform's folder for it."""
    if env := os.environ.get("VYVID_CONFIG"):
        return Path(env).expanduser()
    return platformdirs.user_config_path("vyvid") / "config.toml"


def escapes(path: Path, root: Path | None) -> bool:
    """Whether ``path``, written under ``root``, resolves through a symlink to somewhere outside it. A
    path written elsewhere is the user's own choice, so it never escapes."""
    if root is None:
        return False
    written, base = Path(os.path.abspath(path)), Path(os.path.abspath(root))
    return written.is_relative_to(base) and not written.resolve().is_relative_to(base.resolve())


def refusals(scopes: list[Scope]) -> list[str]:
    """A line for each file of a domain that is a link leaving its folder, and so is not read."""
    return [f"{s.name}: {p} is a link that leaves the domain's folder, so it is not read" for s in scopes for p in s.refused()]


def timeouts(scopes: list[Scope]) -> list[str]:
    """A line for each family whose pattern ran out of time in this run, and so matched nothing after."""
    return [f"{s.name}: family {f.name} has a pattern that ran past {PATTERN_SECONDS} seconds, so the family is disabled for this run"
            for s in scopes for f in s.families.values() if f.pattern.timed_out]


def _inside(value: str, root: Path) -> bool:
    """Whether a manifest's path stays in the domain's folder: relative or ``self:``, with no other
    token, no ``~``, and not leaving through ``..`` or a symlink."""
    rest = value.removeprefix("self:").replace("\\", "/")
    if rest.startswith(("~", "/")) or re.match(r"[A-Za-z][\w-]*:", rest):
        return False
    return Path(os.path.realpath(root / rest)).is_relative_to(Path(os.path.realpath(root)))


def leaving(manifest: dict, root: Path) -> list[tuple[str, str]]:
    """The key and value of each path in a manifest that leaves the domain's folder."""
    found: list[tuple[str, str]] = []

    def check(key: str, values) -> None:
        for v in [values] if isinstance(values, str) else values if isinstance(values, list) else []:
            if isinstance(v, str) and not _inside(v, root):
                found.append((key, v))

    for key in MANIFEST_PATHS:
        check(key, manifest.get(key))
    families = manifest.get("families")
    for name, spec in (families.items() if isinstance(families, dict) else []):
        for key in ("defined", "also"):
            check(f"families.{name}.{key}", spec.get(key) if isinstance(spec, dict) else None)
    for item in manifest.get("extractors") if isinstance(manifest.get("extractors"), list) else []:
        check("extractors.paths", item.get("paths") if isinstance(item, dict) else None)
    return found


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
            out[name] = Family(name, Pattern(pattern), places[0] if places else None, spec.get("type"), rule, tuple(places[1:]), (bases or {}).get("self"))
        except (regex.error, TypeError) as error:
            problems.append(f"{where}: family '{name}' has a pattern that does not compile: {error}")
    return out


def _visibility(raw: dict, default: str, where: str, problems: list[str]) -> str:
    value = raw.get("visibility", default)
    if value not in VISIBILITIES:
        problems.append(f"{where}: visibility is '{value}', not one of {', '.join(VISIBILITIES)}")
        return default
    return value


def _paths(values, bases, where, problems) -> list[Path]:
    values = [values] if isinstance(values, str) else (values or [])
    return [p for v in values if (p := _expand(v, bases, where, problems)) is not None]


def _extractors(raw, where, problems, own=False) -> list[dict]:
    """Each extractor as ``{"kind": ..., "settings": {...}}``. Its kind is installed, unless a project's
    own entry gives a ``command``, which only such an entry may, with the keys of COMMAND_KEYS."""
    out = []
    for item in raw or []:
        kind, given = item.get("kind"), [k for k in COMMAND_KEYS if k in item]
        if given and not own:
            problems.append(f"{where}: an extractor sets {', '.join(given)}, which only a project's own entry in the user's configuration may")
        elif given and "command" not in item:
            problems.append(f"{where}: extractor '{kind}' sets {', '.join(given)} without a command")
        elif "command" in item:
            before = len(problems)
            if not isinstance(kind, str) or not NAME_RE.match(kind):
                problems.append(f"{where}: a command extractor needs a lower-case kind")
            settings = {k: v for k, v in item.items() if k != "kind"}
            for key in given:
                try:
                    settings[key] = _step_value(key, [item[key]] if key == "code" and isinstance(item[key], str) else item[key])
                except ValueError as error:
                    problems.append(f"{where}, extractor '{kind}': {error}")
            if len(problems) == before:
                out.append({"kind": kind, "settings": settings})
        elif kind not in extractors.kinds():
            problems.append(f"{where}: an extractor needs an installed kind of {', '.join(extractors.kinds()) or 'none installed'}, not '{kind}'")
        else:
            out.append({"kind": kind, "settings": {k: v for k, v in item.items() if k != "kind"}})
    return out


def _git_policy(raw, where: str, problems: list[str]) -> GitPolicy:
    """A domain's ``git`` table as a policy. An unknown key or value, or a push with nothing committed to push, is a problem."""
    if not isinstance(raw, dict):
        if raw is not None:
            problems.append(f"{where}: git must be a table")
        return GitPolicy()
    if unknown := sorted(set(raw) - set(GIT_CHOICES)):
        problems.append(f"{where}: unknown git keys {', '.join(unknown)}")
    for key, choices in GIT_CHOICES.items():
        if raw.get(key, choices[0]) not in choices:
            problems.append(f"{where}: git.{key} is '{raw[key]}', not one of {', '.join(choices)}")
    policy = GitPolicy(**{k: raw[k] for k in GIT_CHOICES if raw.get(k) in GIT_CHOICES[k]})
    if policy.push == "auto" and policy.commit == "manual":
        problems.append(f"{where}: git.push is auto and git.commit is manual, so nothing would be pushed")
    return policy


def _step_value(key: str, value):
    """The value a step key takes as a recipe stores it. Raises ValueError for one it cannot take."""
    strings = isinstance(value, list) and bool(value) and all(isinstance(v, str) for v in value)
    whole = isinstance(value, int) and not isinstance(value, bool) and value > 0
    if (key in FILTER_KEYS or key == "words") and isinstance(value, str):
        return value
    if key in FILTER_KEYS and strings:
        return ",".join(value)
    if key in ("limit", "n") and whole:
        return value
    if key in ("edges", "ids", "command", "env", "code") and strings and (key != "edges" or set(value) <= set(LINK_EDGES)):
        return list(value)
    if key == "seconds" and isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0:
        return value
    if (key == "direction" and value in DIRECTIONS) or (key == "per_kind" and isinstance(value, bool)):
        return value
    raise ValueError(f"'{key}' must be {EXPECTS[key]}")


def _step(raw, where: str, problems: list[str]) -> dict | None:
    if not isinstance(raw, dict) or raw.get("step") not in STEPS:
        problems.append(f"{where}: a step needs a 'step' of {', '.join(STEPS)}")
        return None
    name = raw["step"]
    required, optional = STEPS[name]
    here = f"{where}, step '{name}'"
    before = len(problems)
    problems += [f"{here}: needs '{k}'" for k in required if k not in raw]
    if unknown := sorted(set(raw) - {"step", *required, *optional}):
        problems.append(f"{here}: unknown keys {', '.join(unknown)}")
    out = {"step": name}
    for key in [k for k in raw if k in (*required, *optional)]:
        try:
            out[key] = _step_value(key, raw[key])
        except ValueError as error:
            problems.append(f"{here}: {error}")
    return out if len(problems) == before else None


def _recipes(raw, scope: str, kind: str, where: str, problems: list[str]) -> list[Recipe]:
    """The recipes a domain or a project declares. A domain's may run no code, so a glue step in one is
    a problem, since a cloned domain must not execute anything."""
    if raw is None:
        return []
    if not isinstance(raw, list) or not all(isinstance(r, dict) for r in raw):
        problems.append(f"{where}: recipes must be an array of tables")
        return []
    out: list[Recipe] = []
    for item in raw:
        name = item.get("name", "")
        here = f"{where}: recipe '{name}'"
        if not isinstance(name, str) or not NAME_RE.match(name) or any(r.name == name for r in out):
            problems.append(f"{where}: a recipe needs a unique lower-case name, not '{name}'")
            continue
        if unknown := sorted(set(item) - {"name", "description", "steps", "budget"}):
            problems.append(f"{here}: unknown keys {', '.join(unknown)}")
        description, budget, steps = item.get("description"), item.get("budget", DEFAULT_BUDGET), item.get("steps")
        if not isinstance(description, str) or not description.strip():
            problems.append(f"{here}: needs a description, saying when to use it")
        if not isinstance(budget, int) or isinstance(budget, bool) or budget < 1:
            problems.append(f"{here}: budget must be a whole number of tokens above zero")
        if not isinstance(steps, list) or not steps:
            problems.append(f"{here}: needs a list of steps")
            continue
        parsed = [_step(s, here, problems) for s in steps]
        if kind != "project" and any(isinstance(s, dict) and s.get("step") == "glue" for s in steps):
            problems.append(f"{here}: has a glue step, and a cloned domain runs no code. Only a project's recipe may")
        if all(parsed) and isinstance(description, str) and isinstance(budget, int):
            out.append(Recipe(name, description.strip(), tuple(parsed), budget, scope))
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
    problems += [f"{where}: domain.toml sets '{k}', which only the user's configuration may" for k in MANIFEST_REFUSED if k in manifest]
    problems += [f"{where}: domain.toml {key} names '{value}', which leaves the domain's folder" for key, value in leaving(manifest, root)]
    return {k: v for k, v in manifest.items() if k not in ("name", *MANIFEST_REFUSED)}


def extractor_runs(config: Config, project: Scope) -> list[Run]:
    """The extractors a project runs, in order: each the domains of its stack bring, parents first,
    then its own. A domain's settings are its defaults updated by the project's
    ``[projects.uses.<domain>.<kind>]``. An installed extractor left with no ``paths`` has nothing to
    read and is skipped, and a command always runs, since it decides what it reads. Raises ConfigError for a ``uses`` that names a domain outside the project's stack or
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
            problems += [f"{where}: uses {domain}.{k} sets {key}, which a domain's extractor may not run as"
                         for k, settings in kinds.items() for key in COMMAND_KEYS if key in settings]

    def run(kind: str, settings: dict, sources: dict[str, str], domain: str | None, self_path: Path | None) -> None:
        # A path comes from the domain's defaults, which may start with self:, or from the project.
        mine = {**bases, "self": self_path} if sources.get("paths", "").startswith("domain") else bases
        paths = _paths(settings.get("paths"), mine, where, problems)
        if paths or "command" in settings:
            code = {"code": _paths(settings["code"], mine, where, problems)} if "code" in settings else {}
            runs.append(Run(kind, {**settings, "paths": paths, **code}, domain, sources))

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
        "general", "general", _visibility(g, "public", "[general]", problems),
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
            name, "domain", _visibility(merged, "private", where, problems), path=root, parents=list(merged.get("parents", [])),
            description=" ".join(str(merged.get("description", "")).split()), recipes=_recipes(merged.get("recipes"), name, "domain", where, problems),
            remote=merged.get("remote"), git=_git_policy(merged.get("git"), where, problems),
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
            name, "project", _visibility(p, "public", where, problems), code=code, docs=docs,
            remotes=[remotes] if isinstance(remotes, str) else list(remotes),
            domains=list(p.get("domains", [])), recipes=_recipes(p.get("recipes"), name, "project", where, problems),
            rules=_paths(p.get("contract"), bases, where, problems),
            skills=_paths(p.get("skills"), bases, where, problems),
            facets=_paths(p.get("facets"), bases, where, problems),
            register_types=_paths(p.get("register_types"), bases, where, problems),
            vocabulary=_paths(p.get("vocabulary"), bases, where, problems),
            families=_families(p.get("families"), where, problems, bases),
            delegates=dict(p.get("delegates", {})),
            extractors=_extractors(p.get("extractors"), where, problems, own=True),
            uses={d: {k: dict(v) for k, v in kinds.items()} for d, kinds in p.get("uses", {}).items()},
            specialises={k: v for k, s in p.get("specialises", {}).items()
                         if (v := _expand(s, bases, where, problems)) is not None},
        )

    trailers = framework.get("commit_trailers", [])
    if not isinstance(trailers, list) or not all(isinstance(t, str) for t in trailers):
        problems.append("[framework]: commit_trailers must be a list of strings")
        trailers = []
    glue = framework.get("glue", "run")
    if glue not in GLUE_CHOICES:
        problems.append(f"[framework]: glue must be one of {', '.join(GLUE_CHOICES)}")
        glue = "run"
    config = Config(path if path.exists() else None, kb, general, domains, projects, _embedding(raw.get("embedding", {}), problems),
                    Path(framework["store"]).expanduser() if "store" in framework else None, tuple(trailers), glue)
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
