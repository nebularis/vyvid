# SPDX-License-Identifier: MIT
"""What every entry point does about text encodings and pipes. Standard library only, since the hook imports it.

Output keeps the stream's own encoding, so a program reading it in the code page gets what it expects. What changes is
that a character the stream cannot hold, or an undecodable argument, becomes an escape and never a traceback. A reader
that goes away ends the run quietly.
"""

from __future__ import annotations

import errno
import os
import sys
from typing import Callable, TextIO

NAME = "Вивід"
PLAIN = "vyvid"
HANGUP = 141 if os.name == "posix" else 1  # 128 + SIGPIPE where there is one
CLOSED_PIPE = {errno.EPIPE, errno.EINVAL}  # Windows reports a closed pipe as EINVAL


def harden_streams() -> None:
    """Make writing to standard output and error never raise on an unencodable character, whatever the encoding.
    A stream whose errors the person chose, with ``PYTHONIOENCODING=<encoding>:<errors>``, is left alone."""
    # A closed stream is None, which print() sends to the other stream and sys.stdout.write() fails on.
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w", encoding="utf-8")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w", encoding="utf-8")
    if ":" in os.environ.get("PYTHONIOENCODING", ""):
        return
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(errors="backslashreplace")
            except (ValueError, OSError):
                pass


def display_name(stream: TextIO | None = None) -> str:
    """``Вивід`` where the stream's encoding can hold it, and ``vyvid`` where it cannot or is not known."""
    encoding = getattr(sys.stdout if stream is None else stream, "encoding", None)
    try:
        NAME.encode(encoding or "ascii")
    except (LookupError, UnicodeError, TypeError):
        return PLAIN
    return NAME


def version_text(stream: TextIO | None = None) -> str:
    """The name for ``--version``, which ends in the bare version for a program that splits on spaces."""
    return NAME + f" ({PLAIN})" if display_name(stream) == NAME else PLAIN


def read_stdin() -> str:
    """Standard input as UTF-8 text, the form a client's JSON is in whatever the locale. Empty when it is closed,
    cannot be read, or holds invalid bytes, which become U+FFFD."""
    try:
        return sys.stdin.buffer.read().decode("utf-8-sig", errors="replace")
    except (AttributeError, OSError, ValueError):
        return ""


def clean_arguments(arguments) -> None:
    """Replace the bytes of a text argument that do not decode, which arrive as lone surrogates, with U+FFFD, since text
    handed to a store or a log cannot hold them. A path keeps its bytes."""
    def clean(value):
        if isinstance(value, str):
            return value.encode("utf-8", "surrogatepass").decode("utf-8", "replace") if any("\ud800" <= c <= "\udfff" for c in value) else value
        return [clean(v) for v in value] if isinstance(value, list) else value

    for name, value in vars(arguments).items():
        setattr(arguments, name, clean(value))


def _hang_up() -> int:
    """The reader went away. Point the streams at the null device so the interpreter's flush at exit stays quiet."""
    for stream in (sys.stdout, sys.stderr):
        try:
            os.dup2(os.open(os.devnull, os.O_WRONLY), stream.fileno())
        except (AttributeError, OSError, ValueError):
            pass
    return HANGUP


def guarded(main: Callable[[], int]) -> int:
    """Run an entry point: harden the streams first, flush inside the guard, and end quietly when a reader closes.
    Any other error goes on."""
    harden_streams()
    try:
        try:
            return main()
        finally:  # also when argparse exits, as it does for --help
            for stream in (sys.stdout, sys.stderr):
                if stream is not None:
                    stream.flush()
    except BrokenPipeError:
        return _hang_up()
    except OSError as error:
        if error.errno in CLOSED_PIPE:
            return _hang_up()
        raise
