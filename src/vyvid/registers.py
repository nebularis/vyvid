# SPDX-License-Identifier: MIT
# The register reader of LATTICE's tools/knowledge/extract.py, relicensed MIT by its author, with its
# column table made a declaration.
"""Read registers by the register types declared for them.

A register is a Markdown table whose header is its schema. The register types say what each column
header means, a property and a kind, which closed sets a controlled column takes its values from,
and which class a type's rows become. The packaged declarations come first, then any a scope adds,
a later declaration of a column, a value set or a type replacing an earlier one.

A row is read only if its identifier cell matches its family. Anything that cannot be read as its
type declares, a header neither mapped nor unmapped, a value outside its set, a facet value its
scheme does not hold, a claim over the limit or a row whose cells do not fit the header, is reported
with its line and never stored or guessed. Identifiers in a cell are kept as written, and resolved
later in the register's scope.
"""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path

from . import anchors

KINDS = {"id", "claim", "label", "text", "ids", "targets", "addenda", "names", "module", "controlled", "facet", "status"}
SEPARATOR_RE = re.compile(r"^\|[\s:|-]+\|?$")
BOLD_RE = re.compile(r"\*\*(?P<claim>.+?)\*\*")
LINK_RE = re.compile(r"\[([^\]]+)\]\([^)]+\)")


class DeclarationError(ValueError):
    def __init__(self, problems: list[str]):
        super().__init__("\n".join(problems))
        self.problems = problems


@dataclass(frozen=True)
class Column:
    header: str
    property: str
    kind: str
    values: str | None = None  # the value set of a controlled or status column
    scheme: str | None = None  # the facet scheme of a facet column
    limit: int | None = None
    trailing: bool = False
    sets_status: str | None = None  # the status a row has when this column is filled


@dataclass
class RegisterTypes:
    columns: dict[str, Column] = field(default_factory=dict)
    values: dict[str, dict[str, str]] = field(default_factory=dict)
    types: dict[str, str] = field(default_factory=dict)  # type name -> class
    unmapped: set[str] = field(default_factory=set)
    claim_limit: int = 200

    @property
    def trailing(self) -> set[str]:
        return {h for h, c in self.columns.items() if c.trailing}


def default_declarations() -> str:
    return resources.files("vyvid").joinpath("data/register-types.toml").read_text(encoding="utf-8")


def declarations(sources: list[tuple[str, str]]) -> RegisterTypes:
    """The register types declared by ``(name, toml)`` sources in scope order, the packaged first."""
    out, problems = RegisterTypes(), []
    for name, text in sources:
        try:
            raw = tomllib.loads(text)
        except tomllib.TOMLDecodeError as error:
            problems.append(f"{name}: {error}")
            continue
        out.claim_limit = raw.get("limits", {}).get("claim", out.claim_limit)
        out.values.update({k: dict(v) for k, v in raw.get("values", {}).items()})
        out.unmapped |= set(raw.get("unmapped", {}).get("columns", []))
        for header, spec in raw.get("columns", {}).items():
            kind = spec.get("kind")
            if kind not in KINDS or "property" not in spec:
                problems.append(f"{name}: column '{header}' needs a property and a kind of {sorted(KINDS)}")
                continue
            out.columns[header] = Column(header, spec["property"], kind, spec.get("values"), spec.get("scheme"),
                                         spec.get("limit"), bool(spec.get("trailing", False)), spec.get("status"))
            out.unmapped.discard(header)
        for type_name, spec in raw.get("types", {}).items():
            if "class" not in spec:
                problems.append(f"{name}: type '{type_name}' names no class")
            else:
                out.types[type_name] = spec["class"]
    for column in out.columns.values():
        if column.kind in ("controlled", "status") and column.values not in out.values:
            problems.append(f"column '{column.header}' takes values from '{column.values}', which is declared nowhere")
        if column.kind == "facet" and not column.scheme:
            problems.append(f"column '{column.header}' is a facet column with no scheme")
    if problems:
        raise DeclarationError(problems)
    return out


@dataclass
class Row:
    """One register entry, as its columns state it. ``values`` maps a property to what its cells hold,
    a controlled value as its individual's name, a facet value as its slug, anything else as written."""

    identifier: str
    cls: str
    source: str
    line: int
    claim: str | None = None
    label: str | None = None
    status: str = "Open"
    pointer: list[str] = field(default_factory=list)
    values: dict[str, list[str]] = field(default_factory=dict)


def _cells(line: str) -> list[str]:
    cells = line.strip().split("|")[1:]
    if cells and not cells[-1].strip():
        cells.pop()
    return [c.strip() for c in cells]


def shorten(text: str, limit: int) -> str:
    """A claim is one sentence. Longer text is cut, and the reader reports that it was."""
    text = re.sub(r"\s+", " ", LINK_RE.sub(r"\1", text)).strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def read(path: Path, name: str, family_pattern: re.Pattern[str], register_type: str, types: RegisterTypes,
         taggable: dict[str, set[str]], root: Path) -> tuple[list[Row], list[str]]:
    """The rows of a register of one type, and every problem found. ``name`` is how the register is
    named in a problem, ``root`` the folder its pointers are resolved against."""
    problems: list[str] = []
    rows: list[Row] = []
    cls = types.types.get(register_type)
    if cls is None:
        return [], [f"{name}: register type '{register_type}' is declared nowhere"]
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    headers: list[str] | None = None
    checked = False
    for number, line in enumerate(lines, 1):
        stripped = line.strip()
        if not stripped.startswith("|"):
            headers = None
            continue
        following = lines[number].strip() if number < len(lines) else ""
        if SEPARATOR_RE.match(following) and not SEPARATOR_RE.match(stripped):
            headers, checked = _cells(stripped), False
            continue
        if headers is None or SEPARATOR_RE.match(stripped):
            continue
        cells = _cells(stripped)
        id_at = next((i for i, h in enumerate(headers) if h in types.columns and types.columns[h].kind == "id"), 0)
        if id_at >= len(cells) or not family_pattern.fullmatch(cells[id_at]):
            continue
        if not checked:
            checked = True
            problems += [f"{name}:{number}: column '{h}' is neither declared nor on the unmapped list"
                         for h in headers if h not in types.columns and h not in types.unmapped]
        identifier = cells[id_at]
        here = f"{name}:{number}: {identifier}"
        if len(cells) < len(headers) and set(headers[len(cells):]) <= types.trailing:
            cells = cells + [""] * (len(headers) - len(cells))
        if len(cells) != len(headers):
            problems.append(f"{here} has {len(cells)} cells under {len(headers)} headers, so its columns cannot be trusted")
            continue
        row = Row(identifier, cls, name, number, pointer=[f"{name}:{number}-{number}"])
        for header, cell in zip(headers, cells):
            column = types.columns.get(header)
            if column is None or not cell or column.kind == "id":
                continue
            if column.kind == "claim":
                bold = BOLD_RE.search(cell)
                lead = bold.group("claim") if bold else cell
                if len(shorten(lead, 10_000)) > types.claim_limit:
                    problems.append(f"{here} has a claim of {len(shorten(lead, 10_000))} characters, which is cut at {types.claim_limit}")
                row.claim = shorten(lead, types.claim_limit)
            elif column.kind == "label":
                row.label = cell
            elif column.property == "pointer":
                ranges, failed = anchors.resolve(root, cell)
                problems += [f"{here} has Pointer {reason}" for reason in failed]
                if ranges:
                    row.pointer = ranges
            elif column.kind == "status":
                # The leading word is the fact, and a tail such as "added 2026-10-27" is for the reader.
                value = types.values[column.values].get(cell.split(",")[0].strip().lower())
                if value is None:
                    problems.append(f"{here} has {header} '{cell}', not one of {sorted(types.values[column.values])}")
                else:
                    row.status = value
            elif column.kind in ("controlled", "facet"):
                allowed = types.values[column.values] if column.kind == "controlled" else {v: v for v in taggable.get(column.scheme, set())}
                for value in (v.strip() for v in cell.split(",") if v.strip()):
                    if value not in allowed:
                        what = f"a taggable value of the {column.scheme} facet" if column.kind == "facet" else f"one of {sorted(allowed)}"
                        problems.append(f"{here} has {header} '{value}', which is not {what}")
                    else:
                        row.values.setdefault(column.property, []).append(allowed[value])
            else:
                if column.limit and len(cell) > column.limit:
                    problems.append(f"{here} has a {header} of {len(cell)} characters, over {column.limit}")
                row.values.setdefault(column.property, []).append(cell.replace("`", "") if column.property == "entryPoint" else cell)
        for header, cell in zip(headers, cells):
            if cell and (column := types.columns.get(header)) is not None and column.sets_status:
                row.status = column.sets_status
        if row.claim is None:
            problems.append(f"{here} has no claim")
        rows.append(row)
    return rows, problems


def types_for(stack) -> RegisterTypes:
    """The register types a stack of scopes declares: the packaged ones, then each scope's that exist."""
    sources = [("vyvid:data/register-types.toml", default_declarations())]
    for scope in stack:
        sources += [(str(p), p.read_text(encoding="utf-8")) for p in scope.register_types if p.exists()]
    return declarations(sources)


def read_scope(scope, types: RegisterTypes, taggable: dict[str, set[str]]) -> tuple[list[Row], list[str]]:
    """Every row of every register a scope's table families are defined in, and every problem found. A
    family with no register type, or whose register is missing, is reported."""
    root = scope.code or scope.path or Path.cwd()
    rows: list[Row] = []
    problems: list[str] = []
    for family in scope.families.values():
        if family.defined is None or family.type is None or family.rule != "table":
            continue
        if not (files := family.paths()):
            problems.append(f"{scope.name}: family {family.name} is defined in {family.defined}, which matches no file")
            continue
        for path in files:
            try:
                name = path.resolve().relative_to(root.resolve()).as_posix()
            except ValueError:
                name = path.as_posix()
            found, trouble = read(path, name, family.pattern, family.type, types, taggable, root)
            rows += found
            problems += trouble
    return rows, problems
