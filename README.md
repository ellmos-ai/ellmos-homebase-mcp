# ellmos-homebase-mcp

Alpha-MCP-Server für lokale LLM-Orchestrierung: Memory, Knowledge, Routing, Schwarmmuster, API-Probing, persistenter Zustand, Tests und spätere Automatisierung unter einem Server.

## Status

- Transport: stdio über das Python-MCP-SDK
- Paketstatus: Alpha-Paket, GitHub-Repo unter `ellmos-ai` vorgesehen
- Aktiver Kern: Modul-Discovery, MCP-Tool-Liste, MCP-Tool-Dispatch, Config-Fallbacks
- Echte lokale SQLite-Module: `hb_mem_*`, `hb_kb_*`, `hb_garden_*`, `hb_state_*`
- Noch Roadmap: echte Anbindung der Quellmodule aus `.MODULES`, BACH und Rinnsal

## Installation für lokale Tests

```powershell
cd "C:\Users\User\OneDrive\.TOPICS\.AI\.MCP\ellmos-homebase-mcp"
$env:PYTHONIOENCODING = "utf-8"
python -m pip install -e ".[dev]"
python -m pytest -q
```

Keine `.venv` im OneDrive-Ordner anlegen. Falls eine isolierte Umgebung gebraucht wird, außerhalb von OneDrive erstellen.

## npm Alpha

Das npm-Paket enthält einen Node-Wrapper, der den Python-Server startet. Voraussetzung bleibt Python 3.10+ mit installiertem Python-Paket `mcp>=1.0.0`.

```powershell
npm install -g ellmos-homebase-mcp@alpha
ellmos-homebase
```

## Start

```powershell
ellmos-homebase
```

Oder direkt aus dem Quellbaum:

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

Wenn keine Config existiert, startet der Server mit den Phase-1-Modulen:

```toml
[modules]
enabled = ["mem", "route", "kb", "swarm", "state", "garden", "api", "test"]
```

Module mit fehlenden optionalen Dependencies werden beim Laden übersprungen, ohne den Serverstart zu blockieren.

## Tools

Die aktuelle Alpha registriert die Tool-Definitionen aus den Modul-Wrappern. Die lokalen Speicher-Module arbeiten bereits mit SQLite. Provider-, API- und Orchestrierungs-Module liefern teilweise noch bewusst `[DRAFT]`-Antworten, damit MCP-Clients die Oberfläche testen können, ohne externe LLM-Provider vorauszusetzen.

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
python -m pytest -q
```

Der nächste sinnvolle Schritt ist, die verbleibenden `[DRAFT]`-Handler für Routing, Schwarm, API-Probing und Tests modulweise durch echte Adapter zu ersetzen und pro Adapter einen lokalen, credential-freien Test zu ergänzen.
