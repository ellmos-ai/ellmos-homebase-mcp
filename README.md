# ellmos-homebase-mcp

<p align="center">
  <img src="assets/homebase-logo.jpg" alt="ellmos Homebase MCP logo" width="360">
</p>

Alpha MCP server for local LLM orchestration: memory, knowledge, routing, swarm patterns, API probing, persistent state, tests, and later automation in one stdio server.

German README: [README_de.md](README_de.md)

## Status

- Transport: stdio via the Python MCP SDK
- Package status: public alpha package under `ellmos-ai`
- Current core: module discovery, MCP tool listing, MCP tool dispatch, config fallbacks
- Real local SQLite modules: `hb_mem_*`, `hb_kb_*`, `hb_garden_*`, `hb_state_*`
- i18n: localized MCP tool descriptions for `en`, `de`, `es`, `zh`, `ja`, `ru` with English fallback
- Roadmap: real adapters for the remaining routing, swarm, API, testing, automation, connector, and plugin modules

## Install

The npm package contains a Node wrapper that starts the Python server. You still need Python 3.10+ and the Python package `mcp>=1.0.0`.

```powershell
npm install -g ellmos-homebase-mcp@alpha
ellmos-homebase
```

For local development:

```powershell
cd "C:\Users\User\OneDrive\.TOPICS\.AI\.MCP\ellmos-homebase-mcp"
$env:PYTHONIOENCODING = "utf-8"
python -m pip install -e ".[dev]"
python -m pytest -q
```

Do not create a `.venv` inside a OneDrive-synced folder. If you need an isolated environment, create it outside OneDrive.

## Start From Source

```powershell
$env:PYTHONPATH = "src"
python -m homebase.server
```

## Configuration

Example: [config/homebase.example.toml](config/homebase.example.toml)

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
enabled = ["mem", "route", "kb", "swarm", "state", "garden", "api", "test"]
```

Modules with missing optional dependencies are skipped without blocking server startup.

## Tools

Important tool groups:

- `hb_mem_*` for SQLite-backed memory
- `hb_kb_*` for SQLite-backed knowledge entries
- `hb_state_*` for persistent SQLite state and tasks
- `hb_garden_*` for a small SQLite garden store
- `hb_api_*` for API exploration
- `hb_test_*` for self-tests
- `hb_route_*` and `hb_swarm_*` when `requests` is available

## Development

```powershell
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONDONTWRITEBYTECODE = "1"
python -m pytest -q
npm run smoke
npm pack --dry-run
```

Next useful step: replace the remaining draft handlers for routing, swarm, API probing, and test orchestration with real credential-free adapters and tests.
