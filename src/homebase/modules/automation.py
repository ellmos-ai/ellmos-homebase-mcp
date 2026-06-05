"""hb_auto_ - Credential-free automation chain planner.

The alpha adapter records chain definitions and local run plans. It never calls
LLMs, shells, or external automation systems unless a future backend is
explicitly configured and implemented.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from homebase.modules import ModuleBase, ToolDefinition
from homebase.storage import connect_db, utc_now


class AutomationModule(ModuleBase):
    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.db_path = config.get("db_path", "~/.homebase/automation.db")
        self.chains_dir = Path(str(config.get("chains_dir", "~/.homebase/chains"))).expanduser()
        self._init_db()
        self._sync_chains()

    def check_dependencies(self) -> tuple[bool, list[str]]:
        return True, []

    def _init_db(self) -> None:
        with connect_db(self.db_path) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS automation_chains (
                    name TEXT PRIMARY KEY,
                    description TEXT,
                    steps_json TEXT NOT NULL,
                    source TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS automation_runs (
                    run_id TEXT PRIMARY KEY,
                    chain TEXT NOT NULL,
                    input TEXT,
                    status TEXT NOT NULL,
                    result_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

    def _sync_chains(self) -> None:
        chains = _configured_chains(self.config) + _chains_from_dir(self.chains_dir)
        if not chains:
            chains = [
                {
                    "name": "local-dry-run",
                    "description": "Default local planning chain that records runs without execution.",
                    "steps": ["accept_input", "plan_steps", "record_local_run"],
                    "source": "builtin",
                }
            ]

        now = utc_now()
        with connect_db(self.db_path) as connection:
            for chain in chains:
                connection.execute(
                    """
                    INSERT INTO automation_chains (name, description, steps_json, source, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(name) DO UPDATE SET
                        description = excluded.description,
                        steps_json = excluded.steps_json,
                        source = excluded.source,
                        updated_at = excluded.updated_at
                    """,
                    (
                        chain["name"],
                        chain.get("description"),
                        json.dumps(chain.get("steps", []), ensure_ascii=False),
                        chain.get("source", "config"),
                        now,
                    ),
                )

    def get_tools(self) -> list[ToolDefinition]:
        return [
            ToolDefinition(
                name="hb_auto_list_chains",
                description="List available local automation chain definitions",
                input_schema={"type": "object", "properties": {}},
                handler=self._list,
            ),
            ToolDefinition(
                name="hb_auto_run",
                description="Queue a local automation chain plan without executing external backends",
                input_schema={
                    "type": "object",
                    "properties": {
                        "chain": {"type": "string"},
                        "input": {"type": "string"},
                    },
                    "required": ["chain"],
                },
                handler=self._run,
            ),
            ToolDefinition(
                name="hb_auto_status",
                description="Check local automation run status",
                input_schema={
                    "type": "object",
                    "properties": {"run_id": {"type": "string"}},
                    "required": ["run_id"],
                },
                handler=self._status,
            ),
            ToolDefinition(
                name="hb_auto_result",
                description="Get the recorded local automation run result",
                input_schema={
                    "type": "object",
                    "properties": {"run_id": {"type": "string"}},
                    "required": ["run_id"],
                },
                handler=self._result,
            ),
        ]

    async def _list(self, **kwargs) -> dict[str, Any]:
        with connect_db(self.db_path) as connection:
            rows = connection.execute(
                """
                SELECT name, description, steps_json, source, updated_at
                FROM automation_chains
                ORDER BY name
                """
            ).fetchall()
        chains = [_chain_row(row) for row in rows]
        return {"status": "ok", "count": len(chains), "chains": chains}

    async def _run(self, **kwargs) -> dict[str, Any]:
        chain = str(kwargs["chain"])
        chain_input = kwargs.get("input")
        with connect_db(self.db_path) as connection:
            chain_row = _get_chain(connection, chain)
            if chain_row is None:
                return {
                    "status": "unknown_chain",
                    "chain": chain,
                    "available": _chain_names(connection),
                }
            run_id = f"auto-{uuid4().hex[:12]}"
            chain_info = _chain_row(chain_row)
            result = {
                "execution": "disabled",
                "delivery": "local_plan_only",
                "chain": chain,
                "planned_steps": chain_info["steps"],
                "message": "Automation backends are disabled in the alpha adapter.",
            }
            now = utc_now()
            connection.execute(
                """
                INSERT INTO automation_runs (run_id, chain, input, status, result_json, created_at, updated_at)
                VALUES (?, ?, ?, 'queued_local_only', ?, ?, ?)
                """,
                (run_id, chain, chain_input, json.dumps(result, ensure_ascii=False), now, now),
            )
        return {"status": "queued", "run_id": run_id, "chain": chain, "executed": False, "result": result}

    async def _status(self, **kwargs) -> dict[str, Any]:
        run_id = str(kwargs["run_id"])
        with connect_db(self.db_path) as connection:
            row = _get_run(connection, run_id)
        if row is None:
            return {"status": "not_found", "run_id": run_id}
        run = _run_row(row)
        return {"status": "ok", "run": run}

    async def _result(self, **kwargs) -> dict[str, Any]:
        run_id = str(kwargs["run_id"])
        with connect_db(self.db_path) as connection:
            row = _get_run(connection, run_id)
        if row is None:
            return {"status": "not_found", "run_id": run_id}
        run = _run_row(row)
        return {"status": "ok", "run_id": run_id, "result": run["result"]}


def _configured_chains(config: dict[str, Any]) -> list[dict[str, Any]]:
    raw = config.get("chains", [])
    chains: list[dict[str, Any]] = []
    if isinstance(raw, dict):
        for name, value in raw.items():
            if isinstance(value, dict):
                chains.append(
                    {
                        "name": str(name),
                        "description": value.get("description"),
                        "steps": _steps(value.get("steps")),
                        "source": "config",
                    }
                )
            else:
                chains.append({"name": str(name), "description": str(value), "steps": [], "source": "config"})
    elif isinstance(raw, list):
        for item in raw:
            if isinstance(item, dict):
                name = str(item.get("name", "")).strip()
                if name:
                    chains.append(
                        {
                            "name": name,
                            "description": item.get("description"),
                            "steps": _steps(item.get("steps")),
                            "source": "config",
                        }
                    )
            elif str(item).strip():
                chains.append({"name": str(item).strip(), "description": None, "steps": [], "source": "config"})
    return chains


def _chains_from_dir(chains_dir: Path) -> list[dict[str, Any]]:
    if not chains_dir.exists() or not chains_dir.is_dir():
        return []
    chains: list[dict[str, Any]] = []
    for path in sorted(chains_dir.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        name = str(data.get("name") or path.stem).strip()
        if not name:
            continue
        chains.append(
            {
                "name": name,
                "description": data.get("description"),
                "steps": _steps(data.get("steps")),
                "source": str(path),
            }
        )
    return chains


def _steps(raw: Any) -> list[str]:
    if isinstance(raw, list):
        return [str(step) for step in raw]
    if isinstance(raw, str):
        return [raw]
    return []


def _get_chain(connection, chain: str):
    return connection.execute(
        """
        SELECT name, description, steps_json, source, updated_at
        FROM automation_chains
        WHERE name = ?
        """,
        (chain,),
    ).fetchone()


def _chain_names(connection) -> list[str]:
    rows = connection.execute("SELECT name FROM automation_chains ORDER BY name").fetchall()
    return [str(row["name"]) for row in rows]


def _get_run(connection, run_id: str):
    return connection.execute(
        """
        SELECT run_id, chain, input, status, result_json, created_at, updated_at
        FROM automation_runs
        WHERE run_id = ?
        """,
        (run_id,),
    ).fetchone()


def _chain_row(row) -> dict[str, Any]:
    return {
        "name": row["name"],
        "description": row["description"],
        "steps": json.loads(row["steps_json"]),
        "source": row["source"],
        "updated_at": row["updated_at"],
    }


def _run_row(row) -> dict[str, Any]:
    return {
        "run_id": row["run_id"],
        "chain": row["chain"],
        "input": row["input"],
        "status": row["status"],
        "result": json.loads(row["result_json"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def create_module(config: dict[str, Any]) -> AutomationModule:
    return AutomationModule(config)
