# SPDX-License-Identifier: MIT
# From LATTICE's tools/knowledge/quanta.py and extractor.py, relicensed MIT by its author.
"""Architectural quanta, derived from coupling in each view of the architecture, kind ``quanta``.

An architectural quantum is the smallest set that must change and be released together because of its coupling, so its
size is the lower bound on incremental change. It is derived, never declared, and separately in each view, because the same
module or component falls into different quanta in different views.

**Data view.** The modules of the core kind (``substrate`` unless ``core_kind`` says otherwise) form one dependency order and
one release, so they are one quantum. Any other module is its own, since its coupling to the core runs one way, unless
something in the core imports it, in which case the core's quantum grows to take it in. A release member left outside the
core's quantum shares its release number without being coupled to it, which is the release policy straddling a quantum
boundary. A module's imports are read from the ``owl:imports`` of the ontology documents under its folder.

**Software view.** Per deployment, from what each component's configuration points at in a compose file. Two components that
use one store share state and are one quantum. A component that names another application component is taken to call it
synchronously, which binds them too. A broker is a contract between components and never merges them, which is how
middleware draws a quantum boundary, but only when nothing else couples the two sides: a shared store defeats a broker.

The modules are the project's data, as ``[[project.extractors.modules]]`` tables with ``name``, ``path`` (inside the project),
``kind`` and ``release`` (whether it is released with the core). A project with a catalogue of its own can write them from it.
Because this is Вивід's own code, a project that reads another runs it over the read.
"""

from __future__ import annotations

import glob
import re
from dataclasses import dataclass, field
from pathlib import Path

import pyoxigraph as ox
import yaml

from ..model import RDF_TYPE, RDFS_LABEL, ki, normalise
from . import Context, Result

STORES = ("postgres", "fuseki", "jena", "mysql", "mariadb", "mongo", "redis", "oxigraph", "graphdb", "virtuoso")
BROKERS = ("rabbitmq", "kafka", "nats", "activemq", "pulsar")
COMPOSE = ("docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml")
OWL = "http://www.w3.org/2002/07/owl#"
CLAIM_LIMIT = 200
VIEW = {"data": "DataView", "software": "SoftwareView"}


@dataclass
class Quantum:
    identifier: str
    view: str
    parts: list[str]
    claim: str
    pointer: str
    deployment: str = ""


@dataclass
class _Union:
    parent: dict[str, str] = field(default_factory=dict)

    def find(self, item: str) -> str:
        self.parent.setdefault(item, item)
        while self.parent[item] != item:
            self.parent[item] = self.parent[self.parent[item]]
            item = self.parent[item]
        return item

    def join(self, a: str, b: str) -> None:
        self.parent[self.find(a)] = self.find(b)


def _fit(text: str) -> str:
    return text if len(text) <= CLAIM_LIMIT else text[: CLAIM_LIMIT - 1].rstrip(" ,") + "…"


def _listed(names: list[str]) -> str:
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]


def data_quanta(kinds: dict[str, str], imports: set[tuple[str, str]], release: set[str], pointers: dict[str, str],
                core: str = "substrate", core_pointer: str = "") -> tuple[list[Quantum], list[str]]:
    """The data view's quanta, and the release members the release policy places across a boundary.

    ``kinds`` maps a module to its kind, ``imports`` holds ``(importer, imported)`` pairs between modules, ``release`` the
    modules released together, ``pointers`` a document per module."""
    inside = {name for name, kind in kinds.items() if kind == core}
    grew = True
    while grew:
        grew = False
        for importer, imported in imports:
            if importer in inside and imported not in inside and imported in kinds:
                inside.add(imported)
                grew = True
    found = []
    if inside:
        found.append(Quantum(
            identifier=f"data/{core}", view="data", parts=sorted(inside),
            claim=_fit(f"The {core}'s {len(inside)} layers are one data quantum: one dependency order released as one, so a change to any of them is a release of all."),
            pointer=core_pointer or pointers.get(sorted(inside)[0], "")))
    for name in sorted(kinds):
        if name in inside:
            continue
        shared = f" It shares the {core}'s release number all the same." if name in release else ""
        found.append(Quantum(
            identifier=f"data/{name}", view="data", parts=[name],
            claim=_fit(f"{name} is its own data quantum, depending on the {core} one way, so it changes alone.{shared}"),
            pointer=pointers.get(name, "")))
    return found, sorted(release - inside)


def role(service: dict) -> str:
    """A component's part in coupling: a store shares state, a broker carries a contract."""
    image = str(service.get("image", "")).lower()
    if any(word in image for word in BROKERS):
        return "broker"
    if any(word in image for word in STORES):
        return "store"
    return "component"


def _environment(service: dict) -> list[str]:
    env = service.get("environment") or {}
    if isinstance(env, dict):
        return [str(v) for v in env.values() if v is not None]
    return [str(item).split("=", 1)[-1] for item in env]


def _depends(service: dict) -> list[str]:
    depends = service.get("depends_on") or []
    return list(depends) if isinstance(depends, (list, dict)) else []


def links(services: dict) -> dict[str, set[str]]:
    """What each component points at: its declared dependencies, and any other component whose name appears as a host in
    its configuration, which is how a store or a broker is usually reached."""
    found: dict[str, set[str]] = {}
    for name, service in services.items():
        service = service or {}
        targets = set(_depends(service))
        for value in _environment(service):
            for other in services:
                if other != name and re.search(rf"(?<![\w-]){re.escape(other)}(?![\w-])", value):
                    targets.add(other)
        found[name] = targets & set(services)
    return found


def software_quanta(deployment: str, compose: dict, pointer: str) -> list[Quantum]:
    """One deployment's quanta. A store or a synchronous call merges, a broker never does."""
    services = compose.get("services") or {}
    roles = {name: role(service or {}) for name, service in services.items()}
    linked = links(services)
    union = _Union()
    for name in services:
        if roles[name] != "broker":
            union.find(name)
    # ponytail: depends_on on another application component is read as a synchronous call, which over-merges where it only
    # orders start-up. Read the component's own configuration if it matters.
    for name, targets in linked.items():
        for target in targets:
            if "broker" in (roles[name], roles[target]):
                continue
            union.join(name, target)
    groups: dict[str, list[str]] = {}
    for name in services:
        if roles[name] != "broker":
            groups.setdefault(union.find(name), []).append(name)
    found = []
    for members in groups.values():
        members.sort()
        stores = [m for m in members if roles[m] == "store"]
        brokered = {m for m in members if any(roles[t] == "broker" for t in linked[m])}
        claim = f"In {deployment}, {_listed(members)} {'is its own quantum' if len(members) == 1 else 'form one quantum'}"
        if stores:
            claim += f", coupled through {_listed(stores)}"
        if len(brokered) > 1:
            claim += ", although a broker between them would otherwise separate them"
        components = [m for m in members if roles[m] == "component"] or members
        found.append(Quantum(identifier=f"software/{deployment}/{components[0]}", view="software", parts=members, claim=_fit(claim + "."),
                             pointer=pointer, deployment=deployment))
    return sorted(found, key=lambda q: q.identifier)


# ---- the extractor --------------------------------------------------------------------------------


def _modules(raw, root: Path, problems: list[str]) -> list[dict]:
    """The module tables, each with a name, a path inside the project, a kind and whether it is released with the core."""
    out: list[dict] = []
    if not isinstance(raw, list):
        problems.append("quanta: modules must be a list of tables with a name, a path, a kind and release")
        return out
    for item in raw:
        name, path = (item.get("name"), item.get("path")) if isinstance(item, dict) else (None, None)
        if not (isinstance(name, str) and name and isinstance(path, str) and path):
            problems.append(f"quanta: a module needs a name and a path, not {item!r}")
            continue
        folder = (root / path).resolve()
        if not folder.is_relative_to(root):
            problems.append(f"quanta: the module {name} names {path}, which leaves the project")
            continue
        out.append({"name": name, "path": folder.relative_to(root).as_posix(), "kind": str(item.get("kind", "applied")), "release": item.get("release") is True,
                    "readme": item.get("readme")})
    return out


def _imports(root: Path, files: list[Path], module_of) -> tuple[set[tuple[str, str]], list[str]]:
    """The imports between modules, read from every ontology document's ``owl:imports``, and the documents that do not parse."""
    declared: dict[str, str] = {}
    imports: list[tuple[str, str]] = []
    problems: list[str] = []
    for path in files:
        rel = path.resolve().relative_to(root).as_posix()
        try:
            triples = list(ox.parse(path=str(path), format=ox.RdfFormat.TURTLE))
        except (OSError, SyntaxError, ValueError) as error:
            problems.append(f"{rel} does not parse ({error.__class__.__name__}), so its imports are not read")
            continue
        for t in triples:
            if t.predicate == RDF_TYPE and t.object == ox.NamedNode(OWL + "Ontology"):
                declared[t.subject.value] = rel
            elif t.predicate == ox.NamedNode(OWL + "versionIRI"):
                declared[t.object.value] = rel
            elif t.predicate == ox.NamedNode(OWL + "imports"):
                imports.append((rel, t.object.value))
    edges = set()
    for rel, target in imports:
        importer, imported = module_of(rel), module_of(declared.get(target, ""))
        if importer and imported and importer != imported:
            edges.add((importer, imported))
    return edges, problems


def _whole(root: Path, rel: str) -> str:
    """A pointer at a whole file, as ``path:1-n``, or at a folder as given."""
    try:
        lines = (root / rel).read_text(encoding="utf-8").count("\n")
    except (OSError, UnicodeError):
        return rel
    return f"{rel}:1-{max(lines, 1)}"


def extract(context: Context, settings: dict) -> Result:
    result = Result()
    root = context.root.resolve()
    scope = context.scope.name
    graph = context.index_graph
    modules = _modules(settings.get("modules", []), root, result.problems)
    core = str(settings.get("core_kind", "substrate"))
    files = sorted({Path(p) for pattern in settings.get("paths", []) for p in glob.glob(str(pattern), recursive=True) if Path(p).is_file()})
    by_path = sorted(((m["path"], m["name"]) for m in modules), key=lambda pair: -len(pair[0]))

    def module_of(rel: str) -> str | None:
        return next((name for path, name in by_path if rel == path or rel.startswith(path + "/")), None)

    imports, problems = _imports(root, [f for f in files if f.suffix == ".ttl"], module_of)
    result.problems += problems
    pointers = {m["name"]: (m["readme"] if isinstance(m["readme"], str) else f"{m['path']}/README.md") for m in modules}
    pointers = {n: p for n, p in pointers.items() if (root / p).is_file()}
    found, straddling = data_quanta({m["name"]: m["kind"] for m in modules}, imports, {m["name"] for m in modules if m["release"]}, pointers, core,
                                    str(settings.get("pointer", "")))
    result.findings += [f"{name} shares the {core}'s release number although nothing in the {core} imports it, so the release policy places it across a quantum boundary"
                        for name in straddling]
    for path in (f for f in files if f.name in COMPOSE):
        rel = path.resolve().relative_to(root).as_posix()
        parts = Path(rel).parts
        deployment = "/".join(parts[1:-1]) or "default"
        try:
            document = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except (OSError, UnicodeError, yaml.YAMLError) as error:
            result.problems.append(f"{rel} does not parse ({error.__class__.__name__}), so its quanta are not read")
            continue
        found += software_quanta(deployment, document if isinstance(document, dict) else {}, rel)
    for q in found:
        subject = ki(f"node/{scope}/{normalise(q.identifier)}")
        result.texts[subject.value] = q.claim
        result.bump(f"quantum:{q.view}")
        result.quads += [ox.Quad(subject, RDF_TYPE, ki("Quantum"), graph), ox.Quad(subject, ki("identifier"), ox.Literal(q.identifier), graph),
                         ox.Quad(subject, ki("claim"), ox.Literal(q.claim), graph), ox.Quad(subject, ki("view"), ki(VIEW[q.view]), graph)]
        if q.pointer:
            result.quads.append(ox.Quad(subject, ki("pointer"), ox.Literal(_whole(root, q.pointer)), graph))
        if q.deployment:
            result.quads.append(ox.Quad(subject, ki("deployment"), ox.Literal(q.deployment), graph))
        for part in q.parts:
            if q.view == "data":
                iri, kind = ki(f"module/{scope}/{part}"), "Module"
            else:
                iri, kind = ki(f"component/{scope}/{q.deployment}/{part}"), "Component"
            result.quads += [ox.Quad(subject, ki("includes"), iri, graph), ox.Quad(iri, RDF_TYPE, ki(kind), graph), ox.Quad(iri, RDFS_LABEL, ox.Literal(part), graph)]
    names = [m["name"] for m in modules]
    result.units = {name: [name] for name in names}
    for kind in {m["kind"] for m in modules}:
        result.units.setdefault(kind, [m["name"] for m in modules if m["kind"] == kind])
    result.unit_paths = {m["path"]: m["name"] for m in modules}
    return result
