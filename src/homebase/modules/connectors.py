"""hb_conn_ - Credential-free connector registry and local queues.

The alpha adapter does not send network messages. It keeps configured
connector profiles plus local inbox/outbox rows so clients can plan and audit
dispatches before real Telegram, Discord, or HomeAssistant backends are wired.
"""

from __future__ import annotations

from typing import Any

from homebase.modules import ModuleBase, ToolDefinition
from homebase.storage import connect_db, utc_now


class ConnectorsModule(ModuleBase):
    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.db_path = config.get("db_path", "~/.homebase/connectors.db")
        self._profiles = _connector_profiles(config)
        self._init_db()
        self._sync_profiles()

    def check_dependencies(self) -> tuple[bool, list[str]]:
        return True, []

    def _init_db(self) -> None:
        with connect_db(self.db_path) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS connectors (
                    name TEXT PRIMARY KEY,
                    kind TEXT NOT NULL,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    config_status TEXT NOT NULL,
                    target_hint TEXT,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS connector_outbox (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    connector TEXT NOT NULL,
                    target TEXT,
                    message TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS connector_inbox (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    connector TEXT NOT NULL,
                    source TEXT,
                    message TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )

    def _sync_profiles(self) -> None:
        now = utc_now()
        with connect_db(self.db_path) as connection:
            for profile in self._profiles:
                connection.execute(
                    """
                    INSERT INTO connectors (name, kind, enabled, config_status, target_hint, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(name) DO UPDATE SET
                        kind = excluded.kind,
                        enabled = excluded.enabled,
                        config_status = excluded.config_status,
                        target_hint = excluded.target_hint,
                        updated_at = excluded.updated_at
                    """,
                    (
                        profile["name"],
                        profile["kind"],
                        1 if profile["enabled"] else 0,
                        profile["config_status"],
                        profile.get("target_hint"),
                        now,
                    ),
                )

    def get_tools(self) -> list[ToolDefinition]:
        return [
            ToolDefinition(
                name="hb_conn_list",
                description="List configured connectors",
                input_schema={"type": "object", "properties": {}},
                handler=self._list,
            ),
            ToolDefinition(
                name="hb_conn_send",
                description="Queue a message for a connector without network delivery",
                input_schema={
                    "type": "object",
                    "properties": {
                        "connector": {"type": "string"},
                        "target": {"type": "string"},
                        "message": {"type": "string"},
                    },
                    "required": ["connector", "message"],
                },
                handler=self._send,
            ),
            ToolDefinition(
                name="hb_conn_receive",
                description="Get recent local inbox messages for a connector",
                input_schema={
                    "type": "object",
                    "properties": {
                        "connector": {"type": "string"},
                        "limit": {"type": "integer", "default": 10},
                    },
                    "required": ["connector"],
                },
                handler=self._receive,
            ),
            ToolDefinition(
                name="hb_conn_status",
                description="Check local connector health and queue counts",
                input_schema={
                    "type": "object",
                    "properties": {"connector": {"type": "string"}},
                    "required": ["connector"],
                },
                handler=self._status,
            ),
        ]

    async def _list(self, **kwargs) -> dict[str, Any]:
        with connect_db(self.db_path) as connection:
            rows = connection.execute(
                """
                SELECT name, kind, enabled, config_status, target_hint, updated_at
                FROM connectors
                ORDER BY name
                """
            ).fetchall()
            connectors = [_row_with_counts(connection, row) for row in rows]
        return {"status": "ok", "count": len(connectors), "connectors": connectors}

    async def _send(self, **kwargs) -> dict[str, Any]:
        connector = str(kwargs["connector"])
        message = str(kwargs["message"])
        target = kwargs.get("target")
        with connect_db(self.db_path) as connection:
            profile = _get_connector(connection, connector)
            if profile is None:
                return {
                    "status": "unknown_connector",
                    "connector": connector,
                    "available": _connector_names(connection),
                }
            if not bool(profile["enabled"]):
                return {"status": "disabled", "connector": connector, "sent": False}
            cursor = connection.execute(
                """
                INSERT INTO connector_outbox (connector, target, message, status, created_at)
                VALUES (?, ?, ?, 'queued_local_only', ?)
                """,
                (connector, target, message, utc_now()),
            )
            outbox_id = int(cursor.lastrowid)
        return {
            "status": "queued",
            "connector": connector,
            "outbox_id": outbox_id,
            "target": target,
            "sent": False,
            "delivery": "local_outbox_only",
        }

    async def _receive(self, **kwargs) -> dict[str, Any]:
        connector = str(kwargs["connector"])
        limit = max(1, min(100, int(kwargs.get("limit", 10))))
        with connect_db(self.db_path) as connection:
            if _get_connector(connection, connector) is None:
                return {
                    "status": "unknown_connector",
                    "connector": connector,
                    "available": _connector_names(connection),
                    "messages": [],
                    "count": 0,
                }
            rows = connection.execute(
                """
                SELECT id, connector, source, message, created_at
                FROM connector_inbox
                WHERE connector = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (connector, limit),
            ).fetchall()
        messages = [dict(row) for row in rows]
        return {"status": "ok", "connector": connector, "count": len(messages), "messages": messages}

    async def _status(self, **kwargs) -> dict[str, Any]:
        connector = str(kwargs["connector"])
        with connect_db(self.db_path) as connection:
            profile = _get_connector(connection, connector)
            if profile is None:
                return {
                    "status": "unknown_connector",
                    "connector": connector,
                    "available": _connector_names(connection),
                }
            return {"status": "ok", "connector": _row_with_counts(connection, profile)}


def _connector_profiles(config: dict[str, Any]) -> list[dict[str, Any]]:
    raw_connectors = config.get("connectors", ["local"])
    if isinstance(raw_connectors, str):
        names = [raw_connectors]
    elif isinstance(raw_connectors, list):
        names = [str(name) for name in raw_connectors if str(name).strip()]
    else:
        names = []

    profiles: dict[str, dict[str, Any]] = {}
    for name in names or ["local"]:
        normalized = str(name).strip()
        profiles[normalized] = {
            "name": normalized,
            "kind": normalized,
            "enabled": True,
            "config_status": "local_queue_only",
            "target_hint": "local-outbox",
        }

    profile_config = config.get("profiles")
    if isinstance(profile_config, dict):
        for name, values in profile_config.items():
            if not isinstance(values, dict):
                continue
            normalized = str(name).strip()
            profiles[normalized] = {
                "name": normalized,
                "kind": str(values.get("kind", normalized)),
                "enabled": bool(values.get("enabled", True)),
                "config_status": str(values.get("config_status", "local_queue_only")),
                "target_hint": values.get("target_hint"),
            }

    for name, token_key in (("telegram", "telegram_token"), ("discord", "discord_token")):
        if token_key in config and name not in profiles:
            profiles[name] = {
                "name": name,
                "kind": name,
                "enabled": True,
                "config_status": "credential_reference_send_disabled",
                "target_hint": None,
            }

    return sorted(profiles.values(), key=lambda item: item["name"])


def _get_connector(connection, connector: str):
    return connection.execute(
        """
        SELECT name, kind, enabled, config_status, target_hint, updated_at
        FROM connectors
        WHERE name = ?
        """,
        (connector,),
    ).fetchone()


def _connector_names(connection) -> list[str]:
    rows = connection.execute("SELECT name FROM connectors ORDER BY name").fetchall()
    return [str(row["name"]) for row in rows]


def _row_with_counts(connection, row) -> dict[str, Any]:
    connector = str(row["name"])
    outbox_pending = connection.execute(
        """
        SELECT COUNT(*) AS count
        FROM connector_outbox
        WHERE connector = ? AND status = 'queued_local_only'
        """,
        (connector,),
    ).fetchone()["count"]
    inbox_count = connection.execute(
        "SELECT COUNT(*) AS count FROM connector_inbox WHERE connector = ?",
        (connector,),
    ).fetchone()["count"]
    result = dict(row)
    result["enabled"] = bool(result["enabled"])
    result["outbox_pending"] = int(outbox_pending)
    result["inbox_count"] = int(inbox_count)
    return result


def create_module(config: dict[str, Any]) -> ConnectorsModule:
    return ConnectorsModule(config)
