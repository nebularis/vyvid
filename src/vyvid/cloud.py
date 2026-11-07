# SPDX-License-Identifier: MIT
"""``vyd cloud script``: a setup script a person pastes into their own cloud environment.

A cloud session cannot clone a private repository, and the only place private text can reach it is the setup script. So the
script carries the files of the private domains the person names, each as base64, and the configuration that makes them
domains, and clones the public ones. It is written to a file and never printed, since it holds private text. Nothing is
embedded that was not named. The configuration inside it is checked by the real loader before the script is written.
"""

from __future__ import annotations

import base64
import hashlib
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

from . import __version__
from . import config as cf
from .configure import Refusal, _block
from .credentials import private_file

LIMIT = 64 * 1024  # what an environment's setup script may hold, about
FILE_LIMIT = 256 * 1024
INSTALL = "git+https://github.com/nebularis/vyvid.git"
SCP = re.compile(r"^[^@/:]+@([^/:]+):(?!\d)(.*)$")
SSH = re.compile(r"^ssh://(?:[^@/]+@)?([^/:]+)(?::\d+)?/(.*)$")


def https(url: str) -> str:
    """A remote with an ssh form written as the https URL of the same repository, since a cloud setup has no key."""
    for form in (SCP, SSH):
        if m := form.match(url.strip()):
            return f"https://{m.group(1)}/{m.group(2)}"
    return url.strip()


def _git(folder: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(folder), *args], capture_output=True)


def destination(name: str, scope: cf.Scope, given: str | None) -> str:
    """Where a domain is written in the cloud, as ``~/...``."""
    if given is not None:
        if not given.startswith("~/") or len(given) <= 2:
            raise Refusal(f"domain {name}: the path '{given}' must start with ~/ and name a folder under it")
        if ".." in given.split("/"):
            raise Refusal(f"domain {name}: the path '{given}' must not hold '..'")
        return given.rstrip("/")
    home = Path.home().resolve()
    folder = scope.path.resolve()
    if folder == home or not folder.is_relative_to(home):
        raise Refusal(f"domain {name}: its folder is outside the home folder, so give the place to write it in the cloud as --domain {name}=~/PATH")
    return "~/" + folder.relative_to(home).as_posix()


def tracked(name: str, folder: Path) -> list[tuple[str, bytes]]:
    """Each file git tracks in the domain's folder, as name and bytes. Refuses what could leave the folder or is too large."""
    if not folder.is_dir() or _git(folder, "rev-parse", "--is-inside-work-tree").returncode:
        raise Refusal(f"domain {name}: its folder is not a git repository, and only the files git tracks are embedded")
    listed = _git(folder, "ls-files", "-z")
    if listed.returncode:
        raise Refusal(f"domain {name}: git could not list its files")
    root, files, problems = folder.resolve(), [], []
    for rel in cf.git_names(listed.stdout):
        path = folder / rel
        shown = f"domain {name}: {rel}"
        if rel.startswith("/") or ".." in Path(rel).parts or not path.resolve().is_relative_to(root):
            problems.append(f"{shown} leaves the domain's folder, so it is not embedded")
        elif not path.is_file():
            problems.append(f"{shown} is tracked and not a readable file here. Restore or commit its removal")
        elif path.stat().st_size > FILE_LIMIT:
            problems.append(f"{shown} is over {FILE_LIMIT // 1024} KB")
        else:
            files.append((rel, path.read_bytes()))
    if problems:
        raise Refusal(*problems)
    return files


def _home(path: str) -> str:
    """A ``~/x`` path as shell words that expand ``$HOME``."""
    return '"$HOME"/' + shlex.quote(path[2:])


def build(config: cf.Config, named: list[str], grants: list[str]) -> tuple[str, list[str], str]:
    """The script's text, the lines that say what went into it, and its fingerprint. Raises Refusal."""
    chosen: dict[str, str | None] = {}
    for item in named:
        name, _, given = item.partition("=")
        if name not in config.domains:
            raise Refusal(f"domain {name} is not in the configuration")
        chosen[name] = given if "=" in item else None
    embedded, notes, public = {}, [], []
    for name, scope in config.domains.items():
        if name in chosen:
            if scope.path is None:
                raise Refusal(f"domain {name} has no folder")
            files = tracked(name, scope.path)
            embedded[name] = (destination(name, scope, chosen[name]), files)
            notes.append(f"domain {name}: embedded, {len(files)} file{'' if len(files) == 1 else 's'} at {embedded[name][0]}")
        elif scope.visibility == "private":
            notes.append(f"domain {name}: left out, it was not named with --domain")
        else:
            remote = scope.remote[0] if isinstance(scope.remote, list) and scope.remote else scope.remote
            if not remote and scope.path is not None:
                done = _git(scope.path, "config", "--get", "remote.origin.url")
                remote = done.stdout.decode("utf-8", "replace").strip() if not done.returncode else None
            if not remote:
                notes.append(f"domain {name}: left out, it has no remote")
                continue
            entry = {"name": name, "remote": https(remote), "trust": scope.trust, **({"commit": scope.commit} if scope.commit else {}),
                     "visibility": "public", "git": {"pull": "manual", "commit": "manual", "push": "manual"}}
            public.append(entry)
            notes.append(f"domain {name}: cloned from {https(remote)}")
    framework = {"kb": "~/vyvid-kb", "glue": "stop", **({"trusted_repositories": grants} if grants else {})}
    blocks = [_block("framework", framework, array=False)]
    blocks += [_block("domains", {"name": n, "path": place, "trust": "own", "visibility": "private"}) for n, (place, _) in embedded.items()]
    blocks += [_block("domains", e) for e in public]
    toml = "\n\n".join("\n".join(b) for b in blocks) + "\n"
    try:
        cf.load(Path("cloud-config.toml"), toml)
    except cf.ConfigError as error:
        raise Refusal("the configuration for the cloud environment cannot be used:", *error.problems) from error
    if "VYD_CONFIG" in toml:
        raise Refusal("the configuration holds the text that ends its here-document")

    body = ['LOG="${VYD_CLOUD_LOG:-/tmp/vyd-cloud-setup.log}"', 'exec >"$LOG" 2>&1',
            'fail() { echo "FAILED: $1. Carrying on."; }',
            'export PATH="$HOME/.local/bin:$PATH"',
            f'uv tool install --force "{INSTALL}@v{__version__}" || fail "installing vyd"',
            'put() { mkdir -p "$(dirname "$1")" && base64 -d >"$1"; }']
    for name, (place, files) in embedded.items():
        for rel, data in files:
            body += [f'put {_home(place + "/" + rel)} <<\'VYD_B64\' || fail "writing {shlex.quote(name + "/" + rel)}"',
                     *base64.encodebytes(data).decode().splitlines(), "VYD_B64"]
    body += ['mkdir -p "$HOME/.config/vyvid" || fail "making the configuration folder"',
             "# The cloud runs Linux, so this is where the configuration is read from.",
             'cat >"$HOME/.config/vyvid/config.toml" <<\'VYD_CONFIG\' || fail "writing the configuration"', toml.rstrip("\n"), "VYD_CONFIG",
             'vyd kb clone || fail "cloning the public domains"',
             'vyd install --client claude-code || fail "installing the client files"',
             "vyd --version", "vyd config | grep -E '^(configuration|domains):'", "exit 0"]
    text = "\n".join(body) + "\n"
    digest = hashlib.sha256(text.encode()).hexdigest()[:12]
    head = ["#!/bin/sh", f"# Written by vyd cloud script, version {__version__}.",
            f"# Fingerprint {digest}, the first 12 hex digits of the SHA-256 of everything after these comments.",
            "# This script holds private text. Paste it only into a cloud environment that no one else uses."]
    return "\n".join(head) + "\n" + text, notes, digest


def command(output: str, domains: list[str], grants: list[str], dry_run: bool) -> int:
    try:
        text, notes, digest = build(cf.load(), domains, grants)
        data = text.encode()
        target = Path(output).expanduser()
        lines = [f"script {len(data)} bytes of {LIMIT} allowed", f"fingerprint {digest}", *notes]
        if len(data) > LIMIT:
            lines.insert(1, f"WARNING: {len(data)} bytes is over the {LIMIT} byte limit of a setup script. Name fewer domains")
        if not dry_run:
            target.parent.mkdir(parents=True, exist_ok=True)
            private_file(target)
            try:
                target.chmod(0o600)
            except OSError:
                pass
            target.write_bytes(data)
            lines.insert(0, f"written {target}")
        else:
            lines.insert(0, f"would write {target}, and wrote nothing")
        print("\n".join(lines))
        return 0
    except Refusal as refusal:
        for problem in refusal.problems:
            print(f"vyd: {problem}", file=sys.stderr)
        return 1
    except cf.ConfigError as error:
        print(f"the configuration at {cf.config_path()} cannot be used:", file=sys.stderr)
        for problem in error.problems:
            print(f"  {problem}", file=sys.stderr)
        return 2
