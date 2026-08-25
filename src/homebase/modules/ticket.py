"""hb_ticket_ - Read-only seam onto the real `_control-center/_TICKETS` tree.

T-20260825-196589547 (1): v1 scope is READ ONLY (list/show per lifecycle
category) -- no move, no write, no claim. Like hb_policy_*/hb_lock_*, this
namespace has NO bundled fallback: an empty local ticket store would look
like a real answer about live ticket state while actually being nothing.
Fails closed if either ticket-master itself (presence/capability signal)
or the `_TICKETS` folder (the actual read target) cannot be resolved.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

from homebase import engines as engine_seams
from homebase.modules import ModuleBase, ToolDefinition

logger = logging.getLogger("homebase.ticket")

_LIFECYCLE_CATEGORIES = (
    "INBOX", "ACTIONABLE", "QUEUED", "BLOCKED", "WAITING", "USER", "PARKED", "SOLVED",
)
_HEADER_FIELD_RE = re.compile(r"^([A-ZÄÖÜ][A-Za-zÄÖÜäöü0-9_-]*):\s*(.*)$")
_TICKET_ID_RE = re.compile(r"^(T-\d{8}-\d+)")


def _parse_header(text: str) -> dict[str, str]:
    """Extract the flat `FELD: wert` header lines from a ticket file (ID,
    TITEL, ERSTELLT, STATUS, PRIORITAET, ...). Stops at the first section
    divider so VERLAUF/LOESUNG free text is never included -- this is a
    metadata listing, not a content dump."""
    fields: dict[str, str] = {}
    for line in text.splitlines():
        if line.startswith("---") or line.startswith("==="):
            if fields:
                break
            continue
        match = _HEADER_FIELD_RE.match(line)
        if match:
            fields[match.group(1)] = match.group(2).strip()
    return fields


class TicketModule(ModuleBase):
    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self._audit_mod = engine_seams.load_ticket_master(config.get("_engine_path"))
        self._tickets_root: Path | None = None
        self._unavailable: str | None = None
        if self._audit_mod is None:
            self._unavailable = engine_seams.unavailable_message(
                tool_family="hb_ticket_*",
                engine="ticket-master",
                module="ticket",
                configured_path=config.get("_engine_path"),
            )
        else:
            self._tickets_root = engine_seams.resolve_tickets_root(config.get("_tickets_root"))
            if self._tickets_root is None:
                self._unavailable = (
                    "hb_ticket_*: ticket-master is present, but the `_TICKETS` folder "
                    "could not be found (checked HOMEBASE_TICKETS_ROOT, [ticket].tickets_root, "
                    "the OneDrive env var, and the default path). Set one of these to the "
                    "real `_control-center/_TICKETS` directory."
                )
        if self._unavailable is not None:
            logger.error(self._unavailable)

    def _require_root(self) -> Path:
        if self._unavailable is not None:
            raise engine_seams.CanonicalEngineUnavailable(self._unavailable)
        assert self._tickets_root is not None
        return self._tickets_root

    def get_tools(self) -> list[ToolDefinition]:
        return [
            ToolDefinition(
                name="hb_ticket_list",
                description=(
                    "List tickets in one lifecycle category (INBOX/ACTIONABLE/QUEUED/"
                    "BLOCKED/WAITING/USER/PARKED/SOLVED) -- header fields only, read-only."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "category": {"type": "string", "enum": list(_LIFECYCLE_CATEGORIES)},
                        "limit": {"type": "integer", "default": 50},
                    },
                    "required": ["category"],
                },
                handler=self._list,
            ),
            ToolDefinition(
                name="hb_ticket_show",
                description="Show one ticket's header fields by ID (e.g. T-20260825-196589547), read-only.",
                input_schema={
                    "type": "object",
                    "properties": {"ticket_id": {"type": "string"}},
                    "required": ["ticket_id"],
                },
                handler=self._show,
            ),
        ]

    async def _list(self, **kwargs) -> dict[str, Any]:
        root = self._require_root()
        category = kwargs["category"]
        if category not in _LIFECYCLE_CATEGORIES:
            return {"engine": "canonical", "status": "invalid_category", "known": list(_LIFECYCLE_CATEGORIES)}
        limit = int(kwargs.get("limit", 50))
        folder = root / category
        if not folder.is_dir():
            return {"engine": "canonical", "category": category, "tickets": [], "count": 0}
        entries = []
        for path in sorted(folder.glob("T-*.txt"))[:limit]:
            try:
                fields = _parse_header(path.read_text(encoding="utf-8"))
            except OSError as exc:
                logger.info("Could not read ticket file %s: %s", path, exc)
                continue
            entries.append({
                "id": fields.get("ID", path.stem),
                "titel": fields.get("TITEL"),
                "status": fields.get("STATUS"),
                "prioritaet": fields.get("PRIORITAET"),
                "file": path.name,
            })
        return {"engine": "canonical", "category": category, "tickets": entries, "count": len(entries)}

    async def _show(self, **kwargs) -> dict[str, Any]:
        root = self._require_root()
        ticket_id = kwargs["ticket_id"]
        if not _TICKET_ID_RE.match(ticket_id):
            return {"engine": "canonical", "status": "invalid_id"}
        matches = []
        for category in _LIFECYCLE_CATEGORIES:
            folder = root / category
            if not folder.is_dir():
                continue
            for path in folder.glob(f"{ticket_id}*.txt"):
                matches.append((category, path))
        if not matches:
            return {"engine": "canonical", "status": "not_found", "ticket_id": ticket_id}
        category, path = matches[0]
        fields = _parse_header(path.read_text(encoding="utf-8"))
        return {
            "engine": "canonical",
            "status": "found",
            "category": category,
            "file": path.name,
            "header": fields,
            "collision": len(matches) > 1,
        }


def create_module(config: dict[str, Any]) -> TicketModule:
    return TicketModule(config)
