# ellmos-homebase-mcp

<p align="center">
  <img src="assets/homebase-logo.jpg" alt="ellmos Homebase MCP Logo" width="640">
</p>

Alpha-MCP-Server für **local-first LLM-Orchestrierung**: Memory, Knowledge, Routing, Schwarmmuster, API-Probing, persistenter Zustand, Tests, Automatisierungsplanung und Plugin-Discovery in einem stdio-Server.

Homebase ist primär für **lokale LLMs** (Ollama, Qwen, Llama oder beliebige lokal gehostete Modelle über eine MCP-fähige Harness) konzipiert. Alle persistenten Daten werden per SQLite ohne Cloud-Abhängigkeit gespeichert. Externe LLM-Anbieter (Claude, Codex, Gemini, OpenAI) können sich ebenfalls als MCP-Clients verbinden, aber lokale, offline-fähige Setups sind das primäre Zielszenario.

Englische Standard-README: [README.md](README.md)

*Teil der [ellmos-ai](https://github.com/ellmos-ai)-Familie.*

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![npm version](https://img.shields.io/npm/v/ellmos-homebase-mcp.svg)](https://www.npmjs.com/package/ellmos-homebase-mcp)
[![Python](https://img.shields.io/badge/python-%3E%3D3.10-blue.svg)](https://www.python.org/)
[![Node.js](https://img.shields.io/badge/node-%3E%3D18-brightgreen.svg)](https://nodejs.org/)
[![MCP](https://img.shields.io/badge/MCP-stdio-blueviolet.svg)](https://modelcontextprotocol.io/)
[![Status: alpha](https://img.shields.io/badge/status-alpha-orange.svg)](https://www.npmjs.com/package/ellmos-homebase-mcp)
[![Homebase tests](https://github.com/ellmos-ai/ellmos-homebase-mcp/actions/workflows/tests.yml/badge.svg)](https://github.com/ellmos-ai/ellmos-homebase-mcp/actions/workflows/tests.yml)

**Auffindbarkeit:** Veröffentlicht auf [npm](https://www.npmjs.com/package/ellmos-homebase-mcp) als `ellmos-homebase-mcp` und gepflegt in der Organisation [`ellmos-ai`](https://github.com/ellmos-ai).

## Einstieg

| Bedarf | Einstieg |
|---|---|
| Alpha-MCP-Server installieren | `npm install -g ellmos-homebase-mcp@alpha` |
| Aus einem Quellcode-Checkout starten | `python -m homebase.server` mit `PYTHONPATH=src` |
| Lokale LLM-Harness, Claude Code, Codex oder anderen MCP-Client konfigurieren | [MCP-Client-Konfiguration](#mcp-client-konfiguration) |
| Maschinenlesbare Projektzusammenfassung prüfen | [llms.txt](llms.txt) |
| Registry-Metadaten prüfen | [server.json](server.json) |

## Status

- Transport: stdio über das Python-MCP-SDK
- Paketstatus: öffentliches Alpha-Paket unter `ellmos-ai`
- Release-Metadaten: MIT-`LICENSE`, `CHANGELOG.md`, `llms.txt` und MCP-Registry-Metadaten in `server.json`
- Test-Gate: GitHub Actions prüft Python 3.10/3.11/3.12 sowie Node.js 20/22/24 mit Smoke- und npm-Paketchecks
- Aktiver Kern: Modul-Discovery, MCP-Tool-Liste, MCP-Tool-Dispatch, Config-Fallbacks, lokale Planungs-, Probing-, Queue- und Dry-run-Adapter
- Echte lokale SQLite-Module: `hb_mem_*`, `hb_kb_*`, `hb_garden_*`, `hb_state_*`
- Engine-Seams: `hb_garden_*` und `hb_state_task_*` können über `[engines].mode = "canonical"`
  an die echten Gardener-/Rinnsal-Engines delegieren statt an die eingebauten SQLite-Kopien
  (Default bleibt `"bundled"` für eine Zero-Dependency-Installation). Siehe
  [KONZEPT.md](KONZEPT.md#engine-seams-canonicalbundled--umsetzungsstand-2026-07-04-ticket-t-20260704-01).
- Team-Memory-Grundlagen: `agent_id`-Herkunft und Filter für Memory, Knowledge, State-Memory und Tasks; SQLite nutzt WAL plus Busy-Timeout für sicherere parallele Agenten
- Credential-freie Alpha-Adapter: `hb_route_*`, `hb_swarm_*`, `hb_api_*`, `hb_test_*`, `hb_conn_*`, `hb_auto_*`, `hb_plug_*`
- i18n: vollständig lokalisierte MCP-Tool-Beschreibungen, Input-Schema-Feldbeschreibungen und Unknown-Tool-Fehler für `en`, `de`, `es`, `zh`, `ja`, `ru` (Englisch-Fallback für nicht gesetzte Keys)
- Roadmap: optionale echte LLM/API-Integrationen und explizite Ausführungsbackends

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

Homebase nutzt das standardisierte stdio-`mcpServers`-Format. Dasselbe Snippet funktioniert in jedem MCP-fähigen Client oder jeder Harness: BACH/Buddha (lokales Ollama), Claude Code, Codex, Cursor oder einem anderen MCP-Host.

> **Hinweis zu lokalen LLMs:** Eine bare Ollama-Instanz spricht kein MCP nativ — dafür braucht es eine MCP-fähige Harness (z.B. BACH, einen Open-Source-MCP-Proxy oder eine andere Orchestrierungsschicht). Diese Harness wird dann so konfiguriert, dass sie Homebase als MCP-Server einbindet (Snippet unten).

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

Maschinenlesbarer Projektkontext: [llms.txt](llms.txt)

MCP-Registry-Metadaten: [server.json](server.json)

Standardpfade:

- `%USERPROFILE%\.homebase\homebase.toml`
- `%USERPROFILE%\.config\homebase\homebase.toml`
- Override per `HOMEBASE_CONFIG`

Die Sprache kann über `[server].language`, `HOMEBASE_LANG` oder `HOMEBASE_LOCALE` gesetzt werden.
Der schreibende Agent kann pro Tool-Aufruf als `agent_id` übergeben werden; sonst nutzen die Module `HOMEBASE_AGENT_ID`, `AGENT_ID`, eine modulweite `agent_id` oder `unknown`.

```toml
[server]
name = "ellmos-homebase"
language = "de" # en, de, es, zh, ja, ru

[modules]
enabled = ["mem", "route", "kb", "swarm", "state", "garden", "api", "test", "conn", "auto", "plug"]
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
- `hb_conn_*` für eine lokale Connector-Registry plus SQLite-gestützte Inbox-/Outbox-Queues ohne Netzwerksends
- `hb_auto_*` für lokale Automatisierungsketten und queue-basierte Planläufe ohne Backend-Ausführung
- `hb_plug_*` für lokale Plugin-Discovery und Dry-run-Protokolle ohne Plugin-Code auszuführen

## Auffindbarkeitskontext

`ellmos-homebase-mcp` ist der passende Suchanker für einen local-first, offline-fähigen MCP-Server, der lokalen LLMs (Ollama, Qwen, Llama o.ä.) persistentes Gedächtnis, Knowledge-Management, Routing und Orchestrierung gibt — ohne Cloud-Abhängigkeit. Externe LLM-Anbieter können ihn ebenfalls als MCP-Server nutzen, aber lokale Setups sind das primäre Designziel.

Geeignete Suchphrasen:

- `ellmos Homebase MCP server`
- `local-first LLM orchestration MCP`
- `MCP server SQLite memory knowledge routing`
- `offline agent orchestration MCP server`
- `MCP swarm planning persistent state API discovery`

Nicht gemeint sind Elmo-/ELMO-Voice-Tools, AllenAI-ELMo-Embeddings, Eclipse LMOS, generische Cloud-Agent-Plattformen oder einzelne MCP-Memory-Server ohne Orchestrierungsschicht.

## ellmos-ai-Ökosystem

Dieser MCP-Server ist Teil des **[ellmos-ai](https://github.com/ellmos-ai)**-Ökosystems — KI-Infrastruktur, MCP-Server und intelligente Werkzeuge.

### MCP-Server-Familie

| Server | Tools | Fokus | npm |
|--------|-------|-------|-----|
| [FileCommander](https://github.com/ellmos-ai/ellmos-filecommander-mcp) | 46 | Dateisystem, Prozessverwaltung, interaktive Sitzungen, Cloud-Lock-sichere Operationen | [`ellmos-filecommander-mcp`](https://www.npmjs.com/package/ellmos-filecommander-mcp) |
| [CodeCommander](https://github.com/ellmos-ai/ellmos-codecommander-mcp) | 22 | Code-Analyse, JSON-Reparatur, Imports, Diffs, Regex | [`ellmos-codecommander-mcp`](https://www.npmjs.com/package/ellmos-codecommander-mcp) |
| [Clatcher](https://github.com/ellmos-ai/ellmos-clatcher-mcp) | 12 | Dateireparatur, Formatkonvertierung, Batch-Operationen | [`ellmos-clatcher-mcp`](https://www.npmjs.com/package/ellmos-clatcher-mcp) |
| [n8n Manager](https://github.com/ellmos-ai/n8n-manager-mcp) | 18 | n8n-Workflow-Verwaltung über KI-Assistenten | [`n8n-manager-mcp`](https://www.npmjs.com/package/n8n-manager-mcp) |
| [ControlCenter](https://github.com/ellmos-ai/ellmos-controlcenter-mcp) | 20 | MCP-Stack-Discovery, Profilverwaltung, Control Plane | [`ellmos-controlcenter-mcp`](https://www.npmjs.com/package/ellmos-controlcenter-mcp) |
| **[Homebase](https://github.com/ellmos-ai/ellmos-homebase-mcp)** | **45** | **Local-first LLM-Gedächtnis, Wissen, Zustand, Routing, Schwarm-Orchestrierung** | **[`ellmos-homebase-mcp`](https://www.npmjs.com/package/ellmos-homebase-mcp)** (alpha) |
| [ServerCommander](https://github.com/ellmos-ai/ellmos-servercommander-mcp) | 8 | Server-Operationen: Health-Checks, Log-Analyse, Deploy-Dry-Runs, Mail-Diagnose | [`ellmos-servercommander-mcp`](https://www.npmjs.com/package/ellmos-servercommander-mcp) (alpha) |
| [Blender Use](https://github.com/ellmos-ai/ellmos-blender-use-mcp) | 3 | Headless Blender-Asset-QA und FBX-Reimport-Verifikation | [`ellmos-blender-use-mcp`](https://www.npmjs.com/package/ellmos-blender-use-mcp) (alpha) |
| [Open Compute](https://github.com/ellmos-ai/open-compute-mcp) | 10 | Modell-agnostischer Computer-Use: Capture, safety-gated Aktionen, Windows-UIA | [`open-compute-mcp`](https://www.npmjs.com/package/open-compute-mcp) (alpha) |

### KI-Infrastruktur

| Projekt | Beschreibung |
|---------|-------------|
| [BACH](https://github.com/ellmos-ai/bach) | Local-first textbasiertes OS für LLM-Agenten — 113+ Handler, 550+ Tools, SQLite-Memory |
| [open-compute](https://github.com/ellmos-ai/open-compute) | Modell-agnostischer Computer-Use-Kern hinter Open Compute MCP |
| [clutch](https://github.com/ellmos-ai/clutch) | Provider-neutrale LLM-Orchestrierung mit Auto-Routing und Budget-Tracking |
| [rinnsal](https://github.com/ellmos-ai/rinnsal) | Leichte Agent-Memory-, Connector- und Automatisierungsinfrastruktur |
| [ellmos-stack](https://github.com/ellmos-ai/ellmos-stack) | Self-hosted AI Research Stack (Ollama + n8n + Rinnsal + KnowledgeDigest) |
| [MarbleRun](https://github.com/ellmos-ai/MarbleRun) | Autonomes Agent-Chain-Framework für Claude Code |
| [gardener](https://github.com/ellmos-ai/gardener) | Minimalistischer datenbankgetriebener LLM-OS-Prototyp (4 Funktionen, 1 Tabelle) |
| [ellmos-tests](https://github.com/ellmos-ai/ellmos-tests) | Testframework für LLM-Betriebssysteme (7 Dimensionen) |

### Desktop-Software

Unsere Partnerorganisation **[open-bricks](https://github.com/open-bricks)** bündelt KI-native Desktop-Anwendungen: eine moderne Open-Source-Softwaresuite für Datei-, Dokumenten- und Entwicklerwerkzeuge.

## Entwicklung

```powershell
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONDONTWRITEBYTECODE = "1"
python -m pytest -q
npm run smoke
npm pack --dry-run --json
```

Der nächste sinnvolle Schritt ist, optionale Ausführungsbackends nur explizit konfiguriert zu aktivieren.
