"""SQLite connection whose context exit commits/rolls back AND closes the handle.

The standard sqlite3.Connection context manager manages a transaction but does not
close the connection. Keeping Windows handles open prevents temporary database
cleanup and can lock files when rebuilding authoring registries.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path


class ClosingConnection(sqlite3.Connection):
    def __exit__(self, exc_type, exc_value, traceback):
        try:
            return super().__exit__(exc_type, exc_value, traceback)
        finally:
            self.close()


def connect(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path, factory=ClosingConnection)
    connection.row_factory = sqlite3.Row
    return connection
