# SPDX-License-Identifier: MIT
"""``vyd-hook``: remind an agent to ask the index, from a client's pre-tool hook. It never refuses a tool.

A client runs this before each tool call and it must cost almost nothing, so it imports the standard library alone. It reads
the call on standard input, keeps a small file per session of whether the index was asked, and prints the client's form of a
reminder when a search runs with no question asked lately. Whatever goes wrong, it prints no decision and exits 0, since in
some clients an error in a hook denies the tool.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
import time
from pathlib import Path

from . import streams

SEARCH_TOOLS = {"Grep", "Glob", "grep", "glob", "rg", "search", "semantic_search", "grep_search", "file_search"}  # rg is Copilot's
SHELL_TOOLS = {"Bash", "PowerShell", "bash", "powershell", "shell", "exec_command", "run_in_terminal", "runInTerminal", "execute"}
SEARCH = re.compile(r"(?:^|[|;&(]\s*|\bxargs\s+|\benv\s+\S+\s+|\bsudo\s+)(?:git\s+grep|grep|egrep|fgrep|rg|ag|ack|sed|awk|find|fd|Select-String|sls|findstr|Get-ChildItem|gci|ls\s+-R|dir\s+/s)\b", re.M | re.I)
ASK = re.compile(r"(?:\bgraph:ask\b(?:\s+--)?|\bvyd)\s+(?:find|read|node|exists|reaches|recipe\s+run|context)\b")
QUIET_AFTER_ASK = 15  # searches an agent may run after a question before it is reminded again
REMINDER = ("Before making any decision, ALWAYS check if the index can answer first. Before searching with any tool (e.g., PowerShell, grep, "
            "sed, awk, etc), ALWAYS see if the index can answer first. Ask with `{ask} <the problem in your own words>`. This search still runs. "
            "Anything the index misses gets recorded as a miss and presented back to the user as a potential index improvement.")


def classify(name: str, tool_input: dict | str) -> str | None:
    """``ask``, ``search`` or None, for one tool call. A shell command that asks the index counts as asking, whatever else it does."""
    if name in SEARCH_TOOLS:
        return "search"
    if name in SHELL_TOOLS or name.endswith(("Terminal", "__shell")):
        command = tool_input if isinstance(tool_input, str) else str(tool_input.get("command") or tool_input.get("cmd") or tool_input.get("input") or "")
        if ASK.search(command):
            return "ask"
        if SEARCH.search(command):
            return "search"
    return None


def state_dir() -> Path:
    home = os.environ.get("VYVID_HOOK_STATE")
    folder = Path(home) if home else Path(tempfile.gettempdir()) / f"vyvid-hook-{os.getuid() if hasattr(os, 'getuid') else 'user'}"
    folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    return folder


def decide(session: str, kind: str, folder: Path, now: float) -> bool:
    """Whether to remind on this call, keeping the session's count. Old sessions' files are removed as we pass."""
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", session)[:80] or "session"
    path = folder / safe
    try:
        asked, since = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        asked, since = False, 0
    if kind == "ask":
        asked, since = True, 0
    else:
        since += 1
    path.write_text(json.dumps([asked, since]), encoding="utf-8")
    if kind != "search":
        return False
    if asked and since <= QUIET_AFTER_ASK:
        return False
    if asked:
        path.write_text(json.dumps([True, 0]), encoding="utf-8")
    for old in folder.iterdir():
        if now - old.stat().st_mtime > 7 * 86400:
            old.unlink(missing_ok=True)
    return True


def output(client: str, text: str) -> dict:
    """The client's form of a message to the model that makes no decision."""
    if client == "copilot":
        return {"additionalContext": text}  # Copilot documents this field on postToolUse, which is where install registers it
    return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext": text}}


def handle(client: str, raw: str, ask: str, folder: Path, now: float) -> dict:
    call = json.loads(raw)
    name = call.get("tool_name") or call.get("toolName") or ""
    tool_input = call.get("tool_input") if "tool_input" in call else call.get("toolArgs", {})
    if isinstance(tool_input, str):
        try:
            tool_input = json.loads(tool_input)
        except ValueError:
            pass
    kind = classify(str(name), tool_input if isinstance(tool_input, (dict, str)) else {})
    if kind is None:
        return {}
    session = str(call.get("session_id") or call.get("sessionId") or call.get("transcript_path") or os.getppid())
    return output(client, REMINDER.format(ask=ask)) if decide(session, kind, folder, now) else {}


def main(argv: list[str] | None = None) -> int:
    answer: dict = {}
    try:
        p = argparse.ArgumentParser(prog="vyd-hook", description=(__doc__ or "").splitlines()[0])
        p.add_argument("--client", default="claude-code", choices=("claude-code", "codex", "copilot"))
        p.add_argument("--ask", default="vyd find", help="the command that asks the index in this project")
        a = p.parse_args(argv)
        answer = handle(a.client, streams.read_stdin(), a.ask, state_dir(), time.time())
    except (Exception, SystemExit):  # a hook never fails a tool, whatever went wrong, such as nesting too deep for the parser
        answer = {}
    try:
        print(json.dumps(answer))
        sys.stdout.flush()
    except (OSError, ValueError, AttributeError):
        pass
    return 0


def run() -> None:
    """The ``vyd-hook`` console script. A reader that has gone away is no failure either."""
    try:
        code = streams.guarded(main)
    except Exception:
        code = 0
    sys.exit(0 if code == streams.HANGUP else code)


if __name__ == "__main__":
    run()
