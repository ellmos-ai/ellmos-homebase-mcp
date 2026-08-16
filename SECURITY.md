# Security Policy

## Execution Safety and Local-First Guarantees

`ellmos-homebase-mcp` is designed from the ground up as a **local-first, offline-capable** MCP stdio server with strict isolation and zero unexpected side-effects:

1. **Local-First & Offline Storage**: All memory, knowledge, persistent state, garden storage, routing statistics, connector queues, automation plans, and plugin registry entries are stored exclusively in local SQLite databases (default: `.homebase/`). No external cloud storage, telemetry, or remote tracking endpoints are contacted without explicit operator configuration.
2. **Credential-Free Routing & Discovery**: Model routing recommendations (`hb_route_*`), passive API discovery (`hb_api_*`), and plugin discovery (`hb_plug_*`) operate without requiring or exposing API tokens, private keys, or cloud credentials.
3. **No Autonomous Network Execution**: Connector queues (`hb_conn_*`) and automation chains (`hb_auto_*`) operate in plan-and-queue mode. They do not initiate unprompted network traffic or execute external code payloads autonomously.
4. **Fail-Closed Engine Seams**: In stack environments with canonical integration backends, any unreachable or unconfigured engine fails closed with a clear diagnostic tool error rather than silently falling back to unisolated storage.
5. **Data Protection & Secret Hygiene**: Example configuration files (`config/homebase.example.toml`) contain sanitized placeholders. Live configuration files (`homebase.toml`, `config/homebase.toml`, `*.local.toml`, `*.secret.toml`), database files, and private keys are strictly git-ignored and excluded from npm package distribution.

## Supported Versions

| Version | Supported | Notes |
|---|---|---|
| `0.1.0-alpha.x` | :white_check_mark: | Current active release branch |
| `< 0.1.0-alpha.1` | :x: | Legacy preview prototypes |

## Reporting a Vulnerability

If you discover a security issue, unintended network exposure, credential leak, or isolation bypass within `ellmos-homebase-mcp`, please report it privately to the maintainers rather than opening a public issue.
