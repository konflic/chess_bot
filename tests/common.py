"""Shared helpers for the GameZZ test suite.

Every test module is a standalone plain-assert script (stdlib only, runnable
with `python tests/<name>.py`) so it stays isolated: each one gets its own
temp SQLite database. `run_all.py` executes them as subprocesses to keep that
isolation.
"""

import os
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

VALID_FLEET = [
    ["A1", "A2", "A3", "A4"],
    ["B1", "B2", "B3"],
    ["C1", "C2", "C3"],
    ["D1", "D2"],
    ["E1", "E2"],
    ["F1", "F2"],
    ["G1"], ["G3"], ["G5"], ["G7"],
]


def fresh_db():
    return os.path.join(tempfile.mkdtemp(), "test.db")


def configure_test_db():
    """Point configuration.GAMES_DB at a fresh temp DB.

    Must be called BEFORE importing web.main (managers are singletons bound
    to the DB at import time).
    """
    import configuration

    configuration.GAMES_DB = fresh_db()
    return configuration.GAMES_DB
