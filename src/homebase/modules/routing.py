"""hb_route_ - Credential-free model-routing, with a seam onto the real clutch engine.

Bundled mode keeps the zero-dependency heuristics below. ``[engines.route] mode =
"canonical"`` delegates ``hb_route_select`` to clutch's own dry-run route recipe (the
same sequence as ``clutch route``: ``Fahrer.strecke_analysieren`` -> ``Scorer.bewerte``
-> ``Fahrer.kuppeln``; no LLM call) and ``hb_route_stats`` to ``Fahrer.status()``.

Gaps of clutch's public API, reported instead of worked around:

* ``hb_route_evaluate`` -> ``not_supported``. clutch stores a label per *executed* drive
  (``Fahrer.feedback`` / ``Fahrtenbuch.eval_label_setzen(fahrt_id, quality_score, passed)``),
  needs ``passed`` as well, and ``hb_route_select`` is a dry run that records no drive, so
  its ``route_id`` is not a clutch ``fahrt_id``. Writing a fake drive would corrupt clutch's
  learning data.
* Constraints other than ``provider`` and ``model`` (``max_tokens``, ``speed``, ``cost`` ...)
  have no clutch counterpart and are listed in ``unsupported_constraints``.

Unreachable engine or routing journal under ``canonical`` -> every tool of the family raises
``CanonicalEngineUnavailable`` (MODE-CONTRACT.md).
"""

from __future__ import annotations

import hashlib
import inspect
import logging
import re
from pathlib import Path
from typing import Any

from homebase import engines as engine_seams
from homebase.modules import ModuleBase, ToolDefinition

logger = logging.getLogger("homebase.routing")

_CANONICAL_CONSTRAINTS = ("provider", "model")


class RoutingModule(ModuleBase):
    """Recommend model routes without calling providers."""

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.engine_mode = "bundled"
        self._clutch = None
        self._clutch_db: Path | None = None
        self._unavailable: str | None = None
        if str(config.get("_engine_mode", "bundled")) == "canonical":
            self._clutch = engine_seams.load_clutch(config.get("_engine_path"))
            if self._clutch is None:
                self._unavailable = engine_seams.unavailable_message(
                    tool_family="hb_route_*",
                    engine="clutch",
                    module="route",
                    configured_path=config.get("_engine_path"),
                )
            else:
                # Optional explicit journal (`[route].clutch_db`); otherwise clutch's own
                # ~/.clutch/clutch.db (CLUTCH_HOME). It must already exist: Fahrer() would
                # otherwise create an empty routing journal -- a second, disconnected store.
                explicit = config.get("clutch_db")
                self._clutch_db = Path(str(explicit)).expanduser() if explicit else self._clutch.default_db_path
                if self._clutch_db is None or not self._clutch_db.is_file():
                    self._unavailable = engine_seams.database_unavailable_message(
                        tool_family="hb_route_*",
                        engine="clutch",
                        module="route",
                        db_path=self._clutch_db,
                        db_setting="[route].clutch_db or CLUTCH_HOME",
                    )
                else:
                    self.engine_mode = "canonical"
            if self._unavailable is not None:
                logger.error(self._unavailable)
        self.providers = config.get("providers", ["ollama"])
        self.default_provider = config.get("default_provider", "ollama")
        self.models = config.get(
            "models",
            {
                "fast": "qwen2.5:7b",
                "code": "qwen2.5-coder:7b",
                "long_context": "qwen2.5:14b",
                "general": "qwen2.5:7b",
            },
        )
        self._history: list[dict[str, Any]] = []
        self._feedback: list[dict[str, Any]] = []

    def get_tools(self) -> list[ToolDefinition]:
        return [
            ToolDefinition(
                name="hb_route_select",
                description="Analyze a prompt and recommend the best model/provider",
                input_schema={
                    "type": "object",
                    "properties": {
                        "prompt": {"type": "string", "description": "The prompt to route"},
                        "constraints": {"type": "object", "description": "Optional constraints (max_tokens, speed, cost)"},
                    },
                    "required": ["prompt"],
                },
                handler=self._select,
            ),
            ToolDefinition(
                name="hb_route_evaluate",
                description="Rate a response for routing feedback loop (epsilon-greedy learning)",
                input_schema={
                    "type": "object",
                    "properties": {
                        "route_id": {"type": "string"},
                        "quality": {"type": "number", "minimum": 0, "maximum": 1},
                    },
                    "required": ["route_id", "quality"],
                },
                handler=self._evaluate,
            ),
            ToolDefinition(
                name="hb_route_stats",
                description="Get routing statistics and learning progress",
                input_schema={"type": "object", "properties": {}},
                handler=self._stats,
            ),
        ]

    def _require_engine(self) -> None:
        """Fail closed when canonical was requested but is unreachable."""
        if self._unavailable is not None:
            raise engine_seams.CanonicalEngineUnavailable(self._unavailable)

    def _fahrer(self):
        return self._clutch.Fahrer(db_path=self._clutch_db)

    async def _select_canonical(self, prompt: str, constraints: dict[str, Any]) -> dict[str, Any]:
        fahrer = self._fahrer()
        profil = fahrer.strecke_analysieren(prompt)
        score = self._clutch.get_scorer().bewerte(prompt)
        kwargs: dict[str, Any] = {"zweck": score.zweck}
        unsupported = sorted(key for key in constraints if key not in _CANONICAL_CONSTRAINTS)
        parameters = inspect.signature(fahrer.kuppeln).parameters
        if constraints.get("model"):
            if "model_override" in parameters:
                kwargs["model_override"] = str(constraints["model"])
            else:
                # Older clutch checkouts lack the parameter: never pretend it was honoured.
                unsupported.append("model")
        if constraints.get("provider"):
            kwargs["praeferenz"] = [str(constraints["provider"])]
        config = fahrer.kuppeln(profil, **kwargs)
        return {
            "status": "ok",
            "engine": "canonical",
            "route_id": _route_id(prompt, config.gang.provider, config.gang.model_id),
            "provider": config.gang.provider,
            "model": config.gang.model_id,
            "strategy": profil.typ.value,
            "confidence": profil.konfidenz,
            "score": score.score,
            "zweck": score.zweck,
            "unsupported_constraints": unsupported,
            "clutch": config.to_dict(),
        }

    async def _select(self, **kwargs) -> dict[str, Any]:
        self._require_engine()
        prompt = str(kwargs["prompt"])
        constraints = kwargs.get("constraints") or {}
        if not isinstance(constraints, dict):
            constraints = {}

        if self.engine_mode == "canonical":
            return await self._select_canonical(prompt, constraints)

        signals = _prompt_signals(prompt)
        strategy = _strategy_from_signals(signals, constraints)
        provider = str(constraints.get("provider") or self.default_provider)
        if provider not in self.providers and self.providers:
            provider = str(self.providers[0])
        model = str(constraints.get("model") or self.models.get(strategy) or self.models.get("general") or "default")
        recommendation = {
            "status": "ok",
            "route_id": _route_id(prompt, provider, model),
            "provider": provider,
            "model": model,
            "strategy": strategy,
            "confidence": _confidence(signals, constraints),
            "signals": signals,
            "constraints": constraints,
            "available_providers": self.providers,
        }
        self._history.append(recommendation)
        return recommendation

    async def _evaluate(self, **kwargs) -> dict[str, Any]:
        self._require_engine()
        if self.engine_mode == "canonical":
            return {
                "status": "not_supported",
                "engine": "canonical",
                "operation": "evaluate",
                "message": (
                    "hb_route_evaluate is not available in canonical mode: clutch stores a quality "
                    "label per executed drive (fahrt_id) together with a pass/fail flag, while "
                    "hb_route_select is a dry run that records no drive -- its route_id is not a "
                    "clutch fahrt_id and the tool has no 'passed' input. Use clutch's own feedback "
                    "path (Fahrer.feedback) for executed drives, or the bundled store "
                    "([engines.route] mode = \"bundled\")."
                ),
            }
        route_id = str(kwargs["route_id"])
        quality = min(1.0, max(0.0, float(kwargs["quality"])))
        feedback = {"route_id": route_id, "quality": quality}
        self._feedback.append(feedback)
        return {"status": "recorded", **feedback}

    async def _stats(self, **kwargs) -> dict[str, Any]:
        self._require_engine()
        if self.engine_mode == "canonical":
            status = self._fahrer().status()
            return {
                "status": "ok",
                "engine": "canonical",
                "routes": status.get("tacho", {}).get("gesamte_fahrten"),
                "clutch": status,
            }
        average_quality = None
        if self._feedback:
            average_quality = round(sum(item["quality"] for item in self._feedback) / len(self._feedback), 3)
        return {
            "status": "ok",
            "routes": len(self._history),
            "feedback": len(self._feedback),
            "average_quality": average_quality,
            "providers": self.providers,
            "models": self.models,
        }


def _prompt_signals(prompt: str) -> dict[str, Any]:
    lower = prompt.lower()
    words = re.findall(r"\w+", lower)
    code_terms = {"api", "bug", "code", "debug", "javascript", "python", "refactor", "stacktrace", "test", "typescript"}
    research_terms = {"analysis", "analyse", "evidence", "literature", "paper", "research", "source", "study"}
    planning_terms = {"architecture", "plan", "roadmap", "steps", "strategy", "workflow"}
    creative_terms = {"brand", "copy", "design", "story", "tone", "write"}
    return {
        "word_count": len(words),
        "has_code": bool(code_terms.intersection(words) or "```" in prompt),
        "has_research": bool(research_terms.intersection(words)),
        "has_planning": bool(planning_terms.intersection(words)),
        "has_creative": bool(creative_terms.intersection(words)),
        "long_context": len(prompt) > 4000 or len(words) > 700,
    }


def _strategy_from_signals(signals: dict[str, Any], constraints: dict[str, Any]) -> str:
    if constraints.get("speed") == "fast" or constraints.get("latency") == "low":
        return "fast"
    if signals["has_code"]:
        return "code"
    if signals["long_context"] or int(constraints.get("max_tokens") or 0) > 4096:
        return "long_context"
    return "general"


def _confidence(signals: dict[str, Any], constraints: dict[str, Any]) -> float:
    score = 0.55
    if any(signals[key] for key in ("has_code", "has_research", "has_planning", "has_creative")):
        score += 0.1
    if constraints:
        score += 0.1
    if signals["long_context"]:
        score += 0.1
    return round(min(score, 0.9), 2)


def _route_id(prompt: str, provider: str, model: str) -> str:
    digest = hashlib.sha256(f"{provider}\0{model}\0{prompt}".encode("utf-8")).hexdigest()
    return digest[:16]


def create_module(config: dict[str, Any]) -> RoutingModule:
    return RoutingModule(config)
