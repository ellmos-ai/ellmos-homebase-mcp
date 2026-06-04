"""Homebase MCP Server - Entry Point.

Loads available modules, registers their tools, and starts the MCP server.
Modules with missing dependencies are skipped gracefully.
"""

import asyncio
import logging
import sys

import mcp.types as types
from mcp.server import Server
from mcp.server.stdio import stdio_server

from homebase.config import load_config
from homebase.registry import ModuleRegistry

logger = logging.getLogger("homebase")

app = Server("ellmos-homebase")
_registry: ModuleRegistry | None = None


def get_registry() -> ModuleRegistry:
    global _registry
    if _registry is None:
        config = load_config()
        _registry = ModuleRegistry(config)
        _registry.discover_and_load()
    return _registry


@app.list_tools()
async def list_tools() -> list[types.Tool]:
    return get_registry().list_tools()


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> dict:
    return await get_registry().call_tool(name, arguments)


async def serve():
    registry = get_registry()

    for name in registry.loaded_names:
        logger.info("Module loaded: %s", name)
    for name, reason in registry.skipped_modules:
        logger.warning("Module skipped: %s (%s)", name, reason)

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
