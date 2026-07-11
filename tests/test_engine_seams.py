"""Tests for the canonical|bundled engine seams (homebase.engines + garden/state modules).

Fixture engines are written to tmp_path at test time so these tests do not
depend on this machine's absolute OneDrive layout and stay portable across
CI/hosts. The fixtures mirror the real Gardener/Rinnsal public API contract
(see .AI/.OS/gardener/gardener.py and .AI/.OS/rinnsal/rinnsal/tasks/client.py)
closely enough to validate the seam wiring, not to be a full reimplementation.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from homebase import engines as engine_seams
from homebase.config import HomebaseConfig
from homebase.engines import (
    engine_summary,
    import_from_path,
    resolve_catalog_module_path,
    resolve_engine_path,
)
from homebase.registry import ModuleRegistry


@pytest.fixture(autouse=True)
def _no_real_engine_defaults(monkeypatch):
    """Blank out the built-in default candidate directories for these tests.

    This suite must stay host-independent: on a machine that actually has the
    real .AI/.OS/gardener or rinnsal checkouts (e.g. this ecosystem's own dev
    boxes), the default-candidate fallback would find them for real and mask
    what a "canonical engine missing" scenario is supposed to look like on a
    third-party install.
    """
    monkeypatch.setattr(engine_seams, "_DEFAULT_CANDIDATES", {})


def _write_fixture_gardener(tmp_path: Path) -> Path:
    engine_dir = tmp_path / "engines" / "gardener"
    engine_dir.mkdir(parents=True)
    (engine_dir / "gardener.py").write_text(
        '''
"""Minimal fixture double for the real Gardener engine (everything+FTS5)."""
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


class Gardener:
    def __init__(self, home=None, data_dir=None):
        self.data_dir = Path(data_dir) if data_dir else Path.home() / ".gardener-fixture"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.data_dir / "gardener.db"
        conn = sqlite3.connect(str(self.db_path))
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS everything (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT NOT NULL DEFAULT 'knowledge',
                name TEXT NOT NULL UNIQUE,
                content TEXT DEFAULT '',
                tags TEXT DEFAULT '',
                meta TEXT DEFAULT '{}',
                pinned INTEGER DEFAULT 0,
                created TEXT NOT NULL,
                updated TEXT NOT NULL
            )
            """
        )
        conn.commit()
        conn.close()

    def _now(self):
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

    def _conn(self):
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def find(self, query, type=None, limit=20):
        conn = self._conn()
        rows = conn.execute(
            "SELECT * FROM everything WHERE name LIKE ? OR content LIKE ? LIMIT ?",
            (f"%{query}%", f"%{query}%", limit),
        ).fetchall()
        conn.close()
        return [dict(row) | {"source": "user"} for row in rows]

    def get(self, name):
        conn = self._conn()
        row = conn.execute("SELECT * FROM everything WHERE name = ?", (name,)).fetchone()
        conn.close()
        return dict(row) | {"source": "user"} if row else None

    def put(self, name, content="", type="memory", tags="", meta=None, pinned=False, target="auto"):
        now = self._now()
        conn = self._conn()
        existing = conn.execute("SELECT id FROM everything WHERE name = ?", (name,)).fetchone()
        if existing:
            conn.execute(
                "UPDATE everything SET content=?, type=?, updated=? WHERE name=?",
                (content, type, now, name),
            )
        else:
            conn.execute(
                "INSERT INTO everything (name, content, type, created, updated) VALUES (?,?,?,?,?)",
                (name, content, type, now, now),
            )
        conn.commit()
        conn.close()
        return self.get(name)

    def run(self, name, input=None):
        entry = self.get(name)
        if not entry:
            return False, f"not found: {name}"
        return True, f"ran: {entry['content']}"
''',
        encoding="utf-8",
    )
    return engine_dir


def _write_fixture_rinnsal(tmp_path: Path) -> Path:
    engine_dir = tmp_path / "engines" / "rinnsal"
    package_dir = engine_dir / "rinnsal" / "tasks"
    package_dir.mkdir(parents=True)
    (engine_dir / "rinnsal" / "__init__.py").write_text("", encoding="utf-8")
    (package_dir / "__init__.py").write_text("", encoding="utf-8")
    (package_dir / "client.py").write_text(
        '''
"""Fixture double for rinnsal.tasks.client.TaskClient (rinnsal_tasks schema)."""
import sqlite3
from datetime import datetime

TASK_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS rinnsal_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT DEFAULT '',
    status TEXT NOT NULL DEFAULT 'open',
    priority TEXT NOT NULL DEFAULT 'medium',
    agent_id TEXT NOT NULL DEFAULT 'default',
    tags TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    done_at TEXT
);
"""

VALID_PRIORITIES = ("critical", "high", "medium", "low")


class TaskClient:
    def __init__(self, db_path=None, agent_id="default"):
        self.db_path = db_path
        self.agent_id = agent_id
        conn = sqlite3.connect(str(self.db_path))
        conn.executescript(TASK_SCHEMA_SQL)
        conn.commit()
        conn.close()

    def _conn(self):
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def add(self, title, description="", priority="medium", tags=""):
        now = datetime.now().isoformat()
        conn = self._conn()
        cur = conn.execute(
            "INSERT INTO rinnsal_tasks (title, description, status, priority, agent_id, tags, created_at, updated_at) "
            "VALUES (?, ?, 'open', ?, ?, ?, ?, ?)",
            (title, description, priority, self.agent_id, tags, now, now),
        )
        conn.commit()
        task_id = cur.lastrowid
        conn.close()
        return {"id": task_id, "title": title, "status": "open", "priority": priority, "agent_id": self.agent_id}

    def list(self, status=None, priority=None, include_done=False, limit=50):
        conn = self._conn()
        conditions = []
        params = []
        if status:
            conditions.append("status = ?")
            params.append(status)
        elif not include_done:
            conditions.append("status NOT IN ('done', 'cancelled')")
        where = "WHERE " + " AND ".join(conditions) if conditions else ""
        params.append(limit)
        rows = conn.execute(
            f"SELECT id, title, description, status, priority, agent_id, tags, created_at, updated_at, done_at "
            f"FROM rinnsal_tasks {where} ORDER BY id ASC LIMIT ?",
            params,
        ).fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def update(self, task_id, title=None, description=None, priority=None, tags=None):
        fields = []
        params = []
        if description is not None:
            fields.append("description = ?")
            params.append(description)
        if priority is not None:
            fields.append("priority = ?")
            params.append(priority)
        if not fields:
            return False
        params.append(task_id)
        conn = self._conn()
        cur = conn.execute(f"UPDATE rinnsal_tasks SET {', '.join(fields)} WHERE id = ?", params)
        conn.commit()
        changed = cur.rowcount > 0
        conn.close()
        return changed

    def _set_status(self, task_id, status):
        conn = self._conn()
        done_at = datetime.now().isoformat() if status == "done" else None
        cur = conn.execute(
            "UPDATE rinnsal_tasks SET status = ?, done_at = ? WHERE id = ?", (status, done_at, task_id)
        )
        conn.commit()
        changed = cur.rowcount > 0
        conn.close()
        return changed

    def activate(self, task_id):
        return self._set_status(task_id, "active")

    def done(self, task_id):
        return self._set_status(task_id, "done")

    def reopen(self, task_id):
        return self._set_status(task_id, "open")
''',
        encoding="utf-8",
    )
    return engine_dir


def test_resolve_engine_path_prefers_env_override(tmp_path, monkeypatch):
    real = tmp_path / "real-garden"
    real.mkdir()
    decoy = tmp_path / "decoy-garden"
    decoy.mkdir()
    monkeypatch.setenv("HOMEBASE_ENGINE_GARDEN_PATH", str(real))

    resolved = resolve_engine_path("garden", str(decoy))

    assert resolved == real


def test_resolve_engine_path_uses_configured_path_when_no_env(tmp_path, monkeypatch):
    monkeypatch.delenv("HOMEBASE_ENGINE_GARDEN_PATH", raising=False)
    configured = tmp_path / "configured-garden"
    configured.mkdir()

    resolved = resolve_engine_path("garden", str(configured))

    assert resolved == configured


def test_resolve_engine_path_uses_v2_module_catalog_before_legacy_defaults(tmp_path, monkeypatch):
    monkeypatch.delenv("HOMEBASE_ENGINE_GARDEN_PATH", raising=False)
    module_dir = tmp_path / ".MODULES" / ".MEMORY" / "GARDENER"
    module_dir.mkdir(parents=True)
    catalog_path = tmp_path / ".MODULES" / "modules.catalog.json"
    catalog_path.write_text(
        json.dumps({
            "schema": "ellmos.modules-catalog.v1",
            "modules": [{"id": "GARDENER", "resolved_source": ".MEMORY/GARDENER"}],
        }),
        encoding="utf-8",
    )
    monkeypatch.setenv("ELLMOS_MODULES_CATALOG", str(catalog_path))

    assert resolve_catalog_module_path("GARDENER") == module_dir
    assert resolve_engine_path("garden", None) == module_dir


def test_configured_engine_path_wins_over_catalog(tmp_path, monkeypatch):
    monkeypatch.delenv("HOMEBASE_ENGINE_GARDEN_PATH", raising=False)
    configured = tmp_path / "configured"
    configured.mkdir()
    catalog_module = tmp_path / ".MODULES" / "GARDENER"
    catalog_module.mkdir(parents=True)
    catalog_path = tmp_path / ".MODULES" / "modules.catalog.json"
    catalog_path.write_text(
        json.dumps({
            "schema": "ellmos.modules-catalog.v1",
            "modules": [{"id": "GARDENER", "resolved_source": "GARDENER"}],
        }),
        encoding="utf-8",
    )
    monkeypatch.setenv("ELLMOS_MODULES_CATALOG", str(catalog_path))

    assert resolve_engine_path("garden", str(configured)) == configured


def test_resolve_engine_path_returns_none_when_nothing_exists(monkeypatch):
    monkeypatch.delenv("HOMEBASE_ENGINE_GARDEN_PATH", raising=False)
    monkeypatch.setattr(engine_seams, "_module_catalog_candidates", lambda: [])
    monkeypatch.setitem(engine_seams._DEFAULT_CANDIDATES, "garden", [])

    resolved = resolve_engine_path("garden", "/definitely/does/not/exist-xyz")

    assert resolved is None


def test_import_from_path_returns_none_for_missing_module(tmp_path):
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()

    assert import_from_path("no_such_module_xyz", empty_dir) is None


def test_engine_summary_flags_unimplemented_seams_as_bundled_only():
    config = HomebaseConfig(engine_mode="canonical")

    summary = engine_summary(config)

    assert "garden=canonical" in summary
    assert "state=canonical" in summary
    assert "mem=bundled-only (canonical requested, no seam implemented yet)" in summary
    assert "kb=bundled-only (canonical requested, no seam implemented yet)" in summary
    assert "route=bundled-only (canonical requested, no seam implemented yet)" in summary


def test_engine_summary_reports_bundled_when_not_requested():
    config = HomebaseConfig()

    summary = engine_summary(config)

    assert summary == ["garden=bundled", "state=bundled", "mem=bundled", "kb=bundled", "route=bundled"]


@pytest.mark.asyncio
async def test_garden_canonical_seam_roundtrip(tmp_path, monkeypatch):
    monkeypatch.delenv("HOMEBASE_ENGINE_GARDEN_PATH", raising=False)
    engine_dir = _write_fixture_gardener(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))  # keep the fixture's own db out of the real user profile

    config = HomebaseConfig(
        enabled_modules=["garden"],
        engine_mode="canonical",
        engine_configs={"garden": {"path": str(engine_dir)}},
    )
    registry = ModuleRegistry(config)
    loaded, skipped = registry.discover_and_load()
    assert loaded == ["garden"]
    assert skipped == []

    stored = await registry.call_tool("hb_garden_put", {"key": "seam-note", "value": "hits the real engine"})
    found = await registry.call_tool("hb_garden_find", {"query": "real engine"})
    fetched = await registry.call_tool("hb_garden_get", {"key": "seam-note"})

    assert stored["engine"] == "canonical"
    assert found["engine"] == "canonical"
    assert found["count"] == 1
    assert fetched["entry"]["value"] == "hits the real engine"


@pytest.mark.asyncio
async def test_garden_falls_back_to_bundled_when_canonical_engine_missing(tmp_path, monkeypatch):
    monkeypatch.delenv("HOMEBASE_ENGINE_GARDEN_PATH", raising=False)
    monkeypatch.setattr(engine_seams, "_module_catalog_candidates", lambda: [])
    monkeypatch.setitem(engine_seams._DEFAULT_CANDIDATES, "garden", [])
    config = HomebaseConfig(
        enabled_modules=["garden"],
        engine_mode="canonical",
        engine_configs={"garden": {"path": str(tmp_path / "nowhere")}},
        module_configs={"garden": {"db_path": str(tmp_path / "garden.db")}},
    )
    registry = ModuleRegistry(config)
    registry.discover_and_load()

    stored = await registry.call_tool("hb_garden_put", {"key": "k", "value": "v"})

    assert stored["engine"] == "bundled"


@pytest.mark.asyncio
async def test_state_task_canonical_seam_roundtrip_and_status_mapping(tmp_path):
    engine_dir = _write_fixture_rinnsal(tmp_path)
    config = HomebaseConfig(
        enabled_modules=["state"],
        engine_mode="canonical",
        engine_configs={"state": {"path": str(engine_dir)}},
        module_configs={"state": {"task_db_path": str(tmp_path / "scanner_tasks.db")}},
    )
    registry = ModuleRegistry(config)
    loaded, skipped = registry.discover_and_load()
    assert loaded == ["state"]
    assert skipped == []

    created = await registry.call_tool("hb_state_task_create", {"title": "Seam roundtrip", "priority": "high"})
    assert created["engine"] == "canonical"

    in_progress = await registry.call_tool(
        "hb_state_task_update", {"task_id": created["task_id"], "status": "in_progress"}
    )
    assert in_progress["status"] == "updated"

    listed = await registry.call_tool("hb_state_task_list", {"status": "in_progress"})
    assert listed["engine"] == "canonical"
    assert listed["count"] == 1
    assert listed["tasks"][0]["status"] == "in_progress"  # translated back from rinnsal's "active"

    done = await registry.call_tool("hb_state_task_update", {"task_id": created["task_id"], "status": "done"})
    assert done["status"] == "updated"
    done_list = await registry.call_tool("hb_state_task_list", {"status": "done"})
    assert done_list["count"] == 1


@pytest.mark.asyncio
async def test_state_falls_back_to_bundled_when_canonical_engine_missing(tmp_path):
    config = HomebaseConfig(
        enabled_modules=["state"],
        engine_mode="canonical",
        engine_configs={"state": {"path": str(tmp_path / "nowhere")}},
        module_configs={"state": {"db_path": str(tmp_path / "rinnsal.db")}},
    )
    registry = ModuleRegistry(config)
    registry.discover_and_load()

    created = await registry.call_tool("hb_state_task_create", {"title": "Bundled fallback"})

    assert created["engine"] == "bundled"
