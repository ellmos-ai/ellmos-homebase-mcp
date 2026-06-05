"""hb_api_ - Passive API discovery and exploration."""

from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from homebase.modules import ModuleBase, ToolDefinition
from homebase.storage import connect_db, utc_now


OPENAPI_PATHS = ("openapi.json", "swagger.json", "api/openapi.json", "api/swagger.json")
WORDLIST_PATHS = ("health", "api", "version", "status")


class ApiModule(ModuleBase):
    """Credential-free HTTP probing with SQLite-backed history."""

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.db_path = config.get("db_path", "~/.homebase/probes.db")
        self.timeout = float(config.get("timeout", 10))
        self._init_db()

    def _init_db(self) -> None:
        with connect_db(self.db_path) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS api_probes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT NOT NULL,
                    strategies TEXT NOT NULL,
                    result_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )

    def get_tools(self) -> list[ToolDefinition]:
        return [
            ToolDefinition(
                name="hb_api_probe",
                description="Probe a URL using all strategies (OpenAPI, wordlist, pattern, HATEOAS)",
                input_schema={
                    "type": "object",
                    "properties": {
                        "url": {"type": "string"},
                        "strategies": {
                            "type": "array",
                            "items": {"type": "string"},
                            "default": ["openapi", "wordlist", "pattern", "hateoas"],
                        },
                    },
                    "required": ["url"],
                },
                handler=self._probe,
            ),
            ToolDefinition(
                name="hb_api_discover",
                description="Auto-detect API schema from a base URL",
                input_schema={"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]},
                handler=self._discover,
            ),
            ToolDefinition(
                name="hb_api_export",
                description="Export probe results as Markdown or JSON",
                input_schema={
                    "type": "object",
                    "properties": {"probe_id": {"type": "integer"}, "format": {"type": "string", "enum": ["markdown", "json"]}},
                    "required": ["probe_id"],
                },
                handler=self._export,
            ),
            ToolDefinition(
                name="hb_api_history",
                description="List previous probe results",
                input_schema={"type": "object", "properties": {"limit": {"type": "integer", "default": 20}}},
                handler=self._history,
            ),
        ]

    async def _probe(self, **kwargs) -> dict[str, Any]:
        url = str(kwargs["url"])
        strategies = kwargs.get("strategies") or ["openapi", "wordlist", "pattern", "hateoas"]
        strategies = [str(strategy).lower() for strategy in strategies]
        result: dict[str, Any] = {
            "status": "ok",
            "url": url,
            "strategies": strategies,
            "openapi": [],
            "wordlist": [],
            "patterns": _url_patterns(url) if "pattern" in strategies else {},
            "links": [],
        }

        if "openapi" in strategies:
            result["openapi"] = [_probe_json(urljoin(_base_url(url), path), self.timeout) for path in OPENAPI_PATHS]
        if "wordlist" in strategies:
            result["wordlist"] = [_probe_headish(urljoin(_base_url(url), path), self.timeout) for path in WORDLIST_PATHS]
        if "hateoas" in strategies:
            base_doc = _probe_json(url, self.timeout)
            result["links"] = _extract_links(base_doc.get("json"))
            result["base"] = base_doc

        probe_id = self._store_probe(url, strategies, result)
        result["probe_id"] = probe_id
        return result

    async def _discover(self, **kwargs) -> dict[str, Any]:
        probe = await self._probe(url=kwargs["url"], strategies=["openapi", "pattern"])
        candidates = [
            item for item in probe["openapi"]
            if item.get("ok") and item.get("is_openapi")
        ]
        return {
            "status": "found" if candidates else "not_found",
            "url": kwargs["url"],
            "probe_id": probe["probe_id"],
            "schemas": candidates,
            "patterns": probe["patterns"],
        }

    async def _export(self, **kwargs) -> dict[str, Any]:
        probe_id = int(kwargs["probe_id"])
        output_format = str(kwargs.get("format", "markdown"))
        entry = self._get_probe(probe_id)
        if entry is None:
            return {"status": "not_found", "probe_id": probe_id}
        if output_format == "json":
            return {"status": "ok", "probe_id": probe_id, "format": "json", "content": entry["result"]}
        return {
            "status": "ok",
            "probe_id": probe_id,
            "format": "markdown",
            "content": _markdown_export(entry),
        }

    async def _history(self, **kwargs) -> dict[str, Any]:
        limit = int(kwargs.get("limit", 20))
        with connect_db(self.db_path) as connection:
            rows = connection.execute(
                """
                SELECT id, url, strategies, created_at
                FROM api_probes
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return {"status": "ok", "count": len(rows), "results": [dict(row) for row in rows]}

    def _store_probe(self, url: str, strategies: list[str], result: dict[str, Any]) -> int:
        with connect_db(self.db_path) as connection:
            cursor = connection.execute(
                """
                INSERT INTO api_probes (url, strategies, result_json, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (url, json.dumps(strategies), json.dumps(result, ensure_ascii=False), utc_now()),
            )
            return int(cursor.lastrowid)

    def _get_probe(self, probe_id: int) -> dict[str, Any] | None:
        with connect_db(self.db_path) as connection:
            row = connection.execute(
                "SELECT id, url, strategies, result_json, created_at FROM api_probes WHERE id = ?",
                (probe_id,),
            ).fetchone()
        if row is None:
            return None
        entry = dict(row)
        entry["strategies"] = json.loads(entry["strategies"])
        entry["result"] = json.loads(entry.pop("result_json"))
        return entry


def _base_url(url: str) -> str:
    return url if url.endswith("/") else f"{url}/"


def _probe_json(url: str, timeout: float) -> dict[str, Any]:
    response = _http_get(url, timeout)
    content_type = response.get("content_type") or ""
    body = response.get("body") or ""
    parsed = None
    if response.get("ok") and ("json" in content_type or body.strip().startswith(("{", "["))):
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError:
            parsed = None
    return {
        "url": url,
        "ok": bool(response.get("ok")),
        "status_code": response.get("status_code"),
        "content_type": content_type,
        "json": parsed,
        "is_openapi": _is_openapi(parsed),
        "error": response.get("error"),
    }


def _probe_headish(url: str, timeout: float) -> dict[str, Any]:
    response = _http_get(url, timeout, max_bytes=256)
    return {
        "url": url,
        "ok": bool(response.get("ok")),
        "status_code": response.get("status_code"),
        "content_type": response.get("content_type"),
        "error": response.get("error"),
    }


def _http_get(url: str, timeout: float, max_bytes: int = 1024 * 1024) -> dict[str, Any]:
    request = Request(url, method="GET", headers={"User-Agent": "ellmos-homebase-api-prober/0.1"})
    try:
        with urlopen(request, timeout=timeout) as response:
            body = response.read(max_bytes).decode("utf-8", errors="replace")
            return {
                "ok": 200 <= int(response.status) < 400,
                "status_code": int(response.status),
                "content_type": response.headers.get("content-type", ""),
                "body": body,
                "error": None,
            }
    except HTTPError as exc:
        return {"ok": False, "status_code": int(exc.code), "content_type": "", "body": "", "error": str(exc)}
    except (URLError, TimeoutError, OSError) as exc:
        return {"ok": False, "status_code": None, "content_type": "", "body": "", "error": str(exc)}


def _is_openapi(value: Any) -> bool:
    return isinstance(value, dict) and ("openapi" in value or "swagger" in value or "paths" in value)


def _extract_links(value: Any) -> list[str]:
    links: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if key in {"href", "url", "link"} and isinstance(item, str):
                links.append(item)
            else:
                links.extend(_extract_links(item))
    elif isinstance(value, list):
        for item in value:
            links.extend(_extract_links(item))
    return sorted(set(links))


def _url_patterns(url: str) -> dict[str, Any]:
    base = _base_url(url)
    return {
        "base_url": base,
        "openapi_candidates": [urljoin(base, path) for path in OPENAPI_PATHS],
        "common_endpoint_candidates": [urljoin(base, path) for path in WORDLIST_PATHS],
    }


def _markdown_export(entry: dict[str, Any]) -> str:
    result = entry["result"]
    lines = [
        f"# API Probe {entry['id']}",
        "",
        f"- URL: `{entry['url']}`",
        f"- Created: `{entry['created_at']}`",
        f"- Strategies: `{', '.join(entry['strategies'])}`",
        "",
        "## OpenAPI Candidates",
    ]
    for candidate in result.get("openapi", []):
        marker = "yes" if candidate.get("is_openapi") else "no"
        lines.append(f"- `{candidate['url']}` status={candidate.get('status_code')} openapi={marker}")
    if result.get("links"):
        lines.extend(["", "## Links"])
        lines.extend(f"- `{link}`" for link in result["links"])
    return "\n".join(lines)


def create_module(config: dict[str, Any]) -> ApiModule:
    return ApiModule(config)
