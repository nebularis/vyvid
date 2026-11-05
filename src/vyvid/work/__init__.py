# SPDX-License-Identifier: MIT
"""The work board: the slice boards of a project's status records, read across every branch.

``settings`` is the ``[project.work]`` table, ``core`` reads and renders the boards, ``migrate`` moves a
project's older boards and identifiers onto the board's shape, and ``command`` is the command line.
"""
