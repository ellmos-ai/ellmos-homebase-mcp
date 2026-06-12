# Changelog

All notable changes to `ellmos-homebase-mcp` are tracked here.

## 2026-06-12

### Documentation

- Added README start-here tables and discovery context for local-first MCP orchestration searches.
- Expanded `llms.txt`, npm keywords, Python keywords, and MCP Registry metadata with SQLite memory, agent orchestration, swarm planning, API discovery, connector queue, and plugin discovery search anchors.

## 2026-06-10

### Fixed

- `registry.py`: Eliminated a race condition in `ModuleRegistry.list_tools` — previously `_handlers.clear()` could expose an empty dict if `call_tool` ran concurrently during the rebuild; now builds into a local dict and atomically assigns to `self._handlers` after the full rebuild completes.

## 2026-06-07

- Added a GitHub Actions test workflow for Python 3.10, 3.11, and 3.12 plus Node.js 20, 22, and 24 smoke/package checks.
- Added MIT `LICENSE`, MCP Registry metadata in `server.json`, and machine-readable project context in `llms.txt`.
- Tightened npm packaging so ignored Python bytecode under `src/` is not included in `npm pack`.

## 0.1.0-alpha.8 - 2026-06-05

- Added local automation-chain and plugin-discovery adapters.
- Kept automation and plugin execution plan-only/dry-run for the alpha release.
- Updated public README metadata for the expanded Homebase tool set.
