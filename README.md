# ellmos-homebase-mcp

<p align="center">
  <img src="assets/homebase-logo.jpg" alt="ellmos Homebase MCP logo" width="640">
</p>

Alpha MCP server for local LLM orchestration: memory, knowledge, routing, swarm patterns, API probing, persistent state, tests, automation planning, and plugin discovery in one stdio server.

German README: [README_de.md](README_de.md)

*Part of the [ellmos-ai](https://github.com/ellmos-ai) family.*

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![npm version](https://img.shields.io/npm/v/ellmos-homebase-mcp.svg)](https://www.npmjs.com/package/ellmos-homebase-mcp)
[![Python](https://img.shields.io/badge/python-%3E%3D3.10-blue.svg)](https://www.python.org/)
[![Node.js](https://img.shields.io/badge/node-%3E%3D18-brightgreen.svg)](https://nodejs.org/)
[![MCP](https://img.shields.io/badge/MCP-stdio-blueviolet.svg)](https://modelcontextprotocol.io/)
[![Status: alpha](https://img.shields.io/badge/status-alpha-orange.svg)](https://www.npmjs.com/package/ellmos-homebase-mcp)
[![Homebase tests](https://github.com/ellmos-ai/ellmos-homebase-mcp/actions/workflows/tests.yml/badge.svg)](https://github.com/ellmos-ai/ellmos-homebase-mcp/actions/workflows/tests.yml)

**Discoverability:** Published on [npm](https://www.npmjs.com/package/ellmos-homebase-mcp) as `ellmos-homebase-mcp` and maintained in the [`ellmos-ai`](https://github.com/ellmos-ai) organization.

## Start Here

| Need | Entry point |
|---|---|
| Install the alpha MCP server | `npm install -g ellmos-homebase-mcp@alpha` |
| Run from a source checkout | `python -m homebase.server` with `PYTHONPATH=src` |
| Configure Claude, Codex, or another MCP client | [MCP Client Configuration](#mcp-client-configuration) |
| Inspect the machine-readable project summary | [llms.txt](llms.txt) |
| Check registry metadata | [server.json](server.json) |

## Status

- Transport: stdio via the Python MCP SDK
- Package status: public alpha package under `ellmos-ai`
- Release metadata: MIT `LICENSE`, `CHANGELOG.md`, `llms.txt`, and MCP Registry metadata in `server.json`
- Test gate: GitHub Actions covers Python 3.10/3.11/3.12 plus Node.js 20/22/24 smoke and npm package checks
- Current core: module discovery, MCP tool listing, MCP tool dispatch, config fallbacks, local planning/probing/queue/dry-run adapters
- Real local SQLite modules: `hb_mem_*`, `hb_kb_*`, `hb_garden_*`, `hb_state_*`
- Credential-free alpha adapters: `hb_route_*`, `hb_swarm_*`, `hb_api_*`, `hb_test_*`, `hb_conn_*`, `hb_auto_*`, `hb_plug_*`
- i18n: localized MCP tool descriptions, input-schema field descriptions, and unknown-tool errors for `en`, `de`, `es`, `zh`, `ja`, `ru` with English fallback
- Roadmap: optional real LLM/API integrations and explicit execution backends

## Install

The npm package contains a Node wrapper that starts the Python server. You still need Python 3.10+ and the Python package `mcp>=1.0.0`.

### Option 1: Install From npm

```powershell
npm install -g ellmos-homebase-mcp@alpha
ellmos-homebase
```

### Option 2: Install From Source

```powershell
git clone https://github.com/ellmos-ai/ellmos-homebase-mcp.git
cd ellmos-homebase-mcp
$env:PYTHONIOENCODING = "utf-8"
python -m pip install -e ".[dev]"
python -m pytest -q
```

Avoid creating a `.venv` inside cloud-synced folders if your sync client locks files. If you need an isolated environment, create it outside that folder.

## Start From Source

```powershell
$env:PYTHONPATH = "src"
python -m homebase.server
```

## MCP Client Configuration

### Global npm Install

```json
{
  "mcpServers": {
    "homebase": {
      "command": "ellmos-homebase"
    }
  }
}
```

### Source Checkout

```json
{
  "mcpServers": {
    "homebase": {
      "command": "python",
      "args": ["-m", "homebase.server"],
      "env": {
        "PYTHONPATH": "/absolute/path/to/ellmos-homebase-mcp/src"
      }
    }
  }
}
```

Replace `/absolute/path/to/ellmos-homebase-mcp` with your local checkout path.

## Server Configuration

Example: [config/homebase.example.toml](config/homebase.example.toml)

Machine-readable project context: [llms.txt](llms.txt)

MCP Registry metadata: [server.json](server.json)

Default paths:

- `%USERPROFILE%\.homebase\homebase.toml`
- `%USERPROFILE%\.config\homebase\homebase.toml`
- override with `HOMEBASE_CONFIG`

Language can be configured with `[server].language`, `HOMEBASE_LANG`, or `HOMEBASE_LOCALE`.

```toml
[server]
name = "ellmos-homebase"
language = "en" # en, de, es, zh, ja, ru

[modules]
enabled = ["mem", "route", "kb", "swarm", "state", "garden", "api", "test", "conn", "auto", "plug"]
```

Modules with missing optional dependencies are skipped without blocking server startup.

## Tools

Important tool groups:

- `hb_mem_*` for SQLite-backed memory
- `hb_kb_*` for SQLite-backed knowledge entries
- `hb_state_*` for persistent SQLite state and tasks
- `hb_garden_*` for a small SQLite garden store
- `hb_route_*` for credential-free model-routing recommendations and feedback stats
- `hb_swarm_*` for credential-free swarm planning patterns
- `hb_api_*` for passive HTTP API discovery with SQLite history
- `hb_test_*` for built-in metadata and smoke self-tests
- `hb_conn_*` for a local connector registry plus SQLite-backed inbox/outbox queues without network sends
- `hb_auto_*` for local automation chain definitions and queued plan-only runs without backend execution
- `hb_plug_*` for local plugin discovery and dry-run records without executing plugin code

## Discovery Context

Use `ellmos-homebase-mcp` when searching for a local-first MCP server that combines SQLite memory, knowledge entries, persistent state, model-routing recommendations, swarm planning, passive API discovery, connector queues, automation-chain planning, and plugin discovery.

Good search phrases:

- `ellmos Homebase MCP server`
- `local-first LLM orchestration MCP`
- `MCP server SQLite memory knowledge routing`
- `offline agent orchestration MCP server`
- `MCP swarm planning persistent state API discovery`

Not the same as Elmo/ELMO voice tools, AllenAI ELMo embeddings, Eclipse LMOS, generic cloud agent platforms, or single-purpose MCP memory servers.

## Development

```powershell
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONDONTWRITEBYTECODE = "1"
python -m pytest -q
npm run smoke
npm pack --dry-run --json
```

Next useful step: add optional execution backends behind explicit configuration.
