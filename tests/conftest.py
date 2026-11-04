# SPDX-License-Identifier: MIT
"""Every test reads and writes below its own temporary folders, never the real home."""

from __future__ import annotations

import platformdirs
import pytest

from vyvid import config


@pytest.fixture(autouse=True)
def isolated_state(tmp_path_factory, monkeypatch, request):
    """The user's folders are temporary ones. Configurations count as trusted, so the suite's glue and
    command extractors run, unless a test is marked ``real_trust``, which exercises the real decision."""
    home = tmp_path_factory.mktemp("home")
    for kind in ("state", "data", "config", "cache"):
        monkeypatch.setattr(platformdirs, f"user_{kind}_path", lambda *a, k=kind, **_: home / k)
    if "real_trust" not in request.keywords:
        monkeypatch.setattr(config, "trusted", lambda _config: True)
