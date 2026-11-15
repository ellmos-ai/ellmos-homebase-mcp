import json

import mcp.types as types
import pytest
from mcp.server import Server

from homebase import server

_SDK_V1 = hasattr(Server, "list_tools")


class _FakeRegistry:
    def list_tools(self) -> list:
        return []

    async def call_tool(self, name: str, arguments: dict) -> dict:
        assert name == "hb_mem_query"
        assert arguments == {"query": "Umlaut"}
        return {"status": "ok", "results": [{"content": "Grün"}]}



async def _dispatch_call_tool(name: str, arguments: dict):
    """Run tools/call through the handler registered for the installed SDK."""
    params = types.CallToolRequestParams(name=name, arguments=arguments)
    if _SDK_V1:
        request = types.CallToolRequest(method="tools/call", params=params)
        response = await server.app.request_handlers[types.CallToolRequest](request)
        result = response.root
        return result.content, result.isError
    entry = server.app.get_request_handler("tools/call")
    assert entry is not None
    result = await entry.handler(None, params)
    return result.content, result.is_error


@pytest.mark.asyncio
async def test_call_tool_serializes_registry_dict_as_text_content(monkeypatch):
    monkeypatch.setattr(server, "get_registry", lambda: _FakeRegistry())

    content, is_error = await _dispatch_call_tool("hb_mem_query", {"query": "Umlaut"})

    assert is_error is False
    assert len(content) == 1
    assert isinstance(content[0], types.TextContent)
    assert json.loads(content[0].text) == {
        "status": "ok",
        "results": [{"content": "Grün"}],
    }


@pytest.mark.asyncio
async def test_call_tool_failure_becomes_error_result(monkeypatch):
    class _FailingRegistry(_FakeRegistry):
        async def call_tool(self, name: str, arguments: dict) -> dict:
            raise RuntimeError("Modul nicht verfügbar")

    monkeypatch.setattr(server, "get_registry", lambda: _FailingRegistry())

    content, is_error = await _dispatch_call_tool("hb_mem_query", {"query": "Umlaut"})

    assert is_error is True
    assert "Modul nicht verfügbar" in content[0].text


@pytest.mark.asyncio
async def test_list_tools_handler_is_registered(monkeypatch):
    monkeypatch.setattr(server, "get_registry", lambda: _FakeRegistry())

    assert await server.list_tools() == []
    if _SDK_V1:
        assert types.ListToolsRequest in server.app.request_handlers
    else:
        assert server.app.get_request_handler("tools/list") is not None
