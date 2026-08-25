"""Tests for the canonical|bundled engine seams (homebase.engines + garden/state modules).

Fixture engines are written to tmp_path at test time so these tests do not
depend on this machine's absolute OneDrive layout and stay portable across
CI/hosts. The fixtures mirror the real Gardener/Rinnsal public API contract
(see .AI/.OS/gardener/gardener.py and .AI/.OS/rinnsal/rinnsal/tasks/client.py)
closely enough to validate the seam wiring, not to be a full reimplementation.
"""

from __future__ import annotations

import json
import sqlite3
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
    assert "mem=canonical" in summary  # USMC seam implemented
    assert "kb=bundled-only (canonical requested, no seam implemented yet)" in summary
    assert "route=bundled-only (canonical requested, no seam implemented yet)" in summary


def test_engine_summary_reports_bundled_when_not_requested():
    config = HomebaseConfig()

    summary = engine_summary(config)

    assert summary == [
        "garden=bundled", "state=bundled", "mem=bundled", "kb=bundled", "route=bundled",
        "policy=canonical-only (no bundled alternative for this namespace)",
        "ticket=canonical-only (no bundled alternative for this namespace)",
        "lock=canonical-only (no bundled alternative for this namespace)",
    ]


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
async def test_garden_fails_closed_when_canonical_engine_missing(tmp_path, monkeypatch):
    """canonical requested + Gardener unreachable => tool error, never a silent bundled write.

    Inverts the pre-0.1.0a21 contract, which returned engine="bundled" here and
    wrote into a second, disconnected garden.db. See MODE-CONTRACT.md.
    """
    monkeypatch.delenv("HOMEBASE_ENGINE_GARDEN_PATH", raising=False)
    monkeypatch.setattr(engine_seams, "_module_catalog_candidates", lambda: [])
    monkeypatch.setitem(engine_seams._DEFAULT_CANDIDATES, "garden", [])
    bundled_db = tmp_path / "garden.db"
    config = HomebaseConfig(
        enabled_modules=["garden"],
        engine_mode="canonical",
        engine_configs={"garden": {"path": str(tmp_path / "nowhere")}},
        module_configs={"garden": {"db_path": str(bundled_db)}},
    )
    registry = ModuleRegistry(config)
    loaded, skipped = registry.discover_and_load()

    # The server still starts and still offers the tools -- only calling fails.
    assert loaded == ["garden"]
    assert skipped == []
    assert "hb_garden_put" in {tool.name for tool in registry.list_tools()}

    with pytest.raises(engine_seams.CanonicalEngineUnavailable) as excinfo:
        await registry.call_tool("hb_garden_put", {"key": "k", "value": "v"})

    message = str(excinfo.value)
    assert "canonical" in message
    assert "nowhere" in message  # names the unreachable target
    assert 'mode = "bundled"' in message  # names the way out
    assert not bundled_db.exists(), "no shadow bundled store may be created"

    # Reads fail closed too, so a caller cannot mistake an empty bundled store
    # for "the canonical engine has nothing".
    with pytest.raises(engine_seams.CanonicalEngineUnavailable):
        await registry.call_tool("hb_garden_find", {"query": "k"})


def _write_fixture_usmc(tmp_path: Path) -> Path:
    """Write a minimal USMC checkout (facts store) mirroring the real public API.

    Structure mirrors the real .MODULES/.MEMORY/USMC/usmc package so the seam's
    ``import_from_path("usmc", <root>)`` resolves it. SQLite-backed so it persists
    across the per-call USMC clients memory.py constructs.
    """
    engine_dir = tmp_path / "engines" / "usmc-checkout"
    pkg = engine_dir / "usmc"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text(
        "from .client import USMCClient\n__all__ = ['USMCClient']\n", encoding="utf-8"
    )
    (pkg / "client.py").write_text(
        '''
"""Minimal fixture double for the real USMC facts store."""
import sqlite3
from datetime import datetime
from pathlib import Path


class USMCClient:
    VALID_CATEGORIES = ("user", "project", "system", "domain")

    def __init__(self, db_path=None, agent_id="default"):
        self.db_path = Path(db_path) if db_path else Path.home() / ".usmc-fixture" / "usmc.db"
        self.agent_id = agent_id
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path))
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS usmc_facts (
                agent_id TEXT, category TEXT, key TEXT, value TEXT,
                confidence REAL, source TEXT, created_at TEXT, updated_at TEXT,
                PRIMARY KEY (agent_id, category, key)
            )
            """
        )
        conn.commit()
        conn.close()

    def add_fact(self, category, key, value, confidence=1.0):
        if category not in self.VALID_CATEGORIES:
            raise ValueError("bad category")
        now = datetime.now().isoformat()
        conn = sqlite3.connect(str(self.db_path))
        conn.execute(
            """
            INSERT INTO usmc_facts
                (agent_id, category, key, value, confidence, source, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(agent_id, category, key) DO UPDATE SET
                value = excluded.value, confidence = excluded.confidence,
                updated_at = excluded.updated_at
            """,
            (self.agent_id, category, key, value, confidence, "fixture", now, now),
        )
        conn.commit()
        conn.close()
        return {"category": category, "key": key, "value": value, "confidence": confidence, "merged": True}

    def get_facts(self, category=None, min_confidence=0.0, agent_id=None):
        conn = sqlite3.connect(str(self.db_path))
        conditions = ["confidence >= ?"]
        params = [min_confidence]
        if category:
            conditions.append("category = ?")
            params.append(category)
        if agent_id:
            conditions.append("agent_id = ?")
            params.append(agent_id)
        where = " AND ".join(conditions)
        rows = conn.execute(
            "SELECT category, key, value, confidence, source, agent_id, updated_at "
            "FROM usmc_facts WHERE " + where + " ORDER BY confidence DESC, key",
            params,
        ).fetchall()
        conn.close()
        return [
            {"category": r[0], "key": r[1], "value": r[2], "confidence": r[3],
             "source": r[4], "agent_id": r[5], "updated_at": r[6]}
            for r in rows
        ]
''',
        encoding="utf-8",
    )
    return engine_dir


@pytest.mark.asyncio
async def test_mem_usmc_canonical_seam_roundtrip(tmp_path, monkeypatch):
    monkeypatch.delenv("HOMEBASE_ENGINE_MEM_PATH", raising=False)
    engine_dir = _write_fixture_usmc(tmp_path)

    config = HomebaseConfig(
        enabled_modules=["mem"],
        engine_mode="canonical",
        engine_configs={"mem": {"path": str(engine_dir)}},
        module_configs={"mem": {"usmc_db": str(tmp_path / "usmc_test.db")}},
    )
    registry = ModuleRegistry(config)
    loaded, skipped = registry.discover_and_load()
    assert loaded == ["mem"]
    assert skipped == []

    stored = await registry.call_tool(
        "hb_mem_store",
        {"content": "USMC seam works", "category": "fact", "confidence": 0.9, "agent_id": "opus"},
    )
    assert stored["engine"] == "canonical"
    await registry.call_tool(
        "hb_mem_store", {"content": "unrelated lesson entry", "category": "lesson", "agent_id": "opus"}
    )

    found = await registry.call_tool("hb_mem_query", {"query": "seam", "category": "all"})
    assert found["engine"] == "canonical"
    assert found["mode"] == "client_filter"
    assert found["count"] == 1
    assert found["results"][0]["content"] == "USMC seam works"
    assert found["results"][0]["category"] == "fact"
    assert found["results"][0]["agent_id"] == "opus"

    lessons = await registry.call_tool("hb_mem_query", {"query": "", "category": "lesson"})
    assert {row["category"] for row in lessons["results"]} == {"lesson"}

    context = await registry.call_tool("hb_mem_context", {"focus": "USMC"})
    assert context["engine"] == "canonical"
    assert "USMC seam works" in context["context"]

    merge = await registry.call_tool("hb_mem_merge", {"dry_run": True})
    assert merge["status"] == "not_supported"
    assert merge["engine"] == "canonical"


@pytest.mark.asyncio
async def test_mem_fails_closed_when_usmc_missing(tmp_path, monkeypatch):
    """canonical requested + USMC unreachable => tool error for the whole hb_mem_* family.

    The bulk-hygiene ops are gated too: running merge/consolidate against the
    bundled store here would delete rows in the wrong database.
    """
    monkeypatch.delenv("HOMEBASE_ENGINE_MEM_PATH", raising=False)
    monkeypatch.setattr(engine_seams, "_module_catalog_candidates", lambda: [])
    monkeypatch.setitem(engine_seams._DEFAULT_CANDIDATES, "mem", [])
    bundled_db = tmp_path / "memory.db"
    config = HomebaseConfig(
        enabled_modules=["mem"],
        engine_mode="canonical",
        engine_configs={"mem": {"path": str(tmp_path / "nowhere")}},
        module_configs={"mem": {"db_path": str(bundled_db)}},
    )
    registry = ModuleRegistry(config)
    registry.discover_and_load()

    with pytest.raises(engine_seams.CanonicalEngineUnavailable) as excinfo:
        await registry.call_tool("hb_mem_store", {"content": "x", "category": "fact"})
    assert "USMC" in str(excinfo.value)

    for tool, args in (
        ("hb_mem_query", {"query": "x"}),
        ("hb_mem_context", {}),
        ("hb_mem_merge", {"dry_run": True}),
        ("hb_mem_consolidate", {"dry_run": True}),
    ):
        with pytest.raises(engine_seams.CanonicalEngineUnavailable):
            await registry.call_tool(tool, args)

    assert not bundled_db.exists(), "no shadow bundled store may be created"


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


def _fake_home(tmp_path: Path, monkeypatch) -> Path:
    """Point ``Path.home()`` at tmp_path on both POSIX and Windows.

    ``ntpath.expanduser`` reads USERPROFILE and ignores HOME, so setting only
    HOME would silently let these tests resolve against the real user profile.
    """
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    return home


def _state_config(engine_dir: Path, tmp_path: Path, **state_overrides) -> HomebaseConfig:
    return HomebaseConfig(
        enabled_modules=["state"],
        engine_mode="canonical",
        engine_configs={"state": {"path": str(engine_dir)}},
        module_configs={"state": {"db_path": str(tmp_path / "rinnsal.db"), **state_overrides}},
    )


@pytest.mark.asyncio
async def test_state_task_canonical_default_targets_taskplan_db(tmp_path, monkeypatch):
    """The unconfigured canonical default is taskplan's store, not the retired rinnsal queue.

    Regression guard for T-20260814-01: the default pointed at
    ``~/.rinnsal/scanner_tasks.db`` after that directory had been removed, so
    every hb_state_task_* call failed with "unable to open database file".
    """
    monkeypatch.delenv("TASKPLAN_DB", raising=False)
    monkeypatch.delenv("SCANNER_TASKS_DB", raising=False)
    engine_dir = _write_fixture_rinnsal(tmp_path)
    home = _fake_home(tmp_path, monkeypatch)
    (home / ".taskplan").mkdir()

    registry = ModuleRegistry(_state_config(engine_dir, tmp_path))
    registry.discover_and_load()

    created = await registry.call_tool("hb_state_task_create", {"title": "Default path"})
    assert created["engine"] == "canonical"
    listed = await registry.call_tool("hb_state_task_list", {"status": "all"})
    assert listed["count"] == 1

    assert (home / ".taskplan" / "taskplan.db").exists()
    assert not (home / ".rinnsal").exists(), "the retired rinnsal queue must not be recreated"


@pytest.mark.asyncio
async def test_taskplan_db_env_outranks_legacy_scanner_tasks_db(tmp_path, monkeypatch):
    """TASKPLAN_DB wins over SCANNER_TASKS_DB: the canonical engine's own env must not be overruled.

    Otherwise relocating the task DB with TASKPLAN_DB would leave homebase
    writing into a store no other taskplan consumer reads -- the disconnected
    second store MODE-CONTRACT.md forbids.
    """
    engine_dir = _write_fixture_rinnsal(tmp_path)
    _fake_home(tmp_path, monkeypatch)
    canonical_db = tmp_path / "canonical" / "taskplan.db"
    legacy_db = tmp_path / "legacy" / "scanner_tasks.db"
    canonical_db.parent.mkdir()
    legacy_db.parent.mkdir()
    monkeypatch.setenv("TASKPLAN_DB", str(canonical_db))
    monkeypatch.setenv("SCANNER_TASKS_DB", str(legacy_db))

    registry = ModuleRegistry(_state_config(engine_dir, tmp_path))
    registry.discover_and_load()
    await registry.call_tool("hb_state_task_create", {"title": "Follows TASKPLAN_DB"})

    assert canonical_db.exists()
    assert not legacy_db.exists()


@pytest.mark.asyncio
async def test_state_tasks_fail_closed_when_task_db_directory_is_missing(tmp_path, monkeypatch):
    """Engine importable but its DB directory gone => named error, never a freshly created store.

    This is the shape the ticket actually hit. Without the check the engine
    loads, the seam reports canonical, and the caller gets a bare
    ``sqlite3.OperationalError`` that names neither the target nor a way out.
    """
    monkeypatch.delenv("TASKPLAN_DB", raising=False)
    monkeypatch.delenv("SCANNER_TASKS_DB", raising=False)
    engine_dir = _write_fixture_rinnsal(tmp_path)
    home = _fake_home(tmp_path, monkeypatch)  # deliberately without ~/.taskplan

    registry = ModuleRegistry(_state_config(engine_dir, tmp_path))
    registry.discover_and_load()

    with pytest.raises(engine_seams.CanonicalEngineUnavailable) as excinfo:
        await registry.call_tool("hb_state_task_list", {"status": "all"})
    message = str(excinfo.value)
    assert "hb_state_task_*" in message
    assert "taskplan.db" in message  # names the unreachable target
    assert 'mode = "bundled"' in message  # names the way out

    with pytest.raises(engine_seams.CanonicalEngineUnavailable):
        await registry.call_tool("hb_state_task_create", {"title": "no store"})

    assert not (home / ".taskplan").exists(), "the missing store directory must not be created"

    # hb_state_mem_* has no seam and stays usable even in this state -- so the
    # state DB legitimately exists here. What must NOT exist in it is a bundled
    # `tasks` table, which would be the shadow task store.
    stored = await registry.call_tool("hb_state_mem_set", {"key": "k", "value": "v"})
    assert stored["status"] == "stored"
    with sqlite3.connect(str(tmp_path / "rinnsal.db")) as connection:
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "tasks" not in tables, "no shadow bundled task store may be created"


@pytest.mark.asyncio
async def test_state_tasks_fail_closed_but_unseamed_families_keep_working(tmp_path):
    """Only hb_state_task_* is gated; hb_state_mem_* and hb_state_dispatch have no seam.

    Gating the whole StateModule would break tool families that never had a
    canonical counterpart and are bundled by definition, not by fallback.
    """
    config = HomebaseConfig(
        enabled_modules=["state"],
        engine_mode="canonical",
        engine_configs={"state": {"path": str(tmp_path / "nowhere")}},
        module_configs={"state": {"db_path": str(tmp_path / "rinnsal.db")}},
    )
    registry = ModuleRegistry(config)
    registry.discover_and_load()

    with pytest.raises(engine_seams.CanonicalEngineUnavailable) as excinfo:
        await registry.call_tool("hb_state_task_create", {"title": "Bundled fallback"})
    assert "hb_state_task_*" in str(excinfo.value)

    with pytest.raises(engine_seams.CanonicalEngineUnavailable):
        await registry.call_tool("hb_state_task_list", {})

    stored = await registry.call_tool("hb_state_mem_set", {"key": "k", "value": "v"})
    assert stored["status"] == "stored"
    fetched = await registry.call_tool("hb_state_mem_get", {"query": "k"})
    assert fetched["count"] == 1
