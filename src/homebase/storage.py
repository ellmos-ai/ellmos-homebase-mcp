"""Small SQLite helpers for Homebase modules."""

from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path
import re
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


def setup_fts(connection: sqlite3.Connection, table: str, fts: str, columns: list[str]) -> bool:
    """Create an external-content FTS5 index over ``table`` and keep it in sync.

    Returns True when FTS5 is available (index + sync triggers created and the
    existing rows back-filled), False when the SQLite build lacks FTS5 (callers
    then fall back to LIKE). Idempotent: safe to call on every startup. The
    table's primary key MUST be the integer column ``id``.
    """
    col_list = ", ".join(columns)
    new_vals = ", ".join(f"new.{c}" for c in columns)
    old_vals = ", ".join(f"old.{c}" for c in columns)
    try:
        connection.execute(
            f"CREATE VIRTUAL TABLE IF NOT EXISTS {fts} "
            f"USING fts5({col_list}, content='{table}', content_rowid='id')"
        )
    except sqlite3.OperationalError:
        return False  # FTS5 not compiled into this SQLite build

    connection.execute(
        f"CREATE TRIGGER IF NOT EXISTS {table}_fts_ai AFTER INSERT ON {table} BEGIN "
        f"INSERT INTO {fts}(rowid, {col_list}) VALUES (new.id, {new_vals}); END"
    )
    connection.execute(
        f"CREATE TRIGGER IF NOT EXISTS {table}_fts_ad AFTER DELETE ON {table} BEGIN "
        f"INSERT INTO {fts}({fts}, rowid, {col_list}) VALUES('delete', old.id, {old_vals}); END"
    )
    connection.execute(
        f"CREATE TRIGGER IF NOT EXISTS {table}_fts_au AFTER UPDATE ON {table} BEGIN "
        f"INSERT INTO {fts}({fts}, rowid, {col_list}) VALUES('delete', old.id, {old_vals}); "
        f"INSERT INTO {fts}(rowid, {col_list}) VALUES (new.id, {new_vals}); END"
    )

    fts_rows = connection.execute(f"SELECT count(*) AS c FROM {fts}").fetchone()["c"]
    base_rows = connection.execute(f"SELECT count(*) AS c FROM {table}").fetchone()["c"]
    if fts_rows == 0 and base_rows > 0:
        connection.execute(f"INSERT INTO {fts}({fts}) VALUES('rebuild')")
    return True


def fts_match_query(text: str) -> str:
    """Build a safe FTS5 MATCH expression from free text.

    Tokenizes to alphanumerics (keeping German umlauts), lowercases, and joins
    the terms as prefix matches with implicit AND (FTS5 default), e.g.
    ``"doppelter fakt" -> "doppelter* fakt*"``. Returns "" when no usable token
    remains (callers then fall back to LIKE)."""
    tokens = re.findall(r"[0-9a-zA-ZÀ-ɏ]+", text.lower())
    return " ".join(f"{token}*" for token in tokens)
