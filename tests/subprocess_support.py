# SPDX-License-Identifier: MIT
"""Real ``vyd`` and ``vyd-hook`` processes over real pipes, with an environment of their own, for the encoding and pipe tests."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

VYD = [sys.executable, "-m", "vyvid.cli"]
HOOK = [sys.executable, "-m", "vyvid.remind"]
NAME = "Вивід"
POSIX = pytest.mark.skipif(os.name != "posix", reason="needs POSIX file descriptors, signals or shell scripts")
KEEP = ("PATH", "SYSTEMROOT", "SYSTEMDRIVE", "TMPDIR", "TEMP", "TMP", "COMSPEC", "PATHEXT", "LD_LIBRARY_PATH", "DYLD_LIBRARY_PATH")


def environment(home: Path, **extra: str | None) -> dict[str, str]:
    """A child's environment: nothing of the caller's locale or Python settings, every folder of the user's under ``home``, and
    git without the caller's configuration. A value of None removes a variable."""
    env = {k: os.environ[k] for k in KEEP if k in os.environ}
    env.update(HOME=str(home), USERPROFILE=str(home), XDG_CONFIG_HOME=str(home / "xc"), XDG_STATE_HOME=str(home / "xs"),
               XDG_DATA_HOME=str(home / "xd"), XDG_CACHE_HOME=str(home / "xk"), VYVID_CONFIG=str(home / "absent.toml"),
               VYVID_HOOK_STATE=str(home / "hook"), GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull, GIT_TERMINAL_PROMPT="0",
               GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@example.org", GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@example.org")
    env.update({k: v for k, v in extra.items() if v is not None})
    for k, v in extra.items():
        if v is None:
            env.pop(k, None)
    return env


class Ran:
    def __init__(self, code: int, out: bytes, err: bytes):
        self.code, self.out, self.err = code, out, err

    def __repr__(self) -> str:
        return f"exit {self.code}\nstdout: {self.out[:600]!r}\nstderr: {self.err[:1200]!r}"

    def clean(self) -> bool:
        return b"Traceback" not in self.err and b"Traceback" not in self.out


def run(command: list, env: dict[str, str], *, cwd: Path | None = None, stdin: bytes | None = b"", seconds: float = 60, **kwargs) -> Ran:
    """Run ``command`` to the end. ``stdin`` of None leaves a pipe open that never writes, which a hang then fails by the timeout."""
    if stdin is None:
        with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
            process = subprocess.Popen(command, env=env, cwd=cwd, stdin=subprocess.PIPE, stdout=out, stderr=err, **kwargs)
            try:
                process.wait(timeout=seconds)
            finally:
                process.kill()
            out.seek(0), err.seek(0)
            return Ran(process.returncode, out.read(), err.read())
    done = subprocess.run(command, env=env, cwd=cwd, input=stdin, capture_output=True, timeout=seconds, **kwargs)
    return Ran(done.returncode, done.stdout, done.stderr)


def vyd(env: dict[str, str], *args, cwd: Path | None = None, **kwargs) -> Ran:
    return run([*VYD, *args], env, cwd=cwd, **kwargs)


def quote(text: str) -> str:
    """A TOML basic string. JSON escapes agree with it once non-ASCII is left as it is."""
    return json.dumps(text, ensure_ascii=False)


def git(root: Path, *args: str, env: dict[str, str] | None = None) -> None:
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, env=env or environment(root.parent))


def project(root: Path, docs: str = "docs", defined: str = "std.md", mention: str = "a.md", row: str = "x", extra: str = "") -> Path:
    """A repository at ``root`` whose vyvid.toml declares project ``p`` with a standards register, STD-1 defined and STD-99 mentioned
    and never defined. Names may hold any character the file system allows. The docs folder is returned."""
    folder = root / docs
    folder.mkdir(parents=True)
    (root / "vyvid.toml").write_text(f'[project]\nname = "p"\ndocs = {quote("code:" + docs)}\n{extra}\n[project.families]\n'
                                     f'STD = {{ defined = {quote("docs:" + defined)}, type = "standard" }}\n', encoding="utf-8")
    (folder / defined).write_text(f"# Standards\n\n| ID | Standard |\n|---|---|\n| STD-1 | {row} |\n", encoding="utf-8")
    (folder / mention).write_text("See STD-1 and STD-99.\n", encoding="utf-8")
    git(root, "init", "-q", "-b", "main")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "i")
    return folder


def sees(name: str) -> bool:
    """Whether a locale of this name is installed."""
    if shutil.which("locale") is None:
        return False
    return name in subprocess.run(["locale", "-a"], capture_output=True, text=True, encoding="utf-8", errors="replace").stdout.split()


def holds(text: str, encoding: str) -> bool:
    try:
        text.encode(encoding)
    except UnicodeError:
        return False
    return True
