"""hb_lock_ - Read-only seam onto the real lock-master engine.

T-20260825-196589547 (1): v1 scope is READ ONLY (check/list) -- locks are
NOT set through this namespace. Like hb_policy_*/hb_ticket_*, no bundled
fallback exists: a homebase-local "lock store" would be a second,
unconnected truth about who holds a lock, which is exactly the failure mode
MODE-CONTRACT.md exists to prevent for the other seams -- here there is no
seam to silently degrade to, so unavailability fails closed directly.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from homebase import engines as engine_seams
from homebase.modules import ModuleBase, ToolDefinition

logger = logging.getLogger("homebase.lock")


def _default_roots_file() -> Path | None:
    import os

    one_drive = os.environ.get("OneDrive") or os.environ.get("ONEDRIVE")
    candidates = []
    if one_drive:
        candidates.append(Path(one_drive) / "_scripts" / "lock_roots.json")
    candidates.append(Path("~/OneDrive/_scripts/lock_roots.json").expanduser())
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


class LockModule(ModuleBase):
    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self._scan_mod, self._status_mod = engine_seams.load_lock_master(config.get("_engine_path"))
        self._roots_file: Path | None = None
        self._unavailable: str | None = None
        if self._scan_mod is None:
            self._unavailable = engine_seams.unavailable_message(
                tool_family="hb_lock_*",
                engine="lock-master",
                module="lock",
                configured_path=config.get("_engine_path"),
            )
        else:
            roots_override = config.get("_lock_roots_file")
            self._roots_file = Path(roots_override) if roots_override else _default_roots_file()
            if self._roots_file is None or not self._roots_file.is_file():
                self._unavailable = (
                    "hb_lock_*: lock-master is present, but the roots file "
                    "(`_scripts/lock_roots.json`) could not be found. Set "
                    "[lock].lock_roots_file to its real path."
                )
        if self._unavailable is not None:
            logger.error(self._unavailable)

    def _require_engine(self):
        if self._unavailable is not None:
            raise engine_seams.CanonicalEngineUnavailable(self._unavailable)
        assert self._roots_file is not None
        return self._scan_mod.load_config(self._roots_file)

    def get_tools(self) -> list[ToolDefinition]:
        return [
            ToolDefinition(
                name="hb_lock_list",
                description="List all currently active locks across configured roots (read-only).",
                input_schema={"type": "object", "properties": {}},
                handler=self._list,
            ),
            ToolDefinition(
                name="hb_lock_check",
                description=(
                    "Check whether a project directory currently has an active lock "
                    "-- call this BEFORE any write action there (read-only)."
                ),
                input_schema={
                    "type": "object",
                    "properties": {"project_dir": {"type": "string"}},
                    "required": ["project_dir"],
                },
                handler=self._check,
            ),
        ]

    async def _list(self, **kwargs) -> dict[str, Any]:
        config = self._require_engine()
        locks = self._scan_mod.collect_locks(config)
        return {"engine": "canonical", "locks": locks, "count": len(locks)}

    async def _check(self, **kwargs) -> dict[str, Any]:
        self._require_engine()  # fail closed on the same terms as _list
        if self._status_mod is None:
            return {
                "engine": "canonical",
                "status": "status_module_unavailable",
                "note": "lock_status module not resolvable; use hb_lock_list and filter by path instead.",
            }
        project_dir = Path(kwargs["project_dir"]).expanduser()
        entries = self._status_mod.check_project_status(project_dir)
        return {
            "engine": "canonical",
            "project_dir": str(project_dir),
            "locked": len(entries) > 0,
            "locks": entries,
        }


def create_module(config: dict[str, Any]) -> LockModule:
    return LockModule(config)
