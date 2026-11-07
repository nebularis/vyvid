# SPDX-License-Identifier: MIT
"""Managed assets: the domains whose folder lies under the knowledge base, each a git clone of its remote.

Вивід clones, pulls, commits and pushes these by the domain's git policy, and nothing else, but the
private documents of a project, which ``docs_record`` keeps by the project's ``git.docs`` policy. A folder
anywhere else, such as one inside a project, is read and never touched by git, and a package a
domain names is never installed. Every git call is an argument list run in the domain's folder
with prompting for credentials switched off, so a missing credential fails instead of waiting.
"""

from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from .build import store_dir
from .config import Config, GitPolicy, Scope, glue_env, run_limited
from .credentials import private_dir, redact, scan_file
from .resolve import normalise_remote

DAY = 24 * 60 * 60
GITLEAKS_SECONDS = 30
STAMPS = "kb-pulls.json"


class KbError(Exception):
    """A request that names something that is not a managed domain."""


@dataclass
class Result:
    """What one operation did to one domain, and whether it went as asked."""

    name: str
    ok: bool
    text: str


@dataclass
class Status:
    name: str
    folder: Path
    remote: str | None
    policy: GitPolicy
    exists: bool = False
    clone: bool = False  # a repository at the folder itself whose remote is the configured one
    branch: str | None = None
    ahead: int | None = None
    behind: int | None = None
    changes: int = 0
    last_pull: float | None = None
    held: list[str] = field(default_factory=list)  # instruction-bearing files changed upstream, not merged


def git(folder: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-c", "i18n.logOutputEncoding=UTF-8", *args], cwd=folder, capture_output=True, text=True, encoding="utf-8", errors="replace",
                          env={**os.environ, "GIT_TERMINAL_PROMPT": "0"})


def managed(config: Config) -> list[Scope]:
    """The domains whose folder lies under the knowledge base, in configuration order."""
    if config.kb is None:
        return []
    kb = config.kb.expanduser().resolve()
    return [d for d in config.domains.values() if d.path is not None and kb in d.path.resolve().parents]


def select(config: Config, names: list[str]) -> list[Scope]:
    """The named managed domains, or all of them when none are named."""
    every = managed(config)
    if not names:
        return every
    by_name = {d.name: d for d in every}
    if missing := [n for n in names if n not in by_name]:
        raise KbError(f"not a managed domain, since its folder is not under the knowledge base: {', '.join(missing)}")
    return [by_name[n] for n in names]


def _stamps(config: Config) -> dict[str, float]:
    try:
        return json.loads((store_dir(config) / STAMPS).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _stamp(config: Config, name: str, when: float) -> None:
    stamps = {**_stamps(config), name: when}
    path = store_dir(config) / STAMPS
    private_dir(path.parent)
    path.write_text(json.dumps(stamps, indent=2) + "\n", encoding="utf-8", newline="\n")


def is_clone(scope: Scope) -> bool:
    """Whether the folder is itself a git repository with a remote that is the domain's configured one."""
    folder = scope.path
    if folder is None or not folder.is_dir() or scope.remote is None:
        return False
    top = git(folder, "rev-parse", "--show-toplevel")
    if top.returncode or Path(top.stdout.strip()).resolve() != folder.resolve():
        return False
    urls = git(folder, "config", "--get-regexp", r"^remote\..*\.url$").stdout.splitlines()
    return normalise_remote(scope.remote) in {normalise_remote(line.split(None, 1)[1]) for line in urls if " " in line}


def inspect(config: Config, scope: Scope) -> Status:
    folder = scope.path
    status = Status(scope.name, folder, scope.remote, scope.git, exists=folder.exists(), last_pull=_stamps(config).get(scope.name))
    if not is_clone(scope):
        return status
    status.clone = True
    status.branch = git(folder, "branch", "--show-current").stdout.strip() or None
    counts = git(folder, "rev-list", "--left-right", "--count", "@{u}...HEAD")
    if counts.returncode == 0:
        status.behind, status.ahead = map(int, counts.stdout.split())
    status.changes = len(git(folder, "status", "--porcelain").stdout.splitlines())
    status.held = held(scope)
    return status


def instruction_bearing(scope: Scope, changed: list[str]) -> list[str]:
    """The changed files that can steer an agent: the manifest, any file the domain names as rules, skills,
    register types, facets or vocabulary, anything under a folder it names, and any file called SKILL.md."""
    named = [os.path.abspath(p) for p in (*scope.rules, *scope.skills, *scope.register_types, *scope.facets, *scope.vocabulary)]
    named.append(os.path.abspath(scope.path / "domain.toml"))

    def steers(file: str) -> bool:
        full = os.path.abspath(scope.path / file)
        return Path(file).name == "SKILL.md" or any(full == n or full.startswith(n + os.sep) for n in named)

    return [f for f in changed if steers(f)]


def changed(scope: Scope) -> list[str]:
    """The files that differ between HEAD and its upstream as last fetched, none if there is no upstream."""
    done = git(scope.path, "diff", "--name-only", "HEAD...@{u}")
    return done.stdout.splitlines() if done.returncode == 0 else []


def held(scope: Scope) -> list[str]:
    """The instruction-bearing files changed upstream, for a domain that is not the user's own."""
    return [] if scope.trust == "own" or not is_clone(scope) else instruction_bearing(scope, changed(scope))


def accept(config: Config, scope: Scope, clock: Callable[[], float] = time.time) -> Result:
    """Fast-forward a held domain to its upstream. Its trust and commit stay as the user wrote them."""
    done = git(scope.path, "merge", "--ff-only", "@{u}")
    if done.returncode:
        return Result(scope.name, False, (done.stderr or done.stdout).strip())
    _stamp(config, scope.name, clock())
    return Result(scope.name, True, done.stdout.strip())


def clone(config: Config, scope: Scope) -> Result:
    """Clone the domain's remote into its folder. A folder that holds anything else is reported and left alone."""
    folder = scope.path
    if scope.remote is None:
        return Result(scope.name, False, "no remote is configured, so there is nothing to clone")
    if folder.exists() and is_clone(scope):
        return Result(scope.name, True, f"already a clone of {scope.remote}")
    if folder.exists() and (not folder.is_dir() or any(folder.iterdir())):
        return Result(scope.name, False, f"{folder} exists and is not a clone of {scope.remote}, so it is left as it is")
    folder.parent.mkdir(parents=True, exist_ok=True)
    done = git(folder.parent, "clone", scope.remote, str(folder))
    return Result(scope.name, done.returncode == 0, f"cloned {scope.remote}" if done.returncode == 0 else done.stderr.strip())


def is_due(policy, last: float | None, now: float) -> bool:
    if policy.pull == "on-start":
        return True
    return policy.pull == "daily" and (last is None or now - last > DAY)


def pull(config: Config, scopes: list[Scope], due: bool = False, clock: Callable[[], float] = time.time) -> list[Result]:
    """``git pull --ff-only`` in each domain, only those due by policy with ``due``. A pull that cannot
    fast-forward is reported with git's reason and left as it was, never merged or stashed. For a domain
    that is not the user's own it fetches first and merges nothing if a file that can steer an agent changed."""
    results = []
    for scope in scopes:
        now = clock()
        if due and not is_due(scope.git, _stamps(config).get(scope.name), now):
            continue
        if not is_clone(scope):
            why = "no remote is configured" if scope.remote is None else f"{scope.path} is not a clone of {scope.remote}, run vyd kb clone"
            results.append(Result(scope.name, False, why))
            continue
        if scope.trust != "own":
            fetched = git(scope.path, "fetch")
            if fetched.returncode:
                results.append(Result(scope.name, False, (fetched.stderr or fetched.stdout).strip()))
                continue
            if files := held(scope):
                read = shlex.join(["git", "-C", str(scope.path), "diff", "HEAD...@{u}"])
                results.append(Result(scope.name, False, f"held, nothing merged, since these instruction-bearing files changed upstream: {', '.join(files)}. "
                                                           f"Read them with {read}, then a person runs vyd kb accept {scope.name}"))
                continue
            done = git(scope.path, "merge", "--ff-only", "@{u}")
        else:
            done = git(scope.path, "pull", "--ff-only")
        if done.returncode:
            results.append(Result(scope.name, False, (done.stderr or done.stdout).strip()))
            continue
        _stamp(config, scope.name, now)
        results.append(Result(scope.name, True, done.stdout.strip()))
    return results


def pull_due(config: Config, stack: list[Scope], clock: Callable[[], float] = time.time) -> list[Result]:
    """What the managed domains of a stack that have a remote and are due for a pull did."""
    ours = {d.name for d in managed(config) if d.remote}
    return pull(config, [s for s in stack if s.name in ours], due=True, clock=clock)


def _files(paths: list[Path]) -> list[Path]:
    """The files a stage of these paths could take: each file, and the files under each folder but its .git."""
    return [f for p in paths for f in ([p] if p.is_file() else sorted(p.rglob("*")) if p.is_dir() else []) if f.is_file() and ".git" not in f.parts]


def _gitleaks(file: Path) -> tuple[list[tuple[int, str]], str | None]:
    """What ``gitleaks`` finds in one file, as line and rule, and a note if it could not run.

    It runs in an empty folder under the minimal environment, so no ignore file or configuration of the
    domain's is read, and ``gitleaks:allow`` comments are ignored. Its own redaction keeps the secret out of the report."""
    with tempfile.TemporaryDirectory() as work:
        report = Path(work) / "report.json"
        command = ["gitleaks", "dir", "--no-banner", "--no-color", "--redact", "--ignore-gitleaks-allow", "--exit-code", "2",
                   "--log-level", "error", "--report-format", "json", "--report-path", str(report), str(file)]
        try:
            done = run_limited(command, "", Path(work), glue_env({}), GITLEAKS_SECONDS)
            found = json.loads(report.read_text(encoding="utf-8")) if done.returncode == 2 else []
        except subprocess.TimeoutExpired:
            return [], f"gitleaks did not finish within {GITLEAKS_SECONDS} seconds"
        except (OSError, ValueError) as error:
            return [], f"gitleaks could not be run or read ({error.__class__.__name__})"
        if done.returncode not in (0, 2):
            return [], f"gitleaks exited {done.returncode}: {redact(done.stderr.strip())[:200]}"
    return [(int(f["StartLine"]), str(f["RuleID"])) for f in found], None


def leaks(folder: Path, files: list[Path]) -> tuple[list[str], list[str]]:
    """``path:line rule`` for each credential found in the files, by the built-in scan and by ``gitleaks``
    where it is installed, and a note for each time ``gitleaks`` failed. Never the matched text."""
    found: dict[str, None] = {}
    notes: list[str] = []
    for file in files:
        hits = scan_file(file)
        if shutil.which("gitleaks"):
            more, note = _gitleaks(file)
            hits, notes = hits + more, notes + ([note] if note else [])
        shown = file.relative_to(folder).as_posix() if file.is_relative_to(folder) else file.name
        found.update(dict.fromkeys(f"{shown}:{line} {rule}" for line, rule in hits))
    return list(found), list(dict.fromkeys(notes))


def record(config: Config, paths: list[str], message: str) -> list[Result]:
    """Stage the paths in the managed domains holding them, and by each domain's policy commit and push.

    Nothing is staged unless every path is acceptable, and nothing of a domain whose files hold what looks like a credential. A path outside every managed domain belongs to a
    project, whose own contract governs its commits."""
    domains = managed(config)
    grouped: dict[str, list[Path]] = {}
    refused = []
    for raw in paths:
        path = Path(raw).expanduser().resolve()
        home = next((d for d in domains if d.path.resolve() in path.parents or d.path.resolve() == path), None)
        if home is None:
            refused.append(Result(raw, False, "is in no managed domain. The project's own contract governs commits there, and Вивід never commits or pushes a project's files"))
        elif not is_clone(home):
            refused.append(Result(raw, False, f"is in domain {home.name}, whose folder is not a clone of its remote"))
        elif git(home.path, "check-ignore", "-q", "--", str(path)).returncode == 0:
            refused.append(Result(raw, False, f"is ignored by git in domain {home.name}"))
        else:
            grouped.setdefault(home.name, []).append(path)
    if refused:
        return refused
    results = []
    for name, files in grouped.items():
        results += _keep(config, name, config.domains[name].path, config.domains[name].git, files, message)
    return results


def _keep(config: Config, name: str, folder: Path, policy: GitPolicy, files: list[Path], message: str) -> list[Result]:
    """Scan the files for credentials, then stage them in the repository at ``folder`` and by ``policy`` commit and push."""
    found, notes = leaks(folder.resolve(), _files(files))
    results = [Result(name, True, f"{note}, so only the built-in scan was done") for note in notes]
    if found:
        return results + [Result(name, False, "refused, nothing staged, since these look like credentials: " + ", ".join(found)
                                 + ". Remove them. If one is a false positive, stage the file with git yourself, since vyd has no flag to skip this scan")]
    added = git(folder, "add", "--", *map(str, files))
    if added.returncode:
        return results + [Result(name, False, added.stderr.strip())]
    staged = git(folder, "diff", "--cached", "--name-only", "--", *map(str, files)).stdout.split()
    if not staged:
        results.append(Result(name, True, "nothing changed in those paths, so nothing to commit"))
    elif policy.commit == "manual":
        results.append(Result(name, True, f"staged {', '.join(staged)}. Commit is manual, so nothing is committed"))
    else:
        text = "\n\n".join([message, *(["\n".join(config.commit_trailers)] if config.commit_trailers else [])])
        done = git(folder, "commit", "-m", text, "--", *map(str, files))
        if done.returncode:
            results.append(Result(name, False, (done.stderr or done.stdout).strip()))
        elif policy.push != "auto":
            results.append(Result(name, True, f"committed {', '.join(staged)}. Push is manual, so nothing is pushed"))
        else:
            pushed = git(folder, "push")
            results.append(Result(name, pushed.returncode == 0,
                                  f"committed and pushed {', '.join(staged)}" if pushed.returncode == 0 else f"committed {', '.join(staged)}, but the push failed: {pushed.stderr.strip()}"))
    return results


def _repository(folder: Path) -> Path | None:
    """The git common directory of the repository holding ``folder``, if any."""
    done = git(folder, "rev-parse", "--path-format=absolute", "--git-common-dir")
    return Path(done.stdout.strip()).resolve() if done.returncode == 0 else None


def docs_record(project: Scope, config: Config, paths: list[str], message: str) -> list[Result]:
    """Stage paths under a project's documents folder, outside its code repository, and by its ``git.docs`` policy
    commit and push them, after the same credential scan as ``record``. A folder in no repository keeps nothing in git."""
    name, docs = project.name, project.docs.resolve()
    if not docs.is_dir():
        return [Result(name, False, f"the documents folder {docs} does not exist")]
    files = [Path(raw).expanduser().resolve() for raw in paths]
    if outside := [r for r, f in zip(paths, files) if docs != f and docs not in f.parents]:
        return [Result(r, False, f"is outside the documents folder of project {name}, so nothing is staged") for r in outside]
    here = _repository(docs)
    if here is None:
        return [Result(name, True, f"{docs} is in no git repository, so nothing is kept in git and nothing was done")]
    if project.code is not None and project.code.is_dir() and _repository(project.code.resolve()) == here:
        return [Result(name, False, f"{docs} is in the code repository, whose contract governs its commits, so nothing is staged")]
    if ignored := [r for r, f in zip(paths, files) if git(docs, "check-ignore", "-q", "--", str(f)).returncode == 0]:
        return [Result(r, False, "is ignored by git, so nothing is staged") for r in ignored]
    return _keep(config, name, docs, project.docs_git, files, message)
