# SPDX-License-Identifier: MIT
"""The symbol store: one SQLite file per checkout, ``symbols.sqlite`` in its store folder, with an FTS5 index.

A row is one symbol, its ``id`` being ``package:Module.name``, or one chunk of the prose around the code, of kind ``doc``, its ``id`` being
``package:Module#heading``. A chunk is not in the word index, and its vectors sit in a file of their own. The id may repeat, as a field shared by two
constructors or an overload does, so the rowid is the key. A build lists the files by ``git ls-files`` and never walks
a folder, refuses a link that leaves the repository, and reparses only a file whose content hash changed. The vectors
sit beside it, keyed by rowid and cached by the digest of each text as ``embed`` does.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import subprocess
import tomllib
from collections import Counter
from pathlib import Path
from urllib.parse import quote


from .. import embed
from ..credentials import private_dir, private_file
from . import INSTALL, LANGUAGES, available

DB = "symbols.sqlite"
VECTORS = "symbols.npz"
DOC_VECTORS = "docs.npz"
VERSION = 2
MAX_BYTES = 2_000_000
STOP = frozenset("a an and are as at be by can did do does for from how i if in into is it its me my no not of on or so than that the then this to what when where which who why with".split())
COLUMNS = "id, name, kind, module, package, file, line, end_line, signature, doc, exported"
SCHEMA = f"""
CREATE TABLE symbols (id TEXT NOT NULL, name TEXT NOT NULL, kind TEXT NOT NULL, module TEXT NOT NULL, package TEXT NOT NULL, file TEXT NOT NULL,
  line INTEGER NOT NULL, end_line INTEGER NOT NULL, signature TEXT NOT NULL, doc TEXT NOT NULL, exported INTEGER);
CREATE INDEX symbols_id ON symbols (id);
CREATE INDEX symbols_file ON symbols (file);
CREATE TABLE files (file TEXT PRIMARY KEY, hash TEXT NOT NULL);
CREATE VIRTUAL TABLE words USING fts5 (name, signature, doc, tokenize = 'porter unicode61');
PRAGMA user_version = {VERSION};
"""


def split_words(name: str) -> str:
    return re.sub(r"(?<=[a-z0-9])(?=[A-Z])|_+", " ", name).strip().lower()


def glob_regex(pattern: str, prefix: bool = False) -> re.Pattern:
    """A glob as a regular expression over a posix path: ``*`` and ``?`` stay inside a folder, ``**`` crosses them, and
    ``prefix`` also takes everything under what the glob names."""
    out, i = "", 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            out, i = out + "(?:.*/)?", i + 3
        elif pattern.startswith("**", i):
            out, i = out + ".*", i + 2
        elif pattern[i] in "*?":
            out, i = out + ("[^/]*" if pattern[i] == "*" else "[^/]"), i + 1
        else:
            out, i = out + re.escape(pattern[i]), i + 1
    return re.compile(out + ("(?:/.*)?" if prefix else "") + r"\Z")


def tracked(folder: Path) -> list[str]:
    """The files git tracks under ``folder``, relative to it. Raises ``subprocess.CalledProcessError`` outside a repository."""
    from ..config import git_names  # config imports this package

    return git_names(subprocess.run(["git", "-C", str(folder), "ls-files", "-z"], capture_output=True, check=True).stdout)


def toplevel(folder: Path) -> Path:
    from ..config import git_path  # config imports this package

    return Path(git_path(subprocess.run(["git", "-C", str(folder), "rev-parse", "--show-toplevel"], capture_output=True, check=True).stdout)).resolve()


def listed(project) -> tuple[list[tuple[str, str]], list[str]]:
    """The tracked files a project's declarations name, as ``(path relative to its code folder, language)``, and why any was refused."""
    code, problems = project.code, []
    try:
        names, top = tracked(code), toplevel(code)
    except (subprocess.CalledProcessError, OSError) as error:
        return [], [f"symbols need a git repository, and {code} is not one ({error.__class__.__name__})"]
    found: dict[str, str] = {}
    for spec in project.symbols:
        wanted = []
        for place in spec.paths:
            try:
                wanted.append(glob_regex(place.relative_to(code).as_posix()))
            except ValueError:
                problems.append(f"symbols of {spec.language}: {place} is outside the code folder, so it is not read")
        for name in names:
            if name.endswith(LANGUAGES[spec.language]) and any(w.match(name) for w in wanted):
                path = code / name
                if not path.is_file():
                    continue
                if not path.resolve().is_relative_to(top):
                    problems.append(f"{name}: is a link that leaves the repository, so it is not read")
                else:
                    found.setdefault(name, spec.language)
    return sorted(found.items()), problems


def manifest_name(folder: Path, top: Path) -> str | None:
    """The package a folder's manifest names: a ``.cabal`` file's ``name``, ``pyproject.toml``'s ``project.name``, ``package.json``'s
    ``name`` or ``pom.xml``'s ``artifactId``, read as text and never run. A link leaving the repository is not read."""

    def text(path: Path) -> str | None:
        try:
            if path.is_file() and path.resolve().is_relative_to(top) and path.stat().st_size <= MAX_BYTES:
                return path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            pass
        return None

    for cabal in sorted(folder.glob("*.cabal")):
        if (body := text(cabal)) and (m := re.search(r"^name:\s*(\S+)", body, re.M | re.I)):
            return m.group(1)
    if body := text(folder / "pyproject.toml"):
        try:
            if isinstance(name := tomllib.loads(body).get("project", {}).get("name"), str):
                return name
        except tomllib.TOMLDecodeError:
            pass
    if body := text(folder / "package.json"):
        try:
            if isinstance(name := json.loads(body).get("name"), str):
                return name
        except (ValueError, AttributeError):
            pass
    if (body := text(folder / "pom.xml")) and (m := re.search(r"<artifactId>\s*([^<\s]+)\s*</artifactId>", re.sub(r"<parent>.*?</parent>", "", body, flags=re.S))):
        return m.group(1)
    return None


def package_of(folder: Path, top: Path, fallback: str, seen: dict) -> tuple[str, Path]:
    """The nearest package above ``folder``, up to ``top``, with the folder that names it. The project's name where none does."""
    if folder not in seen:
        name = manifest_name(folder, top)
        seen[folder] = (name, folder) if name else (package_of(folder.parent, top, fallback, seen) if folder != top else (fallback, top))
    return seen[folder]


def module_of(language: str, declared: str | None, relative: Path) -> str:
    """The module a file declares, else its path under its package, less a leading ``src`` and an ``__init__``."""
    if declared:
        return declared
    parts = list(relative.with_suffix("").parts)
    if language == "haskell":
        return parts[-1]
    if parts and parts[0] == "src":
        parts = parts[1:]
    return ".".join(parts[:-1] if parts[-1] == "__init__" and len(parts) > 1 else parts)


def connect(path: Path, write: bool = False) -> sqlite3.Connection:
    if write:
        private_file(path)
        return sqlite3.connect(path)
    return sqlite3.connect(f"file:{quote(str(path))}?mode=ro", uri=True)


def _reset(db: sqlite3.Connection) -> None:
    if db.execute("PRAGMA user_version").fetchone()[0] != VERSION:
        for (name,) in db.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'").fetchall():
            db.execute(f'DROP TABLE IF EXISTS "{name}"')
        db.executescript(SCHEMA)


def _forget(db: sqlite3.Connection, file: str) -> None:
    db.execute("DELETE FROM words WHERE rowid IN (SELECT rowid FROM symbols WHERE file = ?)", (file,))
    db.execute("DELETE FROM symbols WHERE file = ?", (file,))
    db.execute("DELETE FROM files WHERE file = ?", (file,))


def build(project, directory: Path) -> tuple[Counter, list[str]]:
    """Bring the store in ``directory`` up to the project's files, reparsing only those whose content hash changed and removing
    the rows of files gone. Returns the counts and why any file or the whole build was skipped. A file that does not parse
    costs that file alone."""
    counts: Counter = Counter()
    if not available():
        return counts, [f"project {project.name} asks for symbols, which need the grammars. {INSTALL}"]
    from . import extract

    files, problems = listed(project)
    try:
        top = toplevel(project.code)
    except (subprocess.CalledProcessError, OSError):
        return counts, problems  # listed has said it is no repository
    private_dir(directory)
    seen = {}
    db = connect(directory / DB, write=True)
    try:
        _reset(db)
        known = dict(db.execute("SELECT file, hash FROM files"))
        for file in sorted(set(known) - {f for f, _ in files}):
            _forget(db, file)
            counts["removed"] += 1
        for file, language in files:
            path = project.code / file
            try:
                if path.stat().st_size > MAX_BYTES:
                    problems.append(f"{file}: is over {MAX_BYTES} bytes, so it is not parsed")
                    continue
                src = path.read_bytes()
            except OSError as error:
                problems.append(f"{file}: cannot be read ({error.__class__.__name__})")
                continue
            package, base = package_of(path.resolve().parent, top, project.name, seen)
            digest = hashlib.sha256(b"\0".join([src, language.encode(), package.encode(), str(base).encode()])).hexdigest()
            if known.get(file) == digest:
                counts["unchanged"] += 1
                continue
            _forget(db, file)
            try:
                declared, symbols = extract.parse(language, src)
                chunks = extract.docs(language, src)
            except Exception as error:  # a grammar or a deeply nested tree fails this file alone
                problems.append(f"{file}: does not parse ({error.__class__.__name__}), so it has no symbols")
                counts["failed"] += 1
                continue
            module = module_of(language, declared, path.resolve().relative_to(base) if path.resolve().is_relative_to(base) else Path(file))
            for s in symbols + chunks:
                cursor = db.execute(f"INSERT INTO symbols ({COLUMNS}) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (
                    f"{package}:{module}{'#' if s['kind'] == 'doc' else '.'}{s['qual']}", s["name"], s["kind"], module, package, file, s["line"], s["end_line"], s["sig"], s["doc"],
                    None if s["exported"] is None else int(s["exported"])))
                if s["kind"] == "doc":
                    continue
                name = s["name"] if split_words(s["name"]) == s["name"].lower() else f"{s['name']} {split_words(s['name'])}"
                db.execute("INSERT INTO words (rowid, name, signature, doc) VALUES (?, ?, ?, ?)", (cursor.lastrowid, name, s["sig"], s["doc"]))
            db.execute("INSERT INTO files (file, hash) VALUES (?, ?)", (file, digest))
            counts["parsed"] += 1
        db.commit()
        counts["symbols"] = db.execute("SELECT count(*) FROM symbols WHERE kind != 'doc'").fetchone()[0]
        counts["docs"] = db.execute("SELECT count(*) FROM symbols WHERE kind = 'doc'").fetchone()[0]
    finally:
        db.close()
    return counts, problems


def vector_text(row: dict, docs_first: bool = True) -> str:
    """What is embedded for a symbol: its name as words, its kind and module, then its signature and doc (the doc first with ``docs_first``)."""
    if row["kind"] == "doc":
        return f"{row['name']}. Written in {row['module']}. {row['doc']}"
    head = f"{split_words(row['name'])}. {row['kind']} in {row['module']}"
    parts = (head, row["doc"], row["signature"]) if docs_first else (head, row["signature"], row["doc"])
    text = ". ".join(x.rstrip(".") for x in parts if x) + "."
    return text[:-1] + ". Exported." if row["exported"] else text


def rows(db: sqlite3.Connection, where: str = "", args: tuple = ()) -> list[dict]:
    """The symbols matching a ``WHERE`` clause, each with its ``rowid``."""
    db.row_factory = sqlite3.Row
    return [dict(r) for r in db.execute(f"SELECT rowid, {COLUMNS} FROM symbols {where}", args)]


def embed_all(directory: Path, spec: embed.ModelSpec, model=None, warm: Path | None = None) -> int:
    """Write the vectors of every symbol, and of every chunk of documentation in a file of its own, embedding only text not seen before.
    Returns how many were embedded now."""
    db = connect(directory / DB)
    try:
        everything = rows(db)
    finally:
        db.close()
    try:
        return sum(embed.build({str(r["rowid"]): vector_text(r) for r in everything if (r["kind"] == "doc") == is_doc}, directory, spec, model, warm, name)
                   for is_doc, name in ((False, VECTORS), (True, DOC_VECTORS)))
    except embed.Unavailable:
        (directory / DOC_VECTORS).unlink(missing_ok=True)
        (directory / VECTORS).unlink(missing_ok=True)
        raise


def refresh(project, directory: Path, spec: embed.ModelSpec, make_vectors: bool = True, model=None, warm: Path | None = None) -> tuple[Counter, list[str]]:
    """``build``, then the vectors, or no vectors where they are not wanted or cannot be made, so a stale set never outlives its rows."""
    counts, problems = build(project, directory)
    if not (directory / DB).exists():
        return counts, problems
    target = directory / VECTORS
    if not make_vectors:
        target.unlink(missing_ok=True)
        (directory / DOC_VECTORS).unlink(missing_ok=True)
        return counts, problems + ["no symbol embeddings, because the build was told not to make them"]
    if target.exists() and (directory / DOC_VECTORS).exists() and not (counts["parsed"] or counts["removed"]):
        return counts, problems  # nothing changed, so the vectors still match the rows
    try:
        counts["embedded"] = embed_all(directory, spec, model, warm)
    except embed.Unavailable as error:
        problems.append(f"no symbol embeddings, so symbols are ranked by word alone: {error}")
    return counts, problems


# ---- Searching ---------------------------------------------------------------------------------


def match_query(words: str) -> str:
    terms = [t for t in dict.fromkeys(re.findall(r"[a-z0-9]+", words.lower())) if t not in STOP]
    return " OR ".join(f'"{t}"' for t in terms)


def word_rank(db: sqlite3.Connection, words: str, limit: int = 100) -> list[int]:
    """The rowids that match the words, best first, by BM25 over name, signature and doc with the name weighing most."""
    query = match_query(words)
    if not query:
        return []
    return [r[0] for r in db.execute("SELECT rowid FROM words WHERE words MATCH ? ORDER BY bm25(words, 3.0, 1.0, 1.0) LIMIT ?", (query, limit))]


def named_rank(db: sqlite3.Connection, words: str) -> list[int]:
    """The rowids whose name is a word of the question that reads as an identifier (camelCase, PascalCase or snake_case), which a name written
    in a question names outright. A plain word such as ``process`` is not taken for one, since it would name every symbol that shares it."""
    tokens = [t for t in dict.fromkeys(re.findall(r"[A-Za-z0-9_']+", words)) if "_" in t or re.search(r"[a-z0-9][A-Z]", t)]
    if not tokens:
        return []
    return [r[0] for r in db.execute(f"SELECT rowid FROM symbols WHERE kind != 'doc' AND name IN ({','.join('?' * len(tokens))}) ORDER BY rowid", tokens)]


def meaning_rank(rowids: np.ndarray, vectors: np.ndarray, question: np.ndarray, limit: int = 100) -> list[tuple[int, float]]:
    """The rowids closest in meaning to the question, best first, with their cosine scores."""
    import numpy as np  # loaded only where it is needed, since every command imports this module
    if not len(rowids):
        return []
    scores = vectors @ question
    order = np.argsort(-scores)[:limit]
    return [(int(rowids[i]), float(scores[i])) for i in order]


def collapse(db: sqlite3.Connection, ranked: list[tuple[int, float]]) -> list[tuple[int, float]]:
    """Documentation chunks with only the best window of each section kept, where windows of one section share a file and an id up to ``+n``."""
    if not ranked:
        return []
    found = {r[0]: (r[1], re.sub(r"\+\d+$", "", r[2])) for r in db.execute(f"SELECT rowid, file, id FROM symbols WHERE rowid IN ({','.join('?' * len(ranked))})", [i for i, _ in ranked])}
    seen, out = set(), []
    for item in ranked:
        if (key := found[item[0]]) not in seen:
            seen.add(key)
            out.append(item)
    return out


def combine(method: str, symbols: list[tuple[int, float]], docs: list[tuple[int, float]], limit: int, share: float = 0.4) -> list[int]:
    """The rowids to show for ``limit`` places, symbols and documentation chunks being each a list of ``(rowid, cosine)``, best first.

    ``symbols`` and ``docs`` are one list each. ``mixed`` sorts both by cosine, ``capped`` does so with at most two fifths of the places going to
    documentation, ``fit`` puts symbols first and takes the places left to documentation, and ``split`` shows ``limit`` symbols, then
    three fifths of ``limit`` documentation chunks beyond them."""
    cap = max(1, int(limit * share + 1e-9)) if share > 0 else 0
    if method == "symbols":
        return [i for i, _ in symbols[:limit]]
    if method == "docs":
        return [i for i, _ in docs[:limit]]
    if method == "fit":
        return [i for i, _ in symbols[:limit - cap]] + [i for i, _ in docs[:cap]]
    if method == "split":
        return [i for i, _ in symbols[:limit]] + [i for i, _ in docs[:max(1, limit * 3 // 5)]]
    doc_ids = {i for i, _ in docs}
    out, taken = [], 0
    for i, _ in sorted(symbols + docs, key=lambda x: -x[1]):
        if i in doc_ids and method == "capped" and taken >= cap:
            continue
        taken += i in doc_ids
        out.append(i)
        if len(out) == limit:
            break
    return out


def fuse(*lists: list[int], k: int = 60) -> list[tuple[int, float]]:
    """Reciprocal rank fusion of ranked lists of rowids: the sum of 1 / (k + rank) over the lists, best first."""
    score: dict[int, float] = {}
    for ranked in lists:
        for place, rowid in enumerate(ranked, 1):
            score[rowid] = score.get(rowid, 0.0) + 1 / (k + place)
    return sorted(score.items(), key=lambda item: (-item[1], item[0]))


def load_vectors(directory: Path, spec: embed.ModelSpec, name: str = VECTORS) -> tuple[np.ndarray, np.ndarray]:
    """The rowids and vectors written beside the store, of the symbols or with ``DOC_VECTORS`` of the documentation. Raises ``embed.Unavailable`` where there are none or another model made them."""
    import numpy as np  # loaded only where it is needed, since every command imports this module
    nodes, vectors = embed.load(directory, spec, name)
    return np.array([int(n) for n in nodes], dtype=np.int64), vectors


def read_source(root: Path, row: dict, limit: int = 60) -> tuple[list[str], str]:
    """The source lines of a symbol and a note on them, read from its file inside the repository. A link leaving it is not read."""
    path = root / row["file"]
    top = toplevel(root)
    if not path.resolve().is_relative_to(top):
        return [], f"{row['file']} is a link that leaves the repository, so it is not read"
    data = path.read_bytes()
    lines = data.decode("utf-8", errors="replace").splitlines()[row["line"] - 1:row["end_line"]]
    note = "" if len(lines) <= limit else f"{len(lines) - limit} more lines follow in {row['file']}"
    return lines[:limit], note
