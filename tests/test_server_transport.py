import json

import mcp.types as types
import pytest

from homebase import server


class _FakeRegistry:
    def list_tools(self) -> list:
        return []

    async def call_tool(self, name: str, arguments: dict) -> dict:
        assert name == "hb_mem_query"
        assert arguments == {"query": "Umlaut"}
        return {"status": "ok", "results": [{"content": "Grün"}]}



@pytest.mark.asyncio
async def test_call_tool_serializes_registry_dict_as_text_content(monkeypatch):
    monkeypatch.setattr(server, "get_registry", lambda: _FakeRegistry())
    request = types.CallToolRequest(
        method="tools/call",
        params=types.CallToolRequestParams(
            name="hb_mem_query",
            arguments={"query": "Umlaut"},
        ),
    )

    response = await server.app.request_handlers[types.CallToolRequest](request)

    result = response.root
    assert result.isError is False
    assert len(result.content) == 1
    assert isinstance(result.content[0], types.TextContent)
    assert json.loads(result.content[0].text) == {
        "status": "ok",
        "results": [{"content": "Grün"}],
    }
