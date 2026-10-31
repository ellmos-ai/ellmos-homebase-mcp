"""hb_kb_ - Knowledge database, with a seam onto the real KnowledgeDigest engine.

``[engines.kb] mode = "canonical"`` delegates to KnowledgeDigest's own database
(``KnowledgeDigest.search_all``). KnowledgeDigest's public API is narrower than
this tool family, so under a *reachable* canonical engine:

* ``hb_kb_search`` is delegated (``query``, ``limit``). ``category`` and ``agent_id``
  have no counterpart (KnowledgeDigest indexes skills, wikis and documents without
  tags or per-agent provenance) -> ``not_supported`` instead of a silently unfiltered list.
* ``hb_kb_ingest`` / ``hb_kb_get`` / ``hb_kb_list`` -> ``not_supported``: KnowledgeDigest
  ingests files and directories only (no text/tag/agent ingest), has no public
  document-by-id getter and no tag index. Reported, not worked around.

Unreachable engine or database under ``canonical`` -> every tool of the family raises
``CanonicalEngineUnavailable`` and no bundled store is created (MODE-CONTRACT.md).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from homebase import engines as engine_seams
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

logger = logging.getLogger("homebase.knowledge")


class KnowledgeModule(ModuleBase):
    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.db_path = config.get("db_path", "~/.homebase/knowledge.db")

        self.engine_mode = "bundled"
        self._kd = None
        self._kd_db: Path | None = None
        self._unavailable: str | None = None
        if str(config.get("_engine_mode", "bundled")) == "canonical":
            self._kd = engine_seams.load_knowledgedigest(config.get("_engine_path"))
            if self._kd is None:
                self._unavailable = engine_seams.unavailable_message(
                    tool_family="hb_kb_*",
                    engine="KnowledgeDigest",
                    module="kb",
                    configured_path=config.get("_engine_path"),
                )
            else:
                # Optional explicit DB (`[kb].kd_db`); otherwise KnowledgeDigest's own default.
                explicit = config.get("kd_db")
                self._kd_db = Path(str(explicit)).expanduser() if explicit else self._kd.default_db_path
                # The DB must already exist: opening a missing one would let
                # KnowledgeDigest create an empty store -- a second, disconnected database.
                if self._kd_db is None or not self._kd_db.is_file():
                    self._unavailable = engine_seams.database_unavailable_message(
                        tool_family="hb_kb_*",
                        engine="KnowledgeDigest",
                        module="kb",
                        db_path=self._kd_db,
                        db_setting="[kb].kd_db or KnowledgeDigest's own db_path setting",
                    )
                else:
                    self.engine_mode = "canonical"
            if self._unavailable is not None:
                logger.error(self._unavailable)

        # Only create the bundled store when bundled is the *chosen* mode. An
        # unreachable canonical engine must not leave a second knowledge.db behind.
        if self.engine_mode == "bundled" and self._unavailable is None:
            self._init_db()

    def _require_engine(self) -> None:
        """Fail closed when canonical was requested but is unreachable."""
        if self._unavailable is not None:
            raise engine_seams.CanonicalEngineUnavailable(self._unavailable)

    def _unsupported(self, operation: str, reason: str) -> dict[str, Any]:
        return {
            "status": "not_supported",
            "engine": "canonical",
            "operation": operation,
            "message": (
                f"hb_kb_{operation} is not available in canonical mode: {reason} "
                "Use the bundled store ([engines.kb] mode = \"bundled\") for this operation."
            ),
        }

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
            self._fts = setup_fts(
                connection, "knowledge_entries", "knowledge_fts", ["content", "source", "tags"]
            )

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
        self._require_engine()
        query = str(kwargs["query"])
        limit = int(kwargs.get("limit", 10))
        category = kwargs.get("category")
        agent_id = kwargs.get("agent_id")

        if self.engine_mode == "canonical":
            unsupported = [name for name, value in (("category", category), ("agent_id", agent_id)) if value]
            if unsupported:
                return self._unsupported(
                    "search",
                    f"KnowledgeDigest has no {' / '.join(unsupported)} filter (it indexes skills, wikis "
                    "and documents without tags or per-agent provenance); an unfiltered list would "
                    "pretend the filter was applied.",
                )
            kd = self._kd.cls(db_path=self._kd_db)
            try:
                rows = kd.search_all(query, limit=limit)
            finally:
                kd.close()
            return {
                "status": "ok",
                "engine": "canonical",
                "query": query,
                "count": len(rows),
                "results": [dict(row) for row in rows],
            }

        if getattr(self, "_fts", False):
            match = fts_match_query(query)
            if match:
                fsql = """
                    SELECT e.id, e.content, e.source, e.tags, e.agent_id, e.created_at
                    FROM knowledge_fts f JOIN knowledge_entries e ON e.id = f.rowid
                    WHERE knowledge_fts MATCH ?
                """
                fparams: list[Any] = [match]
                if category:
                    fsql += " AND e.tags LIKE ?"
                    fparams.append(contains_term(str(category)))
                if agent_id:
                    fsql += " AND e.agent_id = ?"
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
                    "results": [_entry_from_row(row) for row in rows],
                }

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
        self._require_engine()
        if self.engine_mode == "canonical":
            return self._unsupported(
                "ingest",
                "KnowledgeDigest ingests files and directories only (KnowledgeDigest.ingest(path)); "
                "it has no text-ingest API and no tag or agent_id fields.",
            )
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
        self._require_engine()
        if self.engine_mode == "canonical":
            return self._unsupported(
                "get",
                "KnowledgeDigest has no public document-by-id getter (only get_skill by name and "
                "get_wiki by path), and its ids are not homebase entry ids.",
            )
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
        self._require_engine()
        if self.engine_mode == "canonical":
            return self._unsupported(
                "list",
                "KnowledgeDigest has no tag index; its documents carry keywords, not tags.",
            )
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
