"""hb_route_ - Credential-free model-routing heuristics."""

from __future__ import annotations

import hashlib
import re
from typing import Any

from homebase.modules import ModuleBase, ToolDefinition


class RoutingModule(ModuleBase):
    """Recommend local model routes without calling providers."""

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
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

    async def _select(self, **kwargs) -> dict[str, Any]:
        prompt = str(kwargs["prompt"])
        constraints = kwargs.get("constraints") or {}
        if not isinstance(constraints, dict):
            constraints = {}

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
        route_id = str(kwargs["route_id"])
        quality = min(1.0, max(0.0, float(kwargs["quality"])))
        feedback = {"route_id": route_id, "quality": quality}
        self._feedback.append(feedback)
        return {"status": "recorded", **feedback}

    async def _stats(self, **kwargs) -> dict[str, Any]:
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
