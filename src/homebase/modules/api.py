"""hb_api_ — API discovery and exploration (wraps ApiProber).

Passive API probing: OpenAPI detection, wordlist scanning, HATEOAS crawling.
Zero external dependencies (stdlib only).
"""

from __future__ import annotations
from typing import Any
from homebase.modules import ModuleBase, ToolDefinition


class ApiModule(ModuleBase):

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.db_path = config.get("db_path", "~/.homebase/probes.db")
        self.timeout = config.get("timeout", 10)

    def get_tools(self) -> list[ToolDefinition]:
        return [
            ToolDefinition(name="hb_api_probe", description="Probe a URL using all strategies (OpenAPI, wordlist, pattern, HATEOAS)", input_schema={"type": "object", "properties": {"url": {"type": "string"}, "strategies": {"type": "array", "items": {"type": "string"}, "default": ["openapi", "wordlist", "pattern", "hateoas"]}}, "required": ["url"]}, handler=self._probe),
            ToolDefinition(name="hb_api_discover", description="Auto-detect API schema from a base URL", input_schema={"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]}, handler=self._discover),
            ToolDefinition(name="hb_api_export", description="Export probe results as Markdown or JSON", input_schema={"type": "object", "properties": {"probe_id": {"type": "integer"}, "format": {"type": "string", "enum": ["markdown", "json"]}}, "required": ["probe_id"]}, handler=self._export),
            ToolDefinition(name="hb_api_history", description="List previous probe results", input_schema={"type": "object", "properties": {"limit": {"type": "integer", "default": 20}}}, handler=self._history),
        ]

    async def _probe(self, **kwargs) -> str:
        return f"[DRAFT] Would probe {kwargs.get('url')}"

    async def _discover(self, **kwargs) -> str:
        return f"[DRAFT] Would auto-discover API at {kwargs.get('url')}"

    async def _export(self, **kwargs) -> str:
        return f"[DRAFT] Would export probe #{kwargs.get('probe_id')}"

    async def _history(self, **kwargs) -> str:
        return "[DRAFT] Would list probe history"


def create_module(config: dict[str, Any]) -> ApiModule:
    return ApiModule(config)
