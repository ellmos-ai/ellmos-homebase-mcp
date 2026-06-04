# ellmos-homebase-mcp

Alpha-MCP-Server für lokale LLM-Orchestrierung: Memory, Knowledge, Routing, Schwarmmuster, API-Probing, persistenter Zustand, Tests und spätere Automatisierung in einem stdio-Server.

Englische Standard-README: [README.md](README.md)

## Status

- Transport: stdio über das Python-MCP-SDK
- Paketstatus: öffentliches Alpha-Paket unter `ellmos-ai`
- Aktiver Kern: Modul-Discovery, MCP-Tool-Liste, MCP-Tool-Dispatch, Config-Fallbacks
- Echte lokale SQLite-Module: `hb_mem_*`, `hb_kb_*`, `hb_garden_*`, `hb_state_*`
- i18n: lokalisierte MCP-Tool-Beschreibungen für `en`, `de`, `es`, `zh`, `ja`, `ru` mit Englisch-Fallback
- Roadmap: echte Adapter für Routing, Schwarm, API-Probing, Tests, Automatisierung, Connectors und Plugins

## Installation

Das npm-Paket enthält einen Node-Wrapper, der den Python-Server startet. Voraussetzung bleibt Python 3.10+ mit installiertem Python-Paket `mcp>=1.0.0`.

```powershell
npm install -g ellmos-homebase-mcp@alpha
ellmos-homebase
```

Für lokale Entwicklung:

```powershell
cd "C:\Users\User\OneDrive\.TOPICS\.AI\.MCP\ellmos-homebase-mcp"
$env:PYTHONIOENCODING = "utf-8"
python -m pip install -e ".[dev]"
python -m pytest -q
```

Keine `.venv` im OneDrive-Ordner anlegen. Falls eine isolierte Umgebung gebraucht wird, außerhalb von OneDrive erstellen.

## Start Aus Dem Quellbaum

```powershell
$env:PYTHONPATH = "src"
python -m homebase.server
```

## Konfiguration

Beispiel: [config/homebase.example.toml](config/homebase.example.toml)

Standardpfade:

- `%USERPROFILE%\.homebase\homebase.toml`
- `%USERPROFILE%\.config\homebase\homebase.toml`
- Override per `HOMEBASE_CONFIG`

Die Sprache kann über `[server].language`, `HOMEBASE_LANG` oder `HOMEBASE_LOCALE` gesetzt werden.

```toml
[server]
name = "ellmos-homebase"
language = "de" # en, de, es, zh, ja, ru

[modules]
enabled = ["mem", "route", "kb", "swarm", "state", "garden", "api", "test"]
```

Module mit fehlenden optionalen Dependencies werden beim Laden übersprungen, ohne den Serverstart zu blockieren.

## Tools

Wichtige Tool-Gruppen:

- `hb_mem_*` für SQLite-Memory
- `hb_kb_*` für SQLite-Knowledge
- `hb_state_*` für persistenten SQLite-Zustand und Tasks
- `hb_garden_*` für den kleinen SQLite-Garden-Store
- `hb_api_*` für API-Exploration
- `hb_test_*` für Selbsttests
- `hb_route_*` und `hb_swarm_*`, wenn `requests` verfügbar ist

## Entwicklung

```powershell
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONDONTWRITEBYTECODE = "1"
python -m pytest -q
npm run smoke
npm pack --dry-run
```

Der nächste sinnvolle Schritt ist, die verbleibenden Draft-Handler für Routing, Schwarm, API-Probing und Test-Orchestrierung durch echte credential-freie Adapter mit Tests zu ersetzen.
