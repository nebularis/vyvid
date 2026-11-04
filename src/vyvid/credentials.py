# SPDX-License-Identifier: MIT
"""Credentials: where a value has a fixed place it is refused by its shape, and only free text is scanned.

A remote URL, a credential setting and a file about to be staged are checked by their form. Text a
command printed is scanned for known formats and redacted. There is no entropy check, because these
repositories are full of commit hashes and digests. Scanning catches an accident, not someone who
encodes a secret. Nothing here ever returns the credential it found, only where it is and the rule.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from urllib.parse import urlsplit

# Each rule is a name and a pattern. A prefix not at the start of a word is not a match, and each
# has a minimum length, so ``sk-`` in prose or a short example is left alone. The first rule wins an overlap.
RULES = (
    ("private-key", re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY(?: BLOCK)?-----")),
    ("github-token", re.compile(r"(?<![A-Za-z0-9])gh[pousr]_[A-Za-z0-9]{36,}")),
    ("github-pat", re.compile(r"(?<![A-Za-z0-9])github_pat_[A-Za-z0-9_]{50,}")),
    ("gitlab-token", re.compile(r"(?<![A-Za-z0-9])glpat-[A-Za-z0-9_-]{20,}")),
    ("aws-key-id", re.compile(r"(?<![A-Z0-9])(?:AKIA|ASIA)[A-Z0-9]{16}(?![A-Z0-9])")),
    ("slack-token", re.compile(r"(?<![A-Za-z0-9])xox[bpa]-[A-Za-z0-9-]{10,}")),
    ("anthropic-key", re.compile(r"(?<![A-Za-z0-9])sk-ant-[A-Za-z0-9_-]{20,}")),
    ("api-key", re.compile(r"(?<![A-Za-z0-9])sk-[A-Za-z0-9_-]{32,}")),
    ("google-key", re.compile(r"(?<![A-Za-z0-9])AIza[A-Za-z0-9_-]{35}")),
    ("bearer-token", re.compile(r"(?<![A-Za-z0-9])Bearer\s+[A-Za-z0-9._~+/=-]{20,}")),
)
CREDENTIAL_KEYS = ("credential", "credentials", "token", "password", "secret", "api_key")
CREDENTIAL_SUFFIXES = ("_token", "_password", "_secret", "_key")
REFERENCES = ("env:", "keychain:")


def _matches(text: str) -> list[tuple[int, int, str]]:
    """Every match as start, end and rule, in order of position, none overlapping an earlier rule's."""
    found: list[tuple[int, int, str]] = []
    for rule, pattern in RULES:
        for m in pattern.finditer(text):
            if not any(m.start() < end and start < m.end() for start, end, _ in found):
                found.append((m.start(), m.end(), rule))
    return sorted(found)


def scan(text: str) -> list[tuple[int, str]]:
    """The line number and rule of each known credential format in the text."""
    return [(text.count("\n", 0, start) + 1, rule) for start, _, rule in _matches(text)]


def redact(text: str) -> str:
    """The text with each known credential format replaced by ``[redacted]``."""
    out, at = [], 0
    for start, end, _ in _matches(text):
        out += [text[at:start], "[redacted]"]
        at = end
    return "".join(out + [text[at:]])


def remote_problem(url: str) -> str | None:
    """Why a remote URL may not be kept, or None. Never contains the URL."""
    parts = urlsplit(url)
    if parts.query or parts.fragment:
        return "has a query or a fragment, which may hold a credential"
    if "://" in url:
        if parts.password is not None:
            return "has a password. Remove it and use a credential helper or an ssh key"
        if parts.scheme in ("http", "https") and parts.username is not None:
            return "has a user part, which may be a token. Remove the user part and use a credential helper"
    elif ":" in url.split("/", 1)[0].rpartition("@")[0]:  # user:password@host:path
        return "has a password. Remove it and use a credential helper or an ssh key"
    if hits := scan(url):
        return f"holds text shaped like a credential ({hits[0][1]})"
    return None


def host_of(url: str) -> str:
    """The host of a remote in any of its forms, for naming it without its user part or path."""
    host = urlsplit(url).hostname if "://" in url else url.split("/", 1)[0].rpartition("@")[2].split(":", 1)[0]
    return redact(host or "")


def credential_problems(settings: dict, where: str) -> list[str]:
    """A key that names a credential must hold ``env:`` or ``keychain:``. Names the key, never the value."""
    problems = []
    for key, value in settings.items():
        if isinstance(value, dict):
            problems += credential_problems(value, f"{where}, {key}")
        elif isinstance(key, str) and (key in CREDENTIAL_KEYS or key.endswith(CREDENTIAL_SUFFIXES)) \
                and not (isinstance(value, str) and value.startswith(REFERENCES)):
            problems.append(f"{where}: '{key}' must start with env: or keychain:, so no credential sits in the configuration")
    return problems


def scan_file(path: Path) -> list[tuple[int, str]]:
    """The known formats in a file, none for one that cannot be read."""
    try:
        return scan(path.read_bytes().decode("utf-8", errors="replace"))
    except OSError:
        return []


def private_dir(path: Path) -> None:
    """Create a folder owner-only, and tighten one that exists. Where chmod means little, it does nothing."""
    path.mkdir(parents=True, exist_ok=True)
    try:
        path.chmod(0o700)
    except OSError:
        pass


def private_file(path: Path) -> None:
    """Create an empty file owner-only if it is not there. An existing file keeps its mode."""
    if not path.exists():
        os.close(os.open(path, os.O_WRONLY | os.O_CREAT, 0o600))
