"""Tripwire: an unisolated test must still land in temp space.

This file deliberately does NOT opt into any fixture.  It exists to
fail loudly if the structural guard in
``backend.database.concepts._resolve_db_path`` ever stops working —
the exact failure mode that once wrote test rows into the user's real
``~/.codelith/codelith.db``.  Isolation must be the default, not
something each test has to remember.
"""

import tempfile
import unittest
from pathlib import Path

from backend.database import concepts as store


class TestUnisolatedTestsStillIsolated(unittest.TestCase):
    def test_db_path_is_temp_space_not_real_home(self) -> None:
        real = Path.home() / ".codelith" / "codelith.db"
        self.assertNotEqual(
            store.DB_PATH, real,
            "store resolved to the REAL user database inside a test — "
            "the structural guard in _resolve_db_path is broken",
        )
        self.assertIn(
            str(Path(tempfile.gettempdir())).lower(),
            str(store.DB_PATH).lower(),
        )

    def test_a_forgetting_test_cannot_pollute_real_data(self) -> None:
        # Write through the store with no fixture, then verify it did
        # NOT touch the real DB even after a reload of the module.
        import importlib

        store.save_teaching("tripwire-probe", {
            "concept_name": "Probe", "explanation": "x", "content_hash": "hx",
        })
        importlib.reload(store)
        real = Path.home() / ".codelith" / "codelith.db"
        self.assertNotEqual(store.DB_PATH, real)
        self.assertIn(
            str(Path(tempfile.gettempdir())).lower(),
            str(store.DB_PATH).lower(),
        )
