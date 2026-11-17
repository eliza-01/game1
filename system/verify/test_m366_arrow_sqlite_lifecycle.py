"""M366: ArrowStore uses the shared SQLite lifecycle with guaranteed close."""
from __future__ import annotations

import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "system/control-center"))
from arrow_store import ArrowStore


class ArrowSqliteLifecycleM366(unittest.TestCase):
    def test_transaction_commit_rollback_and_immediate_close(self):
        with tempfile.TemporaryDirectory(prefix="m366-arrow-db-") as directory:
            store = ArrowStore(Path(directory))
            with store.connect() as committed:
                committed.execute(
                    "INSERT INTO arrow_settings(key,value) VALUES(?,?)",
                    ("m366_committed", "yes"),
                )
            with self.assertRaises(sqlite3.ProgrammingError):
                committed.execute("SELECT 1")

            with self.assertRaisesRegex(RuntimeError, "intentional rollback"):
                with store.connect() as rolled_back:
                    rolled_back.execute(
                        "INSERT INTO arrow_settings(key,value) VALUES(?,?)",
                        ("m366_rolled_back", "no"),
                    )
                    raise RuntimeError("intentional rollback")
            with self.assertRaises(sqlite3.ProgrammingError):
                rolled_back.execute("SELECT 1")

            with store.connect() as checked:
                self.assertEqual(
                    checked.execute("SELECT value FROM arrow_settings WHERE key=?", ("m366_committed",)).fetchone()[0],
                    "yes",
                )
                self.assertIsNone(
                    checked.execute("SELECT value FROM arrow_settings WHERE key=?", ("m366_rolled_back",)).fetchone(),
                )
            with self.assertRaises(sqlite3.ProgrammingError):
                checked.execute("SELECT 1")
            # TemporaryDirectory deletion also detects locked game1.db on Windows.

    def test_store_actions_leave_no_live_database_handles(self):
        with tempfile.TemporaryDirectory(prefix="m366-arrow-operations-") as directory:
            root = Path(directory)
            fb = root / "arrow.fbx"
            fb.write_bytes(b"; FBX 7.4.0 mock -- no publication")
            store = ArrowStore(root)
            self.assertEqual(store.list(), [])
            entry = store.register({
                "slug": "m366_arrow",
                "name": "M366 arrow",
                "speed": 145,
                "modelSourcePath": str(fb),
            })
            self.assertEqual(entry["status"], "LOCAL_ONLY")
            self.assertIsNotNone(store.get("m366_arrow"))
            with self.assertRaisesRegex(ValueError, "publish"):
                store.activate("m366_arrow")
            with store.connect() as connection:
                connection.execute(
                    "UPDATE arrow_assets SET model_asset_id=?, published_sha256=? WHERE slug=?",
                    ("123456789", entry["sha256"], "m366_arrow"),
                )
            store.activate("m366_arrow")
            self.assertEqual(store.snapshot()["activeArrowSlug"], "m366_arrow")
            # An exclusive SQLite lock must be acquirable after all methods return.
            external = sqlite3.connect(store.db, timeout=0)
            try:
                external.execute("BEGIN EXCLUSIVE")
                external.execute("ROLLBACK")
            finally:
                external.close()


if __name__ == "__main__":
    unittest.main()
