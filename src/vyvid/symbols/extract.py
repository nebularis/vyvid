# SPDX-License-Identifier: MIT
"""Parse one source file into its symbols, with tree-sitter and one query file per language.

A symbol is a dictionary with ``kind``, ``name``, ``qual`` (the name under its owner, as ``Owner.name``),
``sig`` (its signature), ``doc``, ``line``, ``end_line`` and ``exported``, which is None where the language has no
export list to say. ``parse`` returns the module the file declares, or None where its path decides, with the symbols.

The queries are tags queries, each ``@definition.<kind>`` with its ``@name``. Python's, Java's and TypeScript's
start from the grammars' own and Haskell's is ours, since that grammar ships none. Haddock comments are attached
here and not by a query, because ``-- |`` binds to what follows and ``-- ^`` to what precedes.
"""

from __future__ import annotations

import re
from functools import cache
from importlib import resources

SIG_LIMIT, DOC_LIMIT = 400, 300
SKIPPED = ("haddock", "comment")


@cache
def _language(name: str):
    import tree_sitter as ts
    import tree_sitter_haskell, tree_sitter_java, tree_sitter_python, tree_sitter_typescript  # noqa: E401

    pointer = {"python": tree_sitter_python.language, "haskell": tree_sitter_haskell.language, "java": tree_sitter_java.language,
               "typescript": tree_sitter_typescript.language_typescript}[name]()
    language = ts.Language(pointer)
    query = ts.Query(language, resources.files("vyvid.symbols").joinpath(f"queries/{name}.scm").read_text(encoding="utf-8"))
    return ts, ts.Parser(language), query


def clip(text: str, limit: int) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    return text if len(text) <= limit else text[:limit].rsplit(" ", 1)[0] + " ..."


def txt(src: bytes, node) -> str:
    return src[node.start_byte:node.end_byte].decode("utf-8", "replace")


def text_without(src: bytes, node, stop: int | None = None) -> str:
    """The node's source, up to byte ``stop``, with its comments removed, so a signature is whole without its argument docs."""
    end = node.end_byte if stop is None else stop
    out, pos = [], node.start_byte

    def walk(n) -> None:
        nonlocal pos
        if n.start_byte >= end:
            return
        if n.type in SKIPPED:
            out.append(src[pos:n.start_byte])
            pos = n.end_byte
        else:
            for child in n.children:
                walk(child)

    walk(node)
    out.append(src[pos:end])
    return b"".join(out).decode("utf-8", "replace")


def made(kind: str, name: str, qual: str, sig: str, doc: str, node, exported: bool | None = None) -> dict:
    return {"kind": kind, "name": name, "qual": qual, "sig": sig, "doc": doc, "node": node, "exported": exported,
            "line": node.start_point[0] + 1, "end_line": node.end_point[0] + 1}


# ---- Python ------------------------------------------------------------------------------------


def py_doc(src: bytes, node) -> str:
    body = node.child_by_field_name("body")
    if body is not None and body.named_children:
        first = body.named_children[0]
        if first.type == "expression_statement" and first.named_children and first.named_children[0].type == "string":
            return "".join(txt(src, c) for c in first.named_children[0].children if c.type == "string_content")
    return ""


def py_symbol(src: bytes, kind: str, name: str, node) -> dict:
    parents, p = [], node.parent
    while p is not None:
        if p.type in ("class_definition", "function_definition"):
            parents.append((p.type, txt(src, p.child_by_field_name("name"))))
        p = p.parent
    parents.reverse()
    if kind == "function" and parents and parents[-1][0] == "class_definition":
        kind = "method"
    body = node.child_by_field_name("body")
    if kind == "constant":
        sig, doc = clip(txt(src, node), 120), ""
    elif body is not None:
        sig = clip(src[node.start_byte:body.start_byte].decode("utf-8", "replace").rstrip().rstrip(":"), SIG_LIMIT)
        doc = py_doc(src, node)
    else:
        sig, doc = clip(txt(src, node), SIG_LIMIT), ""
    return made(kind, name, ".".join([n for _, n in parents] + [name]), sig, doc, node)


# ---- Java and TypeScript -----------------------------------------------------------------------


def c_doc(src: bytes, node) -> str:
    if node.parent is not None and node.parent.type == "export_statement":
        node = node.parent
    prev = node.prev_named_sibling
    if prev is not None and prev.type in ("block_comment", "comment") and txt(src, prev).startswith("/**") \
            and src[prev.end_byte:node.start_byte].count(b"\n") <= 1:
        return "\n".join(re.sub(r"^\s*\*\s?", "", line) for line in txt(src, prev)[3:-2].splitlines())
    return ""


def c_symbol(src: bytes, kind: str, name: str, node, java: bool) -> dict:
    parents, p = [], node.parent
    while p is not None:
        n = p.child_by_field_name("name") if p.type.endswith(("class_declaration", "interface_declaration", "enum_declaration", "record_declaration")) else None
        if n is not None:
            parents.append(txt(src, n))
        p = p.parent
    parents.reverse()
    body = node.child_by_field_name("body")
    head = src[node.start_byte:(body.start_byte if body is not None else node.end_byte)].decode("utf-8", "replace")
    exported = "public" in head.split(name)[0].split() if java else (node.parent is not None and node.parent.type == "export_statement")
    return made(kind, name, ".".join(parents + [name]), clip(head, SIG_LIMIT).rstrip(";"), c_doc(src, node), node, exported)


# ---- Haskell -----------------------------------------------------------------------------------


def hs_module(root, src: bytes) -> str | None:
    for header in (c for c in root.children if c.type == "header"):
        for m in (c for c in header.children if c.type == "module"):
            if ids := [txt(src, c) for c in m.children if c.type == "module_id"]:
                return ".".join(ids)
        if ids := [txt(src, c) for c in header.children if c.type == "module_id"]:
            return ".".join(ids)
    return None


def hs_exports(root, src: bytes) -> tuple[set[str], set[str]] | None:
    """The names an export list names, and the types it exports with all their constructors, or None where the module has no list."""
    for header in (c for c in root.children if c.type == "header"):
        for e in (c for c in header.children if c.type == "exports"):
            names, full = set(), set()
            for x in (c for c in e.named_children if c.type == "export"):
                kids = list(x.named_children)
                if kids and kids[0].type == "module":
                    continue
                name = next((re.sub(r"[()\s]", "", txt(src, c)) for c in kids if c.type in ("variable", "name", "operator", "prefix_id", "constructor")), None)
                if name is None:
                    name = re.sub(r"[()\s]", "", txt(src, x).split("(")[0] or txt(src, x))
                names.add(name)
                for c in (c for c in kids if c.type == "children"):
                    if any(g.type == "all_names" for g in c.children):
                        full.add(name)
                    names.update(re.sub(r"[()\s]", "", txt(src, g)) for g in c.named_children if g.type != "all_names")
            return names, full
    return None


def hs_hdoc(text: str) -> str:
    text = text.strip()
    if text.startswith("{-"):
        return text[2:].removesuffix("-}").lstrip("|^* ")
    return " ".join(re.sub(r"^--+\s?[|^]?\s?", "", line.strip()) for line in text.splitlines())


def hs_docs(root, src: bytes, symbols: list[dict]) -> None:
    """Attach each Haddock comment: ``-- |`` to the symbol that starts right after it, ``-- ^`` to the one that ends right before."""
    found = []

    def walk(n) -> None:
        if n.type == "haddock":
            found.append(n)
        for c in n.children:
            walk(c)

    walk(root)
    starts = sorted(symbols, key=lambda s: s["dnode"].start_byte)
    ends = sorted(symbols, key=lambda s: s["dnode"].end_byte)
    for h in found:
        text = txt(src, h)
        marker = text.lstrip("-{ ")
        if marker.startswith(("*", "$")):
            continue  # a section heading or a named chunk, not a symbol's doc
        doc = hs_hdoc(text)
        if marker.startswith("^"):
            before = [s for s in ends if s["dnode"].end_byte <= h.start_byte and not re.search(rb"\S", src[s["dnode"].end_byte:h.start_byte].replace(b",", b""))]
            before = [s for s in before if not re.search(rb"\S", src[s["dnode"].end_byte:h.start_byte])] or before
            if before:
                target = max(before, key=lambda s: (s["dnode"].end_byte, s["dnode"].start_byte))
                target["doc"] = target["doc"] or doc
            continue
        end = h.end_byte  # a haddock node is its first line only, and the rest of the block is plain comments
        while m := re.match(rb"[ \t]*\n[ \t]*(--(?!-)(?![ ]*[|^])[^\n]*)", src[end:]):
            if line := re.sub(r"^--\s?", "", m.group(1).decode("utf-8", "replace")).strip():
                doc += " " + line
            end += m.end()
        chosen = None
        for s in [s for s in starts if s["dnode"].start_byte >= end][:6]:
            between = src[end:s["dnode"].start_byte]
            if not re.search(rb"[^\s|=,{]", re.sub(rb"\{-#.*?#-\}", b"", between, flags=re.S)):
                # of several symbols from one node (foo, bar :: T) the doc goes to all of them
                if chosen is None or s["dnode"].start_byte == chosen["dnode"].start_byte:
                    chosen = chosen or s
                    s["doc"] = s["doc"] or doc
                break
            if s["dnode"].start_byte > h.end_byte + 400:
                break


def hs_owner(src: bytes, node) -> str | None:
    p = node.parent
    while p is not None:
        if p.type in ("data_type", "newtype", "class", "data_family", "type_family"):
            if (n := next((c for c in p.children if c.type == "name"), None)) is not None:
                return txt(src, n)
        p = p.parent
    return None


def hs_symbols(src: bytes, matches) -> list[dict]:
    """The symbols a file's matches define. A signature and its definition are one symbol, the signature winning, and a definition with no signature becomes a function."""
    found, seen = [], set()
    for _, caps in matches:
        for capture, nodes in caps.items():
            if not capture.startswith("definition."):
                continue
            kind, dnode = capture.split(".", 1)[1], nodes[0]
            names = caps.get("name", [])
            if kind not in ("function", "method", "unsigned"):
                names = names[:1]  # the first name child is the declared one
            for name_node in names:
                name = re.sub(r"[()\s]", "", txt(src, name_node)) if name_node.type in ("operator", "constructor_operator") else txt(src, name_node)
                owner = None
                if kind == "instance":
                    head = src[dnode.start_byte:next((c.start_byte for c in dnode.children if c.type == "instance_declarations"), dnode.end_byte)]
                    name = re.sub(r"\s*where$", "", clip(head.decode("utf-8", "replace"), 160)).replace("instance ", "", 1)
                    key = (kind, name)
                elif kind in ("constructor", "field"):
                    owner = hs_owner(src, dnode)
                    key = (kind, owner, name, dnode.start_byte)
                elif kind == "method":
                    owner = txt(src, next(c for c in dnode.parent.parent.children if c.type == "name")) if dnode.parent.parent.type == "class" else None
                    key = (kind, owner, name, 0)
                elif kind in ("function", "unsigned"):
                    key = (kind, owner, name, 0)
                else:
                    key = (kind, dnode.id)
                if key not in seen:
                    seen.add(key)
                    found.append({"kind": kind, "name": name, "owner": owner, "dnode": dnode, "doc": ""})
    signed = {s["name"] for s in found if s["kind"] == "function"}
    out, unsigned = [], set()
    for s in found:
        if s["kind"] == "unsigned":
            if s["name"] in signed or s["name"] in unsigned:
                continue
            unsigned.add(s["name"])
            s["kind"] = "function"
        out.append(s)
    return out


def hs_clause_ends(root, src: bytes) -> dict[str, int]:
    """The last line of the top-level equations of each name, so a function's source runs past its signature."""
    last: dict[str, int] = {}
    for block in (c for c in root.children if c.type == "declarations"):
        for c in (c for c in block.children if c.type in ("function", "bind")):
            first = next((x for x in c.children if x.type in ("variable", "infix")), None)
            if first is not None and (named := first if first.type == "variable" else next((x for x in first.children if x.type == "operator"), None)) is not None:
                last[re.sub(r"[()\s]", "", txt(src, named))] = c.end_point[0] + 1
    return last


def hs_signature(src: bytes, s: dict) -> str:
    n, kind = s["dnode"], s["kind"]
    if kind in ("function", "method"):
        return text_without(src, n) if n.type == "signature" else txt(src, n).split("=")[0]
    if kind in ("data", "newtype", "class", "data-family", "type-family"):
        stop = next((c.start_byte for c in n.children if c.type in ("data_constructors", "newtype_constructor", "class_declarations", "deriving", "where")), n.end_byte)
        return re.sub(r"\s*(=|where)\s*$", "", text_without(src, n, stop=stop).strip())
    return "instance " + s["name"] if kind == "instance" else text_without(src, n)


def haskell(root, src: bytes, matches) -> tuple[str | None, list[dict]]:
    module = hs_module(root, src)
    raw = hs_symbols(src, matches)
    hs_docs(root, src, raw)
    ends, listed = hs_clause_ends(root, src), hs_exports(root, src)
    out = []
    for s in raw:
        symbol = made(s["kind"], s["name"], f"{s['owner']}.{s['name']}" if s["owner"] else s["name"], clip(hs_signature(src, s), SIG_LIMIT), s["doc"], s["dnode"])
        if s["kind"] == "instance":
            symbol["qual"] = "instance " + s["name"]
        if s["kind"] in ("function", "method"):
            symbol["end_line"] = max(symbol["end_line"], ends.get(s["name"], 0))
        if listed is not None:
            symbol["exported"] = s["name"] in listed[0] or s["owner"] in listed[1]
        out.append(symbol)
    return module, out


# ---- The driver --------------------------------------------------------------------------------


def parse(language: str, src: bytes) -> tuple[str | None, list[dict]]:
    """The module a file declares, if it says so, and its symbols. Raises whatever the grammar or a deeply nested tree raises, which the caller counts against this file alone."""
    ts, parser, query = _language(language)
    root = parser.parse(src).root_node
    matches = ts.QueryCursor(query).matches(root)
    if language == "haskell":
        module, symbols = haskell(root, src, matches)
    else:
        module, symbols, seen = None, [], set()
        if language == "java" and (package := next((c for c in root.children if c.type == "package_declaration"), None)):
            module = txt(src, package.named_children[0])
        for _, caps in matches:
            for capture, nodes in caps.items():
                if capture.startswith("definition."):
                    for name in caps.get("name", []):
                        if (key := (capture, nodes[0].id, name.id)) not in seen:
                            seen.add(key)
                            kind = capture.split(".", 1)[1]
                            symbols.append(py_symbol(src, kind, txt(src, name), nodes[0]) if language == "python" else c_symbol(src, kind, txt(src, name), nodes[0], language == "java"))
    for s in symbols:
        s["doc"] = clip(s["doc"], DOC_LIMIT) if s["doc"] else ""
        del s["node"]
    return module, symbols
