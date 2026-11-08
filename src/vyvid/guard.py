# SPDX-License-Identifier: MIT
"""Keep a user's private terms out of public repositories.

The code here holds no term and no list. A user names domains in ``[framework.guard]``, and each holds a ``guard`` folder of
files (a domain's root also supplies ``upstreams`` and ``private-upstreams``):

``upstreams``, ``private-upstreams``  the repositories that are public, and those that are private and guarded, as ``host/owner/repo``
``deny-terms``                        a regular expression per line, applied to every guarded repository
``public-deny-terms``                 the same, applied to public repositories alone
``warn-terms``                        the same for public repositories, and a match warns and does not block
``never-track``                       path globs no commit may add
``sensitive-paths``                   ``repo: glob`` or a bare glob, where a commit must carry a ``Placement:`` trailer
``allow``                             names of built-in patterns to switch off

A line that starts ``!`` in a terms file names a path glob to skip, and ``#`` starts a comment.

The repository's class comes from its remotes, so a check cannot be forgotten. A repository under a watched owner that is in
neither list fails closed. A finding names the file, the line and the entry's number in its list, never the term.
"""

from __future__ import annotations

import fnmatch
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

import platformdirs
import regex

from .citations import GitError, git, parse_diff
from .config import Config
from .patterns import Pattern
from .resolve import normalise_remote, remotes

LISTS = ("deny-terms", "public-deny-terms", "warn-terms")
SKIP_ENV = "VYD_GUARD_SKIP"
TRAILER_RE = re.compile(r"^Placement:\s*\S", re.I | re.M)
NO_COMMIT = "0" * 40
GUARDED_HOOKS = ("pre-commit", "commit-msg", "pre-push")
# Every client-side hook git runs, so that a shim chains to the repository's own and none stops running when hooksPath moves.
ALL_HOOKS = ("applypatch-msg", "pre-applypatch", "post-applypatch", "pre-commit", "pre-merge-commit", "prepare-commit-msg", "commit-msg",
             "post-commit", "pre-rebase", "post-checkout", "post-merge", "pre-push", "pre-auto-gc", "post-rewrite", "post-update",
             "push-to-checkout", "reference-transaction", "sendemail-validate", "fsmonitor-watchman")

# Generic patterns, shipped with the code. A user's ``allow`` file switches one off by name. ``everywhere`` ones also guard private repositories.
BUILTIN = {
    "home-path": (r"(?<![\w.~$])(?:/Users|/home)/(?!(?:example|user|username|you|name|me|runner|vscode|node)/)[A-Za-z0-9._-]+/"
                  r"|\b[A-Za-z]:\\Users\\(?!(?:example|user|username|you|name|me)\\)[^\\\s<>%$]+\\", False),
    "private-key": (r"-----BEGIN (?:[A-Z]+ )*PRIVATE KEY-----", True),
    "token": (r"\b(?:ghp_[A-Za-z0-9]{36}|github_pat_[A-Za-z0-9_]{40,}|AKIA[0-9A-Z]{16}|xox[baprs]-[A-Za-z0-9-]{10,}|sk-ant-[A-Za-z0-9_-]{20,})\b", True),
}
ADVICE = ("A guarded repository must not hold what is listed. Do not bypass this check. Report the findings to the maintainer "
          "by file and line, and propose a change that keeps the meaning without them. Only the maintainer may override, with "
          f"{SKIP_ENV}=\"<reason>\", which is logged.")


@dataclass(frozen=True)
class Entry:
    pattern: Pattern
    source: str  # the list it came from
    number: int  # its line in that file


@dataclass
class Lists:
    public: set[str] = field(default_factory=set)
    private: set[str] = field(default_factory=set)
    deny: list[Entry] = field(default_factory=list)
    public_deny: list[Entry] = field(default_factory=list)
    warn: list[Entry] = field(default_factory=list)
    skips: tuple[str, ...] = ()
    never_track: tuple[str, ...] = ()
    sensitive: tuple[tuple[str | None, str], ...] = ()
    allow: frozenset[str] = frozenset()
    problems: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Verdict:
    kind: str  # public, private, unclassified or none
    repo: str = ""  # the remote that decided it


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    what: str
    warn: bool = False

    def __str__(self) -> str:
        return f"{self.path}:{self.line}: {'warning, ' if self.warn else ''}{self.what}" if self.line else f"{self.path}: {'warning, ' if self.warn else ''}{self.what}"


def _lines(path: Path) -> list[tuple[int, str]]:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return []
    return [(n, raw.strip()) for n, raw in enumerate(text.splitlines(), 1) if raw.strip() and not raw.strip().startswith("#")]


def read_lists(config: Config) -> Lists:
    """The lists the user's guard domains hold, merged, with the extra term files of the configuration."""
    out = Lists()
    skips: list[str] = []
    never: list[str] = []
    sensitive: list[tuple[str | None, str]] = []
    allow: set[str] = set()

    def terms(path: Path, source: str, into: list[Entry]) -> None:
        for number, line in _lines(path):
            if line.startswith("!"):
                skips.append(line[1:].strip())
                continue
            try:
                into.append(Entry(Pattern(line, regex.IGNORECASE), source, number))
            except regex.error:
                out.problems.append(f"{source} line {number} is not a regular expression, so it is skipped")

    targets = {"deny-terms": out.deny, "public-deny-terms": out.public_deny, "warn-terms": out.warn}
    for name in config.guard.domains:
        folder = config.domains[name].path
        if folder is None:
            continue
        for kind, into in (("upstreams", out.public), ("private-upstreams", out.private)):
            for place in (folder / "guard" / kind, folder / kind):
                into.update(normalise_remote(line) for _, line in _lines(place))
        for source, into in targets.items():
            terms(folder / "guard" / source, source, into)
        never += [line for _, line in _lines(folder / "guard" / "never-track")]
        for _, line in _lines(folder / "guard" / "sensitive-paths"):
            repo, sep, glob = line.partition(": ")
            sensitive.append((normalise_remote(repo), glob.strip()) if sep and "/" in repo and " " not in repo else (None, line))
        allow |= {line for _, line in _lines(folder / "guard" / "allow")}
    for extra in config.guard.terms:
        terms(extra, "deny-terms", out.deny)
    for extra in config.guard.public_terms:
        terms(extra, "public-deny-terms", out.public_deny)
    out.skips, out.never_track, out.sensitive, out.allow = tuple(skips), tuple(never), tuple(sensitive), frozenset(allow)
    return out


def classify(config: Config, lists: Lists, folder: Path) -> Verdict:
    """public or private when a remote is listed, unclassified when one is under a watched owner and listed nowhere, else none."""
    if not config.guard.on:
        return Verdict("none")
    found = remotes(folder) if folder.exists() else []
    for kind, listed in (("public", lists.public), ("private", lists.private)):
        for remote in found:
            if remote in listed:
                return Verdict(kind, remote)
    for remote in found:
        if any(remote.startswith(owner + "/") for owner in config.guard.watch_owners):
            return Verdict("unclassified", remote)
    return Verdict("none")


# ---- the checks -----------------------------------------------------------------------------------


def _skipped(lists: Lists, path: str) -> bool:
    return any(fnmatch.fnmatch(path, g) or fnmatch.fnmatch("/" + path, g) for g in lists.skips)


def check_lines(lists: Lists, kind: str, lines: list[tuple[str, int, str]], message: bool = False) -> list[Finding]:
    """A finding for each added line that matches a term that applies to a repository of this ``kind``, and each built-in pattern."""
    terms = [("block", lists.deny)] + ([("block", lists.public_deny), ("warn", lists.warn)] if kind == "public" else [])
    built = [(name, Pattern(source)) for name, (source, everywhere) in BUILTIN.items() if name not in lists.allow and (everywhere or kind == "public")]
    out: list[Finding] = []
    for path, number, text in lines:
        if not message and _skipped(lists, path):
            continue
        for mode, entries in terms:
            for entry in entries:
                if entry.pattern.search(text):
                    out.append(Finding(path, number, f"matches {entry.source}:{entry.number}", warn=mode == "warn"))
        for name, pattern in built:
            if pattern.search(text):
                out.append(Finding(path, number, f"matches the built-in pattern {name}"))
    return out


def check_message(lists: Lists, kind: str, text: str) -> list[Finding]:
    body = [line for line in text.splitlines() if not line.startswith("#")]
    return check_lines(lists, kind, [("the commit message", n, line) for n, line in enumerate(body, 1)], message=True)


def check_paths(lists: Lists, kind: str, repo: str, paths: list[str], message: str | None) -> list[Finding]:
    """A finding for a path no commit may add, and, in a public repository, for a commit that touches a sensitive path and has no Placement trailer."""
    out = [Finding(p, 0, "is a path that is never tracked") for p in paths if any(fnmatch.fnmatch(p, g) or fnmatch.fnmatch("/" + p, g) for g in lists.never_track)]
    if kind == "public" and message is not None and not TRAILER_RE.search(message):
        touched = [p for p in paths if any((r is None or r == repo) and fnmatch.fnmatch(p, g) for r, g in lists.sensitive)]
        if touched:
            out.append(Finding(touched[0], 0, f"is one of {len(touched)} sensitive path(s) of this commit, which needs a Placement trailer such as 'Placement: T1, public applied'"))
    return out


# ---- the override ---------------------------------------------------------------------------------


def skip_reason() -> str:
    return os.environ.get(SKIP_ENV, "").strip()


def log_skip(hook: str, verdict: Verdict, reason: str) -> None:
    path = platformdirs.user_state_path("vyvid") / "guard-skips.log"
    path.parent.mkdir(parents=True, exist_ok=True)
    clean = " ".join(reason.split())
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(f"{time.strftime('%Y-%m-%dT%H:%M:%S%z')}\t{hook}\t{verdict.kind}\t{verdict.repo}\t{clean}\n")


# ---- what a hook reads ----------------------------------------------------------------------------


def _split(raw: str) -> list[str]:
    return [p for p in raw.split("\0") if p]


def staged(folder: Path) -> tuple[list[tuple[str, int, str]], list[str]]:
    diff = ["-c", "core.quotepath=off", "diff", "--cached", "--no-color", "--no-ext-diff", "--diff-filter=ACMR"]
    lines = parse_diff(git(folder, *diff, "-U0", "--src-prefix=a/", "--dst-prefix=b/"))
    return lines, _split(git(folder, *diff, "--name-only", "-z"))


def commit_data(folder: Path, sha: str) -> tuple[str, list[tuple[str, int, str]], list[str]]:
    """The message, added lines and paths of one commit, with no lines for a merge."""
    message = git(folder, "log", "-1", "--format=%B", sha)
    parents = git(folder, "log", "-1", "--format=%P", sha).split()
    if len(parents) > 1:
        return message, [], []
    show = ["-c", "core.quotepath=off", "show", "--format=", "--no-color", "--no-ext-diff", "--diff-filter=ACMR"]
    lines = parse_diff(git(folder, *show, "-U0", "--src-prefix=a/", "--dst-prefix=b/", sha))
    return message, lines, _split(git(folder, *show, "--name-only", "-z", sha))


def pushed(folder: Path, remote: str, stdin: str) -> list[str]:
    """The commits a push would send, from the lines git gives a pre-push hook."""
    shas: list[str] = []
    for line in stdin.splitlines():
        parts = line.split()
        if len(parts) != 4 or parts[1] == NO_COMMIT:
            continue
        local, old = parts[1], parts[3]
        span = f"{old}..{local}" if old != NO_COMMIT else local
        extra = [] if old != NO_COMMIT else ["--not", f"--remotes={remote}" if remote else "--remotes"]
        shas += git(folder, "rev-list", "--reverse", span, *extra).split()
    return list(dict.fromkeys(shas))


# ---- the hooks ------------------------------------------------------------------------------------


def report(findings: list[Finding], verdict: Verdict, hook: str) -> int:
    blocking = [f for f in findings if not f.warn]
    for f in findings:
        print(f"vyd guard: {f}", file=sys.stderr)
    if blocking:
        print(f"vyd guard: {len(blocking)} finding(s) in a {verdict.kind} repository, so this {hook} stops. {ADVICE}", file=sys.stderr)
        return 1
    return 0


def run_hook(config: Config, hook: str, args: list[str], stdin: str, folder: Path) -> int:
    lists = read_lists(config)
    verdict = classify(config, lists, folder)
    if verdict.kind == "none":
        return 0
    if reason := skip_reason():
        log_skip(hook, verdict, reason)
        print(f"vyd guard: skipped at the maintainer's word ({SKIP_ENV}), and logged", file=sys.stderr)
        return 0
    if verdict.kind == "unclassified":
        print(f"vyd guard: this repository ({verdict.repo}) is under a watched owner and is in neither list, so this {hook} stops until the maintainer "
              f"classifies it in the guard's upstreams or private-upstreams. Do not bypass this check. Tell the maintainer, who may also override with {SKIP_ENV}=\"<reason>\".", file=sys.stderr)
        return 1
    try:
        findings: list[Finding] = []
        if hook == "pre-commit":
            lines, paths = staged(folder)
            findings = check_lines(lists, verdict.kind, lines) + check_paths(lists, verdict.kind, verdict.repo, paths, None)
        elif hook == "commit-msg":
            text = Path(args[0]).read_text(encoding="utf-8", errors="replace") if args else ""
            _, paths = staged(folder)
            findings = check_message(lists, verdict.kind, text) + check_paths(lists, verdict.kind, verdict.repo, paths, text)
        elif hook == "pre-push":
            for sha in pushed(folder, args[0] if args else "", stdin):
                message, lines, paths = commit_data(folder, sha)
                found = (check_message(lists, verdict.kind, message) + check_lines(lists, verdict.kind, lines)
                         + check_paths(lists, verdict.kind, verdict.repo, paths, message))
                findings += [Finding(f"{sha[:10]} {f.path}", f.line, f.what, f.warn) for f in found]
    except (GitError, OSError) as error:
        print(f"vyd guard: could not read the change ({error}), so it was not checked", file=sys.stderr)
        return 0
    return report(findings, verdict, hook)


def check_tree(config: Config, folder: Path) -> tuple[Verdict, list[Finding]]:
    """Every tracked text file against the lists: the debt a new list leaves in existing text."""
    lists = read_lists(config)
    verdict = classify(config, lists, folder)
    if verdict.kind in ("none", "unclassified"):
        return verdict, []
    names = _split(git(folder, "-c", "core.quotepath=off", "ls-files", "-z"))
    lines: list[tuple[str, int, str]] = []
    for name in names:
        try:
            lines += [(name, n, t) for n, t in enumerate((folder / name).read_text(encoding="utf-8").splitlines(), 1)]
        except (OSError, UnicodeError):
            continue
    return verdict, check_lines(lists, verdict.kind, lines) + check_paths(lists, verdict.kind, verdict.repo, names, None)


# ---- the user-level hooks -------------------------------------------------------------------------


def hook_dir() -> Path:
    return platformdirs.user_data_path("vyvid") / "git-hooks"


def shim(name: str) -> str:
    """A hook that runs the guard where it applies, then the repository's own hook of the same name."""
    guarded = name in GUARDED_HOOKS
    read = 'input=$(mktemp) && cat > "$input"' if name == "pre-push" else 'input=/dev/null'
    run = ('if command -v vyd >/dev/null 2>&1; then\n  vyd guard hook "$hook" "$@" < "$input" || { status=$?; [ "$input" != /dev/null ] && rm -f "$input"; exit $status; }\n'
           'else\n  echo "vyd guard: vyd is not on PATH, so this was not checked" >&2\nfi\n') if guarded else ""
    return ("#!/bin/sh\n# Written by vyd install --client. Runs the guard, then the repository's own hook, since hooksPath replaces its folder.\n"
            f'hook={name}\n{read}\n{run}'
            'common=$(git rev-parse --git-common-dir 2>/dev/null)\nown="$common/hooks/$hook"\n'
            'if [ -x "$own" ]; then "$own" "$@" < "$input"; status=$?; [ "$input" != /dev/null ] && rm -f "$input"; exit $status; fi\n'
            '[ "$input" != /dev/null ] && rm -f "$input"\nexit 0\n')


def _global(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "config", "--global", *args], capture_output=True, text=True, encoding="utf-8", errors="replace")


def hooks_state() -> str:
    """installed when git's global hooksPath is ours, other when it is something else, absent when it is unset."""
    current = _global("--get", "core.hooksPath").stdout.strip()
    if not current:
        return "absent"
    return "installed" if Path(current).expanduser().resolve() == hook_dir().resolve() else "other"


def install_hooks(dry_run: bool) -> int:
    """Write the shims and point git's global hooksPath at them. Returns 1 when the user already has another hooksPath, which is left alone."""
    state = hooks_state()
    if state == "other":
        print(f"vyd: git's global core.hooksPath is already set to {_global('--get', 'core.hooksPath').stdout.strip()}, so the guard's hooks were not installed. "
              f"Chain vyd guard hook <name> from them, or unset it and run vyd install --client again")
        return 1
    folder = hook_dir()
    print(f"{'would write' if dry_run else 'wrote'} {len(ALL_HOOKS)} git hooks in {folder} and {'would set' if dry_run else 'set'} git's global core.hooksPath to it")
    if dry_run:
        return 0
    folder.mkdir(parents=True, exist_ok=True)
    for name in ALL_HOOKS:
        path = folder / name
        path.write_text(shim(name), encoding="utf-8", newline="\n")
        path.chmod(0o755)
    done = _global("core.hooksPath", str(folder))
    if done.returncode != 0:
        print(f"vyd: could not set git's global core.hooksPath: {done.stderr.strip()}")
        return 1
    return 0


def status_lines(config: Config, folder: Path) -> list[str]:
    """What `vyd context` and `vyd guard status` say of a folder: its class and whether the hooks are in place."""
    if not config.guard.on:
        return []
    lists = read_lists(config)
    verdict = classify(config, lists, folder)
    out = []
    if verdict.kind == "public":
        out.append("guarded: a public repository, so its commits and pushes are checked against the user's private lists. Do not bypass the check. Report a finding to the maintainer and propose a conformant change")
    elif verdict.kind == "private":
        out.append("guarded: a private repository, so its commits are checked against the lists that apply everywhere")
    elif verdict.kind == "unclassified":
        out.append(f"NOT CLASSIFIED: {verdict.repo} is under a watched owner and in neither list, so a commit here stops until the maintainer classifies it")
    if verdict.kind != "none" and hooks_state() != "installed":
        out.append("NOTE: the guard's git hooks are not installed here, so nothing is checked at commit. Run vyd install")
    out += [f"NOTE: {p}" for p in lists.problems]
    return out
