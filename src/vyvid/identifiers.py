# SPDX-License-Identifier: MIT
# From LATTICE's tools/knowledge/identifiers.py, relicensed MIT by its author.
"""``vyd check identifiers``: whether every identifier a project's tracked Markdown mentions resolves.

A working document names decisions, register entries and questions by short identifiers, and a mention of
a withdrawn or renumbered one reads exactly like a live one. The check reads the project's families, finds
every mention in the tracked Markdown and sorts each as resolved, a variant, removable or unresolved.

**Enumeration is always from ``git ls-files``, never a filesystem walk.** A checkout can hold ignored
folders of confidential material, and a walk would read them.

*A mention resolves on a normalised key*, letters and digits only, so ``ADR-A-C2`` and ``ADR-AC2`` are
one identifier. A mention under another spelling than its definition's is a variant, reported and never failed.

*A removable family's entries are meant to disappear*, so its unresolved mention is reported, never failed.

*A baseline lists identifiers mentioned and defined nowhere*, one per line with a reason after ``#``, named
by a family's ``exceptions`` or the project's ``identifiers.exceptions``. Only an unresolved identifier not
listed fails. An entry no mention needs any longer is reported as stale, never failed.

*A qualified mention of a scope nothing configures*, such as ``other:STD-1``, is no mention here, since
it names an entry that scope holds.

*A mention covered by a move* resolves through the domain, and only if the domain defines it. A moved row's
copy still in the project's register is not a duplicate.

*An identifier a family defines twice* fails, and the first in wins: the line committed earlier keeps the
number, to the second. Two sharing the second are left to the maintainer.
"""

from __future__ import annotations

import datetime
import fnmatch
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

from .build import store_dir
from .config import Config, Family, Scope
from .model import normalise
from .resolve import definition_sites, forget, moved, visible_families
from .symbols import store as symbol_store

Site = tuple[Path, int]
# The scope a mention is qualified with, written directly before it. One that nothing configures names an entry of no scope here.
QUALIFIER = re.compile(r"(?<![\w-])[a-z][a-z0-9-]*:$")


@dataclass
class Mention:
    """Every site that writes one identifier, under the spellings actually used."""

    scope: Scope  # the scope it names an entry of, the project's own unless the mention is qualified
    family: Family
    key: str
    spellings: dict[str, list[Site]] = field(default_factory=dict)

    @property
    def sites(self) -> list[Site]:
        return [site for spelling in sorted(self.spellings) for site in self.spellings[spelling]]


@dataclass
class Findings:
    unresolved: list[tuple[Mention, str]] = field(default_factory=list)  # the mention and why it resolves to nothing
    removable: list[Mention] = field(default_factory=list)
    variants: list[tuple[Mention, str]] = field(default_factory=list)  # the mention and the canonical spelling
    duplicated: list[tuple[Family, list[tuple[Path, int, str]]]] = field(default_factory=list)
    stale: list[tuple[Path, int, str]] = field(default_factory=list)


def tracked(project: Scope) -> list[Path]:
    """The tracked Markdown of the repositories holding the project's code and documents, from git, less what
    the project skips and the generated copies. Raises ``subprocess.CalledProcessError`` outside a repository, but for
    private documents, which when they are in none track nothing."""
    tops: list[Path] = []
    for folder in (project.code, project.docs):
        if folder is not None and folder.is_dir():
            done = subprocess.run(["git", "-C", str(folder), "rev-parse", "--show-toplevel"], capture_output=True, text=True)
            if done.returncode and folder is project.docs and project.private_docs:
                continue  # private documents in no repository track nothing, so none is read
            if done.returncode:
                raise subprocess.CalledProcessError(done.returncode, done.args, done.stdout, done.stderr)
            top = Path(done.stdout.strip()).resolve()
            if top not in tops:
                tops.append(top)
    scan, keep = project.identifiers, []
    for top in tops:
        listing = subprocess.run(["git", "-C", str(top), "ls-files", "-z", "--", "*.md"], capture_output=True, text=True, check=True).stdout
        for name in filter(None, listing.split("\0")):
            path = top / name
            if not path.is_file() or any(fnmatch.fnmatchcase(name, g) or fnmatch.fnmatchcase(path.name, g) for g in scan.skip):
                continue
            if scan.generated is not None:
                with path.open(encoding="utf-8", errors="replace") as handle:
                    if scan.generated.match(handle.read(200)):
                        continue
            keep.append(path)
    return keep


def mentions(config: Config, project: Scope, paths: list[Path]) -> dict[tuple[str, str, str], Mention]:
    """Every mention in the files, as ``(scope, family name, normalised key)`` -> Mention. A bare mention names
    an entry of the project and a qualified one, ``other:STD-1``, of the scope it names. The first family to
    match a spelling on a line owns it. A ``defined_only`` family matches what its source defines and any
    spelling with a prefix one of its entries has, so ``WB-99`` is a broken mention and ``UTF-8`` no mention."""
    bare = [(f, f.pattern.derive(lambda p: rf"(?<!\w)(?:{p})(?!\w)")) for f in visible_families(config, project) if f.defined is not None]
    named = [(s, f, f.pattern.derive(lambda p, n=re.escape(s.name): rf"(?<!\w){n}:(?:{p})(?!\w)"))
             for s in [config.general, *config.domains.values(), *config.projects.values()]
             for f in visible_families(config, s) if f.defined is not None]
    found: dict[tuple[str, str, str], Mention] = {}

    prefixes: dict[str, set[str]] = {}

    def known(family: Family, spelling: str) -> bool:
        """Whether a ``defined_only`` family has an entry with this spelling's prefix."""
        if family.name not in prefixes:
            prefixes[family.name] = {site[2].split("-", 1)[0] for sites in definition_sites(family).values() for site in sites}
        return spelling.split("-", 1)[0] in prefixes[family.name]

    def add(scope: Scope, family: Family, spelling: str, path: Path, number: int) -> bool:
        key = normalise(spelling)
        if family.defined_only and key not in definition_sites(family) and not known(family, spelling):
            return False
        found.setdefault((scope.name, family.name, key), Mention(scope, family, key)).spellings.setdefault(spelling, []).append((path, number))
        return True

    for path in paths:
        ending = None
        for number, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            if ending is not None:
                if line.startswith(ending):
                    ending = None
                continue
            ending = next((end for begin, end in project.identifiers.regions if line.startswith(begin)), None)
            if ending is not None:
                continue
            claimed: set[str] = set()
            spans: list[tuple[int, int]] = []
            for scope, family, form in named:
                for match in form.finditer(line):
                    if add(scope, family, match.group(0).split(":", 1)[1], path, number):
                        spans.append(match.span())
            for family, form in bare:
                for match in form.finditer(line):
                    if match.group(0) not in claimed and not any(a <= match.start() and match.end() <= b for a, b in spans) \
                            and not QUALIFIER.search(line[: match.start()]) and add(project, family, match.group(0), path, number):
                        claimed.add(match.group(0))
    return found


def gone_symbols(config: Config, project: Scope, paths: list[Path]) -> list[tuple[str, Path, int]] | None:
    """The mentions of ``package:Module.name`` in the files that the project's symbol store no longer holds, as the identifier, file and line.
    None where the project builds no symbols or none are built yet. A package the store holds no symbol of cannot be told from a scope, so it is not matched."""
    path = store_dir(config, project) / symbol_store.DB
    if not project.symbols or not path.is_file():
        return None
    db = symbol_store.connect(path)
    try:
        held = {r[0] for r in db.execute("SELECT id FROM symbols")}
        packages = sorted({r[0] for r in db.execute("SELECT DISTINCT package FROM symbols")}, key=len, reverse=True)
    finally:
        db.close()
    if not packages:
        return []
    form = re.compile(r"(?<![\w-])(?:" + "|".join(map(re.escape, packages)) + r"):[A-Za-z_][\w']*(?:\.[\w']+)+")
    found = []
    for file in paths:
        for number, line in enumerate(file.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            found += [(m.group(0), file, number) for m in form.finditer(line) if m.group(0) not in held]
    return found


def baseline(path: Path | None) -> dict[str, tuple[Path, int, str]]:
    """The identifiers a baseline file excuses, as normalised key -> (file, line, spelling)."""
    entries: dict[str, tuple[Path, int, str]] = {}
    if path is not None and path.is_file():
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if entry := line.split("#", 1)[0].strip():
                entries.setdefault(normalise(entry), (path, number, entry))
    return entries


def examine(config: Config, project: Scope, families: list[Family], found: dict[tuple[str, str, str], Mention]) -> Findings:
    """Sort every mention into resolved, a variant, removable or unresolved, and find the duplicates and the
    baseline entries nothing needs."""
    findings, used = Findings(), set()
    project_baseline = baseline(project.identifiers.exceptions)
    excuses = {f.name: baseline(f.exceptions) for f in families}
    order = {f.name: i for i, f in enumerate(families)}
    for mention in sorted(found.values(), key=lambda m: (m.scope.name != project.name, order.get(m.family.name, 0), m.key)):
        family, spelling = mention.family, sorted(mention.spellings)[0]
        if (hit := moved(config, mention.scope, spelling)) is not None:
            move, target = hit
            if any(normalise(target) in definition_sites(g) for g in config.domains[move.to].families.values() if g.pattern.fullmatch(target)):
                continue
            why = f"moved to {move.to}:{target}, which defines nothing by that name"
        else:
            canonical = definition_sites(family).get(mention.key)
            if canonical:
                if any(s != canonical[0][2] for s in mention.spellings):
                    findings.variants.append((mention, canonical[0][2]))
                continue
            why = "mentioned but never defined"
        excused = excuses.get(family.name, {}).get(mention.key) or project_baseline.get(mention.key)
        if excused is not None:
            used.add((excused[0], mention.key))
        elif family.removable:
            findings.removable.append(mention)
        else:
            findings.unresolved.append((mention, why))
    for family in families:
        if family.rule != "question":  # a question defined again keeps its first definition
            findings.duplicated += [(family, sites) for sites in definition_sites(family).values()
                                    if len(sites) > 1 and moved(config, project, sites[0][2]) is None]
    for entries in [project_baseline, *excuses.values()]:
        findings.stale += [entry for key, entry in entries.items() if (entry[0], key) not in used and entry not in findings.stale]
    return findings


def committed_on(path: Path, line: int) -> str:
    """When the line was committed, to the second in UTC as 2026-11-02T14:13:37Z, from git blame,
    "uncommitted" for a line not yet committed, or "unknown" where git cannot say. Line 0 dates the
    file's first commit. Two branches often number rows on the same day, so a day cannot order them."""
    try:
        if line == 0:
            out = subprocess.run(["git", "log", "--diff-filter=A", "--format=%ct", "--", str(path)],
                                 cwd=path.parent, capture_output=True, text=True, check=True).stdout
            return _utc(int(out.strip().splitlines()[-1])) if out.strip() else "uncommitted"
        out = subprocess.run(["git", "blame", "--line-porcelain", f"-L{line},{line}", "--", str(path)],
                             cwd=path.parent, capture_output=True, text=True, check=True).stdout
    except (subprocess.CalledProcessError, OSError, IndexError):
        return "unknown"
    if out.startswith("0" * 40):
        return "uncommitted"
    for row in out.splitlines():
        if row.startswith("committer-time "):
            return _utc(int(row.split()[1]))
    return "unknown"


def _utc(seconds: int) -> str:
    return datetime.datetime.fromtimestamp(seconds, datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def first_in(dates: list[str]) -> int | None:
    """The index of the site committed first, or None where two share the earliest time or one has
    no time, since then the rule cannot pick and the maintainer does."""
    known = [d for d in dates if d[:1].isdigit()]
    if len(known) != len(dates) or known.count(min(known)) > 1:
        return None
    return dates.index(min(known))


def _label(mention: Mention, project: Scope, spelling: str) -> str:
    return spelling if mention.scope.name == project.name else f"{mention.scope.name}:{spelling}"


def _name(path: Path, roots: list[Path]) -> str:
    return next((path.relative_to(r).as_posix() for r in roots if path.is_relative_to(r)), path.as_posix())


def _where(sites: list[Site], roots: list[Path], limit: int = 4) -> str:
    shown = ", ".join(f"{_name(path, roots)}:{line}" for path, line in sites[:limit])
    return shown + (f" and {len(sites) - limit} more" if len(sites) > limit else "")


def command(config: Config, project: Scope | None, as_json: bool, everything: bool) -> int:
    """Print the findings, plain or as JSON. Returns 1 if an identifier is unresolved or defined twice, or a
    pattern ran out of time, 2 if the files cannot be listed. The rest is reported and never fails."""
    if project is None:
        print("no project claims this folder, so there are no identifiers to check")
        return 0
    forget()
    families = [f for f in visible_families(config, project) if f.defined is not None]
    try:
        paths = tracked(project)
    except (subprocess.CalledProcessError, OSError) as error:
        print(f"vyd: cannot list the tracked Markdown of {project.name}: {error}", file=sys.stderr)
        return 2
    found = mentions(config, project, paths)
    findings = examine(config, project, families, found)
    slow = [f.name for f in families if f.pattern.timed_out]
    roots = [r for r in (project.code, project.docs) if r is not None]
    settled = [(f, sites, [committed_on(p, n) for p, n, _ in sites]) for f, sites in findings.duplicated]
    failed = bool(findings.unresolved or settled or slow)
    gone = gone_symbols(config, project, paths)
    if as_json:
        print(json.dumps({**_json(findings, settled, slow, roots, len(paths), project),
                          **({} if gone is None else {"symbols_gone": [{"identifier": i, "path": _name(p, roots), "line": n} for i, p, n in gone]})}, indent=2))
        return int(failed)
    for mention, why in findings.unresolved:
        print(f"ERROR: {_label(mention, project, sorted(mention.spellings)[0])} ({mention.family.name}) is {why}: {_where(mention.sites, roots)}")
    for family, sites, dates in settled:
        first = first_in(dates)
        where = ", ".join(f"{_name(p, roots)}:{n} ({d})" for (p, n, _), d in zip(sites, dates))
        keeps = (f" {_name(sites[first][0], roots)}:{sites[first][1]} keeps the number." if first is not None
                 else " No one site was committed first, so the maintainer decides which keeps it.")
        print(f"ERROR: {sites[0][2]} ({family.name}) is defined {len(sites)} times: {where}.{keeps}")
    for name in slow:
        print(f"ERROR: family {name} has a pattern that ran out of time, so its mentions are incomplete")
    if everything:
        for mention, canonical in findings.variants:
            print(f"variant: {', '.join(s for s in sorted(mention.spellings) if s != canonical)} -> {canonical} ({mention.family.name}): {_where(mention.sites, roots)}")
        for mention in findings.removable:
            print(f"removable: {_label(mention, project, sorted(mention.spellings)[0])} ({mention.family.name}) is no longer defined: {_where(mention.sites, roots)}")
    for identifier, path, number in gone or []:
        print(f"symbol gone: {identifier} is in no file the symbol store holds: {_name(path, roots)}:{number}")
    for path, number, entry in findings.stale:
        print(f"stale: {entry} ({_name(path, roots)}:{number}) is excused and nothing needs it")
    if project.private_docs and project.docs is not None and project.docs.is_dir() and subprocess.run(
            ["git", "-C", str(project.docs), "rev-parse", "--show-toplevel"], capture_output=True).returncode:
        print(f"not read: {project.docs} is in no git repository and only tracked files are scanned, so no mention in those documents was checked")
    print(f"{'identifier check failed' if failed else 'identifier check passed'}: {len(found)} identifiers mentioned in {len(paths)} files, "
          f"{len(findings.unresolved)} unresolved, {len(settled)} defined twice, {len(findings.variants)} written under another spelling, "
          f"{len(findings.removable)} removable no longer defined, {len(findings.stale)} stale exceptions"
          + ("" if gone is None else f", {len(gone)} symbols gone") + ("" if everything else " (--all lists them)"))
    return int(failed)


def _json(findings: Findings, settled: list, slow: list[str], roots: list[Path], files: int, project: Scope) -> dict:
    def sites(items: list[Site]) -> list[dict]:
        return [{"path": _name(p, roots), "line": n} for p, n in items]

    def mention(m: Mention) -> dict:
        return {"identifier": _label(m, project, sorted(m.spellings)[0]), "scope": m.scope.name, "family": m.family.name, "sites": sites(m.sites)}

    duplicates = []
    for family, defined, dates in settled:
        first = first_in(dates)
        duplicates.append({"identifier": defined[0][2], "family": family.name, "keeps": None if first is None else _name(defined[first][0], roots) + f":{defined[first][1]}",
                           "sites": [{"path": _name(p, roots), "line": n, "committed": d} for (p, n, _), d in zip(defined, dates)]})
    return {
        "files": files,
        "unresolved": [{**mention(m), "why": why} for m, why in findings.unresolved],
        "removable": [mention(m) for m in findings.removable],
        "variants": [{**mention(m), "canonical": canonical, "spellings": sorted(m.spellings)} for m, canonical in findings.variants],
        "duplicates": duplicates,
        "stale": [{"identifier": e, "path": _name(p, roots), "line": n} for p, n, e in findings.stale],
        "timed_out": slow,
    }
