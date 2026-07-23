"""Engine seams: optionally load the real canonical engines instead of the
bundled zero-dependency implementations.

Background (see KONZEPT.md "Engine Seams"): each `hb_*` module ships a
self-contained SQLite implementation so a bare `pip install`/`npx` always
works with no third-party engine present ("bundled" mode). On systems where
the canonical ellmos engines (Gardener, Rinnsal, clutch, ...) already exist
on disk, `[engines].mode = "canonical"` in homebase.toml makes the affected
modules import and delegate to the *real* engine/DB instead of maintaining a
second, disconnected copy. If the canonical engine cannot be found or fails
to import, modules fall back to "bundled" and log why -- the server must
never fail to start because a canonical engine is missing.

This module only knows how to *locate and import* an engine. Each module
(garden.py, state.py, ...) decides what to do with the imported object.
"""

from __future__ import annotations

import importlib
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

logger = logging.getLogger("homebase.engines")

# Modules with a real canonical seam implemented today. Kept as a small,
# explicit map so `engine_summary()` can tell "canonical requested and wired"
# apart from "canonical requested but this module has no seam yet" (mem/kb/
# route currently fall in the latter bucket -- see KONZEPT.md).
SEAM_IMPLEMENTED = {"garden", "state", "mem"}

# Default candidate directories per engine, checked when no explicit `path`
# is configured. These match this ecosystem's `.AI/.MEMORY/` / `.AI/.OS/`
# layout (gardener moved to `.MEMORY/GARDENER` 2026-07-11; old `.OS` path kept
# as fallback for systems that have not migrated yet) but are only a
# convenience default -- any system can override via `[engines.<name>].path`
# or the `HOMEBASE_ENGINE_<NAME>_PATH` environment variable.
_DEFAULT_CANDIDATES: dict[str, list[str]] = {
    "garden": [
        "~/OneDrive/.TOPICS/.AI/.MODULES/.MEMORY/GARDENER",
        "~/.TOPICS/.AI/.MODULES/.MEMORY/GARDENER",
        "~/OneDrive/.TOPICS/.AI/.MEMORY/GARDENER",
        "~/.TOPICS/.AI/.MEMORY/GARDENER",
        "~/OneDrive/.TOPICS/.AI/.OS/gardener",
        "~/.TOPICS/.AI/.OS/gardener",
    ],
    "state": [
        "~/OneDrive/.TOPICS/.AI/.OS/rinnsal",
        "~/.TOPICS/.AI/.OS/rinnsal",
    ],
    "mem": [
        "~/OneDrive/.TOPICS/.AI/.MODULES/.MEMORY/USMC",
        "~/.TOPICS/.AI/.MODULES/.MEMORY/USMC",
    ],
}

_CATALOG_MODULE_IDS = {
    "garden": "GARDENER",
    "mem": "USMC",
}


def _module_catalog_candidates() -> list[Path]:
    """Return configured and conventional module catalog locations in priority order."""
    candidates: list[Path] = []
    configured = os.environ.get("ELLMOS_MODULES_CATALOG")
    if configured:
        candidates.append(Path(configured).expanduser())
    one_drive = os.environ.get("OneDrive") or os.environ.get("ONEDRIVE")
    if one_drive:
        candidates.append(Path(one_drive) / ".TOPICS" / ".AI" / ".MODULES" / "modules.catalog.json")
    candidates.extend([
        Path("~/OneDrive/.TOPICS/.AI/.MODULES/modules.catalog.json").expanduser(),
        Path("~/.TOPICS/.AI/.MODULES/modules.catalog.json").expanduser(),
    ])
    result: list[Path] = []
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved not in result:
            result.append(resolved)
    return result


def resolve_catalog_module_path(module_id: str) -> Path | None:
    """Resolve a module ID from the v2 catalog without importing the catalog tooling."""
    for catalog_path in _module_catalog_candidates():
        try:
            catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if catalog.get("schema") != "ellmos.modules-catalog.v1":
            continue
        for module in catalog.get("modules", []):
            if not isinstance(module, dict) or module.get("id") != module_id:
                continue
            resolved_source = module.get("resolved_source")
            if not isinstance(resolved_source, str) or not resolved_source:
                break
            module_path = (catalog_path.parent / resolved_source).resolve()
            if module_path.is_dir():
                return module_path
            break
    return None


def resolve_engine_path(name: str, configured_path: str | None) -> Path | None:
    """Return the first existing directory for a canonical engine, or None."""
    candidates: list[str] = []
    env_override = os.environ.get(f"HOMEBASE_ENGINE_{name.upper()}_PATH")
    if env_override:
        candidates.append(env_override)
    if configured_path:
        candidates.append(configured_path)
    module_id = _CATALOG_MODULE_IDS.get(name)
    if module_id:
        catalog_path = resolve_catalog_module_path(module_id)
        if catalog_path is not None:
            candidates.append(str(catalog_path))
    candidates.extend(_DEFAULT_CANDIDATES.get(name, []))

    for candidate in candidates:
        path = Path(candidate).expanduser()
        if path.exists():
            return path
    return None


def import_from_path(module_name: str, search_path: Path) -> Any | None:
    """Import ``module_name`` after temporarily adding ``search_path`` to sys.path.

    Returns the imported module, or None if the import fails. Never raises --
    a missing/broken canonical engine must degrade to the bundled fallback,
    not crash the server.
    """
    search_str = str(search_path)
    inserted = search_str not in sys.path
    if inserted:
        sys.path.insert(0, search_str)
    try:
        return importlib.import_module(module_name)
    except Exception as exc:  # noqa: BLE001 - any import-time failure must degrade gracefully
        logger.info("Canonical engine import '%s' from %s failed: %s", module_name, search_path, exc)
        return None
    finally:
        if inserted:
            try:
                sys.path.remove(search_str)
            except ValueError:
                pass


def load_gardener(configured_path: str | None = None):
    """Return a ready ``gardener.Gardener()`` instance, or None if unavailable."""
    path = resolve_engine_path("garden", configured_path)
    if path is None:
        logger.info("Canonical Gardener engine not found (checked %s and defaults)", configured_path)
        return None
    module = import_from_path("gardener", path)
    if module is None or not hasattr(module, "Gardener"):
        return None
    try:
        return module.Gardener()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Canonical Gardener engine found at %s but failed to initialize: %s", path, exc)
        return None


def load_rinnsal_task_client_class(configured_path: str | None = None):
    """Return the real ``rinnsal.tasks.client.TaskClient`` class, or None."""
    path = resolve_engine_path("state", configured_path)
    if path is None:
        logger.info("Canonical Rinnsal engine not found (checked %s and defaults)", configured_path)
        return None
    module = import_from_path("rinnsal.tasks.client", path)
    if module is None or not hasattr(module, "TaskClient"):
        return None
    return module.TaskClient


def load_usmc_client_class(configured_path: str | None = None):
    """Return the real ``usmc.USMCClient`` class, or None if unavailable.

    Returns the class (not an instance) because USMC is multi-agent by design:
    ``memory.py`` constructs one client per call with the resolved ``agent_id``
    so per-call provenance is preserved. Never raises -- a missing/broken USMC
    checkout degrades the memory module to its bundled SQLite store.
    """
    path = resolve_engine_path("mem", configured_path)
    if path is None:
        logger.info("Canonical USMC engine not found (checked %s and defaults)", configured_path)
        return None
    module = import_from_path("usmc", path)
    if module is None or not hasattr(module, "USMCClient"):
        return None
    return module.USMCClient


def engine_summary(config) -> list[str]:
    """Human-readable per-module engine mode lines for startup logging.

    ``config`` is a ``homebase.config.HomebaseConfig``. Modules without an
    implemented seam are reported as "bundled-only" when canonical was
    requested for them, so operators see the request was heard but not (yet)
    wired -- rather than silently ignored. See KONZEPT.md "Engine Seams".
    """
    lines = []
    for name in ("garden", "state", "mem", "kb", "route"):
        settings = config.engine_settings(name)
        mode = settings["mode"]
        if mode == "canonical" and name not in SEAM_IMPLEMENTED:
            lines.append(f"{name}=bundled-only (canonical requested, no seam implemented yet)")
        else:
            lines.append(f"{name}={mode}")
    return lines
