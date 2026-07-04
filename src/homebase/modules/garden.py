"""hb_garden_ - Minimal knowledge store, with a seam onto the real Gardener engine."""

from __future__ import annotations

import logging
from typing import Any

from homebase import engines as engine_seams
from homebase.modules import ModuleBase, ToolDefinition
from homebase.storage import connect_db, contains_term, utc_now

logger = logging.getLogger("homebase.garden")


class GardenModule(ModuleBase):
    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.db_path = config.get("db_path", "~/.homebase/garden.db")
        self.allow_run = bool(config.get("allow_run", False))

        self.engine_mode = "bundled"
        self._gardener = None
        requested_mode = str(config.get("_engine_mode", "bundled"))
        if requested_mode == "canonical":
            self._gardener = engine_seams.load_gardener(config.get("_engine_path"))
            if self._gardener is not None:
                self.engine_mode = "canonical"
            else:
                logger.warning(
                    "hb_garden_*: canonical mode requested but the real Gardener engine "
                    "was not found/importable; falling back to the bundled garden store."
                )

        if self.engine_mode == "bundled":
            self._init_db()

    def _init_db(self) -> None:
        with connect_db(self.db_path) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS garden_entries (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

    def get_tools(self) -> list[ToolDefinition]:
        return [
            ToolDefinition(
                name="hb_garden_find",
                description="Search the garden",
                input_schema={
                    "type": "object",
                    "properties": {"query": {"type": "string"}, "limit": {"type": "integer", "default": 10}},
                    "required": ["query"],
                },
                handler=self._find,
            ),
            ToolDefinition(
                name="hb_garden_get",
                description="Get a specific entry by key",
                input_schema={"type": "object", "properties": {"key": {"type": "string"}}, "required": ["key"]},
                handler=self._get,
            ),
            ToolDefinition(
                name="hb_garden_put",
                description="Store or update an entry",
                input_schema={
                    "type": "object",
                    "properties": {"key": {"type": "string"}, "value": {"type": "string"}},
                    "required": ["key", "value"],
                },
                handler=self._put,
            ),
            ToolDefinition(
                name="hb_garden_run",
                description="Run a stored command if execution is explicitly enabled",
                input_schema={"type": "object", "properties": {"key": {"type": "string"}}, "required": ["key"]},
                handler=self._run,
            ),
        ]

    async def _find(self, **kwargs) -> dict[str, Any]:
        query = str(kwargs["query"])
        limit = int(kwargs.get("limit", 10))

        if self.engine_mode == "canonical":
            rows = self._gardener.find(query, limit=limit)
            return {
                "status": "ok",
                "engine": "canonical",
                "count": len(rows),
                "results": [_garden_entry(row) for row in rows],
            }

        with connect_db(self.db_path) as connection:
            rows = connection.execute(
                """
                SELECT key, value, updated_at
                FROM garden_entries
                WHERE key LIKE ? OR value LIKE ?
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (contains_term(query), contains_term(query), limit),
            ).fetchall()
        return {"status": "ok", "engine": "bundled", "count": len(rows), "results": [dict(row) for row in rows]}

    async def _get(self, **kwargs) -> dict[str, Any]:
        key = str(kwargs["key"])

        if self.engine_mode == "canonical":
            entry = self._gardener.get(key)
            if entry is None:
                return {"status": "not_found", "engine": "canonical", "key": key}
            return {"status": "ok", "engine": "canonical", "entry": _garden_entry(entry)}

        with connect_db(self.db_path) as connection:
            row = connection.execute(
                "SELECT key, value, updated_at FROM garden_entries WHERE key = ?",
                (key,),
            ).fetchone()
        if row is None:
            return {"status": "not_found", "engine": "bundled", "key": key}
        return {"status": "ok", "engine": "bundled", "entry": dict(row)}

    async def _put(self, **kwargs) -> dict[str, Any]:
        key = str(kwargs["key"])
        value = str(kwargs["value"])

        if self.engine_mode == "canonical":
            self._gardener.put(key, content=value, type="homebase", target="user")
            return {"status": "stored", "engine": "canonical", "key": key}

        with connect_db(self.db_path) as connection:
            connection.execute(
                """
                INSERT INTO garden_entries (key, value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    updated_at = excluded.updated_at
                """,
                (key, value, utc_now()),
            )
        return {"status": "stored", "engine": "bundled", "key": key}

    async def _run(self, **kwargs) -> dict[str, Any]:
        key = str(kwargs["key"])
        if not self.allow_run:
            return {
                "status": "disabled",
                "key": key,
                "message": "Command execution is disabled. Set [garden].allow_run=true to enable a future executor.",
            }

        if self.engine_mode == "canonical":
            success, output = self._gardener.run(key)
            return {
                "status": "ok" if success else "error",
                "engine": "canonical",
                "key": key,
                "output": output,
            }

        return {
            "status": "not_implemented",
            "engine": "bundled",
            "key": key,
            "message": "Execution backend is not implemented yet.",
        }


def _garden_entry(entry: dict[str, Any]) -> dict[str, Any]:
    """Map a real Gardener `everything` row onto the historical key/value/updated_at shape.

    Keeps `hb_garden_*` callers that only look at key/value/updated_at working
    unchanged, while surfacing the richer canonical fields (type, tags,
    source, pinned) for callers that want them.
    """
    return {
        "key": entry.get("name"),
        "value": entry.get("content", ""),
        "updated_at": entry.get("updated"),
        "type": entry.get("type"),
        "tags": entry.get("tags"),
        "pinned": entry.get("pinned"),
        "source": entry.get("source"),
    }


def create_module(config: dict[str, Any]) -> GardenModule:
    return GardenModule(config)
