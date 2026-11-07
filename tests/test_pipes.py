# SPDX-License-Identifier: MIT
"""What ``vyd`` and ``vyd-hook`` do over real pipes: readers that go away, slow readers, closed or odd standard streams, input that
is not UTF-8, and children that write what they like. Real processes, bytes in and out."""

from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
import time
from pathlib import Path

import pytest

from subprocess_support import HOOK, POSIX, VYD, environment, file_name_encoding, holds, on_disk, project, quote, run, sees, unseen, vyd
from test_encodings import ENCODINGS, LOCALES
from vyvid import streams

HANGUP = streams.HANGUP


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    """A built project whose STD-1 holds a large row, and the environment to run in."""
    base = tmp_path_factory.mktemp("pipes")
    root = base / "repo"
    project(root, row="y" * 300_000)
    env = environment(base)
    assert vyd(env, "build", "--no-embed", cwd=root).code == 0
    return base, root, env


# -- a reader that goes away ------------------------------------------------------------------------------------

LONG = {"help": ["--help"], "context": ["context", "--no-pull"], "read": ["read", "STD-1"], "config": ["config"], "identifiers": ["check", "identifiers", "."],
        "find": ["find", "ledger"]}


@pytest.mark.parametrize("command", LONG)
@pytest.mark.parametrize("after", ["at once", "after one line"])
def test_a_reader_that_closes_early_gives_no_traceback(command, after, world):
    _, root, env = world
    process = subprocess.Popen([*VYD, *LONG[command]], env=env, cwd=root, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if after == "after one line":
        process.stdout.readline()
    process.stdout.close()
    err = process.stderr.read()
    assert process.wait(timeout=60) in (0, 1, HANGUP) and b"Traceback" not in err, err[-600:]  # 1 is the identifier check's own


def test_a_large_read_whose_reader_leaves_exits_141_where_there_is_a_signal_to_mimic(world):
    _, root, env = world
    process = subprocess.Popen([*VYD, "read", "STD-1"], env=env, cwd=root, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    process.stdout.read(10)
    process.stdout.close()
    assert process.wait(timeout=60) == HANGUP and b"Traceback" not in process.stderr.read()


def test_output_larger_than_the_pipe_read_slowly_arrives_whole_and_in_order(world, tmp_path):
    _, root, env = world
    with (tmp_path / "ref").open("wb") as reference:
        assert subprocess.run([*VYD, "read", "STD-1"], env=env, cwd=root, stdout=reference, stderr=subprocess.DEVNULL).returncode == 0
    process = subprocess.Popen([*VYD, "read", "STD-1"], env=env, cwd=root, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    got = bytearray()
    while chunk := process.stdout.read(4096):
        got += chunk
        time.sleep(0.0005)
    assert process.wait(timeout=60) == 0 and bytes(got) == (tmp_path / "ref").read_bytes() and len(got) > 300_000


def test_standard_output_holds_no_note_from_standard_error(tmp_path):
    root = tmp_path / "repo"
    project(root, extra='domains = ["absent"]\n')
    env = environment(tmp_path)
    ran = vyd(env, "context", "--json", "--no-pull", cwd=root)
    assert ran.code == 0 and json.loads(ran.out)["project"] == "p"
    assert b"NOTE" not in ran.out and b"NOTE: domain absent" in ran.err, ran


# -- standard input -----------------------------------------------------------------------------------------------

QUIET = {"version": (["--version"], 0), "config": (["config"], 0), "identifiers": (["check", "identifiers", "."], 1), "read": (["read", "STD-1"], 0)}
INPUTS = {"empty": b"", "invalid": b"\xff\xfe\x80\x00" * 50, "bom": b"\xef\xbb\xbfyes\n", "huge": b"yes\n" * 5_000_000, "yes": b"yes\n"}


@pytest.mark.parametrize("name", INPUTS)
@pytest.mark.parametrize("command", QUIET)
def test_a_command_that_does_not_read_is_unmoved_by_what_is_piped_in(command, name, world):
    _, root, env = world
    args, code = QUIET[command]
    ran = vyd(env, *args, cwd=root, stdin=INPUTS[name])
    assert ran.clean() and ran.code == code, ran


@pytest.mark.parametrize("command", QUIET)
def test_a_command_that_does_not_read_does_not_wait_for_a_pipe_that_never_writes(command, world):
    _, root, env = world
    args, code = QUIET[command]
    ran = vyd(env, *args, cwd=root, stdin=None, seconds=30)
    assert ran.clean() and ran.code == code, ran


@pytest.mark.parametrize("command", QUIET)
def test_dev_null_as_standard_input(command, world):
    _, root, env = world
    args, code = QUIET[command]
    done = subprocess.run([*VYD, *args], env=env, cwd=root, stdin=subprocess.DEVNULL, capture_output=True, timeout=60)
    assert b"Traceback" not in done.stderr and done.returncode == code


def _closing(redirect: str, command: list[str]) -> list[str]:
    return ["sh", "-c", f'exec "$@" {redirect}', "sh", *command]


@POSIX
@pytest.mark.parametrize("redirect", ["0<&-", "1>&-", "2>&-", "1>&- 2>&-", "0<&- 1>&- 2>&-"])
@pytest.mark.parametrize("command", QUIET)
def test_a_closed_standard_stream_is_no_crash(command, redirect, world):
    _, root, env = world
    args, code = QUIET[command]
    ran = run(_closing(redirect, [*VYD, *args]), env, cwd=root)
    assert ran.clean() and ran.code == code, ran


@POSIX
def test_closed_standard_error_does_not_send_its_notes_to_standard_output(tmp_path):
    root = tmp_path / "repo"
    project(root, extra='domains = ["absent"]\n')
    ran = run(_closing("2>&-", [*VYD, "context", "--json", "--no-pull"]), environment(tmp_path), cwd=root)
    assert ran.code == 0 and json.loads(ran.out)["project"] == "p" and b"NOTE" not in ran.out, ran


@pytest.mark.parametrize("how", ["said yes", "bom yes", "invalid", "nothing"])
def test_trust_from_a_pipe_is_refused_and_records_nothing(how, tmp_path):
    root = tmp_path / "repo"
    project(root)
    env = environment(tmp_path)
    given = {"said yes": b"yes\n", "bom yes": b"\xef\xbb\xbfyes\n", "invalid": b"\xff\xfe\n", "nothing": b""}[how]
    ran = vyd(env, "trust", cwd=root, stdin=given)
    assert ran.code == 1 and b"a person must run vyd trust" in ran.err and ran.clean(), ran
    assert not list(tmp_path.rglob("trusted.json"))


def own_config(env: dict, home: Path) -> Path:
    env.pop("VYVID_CONFIG", None)  # the user's own configuration is read, and trusted whatever it holds
    where = run([sys.executable, "-c", "import platformdirs; print(platformdirs.user_config_path('vyvid'))"], env).out.decode().strip()
    path = Path(where) / "config.toml"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


@pytest.mark.parametrize("given", [b"yes\n", b"own\nyes\n", b"\xff\xfe\x80"])
def test_a_gated_domain_trust_from_a_pipe_is_refused_and_changes_nothing(given, tmp_path):
    env = environment(tmp_path)
    folder = tmp_path / "dom"
    folder.mkdir()
    config = own_config(env, tmp_path)
    config.write_text(f'[[domains]]\nname = "shared"\npath = {quote(str(folder))}\ntrust = "knowledge"\n', encoding="utf-8")
    before = config.read_bytes()
    ran = vyd(env, "domain", "trust", "shared", "own", stdin=given)
    assert ran.code != 0 and ran.clean() and config.read_bytes() == before, ran


# -- the hook ----------------------------------------------------------------------------------------------------

SEARCH = {"tool_name": "Bash", "tool_input": {"command": "grep 项目 日本語 тест 😀 *.md"}, "session_id": "сессія-项目"}


def hook(env: dict, data: bytes, **kwargs):
    return run(HOOK, env, stdin=data, **kwargs)


def decoded(ran, encoding: str = "utf-8"):
    return json.loads(ran.out.decode(encoding))


@pytest.mark.parametrize("encoding", ENCODINGS)
def test_a_hook_payload_with_unicode_survives_every_output_encoding(encoding, tmp_path):
    ran = hook(environment(tmp_path, PYTHONIOENCODING=encoding), json.dumps(SEARCH, ensure_ascii=False).encode("utf-8"))
    assert ran.code == 0 and ran.clean(), ran
    assert "hookSpecificOutput" in decoded(ran, encoding)


@pytest.mark.parametrize("locale", [name for name in LOCALES if name != "utf8"])
def test_a_hook_payload_with_unicode_under_a_code_page_locale(locale, tmp_path):
    if not sees(locale):
        pytest.skip(unseen(locale))
    ran = hook(environment(tmp_path, **LOCALES[locale]), json.dumps(SEARCH, ensure_ascii=False).encode("utf-8"))
    assert ran.code == 0 and "hookSpecificOutput" in decoded(ran), ran


NESTED = b"[" * 200_000
HOOK_INPUTS = {"invalid bytes": b"\xff\xfe\x80{", "empty": b"", "truncated": b'{"tool_name": "Bash", "tool_input": {"comm', "nul": b'{"tool_name": "Bash"\x00}',
               "nul only": b"\x00" * 1000, "nested": NESTED, "huge junk": b"x" * 20_000_000, "not an object": b"[1, 2]", "null": b"null",
               "wrong types": b'{"tool_name": 5, "tool_input": 7, "session_id": []}'}


@pytest.mark.parametrize("name", HOOK_INPUTS)
def test_a_hook_never_fails_whatever_it_is_given(name, tmp_path):
    ran = hook(environment(tmp_path), HOOK_INPUTS[name], seconds=60)
    assert ran.code == 0 and ran.clean() and decoded(ran) == {}, ran


def test_a_hook_reads_a_huge_valid_payload_and_a_byte_order_mark(tmp_path):
    env = environment(tmp_path)
    big = json.dumps({**SEARCH, "tool_input": {"command": "grep x " + "a" * 3_000_000}}).encode()
    assert "hookSpecificOutput" in decoded(hook(env, big, seconds=60))
    assert "hookSpecificOutput" in decoded(hook(env, b"\xef\xbb\xbf" + json.dumps(SEARCH).encode()))


@POSIX
def test_a_hook_with_standard_input_closed(tmp_path):
    env = environment(tmp_path)
    assert (ran := run(_closing("0<&-", HOOK), env)).code == 0 and decoded(ran) == {}, ran


def test_a_hook_whose_reader_has_gone_still_exits_zero(tmp_path):
    process = subprocess.Popen(HOOK, env=environment(tmp_path), stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    process.stdout.close()
    process.stdin.write(json.dumps(SEARCH).encode())
    process.stdin.close()
    assert process.wait(timeout=30) == 0 and b"Traceback" not in process.stderr.read()


def test_the_hook_piped_from_vyd_and_vyd_piped_to_a_command_that_ignores_it(world):
    _, root, env = world
    first = subprocess.Popen([*VYD, "context", "--json", "--no-pull"], env=env, cwd=root, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    second = subprocess.Popen(HOOK, env=env, stdin=first.stdout, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    first.stdout.close()
    out, err = second.communicate(timeout=60)
    assert first.wait(timeout=60) == 0 and second.returncode == 0 and json.loads(out) == {} and b"Traceback" not in err + first.stderr.read()
    first = subprocess.Popen([*VYD, "read", "STD-1"], env=env, cwd=root, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    second = subprocess.Popen([*VYD, "--version"], env=env, stdin=first.stdout, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    first.stdout.close()
    second.communicate(timeout=60)
    assert first.wait(timeout=60) in (0, HANGUP) and b"Traceback" not in first.stderr.read()


def test_one_command_answers_the_next(world):
    _, root, env = world
    named = vyd(env, "resolve", "STD-1", cwd=root).out.decode().strip()
    assert named.endswith("STD-1")
    ran = vyd(env, "read", named, cwd=root)
    assert ran.code == 0 and b"STD-1" in ran.out


# -- children that write what they like ---------------------------------------------------------------------------

FAKE_GIT = '''#!/bin/sh
exec "{python}" "{script}" "$@"
'''
FAKE_GIT_PY = r'''
import os, subprocess, sys
mode = os.environ["FAKEGIT_MODE"]
real = subprocess.run([os.environ["REAL_GIT"], *sys.argv[1:]], capture_output=True)
out = real.stdout
if mode == "invalid":
    out = b"\xff\xfe/bad\x80\n"; sys.stderr.buffer.write(b"\xff\xfe")
elif mode == "huge":
    out = b"a/b.md\0" * 1_000_000
elif mode == "bom":
    out = b"\xef\xbb\xbf" + out
elif mode == "crlf":
    out = out.replace(b"\n", b"\r\n")
elif mode == "utf16fail":
    sys.stderr.buffer.write("fatal: ошибка\n".encode("utf-16")); sys.exit(128)
sys.stdout.buffer.write(out)
sys.exit(real.returncode)
'''


@POSIX
@pytest.mark.parametrize("mode", ["invalid", "huge", "bom", "crlf", "utf16fail"])
@pytest.mark.parametrize("command", [["config"], ["check", "identifiers", "."], ["context", "--no-pull"], ["build", "--no-embed"]])
def test_a_git_that_writes_what_it_likes_is_no_crash_and_no_hang(mode, command, tmp_path):
    import shutil

    root = tmp_path / "repo"
    project(root)
    bin_ = tmp_path / "bin"
    bin_.mkdir()
    (bin_ / "fake.py").write_text(FAKE_GIT_PY, encoding="utf-8")
    (bin_ / "git").write_text(FAKE_GIT.format(python=sys.executable, script=bin_ / "fake.py"), encoding="utf-8")
    (bin_ / "git").chmod((bin_ / "git").stat().st_mode | stat.S_IXUSR)
    env = environment(tmp_path, PATH=f"{bin_}{os.pathsep}{os.environ['PATH']}", FAKEGIT_MODE=mode, REAL_GIT=shutil.which("git"))
    ran = vyd(env, *command, cwd=root, seconds=60)
    assert ran.clean() and ran.code in (0, 1, 2), ran
    if mode == "crlf" and command[0] == "check":
        assert ran.code == 1 and b"ERROR: STD-99" in ran.out, "line endings from git do not hide the project"


# -- command extractors and glue ----------------------------------------------------------------------------------

CHILD = r'''
import json, os, sys
mode = sys.argv[1]
if mode == "early":
    sys.exit(0)
if mode == "flood":
    sys.stderr.write("e" * 5_000_000)
    sys.stderr.flush()
raw = sys.stdin.buffer.read()
request = json.loads(raw.decode("utf-8"))
settings = request["settings"]
open(settings["seen"], "wb").write(raw)
if mode == "noise":
    sys.stdout.buffer.write(b"\xff\xfe\x80 out"); sys.stderr.buffer.write(b"\xff\xfe\x80 err")
if mode == "fail":
    sys.stderr.buffer.write(b"\xff\xfe\x80 failed"); sys.exit(3)
json.dump({"protocol": 1}, open(os.path.join(request["output"], "result.json"), "w"))
'''
LABEL = "日本語 тест проєкт 😀"


def extractor_world(tmp_path: Path, mode: str, pad: int = 0, name: str = "code", encoding: str = "utf-8") -> tuple[dict, Path, Path]:
    env = environment(tmp_path)
    code = tmp_path / name
    os.makedirs(on_disk(code / "docs", encoding))
    with open(on_disk(code / "docs" / "a.md", encoding), "wb") as handle:
        handle.write(b"x\n")
    script, seen = tmp_path / "child.py", tmp_path / "seen"
    script.write_text(CHILD, encoding="utf-8")
    own_config(env, tmp_path).write_text(
        f'[[projects]]\nname = "p"\ncode = {quote(str(code))}\ndocs = "code:docs"\n\n[[projects.extractors]]\nkind = "cmd"\n'
        f'command = [{quote(sys.executable)}, {quote(str(script))}, "{mode}"]\npaths = ["code:docs/*.md"]\nseen = {quote(str(seen))}\n'
        f'label = {quote(LABEL)}\npad = {quote("x" * pad)}\nseconds = 20\n', encoding="utf-8")
    return env, code, seen


@pytest.mark.parametrize("mode, pad", [("noise", 0), ("fail", 0), ("flood", 2_000_000), ("early", 2_000_000), ("plain", 0)])
@pytest.mark.parametrize("locale", ["utf8", "zh_CN.GBK"])
def test_a_command_extractor_that_writes_invalid_bytes_floods_or_leaves_early_is_no_crash(mode, pad, locale, tmp_path):
    if locale != "utf8" and not sees(locale):
        pytest.skip(unseen(locale))
    # A name this locale can hold, written in its encoding: on Linux a GBK machine cannot name a folder in Ukrainian
    encoding = file_name_encoding(tuple(LOCALES[locale].items()))
    env, code, seen = extractor_world(tmp_path, mode, pad, name="代码 проєкт" if holds("代码 проєкт", encoding) else "代码 项目", encoding=encoding)
    env.update(LOCALES[locale])
    ran = vyd(env, "build", "--no-embed", cwd=on_disk(code, encoding), seconds=60)
    assert ran.clean() and ran.code == 0, ran
    if mode == "fail":
        assert b"exited 3" in ran.out + ran.err
    if mode in ("noise", "plain", "flood", "fail"):
        raw = seen.read_bytes()
        assert raw.isascii() or raw.decode("utf-8"), "the request is UTF-8"
        assert json.loads(raw.decode("utf-8"))["settings"]["label"] == LABEL


GLUE = r'''
import json, sys
mode = sys.argv[1]
json.load(sys.stdin)
sys.stderr.buffer.write(b"\xff\xfe\x80 note")
if mode == "invalid":
    sys.stdout.buffer.write(b"\xff\xfe\x80")
elif mode == "unicode":
    json.dump([{"id": "G-1", "kind": "Note", "claim": "日本語 тест 😀"}], sys.stdout)
else:
    print("[]")
'''


@pytest.mark.parametrize("mode, code", [("invalid", 1), ("unicode", 0), ("empty", 0)])
@pytest.mark.parametrize("locale", ["utf8", "zh_CN.GBK"])
def test_glue_that_writes_invalid_bytes_or_unicode_is_no_crash(mode, code, locale, tmp_path):
    if locale != "utf8" and not sees(locale):
        pytest.skip(unseen(locale))
    env = environment(tmp_path, **LOCALES[locale])
    encoding = file_name_encoding(tuple(LOCALES[locale].items()))
    root = tmp_path / "代码"
    os.makedirs(on_disk(root / "docs", encoding))
    script = tmp_path / "glue.py"
    script.write_text(GLUE, encoding="utf-8")
    own_config(env, tmp_path).write_text(
        f'[[projects]]\nname = "p"\ncode = {quote(str(root))}\ndocs = "code:docs"\n\n[[projects.recipes]]\nname = "g"\ndescription = "d"\n'
        f'steps = [{{ step = "glue", command = [{quote(sys.executable)}, {quote(str(script))}, "{mode}"] }}]\n', encoding="utf-8")
    ran = vyd(env, "recipe", "run", "g", "q", cwd=on_disk(root, encoding))
    assert ran.clean() and ran.code == code, ran
    if mode == "unicode":
        assert "G-1" in ran.out.decode(env.get("PYTHONIOENCODING", "utf-8") if locale == "utf8" else "gbk", "replace")
