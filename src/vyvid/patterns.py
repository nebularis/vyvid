# SPDX-License-Identifier: MIT
"""A family's pattern, run on the ``regex`` package under a time limit.

A pattern comes from a manifest, so a hostile one could hang a build by backtracking. Every call
passes ``timeout=SECONDS``. A pattern that times out is disabled for the run, matches nothing from
then on, and is reported by ``config.timeouts``, so the build carries on.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator

import regex

SECONDS = 0.5


class Pattern:
    """A compiled pattern with ``match``, ``search``, ``fullmatch`` and ``finditer`` that time out safely."""

    def __init__(self, source: str, flags: int = 0, owner: Pattern | None = None):
        self.pattern = source
        self._compiled = regex.compile(source, flags)
        self._owner = owner or self
        self.timed_out = False

    def derive(self, build: Callable[[str], str], flags: int = 0) -> Pattern:
        """A pattern around this one, such as ``lambda p: f"^#\\s+(?:{p})"``. A timeout in it disables this one."""
        return Pattern(build(self.pattern), flags, self._owner)

    def _run(self, method: str, text: str):
        if self._owner.timed_out:
            return None
        try:
            return getattr(self._compiled, method)(text, timeout=SECONDS)
        except TimeoutError:
            self._owner.timed_out = True
            return None

    def match(self, text: str):
        return self._run("match", text)

    def search(self, text: str):
        return self._run("search", text)

    def fullmatch(self, text: str):
        return self._run("fullmatch", text)

    def finditer(self, text: str) -> Iterator:
        """The matches in order. The limit applies while iterating, so a timeout ends the iteration."""
        if self._owner.timed_out:
            return
        try:
            yield from self._compiled.finditer(text, timeout=SECONDS)
        except TimeoutError:
            self._owner.timed_out = True
