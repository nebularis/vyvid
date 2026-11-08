# SPDX-License-Identifier: MIT
"""One project reading another's knowledge, from a snapshot of a commit it is pinned to.

The snapshot is ``git archive`` of the pinned commit from the clone the user configured for the read project, extracted
into the base store under the project's name and the commit, with a record of its tree. It is never a checkout, so the index
is reproducible, and a different pin is a different folder and so a rebuild. A snapshot whose files no longer match its record
is extracted again.

The read scope is built from the snapshot's own ``vyvid.toml`` cut down to knowledge: its families, vocabulary, facets,
register types and built-in extractors, and the extractors of the reader's domains it names. Its rules, contract, domains, delegates, moves, hooks and command extractors are
dropped. Its recipes and skills stay only by name in the reader's allow-list, and only under review.
"""

from __future__ import annotations

import hashlib
import io
import os
import shutil
import subprocess
import tarfile
import tempfile
from dataclasses import replace
from pathlib import Path

from .config import COMMAND_KEYS, Config, Read, Scope, file_project, read_project_file

RECORD = "record"
# What of a read project's vyvid.toml survives: knowledge, and the names its skills and recipes would have.
KEPT = ("name", "visibility", "docs", "facets", "register_types", "vocabulary", "families", "extractors", "skills", "skill_prefix",
        "skill_values", "recipes")


def folder(config: Config, name: str, commit: str) -> Path:
    from .build import store_dir  # build imports resolve, which imports this module

    return store_dir(config) / "reads" / name / commit


def fingerprint(root: Path) -> str:
    """A digest of every file's name, size and modification time under ``root``, which an edit to the snapshot changes."""
    digest = hashlib.sha256()
    for path in sorted(p for p in root.rglob("*") if p.is_file() or p.is_symlink()):
        stat = path.lstat()
        digest.update(f"{path.relative_to(root).as_posix()}\0{stat.st_size}\0{stat.st_mtime_ns}\n".encode("utf-8"))
    return digest.hexdigest()


def _git(source: Path, *args: str, binary: bool = False):
    return subprocess.run(["git", "-C", str(source), *args], capture_output=True, text=not binary, **({} if binary else {"encoding": "utf-8", "errors": "replace"}))


def source_of(config: Config, name: str) -> Path | None:
    """The clone the user configured for the project ``name``."""
    code = config.entries.get(name, {}).get("code")
    return Path(code).expanduser() if code else None


def snapshot(config: Config, read: Read) -> tuple[Path | None, list[str]]:
    """The folder holding the read's commit, extracted now if it is missing or was changed, and the notes on how it got here."""
    source = source_of(config, read.name)
    base = folder(config, read.name, read.commit)
    tree, record = base / "tree", base / RECORD
    if source is None or not source.is_dir():
        return None, [f"reads {read.name}: the project has no configured code folder to take commit {read.commit[:12]} from"]
    head = _git(source, "rev-parse", "--verify", "--quiet", f"{read.commit}^{{tree}}")
    wanted = head.stdout.strip()
    if head.returncode != 0 or not wanted:
        return None, [f"reads {read.name}: commit {read.commit[:12]} is not in {source}. Fetch it there, or run vyd reads pin"]
    notes: list[str] = []
    if tree.is_dir() and record.is_file():
        if record.read_text(encoding="utf-8").split() == [wanted, fingerprint(tree)]:
            return tree, notes
        notes.append(f"reads {read.name}: the snapshot of {read.commit[:12]} did not match its record, so it was extracted again")
    shutil.rmtree(base, ignore_errors=True)
    packed = _git(source, "archive", "--format=tar", read.commit, binary=True)
    if packed.returncode != 0:
        return None, [f"reads {read.name}: git archive of {read.commit[:12]} failed: {packed.stderr.decode('utf-8', 'replace').strip()}"]
    base.mkdir(parents=True)
    staged = Path(tempfile.mkdtemp(dir=base))
    with tarfile.TarFile(fileobj=io.BytesIO(packed.stdout)) as archive:
        archive.extractall(staged, filter="data")  # refuses a link or a path that leaves the folder
    os.replace(staged, tree)
    record.write_text(f"{wanted}\n{fingerprint(tree)}\n", encoding="utf-8", newline="\n")
    return tree, notes


def _cut(table: dict, read: Read, reviewed: bool, reader: Scope) -> dict:
    """The knowledge of a read project's vyvid.toml: no command extractor, and recipes only by name once reviewed, never with glue.
    It keeps the reader's domains the read names, with the settings the read project gives them, since their extractors are the reader's."""
    kept = {k: v for k, v in table.items() if k in KEPT}
    named = [d for d in read.domains if d in reader.domains]
    kept["domains"] = named
    kept["uses"] = {d: v for d, v in table.get("uses", {}).items() if d in named} if isinstance(table.get("uses"), dict) else {}
    kept["extractors"] = [e for e in table.get("extractors", []) if isinstance(e, dict) and not any(k in e for k in COMMAND_KEYS)]
    kept["recipes"] = [r for r in table.get("recipes", []) if reviewed and isinstance(r, dict) and r.get("name") in read.recipes
                       and not any(isinstance(s, dict) and s.get("step") == "glue" for s in r.get("steps", []))]
    return kept


def read_scope(config: Config, reader: Scope, read: Read) -> tuple[Scope | None, list[str]]:
    """The scope that is ``reader``'s read of ``read``, answered from the snapshot, with the notes on how it was made."""
    root, notes = snapshot(config, read)
    if root is None:
        return None, notes
    file = root / "vyvid.toml"
    if not file.is_file():
        return None, notes + [f"reads {read.name}: commit {read.commit[:12]} has no vyvid.toml to say where its knowledge is"]
    table, problems = read_project_file(file)
    if problems:
        return None, notes + [f"reads {read.name}: {p}" for p in problems]
    if table.get("name") != read.name:
        return None, notes + [f"reads {read.name}: its vyvid.toml at {read.commit[:12]} names the project '{table.get('name')}'"]
    standing = read.standing(reader)
    scope, problems = file_project(config, file, _cut(table, read, standing == "reviewed", reader), root, None)
    if scope is None:
        return None, notes + [f"reads {read.name}: {p}" for p in problems]
    return replace(scope, remotes=[], read_of=reader.name, read_commit=read.commit, read_standing=standing), notes


def realise(config: Config, reader: Scope) -> Config:
    """``config`` with each of ``reader``'s reads replaced by its scope from the snapshot, and ``reader.read_notes`` saying what failed."""
    made: dict[str, Scope] = {}
    reader.read_notes = []
    for name, read in list(reader.reads.items()):
        scope, notes = read_scope(config, reader, read)
        reader.read_notes += notes
        if scope is None:
            del reader.reads[name]
        else:
            made[name] = scope
    return replace(config, projects={**config.projects, **made}) if made else config
