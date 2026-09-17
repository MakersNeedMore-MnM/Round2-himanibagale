"""Test suite root package.

Isolation from the user's real ``~/.mentor`` store is structural, not
fixture-based: :mod:`backend.database.concepts` resolves ``DB_PATH``
into per-process temp space whenever the process looks like a test
run (unittest/pytest in ``sys.argv``, or pytest's env marker).  A test
that forgets every fixture lands in temp space — fail-closed, with a
wrong assertion as the worst outcome.  ``tests/conftest.py`` keeps the
pytest-shaped autouse fixture for when the suite moves to pytest.
"""

from __future__ import annotations
