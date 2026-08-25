# Changelog

All notable changes to `ellmos-homebase-mcp` are tracked here.

## 0.1.0-alpha.23 (Discoverability & Design Audit) - 2026-08-24

### Discoverability & Documentation
- **Bilingual Schnellnavigation / Quick Navigation**: Added structured anchor links across `README.md` and `README_de.md` for fast developer and AI agent orientation.
- **Interactive Bilingual Mermaid Sequence Diagram**: Added `sequenceDiagram` visualizing end-to-end MCP client invocation, stdio transport, argument validation, engine seam routing (bundled SQLite vs canonical), error gating, and local JSON-RPC response lifecycle.
- **Core Capabilities & Security Invariants Matrix**: Added comprehensive English and German comparison table detailing 100% Local-First / Zero-Egress, strict fail-closed engine seams (`MODE-CONTRACT.md`), `agent_id` team-memory provenance, credential-free discovery, unprivileged operation, and multi-OS smoke coverage.
- **Expanded Partner & Desktop Ecosystem**: Cross-linked 16 sibling and partner repositories across `open-bricks`, `file-bricks`, `doc-bricks`, `dev-bricks`, and `ellmos-ai` (FileCommander, CodeCommander, Clatcher, n8n Manager, ControlCenter, ServerCommander, Blender Use, Open Compute, ProFiler, DokuZen, PDFtoPDFocr, KnowledgeDigest, DevCenter, CodeBox, MemoryHooker, sqlite-transit-sync).
- **Shields.io Badges**: Synchronized Python matrix (3.10–3.13), Platforms (Linux, Windows, macOS), Privacy (100% Local-First | Zero-Egress), Storage (SQLite WAL), and verified test status (108 passed | 100%).
- **Machine-Readable LLM Context**: Synchronized `llms.txt` Last-checked timestamp to `2026-08-24` and referenced security policy and sequence lifecycle.

### Security & CI Matrix
- **Security Policy SLA & Channels**: Enhanced `SECURITY.md` with explicit 48-hour response SLA, supported version matrix (`0.1.0-alpha.x`), private advisory links, and dedicated reporting emails (`security@ellmos.ai`, `support@lukasgeiger.com`).
- **CI Workflow Concurrency**: Added `concurrency: { group: ${{ github.workflow }}-${{ github.ref }}, cancel-in-progress: true }` to `.github/workflows/tests.yml` to prevent redundant run queues.
- **PEP 621 Metadata Standards**: Expanded `pyproject.toml` with Python 3.10–3.13 classifiers, OS Independent status, and full `[project.urls]` mapping (`Homepage`, `Documentation`, `Repository`, `Issues`, `Changelog`, `Parent Organization`, `Umbrella Ecosystem`).

### Tests & Quality Assurance
- **Automated Metadata & Contract Tests**: Added 6 new contract tests in `tests/test_metadata.py` verifying Mermaid sequence diagrams, quick navigation anchors, core capability tables, CI concurrency, PEP 621 URLs/classifiers, security SLAs, ecosystem parity, and `package.json` links (108/108 tests passing 100% green).

## 0.1.0-alpha.23 (Hygiene Audit) - 2026-08-21

### CI & Tooling
- **GitHub Actions CI Matrix Hardening**: Updated `.github/workflows/tests.yml` to include Python 3.13 matrix builds alongside Python 3.10, 3.11, and 3.12.
- **Automated Ruff Linting in CI**: Integrated `ruff check .` step directly into the CI pipeline.
- **Standardized PEP 621 `[tool.ruff]` Config**: Added standard `[tool.ruff]` and `[tool.ruff.lint]` configuration in `pyproject.toml` (target Python 3.10, line-length 120, standard import sorting `I`).

### Security & Privacy
- **Bilingual Security Policy**: Expanded `SECURITY.md` with German translation (`Sicherheitsrichtlinie`), explicit Local-First / Zero-Egress SQLite guarantees, and direct reporting channels (`security@ellmos.ai` and GitHub private advisories).

### Tests & Quality Assurance
- **Expanded Metadata & CI Parity Tests**: Added `test_github_actions_workflow_ci_matrix_and_lint` and `test_ruff_config_in_pyproject` to `tests/test_metadata.py` (102/102 passed, 100% green).
- **Import Hygiene**: Standardized and sorted module imports across `src/` and `tests/`.
- **Documentation Parity**: Updated `llms.txt` Last-checked timestamp to `2026-08-21` and test count badge in `README.md` and `README_de.md` to 102 passed.

## 0.1.0-alpha.23 - 2026-08-16

### Security
- **Standardized `SECURITY.md`**: Added explicit security policy establishing local-first SQLite persistence, credential-free model routing and API discovery, bounded offline queue execution, fail-closed canonical engine seams, and strict secret ignore rules.

### Discoverability & Documentation
- **Badges & Metadata**: Updated `README.md` and `README_de.md` with verified test suite status (96 passed, 100% green) and `llms.txt` LLMs-Ready badge.
- **Machine-Readable LLM Index**: Synchronized `llms.txt` Last-checked timestamp to `2026-08-16`.
- **Packaging Parity**: Included `SECURITY.md` in `package.json` package files list.

### Tests & Quality Assurance
- **Automated Metadata & Discoverability Tests**: Extended `tests/test_metadata.py` with test cases verifying `SECURITY.md` existence/contents, package file inclusions, `llms.txt` discoverability markers, and ecosystem cross-references.
- **Test Suite Verification**: All 99 unit, engine-seam, i18n, registry, and repository hygiene tests pass 100% green.

## 0.1.0-alpha.24 - 2026-08-25

### Added
- **Three new canonical-only tool families**: `hb_policy_*` (`resolve`, `list` — delegates to
  `policy-registry`), `hb_ticket_*` (`list`, `show` — reads `_control-center/_TICKETS`
  lifecycle folders via `ticket-master`), `hb_lock_*` (`list`, `check` — reads the systemwide
  lock scan via `lock-master`). All three are read-only in v1 (no `register_rule`, no ticket
  move/write, no lock creation) and belong to a new third category alongside the existing
  `canonical`/`bundled` split: **canonical-only, no bundled fallback at all.** A locally faked
  copy of live policy/ticket/lock state would be actively misleading (unlike `hb_kb_*`/`hb_route_*`,
  which are an honest, smaller standalone reimplementation) — so these three namespaces never
  read `_engine_mode` and fail closed unconditionally when the target module or its data
  location cannot be resolved. Requested via T-20260825-196589547 (HB1=wie-empfohlen).
- `engines.py`: `resolve_tickets_root()`, `load_ticket_master()`, `load_lock_master()`,
  `load_policy_registry()` — same `resolve → import → CanonicalEngineUnavailable-at-call-time`
  shape as the existing seams. `CANONICAL_ONLY` set and an `engine_summary()` branch that
  reports these three as `canonical-only (no bundled alternative for this namespace)` instead
  of a mode string.

### Changed
- **`load_gardener()`/`load_usmc_client_class()` now try `source-resolver` first** (only when no
  explicit `configured_path` is given) before falling back to the existing
  `resolve_engine_path` + `import_from_path` candidate chain. `source-resolver` v0.1.1 confirms
  presence for the `memory.organic` (GARDENER) / `memory.curated` (USMC) roles via a bare
  `shutil.which()` check and returns the CLI path, not a package directory — so the integration
  is a **bare `importlib.import_module()`** on a `RESOLVED` status, not a `sys.path` insert.
  Standalone operation (source-resolver absent or the import fails) falls through unchanged to
  the pre-existing candidate chain — the fail-closed promise for both seams is unaffected.
  `policy.registry` was deliberately **not** wired the same way: that role requires a `scope`
  and its adapter returns resolved *policy content*, not a filesystem location — using it to
  find "where is the package installed" would be a category error.

### Fixed
- **`_DEFAULT_CANDIDATES` for the new `policy`/`ticket`/`lock` engines initially pointed at their
  OneDrive Plan-D projection folders**, mirroring the existing `garden`/`state` pattern. That is
  wrong for these three: `policy-registry`/`ticket-master`/`lock-master` are Plan-D "Klasse B"
  modules whose OneDrive folder holds only `ellmos-module.v2.json` + `README.md` (manifest +
  pointer) — never the real package (verified empirically: `ls` on the OneDrive
  `policy-registry` folder shows exactly those two files, no source). GARDENER/USMC deploy real
  importable code into their OneDrive path (confirmed via a present `__pycache__`); the new
  three do not follow that model. Fixed by pointing `_DEFAULT_CANDIDATES` at the local clone
  (`C:/_Local_DEV/repos/<name>[/src]`) and deliberately **excluding** `policy`/`ticket`/`lock`
  from `_CATALOG_MODULE_IDS` (the module-catalog's `resolved_source` field also points at the
  wrong OneDrive location and takes precedence in `resolve_engine_path`'s candidate order).
- **`~/.policy-registry/registry.json` had 6 entries with `"summary"` stored as a 1-element
  JSON array instead of a string** (root cause: a trailing comma — `(f"...",)` — in an earlier
  session's `register_evidence.py`), which raised `TypeError` inside
  `PolicyRegistry.search()` and was only found because the new `hb_policy_list` end-to-end
  smoke test against the live registry surfaced it. Fixed directly in the live registry file;
  not part of this ticket's original scope, but blocking real verification of the new seam.

### Documentation
- `MODE-CONTRACT.md` §3: three new rows for `hb_policy_*`/`hb_ticket_*`/`hb_lock_*`, all marked
  "Fail-closed IMMER (kein bundled-Modus)", plus a new paragraph naming the third category.
  New §3a "Bewusste Nicht-Seams" documents why `roshambo` (overlaps lock-master, subsumed by the
  choice-bundle mechanism), `session-checkpoint` (private module with its own ADR-001/002
  explaining deliberate isolation — would need its own maintainer to declare a seam adapter
  first) and `grounding-seed` (bootstrap-only, wrong layer) were deliberately not seamed.
- `.AI/.MCP/MCP-STACK-MAP.md`: tool count `~45` → `51`, version bump, 3 new namespace rows in
  the detailed table.

### Maintenance
- Synchronize 0.1.0-alpha.24 / 0.1.0a24 across `package.json`, `package-lock.json`,
  `pyproject.toml`, `src/homebase/__init__.py`, `server.json`, `glama.json`.
- Test suite: 87 passed (20 new — `test_new_seams.py`), `ruff check .` clean. Verified end-to-end
  against the live system, not just mocks: `hb_policy_list` returned 8 real registry entries,
  `hb_ticket_show` resolved a real ticket by ID, `hb_lock_list` returned 20 real active locks
  (a full recursive scan across all configured project roots — takes roughly 2 minutes on this
  machine, a known characteristic of OneDrive-tree scans in this ecosystem, not a bug).

## 0.1.0-alpha.22 - 2026-08-14

### Fixed
- **`hb_state_task_*` (canonical) pointed at a deleted directory.** The default task DB was
  `~/.rinnsal/scanner_tasks.db`, but the task engine was extracted from rinnsal into TASKPLAN
  on 2026-07-11 and its store is `~/.taskplan/taskplan.db`; `~/.rinnsal/` no longer exists.
  Every canonical `hb_state_task_*` call therefore failed with
  `unable to open database file`. The table name `rinnsal_tasks` is unchanged — only the
  database location moved. Reported as T-20260814-01.
- Resolution order is now, most specific first: `[state].task_db_path` → `$TASKPLAN_DB` →
  `$SCANNER_TASKS_DB` (legacy, still honoured) → `~/.taskplan/taskplan.db`. `$TASKPLAN_DB`
  outranks the legacy name because it is the canonical engine's own resolution input:
  relocating the task DB with it must not leave homebase writing into a store no other
  taskplan consumer reads.

### Changed
- **Fail-closed now also covers an unreachable target database, not just an unreachable engine.**
  Previously, if the engine imported but its DB directory was gone, callers got a bare
  `sqlite3.OperationalError` naming neither the tool family, the target, nor a way out —
  the exact gap this bug exposed. `hb_state_task_*` now raises `CanonicalEngineUnavailable`
  with all three. The directory is deliberately not created: an empty `taskplan.db` beside a
  missing store is the second, disconnected database `MODE-CONTRACT.md` exists to prevent.

### Documentation
- `MODE-CONTRACT.md` §3 names the real canonical target (TASKPLAN, `rinnsal_tasks` in
  `~/.taskplan/taskplan.db`), the resolution order and the new unreachable-DB case.
- `config/homebase.example.toml` and `KONZEPT.md` "Engine Seams" corrected accordingly.
- `TODO.md`: filed the remaining divergence — taskplan's own resolution additionally consults
  its config file, which this seam does not read.

### Maintenance
- Synchronize 0.1.0-alpha.22 / 0.1.0a22 across `package.json`, `package-lock.json`
  (was stuck at 0.1.0-alpha.20), `pyproject.toml`, `src/homebase/__init__.py`, `server.json`
  and `glama.json`.
- Test suite: 67 passed (3 new — default target, env precedence, missing-directory fail-closed).


## 0.1.0-alpha.21 - 2026-08-13

### Changed (BREAKING)
- **No silent fallback from `canonical` to `bundled`.** When `[engines].mode` (or
  `[engines.<name>].mode`) is `"canonical"` and the canonical engine cannot be found or
  imported, the affected tool family now raises `CanonicalEngineUnavailable` instead of
  quietly serving the bundled SQLite store. Previously such calls returned
  `"engine": "bundled"` with a success status while writing into a second, disconnected
  database. Affects `hb_garden_*`, `hb_state_task_*` and `hb_mem_*`.
- The bundled store is no longer created at all in that state, so no shadow DB is left behind.
- **Migration:** `[engines].mode` applies to `garden`, `state` and `mem` together. On hosts
  that have only some canonical engines, set `mode = "bundled"` per namespace instead of
  relying on the global setting. See `MODE-CONTRACT.md` §4.

### Added
- `MODE-CONTRACT.md` — binding definition of the `canonical` and `bundled` stack modes, the
  per-namespace seam status, the start-vs-call boundary, and the migration path. Cross-linked
  from KONZEPT.md and shipped in the npm package.
- Error messages name the affected tool family, the unreachable target and both remedies.

### Unchanged (documented, not invented)
- The server still starts and still lists all tools when a canonical engine is missing — the
  rule applies at call time, not at startup.
- `hb_state_mem_*`, `hb_state_dispatch` and `hb_kb_*`/`hb_route_*` have no canonical seam and
  keep working in every mode. A `canonical` request for `kb`/`route` remains a no-op that is
  visible only in the startup summary.

### Maintenance
- Synchronize `llms.txt` Last-checked timestamp to `2026-08-10`.
- Add `open-bricks` ecosystem and `ellmos-ai` organization Shields.io badges in `README.md` and `README_de.md`.
- Verify Pytest test suite (64 passed tests 100% green).

### Discoverability
- Include `glama.json` in npm package contents so validated registry metadata ships with the installable package.
- Refresh the machine-readable `llms.txt` registry index and verification date.
- Remove the unverified legacy `smithery.yaml`; current Smithery publication for local stdio servers requires a validated MCPB bundle.

### Fixed
- Make registry-schema localization assertions use the serialized MCP protocol form, preserving CI coverage across SDK versions that expose different Python attribute aliases.

## 0.1.0-alpha.18 - 2026-07-25

### Added
- GFM LLM note callout box (`> [!NOTE]`) added to `README.md` and `README_de.md` for AI assistant/agent discoverability.
- Mermaid System Architecture diagrams added to `README.md` and `README_de.md` showcasing client transport, core engine, 11 functional tool modules, and local SQLite storage.

### Maintenance & Security
- Remove eight accidentally published `-WORKSTATION-LG` conflict copies; canonical project files remain unchanged.
- Add standard `.gitignore` entry for `-WORKSTATION-LG.gitignore`.
- Synchronize version 0.1.0-alpha.18 / 0.1.0a18 across `package.json`, `package-lock.json`, `pyproject.toml`, `src/homebase/__init__.py`, `server.json`, and `glama.json`.
- Verify Pytest test suite (117 tests passing).

### Changed
- Updated `llms.txt` header to `Last-checked: 2026-07-25`.


## 0.1.0-alpha.17 - 2026-07-24

### Fixed
- Correct FileCommander (46) and CodeCommander (22) tool counts in the ecosystem family table; counts now verified against the live MCP `tools/list` surface.
- Align `pyproject.toml` and `homebase.__version__` with the npm package version (were stuck at 0.1.0a15).

## 0.1.0-alpha.16 - 2026-07-24

### Changed
- Unified the ellmos-ai ecosystem section in README.md and README_de.md: full 9-server MCP family table with refreshed tool counts, AI infrastructure, and desktop software links.
- Added `glama.json` for the Glama MCP directory listing.
- Synced `server.json` version metadata.
- Added the `mcpName` registry field to package.json (io.github.ellmos-ai/ellmos-homebase-mcp).

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
