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
        if first.type == "expression_statement" and first.named_children:
            literal = first.named_children[0]
            parts = [literal] if literal.type == "string" else [c for c in literal.named_children if c.type == "string"] if literal.type == "concatenated_string" else []
            if not any(set(txt(src, p.children[0]).lower()) & set("fbt") for p in parts):  # an f-string or bytes literal is no __doc__
                return "".join(txt(src, c) for p in parts for c in p.children if c.type == "string_content")
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
        colon = next(c for c in node.children if c.type == ":")  # the block starts after any comment that follows the colon
        sig = clip(text_without(src, node, colon.start_byte).rstrip(), SIG_LIMIT)
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


# ---- What authors wrote around the code --------------------------------------------------------

DOC_WINDOW, DOC_OVERLAP, DOC_MIN = 900, 150, 80
META = re.compile(r"^(module|copyright|licen[sc]e|maintainer|stability|portability|author|spdx-license-identifier)\s*:|^(copyright|spdx-license-identifier)\b", re.I)
LICENCE = re.compile(r"licensed under|all rights reserved|permission is hereby granted|without warranty", re.I)
HEADING = re.compile(r"^\[([^\]]{2,80})\]$")
UNDERLINE = re.compile(r"^(={3,}|-{3,}|~{3,})$")
RULE = re.compile(r"^[-=~#*_/\\ ]{3,}$")


def hs_blocks(text: str) -> list[tuple[list[tuple[int, str]], bool]]:
    """The comments at the left margin of a Haskell file that are not a declaration's Haddock, as numbered lines and whether the module follows.
    A ``{- ... -}`` block, a run of ``--`` lines, or ``-- $name``. Nested block comments are not tracked."""
    lines, out, i = text.splitlines(), [], 0

    def header(end: int) -> bool:
        rest = next((x for x in lines[end:] if x.strip() and not x.startswith("{-#")), "")
        return rest.startswith("module ")

    while i < len(lines):
        if lines[i].startswith("{-") and not lines[i].startswith("{-#"):
            j = i
            while "-}" not in lines[j] and j + 1 < len(lines):
                j += 1
            body = [(n + 1, lines[n]) for n in range(i, j + 1)]
            body[0] = (body[0][0], re.sub(r"^\{-\s*\|?\s?", "", body[0][1]))
            body[-1] = (body[-1][0], body[-1][1].split("-}")[0])
            out.append((body, header(j + 1)))
            i = j + 1
        elif lines[i].startswith("--"):
            j = i
            while j + 1 < len(lines) and lines[j + 1].startswith("--"):
                j += 1
            body = [(n + 1, re.sub(r"^--+ ?", "", lines[n])) for n in range(i, j + 1)]
            is_header = header(j + 1)
            first = next((t for _, t in body if t.strip() and not RULE.match(t.strip())), "").lstrip()
            if first.startswith("|"):
                at = next(k for k, (_, t) in enumerate(body) if t.strip().startswith("|"))
                body[at] = (body[at][0], body[at][1].replace("|", "", 1))
            if (is_header or (not first.startswith(("|", "^", "*")) and len(body) >= 3)):
                if first.startswith("$"):
                    body = [(n, t) if t.strip() != first.strip() else (n, f"[{first.strip()[1:]}]") for n, t in body]
                out.append((body, is_header))
            i = j + 1
        else:
            i += 1
    return out


def py_blocks(src: bytes) -> list[tuple[list[tuple[int, str]], bool]]:
    """The module docstring and the runs of at least three ``#`` lines at the left margin of a Python file."""
    _, parser, _ = _language("python")
    root = parser.parse(src).root_node
    out, run = [], []

    def flush() -> None:
        if len(run) >= 3:
            out.append(([(c.start_point[0] + 1, re.sub(r"^#+ ?", "", txt(src, c))) for c in run], False))
        run.clear()

    first = next((c for c in root.named_children if c.type != "comment"), None)
    if first is not None and first.type == "expression_statement" and first.named_children and first.named_children[0].type == "string":
        s = first.named_children[0]
        body = re.match(r"^[rRuU]*(\"\"\"|'''|\"|')(.*)\1$", txt(src, s), re.S)
        if body:
            out.append(([(s.start_point[0] + 1 + k, t) for k, t in enumerate(body.group(2).splitlines())], True))
    for c in root.children:
        if c.type == "comment" and c.start_point[1] == 0 and (not run or c.start_point[0] == run[-1].start_point[0] + 1):
            run.append(c)
        else:
            flush()
            if c.type == "comment" and c.start_point[1] == 0:
                run.append(c)
    flush()
    return out


def c_blocks(src: bytes, java: bool) -> list[tuple[list[tuple[int, str]], bool]]:
    """The comment that opens a Java or TypeScript file, where it is followed by a package or an import and so is not a class's own doc."""
    _, parser, _ = _language("typescript" if not java else "java")
    kids = parser.parse(src).root_node.children
    if len(kids) > 1 and kids[0].type in ("block_comment", "comment") and txt(src, kids[0]).startswith("/*") and kids[1].type in ("package_declaration", "import_declaration", "import_statement"):
        return [([(kids[0].start_point[0] + 1 + k, re.sub(r"^\s*(/\*+|\*+/|\*)\s?", "", t)) for k, t in enumerate(txt(src, kids[0]).splitlines())], True)]
    return []


def split_sections(block: list[tuple[int, str]]) -> list[tuple[str, list[tuple[int, str]]]]:
    """A block's lines without licence and metadata lines, cut into ``(heading, lines)`` at ``[Heading]`` lines and at underlined headings."""
    sections: list[tuple[str, list[tuple[int, str]]]] = [("", [])]
    for k, (n, t) in enumerate(block):
        t = t.rstrip()
        if (m := HEADING.match(t.strip())) or (t.strip() and k + 1 < len(block) and UNDERLINE.match(block[k + 1][1].strip()) and len(t.strip()) < 80):
            sections.append((m.group(1) if m else t.strip(), [(n, "")]))
        elif META.match(t.strip()) or RULE.match(t.strip()) or UNDERLINE.match(t.strip()):
            continue
        else:
            sections[-1][1].append((n, t))
    return [(h, lines) for h, lines in sections if any(t.strip() for _, t in lines)]


def windows(lines: list[tuple[int, str]]) -> list[list[tuple[int, str]]]:
    """Lines cut into windows of about ``DOC_WINDOW`` characters, each starting with the last lines of the one before, up to ``DOC_OVERLAP`` characters."""
    out, cur, fresh = [], [], 0
    for line in lines:
        if cur and fresh and sum(len(t) + 1 for _, t in cur) + len(line[1]) > DOC_WINDOW:
            out.append(cur)
            tail, size = [], 0
            for x in reversed(cur):
                if size >= DOC_OVERLAP:
                    break
                tail.insert(0, x)
                size += len(x[1]) + 1
            cur, fresh = tail, 0
        cur.append(line)
        fresh += 1
    return out + [cur] if fresh else out


def slug(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-")


def docs(language: str, src: bytes) -> list[dict]:
    """The prose around the code as chunks shaped like symbols, of kind ``doc``: ``name`` is the heading, ``qual`` is its slug or ``L<line>`` with ``+n`` for a later window,
    and ``doc`` is the text. Haskell reads its module header, ``-- $name`` sections, block comments and runs of ``--`` lines, Python its module docstring and runs of
    ``#`` lines, Java and TypeScript only a header comment followed by a package or an import. A chunk under ``DOC_MIN`` characters or holding a licence is dropped."""
    blocks = hs_blocks(src.decode("utf-8", "replace")) if language == "haskell" else py_blocks(src) if language == "python" else c_blocks(src, language == "java")
    out = []
    for block, is_header in blocks:
        for heading, lines in split_sections(block):
            start = next((n for n, t in lines if t.strip()), lines[0][0])
            base = slug(heading) or f"L{start}"
            for k, window in enumerate(windows(lines), 1):
                body = "\n".join(t.strip() for _, t in window).strip()
                if (len(body) < DOC_MIN and not (language == "python" and is_header and body)) or LICENCE.search(body):
                    continue
                shown = [n for n, t in window if t.strip()]
                out.append({"kind": "doc", "name": heading or ("module header" if is_header else "note"), "qual": base if k == 1 else f"{base}+{k}",
                            "sig": "", "doc": body, "line": shown[0], "end_line": shown[-1], "exported": None})
    return out
