"""hb_state_ - Persistent state."""

from __future__ import annotations

from typing import Any

from homebase.modules import ModuleBase, ToolDefinition
from homebase.storage import connect_db, contains_term, ensure_column, resolve_agent_id, utc_now


class StateModule(ModuleBase):
    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.db_path = config.get("db_path", "~/.homebase/rinnsal.db")
        self._init_db()

    def _init_db(self) -> None:
        with connect_db(self.db_path) as connection:
            _ensure_state_memory_table(connection)
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    description TEXT,
                    priority TEXT NOT NULL DEFAULT 'medium',
                    status TEXT NOT NULL DEFAULT 'open',
                    agent_id TEXT NOT NULL DEFAULT 'unknown',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            ensure_column(connection, "tasks", "agent_id", "TEXT NOT NULL DEFAULT 'unknown'")

    def get_tools(self) -> list[ToolDefinition]:
        return [
            ToolDefinition(
                name="hb_state_mem_get",
                description="Get state memory entries",
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "type": {"type": "string", "enum": ["fact", "lesson", "all"]},
                        "agent_id": {"type": "string", "description": "Optional agent filter"},
                    },
                },
                handler=self._mem_get,
            ),
            ToolDefinition(
                name="hb_state_mem_set",
                description="Store a state memory entry",
                input_schema={
                    "type": "object",
                    "properties": {
                        "key": {"type": "string"},
                        "value": {"type": "string"},
                        "type": {"type": "string", "enum": ["fact", "lesson"]},
                        "agent_id": {
                            "type": "string",
                            "description": "Agent identifier for state-memory provenance",
                        },
                    },
                    "required": ["key", "value"],
                },
                handler=self._mem_set,
            ),
            ToolDefinition(
                name="hb_state_task_list",
                description="List tasks with optional status filter",
                input_schema={
                    "type": "object",
                    "properties": {
                        "status": {"type": "string", "enum": ["open", "in_progress", "done", "all"]},
                        "agent_id": {"type": "string", "description": "Optional agent filter"},
                    },
                },
                handler=self._task_list,
            ),
            ToolDefinition(
                name="hb_state_task_create",
                description="Create a new task",
                input_schema={
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "description": {"type": "string"},
                        "priority": {"type": "string", "enum": ["low", "medium", "high"]},
                        "agent_id": {"type": "string", "description": "Agent identifier for task provenance"},
                    },
                    "required": ["title"],
                },
                handler=self._task_create,
            ),
            ToolDefinition(
                name="hb_state_task_update",
                description="Update a task (status, description, priority)",
                input_schema={
                    "type": "object",
                    "properties": {
                        "task_id": {"type": "integer"},
                        "status": {"type": "string", "enum": ["open", "in_progress", "done"]},
                        "description": {"type": "string"},
                        "priority": {"type": "string", "enum": ["low", "medium", "high"]},
                        "agent_id": {"type": "string", "description": "Optional agent filter"},
                    },
                    "required": ["task_id"],
                },
                handler=self._task_update,
            ),
            ToolDefinition(
                name="hb_state_dispatch",
                description="Return connector-dispatch status",
                input_schema={
                    "type": "object",
                    "properties": {
                        "connector": {"type": "string", "description": "Connector name"},
                        "message": {"type": "string"},
                        "target": {"type": "string", "description": "Channel/chat ID"},
                    },
                    "required": ["connector", "message"],
                },
                handler=self._dispatch,
            ),
        ]

    async def _mem_get(self, **kwargs) -> dict[str, Any]:
        query = kwargs.get("query")
        memory_type = str(kwargs.get("type", "all"))
        agent_id = kwargs.get("agent_id")
        sql = "SELECT id, key, value, type, agent_id, updated_at FROM state_memory WHERE 1 = 1"
        params: list[Any] = []
        if query:
            sql += " AND (key LIKE ? OR value LIKE ?)"
            params.extend([contains_term(str(query)), contains_term(str(query))])
        if memory_type != "all":
            sql += " AND type = ?"
            params.append(memory_type)
        if agent_id:
            sql += " AND agent_id = ?"
            params.append(str(agent_id))
        sql += " ORDER BY updated_at DESC"

        with connect_db(self.db_path) as connection:
            rows = connection.execute(sql, params).fetchall()
        return {"status": "ok", "count": len(rows), "results": [dict(row) for row in rows]}

    async def _mem_set(self, **kwargs) -> dict[str, Any]:
        key = str(kwargs["key"])
        memory_type = str(kwargs.get("type", "fact"))
        agent_id = resolve_agent_id(self.config, kwargs.get("agent_id"))
        with connect_db(self.db_path) as connection:
            connection.execute(
                """
                INSERT INTO state_memory (key, value, type, agent_id, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(agent_id, key) DO UPDATE SET
                    value = excluded.value,
                    type = excluded.type,
                    agent_id = excluded.agent_id,
                    updated_at = excluded.updated_at
                """,
                (key, str(kwargs["value"]), memory_type, agent_id, utc_now()),
            )
        return {"status": "stored", "key": key, "type": memory_type, "agent_id": agent_id}

    async def _task_list(self, **kwargs) -> dict[str, Any]:
        status = str(kwargs.get("status", "open"))
        agent_id = kwargs.get("agent_id")
        sql = "SELECT id, title, description, priority, status, agent_id, created_at, updated_at FROM tasks"
        params: list[Any] = []
        if status != "all":
            sql += " WHERE status = ?"
            params.append(status)
        if agent_id:
            sql += " AND agent_id = ?" if " WHERE " in sql else " WHERE agent_id = ?"
            params.append(str(agent_id))
        sql += " ORDER BY id DESC"

        with connect_db(self.db_path) as connection:
            rows = connection.execute(sql, params).fetchall()
        return {"status": "ok", "count": len(rows), "tasks": [dict(row) for row in rows]}

    async def _task_create(self, **kwargs) -> dict[str, Any]:
        now = utc_now()
        agent_id = resolve_agent_id(self.config, kwargs.get("agent_id"))
        with connect_db(self.db_path) as connection:
            cursor = connection.execute(
                """
                INSERT INTO tasks (title, description, priority, status, agent_id, created_at, updated_at)
                VALUES (?, ?, ?, 'open', ?, ?, ?)
                """,
                (
                    str(kwargs["title"]),
                    kwargs.get("description"),
                    str(kwargs.get("priority", "medium")),
                    agent_id,
                    now,
                    now,
                ),
            )
            task_id = int(cursor.lastrowid)
        return {"status": "created", "task_id": task_id, "agent_id": agent_id}

    async def _task_update(self, **kwargs) -> dict[str, Any]:
        task_id = int(kwargs["task_id"])
        updates = []
        params: list[Any] = []
        for key in ("status", "description", "priority"):
            if key in kwargs:
                updates.append(f"{key} = ?")
                params.append(kwargs[key])
        if not updates:
            return {"status": "unchanged", "task_id": task_id}
        updates.append("updated_at = ?")
        params.append(utc_now())
        params.append(task_id)
        agent_id = kwargs.get("agent_id")
        where = "id = ?"
        if agent_id:
            where += " AND agent_id = ?"
            params.append(str(agent_id))

        with connect_db(self.db_path) as connection:
            cursor = connection.execute(f"UPDATE tasks SET {', '.join(updates)} WHERE {where}", params)
        return {"status": "updated" if cursor.rowcount else "not_found", "task_id": task_id, "agent_id": agent_id}

    async def _dispatch(self, **kwargs) -> dict[str, Any]:
        return {
            "status": "not_implemented",
            "connector": kwargs.get("connector"),
            "message": "Connector dispatch is intentionally disabled until connectors are configured.",
        }


def create_module(config: dict[str, Any]) -> StateModule:
    return StateModule(config)


def _ensure_state_memory_table(connection) -> None:
    rows = connection.execute("PRAGMA table_info(state_memory)").fetchall()
    columns = {row["name"] for row in rows}
    if not columns:
        _create_state_memory_table(connection)
        return
    if {"id", "agent_id"}.issubset(columns):
        connection.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_state_memory_agent_key ON state_memory(agent_id, key)"
        )
        return

    legacy_agent_expr = "COALESCE(agent_id, 'unknown')" if "agent_id" in columns else "'unknown'"
    connection.execute("ALTER TABLE state_memory RENAME TO state_memory_legacy")
    _create_state_memory_table(connection)
    connection.execute(
        f"""
        INSERT OR IGNORE INTO state_memory (key, value, type, agent_id, updated_at)
        SELECT key, value, type, {legacy_agent_expr}, updated_at
        FROM state_memory_legacy
        """
    )
    connection.execute("DROP TABLE state_memory_legacy")


def _create_state_memory_table(connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS state_memory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT NOT NULL,
            value TEXT NOT NULL,
            type TEXT NOT NULL DEFAULT 'fact',
            agent_id TEXT NOT NULL DEFAULT 'unknown',
            updated_at TEXT NOT NULL,
            UNIQUE(agent_id, key)
        )
        """
    )
