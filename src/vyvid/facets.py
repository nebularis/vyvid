# SPDX-License-Identifier: MIT
# From LATTICE's tools/knowledge/facets.py, relicensed MIT by its author, generalised to any schemes
# and to several registers merged in the order of their scopes.
"""Read facet registers into SKOS concept schemes, and write them as Turtle.

A facet register's Schemes table declares its schemes, and a section per scheme lists its values,
one row each, whose columns are the SKOS properties that state their meaning. A value with no
broader value is a top concept of its scheme. ``Group`` yes is the editorial note "group", a value
that organises others and is never tagged, and ``Ratified`` no is the editorial note "proposed".
Broader and related values are slugs separated by spaces, and a related value may sit in another
scheme.

Several registers are merged in the order of their scopes, general first and the project last. A
later register may add schemes and values, and name an earlier register's values as broader or
related, which is how a domain extends a general scheme. A slug is defined once across all of them.
A register that cannot be read, or a merge that names a value defined nowhere, is refused with every
problem listed. The Turtle is deterministic: rows in their order, a cell's values sorted.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path

NS = "https://www.nebularis.org/vyvid/facets#"
SCHEME_COLUMNS = ["ID", "Label", "Definition"]
VALUE_COLUMNS = ["ID", "Label", "Broader", "Related", "Group", "Definition", "Scope note", "Ratified"]
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9.+-]*$")
SCHEME_RE = re.compile(r"^[A-Z][A-Za-z0-9]*$")
SEPARATOR_RE = re.compile(r"^\|[\s:|-]+\|?$")
HEADING_RE = re.compile(r"^##\s+(?P<name>.+?)\s*$")


class RegisterError(ValueError):
    """The registers cannot be read as schemes, with every problem found listed."""

    def __init__(self, problems: list[str]):
        super().__init__("\n".join(problems))
        self.problems = problems


@dataclass
class Scheme:
    slug: str
    label: str
    definition: str
    where: str = ""


@dataclass
class Value:
    slug: str
    scheme: str
    label: str
    definition: str
    broader: list[str] = field(default_factory=list)
    related: list[str] = field(default_factory=list)
    group: bool = False
    scope_note: str = ""
    ratified: bool = True
    where: str = ""


def default_register() -> str:
    """The general facet register that ships with the package, from LATTICE's, under MIT."""
    return resources.files("vyvid").joinpath("data/facets.md").read_text(encoding="utf-8")


def _cells(line: str) -> list[str]:
    cells = line.strip().split("|")[1:]
    if cells and not cells[-1].strip():
        cells.pop()
    return [c.strip() for c in cells]


def _flag(cell: str, name: str, where: str, problems: list[str], *, blank: bool) -> bool:
    if cell == "yes":
        return True
    if cell == "no" or (blank and cell == ""):
        return False
    problems.append(f"{where}: {name} is {cell!r}, not yes or no{' or empty' if blank else ''}")
    return False


def _read(name: str, text: str, problems: list[str]) -> tuple[list[Scheme], list[Value]]:
    """One register's schemes and values, in its order, adding what it cannot read to ``problems``."""
    schemes: list[Scheme] = []
    values: list[Value] = []
    section: str | None = None
    headers: list[str] | None = None
    rejected = False
    for number, line in enumerate(text.splitlines(), 1):
        where = f"{name}:{number}"
        if (heading := HEADING_RE.match(line)) is not None:
            section, headers = heading["name"], None
            continue
        if not line.strip().startswith("|"):
            headers = None
            continue
        if headers is None:
            headers = _cells(line)
            wanted = SCHEME_COLUMNS if section == "Schemes" else VALUE_COLUMNS
            rejected = headers != wanted
            if rejected:
                problems.append(f"{where}: the columns under {section!r} are {headers}, not {wanted}")
            continue
        if SEPARATOR_RE.match(line.strip()) or rejected:
            continue
        cells = _cells(line)
        if len(cells) != len(headers):
            problems.append(f"{where}: {len(cells)} cells under {len(headers)} columns")
            continue
        row = dict(zip(headers, cells))
        if section == "Schemes":
            schemes.append(Scheme(row["ID"], row["Label"], row["Definition"], where))
        else:
            values.append(Value(
                slug=row["ID"], scheme=section or "", label=row["Label"], definition=row["Definition"],
                broader=sorted(row["Broader"].split()), related=sorted(row["Related"].split()),
                group=_flag(row["Group"], "Group", where, problems, blank=True), scope_note=row["Scope note"],
                ratified=_flag(row["Ratified"], "Ratified", where, problems, blank=False), where=where,
            ))
    return schemes, values


def merge(registers: list[tuple[str, str]]) -> tuple[list[Scheme], list[Value]]:
    """The schemes and values of several registers, given as ``(name, text)`` in scope order."""
    problems: list[str] = []
    schemes: dict[str, Scheme] = {}
    seen: dict[str, Value] = {}
    values: list[Value] = []
    for name, text in registers:
        own_schemes, own_values = _read(name, text, problems)
        for scheme in own_schemes:
            if not SCHEME_RE.match(scheme.slug):
                problems.append(f"{scheme.where}: scheme {scheme.slug!r} is not a capitalised name")
            elif scheme.slug in schemes:
                problems.append(f"{scheme.where}: scheme {scheme.slug} is already declared at {schemes[scheme.slug].where}")
            else:
                schemes[scheme.slug] = scheme
        for value in own_values:
            if value.scheme not in schemes:
                problems.append(f"{value.where}: a value under {value.scheme!r}, which no register declares as a scheme")
            if not SLUG_RE.match(value.slug):
                problems.append(f"{value.where}: {value.slug!r} is not a slug of lower-case letters, digits and hyphens")
            if value.slug in seen:
                problems.append(f"{value.where}: {value.slug} is already defined at {seen[value.slug].where}")
                continue
            for label, text_ in (("Label", value.label), ("Definition", value.definition)):
                if not text_:
                    problems.append(f"{value.where}: {value.slug} has no {label}")
            seen[value.slug] = value
            values.append(value)
    for value in values:
        for broader in value.broader:
            if broader not in seen:
                problems.append(f"{value.where}: {value.slug}'s broader value {broader} is defined nowhere")
            elif seen[broader].scheme != value.scheme:
                problems.append(f"{value.where}: {value.slug}'s broader value {broader} is in {seen[broader].scheme}, not {value.scheme}")
        problems += [f"{value.where}: {value.slug}'s related value {r} is defined nowhere" for r in value.related if r not in seen]
    if problems:
        raise RegisterError(problems)
    return list(schemes.values()), values


def _literal(text: str) -> str:
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def turtle(schemes: list[Scheme], values: list[Value], namespace: str = NS, label: str = "Вивід facets") -> str:
    """The schemes as Turtle, the same bytes for the same registers."""
    out = [
        "# Generated by vyvid from the facet registers. Never committed and never edited: change a register.",
        "",
        "@prefix fct:  <" + namespace + "> .",
        "@prefix owl:  <http://www.w3.org/2002/07/owl#> .",
        "@prefix rdf:  <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .",
        "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .",
        "@prefix skos: <http://www.w3.org/2004/02/skos/core#> .",
        "",
        f"<{namespace.rstrip('#/')}>",
        "    rdf:type owl:Ontology ;",
        f"    rdfs:label {_literal(label)} .",
        "",
    ]
    for scheme in schemes:
        out += [
            f"fct:{scheme.slug} rdf:type skos:ConceptScheme ;",
            f"    skos:prefLabel {_literal(scheme.label)} ;",
            f"    skos:definition {_literal(scheme.definition)} .",
            "",
        ]
    for value in values:
        lines = [f"fct:{value.slug} rdf:type skos:Concept ; skos:inScheme fct:{value.scheme}"]
        if value.broader:
            lines.append("skos:broader " + " , ".join(f"fct:{b}" for b in value.broader))
        else:
            lines.append(f"skos:topConceptOf fct:{value.scheme}")
        if value.related:
            lines.append("skos:related " + " , ".join(f"fct:{r}" for r in value.related))
        lines.append(f"skos:prefLabel {_literal(value.label)}")
        lines.append(f"skos:definition {_literal(value.definition)}")
        if value.scope_note:
            lines.append(f"skos:scopeNote {_literal(value.scope_note)}")
        if value.group:
            lines.append('skos:editorialNote "group"')
        if not value.ratified:
            lines.append('skos:editorialNote "proposed"')
        out.append(" ;\n    ".join(lines) + " .")
        out.append("")
    return "\n".join(out)


def taggable(values: list[Value]) -> dict[str, set[str]]:
    """Per scheme, the values an entry may be tagged with: every value but a group."""
    out: dict[str, set[str]] = {}
    for value in values:
        if not value.group:
            out.setdefault(value.scheme, set()).add(value.slug)
    return out


def write(path: Path, text: str) -> Path:
    """Write ``text`` to ``path`` only when its bytes differ, so a build that changes nothing leaves its time alone."""
    if not path.exists() or path.read_text(encoding="utf-8") != text:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")
    return path


def registers(stack) -> list[tuple[str, str]]:
    """The facet registers of a stack of scopes, general first, as ``(name, text)``: the general
    scope's configured registers, or the packaged default when it names none, then every register
    a domain or the project names that exists."""
    general, *rest = stack
    found = [(str(p), p.read_text(encoding="utf-8")) for p in general.facets if p.exists()]
    out = found or [("vyvid:data/facets.md", default_register())]
    for scope in rest:
        out += [(str(p), p.read_text(encoding="utf-8")) for p in scope.facets if p.exists()]
    return out
