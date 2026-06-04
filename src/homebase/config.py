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
    "mem", "route", "kb", "swarm", "state", "garden", "api", "test",
]


@dataclass
class HomebaseConfig:
    enabled_modules: list[str] = field(default_factory=lambda: list(DEFAULT_ENABLED_MODULES))
    language: str = "en"
    module_configs: dict[str, dict[str, Any]] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)

    def module_config(self, name: str) -> dict[str, Any]:
        return self.module_configs.get(name, {})


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

    module_configs = {}
    for key, value in raw.items():
        if key not in ("server", "modules") and isinstance(value, dict):
            module_configs[key] = value

    return HomebaseConfig(
        enabled_modules=enabled,
        language=language,
        module_configs=module_configs,
        raw=raw,
    )


def _env_language(default: str) -> str:
    return os.environ.get("HOMEBASE_LANG") or os.environ.get("HOMEBASE_LOCALE") or default
