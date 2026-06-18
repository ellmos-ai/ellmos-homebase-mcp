"""hb_kb_ - Knowledge database."""

from __future__ import annotations

import json
from typing import Any

from homebase.modules import ModuleBase, ToolDefinition
from homebase.storage import connect_db, contains_term, ensure_column, resolve_agent_id, utc_now


class KnowledgeModule(ModuleBase):
    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.db_path = config.get("db_path", "~/.homebase/knowledge.db")
        self._init_db()

    def _init_db(self) -> None:
        with connect_db(self.db_path) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS knowledge_entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content TEXT NOT NULL,
                    source TEXT,
                    tags TEXT NOT NULL DEFAULT '[]',
                    agent_id TEXT NOT NULL DEFAULT 'unknown',
                    created_at TEXT NOT NULL
                )
                """
            )
            ensure_column(connection, "knowledge_entries", "agent_id", "TEXT NOT NULL DEFAULT 'unknown'")

    def get_tools(self) -> list[ToolDefinition]:
        return [
            ToolDefinition(
                name="hb_kb_search",
                description="Full-text search in knowledge database",
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "limit": {"type": "integer", "default": 10},
                        "category": {"type": "string"},
                        "agent_id": {"type": "string", "description": "Optional agent filter"},
                    },
                    "required": ["query"],
                },
                handler=self._search,
            ),
            ToolDefinition(
                name="hb_kb_ingest",
                description="Add new knowledge (text, URL, or file content)",
                input_schema={
                    "type": "object",
                    "properties": {
                        "content": {"type": "string"},
                        "source": {"type": "string", "description": "URL or file path"},
                        "tags": {"type": "array", "items": {"type": "string"}},
                        "agent_id": {
                            "type": "string",
                            "description": "Agent identifier for shared-knowledge provenance",
                        },
                    },
                    "required": ["content"],
                },
                handler=self._ingest,
            ),
            ToolDefinition(
                name="hb_kb_get",
                description="Get a single knowledge entry with metadata",
                input_schema={
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer"},
                        "agent_id": {"type": "string", "description": "Optional agent filter"},
                    },
                    "required": ["id"],
                },
                handler=self._get,
            ),
            ToolDefinition(
                name="hb_kb_list",
                description="List tags in the knowledge base",
                input_schema={
                    "type": "object",
                    "properties": {"agent_id": {"type": "string", "description": "Optional agent filter"}},
                },
                handler=self._list,
            ),
        ]

    async def _search(self, **kwargs) -> dict[str, Any]:
        query = str(kwargs["query"])
        limit = int(kwargs.get("limit", 10))
        category = kwargs.get("category")
        agent_id = kwargs.get("agent_id")

        params: list[Any] = [contains_term(query), contains_term(query), contains_term(query)]
        sql = """
            SELECT id, content, source, tags, agent_id, created_at
            FROM knowledge_entries
            WHERE (content LIKE ? OR source LIKE ? OR tags LIKE ?)
        """
        if category:
            sql += " AND tags LIKE ?"
            params.append(contains_term(str(category)))
        if agent_id:
            sql += " AND agent_id = ?"
            params.append(str(agent_id))
        sql += " ORDER BY id DESC LIMIT ?"
        params.append(limit)

        with connect_db(self.db_path) as connection:
            rows = connection.execute(sql, params).fetchall()

        return {
            "status": "ok",
            "query": query,
            "agent_id": agent_id,
            "count": len(rows),
            "results": [_entry_from_row(row) for row in rows],
        }

    async def _ingest(self, **kwargs) -> dict[str, Any]:
        tags = kwargs.get("tags") or []
        if not isinstance(tags, list):
            tags = [str(tags)]
        agent_id = resolve_agent_id(self.config, kwargs.get("agent_id"))

        with connect_db(self.db_path) as connection:
            cursor = connection.execute(
                """
                INSERT INTO knowledge_entries (content, source, tags, agent_id, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    str(kwargs["content"]),
                    kwargs.get("source"),
                    json.dumps(tags, ensure_ascii=False),
                    agent_id,
                    utc_now(),
                ),
            )
            entry_id = int(cursor.lastrowid)

        return {"status": "ingested", "id": entry_id, "tags": tags, "agent_id": agent_id}

    async def _get(self, **kwargs) -> dict[str, Any]:
        entry_id = int(kwargs["id"])
        agent_id = kwargs.get("agent_id")
        sql = "SELECT id, content, source, tags, agent_id, created_at FROM knowledge_entries WHERE id = ?"
        params: list[Any] = [entry_id]
        if agent_id:
            sql += " AND agent_id = ?"
            params.append(str(agent_id))
        with connect_db(self.db_path) as connection:
            row = connection.execute(sql, params).fetchone()
        if row is None:
            return {"status": "not_found", "id": entry_id}
        return {"status": "ok", "entry": _entry_from_row(row)}

    async def _list(self, **kwargs) -> dict[str, Any]:
        agent_id = kwargs.get("agent_id")
        sql = "SELECT tags FROM knowledge_entries"
        params: list[Any] = []
        if agent_id:
            sql += " WHERE agent_id = ?"
            params.append(str(agent_id))
        tags: set[str] = set()
        with connect_db(self.db_path) as connection:
            rows = connection.execute(sql, params).fetchall()
        for row in rows:
            tags.update(json.loads(row["tags"] or "[]"))
        return {"status": "ok", "agent_id": agent_id, "tags": sorted(tags), "count": len(tags)}


def _entry_from_row(row) -> dict[str, Any]:
    entry = dict(row)
    entry["tags"] = json.loads(entry.get("tags") or "[]")
    return entry


def create_module(config: dict[str, Any]) -> KnowledgeModule:
    return KnowledgeModule(config)
