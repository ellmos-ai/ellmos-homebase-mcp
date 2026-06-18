"""Small SQLite helpers for Homebase modules."""

from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path
import sqlite3
from typing import Any


def connect_db(db_path: str) -> sqlite3.Connection:
    path = Path(db_path).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=30.0)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA busy_timeout=30000")
    connection.execute("PRAGMA foreign_keys=ON")
    return connection


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def contains_term(query: str) -> str:
    return f"%{query}%"


def resolve_agent_id(config: dict[str, Any], explicit: Any = None) -> str:
    """Resolve the writing agent for shared-memory provenance."""
    if explicit not in (None, ""):
        return str(explicit)
    env_agent = os.environ.get("HOMEBASE_AGENT_ID") or os.environ.get("AGENT_ID")
    if env_agent:
        return env_agent
    return str(config.get("agent_id") or config.get("default_agent_id") or "unknown")


def ensure_column(connection: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    """Add a column to an existing SQLite table when older alpha DBs lack it."""
    existing = {row["name"] for row in connection.execute(f"PRAGMA table_info({table})")}
    if column not in existing:
        connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
