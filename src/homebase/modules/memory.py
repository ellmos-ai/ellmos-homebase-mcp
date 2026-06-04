"""hb_mem_ - Persistent memory module."""

from __future__ import annotations

from typing import Any

from homebase.modules import ModuleBase, ToolDefinition
from homebase.storage import connect_db, contains_term, utc_now


class MemoryModule(ModuleBase):
    """SQLite-backed persistent memory for LLMs."""

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.db_path = config.get("db_path", "~/.homebase/memory.db")
        self._init_db()

    def _init_db(self) -> None:
        with connect_db(self.db_path) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content TEXT NOT NULL,
                    category TEXT NOT NULL,
                    confidence REAL NOT NULL DEFAULT 1.0,
                    created_at TEXT NOT NULL
                )
                """
            )

    def get_tools(self) -> list[ToolDefinition]:
        return [
            ToolDefinition(
                name="hb_mem_store",
                description="Store a fact, lesson, or working memory entry",
                input_schema={
                    "type": "object",
                    "properties": {
                        "content": {"type": "string", "description": "The content to store"},
                        "category": {
                            "type": "string",
                            "enum": ["fact", "lesson", "working"],
                            "description": "Memory category",
                        },
                        "confidence": {
                            "type": "number",
                            "minimum": 0,
                            "maximum": 1,
                            "description": "Confidence score (0-1)",
                        },
                    },
                    "required": ["content", "category"],
                },
                handler=self._store,
            ),
            ToolDefinition(
                name="hb_mem_query",
                description="Search memory by keyword",
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query"},
                        "category": {"type": "string", "enum": ["fact", "lesson", "working", "all"]},
                        "limit": {"type": "integer", "default": 10},
                    },
                    "required": ["query"],
                },
                handler=self._query,
            ),
            ToolDefinition(
                name="hb_mem_context",
                description="Generate compact context string for prompt injection",
                input_schema={
                    "type": "object",
                    "properties": {
                        "max_tokens": {"type": "integer", "default": 500, "description": "Approximate token budget"},
                        "focus": {"type": "string", "description": "Optional topic focus"},
                    },
                },
                handler=self._context,
            ),
            ToolDefinition(
                name="hb_mem_merge",
                description="Preview confidence-based merge candidates for overlapping memories",
                input_schema={
                    "type": "object",
                    "properties": {
                        "dry_run": {"type": "boolean", "default": True, "description": "Preview merge without applying"},
                    },
                },
                handler=self._merge,
            ),
        ]

    async def _store(self, **kwargs) -> dict[str, Any]:
        content = str(kwargs["content"])
        category = str(kwargs["category"])
        confidence = min(1.0, max(0.0, float(kwargs.get("confidence", 1.0))))

        with connect_db(self.db_path) as connection:
            cursor = connection.execute(
                """
                INSERT INTO memories (content, category, confidence, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (content, category, confidence, utc_now()),
            )
            memory_id = int(cursor.lastrowid)

        return {"status": "stored", "id": memory_id, "category": category, "confidence": confidence}

    async def _query(self, **kwargs) -> dict[str, Any]:
        query = str(kwargs["query"])
        category = str(kwargs.get("category", "all"))
        limit = int(kwargs.get("limit", 10))

        sql = """
            SELECT id, content, category, confidence, created_at
            FROM memories
            WHERE content LIKE ?
        """
        params: list[Any] = [contains_term(query)]
        if category != "all":
            sql += " AND category = ?"
            params.append(category)
        sql += " ORDER BY id DESC LIMIT ?"
        params.append(limit)

        with connect_db(self.db_path) as connection:
            rows = connection.execute(sql, params).fetchall()

        return {"status": "ok", "query": query, "count": len(rows), "results": [dict(row) for row in rows]}

    async def _context(self, **kwargs) -> dict[str, Any]:
        max_tokens = int(kwargs.get("max_tokens", 500))
        focus = kwargs.get("focus")
        char_budget = max_tokens * 4

        sql = "SELECT content, category, confidence, created_at FROM memories"
        params: list[Any] = []
        if focus:
            sql += " WHERE content LIKE ?"
            params.append(contains_term(str(focus)))
        sql += " ORDER BY confidence DESC, id DESC LIMIT 50"

        with connect_db(self.db_path) as connection:
            rows = connection.execute(sql, params).fetchall()

        parts = []
        used_chars = 0
        for row in rows:
            line = f"- [{row['category']}:{row['confidence']:.2f}] {row['content']}"
            if used_chars + len(line) > char_budget:
                break
            parts.append(line)
            used_chars += len(line)

        return {"status": "ok", "focus": focus, "context": "\n".join(parts), "entries": len(parts)}

    async def _merge(self, **kwargs) -> dict[str, Any]:
        dry_run = bool(kwargs.get("dry_run", True))
        with connect_db(self.db_path) as connection:
            duplicates = connection.execute(
                """
                SELECT content, category, COUNT(*) AS count
                FROM memories
                GROUP BY content, category
                HAVING COUNT(*) > 1
                """
            ).fetchall()

        return {
            "status": "dry_run" if dry_run else "not_implemented",
            "duplicate_groups": [dict(row) for row in duplicates],
            "message": "Automatic merge is intentionally preview-only in this alpha.",
        }


def create_module(config: dict[str, Any]) -> MemoryModule:
    return MemoryModule(config)
