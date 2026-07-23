"""hb_mem_ - Persistent memory module, with a seam onto the canonical USMC engine.

Bundled mode (default) keeps a self-contained SQLite store with FTS5 search,
confidence-based merge, and decay/consolidation -- a zero-dependency install
always works. With ``[engines.mem].mode = "canonical"`` (or global
``[engines].mode = "canonical"``) and a USMC checkout present, ``hb_mem_store``
/``hb_mem_query``/``hb_mem_context`` delegate to the real, cross-agent USMC
store instead of a second disconnected copy.

Model-reconciliation notes (USMC's model differs from this flat memory):

* USMC has no free-text keyword search, so canonical ``hb_mem_query`` filters
  USMC facts client-side (``mode = "client_filter"``).
* USMC facts use fixed categories ({user,project,system,domain}); homebase's own
  category (fact/lesson/working) is preserved in the fact KEY as
  ``"<category>/<uuid>"`` under a single backing USMC category, so all homebase
  memories stay together and remain queryable.
* Per-call ``agent_id`` provenance is preserved by constructing one USMC client
  per call bound to that agent (USMC is multi-agent by design).
* ``hb_mem_merge``/``hb_mem_consolidate`` are bundled-only bulk-hygiene ops; USMC
  applies confidence-merge per fact on write and has no bulk equivalent, so
  canonical mode reports ``not_supported`` for them (deferred, TODO #72).
"""

from __future__ import annotations

import logging
import uuid
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

logger = logging.getLogger("homebase.memory")

# Single USMC fact category that backs all homebase memories (must be one of
# USMC's valid categories). The homebase category lives in the fact key prefix.
_USMC_CATEGORY = "domain"


class MemoryModule(ModuleBase):
    """SQLite-backed persistent memory for LLMs, with an optional USMC seam."""

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.db_path = config.get("db_path", "~/.homebase/memory.db")

        self.engine_mode = "bundled"
        self._usmc_cls = None
        # Optional explicit USMC DB path; None lets USMC use its own default store.
        self._usmc_db = config.get("usmc_db") or None
        if str(config.get("_engine_mode", "bundled")) == "canonical":
            self._usmc_cls = engine_seams.load_usmc_client_class(config.get("_engine_path"))
            if self._usmc_cls is not None:
                self.engine_mode = "canonical"
            else:
                logger.warning(
                    "hb_mem_*: canonical mode requested but the real USMC engine was not "
                    "found/importable; falling back to the bundled memory store."
                )

        if self.engine_mode == "bundled":
            self._init_db()

    def _usmc(self, agent_id: str):
        """Construct a USMC client bound to ``agent_id`` for write provenance."""
        return self._usmc_cls(db_path=self._usmc_db, agent_id=agent_id)

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

        if self.engine_mode == "canonical":
            key = f"{category}/{uuid.uuid4().hex[:12]}"
            self._usmc(agent_id).add_fact(_USMC_CATEGORY, key, content, confidence=confidence)
            return {
                "status": "stored",
                "engine": "canonical",
                "key": key,
                "category": category,
                "confidence": confidence,
                "agent_id": agent_id,
            }

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
            "engine": "bundled",
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

        if self.engine_mode == "canonical":
            return self._query_canonical(query, category, limit, agent_id)

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
                    "engine": "bundled",
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
            "engine": "bundled",
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

        if self.engine_mode == "canonical":
            return self._context_canonical(focus, agent_id, char_budget)

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
            "engine": "bundled",
            "focus": focus,
            "agent_id": agent_id,
            "context": "\n".join(parts),
            "entries": len(parts),
        }

    # ---- USMC (canonical) delegation helpers -------------------------------

    def _facts_to_memories(self, facts: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Map USMC fact rows back onto homebase's memory shape."""
        results: list[dict[str, Any]] = []
        for fact in facts:
            key = str(fact.get("key", ""))
            hb_category = key.split("/", 1)[0] if "/" in key else "fact"
            results.append(
                {
                    "content": fact.get("value", ""),
                    "category": hb_category,
                    "confidence": fact.get("confidence", 1.0),
                    "agent_id": fact.get("agent_id"),
                    "created_at": fact.get("updated_at"),
                }
            )
        return results

    def _query_canonical(self, query: str, category: str, limit: int, agent_id: Any) -> dict[str, Any]:
        facts = self._usmc(str(agent_id or "default")).get_facts(
            category=_USMC_CATEGORY, agent_id=agent_id
        )
        needle = query.lower()
        results: list[dict[str, Any]] = []
        for memory in self._facts_to_memories(facts):
            if category != "all" and memory["category"] != category:
                continue
            if needle and needle not in str(memory["content"]).lower():
                continue
            results.append(memory)
        results = results[:limit]
        return {
            "status": "ok",
            "engine": "canonical",
            "query": query,
            "mode": "client_filter",
            "agent_id": agent_id,
            "count": len(results),
            "results": results,
        }

    def _context_canonical(self, focus: Any, agent_id: Any, char_budget: int) -> dict[str, Any]:
        facts = self._usmc(str(agent_id or "default")).get_facts(
            category=_USMC_CATEGORY, agent_id=agent_id
        )
        memories = self._facts_to_memories(facts)
        memories.sort(key=lambda m: float(m.get("confidence") or 0.0), reverse=True)
        parts: list[str] = []
        used_chars = 0
        for memory in memories:
            if focus and str(focus).lower() not in str(memory["content"]).lower():
                continue
            conf = float(memory.get("confidence") or 0.0)
            line = f"- [{memory['agent_id']}:{memory['category']}:{conf:.2f}] {memory['content']}"
            if used_chars + len(line) > char_budget:
                break
            parts.append(line)
            used_chars += len(line)
        return {
            "status": "ok",
            "engine": "canonical",
            "focus": focus,
            "agent_id": agent_id,
            "context": "\n".join(parts),
            "entries": len(parts),
        }

    async def _merge(self, **kwargs) -> dict[str, Any]:
        if self.engine_mode == "canonical":
            return _canonical_bulk_unsupported("merge")

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
                    "engine": "bundled",
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
            "engine": "bundled",
            "agent_id": agent_id,
            "merged_groups": merged_groups,
            "removed_rows": removed_rows,
            "message": f"Merged {merged_groups} duplicate group(s); removed {removed_rows} redundant row(s).",
        }

    async def _consolidate(self, **kwargs) -> dict[str, Any]:
        if self.engine_mode == "canonical":
            return _canonical_bulk_unsupported("consolidate")

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
                    "engine": "bundled",
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
            "engine": "bundled",
            "agent_id": agent_id,
            "decay": decay,
            "min_confidence": min_confidence,
            "kept": survivors,
            "pruned": len(prune_ids),
            "message": f"Decayed confidence by {decay}; kept {survivors}, pruned {len(prune_ids)} below {min_confidence}.",
        }


def _canonical_bulk_unsupported(op: str) -> dict[str, Any]:
    return {
        "status": "not_supported",
        "engine": "canonical",
        "operation": op,
        "message": (
            f"hb_mem_{op} is a bundled-only bulk-hygiene operation. USMC applies "
            "confidence-merge per fact on write and has no bulk equivalent; run this "
            "in bundled mode. (TODO #72)"
        ),
    }


def create_module(config: dict[str, Any]) -> MemoryModule:
    return MemoryModule(config)
