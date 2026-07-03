"""hb_mem_ - Persistent memory module."""

from __future__ import annotations

from typing import Any

from homebase.modules import ModuleBase, ToolDefinition
from homebase.storage import (
    connect_db,
    contains_term,
    ensure_column,
    fts_match_query,
    resolve_agent_id,
    setup_fts,
    utc_now,
)


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
                    agent_id TEXT NOT NULL DEFAULT 'unknown',
                    created_at TEXT NOT NULL
                )
                """
            )
            ensure_column(connection, "memories", "agent_id", "TEXT NOT NULL DEFAULT 'unknown'")
            self._fts = setup_fts(connection, "memories", "memories_fts", ["content"])

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
                        "agent_id": {
                            "type": "string",
                            "description": "Agent identifier for shared-memory provenance",
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
                        "agent_id": {"type": "string", "description": "Optional agent filter"},
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
                        "agent_id": {"type": "string", "description": "Optional agent filter"},
                    },
                },
                handler=self._context,
            ),
            ToolDefinition(
                name="hb_mem_merge",
                description="Confidence-based merge of duplicate memories (dry_run previews; dry_run=false applies the merge)",
                input_schema={
                    "type": "object",
                    "properties": {
                        "dry_run": {"type": "boolean", "default": True, "description": "Preview merge without applying. Set false to apply."},
                        "agent_id": {"type": "string", "description": "Optional agent filter"},
                    },
                },
                handler=self._merge,
            ),
            ToolDefinition(
                name="hb_mem_consolidate",
                description="Decay memory confidence and prune low-confidence entries (dry_run previews; dry_run=false applies)",
                input_schema={
                    "type": "object",
                    "properties": {
                        "dry_run": {"type": "boolean", "default": True, "description": "Preview without applying. Set false to apply."},
                        "decay": {"type": "number", "default": 0.1, "minimum": 0, "maximum": 1, "description": "Absolute confidence reduction per entry."},
                        "min_confidence": {"type": "number", "default": 0.2, "minimum": 0, "maximum": 1, "description": "Entries below this (after decay) are pruned."},
                        "agent_id": {"type": "string", "description": "Optional agent filter"},
                    },
                },
                handler=self._consolidate,
            ),
        ]

    async def _store(self, **kwargs) -> dict[str, Any]:
        content = str(kwargs["content"])
        category = str(kwargs["category"])
        confidence = min(1.0, max(0.0, float(kwargs.get("confidence", 1.0))))
        agent_id = resolve_agent_id(self.config, kwargs.get("agent_id"))

        with connect_db(self.db_path) as connection:
            cursor = connection.execute(
                """
                INSERT INTO memories (content, category, confidence, agent_id, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (content, category, confidence, agent_id, utc_now()),
            )
            memory_id = int(cursor.lastrowid)

        return {
            "status": "stored",
            "id": memory_id,
            "category": category,
            "confidence": confidence,
            "agent_id": agent_id,
        }

    async def _query(self, **kwargs) -> dict[str, Any]:
        query = str(kwargs["query"])
        category = str(kwargs.get("category", "all"))
        limit = int(kwargs.get("limit", 10))
        agent_id = kwargs.get("agent_id")

        if getattr(self, "_fts", False):
            match = fts_match_query(query)
            if match:
                fsql = """
                    SELECT m.id, m.content, m.category, m.confidence, m.agent_id, m.created_at
                    FROM memories_fts f JOIN memories m ON m.id = f.rowid
                    WHERE memories_fts MATCH ?
                """
                fparams: list[Any] = [match]
                if category != "all":
                    fsql += " AND m.category = ?"
                    fparams.append(category)
                if agent_id:
                    fsql += " AND m.agent_id = ?"
                    fparams.append(str(agent_id))
                fsql += " ORDER BY rank LIMIT ?"
                fparams.append(limit)
                with connect_db(self.db_path) as connection:
                    rows = connection.execute(fsql, fparams).fetchall()
                return {
                    "status": "ok",
                    "query": query,
                    "mode": "fts5",
                    "agent_id": agent_id,
                    "count": len(rows),
                    "results": [dict(row) for row in rows],
                }

        sql = """
            SELECT id, content, category, confidence, agent_id, created_at
            FROM memories
            WHERE content LIKE ?
        """
        params: list[Any] = [contains_term(query)]
        if category != "all":
            sql += " AND category = ?"
            params.append(category)
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
            "results": [dict(row) for row in rows],
        }

    async def _context(self, **kwargs) -> dict[str, Any]:
        max_tokens = int(kwargs.get("max_tokens", 500))
        focus = kwargs.get("focus")
        agent_id = kwargs.get("agent_id")
        char_budget = max_tokens * 4

        sql = "SELECT content, category, confidence, agent_id, created_at FROM memories WHERE 1 = 1"
        params: list[Any] = []
        if focus:
            sql += " AND content LIKE ?"
            params.append(contains_term(str(focus)))
        if agent_id:
            sql += " AND agent_id = ?"
            params.append(str(agent_id))
        sql += " ORDER BY confidence DESC, id DESC LIMIT 50"

        with connect_db(self.db_path) as connection:
            rows = connection.execute(sql, params).fetchall()

        parts = []
        used_chars = 0
        for row in rows:
            line = f"- [{row['agent_id']}:{row['category']}:{row['confidence']:.2f}] {row['content']}"
            if used_chars + len(line) > char_budget:
                break
            parts.append(line)
            used_chars += len(line)

        return {
            "status": "ok",
            "focus": focus,
            "agent_id": agent_id,
            "context": "\n".join(parts),
            "entries": len(parts),
        }

    async def _merge(self, **kwargs) -> dict[str, Any]:
        dry_run = bool(kwargs.get("dry_run", True))
        agent_id = kwargs.get("agent_id")
        params: list[Any] = []
        where = ""
        if agent_id:
            where = "WHERE agent_id = ?"
            params.append(str(agent_id))

        with connect_db(self.db_path) as connection:
            duplicates = connection.execute(
                f"""
                SELECT content, category, agent_id, COUNT(*) AS count, MAX(confidence) AS max_confidence
                FROM memories
                {where}
                GROUP BY content, category, agent_id
                HAVING COUNT(*) > 1
                """,
                params,
            ).fetchall()

            if dry_run:
                return {
                    "status": "dry_run",
                    "agent_id": agent_id,
                    "duplicate_groups": [dict(row) for row in duplicates],
                    "message": "Preview only. Call with dry_run=false to apply the confidence-based merge.",
                }

            # Confidence-based merge: per duplicate group keep one survivor that
            # carries the group's highest confidence; delete the redundant rows.
            merged_groups = 0
            removed_rows = 0
            for group in duplicates:
                rows = connection.execute(
                    """
                    SELECT id, confidence FROM memories
                    WHERE content = ? AND category = ? AND agent_id = ?
                    ORDER BY confidence DESC, id ASC
                    """,
                    (group["content"], group["category"], group["agent_id"]),
                ).fetchall()
                if len(rows) <= 1:
                    continue
                survivor_id = int(rows[0]["id"])
                max_confidence = max(float(row["confidence"]) for row in rows)
                loser_ids = [(int(row["id"]),) for row in rows[1:]]
                connection.execute(
                    "UPDATE memories SET confidence = ? WHERE id = ?",
                    (max_confidence, survivor_id),
                )
                connection.executemany("DELETE FROM memories WHERE id = ?", loser_ids)
                merged_groups += 1
                removed_rows += len(loser_ids)

        return {
            "status": "merged",
            "agent_id": agent_id,
            "merged_groups": merged_groups,
            "removed_rows": removed_rows,
            "message": f"Merged {merged_groups} duplicate group(s); removed {removed_rows} redundant row(s).",
        }

    async def _consolidate(self, **kwargs) -> dict[str, Any]:
        dry_run = bool(kwargs.get("dry_run", True))
        agent_id = kwargs.get("agent_id")
        decay = min(1.0, max(0.0, float(kwargs.get("decay", 0.1))))
        min_confidence = min(1.0, max(0.0, float(kwargs.get("min_confidence", 0.2))))

        where = ""
        params: list[Any] = []
        if agent_id:
            where = "WHERE agent_id = ?"
            params.append(str(agent_id))

        with connect_db(self.db_path) as connection:
            rows = connection.execute(
                f"SELECT id, confidence FROM memories {where}", params
            ).fetchall()

            survivors = 0
            prune_ids: list[tuple[int]] = []
            for row in rows:
                new_confidence = max(0.0, float(row["confidence"]) - decay)
                if new_confidence < min_confidence:
                    prune_ids.append((int(row["id"]),))
                    continue
                survivors += 1
                if not dry_run and new_confidence != float(row["confidence"]):
                    connection.execute(
                        "UPDATE memories SET confidence = ? WHERE id = ?",
                        (new_confidence, int(row["id"])),
                    )

            if dry_run:
                return {
                    "status": "dry_run",
                    "agent_id": agent_id,
                    "decay": decay,
                    "min_confidence": min_confidence,
                    "would_keep": survivors,
                    "would_prune": len(prune_ids),
                }

            if prune_ids:
                connection.executemany("DELETE FROM memories WHERE id = ?", prune_ids)

        return {
            "status": "consolidated",
            "agent_id": agent_id,
            "decay": decay,
            "min_confidence": min_confidence,
            "kept": survivors,
            "pruned": len(prune_ids),
            "message": f"Decayed confidence by {decay}; kept {survivors}, pruned {len(prune_ids)} below {min_confidence}.",
        }


def create_module(config: dict[str, Any]) -> MemoryModule:
    return MemoryModule(config)
