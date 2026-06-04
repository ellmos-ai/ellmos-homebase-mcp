"""Small SQLite helpers for Homebase modules."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sqlite3


def connect_db(db_path: str) -> sqlite3.Connection:
    path = Path(db_path).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    return connection


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def contains_term(query: str) -> str:
    return f"%{query}%"
