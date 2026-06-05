"""hb_plug_ - Credential-free plugin discovery and dry-run registry."""

from __future__ import annotations

import json
from pathlib import Path
try:
    import tomllib
except ImportError:
    import tomli as tomllib
from typing import Any
from uuid import uuid4

from homebase.modules import ModuleBase, ToolDefinition
from homebase.storage import connect_db, utc_now


class PluginsModule(ModuleBase):
    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.db_path = config.get("db_path", "~/.homebase/plugins.db")
        self.plugins_dir = Path(str(config.get("plugins_dir", "~/.homebase/plugins"))).expanduser()
        self._init_db()
        self._sync_configured_plugins()
        self._discover_path(self.plugins_dir)

    def check_dependencies(self) -> tuple[bool, list[str]]:
        return True, []

    def _init_db(self) -> None:
        with connect_db(self.db_path) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS plugins (
                    name TEXT PRIMARY KEY,
                    path TEXT,
                    kind TEXT NOT NULL,
                    description TEXT,
                    metadata_json TEXT NOT NULL,
                    discovered_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS plugin_runs (
                    run_id TEXT PRIMARY KEY,
                    plugin TEXT NOT NULL,
                    args_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    result_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )

    def _sync_configured_plugins(self) -> None:
        raw = self.config.get("plugins", {})
        entries: list[dict[str, Any]] = []
        if isinstance(raw, dict):
            for name, value in raw.items():
                if isinstance(value, dict):
                    entries.append(
                        {
                            "name": str(name),
                            "path": value.get("path"),
                            "kind": str(value.get("kind", "configured")),
                            "description": value.get("description"),
                            "metadata": value,
                        }
                    )
                else:
                    entries.append(
                        {
                            "name": str(name),
                            "path": str(value),
                            "kind": "configured",
                            "description": None,
                            "metadata": {"path": str(value)},
                        }
                    )
        elif isinstance(raw, list):
            for item in raw:
                if isinstance(item, dict) and item.get("name"):
                    entries.append(
                        {
                            "name": str(item["name"]),
                            "path": item.get("path"),
                            "kind": str(item.get("kind", "configured")),
                            "description": item.get("description"),
                            "metadata": item,
                        }
                    )
        self._store_plugins(entries)

    def get_tools(self) -> list[ToolDefinition]:
        return [
            ToolDefinition(
                name="hb_plug_list",
                description="List discovered local plugins",
                input_schema={"type": "object", "properties": {}},
                handler=self._list,
            ),
            ToolDefinition(
                name="hb_plug_info",
                description="Get local plugin metadata",
                input_schema={
                    "type": "object",
                    "properties": {"plugin": {"type": "string"}},
                    "required": ["plugin"],
                },
                handler=self._info,
            ),
            ToolDefinition(
                name="hb_plug_run",
                description="Record a plugin dry-run without executing plugin code",
                input_schema={
                    "type": "object",
                    "properties": {
                        "plugin": {"type": "string"},
                        "args": {"type": "object"},
                    },
                    "required": ["plugin"],
                },
                handler=self._run,
            ),
            ToolDefinition(
                name="hb_plug_discover",
                description="Scan a local directory for plugin metadata",
                input_schema={"type": "object", "properties": {"path": {"type": "string"}}},
                handler=self._discover,
            ),
        ]

    async def _list(self, **kwargs) -> dict[str, Any]:
        with connect_db(self.db_path) as connection:
            rows = connection.execute(
                """
                SELECT name, path, kind, description, metadata_json, discovered_at
                FROM plugins
                ORDER BY name
                """
            ).fetchall()
        plugins = [_plugin_row(row) for row in rows]
        return {"status": "ok", "count": len(plugins), "plugins": plugins}

    async def _info(self, **kwargs) -> dict[str, Any]:
        plugin = str(kwargs["plugin"])
        with connect_db(self.db_path) as connection:
            row = _get_plugin(connection, plugin)
        if row is None:
            return {"status": "not_found", "plugin": plugin}
        return {"status": "ok", "plugin": _plugin_row(row)}

    async def _run(self, **kwargs) -> dict[str, Any]:
        plugin = str(kwargs["plugin"])
        args = kwargs.get("args") or {}
        if not isinstance(args, dict):
            args = {"value": args}
        with connect_db(self.db_path) as connection:
            row = _get_plugin(connection, plugin)
            if row is None:
                return {"status": "not_found", "plugin": plugin, "executed": False}
            run_id = f"plug-{uuid4().hex[:12]}"
            result = {
                "execution": "disabled",
                "delivery": "dry_run_recorded",
                "plugin": plugin,
                "message": "Plugin execution is disabled in the alpha adapter.",
            }
            connection.execute(
                """
                INSERT INTO plugin_runs (run_id, plugin, args_json, status, result_json, created_at)
                VALUES (?, ?, ?, 'dry_run_recorded', ?, ?)
                """,
                (
                    run_id,
                    plugin,
                    json.dumps(args, ensure_ascii=False),
                    json.dumps(result, ensure_ascii=False),
                    utc_now(),
                ),
            )
        return {"status": "dry_run_recorded", "run_id": run_id, "plugin": plugin, "executed": False, "result": result}

    async def _discover(self, **kwargs) -> dict[str, Any]:
        path = Path(str(kwargs.get("path") or self.plugins_dir)).expanduser()
        discovered = self._discover_path(path)
        return {"status": "ok", "path": str(path), "count": len(discovered), "plugins": discovered}

    def _discover_path(self, path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        candidates = [path] if path.is_dir() else []
        if path.is_dir():
            candidates.extend(child for child in sorted(path.iterdir()) if child.is_dir())
        discovered = [_read_plugin(candidate) for candidate in candidates]
        plugins = [plugin for plugin in discovered if plugin is not None]
        self._store_plugins(plugins)
        return plugins

    def _store_plugins(self, plugins: list[dict[str, Any]]) -> None:
        now = utc_now()
        with connect_db(self.db_path) as connection:
            for plugin in plugins:
                connection.execute(
                    """
                    INSERT INTO plugins (name, path, kind, description, metadata_json, discovered_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(name) DO UPDATE SET
                        path = excluded.path,
                        kind = excluded.kind,
                        description = excluded.description,
                        metadata_json = excluded.metadata_json,
                        discovered_at = excluded.discovered_at
                    """,
                    (
                        plugin["name"],
                        plugin.get("path"),
                        plugin.get("kind", "unknown"),
                        plugin.get("description"),
                        json.dumps(plugin.get("metadata", {}), ensure_ascii=False),
                        now,
                    ),
                )


def _read_plugin(path: Path) -> dict[str, Any] | None:
    for manifest in ("plugin.json", "package.json", "pyproject.toml", "SKILL.md"):
        manifest_path = path / manifest
        if not manifest_path.exists():
            continue
        try:
            if manifest == "plugin.json":
                data = json.loads(manifest_path.read_text(encoding="utf-8"))
                return _plugin_from_metadata(path, data, "plugin-json")
            if manifest == "package.json":
                data = json.loads(manifest_path.read_text(encoding="utf-8"))
                return _plugin_from_metadata(path, data, "node-package")
            if manifest == "pyproject.toml":
                data = tomllib.loads(manifest_path.read_text(encoding="utf-8"))
                project = data.get("project", {})
                return _plugin_from_metadata(path, project, "python-package")
            if manifest == "SKILL.md":
                text = manifest_path.read_text(encoding="utf-8")
                return {
                    "name": path.name,
                    "path": str(path),
                    "kind": "skill",
                    "description": _first_heading(text),
                    "metadata": {"manifest": str(manifest_path)},
                }
        except (OSError, json.JSONDecodeError, tomllib.TOMLDecodeError):
            continue
    return None


def _plugin_from_metadata(path: Path, metadata: dict[str, Any], kind: str) -> dict[str, Any] | None:
    name = str(metadata.get("name") or path.name).strip()
    if not name:
        return None
    return {
        "name": name,
        "path": str(path),
        "kind": str(metadata.get("kind", kind)),
        "description": metadata.get("description"),
        "metadata": metadata,
    }


def _first_heading(text: str) -> str | None:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip() or None
    return None


def _get_plugin(connection, plugin: str):
    return connection.execute(
        """
        SELECT name, path, kind, description, metadata_json, discovered_at
        FROM plugins
        WHERE name = ?
        """,
        (plugin,),
    ).fetchone()


def _plugin_row(row) -> dict[str, Any]:
    return {
        "name": row["name"],
        "path": row["path"],
        "kind": row["kind"],
        "description": row["description"],
        "metadata": json.loads(row["metadata_json"]),
        "discovered_at": row["discovered_at"],
    }


def create_module(config: dict[str, Any]) -> PluginsModule:
    return PluginsModule(config)
