"""Shared pytest fixtures for the whole test suite.

Isolation from the user's real ``~/.codelith`` store is *primarily*
structural: :mod:`backend.database.concepts` resolves ``DB_PATH``
into per-process temp space when the process looks like a test run —
see ``_resolve_db_path`` there.  The autouse fixture below adds the
per-test layer on top: a UNIQUE temp directory per test (so
parallel-ish suites and repeated runs never share state) plus a
cleaned-up migration-module isolation.

Two layers, because they fail differently:
- the structural guard needs no cooperation from any test, but shares
  one temp DB across all tests in a process;
- this fixture gives every test a private DB, but only for pytest
  runs (unittest discover never loads conftest.py — which is fine,
  the structural guard covers that runner).
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def isolated_store(request, monkeypatch):
    """Give every test a private temp ``codelith.db`` (per-test layer)."""
    tmp = tempfile.mkdtemp(prefix="codelith-test-")
    db_path = Path(tmp) / "codelith.db"

    import backend.database.concepts as store

    monkeypatch.setattr(store, "DB_PATH", db_path)
    monkeypatch.setattr(store, "_schema_ready", False)

    yield db_path

    # No explicit cleanup: SQLite may keep WAL/SHM sidecar files briefly
    # open on Windows; each test got a UNIQUE directory so nothing leaks
    # between tests either way.
