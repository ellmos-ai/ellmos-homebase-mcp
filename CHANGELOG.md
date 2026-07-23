# Changelog

All notable changes to `ellmos-homebase-mcp` are tracked here.

## 0.1.0-alpha.15 - 2026-07-23

### Fixed

- Return `not_found` instead of a misleading successful empty run when `hb_test_run`
  receives an unknown single test name for an otherwise valid battery.

### Added

- USMC engine seam for `hb_mem_*`. With `[engines.mem].mode = "canonical"` (or global canonical) and a USMC checkout present, `hb_mem_store`/`hb_mem_query`/`hb_mem_context` delegate to the real cross-agent USMC store instead of a second disconnected copy; responses carry an `"engine"` field. Because USMC's model differs (typed key/value facts, no free-text search), the seam reconciles it: homebase's category is kept in the fact key, keyword query filters client-side (`mode: "client_filter"`), and per-call `agent_id` provenance is preserved via one USMC client per call. `hb_mem_merge`/`hb_mem_consolidate` remain bundled-only bulk-hygiene ops and report `not_supported` under canonical (deferred, TODO #72). A missing/broken USMC checkout degrades to the bundled store and never fails startup. Verified with a SQLite fixture double (store→query→context roundtrip, bundled fallback), a real-import smoke check, and a live roundtrip against the real USMC client. Known canonical-mode differences: `hb_mem_store` returns the USMC fact `key` instead of the bundled numeric `id`, and query/context read the full fact set per call (USMC's API has no limit parameter; truncation happens post-fetch).
- i18n regression guard (`tests/test_i18n_completeness.py`): locale key-set parity for `TRANSLATIONS`/`SCHEMA_TRANSLATIONS` plus a full-registry check that every registered tool has a `tool.<name>` entry — the silent-stub-locale bug class can no longer ship unnoticed.
- i18n polish: full-width CJK punctuation（），for the zh/ja tool descriptions (matching the ServerCommander precedent), Spanish participle fix (`basándose en la confianza`), Russian word-order fix (`dry-run плагина`).
- Complete i18n tool-description coverage. `es`, `zh`, `ja`, and `ru` gained the 37 `hb_*`
  tool descriptions that previously fell back to English (only 7 were localized per language
  before). `hb_mem_consolidate`, which had been English-only in every locale including German,
  is now translated in all six. German and the input-schema field descriptions were already
  complete, so every locale now covers all 46 tool descriptions.
- Add metadata regression tests that keep npm, Python, MCP registry, and runtime versions
  synchronized and guard the documented non-module boundaries for `ellmos-chat`, `ellmos-core`,
  `ellmos-stack`, and `open-compute`.

### Changed

- Mark the completed Homebase concept-boundary and release-metadata TODOs as done.
- Maintenance update: refresh llms.txt Last-checked timestamp for 2026-07-22 and verify test suite & metadata sync.

## 0.1.0-alpha.14 - 2026-07-04

### Added

- **Engine seams (`[engines].mode = "canonical" | "bundled"`).** `hb_garden_*` and
  `hb_state_task_*` can now delegate to the real canonical engines instead of homebase's
  own disconnected SQLite copies: `hb_garden_*` to the real Gardener (`everything` + FTS5,
  `~/.gardener/gardener.db`) and `hb_state_task_*` to the real Rinnsal `TaskClient`
  (`rinnsal_tasks` table, defaults to `~/.rinnsal/scanner_tasks.db`). `mode = "bundled"`
  (still the zero-dependency default for a bare install) keeps the previous self-contained
  behavior unchanged. New `homebase/engines.py` resolves engine paths (config override, then
  `HOMEBASE_ENGINE_<NAME>_PATH` env var, then this ecosystem's default `.AI/.OS/*` locations)
  and imports the real engine module, falling back to bundled with a logged warning if the
  canonical engine is missing or fails to import — the server never fails to start over this.
- Startup now logs one `Engine seams: ...` line summarizing the resolved mode per module,
  including an explicit `bundled-only (canonical requested, no seam implemented yet)` marker
  for `hb_mem_*`/`hb_kb_*`/`hb_route_*` when canonical mode is requested globally but no seam
  exists yet for that module (see KONZEPT.md "Engine Seams").
- Tool responses from `hb_garden_*`/`hb_state_task_*` now include an `"engine"` field
  (`"canonical"` or `"bundled"`) so callers can tell which store answered.
- Tests: `tests/test_engine_seams.py` covers path resolution, import fallback, and full
  canonical-mode roundtrips against fixture doubles of the real Gardener/Rinnsal APIs.

### Fixed

- `hb_garden_*` and `hb_state_task_*` no longer silently diverge from the real Gardener/Rinnsal
  data other tools (the CLI, the `_tasks` scanner) read and write, closing the gap noted in the
  KONZEPT.md status callout ("credential-free reimplementations, not the real engines").

## 0.1.0-alpha.13 - 2026-07-03

### Added

- `hb_kb_search` and `hb_mem_query` now use a real external-content FTS5 index (`storage.setup_fts` / `fts_match_query`) for prefix-match keyword search, with automatic `LIKE` fallback when the local SQLite build lacks FTS5.
- `hb_mem_merge` applies a real confidence-based dedup (previously preview-only): keeps the highest-confidence survivor per duplicate group and deletes the redundant rows.
- New `hb_mem_consolidate` tool decays memory confidence and prunes low-confidence entries (`dry_run` previews, `dry_run=false` applies).
- Tests for FTS category filtering, agent-scoped merge/consolidate, and mode reporting.

### Security

- Expand repository and npm package hygiene rules for local Homebase configs, npm/PyPI tokens, token JSON files, recovery codes, and private SSH key filenames.

## 0.1.0-alpha.12 - 2026-06-18

### Added

- `hb_mem_*`, `hb_kb_*`, and `hb_state_*` now record `agent_id` provenance for shared Team-Memory use.
- Memory, knowledge, state-memory, and task queries can filter by `agent_id`.
- `hb_state_mem_set` now stores the same key separately per agent through a `(agent_id, key)` uniqueness rule, with migration for older alpha databases.

### Changed

- Homebase SQLite connections now enable WAL mode, a 30-second busy timeout, and foreign-key checks to reduce multi-agent write-lock failures.

## 0.1.0-alpha.11 - 2026-06-17

### Changed

- Add a TTY-guarded `update-notifier` check for interactive CLI starts while keeping MCP stdio output unchanged.

### Fixed

- Align `package.json`, lockfile, `pyproject.toml`, Python `__version__`, and `server.json` metadata after the update-notifier release.

## 0.1.0-alpha.9 - 2026-06-13

### Fixed

- `registry.py`: Eliminated a race condition in `ModuleRegistry.list_tools` where `_handlers.clear()` could expose an empty dict if `call_tool` ran concurrently during a rebuild. Handlers are now rebuilt locally and assigned atomically after the full rebuild completes.

### Added

- Added a GitHub Actions test workflow for Python 3.10, 3.11, and 3.12 plus Node.js 20, 22, and 24 smoke/package checks.
- Added MIT `LICENSE`, MCP Registry metadata in `server.json`, and machine-readable project context in `llms.txt`.

### Changed

- Added README start-here tables and discovery context for local-first MCP orchestration searches.
- Expanded `llms.txt`, npm keywords, Python keywords, and MCP Registry metadata with SQLite memory, agent orchestration, swarm planning, API discovery, connector queue, and plugin discovery search anchors.
- Tightened npm packaging so ignored Python bytecode under `src/` is not included in `npm pack`.

## 0.1.0-alpha.8 - 2026-06-05

- Added local automation-chain and plugin-discovery adapters.
- Kept automation and plugin execution plan-only/dry-run for the alpha release.
- Updated public README metadata for the expanded Homebase tool set.
