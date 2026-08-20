"""Unit and migration smoke tests for every Homebase module.

These tests deliberately construct modules with temporary stores.  They cover
the common factory/tool contract for all modules and exercise reopening every
persistent module against an existing (alpha-era) SQLite schema.
"""

from __future__ import annotations

import importlib
import sqlite3
from pathlib import Path

import pytest

from homebase.modules import ModuleBase
from homebase.registry import MODULE_MAP
from homebase.storage import connect_db

_PREFIXES = {
    "mem": "mem",
    "route": "route",
    "kb": "kb",
    "swarm": "swarm",
    "state": "state",
    "garden": "garden",
    "api": "api",
    "test": "test",
    "auto": "auto",
    "conn": "conn",
    "plug": "plug",
}


def _module_config(tmp_path: Path, name: str) -> dict[str, object]:
    config: dict[str, object] = {"db_path": str(tmp_path / f"{name}.db")}
    if name == "api":
        config["timeout"] = 0.1
    if name == "conn":
        config["connectors"] = []
    if name == "auto":
        config["chains_dir"] = str(tmp_path / "chains")
    if name == "plug":
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir(exist_ok=True)
        config["plugins_dir"] = str(plugins_dir)
    return config


def _factory(name: str):
    module = importlib.import_module(MODULE_MAP[name])
    return getattr(module, "create_module")


@pytest.mark.parametrize("name", MODULE_MAP, ids=MODULE_MAP.keys())
def test_every_module_factory_exposes_valid_tool_contract(name: str, tmp_path: Path):
    instance = _factory(name)(_module_config(tmp_path, name))

    assert isinstance(instance, ModuleBase)
    dependencies_ok, missing = instance.check_dependencies()
    assert dependencies_ok, f"{name} missing dependencies: {missing}"

    tools = instance.get_tools()
    assert tools, f"{name} must expose at least one MCP tool"
    tool_names = [tool.name for tool in tools]
    assert len(tool_names) == len(set(tool_names)), f"duplicate tools in {name}"

    prefix = f"hb_{_PREFIXES[name]}_"
    for tool in tools:
        assert tool.name.startswith(prefix), tool.name
        assert callable(tool.handler), tool.name
        assert tool.input_schema.get("type") == "object", tool.name


@pytest.mark.parametrize("name", MODULE_MAP, ids=MODULE_MAP.keys())
def test_every_module_can_be_reopened_without_changing_tool_surface(name: str, tmp_path: Path):
    """Migration smoke: a second startup must be safe for every module."""
    config = _module_config(tmp_path, name)
    first = _factory(name)(config)
    second = _factory(name)(config)

    first_tools = [(tool.name, tool.input_schema) for tool in first.get_tools()]
    second_tools = [(tool.name, tool.input_schema) for tool in second.get_tools()]
    assert second_tools == first_tools


def _create_legacy_schema(kind: str, db_path: Path) -> None:
    """Create representative pre-agent-id schemas and current alpha schemas."""
    with sqlite3.connect(db_path) as connection:
        if kind == "memory":
            connection.execute(
                """
                CREATE TABLE memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content TEXT NOT NULL,
                    category TEXT NOT NULL,
                    confidence REAL NOT NULL DEFAULT 1.0,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "INSERT INTO memories (content, category, confidence, created_at) VALUES (?, ?, ?, ?)",
                ("legacy memory", "fact", 0.8, "2026-01-01T00:00:00+00:00"),
            )
        elif kind == "knowledge":
            connection.execute(
                """
                CREATE TABLE knowledge_entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content TEXT NOT NULL,
                    source TEXT,
                    tags TEXT NOT NULL DEFAULT '[]',
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "INSERT INTO knowledge_entries (content, source, tags, created_at) VALUES (?, ?, ?, ?)",
                ("legacy knowledge", "audit", '["legacy"]', "2026-01-01T00:00:00+00:00"),
            )
        elif kind == "state":
            connection.execute(
                """
                CREATE TABLE state_memory (
                    key TEXT NOT NULL,
                    value TEXT NOT NULL,
                    type TEXT NOT NULL DEFAULT 'fact',
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "INSERT INTO state_memory (key, value, type, updated_at) VALUES (?, ?, ?, ?)",
                ("legacy-key", "legacy-value", "fact", "2026-01-01T00:00:00+00:00"),
            )
            connection.execute(
                """
                CREATE TABLE tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    description TEXT,
                    priority TEXT NOT NULL DEFAULT 'medium',
                    status TEXT NOT NULL DEFAULT 'open',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                INSERT INTO tasks (title, description, priority, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                ("legacy task", "keep me", "low", "open", "2026-01-01T00:00:00+00:00", "2026-01-01T00:00:00+00:00"),
            )
        elif kind == "garden":
            connection.execute(
                "CREATE TABLE garden_entries (key TEXT PRIMARY KEY, value TEXT NOT NULL, updated_at TEXT NOT NULL)"
            )
            connection.execute(
                "INSERT INTO garden_entries (key, value, updated_at) VALUES (?, ?, ?)",
                ("legacy", "garden value", "2026-01-01T00:00:00+00:00"),
            )
        elif kind == "api":
            connection.execute(
                """
                CREATE TABLE api_probes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT NOT NULL,
                    strategies TEXT NOT NULL,
                    result_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "INSERT INTO api_probes (url, strategies, result_json, created_at) VALUES (?, ?, ?, ?)",
                ("http://legacy", "[]", "{}", "2026-01-01T00:00:00+00:00"),
            )
        elif kind == "automation":
            connection.executescript(
                """
                CREATE TABLE automation_chains (
                    name TEXT PRIMARY KEY,
                    description TEXT,
                    steps_json TEXT NOT NULL,
                    source TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE automation_runs (
                    run_id TEXT PRIMARY KEY,
                    chain TEXT NOT NULL,
                    input TEXT,
                    status TEXT NOT NULL,
                    result_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                """
            )
            connection.execute(
                "INSERT INTO automation_chains VALUES (?, ?, ?, ?, ?)",
                ("legacy-chain", "legacy", "[]", "legacy", "2026-01-01T00:00:00+00:00"),
            )
        elif kind == "connectors":
            connection.executescript(
                """
                CREATE TABLE connectors (
                    name TEXT PRIMARY KEY,
                    kind TEXT NOT NULL,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    config_status TEXT NOT NULL,
                    target_hint TEXT,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE connector_outbox (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    connector TEXT NOT NULL,
                    target TEXT,
                    message TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE connector_inbox (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    connector TEXT NOT NULL,
                    source TEXT,
                    message TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )
            connection.execute(
                "INSERT INTO connectors VALUES (?, ?, ?, ?, ?, ?)",
                ("legacy", "local", 1, "unknown", None, "2026-01-01T00:00:00+00:00"),
            )
        elif kind == "plugins":
            connection.executescript(
                """
                CREATE TABLE plugins (
                    name TEXT PRIMARY KEY,
                    path TEXT,
                    kind TEXT NOT NULL,
                    description TEXT,
                    metadata_json TEXT NOT NULL,
                    discovered_at TEXT NOT NULL
                );
                CREATE TABLE plugin_runs (
                    run_id TEXT PRIMARY KEY,
                    plugin TEXT NOT NULL,
                    args_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    result_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )
            connection.execute(
                "INSERT INTO plugins VALUES (?, ?, ?, ?, ?, ?)",
                ("legacy", None, "configured", "legacy plugin", "{}", "2026-01-01T00:00:00+00:00"),
            )
        else:  # pragma: no cover - protects the parametrization from typos
            raise AssertionError(f"unknown legacy schema: {kind}")


@pytest.mark.parametrize(
    "kind, expected_table, expected_value",
    [
        ("memory", "memories", "legacy memory"),
        ("knowledge", "knowledge_entries", "legacy knowledge"),
        ("state", "state_memory", "legacy-value"),
        ("garden", "garden_entries", "garden value"),
        ("api", "api_probes", "http://legacy"),
        ("automation", "automation_chains", "legacy-chain"),
        ("connectors", "connectors", "legacy"),
        ("plugins", "plugins", "legacy"),
    ],
    ids=lambda value: value,
)
def test_persistent_module_migration_smoke_preserves_legacy_rows(
    kind: str, expected_table: str, expected_value: str, tmp_path: Path
):
    db_path = tmp_path / f"legacy-{kind}.db"
    _create_legacy_schema(kind, db_path)
    module_name = {
        "memory": "mem",
        "knowledge": "kb",
        "automation": "auto",
        "connectors": "conn",
        "plugins": "plug",
    }.get(kind, kind)

    _factory(module_name)(_module_config(tmp_path, module_name) | {"db_path": str(db_path)})

    with connect_db(str(db_path)) as connection:
        assert connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (expected_table,)
        ).fetchone()
        if kind == "memory":
            row = connection.execute("SELECT content, agent_id FROM memories").fetchone()
            assert tuple(row) == (expected_value, "unknown")
        elif kind == "knowledge":
            row = connection.execute("SELECT content, agent_id FROM knowledge_entries").fetchone()
            assert tuple(row) == (expected_value, "unknown")
        elif kind == "state":
            row = connection.execute("SELECT value, agent_id FROM state_memory").fetchone()
            assert tuple(row) == (expected_value, "unknown")
            task = connection.execute("SELECT title, agent_id FROM tasks").fetchone()
            assert tuple(task) == ("legacy task", "unknown")
        elif kind == "garden":
            assert connection.execute("SELECT value FROM garden_entries WHERE key = 'legacy'").fetchone()[0] == expected_value
        elif kind == "api":
            assert connection.execute("SELECT url FROM api_probes").fetchone()[0] == expected_value
        elif kind == "automation":
            assert connection.execute("SELECT name FROM automation_chains WHERE name = ?", (expected_value,)).fetchone()
        elif kind == "connectors":
            assert connection.execute("SELECT name FROM connectors WHERE name = ?", (expected_value,)).fetchone()
        elif kind == "plugins":
            assert connection.execute("SELECT name FROM plugins WHERE name = ?", (expected_value,)).fetchone()
