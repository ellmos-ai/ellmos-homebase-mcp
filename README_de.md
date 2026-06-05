# ellmos-homebase-mcp

<p align="center">
  <img src="assets/homebase-logo.jpg" alt="ellmos Homebase MCP Logo" width="640">
</p>

Alpha-MCP-Server für lokale LLM-Orchestrierung: Memory, Knowledge, Routing, Schwarmmuster, API-Probing, persistenter Zustand, Tests und spätere Automatisierung in einem stdio-Server.

Englische Standard-README: [README.md](README.md)

*Teil der [ellmos-ai](https://github.com/ellmos-ai)-Familie.*

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![npm version](https://img.shields.io/npm/v/ellmos-homebase-mcp.svg)](https://www.npmjs.com/package/ellmos-homebase-mcp)
[![Python](https://img.shields.io/badge/python-%3E%3D3.10-blue.svg)](https://www.python.org/)
[![Node.js](https://img.shields.io/badge/node-%3E%3D18-brightgreen.svg)](https://nodejs.org/)
[![MCP](https://img.shields.io/badge/MCP-stdio-blueviolet.svg)](https://modelcontextprotocol.io/)
[![Status: alpha](https://img.shields.io/badge/status-alpha-orange.svg)](https://www.npmjs.com/package/ellmos-homebase-mcp)

**Auffindbarkeit:** Veröffentlicht auf [npm](https://www.npmjs.com/package/ellmos-homebase-mcp) als `ellmos-homebase-mcp` und gepflegt in der Organisation [`ellmos-ai`](https://github.com/ellmos-ai).

## Status

- Transport: stdio über das Python-MCP-SDK
- Paketstatus: öffentliches Alpha-Paket unter `ellmos-ai`
- Aktiver Kern: Modul-Discovery, MCP-Tool-Liste, MCP-Tool-Dispatch, Config-Fallbacks, lokale Planungs- und Probing-Adapter
- Echte lokale SQLite-Module: `hb_mem_*`, `hb_kb_*`, `hb_garden_*`, `hb_state_*`
- Credential-freie Alpha-Adapter: `hb_route_*`, `hb_swarm_*`, `hb_api_*`, `hb_test_*`
- i18n: lokalisierte MCP-Tool-Beschreibungen, Input-Schema-Feldbeschreibungen und Unknown-Tool-Fehler für `en`, `de`, `es`, `zh`, `ja`, `ru` mit Englisch-Fallback
- Roadmap: Backend-Ausführungsadapter für Automatisierung, Connectors, Plugins und optionale echte LLM/API-Integrationen

## Installation

Das npm-Paket enthält einen Node-Wrapper, der den Python-Server startet. Voraussetzung bleibt Python 3.10+ mit installiertem Python-Paket `mcp>=1.0.0`.

### Option 1: Installation per npm

```powershell
npm install -g ellmos-homebase-mcp@alpha
ellmos-homebase
```

### Option 2: Installation aus dem Quellcode

```powershell
git clone https://github.com/ellmos-ai/ellmos-homebase-mcp.git
cd ellmos-homebase-mcp
$env:PYTHONIOENCODING = "utf-8"
python -m pip install -e ".[dev]"
python -m pytest -q
```

Keine `.venv` in cloud-synchronisierten Ordnern anlegen, wenn der Sync-Client Dateien sperrt. Falls eine isolierte Umgebung gebraucht wird, außerhalb dieses Ordners erstellen.

## Start Aus Dem Quellbaum

```powershell
$env:PYTHONPATH = "src"
python -m homebase.server
```

## MCP-Client-Konfiguration

### Globale npm-Installation

```json
{
  "mcpServers": {
    "homebase": {
      "command": "ellmos-homebase"
    }
  }
}
```

### Quellcode-Checkout

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

`/absolute/path/to/ellmos-homebase-mcp` durch den eigenen lokalen Checkout-Pfad ersetzen.

## Server-Konfiguration

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
- `hb_route_*` für credential-freie Modell-Routing-Empfehlungen und Feedback-Statistiken
- `hb_swarm_*` für credential-freie Schwarm-Planungsmuster
- `hb_api_*` für passive HTTP-API-Discovery mit SQLite-Historie
- `hb_test_*` für eingebaute Metadata- und Smoke-Selbsttests

## Entwicklung

```powershell
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONDONTWRITEBYTECODE = "1"
python -m pytest -q
npm run smoke
npm pack --dry-run
```

Der nächste sinnvolle Schritt ist, die verbleibenden Automatisierungs-, Connector- und Plugin-Module an credential-freie lokale Adapter anzubinden und optionale Ausführungsbackends nur explizit konfiguriert zu aktivieren.
