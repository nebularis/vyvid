# SPDX-License-Identifier: MIT
"""Symbols: the names, signatures and docs of a project's source, parsed with tree-sitter into a store of their own.

Nothing here runs code from the repository. The grammars are the optional extra ``vyvid[symbols]``, so
this module imports none of them, and ``extract`` and ``store`` import them only when a parse is asked for.
"""

from __future__ import annotations

# The languages a project may declare and the file suffix each parses.
LANGUAGES = {"python": ".py", "haskell": ".hs", "java": ".java", "typescript": ".ts"}
INSTALL = "Install vyvid[symbols], which holds the grammars"


def available() -> bool:
    """Whether the grammars are installed."""
    try:
        import tree_sitter  # noqa: F401
        import tree_sitter_haskell, tree_sitter_java, tree_sitter_python, tree_sitter_typescript  # noqa: F401, E401
    except ImportError:
        return False
    return True
