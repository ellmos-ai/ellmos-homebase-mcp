"""hb_garden_ - Minimal knowledge store."""

from __future__ import annotations

from typing import Any

from homebase.modules import ModuleBase, ToolDefinition
from homebase.storage import connect_db, contains_term, utc_now


class GardenModule(ModuleBase):
    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.db_path = config.get("db_path", "~/.homebase/garden.db")
        self.allow_run = bool(config.get("allow_run", False))
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
        return {"status": "ok", "count": len(rows), "results": [dict(row) for row in rows]}

    async def _get(self, **kwargs) -> dict[str, Any]:
        key = str(kwargs["key"])
        with connect_db(self.db_path) as connection:
            row = connection.execute(
                "SELECT key, value, updated_at FROM garden_entries WHERE key = ?",
                (key,),
            ).fetchone()
        if row is None:
            return {"status": "not_found", "key": key}
        return {"status": "ok", "entry": dict(row)}

    async def _put(self, **kwargs) -> dict[str, Any]:
        key = str(kwargs["key"])
        value = str(kwargs["value"])
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
        return {"status": "stored", "key": key}

    async def _run(self, **kwargs) -> dict[str, Any]:
        key = str(kwargs["key"])
        if not self.allow_run:
            return {
                "status": "disabled",
                "key": key,
                "message": "Command execution is disabled. Set [garden].allow_run=true to enable a future executor.",
            }
        return {"status": "not_implemented", "key": key, "message": "Execution backend is not implemented yet."}


def create_module(config: dict[str, Any]) -> GardenModule:
    return GardenModule(config)
