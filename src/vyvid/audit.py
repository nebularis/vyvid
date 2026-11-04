# SPDX-License-Identifier: MIT
"""``vyd domain audit <folder>``: the facts about a folder that someone else wrote, before it is trusted.

It reads the folder and runs nothing from it, and it needs no configuration. A finding is
``path:line kind text``, line 0 meaning the file as a whole. The audit decides nothing. A person or
the review skill reads the findings.
"""

from __future__ import annotations

import json
import os
import re
import tomllib
import unicodedata
from dataclasses import asdict, dataclass
from pathlib import Path

import platformdirs

from .config import MANIFEST_REFUSED, NAME_RE, leaving
from .patterns import Pattern

TEXT_SUFFIXES = {".md", ".toml", ".ttl", ".txt"}
LICENCE_RE = re.compile(r"^(licen[cs]e|copying|notice)", re.I)
CUT = 120
MAX_BYTES = 2_000_000
# A string that makes a pattern with nested repetition run for ever, a few characters at a time.
ADVERSARIAL = [c * 40 + "!" for c in "aAC1-_ "]
COMMIT_RE = re.compile(r"^[0-9a-f]{7,64}$")
BASE64_RE = re.compile(r"[A-Za-z0-9+/]{80,}={0,2}")
URL_RE = re.compile(r"\b(?:https?|ftp|ssh|git)://\S+", re.I)
HTML_COMMENT = "<!--"
# ``scope:ID-12``. The identifier is upper case with a dash and a digit, so a URL, ``xsd:long`` and a SPARQL prefix do not match.
CITES_RE = re.compile(r"(?<![\w/.:-])(?P<scope>[a-z][a-z0-9-]*):(?P<id>[A-Z][A-Z0-9]*-(?=[A-Za-z0-9.-]*\d)[A-Za-z0-9][A-Za-z0-9.-]*)")
COMMANDS = re.compile(
    r"\b(?:curl|wget)\b|\|\s*(?:ba|z)?sh\b|\bsudo\b|\brm\s+-\w*[rf]|\bchmod\s+\+x|\bpip3?\s+install|\bnpx\b|\beval\b|\b(?:ba|z)?sh\s+-c\b", re.I)


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    kind: str
    text: str

    def __str__(self) -> str:
        return f"{self.path}:{self.line} {self.kind} {self.text}"


def _cut(text: str) -> str:
    text = text.strip()
    return text if len(text) <= CUT else text[: CUT - 1] + "…"


def _visible(line: str) -> str:
    """The line with each invisible character written as its code point."""
    return "".join(f"<U+{ord(c):04X}>" if unicodedata.category(c) == "Cf" else c for c in line)


def hidden(text: str) -> list[str]:
    """The kinds of hidden text a line holds: ``invisible`` for a format character, ``html-comment`` for a comment."""
    return [kind for kind, hit in (("invisible", any(unicodedata.category(c) == "Cf" for c in text)), ("html-comment", HTML_COMMENT in text)) if hit]


def _files(folder: Path) -> list[Path]:
    """Every file and every link in the folder, without following a link and without the ``.git`` folder."""
    found: list[Path] = []
    for here, dirs, names in os.walk(folder, followlinks=False):
        dirs[:] = sorted(d for d in dirs if d != ".git")
        found += [Path(here) / n for n in sorted(names)]
        found += [Path(here) / d for d in dirs if (Path(here) / d).is_symlink()]
    return found


def _layout(folder: Path, path: Path) -> list[Finding]:
    """Links, files that are not text, and executable files."""
    rel = path.relative_to(folder).as_posix()
    if path.is_symlink():
        target = os.readlink(path)
        outside = not Path(os.path.realpath(path)).is_relative_to(Path(os.path.realpath(folder)))
        return [Finding(rel, 0, "symlink", ("leaves the folder " if outside else "") + f"-> {target}")]
    out = []
    if path.suffix.lower() not in TEXT_SUFFIXES and not LICENCE_RE.match(path.name):
        out.append(Finding(rel, 0, "file-type", f"{path.suffix or path.name} is not Markdown, TOML, Turtle, plain text or a licence"))
    if path.stat().st_mode & 0o111:
        out.append(Finding(rel, 0, "executable", "has an executable bit"))
    return out


def _line_of(text: str, needle: str) -> int:
    return next((n for n, line in enumerate(text.splitlines(), 1) if needle in line), 1)


def _manifest(folder: Path) -> list[Finding]:
    """What the manifest names that it may not, and each family pattern run against a short hostile string."""
    path = folder / "domain.toml"
    if path.is_symlink() or not path.is_file():
        return []
    text = path.read_text(encoding="utf-8", errors="replace")
    try:
        manifest = tomllib.loads(text)
    except tomllib.TOMLDecodeError as error:
        return [Finding("domain.toml", 0, "manifest", f"does not parse ({error})")]
    out = [Finding("domain.toml", _line_of(text, key), "manifest-key", f"sets '{key}', which only the user's configuration may")
           for key in MANIFEST_REFUSED if key in manifest]
    out += [Finding("domain.toml", _line_of(text, value), "manifest-path", f"{key} names '{value}', which leaves the folder")
            for key, value in leaving(manifest, folder)]
    families = manifest.get("families")
    for name, spec in families.items() if isinstance(families, dict) else []:
        source = spec.get("pattern") if isinstance(spec, dict) else None
        if not isinstance(source, str):
            continue
        try:
            pattern = Pattern(source)
        except Exception as error:
            out.append(Finding("domain.toml", _line_of(text, source), "pattern-invalid", f"family {name}: {error}"))
            continue
        for probe in ADVERSARIAL:
            pattern.search(probe)
            pattern.fullmatch(probe)
            if pattern.timed_out:
                out.append(Finding("domain.toml", _line_of(text, source), "pattern-timeout", f"family {name}: {_cut(source)}"))
                break
    return out


def _content(folder: Path, path: Path, scopes: set[str]) -> list[Finding]:
    """Invisible characters, comments, encoded blobs, URLs, command-shaped lines and qualified mentions
    of a scope outside ``scopes``, by line."""
    rel = path.relative_to(folder).as_posix()
    data = path.read_bytes()[:MAX_BYTES]
    if b"\0" in data:
        return []
    out = []
    for n, raw in enumerate(data.decode("utf-8", errors="replace").splitlines(), 1):
        line = raw.removeprefix("﻿") if n == 1 else raw
        kinds = hidden(line) + [kind for kind, hit in (("base64", BASE64_RE.search(line)), ("url", URL_RE.search(line)), ("command", COMMANDS.search(line))) if hit]
        out += [Finding(rel, n, kind, _cut(_visible(line))) for kind in kinds]
        out += [Finding(rel, n, "qualified-mention", f"{m.group(0)} names the scope '{m.group('scope')}'") for m in CITES_RE.finditer(line)
                if m.group("scope") not in scopes]
    return out


def own_name(folder: Path) -> str:
    """The domain's name: ``name`` in its ``domain.toml`` if it sets one, else its folder's."""
    try:
        name = tomllib.loads((folder / "domain.toml").read_text(encoding="utf-8")).get("name")
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError):
        name = None
    return name if isinstance(name, str) else folder.name


def audit(folder: Path, allow: tuple[str, ...] = ()) -> list[Finding]:
    """Every finding in the folder. Nothing in it is run, imported or followed through a link.
    A qualified mention is a finding unless it names the domain itself or a scope in ``allow``, such as a parent."""
    folder = folder.resolve()
    scopes = {own_name(folder), *allow}
    out = _manifest(folder)
    for path in _files(folder):
        out += _layout(folder, path)
        if not path.is_symlink():
            out += _content(folder, path, scopes)
    return [Finding(f.path, f.line, f.kind, _cut(f.text)) for f in out]


def review_path(domain: str, commit: str) -> Path:
    """Where the review of a domain at a commit is recorded. Raises ValueError for a name that is not safe in a path."""
    if not NAME_RE.match(domain) or not COMMIT_RE.match(commit):
        raise ValueError("a review is named by a domain name and a commit hash in hexadecimal")
    return platformdirs.user_data_path("vyvid") / "reviews" / domain / f"{commit}.md"


def command(folder: Path, as_json: bool, allow: tuple[str, ...] = ()) -> int:
    """Print the findings, plain or as JSON. Returns 1 if there are any."""
    if not folder.is_dir():
        print(f"vyd: {folder} is not a folder")
        return 2
    found = audit(folder, allow)
    if as_json:
        print(json.dumps([asdict(f) for f in found], indent=2, ensure_ascii=False))
    else:
        for f in found:
            print(f)
        if not found:
            print("no findings")
    return 1 if found else 0
