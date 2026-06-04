# ellmos-homebase-mcp — Konzept

> Ein lokales LLM bindet diesen einen MCP-Server an und hat sofort alles:
> Memory, Routing, Wissen, Schwarm, persistenten Zustand, API-Exploration, Selbsttest, Plugins und Automatisierung.

## Idee

Lokale LLMs (Ollama, Qwen, Llama via BACH/Buddha) haben keine eigene Orchestrierungslogik,
kein Gedächtnis, kein Routing, keine Schwarmfähigkeit. **Homebase** gibt ihnen all das als
einen einzigen MCP-Server — ein Zuhause für obdachlose LLMs.

## Module (aktuell geplant)

| Namespace | Quelle | Fähigkeit | Status |
|---|---|---|---|
| `hb_mem_` | USMC | Persistentes Gedächtnis (facts, lessons, sessions, context-merge) | Phase 1 |
| `hb_route_` | clutch | Intelligentes Model-Routing (Epsilon-Greedy, Road-Types, Provider) | Phase 1 |
| `hb_kb_` | KnowledgeDigest | Wissensdatenbank (FTS5-Suche, Ingest, Abruf) | Phase 1 |
| `hb_swarm_` | swarm_ai | Schwarmkoordination (parallel, consensus, hierarchy, stigmergy) | Phase 1 |
| `hb_state_` | Rinnsal | Persistenter Zustand (Memory-CRUD, Task-CRUD, Connector-Dispatch) | Phase 1 |
| `hb_garden_` | Gardener | Minimaler Knowledge Store (find/get/put/run) | Phase 1 |
| `hb_api_` | ApiProber | API-Discovery und -Exploration (probe, discover, export) | Phase 1 |
| `hb_test_` | ellmos-tests | Selbsttest (Batteries laufen lassen, Ergebnisse abrufen) | Phase 1 |
| `hb_auto_` | llmauto | Automatisierungsketten (Marble-Runs) | Phase 2 — nach Backend-Abstraktion |
| `hb_conn_` | connectors (BACH) | Kanal-Anbindung (Telegram, Discord, HomeAssistant) | Phase 2 — aus BACH extrahieren |
| `hb_plug_` | plugin_system (BACH) | Plugin-Discovery und -Ausführung | Phase 2 — BACH-Version fertigstellen, dann integrieren |

## Tool-Katalog (Phase 1)

### hb_mem_ — Memory (USMC)
- `hb_mem_store` — Fakt/Lesson/Working-Memory speichern
- `hb_mem_query` — Semantisch/keyword-basiert suchen
- `hb_mem_context` — Kompakten Kontext für Prompt-Injection generieren
- `hb_mem_merge` — Confidence-basiert zusammenführen

### hb_route_ — Routing (clutch)
- `hb_route_select` — Prompt analysieren → bestes Modell/Provider empfehlen
- `hb_route_evaluate` — Antwortqualität bewerten (Feedback-Loop)
- `hb_route_stats` — Routing-Statistiken und Lernfortschritt

### hb_kb_ — Knowledge (KnowledgeDigest)
- `hb_kb_search` — FTS5-Volltextsuche in der Wissensdatenbank
- `hb_kb_ingest` — Neues Wissen aufnehmen (URL, Text, Datei)
- `hb_kb_get` — Einzelnen Eintrag mit Metadaten abrufen
- `hb_kb_list` — Kategorien/Tags auflisten

### hb_swarm_ — Schwarm (swarm_ai)
- `hb_swarm_parallel` — Aufgabe in Chunks parallel verteilen
- `hb_swarm_consensus` — Mehrheitsentscheid über mehrere Agenten
- `hb_swarm_hierarchy` — Boss-Worker-Delegation
- `hb_swarm_stigmergy` — Indirekte Koordination über geteilten Zustand

### hb_state_ — State (Rinnsal)
- `hb_state_mem_get` / `hb_state_mem_set` — Rinnsal-Memory CRUD
- `hb_state_task_list` / `hb_state_task_create` / `hb_state_task_update` — Task-Management
- `hb_state_dispatch` — Connector-Nachricht senden (wenn Connector konfiguriert)

### hb_garden_ — Garden (Gardener)
- `hb_garden_find` — Suchen in der Gardener-DB
- `hb_garden_get` — Eintrag abrufen
- `hb_garden_put` — Eintrag speichern/aktualisieren
- `hb_garden_run` — Gespeicherten Befehl ausführen

### hb_api_ — API-Exploration (ApiProber)
- `hb_api_probe` — URL proben (OpenAPI, Wordlist, HATEOAS)
- `hb_api_discover` — Automatische API-Erkennung
- `hb_api_export` — Ergebnisse als Markdown/JSON exportieren
- `hb_api_history` — Frühere Probes abrufen

### hb_test_ — Selbsttest (ellmos-tests)
- `hb_test_list` — Verfügbare Test-Batteries auflisten
- `hb_test_run` — Battery oder Einzeltest ausführen
- `hb_test_results` — Letzte Testergebnisse abrufen

## Tool-Katalog (Phase 2 — Roadmap)

### hb_auto_ — Automatisierung (llmauto)
- `hb_auto_list_chains` — Verfügbare Marble-Run-Ketten auflisten
- `hb_auto_run` — Kette starten (mit konfigurierbarem Backend)
- `hb_auto_status` — Laufende Kette prüfen
- `hb_auto_result` — Kettenergebnis abrufen
- **Voraussetzung:** Backend-Abstraktion (aktuell Claude-CLI-hardcoded → beliebiger API-Endpunkt)

### hb_conn_ — Connectors (aus BACH)
- `hb_conn_send` — Nachricht über Kanal senden (Telegram, Discord, HA, ...)
- `hb_conn_receive` — Letzte Nachrichten von Kanal abrufen
- `hb_conn_list` — Konfigurierte Kanäle auflisten
- `hb_conn_status` — Kanal-Status prüfen
- **Voraussetzung:** connectors-Modul aus BACH extrahieren (aktuell nur README+TODO)

### hb_plug_ — Plugins (aus BACH)
- `hb_plug_list` — Installierte Plugins auflisten
- `hb_plug_run` — Plugin ausführen
- `hb_plug_info` — Plugin-Metadaten abrufen
- `hb_plug_discover` — Neue Plugins im Verzeichnis finden
- **Voraussetzung:** Plugin-System in BACH fertigstellen, dann Kern extrahieren

## Architektur

```
ellmos-homebase-mcp/
├── src/homebase/
│   ├── server.py          # MCP-Server Entry Point
│   ├── config.py          # Zentrale Konfiguration (homebase.toml)
│   ├── registry.py        # Modul-Auto-Discovery + Graceful Degradation
│   └── modules/
│       ├── __init__.py    # ModuleBase ABC
│       ├── memory.py      # hb_mem_  (USMC)
│       ├── routing.py     # hb_route_ (clutch)
│       ├── knowledge.py   # hb_kb_  (KnowledgeDigest)
│       ├── swarm.py       # hb_swarm_ (swarm_ai)
│       ├── state.py       # hb_state_ (Rinnsal)
│       ├── garden.py      # hb_garden_ (Gardener)
│       ├── api.py         # hb_api_  (ApiProber)
│       ├── testing.py     # hb_test_ (ellmos-tests)
│       ├── automation.py  # hb_auto_ (llmauto)       [Phase 2]
│       ├── connectors.py  # hb_conn_ (BACH)          [Phase 2]
│       └── plugins.py     # hb_plug_ (BACH)          [Phase 2]
├── config/
│   └── homebase.example.toml
├── tests/
└── pyproject.toml
```

### Entkopplungsprinzip

Jedes Modul ist ein eigenständiges Python-Package. Fehlende Dependencies deaktivieren
nur das betroffene Modul — der Server startet trotzdem. Bei Start:

1. Registry scannt `modules/` nach Klassen die `ModuleBase` implementieren
2. Jedes Modul meldet seine Required-Dependencies
3. Registry prüft Verfügbarkeit → registriert nur funktionierende Module
4. Log zeigt: "Loaded: mem, route, kb, garden, api, test | Skipped: swarm (anthropic not installed)"

### Konfiguration

Eine zentrale `homebase.toml`:

```toml
[server]
name = "ellmos-homebase"
host = "localhost"
port = 0  # stdio default

[modules]
enabled = ["mem", "route", "kb", "swarm", "state", "garden", "api", "test"]

[mem]
db_path = "~/.homebase/memory.db"

[route]
providers = ["ollama", "anthropic", "openai"]
default_provider = "ollama"
ollama_endpoint = "http://localhost:11434"

[kb]
db_path = "~/.homebase/knowledge.db"

[swarm]
backend = "ollama"
endpoint = "http://localhost:11434"
model = "qwen3.5:35b-a3b"

[state]
db_path = "~/.homebase/rinnsal.db"

[garden]
db_path = "~/.homebase/garden.db"

[api]
db_path = "~/.homebase/probes.db"
timeout = 10

[test]
test_root = "~/.homebase/tests/"
```

## Quellmodule und ihre Pfade

| Modul | Quellpfad | Sprache | LoC | Dependencies |
|---|---|---|---|---|
| USMC | `.MODULES/USMC/` | Python | ~800 | stdlib |
| clutch | `.MODULES/clutch/` | Python | ~2000 | anthropic, google-genai, requests |
| KnowledgeDigest | `.MODULES/KnowledgeDigest/` | Python | ~4800 | stdlib (+ optional LLM) |
| swarm_ai | `.MODULES/swarm_ai/` | Python | ~3000 | anthropic, requests |
| Rinnsal | `.AI/.OS/rinnsal/` | Python | ~2000 | stdlib |
| Gardener | `.AI/.OS/gardener/` | Python | ~500 | stdlib |
| ApiProber | `.MODULES/ApiProber/` | Python | ~1500 | stdlib |
| ellmos-tests | `.MODULES/ellmos-tests/` | Python | ~1850 | stdlib |
| llmauto | `.MODULES/llmauto/` | Python | ~1200 | stdlib (+ Claude CLI) |
| connectors | BACH `connectors/` | Python | ~500 (geplant) | stdlib |
| plugin_system | BACH | Python | TBD | stdlib |

## Phasen

### Phase 1: Kernmodule
8 Module, alle bereits funktionsfähig. Integration = Import + MCP-Tool-Wrapper.
Vorarbeiten: clutch Provider-Config externalisieren, swarm Backend konfigurierbar machen,
KnowledgeDigest LLM-Summarisierung optional machen, Rinnsal selektiv exponieren.

### Phase 2: Erweiterungen
3 Module, die Vorarbeit in anderen Projekten brauchen:
- **llmauto:** Backend von Claude CLI auf konfigurierbaren Endpoint abstrahieren
- **connectors:** Aus BACH extrahieren (aktuell nur Planungsdokumente, Code in BACH vorhanden)
- **plugin_system:** In BACH fertigstellen, dann Kern nach Homebase portieren

### Phase 3: Ökosystem
- npm-Publish als `ellmos-homebase-mcp`
- Integration in ControlCenter (Homebase-Module als Resources sichtbar)
- Dashboard-Modul für Status aller Module
