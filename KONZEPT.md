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

### Integrationskandidaten (Audit 2026-06-27, noch nicht beschlossen)

| Namespace | Quelle | Fähigkeit | Status |
|---|---|---|---|
| `hb_bridge_` | ellmos-agent-bridge | Partner-Registry, Complexity-Score → Modell-/Partner-Empfehlung, Delegation | Kandidat (HOCH) — könnte `hb_route_`/`hb_swarm_` als Delegations-Rückgrat unterlegen |
| `hb_note_` | llm-note | Notiz-/Logbuch-Engine (SQLite Thought-Log, Notebooks, brainstorm→task) | Kandidat (MITTEL-HOCH) — ergänzt `hb_mem_`/`hb_kb_`, Abgrenzung nötig |
| `hb_lock_` | lock-master | Multi-Agent-Datei-Locks (`LOCK*.txt`, Team-Locks) für Schreibkoordination | Kandidat (MITTEL) — mit systemweitem LOCK-System abstimmen |
| `hb_mind_` | build-your-users-mind | ToM/Feedback-Präkognition (User-Reaktion vorhersagen) | Kandidat (MITTEL) — selbe Schicht wie `hb_inject_` (P2): Logik in homebase, Injektion clientseitig |
| (kein Modul) | ticket-master | Intake→Score→Provider-Match | Nur Logik-Übernahme prüfen für `hb_state_task_`; kein eigenes Modul (prompt-getriebener Workflow) |

### Bewusst nicht integriert (Audit 2026-06-27)

Diese vier `.MODULES` sind **keine** homebase-Module, weil die Abhängigkeitsrichtung umgekehrt ist
(sie konsumieren homebase oder sind Deployment/Fremddomäne):

- **ellmos-chat** — Chat-*Runtime* (Tool-Use-Loop); **Konsument** der homebase-Tools, keine Engine darin.
- **ellmos-core** — FastAPI/HTMX Web-UI + Auth/RBAC; **App/Frontend**, das homebase als Backend nutzen kann.
- **ellmos-stack** — Self-hosted Deployment-Bundle (Ollama+n8n+Rinnsal+KnowledgeDigest); homebase wäre Teil *des Stacks*.
- **open-compute** — Computer-Use-Core (GUI-Automation); andere Domäne als homebases kognitive Infrastruktur. Optionales Fernziel `hb_compute_`.

## Tool-Katalog (Phase 1)

> **Status-Hinweis (Alpha 0.1.0a12, Stand 2026-06-27) — was der Code HEUTE wirklich tut:**
> Der folgende Katalog beschreibt das Zielbild. Im Alpha gilt:
> - **Suche:** `hb_kb_search` und `hb_mem_query` nutzen jetzt **FTS5** (External-Content-Index + Sync-Trigger,
>   Prefix-Match mit implizitem AND), mit automatischem **LIKE-Fallback**, falls die SQLite-Build kein FTS5 hat
>   (2026-06-27). **Semantische/Embedding-Suche** bleibt Stretch-Goal.
> - **`hb_mem_merge`:** echtes Confidence-Merge implementiert (2026-06-27) — `dry_run=true` zeigt
>   Duplikatgruppen, `dry_run=false` behält pro Gruppe den Survivor mit der höchsten Confidence und
>   löscht die redundanten Zeilen (idempotent, getestet).
> - **Engines:** alle Module sind **eigene credential-freie Implementierungen**, nicht die realen
>   USMC/clutch/Rinnsal/Gardener-Engines (siehe „Modul-Bezug / Distribution").
> - **Ausführung deaktiviert (by design):** `hb_swarm_` (plant, führt nicht aus), `hb_auto_`
>   (zeichnet Ketten auf), `hb_conn_` (lokale In-/Outbox, kein Netzwerk-Send), `hb_plug_`
>   (Discovery + Dry-Run), `hb_garden_run` (nur mit `allow_run=true`).
> Die genannten Punkte sind in TODO.md als P1/A-Linie geführt; dieser Hinweis hält Konzept und
> Code-Realität ehrlich auseinander.

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

### Modul-Bezug / Distribution für Dritt-Nutzer (Entscheidung 2026-06-27)

**Frage:** Bekommen Fremd-Nutzer Rinnsal/Gardener/clutch mitgeliefert, fest verbaut, oder die jeweils
aktuelle GitHub-Version?

**Ist-Stand (Alpha 0.1.0a12):** Komplett **self-contained**. Die acht Module sind eigene,
credential-freie Reimplementierungen in `src/homebase/modules/` und importieren **kein** Fremdmodul
(nur `mcp` + stdlib + `homebase.storage`). Ein `pip install ellmos-homebase-mcp` bzw. `npx ellmos-homebase-mcp`
liefert also genau diese eingebauten Implementierungen — Rinnsal/Gardener/clutch sind heute nur die
**konzeptionellen Quellen**, nichts davon wird gebündelt oder zur Laufzeit geladen.

**Zielmodell — GitHub-first, PyPI als koordinierter Endschritt (Entscheidung 2026-06-27):**

1. **Default = eingebaute Zero-Dependency-Implementierung (Boden).** Jeder Nutzer hat sofort einen
   lauffähigen Server ohne Fremd-Pakete. Bleibt die garantierte Untergrenze.

2. **Primär = reale Engine per GitHub-Install — für ALLE Nutzer, nicht nur Eigenbetrieb.**
   Die echten Engines werden über einen **einmaligen Install-Zeit-Fetch aus GitHub** bezogen (kein
   Laufzeit-Fetch): `pip install "rinnsal @ git+https://github.com/ellmos-ai/rinnsal.git@<tag>"`
   (auf Tag/Commit gepinnt für Reproduzierbarkeit). Das ist der reguläre Bezugsweg auch für Dritte,
   die ohnehin GitHub nutzen — **kein PyPI nötig**. Jedes Modul bekommt eine **Seam**: reale Engine
   importieren wenn vorhanden, sonst die eingebaute Implementierung (`check_dependencies()` +
   Graceful-Degradation sind dafür schon da). Solange homebase **selbst** per Git/npm (nicht PyPI)
   verteilt wird, dürfen seine optionalen Extras git-URL-Dependencies tragen — der GitHub-Weg ist
   damit vollwertig, nicht nur Notbehelf.

3. **Letzter Schritt = PyPI, koordiniert für alle Engines gemeinsam.** Erst **wenn** auf PyPI
   veröffentlicht werden soll, **ziehen alle beteiligten Pakete gemeinsam nach** (rinnsal, gardener →
   ggf. `ellmos-gardener` wegen Namenskollision, clutch, swarm_ai, USMC). Warum „alle zusammen": Ein
   auf PyPI veröffentlichtes Paket darf **keine** git-URL-Dependencies in seinen Metadaten tragen
   (PyPI lehnt „direct references" ab) — d. h. sobald homebase selbst auf PyPI geht, müssen seine
   Engine-Extras bereits dort liegen. PyPI ist deshalb ein **All-or-nothing-Endschritt**, kein
   gradueller. Danach: `pip install ellmos-homebase-mcp[all]`, Updates via `pip install -U`.

4. **Verworfen:** Laufzeit-Fetch bei jedem Start (fragil, bricht offline, untauglich für stdio-MCP)
   und Vendoring als Default (eingefrorene Kopie driftet, dupliziert Lizenz/Attribution). Muss ein
   Modul *doch* gebündelt werden, dann als bewusst gepinnte `_vendor/`-Kopie mit Sync-Aufgabe.

**Reihenfolge (erst bauen, dann publishen):** Zuerst die Modul-Seams + GitHub-Install-Integration
umsetzen und alles lauffähig machen (Schicht 1+2). Die PyPI-Migration (Schicht 3) ist der **letzte
Meilenstein**, keine Vorbedingung — sie blockiert den Bau nicht. PyPI ist damit **nicht** mehr gating
(frühere „Voraussetzung"-Notiz ersetzt).

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
