# SPDX-License-Identifier: MIT
# From LATTICE's tools/lattice_repo_catalogue.py, relicensed MIT by its author, with the project-specific checks left out.
"""A repository catalogue: where things live in a repository, stated once and read through one reader.

Code that finds a file by a relative path or an absolute one breaks in another checkout, another worktree or another working
folder. A repository can say once where its modules and areas are, and ask this reader for a place by name. Every answer is a
path relative to the catalogue's root, so a caller joins it to whichever root it is working in.

The catalogue is a Markdown file. Fenced blocks tagged ``toml repository-catalogue`` hold the data, and any other fence is text,
so a block shown as an example inside a longer fence is not read. The blocks merge, and a key defined twice is refused:

``[conventions]``                    ``roles``, ``kinds`` (a name and its meaning) and ``[conventions.release]`` with a
                                     ``version`` and the ``kinds`` released together
``[catalogue] modules``              the modules, by name
``[[roots]]``, ``[[docs]]``          named areas of the repository, with a ``path`` and what it ``owns``
``[[tools]]``                        tool packages, with a ``name``, a ``path`` and ``import-names``
``[generated] paths``                paths a check may find missing

Each module has a README at ``<module_root>/<name>/README.md`` with a ``[module]`` block holding ``kind``, ``roles``,
``imports`` and ``extract``. Every key the reader does not know is kept in ``extra``, so a project may add its own keys and
its own checks on top of the shared reader.
"""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

BLOCK_TAG = "toml repository-catalogue"
FILE_NAME = "repository-catalogue.md"
ANY_FENCE_RE = re.compile(r"^ {0,3}(?P<fence>`{3,}|~{3,})(?P<info>.*)$")
AREA_NAME_RE = re.compile(r"^[a-z][a-z0-9-]*$")


class CatalogueError(ValueError):
    """The catalogue cannot be read, or does not hold what was asked of it."""


@dataclass(frozen=True)
class Module:
    name: str
    path: Path
    kind: str
    roles: tuple[str, ...] = ()
    imports: tuple[str, ...] | None = None
    extract: dict[str, tuple[Path, ...]] = field(default_factory=dict)
    extra: dict[str, Any] = field(default_factory=dict)

    def directory(self, role: str) -> Path:
        """The directory of one of the module's roles, relative to the root."""
        if role not in self.roles:
            raise CatalogueError(f"module {self.name!r} has no role {role!r}: declare it in the roles of the catalogue entry in {self.path.as_posix()}/README.md")
        return self.path / role

    def files(self, role: str) -> tuple[Path, ...]:
        """The files the module's README generates for one role, in extraction order, relative to the root."""
        return self.extract.get(role, ())


@dataclass(frozen=True)
class Area:
    """A root or a documentation area, asked for by ``name`` so no tool writes its path itself."""

    path: str
    owns: str
    name: str | None = None
    adrs: tuple[str, ...] = ()
    row: str | None = None
    group: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ToolPackage:
    name: str
    path: str
    import_names: tuple[str, ...] = ()
    reaches: tuple[str, ...] = ()
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Catalogue:
    root: Path
    file: Path
    conventions: dict[str, Any]
    modules: dict[str, Module]
    roots: tuple[Area, ...] = ()
    docs: tuple[Area, ...] = ()
    tools: tuple[ToolPackage, ...] = ()
    generated: tuple[str, ...] = ()
    extra: dict[str, Any] = field(default_factory=dict)  # the blocks the reader does not know, such as a project's own

    @property
    def release_version(self) -> str | None:
        """The one release number every member module carries, or None."""
        return (self.conventions.get("release") or {}).get("version")

    def release_members(self) -> list[Module]:
        """The modules released together: those of the kinds the release names."""
        kinds = set((self.conventions.get("release") or {}).get("kinds", ()))
        return [m for m in self.modules.values() if m.kind in kinds]

    def is_generated(self, path: str) -> bool:
        """Whether a path is, or lies under, a generated path that a check may find missing."""
        return any(path.rstrip("/") == g.rstrip("/") or path.startswith(g.rstrip("/") + "/") for g in self.generated)

    def area(self, name: str) -> Path:
        """The directory of a root or documentation area by its name, relative to the root."""
        for area in (*self.roots, *self.docs):
            if area.name == name:
                return Path(area.path.rstrip("/"))
        known = ", ".join(sorted(a.name for a in (*self.roots, *self.docs) if a.name))
        raise CatalogueError(f"no root or documentation area named {name!r} (known: {known or 'none'}): give its [[roots]] or [[docs]] entry a name in {self.file.name}")

    def module(self, name: str) -> Module:
        if name not in self.modules:
            raise CatalogueError(f"no module {name!r}: list it under [catalogue] modules in {self.file.name}")
        return self.modules[name]

    def modules_of_kind(self, kind: str) -> list[Module]:
        return [m for m in self.modules.values() if m.kind == kind]


def root_above(path: Path | str, file_name: str = FILE_NAME) -> Path | None:
    """The nearest directory at or above ``path`` that holds the catalogue file, or None."""
    here = Path(path).resolve()
    return next((c for c in (here, *here.parents) if (c / file_name).is_file()), None)


def blocks(markdown: str) -> list[str]:
    """The bodies of a document's catalogue blocks. Any other fence is skipped whole."""
    lines, found, index = markdown.splitlines(), [], 0
    while index < len(lines):
        match = ANY_FENCE_RE.match(lines[index])
        if match is None:
            index += 1
            continue
        fence = match.group("fence")
        closing = re.compile(rf"^ {{0,3}}{re.escape(fence[0])}{{{len(fence)},}}\s*$")
        end = index + 1
        while end < len(lines) and not closing.match(lines[end]):
            end += 1
        if end >= len(lines):
            raise CatalogueError(f"unterminated fence opened at line {index + 1}")
        if match.group("info").strip() == BLOCK_TAG:
            found.append("\n".join(lines[index + 1:end]))
        index = end + 1
    return found


def _merge(into: dict, data: dict, where: str, prefix: str = "") -> None:
    for key, value in data.items():
        dotted = f"{prefix}{key}"
        if key in into and isinstance(into[key], dict) and isinstance(value, dict):
            _merge(into[key], value, where, f"{dotted}.")
        elif key in into:
            raise CatalogueError(f"{where}: key {dotted!r} is defined twice")
        else:
            into[key] = value


def _read(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise CatalogueError(f"{path.as_posix()} does not exist")
    merged: dict[str, Any] = {}
    for body in blocks(path.read_text(encoding="utf-8")):
        try:
            data = tomllib.loads(body)
        except tomllib.TOMLDecodeError as error:
            raise CatalogueError(f"{path.as_posix()}: a catalogue block does not parse ({error})") from None
        _merge(merged, data, path.as_posix())
    return merged


def _strings(value: Any, where: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise CatalogueError(f"{where} must be a list of strings")
    return tuple(value)


def _tables(value: Any, key: str, required: tuple[str, ...], file: str) -> list[dict]:
    if not isinstance(value, list) or not all(isinstance(v, dict) for v in value):
        raise CatalogueError(f"{file}: {key} must be a list of tables, written [[{key}]]")
    for number, entry in enumerate(value, 1):
        for name in required:
            if name not in entry:
                raise CatalogueError(f"{file}: {key} entry {number} needs {name!r}")
    return value


def _areas(value: Any, key: str, file: str) -> tuple[Area, ...]:
    known = {"path", "owns", "name", "adrs", "row", "group"}
    out = []
    for entry in _tables(value, key, ("path", "owns"), file):
        name = entry.get("name")
        if name is not None and not (isinstance(name, str) and AREA_NAME_RE.match(name)):
            raise CatalogueError(f"{file}: {key} {entry['path']}: name {name!r} is not a lower-case word")
        out.append(Area(str(entry["path"]), str(entry["owns"]), name, _strings(entry.get("adrs", []), f"{file}: {key} {entry['path']}: adrs"),
                        entry.get("row"), entry.get("group"), {k: v for k, v in entry.items() if k not in known}))
    return tuple(out)


def _tools(value: Any, file: str) -> tuple[ToolPackage, ...]:
    known = {"name", "path", "import-names", "reaches"}
    return tuple(ToolPackage(str(e["name"]), str(e["path"]), _strings(e.get("import-names", []), f"{file}: tools {e['name']}: import-names"),
                             _strings(e.get("reaches", []), f"{file}: tools {e['name']}: reaches"), {k: v for k, v in e.items() if k not in known})
                 for e in _tables(value, "tools", ("name", "path"), file))


def load(file: Path | str, module_root: str = "") -> Catalogue:
    """Read and validate the catalogue at ``file``. Its root is the folder it is in, and a module ``m`` has its README at
    ``<module_root>/m/README.md`` below it."""
    path = Path(file).resolve()
    base = path.parent
    data = _read(path)
    name = path.name
    conventions = data.get("conventions", {})
    kinds = conventions.get("kinds", {})
    release = conventions.get("release")
    if release is not None:
        if not isinstance(release, dict) or not isinstance(release.get("version"), str):
            raise CatalogueError(f"{name}: [conventions.release] needs a version")
        unknown = set(_strings(release.get("kinds", []), f"{name}: [conventions.release] kinds")) - set(kinds)
        if unknown:
            raise CatalogueError(f"{name}: [conventions.release] kinds {', '.join(sorted(unknown))} are not conventions' kinds")
    names = _strings(data.get("catalogue", {}).get("modules", []), f"{name}: [catalogue] modules")
    if len(set(names)) != len(names):
        raise CatalogueError(f"{name}: a module is listed twice")
    modules: dict[str, Module] = {}
    for module_name in names:
        folder = Path(module_root) / module_name
        readme = folder / "README.md"
        entry = _read(base / readme)
        table = entry.get("module")
        if not isinstance(table, dict):
            raise CatalogueError(f"{readme.as_posix()}: needs a catalogue entry with a [module] table")
        kind = table.get("kind")
        if kind not in kinds:
            raise CatalogueError(f"{readme.as_posix()}: kind {kind!r} is not one of the conventions' kinds ({', '.join(kinds) or 'none'})")
        extract = {role: tuple(folder / f for f in _strings(files, f"{readme.as_posix()}: extract.{role}")) for role, files in (table.get("extract") or {}).items()}
        imports = table.get("imports")
        modules[module_name] = Module(module_name, folder, kind, _strings(table.get("roles", []), f"{readme.as_posix()}: roles"),
                                      None if imports is None else _strings(imports, f"{readme.as_posix()}: imports"), extract,
                                      {k: v for k, v in table.items() if k not in ("kind", "roles", "imports", "extract")})
    roots, docs = _areas(data.get("roots", []), "roots", name), _areas(data.get("docs", []), "docs", name)
    named = [a.name for a in (*roots, *docs) if a.name]
    if len(set(named)) != len(named):
        raise CatalogueError(f"{name}: the area name(s) {', '.join(sorted({n for n in named if named.count(n) > 1}))} are used twice")
    generated = data.get("generated", {})
    known = {"conventions", "catalogue", "roots", "docs", "tools", "generated"}
    return Catalogue(base, path, conventions, modules, roots, docs, _tools(data.get("tools", []), name),
                     _strings(generated.get("paths", []), f"{name}: [generated] paths") if isinstance(generated, dict) else (),
                     {k: v for k, v in data.items() if k not in known})


def dump(catalogue: Catalogue) -> dict[str, Any]:
    """The catalogue as plain data for `vyd catalogue dump`, every path relative to the root."""
    def area(a: Area) -> dict:
        return {"name": a.name, "path": a.path, "owns": a.owns}

    return {"root": str(catalogue.root), "release": {"version": catalogue.release_version, "members": [m.name for m in catalogue.release_members()]},
            "modules": {m.name: {"path": m.path.as_posix(), "kind": m.kind, "roles": list(m.roles), "imports": None if m.imports is None else list(m.imports),
                                 "extract": {r: [p.as_posix() for p in ps] for r, ps in m.extract.items()}} for m in catalogue.modules.values()},
            "roots": [area(a) for a in catalogue.roots], "docs": [area(a) for a in catalogue.docs],
            "tools": [{"name": t.name, "path": t.path} for t in catalogue.tools], "generated": list(catalogue.generated)}


def files_of(spec) -> list[Path]:
    """The files a catalogue is read from, for staleness: the catalogue itself and each listed module's README. Nothing is validated here."""
    if spec is None or not spec.file.is_file():
        return []
    try:
        names = _strings(_read(spec.file).get("catalogue", {}).get("modules", []), "modules")
    except CatalogueError:
        names = ()
    return [spec.file, *(spec.file.parent / spec.module_root / n / "README.md" for n in names)]


def for_scope(scope) -> Catalogue | None:
    """The catalogue of a project's scope, or None where it declares none. Raises CatalogueError where it cannot be read."""
    return None if scope is None or scope.catalogue is None else load(scope.catalogue.file, scope.catalogue.module_root)
