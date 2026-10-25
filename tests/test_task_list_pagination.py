"""Bounded Homebase task pages without reading a host's task database."""

from __future__ import annotations

import importlib
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType

import pytest

from homebase.modules.state import StateModule
from homebase.storage import connect_db

TASKMASTER_PAGE_SHA = "ac2c681c6e1e97133608bf58c5720ceea7be1478"


def _state(tmp_path: Path) -> StateModule:
    return StateModule({"db_path": str(tmp_path / "homebase.db"), "_engine_mode": "bundled"})


@pytest.mark.asyncio
async def test_bundled_417_rows_and_late_agent_are_all_reachable(tmp_path):
    state = _state(tmp_path)
    now = datetime.now(timezone.utc).isoformat()
    with connect_db(state.db_path) as conn:
        conn.executemany(
            "INSERT INTO tasks (title, description, priority, status, agent_id, created_at, updated_at) "
            "VALUES (?, '', 'medium', 'open', ?, ?, ?)",
            [(f"Task {n}", "other" if n <= 200 else "late", now, now) for n in range(1, 418)],
        )

    async def pages(**filters):
        cursor = None
        results = []
        while True:
            page = await state._task_list(cursor=cursor, **filters)
            results.append(page)
            if not page["truncated"]:
                return results
            cursor = page["next_cursor"]

    all_pages = await pages(status="open")
    assert [page["count"] for page in all_pages] == [200, 200, 17]
    assert [page["total"] for page in all_pages] == [417] * 3
    assert [task["id"] for page in all_pages for task in page["tasks"]] == list(range(1, 418))
    assert [page["next_cursor"] for page in all_pages] == [200, 400, None]

    late_pages = await pages(status="open", agent_id="late")
    assert [page["count"] for page in late_pages] == [200, 17]
    assert [page["total"] for page in late_pages] == [217, 217]
    assert [task["id"] for page in late_pages for task in page["tasks"]] == list(range(201, 418))

    empty = await state._task_list(status="done")
    assert (empty["count"], empty["total"], empty["truncated"], empty["next_cursor"]) == (0, 0, False, None)
    beyond = await state._task_list(status="open", cursor=999)
    assert (beyond["count"], beyond["total"], beyond["truncated"], beyond["next_cursor"]) == (0, 417, False, None)
    exact = await state._task_list(status="open", limit=500)
    assert (exact["count"], exact["total"], exact["truncated"]) == (417, 417, False)
    with connect_db(state.db_path) as conn:
        conn.execute("UPDATE tasks SET status = 'done' WHERE id = 1")
        conn.execute("UPDATE tasks SET status = 'in_progress' WHERE id = 2")
    assert (await state._task_list(status="done"))["total"] == 1
    assert (await state._task_list(status="in_progress"))["tasks"][0]["id"] == 2
    assert (await state._task_list(status="all"))["total"] == 417


@pytest.mark.asyncio
async def test_canonical_passes_filters_and_preserves_page_metadata(tmp_path):
    state = _state(tmp_path)
    calls = []

    class PageClient:
        def __init__(self, **kwargs):
            calls.append(("init", kwargs))

        def list_page(self, **kwargs):
            calls.append(("page", kwargs))
            return {
                "count": 1, "total": 217, "limit": kwargs["limit"], "cursor": kwargs["cursor"],
                "next_cursor": 202, "truncated": True,
                "tasks": [{"id": 202, "status": "active", "agent_id": "late"}],
            }

    state.task_engine_mode = "canonical"
    state._task_client_cls = PageClient
    state._task_db_path = str(tmp_path / "canonical.db")
    page = await state._task_list(status="in_progress", agent_id="late", limit=17, cursor=201)
    assert calls[1] == ("page", {"status": "active", "include_done": False,
                                  "agent_id": "late", "limit": 17, "cursor": 201})
    assert (page["count"], page["total"], page["next_cursor"], page["truncated"]) == (1, 217, 202, True)
    assert page["tasks"][0]["status"] == "in_progress"


@pytest.mark.asyncio
async def test_old_canonical_client_returns_upgrade_error_without_legacy_list(tmp_path):
    state = _state(tmp_path)

    class OldClient:
        def __init__(self, **kwargs):
            pass

        def list(self, **kwargs):
            pytest.fail("legacy list must not silently cap the result")

    state.task_engine_mode = "canonical"
    state._task_client_cls = OldClient
    state._task_db_path = str(tmp_path / "canonical.db")
    result = await state._task_list(status="open")
    assert result["status"] == "unavailable"
    assert result["error"]["code"] == "task_pagination_unavailable"
    assert "tasks" not in result and "total" not in result


@pytest.mark.asyncio
@pytest.mark.parametrize("bad_limit", [0, 501, -1, True, 1.5, "200", None])
async def test_invalid_limit_is_rejected(tmp_path, bad_limit):
    with pytest.raises(ValueError, match="limit must be an integer"):
        await _state(tmp_path)._task_list(limit=bad_limit)


@pytest.mark.asyncio
@pytest.mark.parametrize("bad_cursor", [True, 1.5, "200", []])
async def test_invalid_cursor_is_rejected(tmp_path, bad_cursor):
    with pytest.raises(ValueError, match="cursor must be an integer"):
        await _state(tmp_path)._task_list(cursor=bad_cursor)


def _candidate_client(monkeypatch):
    root_raw = os.environ.get("TASKMASTER_T560_ROOT")
    if not root_raw:
        pytest.skip("set TASKMASTER_T560_ROOT to the read-only PR22 worktree for the exact-commit integration test")
    root = Path(root_raw).resolve()
    head = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True, text=True, check=True)
    assert head.stdout.strip() == TASKMASTER_PAGE_SHA
    package = ModuleType("t560_candidate_taskplan")
    package.__path__ = [str(root / "taskplan")]
    monkeypatch.setitem(sys.modules, package.__name__, package)
    module = importlib.import_module("t560_candidate_taskplan.client")
    return module.TaskClient


@pytest.mark.asyncio
async def test_exact_taskmaster_pr22_client_with_isolated_417_row_database(tmp_path, monkeypatch):
    client_class = _candidate_client(monkeypatch)
    db_path = tmp_path / "candidate-taskplan.db"
    other = client_class(db_path=db_path, agent_id="other")
    late = client_class(db_path=db_path, agent_id="late")
    for n in range(200):
        other.add(f"Other {n}")
    for n in range(217):
        late.add(f"Late {n}")

    state = _state(tmp_path)
    state.task_engine_mode = "canonical"
    state._task_client_cls = client_class
    state._task_db_path = str(db_path)
    pages = []
    cursor = None
    while True:
        page = await state._task_list(status="open", cursor=cursor)
        pages.append(page)
        if not page["truncated"]:
            break
        cursor = page["next_cursor"]
    assert [page["count"] for page in pages] == [200, 200, 17]
    assert [page["total"] for page in pages] == [417] * 3
    assert [task["id"] for page in pages for task in page["tasks"]] == list(range(1, 418))

    late_first = await state._task_list(status="open", agent_id="late")
    late_second = await state._task_list(status="open", agent_id="late", cursor=late_first["next_cursor"])
    assert [(page["count"], page["total"]) for page in (late_first, late_second)] == [(200, 217), (17, 217)]
    assert [task["id"] for page in (late_first, late_second) for task in page["tasks"]] == list(range(201, 418))

    assert (await state._task_list(status="done"))["total"] == 0
    assert (await state._task_list(status="all"))["total"] == 417
    assert (await state._task_list(status="open", limit=500))["count"] == 417
    assert (await state._task_list(status="open", cursor=999))["total"] == 417
    assert (await state._task_list(status="open", cursor=999))["tasks"] == []
    task_id = late.add("Done task")["id"]
    late.done(task_id)
    active_id = late.add("Active task")["id"]
    late.activate(active_id)
    assert (await state._task_list(status="done"))["tasks"][0]["id"] == task_id
    assert (await state._task_list(status="in_progress"))["tasks"][0]["status"] == "in_progress"
    assert (await state._task_list(status="all"))["total"] == 419
