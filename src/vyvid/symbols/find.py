# SPDX-License-Identifier: MIT
"""``find --kind symbol`` and ``read`` of a symbol, over the symbol store of the question's project.

Symbols rank by meaning over their vectors, and by BM25 over name, signature and doc where there are none. The chunks of
documentation around the code rank by meaning over theirs, and ``METHOD`` says how the two lists are shown together
(``store.combine``, chosen by ``benchmark/symbols``). Both are read from the store the build wrote, which a question first brings
up to date (only a file whose hash changed is parsed again). Nothing here reads the graph, and nothing enters it.
"""

from __future__ import annotations

import sqlite3

from .. import ask, embed
from ..handoff import registered
from . import extract, store

METHOD = "capped"
SHOWN = 200


def fresh(a) -> list[str]:
    """Bring the project's store up to date, with vectors, and say what could not be done."""
    return store.refresh(a.project, a.directory, a.config.embedding, True, a.model)[1]


def symbol_db(a) -> sqlite3.Connection | None:
    """The built store of the question's project, or None where it declares no symbols or none were built."""
    if a.project is None or not a.project.symbols or not (a.directory / store.DB).exists():
        return None
    return store.connect(a.directory / store.DB)


def vectors(a, name: str = store.VECTORS):
    """The rowids and vectors of the symbols, or with ``store.DOC_VECTORS`` of the documentation, or None where they cannot be had here."""
    try:
        return store.load_vectors(a.directory, a.config.embedding, name)
    except embed.Unavailable:
        return None


def share_of(a, given: float | None) -> float:
    """The share of places documentation may take: the question's own, then the project's, then the configuration's."""
    if given is not None:
        return given
    own = a.project.doc_share if a.project is not None else None
    return own if own is not None else a.config.doc_share


def ranked(a, db: sqlite3.Connection, words: str, limit: int, share: float | None = None) -> tuple[list[dict], float, str]:
    """The best symbols for the words, the best meaning score (-1 where there are no vectors), and a note on what could not be used."""
    ranking, best, note = store.word_rank(db, words), -1.0, ""
    if (loaded := vectors(a)) is not None:
        try:
            a.model = a.model or embed.Model(a.config.embedding)
            meaning = store.meaning_rank(*loaded, a.model.question(words))
            ranking, best = [i for i, _ in meaning], meaning[0][1] if meaning else -1.0
        except embed.Unavailable as error:
            note = f"ranked by word alone, since the model cannot run: {error}"
    else:
        note = "ranked by word alone, since there are no symbol vectors. vyd build says why"
    order = list(dict.fromkeys([*store.named_rank(db, words), *ranking]))[:limit]
    if METHOD != "symbols" and note == "" and (docs := vectors(a, store.DOC_VECTORS)) is not None and len(docs[0]):
        named = store.named_rank(db, words)
        scored = [(i, 1.0) for i in named] + [m for m in meaning if m[0] not in named]
        order = store.combine(METHOD, scored, store.collapse(db, store.meaning_rank(*docs, a.model.question(words))), limit, share_of(a, share))
    by_rowid = {r["rowid"]: r for r in store.rows(db, f"WHERE rowid IN ({','.join('?' * len(order))})", tuple(order))} if order else {}
    return [by_rowid[i] for i in order if i in by_rowid], best, note


def under(row: dict) -> str:
    if row["kind"] == "doc":
        return f"[{row['name']}]  " + extract.clip(row["doc"], SHOWN)
    first = (row["doc"] or "").strip().splitlines()[0] if (row["doc"] or "").strip() else ""
    return f"{row['signature']}" + (f"  -- {first}" if first else "")


def find_symbols(a, words: str, limit: int, share: float | None = None) -> int:
    """The symbols that answer the words, in the table ``find`` prints for entries, with the signature and the first line of the doc under each row."""
    if a.project is None or not a.project.symbols:
        print("this project declares no symbols. Add a [[project.symbols]] table to its vyvid.toml, with a language and the paths to parse.")
        return 0
    problems = fresh(a)
    db = symbol_db(a)
    if db is None:
        print("no symbols were built.")
        for problem in problems:
            print(f"NOTE: {problem}")
        return 0
    try:
        found, best, note = ranked(a, db, words, limit, share)
    finally:
        db.close()
    for problem in problems:
        print(f"NOTE: {problem}")
    if not found:
        print(f"no symbol matches: {words}")
        print("Try other words, a name the code would use, or vyd exists for a declared ontology term.")
        return 0
    for r in found:  # a long path loses its front and never its line
        pointer = f"{r['file']}:{r['line']}"
        r["pointer"] = pointer if len(pointer) <= 90 else "..." + pointer[-87:]
    around = [r for r in found if r["kind"] == "doc"] if METHOD in ("split", "fit") else []
    ask.show([r for r in found if r not in around], ("id", "kind", "module", "pointer"), lambda r: under(r)[:240] + _data(a, r))
    if around:
        print("\nwritten around this code")
        ask.show(around, ("id", "kind", "module", "pointer"), lambda r: under(r)[:240] + _data(a, r))
    if note:
        print(f"\n{note}")
    if best != -1.0 and best < a.config.embedding.weak:
        print(f"\nweak match: no symbol scored {a.config.embedding.weak} or more, so the code may not hold it, or words in its names may differ.")
    tools = registered(a.project)
    if tools:
        print(f"\n{len(tools)} registered code index(es) answer who references a name and what a module calls. Run vyd handoff <name> for the exact commands, which vyd does not run.")
    return 0


def _data(a, row: dict) -> str:
    note = ask.data_note(a, a.project.name, row["name"] if row["kind"] == "doc" else row["signature"], row["doc"])
    return f"\n    {note}" if note else ""


def hint(a, words: str) -> None:
    """One line under a plain ``find`` when symbols match strongly, naming ``--kind symbol``. Nothing where the project has none built."""
    if (db := symbol_db(a)) is None:
        return
    db.close()
    if (loaded := vectors(a)) is None or a.model is None:
        return
    top = store.meaning_rank(*loaded, a.model.question(words), 1)
    if top and top[0][1] >= a.config.embedding.near:
        print(f"\nsymbols of this project match strongly. vyd find {words} --kind symbol has answers.")


def read_symbol(a, identifier: str) -> int | None:
    """The source lines of the symbol an identifier names, None where the project's store holds no such id."""
    if (db := symbol_db(a)) is None:
        return None
    try:
        found = store.rows(db, "WHERE id = ? ORDER BY file, line", (identifier,))
    finally:
        db.close()
    if not found:
        return None
    fenced = a.project.name in a.unmarked
    if fenced:
        print(ask.data_note(a, a.project.name, *(r["signature"] or r["name"] for r in found), *(r["doc"] for r in found)))
        print(f"----- begin data from project {a.project.name} -----")
    print(f"{identifier}  {found[0]['kind']}" + (f"  ({len(found)} definitions)" if len(found) > 1 else ""))
    built = (a.directory / store.DB).stat().st_mtime
    for r in found[:3]:
        lines, note = store.read_source(a.project.code, r)
        print(f"== {r['file']}:{r['line']}-{r['end_line']}")
        print("\n".join(lines))
        if note:
            print(note)
        if (a.project.code / r["file"]).stat().st_mtime > built:
            print(f"NOTE: {r['file']} changed since the symbols were built, so these lines may have moved. Run vyd build")
    if len(found) > 3:
        print(f"{len(found) - 3} more definitions with this identifier")
    if fenced:
        print(f"----- end data from project {a.project.name} -----")
    return 0
