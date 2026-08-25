"""hb_policy_ - Read-only seam onto the real policy-registry engine.

T-20260825-196589547 (1): unlike hb_garden_*/hb_mem_*/hb_state_task_*, this
namespace has NO bundled fallback store at all -- not "bundled disabled by
config", but structurally absent. A homebase-local empty copy of policy
metadata would not be a smaller-but-honest substitute (the way hb_kb_*/
hb_route_* are for KnowledgeDigest/clutch); it would look like a real
answer about live governance state while actually being empty or stale.
Giving a clearly failed-closed error is safer than a confidently wrong one.
Consequently every tool here is canonical-only: if the real policy-registry
engine cannot be resolved, the tool fails closed regardless of configured
mode (there is no "bundled" mode to fall back to for this namespace).

v1 scope (User-Auftrag): read-only tools only (resolve/list). The fresh
Registry.register_rule() append-only mechanism (D2-R2 Stufe 1) is
deliberately NOT exposed here yet -- no operational need established.
"""

from __future__ import annotations

import logging
from typing import Any

from homebase import engines as engine_seams
from homebase.modules import ModuleBase, ToolDefinition

logger = logging.getLogger("homebase.policy")


class PolicyModule(ModuleBase):
    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self._registry_cls = engine_seams.load_policy_registry(config.get("_engine_path"))
        self._unavailable: str | None = None
        if self._registry_cls is None:
            self._unavailable = engine_seams.unavailable_message(
                tool_family="hb_policy_*",
                engine="policy-registry",
                module="policy",
                configured_path=config.get("_engine_path"),
            )
            logger.error(self._unavailable)

    def _require_engine(self):
        if self._unavailable is not None:
            raise engine_seams.CanonicalEngineUnavailable(self._unavailable)
        return self._registry_cls()

    def get_tools(self) -> list[ToolDefinition]:
        return [
            ToolDefinition(
                name="hb_policy_resolve",
                description=(
                    "Resolve the authoritative policy/rule/decision for a scope via "
                    "the real policy-registry engine (read-only, canonical-only)."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "scope": {"type": "string"},
                        "consumer": {"type": "string"},
                        "query": {"type": "string", "default": ""},
                        "required_kind": {"type": "string"},
                    },
                    "required": ["scope"],
                },
                handler=self._resolve,
            ),
            ToolDefinition(
                name="hb_policy_list",
                description="List policy-registry entries (read-only, canonical-only), optionally filtered.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "default": ""},
                        "scope": {"type": "string"},
                        "consumer": {"type": "string"},
                        "kind": {"type": "string"},
                    },
                },
                handler=self._list,
            ),
        ]

    async def _resolve(self, **kwargs) -> dict[str, Any]:
        registry = self._require_engine()
        result = registry.resolve(
            scope=kwargs["scope"],
            consumer=kwargs.get("consumer"),
            query=kwargs.get("query", ""),
            required_kind=kwargs.get("required_kind"),
        )
        return {"engine": "canonical", **result}

    async def _list(self, **kwargs) -> dict[str, Any]:
        registry = self._require_engine()
        entries = registry.search(
            kwargs.get("query", ""),
            scope=kwargs.get("scope"),
            consumer=kwargs.get("consumer"),
            kind=kwargs.get("kind"),
        )
        return {"engine": "canonical", "entries": entries, "count": len(entries)}


def create_module(config: dict[str, Any]) -> PolicyModule:
    return PolicyModule(config)
