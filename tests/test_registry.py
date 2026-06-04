import pytest

from homebase.config import HomebaseConfig
from homebase.registry import ModuleRegistry


def _registry(tmp_path, modules):
    module_configs = {
        "mem": {"db_path": str(tmp_path / "memory.db")},
        "kb": {"db_path": str(tmp_path / "knowledge.db")},
        "garden": {"db_path": str(tmp_path / "garden.db")},
        "state": {"db_path": str(tmp_path / "state.db")},
    }
    registry = ModuleRegistry(HomebaseConfig(enabled_modules=modules, module_configs=module_configs))
    registry.discover_and_load()
    registry.list_tools()
    return registry


@pytest.mark.asyncio
async def test_registry_lists_enabled_tools(tmp_path):
    registry = _registry(tmp_path, ["mem", "kb", "garden", "state", "api", "test"])

    tool_names = {tool.name for tool in registry.list_tools()}

    assert "hb_mem_store" in tool_names
    assert "hb_kb_search" in tool_names
    assert "hb_garden_put" in tool_names
    assert "hb_state_task_create" in tool_names


@pytest.mark.asyncio
async def test_memory_store_query_and_context(tmp_path):
    registry = _registry(tmp_path, ["mem"])

    stored = await registry.call_tool(
        "hb_mem_store",
        {"category": "fact", "content": "Homebase speichert jetzt SQLite-Memory", "confidence": 0.9},
    )
    query = await registry.call_tool("hb_mem_query", {"query": "SQLite", "category": "all"})
    context = await registry.call_tool("hb_mem_context", {"focus": "SQLite", "max_tokens": 80})

    assert stored["status"] == "stored"
    assert query["count"] == 1
    assert query["results"][0]["content"] == "Homebase speichert jetzt SQLite-Memory"
    assert "SQLite-Memory" in context["context"]


@pytest.mark.asyncio
async def test_knowledge_ingest_search_get_and_list(tmp_path):
    registry = _registry(tmp_path, ["kb"])

    ingested = await registry.call_tool(
        "hb_kb_ingest",
        {"content": "ServerCommander prüft Health-Checks.", "source": "test", "tags": ["mcp", "ops"]},
    )
    search = await registry.call_tool("hb_kb_search", {"query": "Health", "category": "ops"})
    fetched = await registry.call_tool("hb_kb_get", {"id": ingested["id"]})
    listed = await registry.call_tool("hb_kb_list", {})

    assert search["count"] == 1
    assert fetched["entry"]["source"] == "test"
    assert listed["tags"] == ["mcp", "ops"]


@pytest.mark.asyncio
async def test_garden_put_find_get_and_safe_run(tmp_path):
    registry = _registry(tmp_path, ["garden"])

    stored = await registry.call_tool("hb_garden_put", {"key": "note", "value": "kleiner Knowledge Store"})
    found = await registry.call_tool("hb_garden_find", {"query": "Knowledge"})
    fetched = await registry.call_tool("hb_garden_get", {"key": "note"})
    run = await registry.call_tool("hb_garden_run", {"key": "note"})

    assert stored["status"] == "stored"
    assert found["count"] == 1
    assert fetched["entry"]["value"] == "kleiner Knowledge Store"
    assert run["status"] == "disabled"


@pytest.mark.asyncio
async def test_state_memory_and_tasks(tmp_path):
    registry = _registry(tmp_path, ["state"])

    mem = await registry.call_tool("hb_state_mem_set", {"key": "focus", "value": "MCP", "type": "fact"})
    mem_list = await registry.call_tool("hb_state_mem_get", {"query": "focus", "type": "all"})
    task = await registry.call_tool("hb_state_task_create", {"title": "Tests ergänzen", "priority": "high"})
    updated = await registry.call_tool("hb_state_task_update", {"task_id": task["task_id"], "status": "done"})
    tasks = await registry.call_tool("hb_state_task_list", {"status": "done"})

    assert mem["status"] == "stored"
    assert mem_list["results"][0]["value"] == "MCP"
    assert updated["status"] == "updated"
    assert tasks["tasks"][0]["title"] == "Tests ergänzen"


def test_registry_skips_unknown_module():
    registry = ModuleRegistry(HomebaseConfig(enabled_modules=["unknown"]))

    loaded, skipped = registry.discover_and_load()

    assert loaded == []
    assert skipped == [("unknown", "unknown module")]


@pytest.mark.asyncio
async def test_registry_rejects_unknown_tool(tmp_path):
    registry = _registry(tmp_path, ["mem"])

    with pytest.raises(ValueError, match="Unknown Homebase tool"):
        await registry.call_tool("hb_missing", {})
