from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread

import pytest

from homebase.config import HomebaseConfig
from homebase.i18n import I18n, normalize_locale
from homebase.registry import ModuleRegistry
from homebase.storage import connect_db


def _registry(tmp_path, modules):
    module_configs = {
        "mem": {"db_path": str(tmp_path / "memory.db")},
        "kb": {"db_path": str(tmp_path / "knowledge.db")},
        "garden": {"db_path": str(tmp_path / "garden.db")},
        "state": {"db_path": str(tmp_path / "state.db")},
        "api": {"db_path": str(tmp_path / "probes.db"), "timeout": 2},
        "conn": {"db_path": str(tmp_path / "connectors.db"), "connectors": ["local", "telegram"]},
        "auto": {
            "db_path": str(tmp_path / "automation.db"),
            "chains": [{"name": "care", "description": "Care workflow", "steps": ["inspect", "patch", "test"]}],
        },
        "plug": {"db_path": str(tmp_path / "plugins.db"), "plugins_dir": str(tmp_path / "plugins")},
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
    assert stored["agent_id"] == "unknown"
    assert query["count"] == 1
    assert query["results"][0]["agent_id"] == "unknown"
    assert query["results"][0]["content"] == "Homebase speichert jetzt SQLite-Memory"
    assert "SQLite-Memory" in context["context"]


@pytest.mark.asyncio
async def test_memory_agent_id_provenance_and_filter(tmp_path):
    registry = _registry(tmp_path, ["mem"])

    await registry.call_tool(
        "hb_mem_store",
        {"category": "lesson", "content": "Gemeinsame Memory braucht Herkunft.", "agent_id": "codex"},
    )
    await registry.call_tool(
        "hb_mem_store",
        {"category": "lesson", "content": "Gemeinsame Memory braucht Herkunft.", "agent_id": "claude"},
    )

    codex = await registry.call_tool("hb_mem_query", {"query": "Herkunft", "agent_id": "codex"})
    context = await registry.call_tool("hb_mem_context", {"focus": "Herkunft", "agent_id": "codex"})
    duplicates = await registry.call_tool("hb_mem_merge", {"agent_id": "codex"})

    assert codex["count"] == 1
    assert codex["results"][0]["agent_id"] == "codex"
    assert "[codex:lesson:" in context["context"]
    assert duplicates["duplicate_groups"] == []


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
    assert ingested["agent_id"] == "unknown"
    assert search["results"][0]["agent_id"] == "unknown"
    assert fetched["entry"]["source"] == "test"
    assert listed["tags"] == ["mcp", "ops"]


@pytest.mark.asyncio
async def test_knowledge_agent_id_provenance_and_filter(tmp_path):
    registry = _registry(tmp_path, ["kb"])

    await registry.call_tool(
        "hb_kb_ingest",
        {"content": "Alpha-Adapter dokumentieren.", "tags": ["alpha"], "agent_id": "codex"},
    )
    await registry.call_tool(
        "hb_kb_ingest",
        {"content": "Alpha-Adapter dokumentieren.", "tags": ["alpha", "review"], "agent_id": "gemini"},
    )

    search = await registry.call_tool("hb_kb_search", {"query": "Adapter", "agent_id": "gemini"})
    tags = await registry.call_tool("hb_kb_list", {"agent_id": "codex"})
    hidden = await registry.call_tool("hb_kb_get", {"id": search["results"][0]["id"], "agent_id": "codex"})

    assert search["count"] == 1
    assert search["results"][0]["agent_id"] == "gemini"
    assert tags["tags"] == ["alpha"]
    assert hidden["status"] == "not_found"


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
    assert mem["agent_id"] == "unknown"
    assert mem_list["results"][0]["value"] == "MCP"
    assert mem_list["results"][0]["agent_id"] == "unknown"
    assert task["agent_id"] == "unknown"
    assert updated["status"] == "updated"
    assert tasks["tasks"][0]["title"] == "Tests ergänzen"


@pytest.mark.asyncio
async def test_state_memory_keeps_same_key_per_agent(tmp_path):
    registry = _registry(tmp_path, ["state"])

    await registry.call_tool("hb_state_mem_set", {"key": "focus", "value": "Homebase", "agent_id": "codex"})
    await registry.call_tool("hb_state_mem_set", {"key": "focus", "value": "ServerCommander", "agent_id": "claude"})
    await registry.call_tool("hb_state_mem_set", {"key": "focus", "value": "Homebase P0", "agent_id": "codex"})

    codex = await registry.call_tool("hb_state_mem_get", {"query": "focus", "agent_id": "codex"})
    all_agents = await registry.call_tool("hb_state_mem_get", {"query": "focus"})

    assert codex["count"] == 1
    assert codex["results"][0]["value"] == "Homebase P0"
    assert codex["results"][0]["agent_id"] == "codex"
    assert all_agents["count"] == 2


@pytest.mark.asyncio
async def test_state_tasks_filter_by_agent_id(tmp_path):
    registry = _registry(tmp_path, ["state"])

    codex_task = await registry.call_tool("hb_state_task_create", {"title": "Codex task", "agent_id": "codex"})
    await registry.call_tool("hb_state_task_create", {"title": "Claude task", "agent_id": "claude"})
    await registry.call_tool(
        "hb_state_task_update",
        {"task_id": codex_task["task_id"], "status": "done", "agent_id": "codex"},
    )

    codex = await registry.call_tool("hb_state_task_list", {"status": "all", "agent_id": "codex"})
    claude_done = await registry.call_tool("hb_state_task_list", {"status": "done", "agent_id": "claude"})

    assert codex["count"] == 1
    assert codex["tasks"][0]["agent_id"] == "codex"
    assert codex["tasks"][0]["status"] == "done"
    assert claude_done["tasks"] == []


def test_connect_db_enables_wal_and_busy_timeout(tmp_path):
    with connect_db(str(tmp_path / "wal.db")) as connection:
        journal_mode = connection.execute("PRAGMA journal_mode").fetchone()[0]
        busy_timeout = connection.execute("PRAGMA busy_timeout").fetchone()[0]

    assert journal_mode == "wal"
    assert busy_timeout == 30000


@pytest.mark.asyncio
async def test_routing_select_evaluate_and_stats(tmp_path):
    registry = _registry(tmp_path, ["route"])

    selected = await registry.call_tool(
        "hb_route_select",
        {"prompt": "Fix this Python bug and add tests", "constraints": {"speed": "fast"}},
    )
    evaluated = await registry.call_tool("hb_route_evaluate", {"route_id": selected["route_id"], "quality": 0.8})
    stats = await registry.call_tool("hb_route_stats", {})

    assert selected["status"] == "ok"
    assert selected["strategy"] == "fast"
    assert selected["signals"]["has_code"] is True
    assert evaluated["status"] == "recorded"
    assert stats["routes"] == 1
    assert stats["average_quality"] == 0.8


@pytest.mark.asyncio
async def test_swarm_parallel_and_consensus_plans(tmp_path):
    registry = _registry(tmp_path, ["swarm"])

    parallel = await registry.call_tool(
        "hb_swarm_parallel",
        {"task": "Audit files", "chunks": ["README", "tests", "src"], "workers": 2},
    )
    consensus = await registry.call_tool("hb_swarm_consensus", {"question": "Ship?", "voters": 3})

    assert parallel["status"] == "planned"
    assert parallel["assignments"][2]["worker"] == "worker-1"
    assert consensus["quorum"] == 2


@pytest.mark.asyncio
async def test_api_probe_history_and_export(tmp_path):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/openapi.json":
                self.send_response(200)
                self.send_header("content-type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"openapi":"3.1.0","paths":{"/health":{}}}')
                return
            if self.path == "/health":
                self.send_response(204)
                self.end_headers()
                return
            self.send_response(404)
            self.end_headers()

        def log_message(self, format, *args):
            return

    httpd = HTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        registry = _registry(tmp_path, ["api"])
        base_url = f"http://127.0.0.1:{httpd.server_port}/"

        probe = await registry.call_tool("hb_api_probe", {"url": base_url, "strategies": ["openapi", "wordlist"]})
        history = await registry.call_tool("hb_api_history", {})
        exported = await registry.call_tool("hb_api_export", {"probe_id": probe["probe_id"], "format": "markdown"})

        assert probe["status"] == "ok"
        assert any(item["is_openapi"] for item in probe["openapi"])
        assert any(item["status_code"] == 204 for item in probe["wordlist"])
        assert history["count"] == 1
        assert "# API Probe" in exported["content"]
    finally:
        httpd.shutdown()
        thread.join(timeout=2)


@pytest.mark.asyncio
async def test_testing_module_runs_builtin_battery(tmp_path):
    registry = _registry(tmp_path, ["test"])

    listed = await registry.call_tool("hb_test_list", {})
    run = await registry.call_tool("hb_test_run", {"battery": "smoke"})
    summary = await registry.call_tool("hb_test_results", {})

    assert listed["count"] >= 2
    assert run["status"] == "ok"
    assert run["failed"] == 0
    assert summary["passed"] == run["passed"]


@pytest.mark.asyncio
async def test_connectors_registry_queues_local_messages(tmp_path):
    registry = _registry(tmp_path, ["conn"])

    listed = await registry.call_tool("hb_conn_list", {})
    queued = await registry.call_tool(
        "hb_conn_send",
        {"connector": "local", "target": "ops", "message": "Check Homebase connectors"},
    )
    status = await registry.call_tool("hb_conn_status", {"connector": "local"})
    received = await registry.call_tool("hb_conn_receive", {"connector": "local"})
    missing = await registry.call_tool("hb_conn_send", {"connector": "email", "message": "test"})

    assert listed["count"] == 2
    assert queued["status"] == "queued"
    assert queued["sent"] is False
    assert queued["delivery"] == "local_outbox_only"
    assert status["connector"]["outbox_pending"] == 1
    assert received["status"] == "ok"
    assert received["messages"] == []
    assert missing["status"] == "unknown_connector"
    assert missing["available"] == ["local", "telegram"]


@pytest.mark.asyncio
async def test_automation_chains_queue_local_runs(tmp_path):
    registry = _registry(tmp_path, ["auto"])

    listed = await registry.call_tool("hb_auto_list_chains", {})
    queued = await registry.call_tool("hb_auto_run", {"chain": "care", "input": "Fix adapters"})
    status = await registry.call_tool("hb_auto_status", {"run_id": queued["run_id"]})
    result = await registry.call_tool("hb_auto_result", {"run_id": queued["run_id"]})
    missing = await registry.call_tool("hb_auto_run", {"chain": "missing"})

    assert listed["count"] == 1
    assert listed["chains"][0]["steps"] == ["inspect", "patch", "test"]
    assert queued["status"] == "queued"
    assert queued["executed"] is False
    assert status["run"]["status"] == "queued_local_only"
    assert result["result"]["delivery"] == "local_plan_only"
    assert missing["status"] == "unknown_chain"
    assert missing["available"] == ["care"]


@pytest.mark.asyncio
async def test_plugins_discover_info_and_dry_run(tmp_path):
    plugin_root = tmp_path / "plugins"
    plugin_dir = plugin_root / "demo-plugin"
    plugin_dir.mkdir(parents=True)
    (plugin_dir / "plugin.json").write_text(
        '{"name":"demo-plugin","description":"Demo plugin","kind":"utility"}',
        encoding="utf-8",
    )
    registry = _registry(tmp_path, ["plug"])

    discovered = await registry.call_tool("hb_plug_discover", {"path": str(plugin_root)})
    listed = await registry.call_tool("hb_plug_list", {})
    info = await registry.call_tool("hb_plug_info", {"plugin": "demo-plugin"})
    run = await registry.call_tool("hb_plug_run", {"plugin": "demo-plugin", "args": {"dry": True}})
    missing = await registry.call_tool("hb_plug_info", {"plugin": "missing"})

    assert discovered["count"] == 1
    assert listed["plugins"][0]["name"] == "demo-plugin"
    assert info["plugin"]["description"] == "Demo plugin"
    assert run["status"] == "dry_run_recorded"
    assert run["executed"] is False
    assert run["result"]["execution"] == "disabled"
    assert missing["status"] == "not_found"


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


def test_routing_and_swarm_schema_descriptions_are_localized(tmp_path):
    registry = _registry(tmp_path, ["route", "swarm"])
    registry.config.language = "de"
    registry.i18n = I18n("de")

    tools = {tool.name: tool for tool in registry.list_tools()}
    route_properties = tools["hb_route_select"].inputSchema["properties"]
    swarm_properties = tools["hb_swarm_parallel"].inputSchema["properties"]

    assert route_properties["prompt"]["description"] == "Prompt-Text, der analysiert oder geroutet werden soll."
    assert route_properties["constraints"]["description"].startswith("Optionale Routing-Vorgaben")
    assert swarm_properties["chunks"]["description"] == "Task-Abschnitte, die auf Worker verteilt werden."
    assert swarm_properties["workers"]["description"] == "Anzahl paralleler Worker, die geplant werden sollen."


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
