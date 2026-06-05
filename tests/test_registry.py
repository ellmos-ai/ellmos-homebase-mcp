import pytest

from homebase.config import HomebaseConfig
from homebase.i18n import I18n, normalize_locale
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


def test_tool_descriptions_are_localized(tmp_path):
    registry = _registry(tmp_path, ["mem"])
    registry.config.language = "de"
    registry.i18n = I18n("de")

    tools = {tool.name: tool for tool in registry.list_tools()}

    assert tools["hb_mem_store"].description.startswith("Speichert einen Fakt")


def test_tool_input_schema_descriptions_are_localized(tmp_path):
    registry = _registry(tmp_path, ["mem"])
    registry.config.language = "de"
    registry.i18n = I18n("de")

    tools = {tool.name: tool for tool in registry.list_tools()}
    properties = tools["hb_mem_store"].inputSchema["properties"]

    assert properties["content"]["description"] == "Inhaltstext."
    assert properties["confidence"]["description"] == "Konfidenzwert von 0 bis 1."


def test_tool_input_schema_descriptions_gain_english_defaults(tmp_path):
    registry = _registry(tmp_path, ["mem"])

    tools = {tool.name: tool for tool in registry.list_tools()}
    properties = tools["hb_mem_query"].inputSchema["properties"]

    assert properties["limit"]["description"] == "Maximum number of results to return."


def test_tool_descriptions_fallback_to_default_for_partial_locale(tmp_path):
    registry = _registry(tmp_path, ["mem"])
    registry.config.language = "es"
    registry.i18n = I18n("es")

    tools = {tool.name: tool for tool in registry.list_tools()}

    assert tools["hb_mem_store"].description.startswith("Guarda")
    assert tools["hb_mem_merge"].description.startswith("Preview")


def test_locale_normalization():
    assert normalize_locale("de-DE") == "de"
    assert normalize_locale("zh_Hans") == "zh"
    assert normalize_locale("unknown") == "en"


@pytest.mark.asyncio
async def test_registry_rejects_unknown_tool(tmp_path):
    registry = _registry(tmp_path, ["mem"])

    with pytest.raises(ValueError, match="Unknown Homebase tool"):
        await registry.call_tool("hb_missing", {})


@pytest.mark.asyncio
async def test_registry_rejects_unknown_tool_with_localized_error(tmp_path):
    registry = _registry(tmp_path, ["mem"])
    registry.i18n = I18n("de")

    with pytest.raises(ValueError, match="Unbekanntes Homebase-Tool"):
        await registry.call_tool("hb_missing", {})
