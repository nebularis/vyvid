# SPDX-License-Identifier: MIT
"""What ``vyd`` does with the text encodings of its output, its folders, its files and its arguments, in real processes.

Output keeps the stream's own encoding, and never crashes on a character it cannot hold. Git's output is read as UTF-8
whatever the locale. A file that cannot be decoded is a problem naming it.
"""

from __future__ import annotations

import ast
import os
import sys
from pathlib import Path

import pytest

from subprocess_support import NAME, POSIX, environment, holds, project, quote, run, sees, vyd
from vyvid import __version__

SRC = Path(__file__).resolve().parent.parent / "src" / "vyvid"

ENCODINGS = ["cp1252", "cp936", "gbk", "gb18030", "cp932", "shift_jis", "euc_jp", "cp949", "euc_kr", "cp950", "big5", "cp1251", "koi8_r",
             "cp437", "cp850", "latin-1", "ascii", "utf-8", "utf-8-sig", "utf-16", "cp866", "cp1125", "koi8_u", "iso8859_5", "mac_cyrillic"]
# The encodings that hold Вивід, stated here and not computed, so a wrong detection fails. Ukrainian і (U+0456) is what many lack.
HOLD_THE_NAME = {"gb18030", "euc_jp", "cp1251", "utf-8", "utf-8-sig", "utf-16", "cp1125", "koi8_u", "iso8859_5", "mac_cyrillic"}
COMMANDS = {"version": ["--version"], "help": ["--help"], "config": ["config"], "context": ["context", "--no-pull"],
            "identifiers": ["check", "identifiers", "."]}


@pytest.fixture(scope="module")
def home(tmp_path_factory):
    return tmp_path_factory.mktemp("home")


@pytest.fixture(scope="module")
def clean_project(tmp_path_factory):
    root = tmp_path_factory.mktemp("clean") / "repo"
    project(root)
    (root / "docs" / "a.md").write_text("See STD-1.\n", encoding="utf-8")
    return root


# -- the output's encoding -------------------------------------------------------------------------------------


@pytest.mark.parametrize("encoding", ENCODINGS)
@pytest.mark.parametrize("command", COMMANDS)
def test_output_keeps_the_streams_encoding_never_crashes_and_names_us_where_it_can(encoding, command, home, clean_project):
    ran = vyd(environment(home, PYTHONIOENCODING=encoding), *COMMANDS[command], cwd=clean_project)
    assert ran.clean() and ran.code == 0, ran
    text = ran.out.decode(encoding) + ran.err.decode(encoding)
    assert holds(NAME, encoding) == (encoding in HOLD_THE_NAME)
    if command in ("version", "help", "context"):
        assert (NAME in text) == (encoding in HOLD_THE_NAME), f"{encoding} and the name"
    if command == "version":
        assert text.split()[-1] == __version__ and text.strip().split()[0] == (NAME if encoding in HOLD_THE_NAME else "vyvid")


def test_a_person_who_chose_the_errors_keeps_them(home):
    probe = "import sys; from vyvid.streams import harden_streams; harden_streams(); print(sys.stdout.errors)"
    for chosen, expected in (("utf-8", b"backslashreplace"), ("utf-8:strict", b"strict"), ("ascii:ignore", b"ignore")):
        assert run([sys.executable, "-c", probe], environment(home, PYTHONIOENCODING=chosen)).out.strip() == expected, chosen


@pytest.mark.parametrize("encoding", ["ascii", "cp1252", "cp437", "latin-1", "cp936", "koi8_r", "utf-8", "cp866", "cp1251", "koi8_u", "iso8859_5"])
@pytest.mark.parametrize("row", ["日本語 тест 😀 ü", "проєкт їґі ёъ світ", "проект ёъ документы"], ids=["mixed", "ukrainian", "russian"])
def test_text_outside_the_encoding_reaches_the_output_as_escapes(encoding, row, tmp_path):
    root = tmp_path / "repo"
    project(root, row=row)
    env = environment(tmp_path, PYTHONIOENCODING=encoding)
    assert vyd(env, "build", "--no-embed", cwd=root).code == 0
    ran = vyd(env, "read", "STD-1", cwd=root)
    assert ran.clean() and ran.code == 0, ran
    assert f"| STD-1 | {row} |".encode(encoding, "backslashreplace") in ran.out
    if not holds(row, encoding):
        assert b"\\u" in ran.out or b"\\U" in ran.out


# -- folders and files with any name ---------------------------------------------------------------------------

NAMES = {"chinese": "项目张三", "japanese": "プロジェクト山田", "korean": "프로젝트김", "cyrillic": "проект-Вивід", "arabic": "مشروع",
         "emoji": "🔥📚", "combining": "e\u0301a\u0308n\u0303", "spaces": "a b  c", "dollar": "a$HOME$(x)b", "quotes": "a'b\"c`d",
         "ampersand": "a&b;c|d", "long": "ж" * 90,
         "russian": "проект-ёъ-документы-стандарт", "ukrainian": "проєкт-їґі-документи-стандарти"}
LOCALES = {"utf8": {"PYTHONUTF8": "1"}, "zh_CN.GBK": {"LC_ALL": "zh_CN.GBK", "PYTHONUTF8": "0"},
           "ja_JP.SJIS": {"LC_ALL": "ja_JP.SJIS", "PYTHONUTF8": "0"}, "ko_KR.eucKR": {"LC_ALL": "ko_KR.eucKR", "PYTHONUTF8": "0"},
           "ru_RU.KOI8-R": {"LC_ALL": "ru_RU.KOI8-R", "PYTHONUTF8": "0"}, "ru_RU.CP1251": {"LC_ALL": "ru_RU.CP1251", "PYTHONUTF8": "0"},
           "ru_RU.CP866": {"LC_ALL": "ru_RU.CP866", "PYTHONUTF8": "0"}, "ru_RU.ISO8859-5": {"LC_ALL": "ru_RU.ISO8859-5", "PYTHONUTF8": "0"},
           "uk_UA.KOI8-U": {"LC_ALL": "uk_UA.KOI8-U", "PYTHONUTF8": "0"}}
CYRILLIC_LOCALES = {"ru_RU.KOI8-R", "ru_RU.CP1251", "ru_RU.CP866", "ru_RU.ISO8859-5", "uk_UA.KOI8-U"}
CASES = [(label, locale) for label in NAMES for locale in LOCALES if locale not in CYRILLIC_LOCALES or label in ("cyrillic", "russian", "ukrainian") or locale == "ru_RU.KOI8-R"]


@pytest.mark.parametrize("label, locale", CASES)
def test_a_project_under_any_name_is_found_read_and_checked_in_any_locale(label, locale, tmp_path):
    if locale != "utf8" and not sees(locale):
        pytest.skip(f"the {locale} locale is not installed")
    name = NAMES[label]
    if os.name == "nt" and any(c in name for c in '"|'):
        pytest.skip("Windows file names cannot hold these characters")
    root = tmp_path / f"r-{name}"
    project(root, docs=f"d-{name}", defined=f"{name}.md", mention=f"m-{name}.md", row="x")
    env = environment(tmp_path, **LOCALES[locale])
    found = vyd(env, "config", cwd=root)
    assert found.clean() and found.code == 0 and b"projects: p" in found.out, found
    checked = vyd(env, "check", "identifiers", cwd=root)
    assert checked.clean() and checked.code == 1, checked
    assert b"ERROR: STD-99" in checked.out and b"ERROR: STD-1 " not in checked.out and b"no project claims" not in checked.out, checked
    built = vyd(env, "build", "--no-embed", cwd=root)
    assert built.clean() and built.code == 0, built
    asked = vyd(env, "read", "STD-1", cwd=root)
    assert asked.clean() and asked.code == 0 and b"STD-1" in asked.out, asked


# -- files that are not UTF-8 ----------------------------------------------------------------------------------

GOOD = 'name = "shared"\n'
BAD_BYTES = {"cp936": "名称 = '项目'\n".encode("cp936"), "shift_jis": "名前 = 'プロジェクト'\n".encode("shift_jis"),
             "truncated-utf16": b"\xff\xfe" + 'name = "x"\n'.encode("utf-16-le")[:-1], "nul": b'name = "a\x00b"\n',
             "bom-then-utf16": b"\xef\xbb\xbf" + 'name = "x"\n'.encode("utf-16"), "latin1": b'name = "caf\xe9"\n',
             "cp1251": 'название = "Привіт, світе"\n'.encode("cp1251"), "koi8_r": 'название = "Привет, мир"\n'.encode("koi8_r"),
             "koi8_u": 'назва = "Привіт, світе"\n'.encode("koi8_u"), "iso8859_5": 'название = "Привет, мир"\n'.encode("iso8859_5")}
VALID_BYTES = {"utf8": lambda t: t.encode(), "bom": lambda t: b"\xef\xbb\xbf" + t.encode(), "utf16-le": lambda t: b"\xff\xfe" + t.encode("utf-16-le"),
               "utf16-be": lambda t: b"\xfe\xff" + t.encode("utf-16-be")}


@pytest.mark.parametrize("case", [c for c in BAD_BYTES if c != "nul"])  # NUL is valid UTF-8, and TOML refuses it
def test_the_bad_bytes_are_not_valid_utf_8_so_nothing_loads_as_the_wrong_text(case):
    with pytest.raises(UnicodeError):
        BAD_BYTES[case].decode("utf-8")


def setup_file(target: str, tmp_path: Path, data: bytes, text: str) -> tuple[Path, Path, dict]:
    """The file under test written as ``data`` (None writes ``text`` for the caller), and the folder to run in."""
    root = tmp_path / "repo"
    project(root)
    (root / "docs" / "a.md").write_text("See STD-1.\n", encoding="utf-8")
    env = environment(tmp_path)
    if target == "config":
        path = tmp_path / "config.toml"
        env["VYVID_CONFIG"] = str(path)
    elif target == "project":
        path = root / "vyvid.toml"
    elif target == "domain":
        folder = tmp_path / "dom"
        folder.mkdir()
        path = folder / "domain.toml"
        (tmp_path / "config.toml").write_text(f'[[domains]]\nname = "shared"\npath = {quote(str(folder))}\n', encoding="utf-8")
        env["VYVID_CONFIG"] = str(tmp_path / "config.toml")
    else:
        path = root / "docs" / "types.toml"
        (root / "vyvid.toml").write_text((root / "vyvid.toml").read_text(encoding="utf-8").replace("[project]\n", '[project]\nregister_types = ["docs:types.toml"]\n'),
                                         encoding="utf-8")
    path.write_bytes(data)
    return path, root, env


COMMAND_OF = {"config": ["config"], "project": ["config"], "domain": ["config"], "types": ["build", "--no-embed"]}
TEXT_OF = {"config": GOOD.replace("name", "[framework]\nglue"), "project": '[project]\nname = "p"\ndocs = "code:docs"\n', "domain": GOOD, "types": "\n"}


@pytest.mark.parametrize("target", COMMAND_OF)
@pytest.mark.parametrize("how", VALID_BYTES)
def test_a_file_a_windows_editor_saved_with_a_mark_or_as_utf_16_loads(target, how, tmp_path):
    text = TEXT_OF[target] if target != "config" else '[framework]\nglue = "stop"\n'
    path, root, env = setup_file(target, tmp_path, VALID_BYTES[how](text), text)
    ran = vyd(env, *COMMAND_OF[target], cwd=root)
    assert ran.clean() and ran.code == 0, f"{path}\n{ran!r}"


@pytest.mark.parametrize("target", COMMAND_OF)
@pytest.mark.parametrize("case", BAD_BYTES)
def test_a_file_that_cannot_be_decoded_is_a_problem_naming_it_and_no_traceback(target, case, tmp_path):
    path, root, env = setup_file(target, tmp_path, BAD_BYTES[case], "")
    ran = vyd(env, *COMMAND_OF[target], cwd=root)
    assert ran.clean(), ran
    assert ran.code != 0, ran
    assert str(path).encode() in ran.out + ran.err, ran


@pytest.mark.parametrize("target", COMMAND_OF)
@pytest.mark.parametrize("data", [b"", b"\xef\xbb\xbf", b"\xff\xfe"], ids=["empty", "bom-alone", "utf16-bom-alone"])
def test_an_empty_file_is_no_traceback(target, data, tmp_path):
    path, root, env = setup_file(target, tmp_path, data, "")
    ran = vyd(env, *COMMAND_OF[target], cwd=root)
    assert ran.clean() and ran.code in (0, 1, 2), ran
    if ran.code:
        assert str(path).encode() in ran.out + ran.err, ran


def test_the_message_for_a_file_it_cannot_decode_names_the_fix(tmp_path):
    path, root, env = setup_file("config", tmp_path, BAD_BYTES["cp936"], "")
    ran = vyd(env, "config", cwd=root)
    assert b"Save it as UTF-8" in ran.err and b"Set-Content -Encoding UTF8" in ran.err, ran


# -- arguments --------------------------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def built_project(tmp_path_factory):
    """One project with its index built under UTF-8, which each case then runs a command in under its own locale. The
    build is not what these cases test, so it is made once rather than once a case."""
    home = tmp_path_factory.mktemp("arguments")
    root = home / "repo"
    project(root)
    assert vyd(environment(home), "build", "--no-embed", cwd=root).code == 0
    return home, root


@POSIX
@pytest.mark.parametrize("locale", ["utf8", "zh_CN.GBK"])
@pytest.mark.parametrize("args", [["read"], ["exists"], ["find"], ["resolve"], ["context", "--no-pull"], ["config"], ["check", "identifiers"], ["build", "--no-embed"]])
@pytest.mark.parametrize("argument", [b"\xff\xfe\x80", b"\xe9\xa1\xb9\xff", b"STD-1\xc3"], ids=["bytes", "cut-utf8", "id-and-cut"])
def test_an_argument_that_cannot_be_decoded_is_no_traceback(locale, args, argument, built_project):
    if locale != "utf8" and not sees(locale):
        pytest.skip(f"the {locale} locale is not installed")
    home, root = built_project
    ran = run([sys.executable, "-m", "vyvid.cli", *(a.encode() for a in args), argument], environment(home, **LOCALES[locale]), cwd=root)
    assert ran.clean() and ran.code in (0, 1, 2), ran


# -- the guard ---------------------------------------------------------------------------------------------------

SUBPROCESS = {"run", "Popen", "check_output", "check_call", "call"}
TEXT_FILE = {"read_text", "write_text"}


def violations(source: str, name: str = "x.py") -> list[str]:
    """Each place that reads or writes text with the locale's encoding: a subprocess call with ``text=True`` and no
    ``encoding``, and an ``open``, ``read_text`` or ``write_text`` that is not binary and names none."""
    found = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Call):
            continue
        func, keywords = node.func, {k.arg: k.value for k in node.keywords}
        if None in keywords:  # **options, which the module defines with its encoding
            keywords["encoding"] = ast.Constant("utf-8")
        owner = ast.unparse(func.value) if isinstance(func, ast.Attribute) else ""
        attr = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
        where = f"{name}:{node.lineno}"
        if owner == "subprocess" and attr in SUBPROCESS:
            texty = any(isinstance(keywords.get(k), ast.Constant) and keywords[k].value for k in ("text", "universal_newlines"))
            if (texty or "errors" in keywords) and "encoding" not in keywords:
                found.append(f"{where} subprocess.{attr} reads text without an encoding")
        elif attr in TEXT_FILE and "encoding" not in keywords:
            found.append(f"{where} {attr} names no encoding")
        elif attr == "open" and owner not in ("os", "core.Repo", "urllib.request"):
            builtin = owner == ""  # open(file, mode) as against path.open(mode)
            args = node.args[1:] if builtin else node.args
            if not builtin and args and not isinstance(args[0], ast.Constant):
                continue  # not a file's open, such as a classmethod taking a project
            mode = ast.literal_eval(keywords["mode"]) if "mode" in keywords else (ast.literal_eval(args[0]) if args else "r")
            if "b" not in mode and "encoding" not in keywords:
                found.append(f"{where} open names no encoding")
    return found


def test_no_text_is_read_or_written_in_the_locales_encoding():
    found = [v for path in sorted(SRC.rglob("*.py")) for v in violations(path.read_text(encoding="utf-8"), path.relative_to(SRC.parent).as_posix())]
    assert not found, "\n".join(found)


@pytest.mark.parametrize("source", ["import subprocess\nsubprocess.run(['x'], text=True)\n", "import subprocess\nsubprocess.Popen(['x'], universal_newlines=True, errors='replace')\n",
                                    "from pathlib import Path\nPath('x').read_text()\n", "from pathlib import Path\nPath('x').write_text('y', newline='\\n')\n",
                                    "open('x')\n", "open('x', 'w')\n", "from pathlib import Path\nPath('x').open()\n", "from pathlib import Path\nPath('x').open('a')\n"])
def test_the_guard_sees_what_it_is_for(source):
    assert violations(source)


@pytest.mark.parametrize("source", ["import subprocess\nsubprocess.run(['x'], capture_output=True)\n", "import subprocess\nsubprocess.run(['x'], text=True, encoding='utf-8')\n",
                                    "open('x', 'rb')\n", "from pathlib import Path\nPath('x').open('wb')\n", "open('x', encoding='utf-8')\n", "import os\nos.open('x', 0)\n",
                                    "from pathlib import Path\nPath('x').read_text(encoding='utf-8')\n"])
def test_the_guard_leaves_alone_what_is_right(source):
    assert not violations(source)
