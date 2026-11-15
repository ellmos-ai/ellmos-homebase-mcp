"""Homebase MCP Server - Entry Point.

Loads available modules, registers their tools, and starts the MCP server.
Modules with missing dependencies are skipped gracefully.
"""

import asyncio
import json
import logging
import sys

import mcp.types as types
from mcp.server import Server
from mcp.server.stdio import stdio_server

from homebase.config import load_config
from homebase.engines import engine_summary
from homebase.registry import ModuleRegistry

logger = logging.getLogger("homebase")

_SERVER_NAME = "ellmos-homebase"
_registry: ModuleRegistry | None = None


def get_registry() -> ModuleRegistry:
    global _registry
    if _registry is None:
        config = load_config()
        _registry = ModuleRegistry(config)
        _registry.discover_and_load()
    return _registry


async def list_tools() -> list[types.Tool]:
    return get_registry().list_tools()


async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    result = await get_registry().call_tool(name, arguments)
    return [types.TextContent(type="text", text=json.dumps(result, ensure_ascii=False))]


def _tool_input_schema(name: str) -> dict | None:
    for tool in get_registry().list_tools():
        if tool.name == name:
            return getattr(tool, "inputSchema", None) or getattr(tool, "input_schema", None)
    return None


def _build_app() -> Server:
    """Create the low-level server for the installed MCP SDK generation.

    SDK 1.x registers handlers through decorators. SDK 2.x removed them and
    takes the handlers as constructor arguments instead.
    """
    if hasattr(Server, "list_tools"):
        server = Server(_SERVER_NAME)
        server.list_tools()(list_tools)
        server.call_tool()(call_tool)
        return server

    async def on_list_tools(_ctx, _params) -> types.ListToolsResult:
        return types.ListToolsResult(tools=await list_tools())

    async def on_call_tool(_ctx, params) -> types.CallToolResult:
        try:
            content = await call_tool(params.name, params.arguments or {})
        except Exception as exc:  # mirror SDK 1.x: tool failures become error results
            logger.exception("Tool call failed: %s", params.name)
            return types.CallToolResult(
                content=[types.TextContent(type="text", text=str(exc))],
                is_error=True,
            )
        return types.CallToolResult(content=content, is_error=False)

    return Server(
        _SERVER_NAME,
        get_tool_input_schema=_tool_input_schema,
        on_list_tools=on_list_tools,
        on_call_tool=on_call_tool,
    )


app = _build_app()


async def serve():
    registry = get_registry()

    for name in registry.loaded_names:
        logger.info("Module loaded: %s", name)
    for name, reason in registry.skipped_modules:
        logger.warning("Module skipped: %s (%s)", name, reason)

    logger.info("Engine seams: %s", ", ".join(engine_summary(registry.config)))
    logger.info(
        "Homebase ready - %d modules, %d tools",
        len(registry.loaded_names),
        len(registry.list_tools()),
    )

    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


def main():
    logging.basicConfig(level=logging.INFO, stream=sys.stderr)
    asyncio.run(serve())


if __name__ == "__main__":
    main()
