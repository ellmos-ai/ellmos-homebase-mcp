# Third-Party License Review

Stand: 2026-09-10.

## Runtime dependencies

| Package | Version checked | License | Use |
|---|---:|---|---|
| `update-notifier` | ^7.3.1 | BSD-2-Clause | Non-intrusive interactive CLI update notification for Node wrapper |
| `mcp` | >=1.0.0 | MIT | Model Context Protocol Python SDK (stdio protocol transport and types) |
| `tomli` | >=2.0 | MIT | TOML parser for Python < 3.11 (Python standard library tomllib used for 3.11+) |

The npm package does not vendor Node dependencies; they are resolved and installed by npm from their respective registry entries. Python dependencies are declared in `pyproject.toml` and resolved via pip.

## Standard Library Dependencies

| Component | License | Notes |
|---|---|---|
| Python Standard Library (`sqlite3`, `asyncio`, `json`, `pathlib`, `logging`, `typing`, `dataclasses`, `argparse`, `sys`, `os`, `shutil`) | Python Software Foundation License (PSFL) | Zero external runtime bloat; core persistence relies entirely on standard library SQLite. |

## Optional Dependencies (Plugins & Backends)

| Package | Version range | License | Purpose |
|---|---:|---|---|
| `anthropic` | >=0.39.0 | MIT | Optional external routing and swarm assistant integrations |
| `google-genai` | >=1.0.0 | Apache-2.0 | Optional Gemini model execution backend |
| `requests` | >=2.31.0 | Apache-2.0 | Optional active HTTP API exploration and probing |

## Development and Testing Dependencies

| Package | Version checked | License | Purpose |
|---|---:|---|---|
| `pytest` | >=8.0 | MIT | Test runner and assertion framework |
| `pytest-asyncio` | >=0.23 | Apache-2.0 | Asyncio event loop testing fixtures |
| `ruff` | >=0.6.0 | MIT / Apache-2.0 | High-performance Python linter and formatter |

## Architecture References & Ecosystem Synergies

| Source | License | Architectural Synergies |
|---|---|---|
| `modelcontextprotocol/python-sdk` | MIT | Reference architecture for stdio MCP JSON-RPC protocol handling; decoupled via standard library. |
| `ellmos-ai/gardener` | MIT | Conceptual baseline for minimalist database-driven LLM OS memory and state. |
| `ellmos-ai/rinnsal` | MIT | Reference for agentic memory queues, connectors, and automation primitives. |
| `ellmos-ai/bach` | MIT | Core local-first operating system and tooling harness for local LLM models. |
| `ellmos-ai/sqlite-transit-sync` | MIT | Zero-dependency SQLite schema migration & replication protocol. |

Implementation note: `ellmos-homebase-mcp` is designed around strict local-first, zero-egress, and non-elevation principles. It vendors no proprietary binaries, embeds no external network telemetry, and uses exclusively permissive open-source licenses (MIT, BSD-2-Clause, Apache-2.0, PSFL).
