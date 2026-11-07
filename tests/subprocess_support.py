# SPDX-License-Identifier: MIT
"""Real ``vyd`` and ``vyd-hook`` processes over real pipes, with an environment of their own, for the encoding and pipe tests."""

from __future__ import annotations

import functools
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

# -P keeps the working folder off the import path, as the installed vyd and vyd-hook launchers do, since under a locale
# whose codec cannot hold the folder's name Python could not start with it there.
VYD = [sys.executable, "-P", "-m", "vyvid.cli"]
HOOK = [sys.executable, "-P", "-m", "vyvid.remind"]
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


def on_disk(path: Path, encoding: str = "utf-8") -> bytes:
    """``path`` as the bytes a machine whose file names are ``encoding`` holds it in. A test runs under UTF-8, so a name for a
    process under another locale is written in that locale's encoding, as a person on that machine would have it."""
    return str(path).encode(encoding, "surrogateescape")


def project(root: Path, docs: str = "docs", defined: str = "std.md", mention: str = "a.md", row: str = "x", extra: str = "",
            encoding: str = "utf-8") -> Path:
    """A repository at ``root`` whose vyvid.toml declares project ``p`` with a standards register, STD-1 defined and STD-99 mentioned
    and never defined. Names may hold any character the file system allows, and are written in ``encoding``. The docs folder is
    returned."""
    folder = root / docs
    os.makedirs(on_disk(folder, encoding))
    toml = (f'[project]\nname = "p"\ndocs = {quote("code:" + docs)}\n{extra}\n[project.families]\n'
            f'STD = {{ defined = {quote("docs:" + defined)}, type = "standard" }}\n')
    for path, text in ((root / "vyvid.toml", toml), (folder / defined, f"# Standards\n\n| ID | Standard |\n|---|---|\n| STD-1 | {row} |\n"),
                       (folder / mention, "See STD-1 and STD-99.\n")):
        with open(on_disk(path, encoding), "wb") as handle:
            handle.write(text.encode("utf-8"))
    for args in (("init", "-q", "-b", "main"), ("add", "-A"), ("commit", "-q", "-m", "i")):
        subprocess.run(["git", "-C", on_disk(root, encoding), *args], check=True, capture_output=True, env=environment(root.parent))
    return folder


@functools.cache
def sees(name: str) -> bool:
    """Whether a locale of this name is installed, asked of the C library as a process under it would ask, since glibc finds
    ``zh_CN.GBK`` installed as ``zh_CN.gbk`` and ``locale -a`` lists only the second. On Linux the locales are made with, for
    example, ``localedef -i zh_CN -f GBK zh_CN.GBK``."""
    probe = "import locale; locale.setlocale(locale.LC_ALL, '')"
    return subprocess.run([sys.executable, "-c", probe], env={**environment(Path(tempfile.gettempdir())), "LC_ALL": name},
                          capture_output=True).returncode == 0


@functools.cache
def file_name_encoding(locale_env: tuple[tuple[str, str], ...]) -> str:
    """The encoding a process with this environment holds file names in: UTF-8 on macOS and Windows, the locale's on Linux."""
    probe = "import sys; print(sys.getfilesystemencoding())"
    env = {**environment(Path(tempfile.gettempdir())), **dict(locale_env)}
    return subprocess.run([sys.executable, "-c", probe], env=env, capture_output=True, text=True, encoding="ascii").stdout.strip()



def holds(text: str, encoding: str) -> bool:
    try:
        text.encode(encoding)
    except UnicodeError:
        return False
    return True
