"""Configuration loader for Homebase MCP."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # Python <3.11 fallback


DEFAULT_CONFIG_PATHS = [
    Path.home() / ".homebase" / "homebase.toml",
    Path.home() / ".config" / "homebase" / "homebase.toml",
]

DEFAULT_ENABLED_MODULES = [
    "mem", "route", "kb", "swarm", "state", "garden", "api", "test", "conn", "auto", "plug",
]

# Zero-dependency default: a source checkout or npm/pip install with no
# homebase.toml at all must stay fully self-contained (see KONZEPT.md "Engine
# Seams"). Systems that want the real Gardener/Rinnsal/clutch engines set
# `[engines].mode = "canonical"` explicitly in their own homebase.toml.
DEFAULT_ENGINE_MODE = "bundled"


@dataclass
class HomebaseConfig:
    enabled_modules: list[str] = field(default_factory=lambda: list(DEFAULT_ENABLED_MODULES))
    language: str = "en"
    module_configs: dict[str, dict[str, Any]] = field(default_factory=dict)
    engine_mode: str = DEFAULT_ENGINE_MODE
    engine_configs: dict[str, dict[str, Any]] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)

    def module_config(self, name: str) -> dict[str, Any]:
        return self.module_configs.get(name, {})

    def engine_settings(self, name: str) -> dict[str, Any]:
        """Resolve the effective engine mode/path for one module.

        Per-module `[engines.<name>]` overrides the global `[engines].mode`.
        `mode` is either "canonical" (use the real Gardener/Rinnsal/clutch
        engine when importable) or "bundled" (always use the built-in
        zero-dependency SQLite implementation).
        """
        per_module = self.engine_configs.get(name, {})
        mode = str(per_module.get("mode") or self.engine_mode)
        return {"mode": mode, "path": per_module.get("path")}


def load_config(path: str | Path | None = None) -> HomebaseConfig:
    """Load config from toml file. Falls back to defaults if no file found."""
    if path is None:
        env_path = os.environ.get("HOMEBASE_CONFIG")
        if env_path:
            path = Path(env_path)
        else:
            for candidate in DEFAULT_CONFIG_PATHS:
                if candidate.exists():
                    path = candidate
                    break

    if path is None or not Path(path).exists():
        return HomebaseConfig(language=_env_language("en"))

    with open(path, "rb") as f:
        raw = tomllib.load(f)

    modules_section = raw.get("modules", {})
    server_section = raw.get("server", {})
    enabled = modules_section.get("enabled", list(DEFAULT_ENABLED_MODULES))
    if isinstance(enabled, str):
        enabled = [enabled]
    language = _env_language(server_section.get("language") or server_section.get("locale") or "en")

    engines_section = raw.get("engines", {})
    engine_mode = str(engines_section.get("mode") or DEFAULT_ENGINE_MODE)
    engine_configs = {
        key: value for key, value in engines_section.items() if isinstance(value, dict)
    }

    module_configs = {}
    for key, value in raw.items():
        if key not in ("server", "modules", "engines") and isinstance(value, dict):
            module_configs[key] = value

    return HomebaseConfig(
        enabled_modules=enabled,
        language=language,
        module_configs=module_configs,
        engine_mode=engine_mode,
        engine_configs=engine_configs,
        raw=raw,
    )


def _env_language(default: str) -> str:
    return os.environ.get("HOMEBASE_LANG") or os.environ.get("HOMEBASE_LOCALE") or default
