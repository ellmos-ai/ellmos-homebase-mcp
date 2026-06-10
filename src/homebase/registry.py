"""Module registry — discovers, validates, and loads Homebase modules."""

from __future__ import annotations

import importlib
import logging
from typing import Any

import mcp.types as types
from mcp.server import Server

from homebase.config import HomebaseConfig
from homebase.i18n import I18n
from homebase.modules import ModuleBase

logger = logging.getLogger("homebase.registry")

MODULE_MAP = {
    "mem": "homebase.modules.memory",
    "route": "homebase.modules.routing",
    "kb": "homebase.modules.knowledge",
    "swarm": "homebase.modules.swarm",
    "state": "homebase.modules.state",
    "garden": "homebase.modules.garden",
    "api": "homebase.modules.api",
    "test": "homebase.modules.testing",
    "auto": "homebase.modules.automation",
    "conn": "homebase.modules.connectors",
    "plug": "homebase.modules.plugins",
}


class ModuleRegistry:
    def __init__(self, config: HomebaseConfig):
        self.config = config
        self._modules: dict[str, ModuleBase] = {}
        self._handlers = {}
        self._tool_count = 0
        self.i18n = I18n(config.language)
        self.loaded_names: list[str] = []
        self.skipped_modules: list[tuple[str, str]] = []

    @property
    def tool_count(self) -> int:
        return self._tool_count

    def discover_and_load(self) -> tuple[list[str], list[tuple[str, str]]]:
        """Load enabled modules. Returns (loaded_names, [(skipped_name, reason)])."""
        loaded = []
        skipped = []
        self._modules.clear()
        self._handlers.clear()
        self._tool_count = 0

        for name in self.config.enabled_modules:
            module_path = MODULE_MAP.get(name)
            if not module_path:
                skipped.append((name, "unknown module"))
                continue

            try:
                mod = importlib.import_module(module_path)
            except ImportError as e:
                skipped.append((name, f"import error: {e}"))
                continue

            factory = getattr(mod, "create_module", None)
            if factory is None:
                skipped.append((name, "no create_module() found"))
                continue

            try:
                instance = factory(self.config.module_config(name))
            except Exception as e:
                skipped.append((name, f"init error: {e}"))
                continue

            deps_ok, missing = instance.check_dependencies()
            if not deps_ok:
                skipped.append((name, f"missing: {', '.join(missing)}"))
                continue

            self._modules[name] = instance
            loaded.append(name)

        self.loaded_names = loaded
        self.skipped_modules = skipped
        return loaded, skipped

    def register_tools(self, server: Server) -> None:
        """Register MCP list/call handlers for all loaded modules."""

        @server.list_tools()
        async def list_tools() -> list[types.Tool]:
            return self.list_tools()

        @server.call_tool()
        async def call_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
            return await self.call_tool(name, arguments)

    def list_tools(self) -> list[types.Tool]:
        """Return all loaded module tools as MCP Tool definitions."""
        handlers: dict[str, Any] = {}
        tools: list[types.Tool] = []

        for name, module in self._modules.items():
            module_tools = module.get_tools()
            for tool_def in module_tools:
                handlers[tool_def.name] = tool_def.handler
                tools.append(
                    types.Tool(
                        name=tool_def.name,
                        description=self.i18n.t(f"tool.{tool_def.name}", tool_def.description),
                        inputSchema=self.i18n.localize_schema(tool_def.input_schema),
                    )
                )
            logger.info("Prepared %d tools from module '%s'", len(module_tools), name)

        self._handlers = handlers
        self._tool_count = len(tools)
        return tools

    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        """Dispatch one MCP tool call by name."""
        if not self._handlers:
            self.list_tools()

        handler = self._handlers.get(name)
        if handler is None:
            message = self.i18n.t("error.unknown_tool", "Unknown Homebase tool: {name}").format(name=name)
            raise ValueError(message)

        result = await handler(**(arguments or {}))
        if isinstance(result, dict):
            return result
        return {"result": result}
