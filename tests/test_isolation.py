# SPDX-License-Identifier: MIT
"""The suite's own home: this process, a process it starts with its own environment, and one started with the suite's
environment as it stands, each keep the user's folders below a temporary folder, whatever the platform."""

from __future__ import annotations

import os
import stat
import subprocess
import sys
from pathlib import Path

from subprocess_support import FOLDER_LINKS, JUNCTIONS, environment, junction, link_to_folder

PROBE = ("import pathlib, platformdirs\n"
         "for kind in ('config', 'state', 'data', 'cache'):\n"
         "    print(getattr(platformdirs, f'user_{kind}_path')('vyvid'))\n"
         "print(pathlib.Path.home())\nprint(pathlib.Path('~').expanduser())\n")


def folders_of(env: dict[str, str]) -> list[Path]:
    done = subprocess.run([sys.executable, "-c", PROBE], env=env, capture_output=True, check=True)
    return [Path(line) for line in done.stdout.decode("utf-8").splitlines()]


def test_this_process_has_its_home_below_the_suites_temporary_folder(tmp_path_factory):
    base = tmp_path_factory.getbasetemp().resolve()
    assert Path.home().resolve().is_relative_to(base) and Path("~").expanduser().resolve().is_relative_to(base)


def test_a_child_with_its_own_environment_keeps_every_folder_below_its_home(tmp_path):
    for folder in folders_of(environment(tmp_path)):
        assert folder.resolve().is_relative_to(tmp_path.resolve()), folder


def test_a_child_with_the_suites_environment_keeps_every_folder_below_the_temporary_folder(tmp_path_factory):
    base = tmp_path_factory.getbasetemp().resolve()
    for folder in folders_of(dict(os.environ)):
        assert folder.resolve().is_relative_to(base), folder


@FOLDER_LINKS
def test_a_link_to_a_folder_reads_as_the_folder(tmp_path):
    (tmp_path / "target").mkdir()
    (tmp_path / "target" / "f.md").write_text("x", encoding="utf-8")
    link_to_folder(tmp_path / "link", tmp_path / "target")
    assert (tmp_path / "link" / "f.md").read_text(encoding="utf-8") == "x"
    assert (tmp_path / "link").is_symlink() or is_junction(tmp_path / "link")


def is_junction(path: Path) -> bool:
    """``Path.is_junction``, which Python 3.11 lacks."""
    return getattr(os.lstat(path), "st_reparse_tag", 0) == getattr(stat, "IO_REPARSE_TAG_MOUNT_POINT", -1)


@JUNCTIONS
def test_a_junction_is_a_link_to_python_only_as_a_junction(tmp_path):
    """What a check of a link must ask on Windows: a junction is not a symbolic link, and resolving one leaves the folder."""
    (tmp_path / "target").mkdir()
    junction(tmp_path / "link", tmp_path / "target")
    link = tmp_path / "link"
    assert is_junction(link) and not link.is_symlink() and link.resolve() == (tmp_path / "target").resolve()
