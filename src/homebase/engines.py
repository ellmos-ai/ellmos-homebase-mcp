"""Engine seams: optionally load the real canonical engines instead of the
bundled zero-dependency implementations.

Background (see KONZEPT.md "Engine Seams"): each `hb_*` module ships a
self-contained SQLite implementation so a bare `pip install`/`npx` always
works with no third-party engine present ("bundled" mode). On systems where
the canonical ellmos engines (Gardener, Rinnsal, clutch, ...) already exist
on disk, `[engines].mode = "canonical"` in homebase.toml makes the affected
modules import and delegate to the *real* engine/DB instead of maintaining a
second, disconnected copy.

If the canonical engine cannot be found or fails to import, the affected tool
family becomes **fail-closed**: the server still starts and still lists its
tools, but each call in that family raises `CanonicalEngineUnavailable`
instead of quietly serving the bundled store. Writing into a second,
disconnected DB behind the operator's back is exactly what the canonical mode
exists to prevent, so a silent downgrade is not an acceptable degradation.
"bundled" remains a fully supported mode -- but only when it is *chosen*.
See MODE-CONTRACT.md for the binding rule.

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


class CanonicalEngineUnavailable(RuntimeError):
    """`mode = "canonical"` was requested but the canonical engine is unreachable.

    Raised at *call* time, not at import/startup time: the server must still
    start and list its tools (see module docstring), but a tool whose canonical
    target is missing must fail loudly rather than write into the bundled
    store. Callers see an MCP tool error naming the mode and the target.
    """


def unavailable_message(
    *,
    tool_family: str,
    engine: str,
    module: str,
    configured_path: str | None,
) -> str:
    """Build the operator-facing message for an unreachable canonical engine.

    Names all three things an operator needs to act: which tools are affected,
    what was looked for and where, and the two ways out (fix the path, or
    choose bundled explicitly for this one namespace).
    """
    target = configured_path or "no explicit path configured"
    return (
        f"{tool_family}: engine mode 'canonical' is configured, but the canonical "
        f"{engine} engine could not be found or imported (target: {target}; also checked "
        f"HOMEBASE_ENGINE_{module.upper()}_PATH, the module catalog, and the built-in "
        f"default locations). Refusing to fall back to the bundled store, because that "
        f"would silently write into a second, disconnected database. "
        f"Fix the engine path, or choose the bundled store explicitly with "
        f"[engines.{module}] mode = \"bundled\" in homebase.toml."
    )


# Modules with a real canonical-VS-bundled TOGGLE implemented today. Kept as
# a small, explicit map so `engine_summary()` can tell "canonical requested
# and wired" apart from "canonical requested but this module has no seam
# yet" (kb/route currently fall in the latter bucket -- see KONZEPT.md).
SEAM_IMPLEMENTED = {"garden", "state", "mem"}

# T-20260825-196589547 (1): policy/ticket/lock are a THIRD category, distinct
# from both buckets above -- they always try the canonical engine and have
# NO bundled alternative to toggle to at all (see policy.py/ticket.py/
# lock.py module docstrings for why a bundled copy of live governance/
# coordination state would be actively misleading rather than a smaller-but-
# honest substitute, unlike kb/route). `_engine_mode` is not read by these
# modules, mirroring kb/route's "no switch exists" shape but inverted:
# kb/route ignore `canonical` and stay bundled; these ignore `bundled` and
# stay canonical-only.
CANONICAL_ONLY = {"policy", "ticket", "lock"}

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
    # T-20260825-196589547 (1): three new seams. IMPORTANT CORRECTION found
    # empirically while smoke-testing this against the real machine: unlike
    # garden/mem/state (whose real code lives directly under the OneDrive
    # path), policy-registry/ticket-master/lock-master are Plan-D "Klasse B"
    # modules -- the OneDrive projection folder holds ONLY a manifest +
    # README pointer (`.AI/.MODULES/.CONTROL/<name>/README.md`: "In OneDrive
    # liegen nur Manifest und Zeiger; der Code wird ausschliesslich im
    # lokalen Git-Klon bearbeitet"), never the importable package itself.
    # Defaults therefore point at the canonical local clone location
    # (`C:\_Local_DEV\repos\<name>`, the one clone path this whole ecosystem
    # uses on every host per Plan-D) instead of the OneDrive projection.
    # `policy-registry` additionally uses a src/ layout, so its candidate is
    # the `src` subdirectory, not the repo root (ticket-master/lock-master
    # both import from their repo root, see load_ticket_master/
    # load_lock_master below).
    "policy": [
        "~/_Local_DEV/repos/policy-registry/src",
        "C:/_Local_DEV/repos/policy-registry/src",
    ],
    "ticket": [
        "~/_Local_DEV/repos/ticket-master",
        "C:/_Local_DEV/repos/ticket-master",
    ],
    "lock": [
        "~/_Local_DEV/repos/lock-master",
        "C:/_Local_DEV/repos/lock-master",
    ],
}

_CATALOG_MODULE_IDS = {
    "garden": "GARDENER",
    "mem": "USMC",
}
# T-20260825-196589547 (1): CORRECTION found empirically -- policy/ticket/
# lock are DELIBERATELY absent from this map. The module catalog's
# `resolved_source` for these three points at their OneDrive Plan-D
# "Klasse B" projection folder (manifest + README pointer only, verified
# empirically: it holds no importable package for any of the three), unlike
# GARDENER/USMC whose real code is genuinely deployed under OneDrive. Since
# `resolve_engine_path` tries the catalog result BEFORE `_DEFAULT_CANDIDATES`
# and only checks `path.exists()` (a directory that exists but contains no
# package still "exists"), registering these here would make catalog
# resolution always win and always be empty -- silently masking the correct
# `_DEFAULT_CANDIDATES` (local clone) entries below. Leaving them unmapped
# means resolution goes straight to the correct local-clone defaults.

# T-20260825-196589547 (2): engines.py's own _DEFAULT_CANDIDATES/catalog logic
# above duplicates in miniature what source-resolver's Stufenleiter already
# does generically. IMPORTANT CORRECTION found while implementing this
# (verified against source-resolver's ladder.py, 2026-08-25): the three
# candidate roles do NOT all return the same shape.
#   - "memory.organic" (Gardener) / "memory.curated" (USMC) resolve via a
#     bare CLI-PRESENCE check (`shutil.which("gardener"/"usmc")`), because
#     both are plain pip/editable installs with no fixed module directory --
#     `quelle` carries a `resolved_path` to the CLI EXECUTABLE, not a Python
#     package directory. Feeding that into `import_from_path()` (which does
#     `sys.path.insert` on a *directory*) would be wrong.
#   - "policy.registry" has a REGISTERED ADAPTER (`adapters/policy_registry.py`
#     in source-resolver) that requires an explicit `scope` and returns
#     resolved POLICY CONTENT, not a module path -- using it to answer "where
#     is the policy-registry PACKAGE installed" would be a category error.
# Consequence: only "garden"/"mem" are routed through source-resolver here
# (as a bare-import hint, see `_try_source_resolver_bare_import` below).
# "policy" (like "state"/"ticket"/"lock") keeps the unchanged legacy
# catalog+defaults path -- see `_CATALOG_MODULE_IDS["policy"]` below.
_SOURCE_RESOLVER_ROLE_BY_ENGINE: dict[str, str] = {
    "garden": "memory.organic",
    "mem": "memory.curated",
}
_SOURCE_RESOLVER_MODULE_NAME: dict[str, str] = {
    "garden": "gardener",
    "mem": "usmc",
}


def _try_source_resolver_bare_import(name: str):
    """Best-effort: if source-resolver confirms the CLI for ``name``'s mapped
    role is on PATH, attempt a BARE ``importlib.import_module`` (no sys.path
    insertion -- see the module-level comment above for why). Returns the
    imported module, or None on ANY failure (package missing, role
    unresolved, import failure) -- callers must fall through to the
    unchanged legacy directory search exactly as if this function did not
    exist."""
    role = _SOURCE_RESOLVER_ROLE_BY_ENGINE.get(name)
    if role is None:
        return None
    try:
        from source_resolver import ResolutionStatus
        from source_resolver import resolve as sr_resolve
    except ImportError:
        return None
    try:
        result = sr_resolve(role)
    except Exception as exc:  # noqa: BLE001 - resolver failure must degrade, not crash
        logger.info("source-resolver lookup for role '%s' failed: %s", role, exc)
        return None
    if result.status != ResolutionStatus.RESOLVED:
        return None
    module_name = _SOURCE_RESOLVER_MODULE_NAME[name]
    try:
        return importlib.import_module(module_name)
    except Exception as exc:  # noqa: BLE001 - must degrade, not crash
        logger.info("Bare import of '%s' after source-resolver hit failed: %s", module_name, exc)
        return None


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
    module = None if configured_path else _try_source_resolver_bare_import("garden")
    if module is not None and hasattr(module, "Gardener"):
        try:
            return module.Gardener()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Gardener resolved via source-resolver but failed to initialize: %s", exc)
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
    module = None if configured_path else _try_source_resolver_bare_import("mem")
    if module is not None and hasattr(module, "USMCClient"):
        return module.USMCClient
    path = resolve_engine_path("mem", configured_path)
    if path is None:
        logger.info("Canonical USMC engine not found (checked %s and defaults)", configured_path)
        return None
    module = import_from_path("usmc", path)
    if module is None or not hasattr(module, "USMCClient"):
        return None
    return module.USMCClient


def load_policy_registry(configured_path: str | None = None):
    """Return the real ``policy_registry.PolicyRegistry`` class, or None.

    Returns the class (not an instance): ``PolicyRegistry()`` with no
    arguments already resolves the correct default registry path
    (``~/.policy-registry/registry.json``), so the caller can instantiate
    per-call exactly like ``load_rinnsal_task_client_class``'s TaskClient.
    T-20260825-196589547 (1): this namespace has no bundled fallback, so a
    None here always means the module fails closed -- see policy.py.
    """
    path = resolve_engine_path("policy", configured_path)
    if path is None:
        logger.info("Canonical policy-registry engine not found (checked %s and defaults)", configured_path)
        return None
    module = import_from_path("policy_registry", path)
    if module is None or not hasattr(module, "PolicyRegistry"):
        return None
    return module.PolicyRegistry


def resolve_tickets_root(configured_path: str | None = None) -> Path | None:
    """Return the `_control-center/_TICKETS` folder, or None if unreachable.

    Deliberately independent of ``resolve_engine_path("ticket", ...)``: "is
    ticket-master's code installed" (a capability/presence check) and
    "where does the `_TICKETS` lifecycle folder live" (a fixed, well-known
    OneDrive convention path, documented in `_control-center/_TICKETS/
    README.md`) are two separate questions -- the folder is not physically
    under ticket-master's own module directory."""
    candidates: list[Path] = []
    env_override = os.environ.get("HOMEBASE_TICKETS_ROOT")
    if env_override:
        candidates.append(Path(env_override))
    if configured_path:
        candidates.append(Path(configured_path))
    one_drive = os.environ.get("OneDrive") or os.environ.get("ONEDRIVE")
    if one_drive:
        candidates.append(Path(one_drive) / ".TOPICS" / "_control-center" / "_TICKETS")
    candidates.append(Path("~/OneDrive/.TOPICS/_control-center/_TICKETS").expanduser())
    for candidate in candidates:
        path = candidate.expanduser()
        if path.is_dir():
            return path
    return None


def load_ticket_master(configured_path: str | None = None):
    """Return the real ``lib.ticket_audit`` module of ticket-master, or None.

    Used only as a PRESENCE/capability signal for `hb_ticket_*` (fail closed
    if ticket-master itself is not installed, even though the actual v1
    list/show operations read `resolve_tickets_root()` directly -- see the
    module docstring of `resolve_tickets_root` for why the two are kept
    separate)."""
    path = resolve_engine_path("ticket", configured_path)
    if path is None:
        logger.info("Canonical ticket-master engine not found (checked %s and defaults)", configured_path)
        return None
    module = import_from_path("lib.ticket_audit", path)
    if module is None or not hasattr(module, "collect_ids"):
        return None
    return module


def load_lock_master(configured_path: str | None = None):
    """Return the real ``lock_scan`` module (functions ``load_config``,
    ``collect_locks``) and ``lock_status`` module (``check_project_status``),
    or (None, None) if unavailable. lock-master ships flat ``py-modules``
    under ``pure-locking/`` (no package/__init__.py), so both are imported
    from that one resolved directory. T-20260825-196589547 (1): no bundled
    fallback for this namespace either -- see lock.py."""
    path = resolve_engine_path("lock", configured_path)
    if path is None:
        logger.info("Canonical lock-master engine not found (checked %s and defaults)", configured_path)
        return None, None
    pure_locking = path / "pure-locking"
    search_path = pure_locking if pure_locking.is_dir() else path
    scan = import_from_path("lock_scan", search_path)
    status = import_from_path("lock_status", search_path)
    if scan is None or not hasattr(scan, "collect_locks") or not hasattr(scan, "load_config"):
        return None, None
    if status is None or not hasattr(status, "check_project_status"):
        return scan, None
    return scan, status


def engine_summary(config) -> list[str]:
    """Human-readable per-module engine mode lines for startup logging.

    ``config`` is a ``homebase.config.HomebaseConfig``. Modules without an
    implemented seam are reported as "bundled-only" when canonical was
    requested for them, so operators see the request was heard but not (yet)
    wired -- rather than silently ignored. See KONZEPT.md "Engine Seams".
    """
    lines = []
    for name in ("garden", "state", "mem", "kb", "route", "policy", "ticket", "lock"):
        if name in CANONICAL_ONLY:
            lines.append(f"{name}=canonical-only (no bundled alternative for this namespace)")
            continue
        settings = config.engine_settings(name)
        mode = settings["mode"]
        if mode == "canonical" and name not in SEAM_IMPLEMENTED:
            lines.append(f"{name}=bundled-only (canonical requested, no seam implemented yet)")
        else:
            lines.append(f"{name}={mode}")
    return lines
