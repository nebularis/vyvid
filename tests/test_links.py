# SPDX-License-Identifier: MIT
"""``vyd check links``, ``vyd refs`` and the MCP server's replies, over a real git repository."""

from __future__ import annotations

from pathlib import Path

from vyvid import cli, links
from vyvid.resolve import forget

from test_identifiers import Repo, commit, write

MARK = "@" "vyd:"  # in two parts, so this file holds no backlink for the repository's own check to read


def run(capsys, *argv):
    forget()
    code = cli.main(list(argv))
    return code, capsys.readouterr().out


def test_a_backlink_resolves_or_fails(tmp_path, monkeypatch, capsys):
    repo = Repo(tmp_path, monkeypatch)
    write(repo.code / "src/a.py", f"# {MARK} STD-1, STD-2\nx = 'STD-9 is only text'\n")
    commit(repo.code)
    code, out = run(capsys, "check", "links", str(repo.code))
    assert code == 0 and "2 backlinks in" in out and "0 broken," in out
    write(repo.code / "src/b.js", f"/* {MARK} STD-9 */\n// {MARK}\n")
    commit(repo.code)
    code, out = run(capsys, "check", "links", str(repo.code))
    assert code == 1 and "src/b.js:1 backlinks STD-9" in out and "src/b.js:2 backlinks nothing" in out


def test_require_fails_an_entry_no_code_names(tmp_path, monkeypatch, capsys):
    repo = Repo(tmp_path, monkeypatch)
    write(repo.code / "src/a.py", f"# {MARK} STD-1\n")
    commit(repo.code)
    code, out = run(capsys, "check", "links", str(repo.code), "--require", "STD")
    assert code == 1 and "STD-2 (docs/standards.md:4) has no backlink in code" in out and "STD-1 (" not in out


def test_a_pointer_to_a_file_that_is_gone_fails(tmp_path, monkeypatch, capsys):
    repo = Repo(tmp_path, monkeypatch, standards="| ID | Claim | Pointer |\n|---|---|---|\n| STD-1 | **One.** | src/a.py |\n")
    write(repo.code / "src/a.py", "x = 1\n")
    commit(repo.code)
    code, out = run(capsys, "check", "links", str(repo.code))
    assert code == 0 and "2 pointers read, 0 broken" in out  # the row itself and what it points at
    (repo.code / "src/a.py").unlink()
    commit(repo.code)
    assert run(capsys, "check", "links", str(repo.code))[0] != 0  # by this check, or by the build refusing the pointer


def test_refs_tells_a_definition_a_backlink_and_a_mention_apart(tmp_path, monkeypatch, capsys):
    repo = Repo(tmp_path, monkeypatch, notes="See STD-1.\n")
    write(repo.code / "src/a.py", f"# {MARK} STD-1\n")
    commit(repo.code)
    code, out = run(capsys, "refs", "STD-1", "--in", str(repo.code))
    rows = {line.split()[0]: line.split()[1] for line in out.splitlines() if ":" in line.split(" ")[0]}
    assert code == 0 and rows == {"docs/notes.md:1": "mentions", "docs/standards.md:3": "defines", "src/a.py:1": "backlinks"}


def test_the_server_lists_its_tools_and_answers_no_notification():
    assert links.answer(Path("."), {"jsonrpc": "2.0", "method": "notifications/initialized"}) is None
    listed = links.answer(Path("."), {"jsonrpc": "2.0", "id": 1, "method": "tools/list"})["result"]["tools"]
    assert {t["name"] for t in listed} == set(links.TOOLS)
    assert links.answer(Path("."), {"jsonrpc": "2.0", "id": 2, "method": "nope"})["error"]["code"] == -32601
    assert links._call(Path("."), "find", {})["isError"]  # words is required, and nothing is run without it


def test_a_tool_runs_vyd_plain_and_uncoloured_before_any_value_a_client_gave(monkeypatch):
    """A client is an agent. It reads the plain table, whatever table or colour the user chose for their own terminal."""
    seen = []

    class Done:
        stdout, stderr, returncode = "ok", "", 0

    monkeypatch.setattr(links.subprocess, "run", lambda args, **kw: (seen.append(list(args)), Done())[1])
    monkeypatch.setenv("VYD_TABLE", "md")
    for name, given in (("refs", {"identifier": "STD-1"}), ("find", {"words": "--table md"}), ("context", {}), ("node", {"identifier": "STD-1"})):
        assert links._call(Path("."), name, given)["isError"] is False
    for args in seen:
        flags = args.index("--table")
        assert args[flags:flags + 4] == ["--table", "plain", "--colour", "never"]
        assert "--" not in args[:flags], "the flags come before any value that a client gave"
