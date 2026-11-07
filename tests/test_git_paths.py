# SPDX-License-Identifier: MIT
"""Paths git prints are decoded as Python decodes a file name, which is UTF-8 on Windows and macOS and the file system's
own encoding on Linux, so a path opens the file it names whatever the locale."""

from __future__ import annotations

import os
import subprocess
import sys

import pytest

from vyvid.config import git_names, git_path

sys.path.insert(0, os.path.dirname(__file__))
from subprocess_support import environment, project, vyd  # noqa: E402


def test_names_in_the_file_systems_encoding_come_back_as_python_would_open_them():
    names = ["项目/标准.md", "проєкт/a b.md", "plain.md"]
    raw = b"\0".join(os.fsencode(n) for n in names) + b"\0"
    assert git_names(raw) == names


def test_a_name_the_file_systems_encoding_cannot_decode_is_left_out_with_a_note(capsys):
    if sys.getfilesystemencoding().lower().replace("-", "") != "utf8":
        pytest.skip("only a UTF-8 file system encoding rejects these bytes")
    assert git_names(b"good.md\0caf\xe9.md\0\0") == ["good.md"]
    assert "caf\\udce9.md" in capsys.readouterr().err


def test_a_path_keeps_its_bytes():
    path = os.path.join("tmp", "проєкт 项目")
    assert git_path(os.fsencode(path) + b"\n") == path


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="only Linux lets a file name hold bytes that are not UTF-8")
def test_a_latin_1_file_name_on_linux_is_no_traceback_and_is_named(tmp_path):
    root = tmp_path / "repo"
    project(root)
    with open(os.path.join(os.fsencode(root / "docs"), b"caf\xe9.md"), "wb") as handle:
        handle.write(b"See STD-1 and STD-99.\n")
    subprocess.run(["git", "-C", str(root), "add", "-A"], check=True, env=environment(tmp_path))
    subprocess.run(["git", "-C", str(root), "commit", "-qm", "latin-1"], check=True, env=environment(tmp_path))
    ran = vyd(environment(tmp_path, PYTHONUTF8="1"), "check", "identifiers", cwd=root)
    assert ran.clean() and b"is a tracked name the file system's encoding cannot decode" in ran.err, ran


def gbk_file_names(monkeypatch):
    """Python as it is on Linux under a GBK locale, whose file names are GBK, here where they are UTF-8."""
    monkeypatch.setattr(os, "fsencode", lambda path: os.fspath(path).encode("gbk", "surrogateescape"))


def test_a_configured_folder_this_machine_cannot_name_is_a_problem_and_no_crash(monkeypatch, tmp_path):
    from vyvid.config import ConfigError, load

    gbk_file_names(monkeypatch)
    text = f'[[projects]]\nname = "p"\ncode = "{(tmp_path / "代码 проєкт").as_posix()}"\ndocs = "code:docs"\n'
    with pytest.raises(ConfigError, match="cannot be a file name on this machine"):
        load(tmp_path / "config.toml", text=text)
    assert load(tmp_path / "config.toml", text=text.replace(" проєкт", "")).projects  # a name GBK holds is read


def test_a_folder_argument_keeps_its_bytes_and_a_text_argument_does_not():
    from argparse import Namespace

    from vyvid.streams import clean_arguments

    arguments = Namespace(folder="caf\udce9", words=["caf\udce9"], identifier="STD-1\udcc3")
    clean_arguments(arguments)
    assert arguments.folder == "caf\udce9" and os.fsencode(arguments.folder) == b"caf\xe9"
    assert arguments.words == ["caf�"] and arguments.identifier == "STD-1�"
