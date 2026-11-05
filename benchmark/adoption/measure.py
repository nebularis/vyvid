# SPDX-License-Identifier: MIT
"""How often does an agent search with a shell or a search tool before it asks the index?

Reads a client's session transcripts, JSON lines holding tool calls, and prints counts and nothing of their text. A
session counts only if it searched at all, or asked. Run it before and after a change to what an agent is told, with
``--since`` or ``--until`` to compare the two periods. It reads the format Claude Code writes, and never part of ``check``.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SEARCH_TOOLS = {"Grep", "Glob"}
SHELL_TOOLS = {"Bash", "PowerShell", "powershell", "run_in_terminal", "shell", "exec_command"}
SEARCH = re.compile(r"(?:^|[|;&(]\s*|\bxargs\s+|\benv\s+\S+\s+)(?:git\s+grep|grep|egrep|fgrep|rg|ag|ack|sed|awk|find|fd|Select-String|sls|findstr|Get-ChildItem|gci|dir)\b", re.M)
ASK = re.compile(r"(?:\bgraph:ask\b(?:\s+--)?|\bvyd)\s+(?:find|read|node|exists|reaches|recipe\s+run|context)\b|\bmise run graph:ask\b")


def classify(name: str, tool_input: dict) -> str | None:
    """``ask``, ``search`` or None, for one tool call."""
    if name in SEARCH_TOOLS:
        return "search"
    if name in SHELL_TOOLS:
        command = str(tool_input.get("command", ""))
        if ASK.search(command):
            return "ask"
        if SEARCH.search(command):
            return "search"
    return None


def session(path: Path) -> tuple[str, list[str]]:
    """The day the session began, and its asks and searches in order."""
    day, calls = "", []
    with path.open(encoding="utf-8", errors="replace") as lines:
        for line in lines:
            try:
                event = json.loads(line)
            except ValueError:
                continue
            day = day or str(event.get("timestamp", ""))[:10]
            message = event.get("message")
            if event.get("type") != "assistant" or not isinstance(message, dict) or not isinstance(message.get("content"), list):
                continue
            for item in message["content"]:
                if isinstance(item, dict) and item.get("type") == "tool_use":
                    kind = classify(str(item.get("name", "")), item.get("input") or {})
                    if kind:
                        calls.append(kind)
    return day, calls


def main() -> int:
    p = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    p.add_argument("folder", type=Path, help="a folder of transcripts, searched for *.jsonl")
    p.add_argument("--since", default="", help="sessions begun on or after this day")
    p.add_argument("--until", default="", help="sessions begun before this day")
    a = p.parse_args()
    rows = []
    for path in sorted(a.folder.expanduser().rglob("*.jsonl")):
        day, calls = session(path)
        if calls and (not a.since or day >= a.since) and (not a.until or day < a.until):
            rows.append(calls)
    if not rows:
        print("no session searched or asked in that period")
        return 0
    asked = [c for c in rows if "ask" in c]
    first = sum(c[0] == "search" for c in asked)
    searches, asks = sum(c.count("search") for c in rows), sum(c.count("ask") for c in rows)
    print(f"sessions that searched or asked      {len(rows)}")
    print(f"sessions that never asked            {len(rows) - len(asked)} ({100 * (len(rows) - len(asked)) / len(rows):.0f}%)")
    print(f"sessions that searched before asking {first} of {len(asked)} that asked" + (f" ({100 * first / len(asked):.0f}%)" if asked else ""))
    print(f"searches {searches}, asks {asks}, {searches / max(asks, 1):.1f} searches per ask")
    return 0


if __name__ == "__main__":
    sys.exit(main())
