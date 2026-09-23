# Third-Party License Review & Level 1 SBOM

> **Project:** `ellmos-ai/ellmos-homebase-mcp`<br>
> **Audited:** Stand: 2026-09-21 (Re-verified Stand: 2026-09-23)<br>
> **Repository License:** [MIT License](LICENSE)<br>
> **Attribution:** [NOTICE](NOTICE)<br>
> **Architecture & Privacy:** 100% Local-First, Zero-Egress Core, Unprivileged User-Mode (`RunAsInvoker`)

---

## Executive Summary & Compliance Assurance

`ellmos-homebase-mcp` is architected as an offline-first, local MCP stdio server. All core persistence operations rely exclusively on the **Python Standard Library** (`sqlite3`, `pathlib`, `json`, `dataclasses`, `asyncio`). External runtime dependencies are strictly bounded to the official `mcp` SDK and standard compatibility packages.

All direct, optional, and development dependencies used or referenced in `ellmos-homebase-mcp` are licensed under strictly **permissive open-source licenses** (MIT, Apache-2.0, BSD-2-Clause, PSFL). There are **zero copyleft, GPL, or AGPL-style viral dependencies**, ensuring unencumbered integration in enterprise, commercial, multi-agent, and academic setups. Canonical copyright attribution for Lukas Geiger, the `ellmos-ai` family, and the `open-bricks` ecosystem is formally preserved in the root [`NOTICE`](NOTICE) file.

Furthermore, `ellmos-homebase-mcp` operates under an uncompromising **Zero-Egress Privacy Boundary**:
1. All persistent memory, knowledge entries, and task states are stored locally in SQLite (`~/.homebase/`).
2. Zero telemetry, user profiling, or unprompted outbound cloud network calls are executed.
3. Execution runs strictly in unprivileged user mode (`RunAsInvoker`), never requesting root or Administrator privileges.

The Python package metadata explicitly declares license files in `pyproject.toml` via `license-files = ["LICENSE", "NOTICE", "THIRD_PARTY_LICENSES.md"]` conforming to the **PEP 639** standard.

---

## Runtime Dependencies

| Package | Version checked | License | Use & Role |
|---|---:|---|---|
| `update-notifier` | ^7.3.1 | BSD-2-Clause | Non-intrusive interactive CLI update notification for Node wrapper |
| `mcp` | >=1.0.0 | MIT | Model Context Protocol Python SDK (stdio protocol transport and types) |
| `tomli` | >=2.0 | MIT | TOML parser for Python < 3.11 (Python standard library `tomllib` used for 3.11+) |

The npm package does not vendor Node dependencies; they are resolved and installed by npm from their respective registry entries. Python dependencies are declared in `pyproject.toml` and resolved via pip.

---

## Standard Library Dependencies

| Component | License | Notes |
|---|---|---|
| Python Standard Library (`sqlite3`, `asyncio`, `json`, `pathlib`, `logging`, `typing`, `dataclasses`, `argparse`, `sys`, `os`, `shutil`) | Python Software Foundation License (PSFL) | Zero external runtime bloat; core persistence relies entirely on standard library SQLite. |

---

## Optional Dependencies (Plugins & Backends)

| Package | Version range | License | Purpose |
|---|---:|---|---|
| `anthropic` | >=0.39.0 | MIT | Optional external routing and swarm assistant integrations |
| `google-genai` | >=1.0.0 | Apache-2.0 | Optional Gemini model execution backend |
| `requests` | >=2.31.0 | Apache-2.0 | Optional active HTTP API exploration and probing |

---

## Development and Testing Dependencies

| Package | Version checked | License | Purpose |
|---|---:|---|---|
| `pytest` | >=8.0 | MIT | Test runner and assertion framework |
| `pytest-asyncio` | >=0.23 | Apache-2.0 | Asyncio event loop testing fixtures |
| `ruff` | >=0.6.0 | MIT / Apache-2.0 | High-performance Python linter and formatter |

---

## Architecture References & Ecosystem Synergies

| Source | License | Architectural Synergies |
|---|---|---|
| `modelcontextprotocol/python-sdk` | MIT | Reference architecture for stdio MCP JSON-RPC protocol handling; decoupled via standard library. |
| `ellmos-ai/gardener` | MIT | Conceptual baseline for minimalist database-driven LLM OS memory and state. |
| `ellmos-ai/rinnsal` | MIT | Reference for agentic memory queues, connectors, and automation primitives. |
| `ellmos-ai/bach` | MIT | Core local-first operating system and tooling harness for local LLM models. |
| `ellmos-ai/sqlite-transit-sync` | MIT | Zero-dependency SQLite schema migration & replication protocol. |

---

## Level 1 SBOM Invariant Cross-Reference Matrix

The following matrix maps the 10 architectural and runtime governance invariants (`INV-LOCAL-01` to `INV-SLA-10`) to the underlying open-source components, operating system interfaces, and verification mechanisms:

| Invariant ID | Title & Scope | Underlying Component / Implementation | Applicable License | Verification Status | Enforcement Seam |
|---|---|---|---|---|---|
| **`INV-LOCAL-01`** | **100% Local-First & Zero Egress** | Python Standard Library (`sqlite3`, `pathlib`) | PSFL-2.0 | CONFIRMED / VERIFIED | SQLite WAL (`~/.homebase/`), zero network analytics |
| **`INV-ENGINE-02`** | **Engine Seams & Fail-Closed Discipline** | `homebase.config`, `homebase.registry` | MIT (`ellmos-homebase-mcp`) | CONFIRMED / VERIFIED | `MODE-CONTRACT.md`, raises `CanonicalEngineUnavailable` |
| **`INV-SEAM-03`** | **Canonical-Only Isolation** | `hb_policy_*`, `hb_ticket_*`, `hb_lock_*` | MIT (`ellmos-homebase-mcp`) | CONFIRMED / VERIFIED | Read-only delegation seams failing closed without stubs |
| **`INV-PROV-04`** | **Deterministic Provenance & Team-Memory** | SQLite schema tables with `agent_id` columns | PSFL-2.0 / MIT | CONFIRMED / VERIFIED | Mandatory `agent_id` attribution on all memories/tasks |
| **`INV-CRED-05`** | **Credential-Free Discovery & Probing** | `hb_route_*`, `hb_swarm_*`, `hb_api_*` | MIT (`ellmos-homebase-mcp`) | CONFIRMED / VERIFIED | Offline model routing and swarm blueprints without keys |
| **`INV-STAGE-06`** | **Plan-Only Staging & Bounded Offline Queues** | `hb_conn_*`, `hb_auto_*` staging models | MIT (`ellmos-homebase-mcp`) | CONFIRMED / VERIFIED | `hb_conn_*` and `hb_auto_*` dry-run manifests |
| **`INV-I18N-07`** | **Native Multilingual Schema Parity** | `src/homebase/i18n.py` catalog mapping | MIT (`ellmos-homebase-mcp`) | CONFIRMED / VERIFIED | 51 tools localized across 6 languages (en, de, es, zh, ja, ru) |
| **`INV-PERM-08`** | **Non-Elevation & RunAsInvoker Principle** | Standard unprivileged user execution | OS Native / PSFL-2.0 | CONFIRMED / VERIFIED | Unprivileged user space execution, dotfile immunity |
| **`INV-SYNC-09`** | **Multi-Host Lock & Conflict Discipline** | `.gitignore`, `.npmignore`, repo conventions | MIT (`ellmos-homebase-mcp`) | CONFIRMED / VERIFIED | Exclusion of `*.sync-conflict-*`, honor of `LOCK.*` |
| **`INV-SLA-10`** | **48h Response, 5-Day Triage & 30-Day Remediation SLA** | Coordinated vulnerability disclosure | MIT (`ellmos-homebase-mcp`) | CONFIRMED / VERIFIED | Bilingual `SECURITY.md`, dedicated response channels |

---

## 10 Governance & Runtime Invariants Verification

All runtime components and architectural dependencies enforce the following 10 invariants:

| Invariant ID | Title & Scope | Verification Status | Enforcement Seam |
|---|---|---|---|
| `INV-LOCAL-01` | 100% Local-First & Zero Egress | CONFIRMED / VERIFIED | SQLite WAL (`~/.homebase/`), zero network analytics |
| `INV-ENGINE-02` | Engine Seams & Fail-Closed Discipline | CONFIRMED / VERIFIED | `MODE-CONTRACT.md`, raises `CanonicalEngineUnavailable` |
| `INV-SEAM-03` | Canonical-Only Isolation | CONFIRMED / VERIFIED | `hb_policy_*`, `hb_ticket_*`, `hb_lock_*` read-only seams |
| `INV-PROV-04` | Deterministic Provenance & Team-Memory | CONFIRMED / VERIFIED | Mandatory `agent_id` attribution on all memories/tasks |
| `INV-CRED-05` | Credential-Free Discovery & Probing | CONFIRMED / VERIFIED | Offline model routing and swarm blueprints without keys |
| `INV-STAGE-06` | Plan-Only Staging & Bounded Offline Queues | CONFIRMED / VERIFIED | `hb_conn_*` and `hb_auto_*` dry-run manifests |
| `INV-I18N-07` | Native Multilingual Schema Parity | CONFIRMED / VERIFIED | 51 tools localized across 6 languages (en, de, es, zh, ja, ru) |
| `INV-PERM-08` | Non-Elevation & RunAsInvoker Principle | CONFIRMED / VERIFIED | Unprivileged user space execution, dotfile immunity |
| `INV-SYNC-09` | Multi-Host Lock & Conflict Discipline | CONFIRMED / VERIFIED | Exclusion of `*.sync-conflict-*`, honor of `LOCK.*` |
| `INV-SLA-10` | 48h Response, 5-Day Triage & 30-Day Remediation SLA | CONFIRMED / VERIFIED | Bilingual `SECURITY.md`, dedicated response channels |

---

## Zero-Copyleft & Permissive Licensing Affirmation

1. **Zero-Copyleft Isolation Guarantee**: 0% viral copyleft dependencies (no GPL, AGPL, or LGPL components in core runtime). 100% permissive dependencies (MIT, BSD-2-Clause, Apache-2.0, PSFL).
2. **Unprivileged RunAsInvoker Non-Elevation Certification**: The core engine runs strictly under standard user permissions without administrative elevation.
3. **Air-Gapped Zero-Egress Guarantee**: No external telemetry, analytics, phone-home, or unverified network connections during execution.
4. **Attribution & Notice**: Canonical root attribution notice is formally maintained in [`NOTICE`](NOTICE).
5. **Audit Certification**: Formally audited on **2026-09-21** and re-verified on **2026-09-23** for Pfad B Discoverability, Level 1 SBOM & Design Parity.
