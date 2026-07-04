# ellmos-homebase-mcp — Entwicklungsziele (TODO)

> Stand: 2026-06-17. Diese Datei hält die strategische Entwicklungsrichtung fest, damit
> homebase gezielt zum **gemeinsamen Gedächtnis des KI-Teams** (Claude, Codex, Gemini, Kimi,
> lokale LLMs via BACH/Buddha) ausgebaut wird. Grundlage: Vergleichsanalyse der drei
> Shared-Memory-Ansätze (BACH-Shared-Memory, USMC, homebase) vom 2026-06-17.
>
> **Leitentscheidung:** homebase ist der **Zugangsträger** (MCP = zero-setup, in jeder Session
> jedes MCP-Agenten sofort verfügbar, immun gegen das Silo-Problem der `.md`-Hubs). Damit es
> ein echtes *Team*-Gedächtnis wird, fehlen ihm aber drei Dinge, die USMC/BACH schon haben:
> Provenance, Concurrency-Sicherheit und automatisches Vergessen. Die nachfolgenden Ziele
> schließen diese Lücken — in Prioritätsreihenfolge.

---

## P0 — Multi-Agent-Grundlagen (ohne diese ist es kein Team-Gedächtnis)

- [x] **Provenance / `agent_id` in allen Memory-Tabellen.**
      Aktuell hat `memory.py`/`knowledge.py`/`state.py` keine Autor-Spalte → man weiß nicht,
      welcher Agent was geschrieben hat. Für ein geteiltes Gedächtnis ist „wer sagt das" ein
      Kernmerkmal. Schema um `agent_id TEXT` erweitern, in jedem `*_store`/`*_set` setzen,
      in `*_query`/`*_context` filterbar machen.
      → Vorbild: USMC (`UNIQUE(agent_id, category, key)`), BACH `shared_memory_*` (`agent_id`,
      `namespace`, `visibility`).
      Erledigt 2026-06-18: `hb_mem_*`, `hb_kb_*` und `hb_state_*` schreiben und filtern
      `agent_id`; `state_memory` nutzt `(agent_id, key)` als eindeutige Kombination und
      migriert ältere Alpha-Datenbanken automatisch.

- [x] **Concurrency-Härtung in `storage.py`.**
      `sqlite3.connect(path)` läuft ohne WAL und ohne `busy_timeout` → bei zwei gleichzeitig
      schreibenden Agenten drohen „database is locked"-Fehler. Setzen:
      `PRAGMA journal_mode=WAL;`, `connect(..., timeout=…)` bzw. `PRAGMA busy_timeout`.
      Gilt für alle acht `~/.homebase/*.db`.
      Erledigt 2026-06-18: `connect_db()` setzt `timeout=30.0`, `PRAGMA journal_mode=WAL`,
      `PRAGMA busy_timeout=30000` und `PRAGMA foreign_keys=ON`.

- [ ] **`hb_mem` auf USMC als Backend umstellen, statt eigener Reimplementierung.**
      Die `KONZEPT.md` nennt USMC als Quelle, der Code reimplementiert die Memory aber selbst.
      Stattdessen `usmc.USMCClient` als Storage-Engine einbinden → erbt automatisch `agent_id`,
      Confidence-Merge, `get_changes_since()` (Delta-Sync) und die 50 grünen Tests.
      Homebase liefert dann nur noch den MCP-Wrapper. Das ist die saubere Schichtung:
      **USMC = Engine, homebase = MCP-Frontend.**
      → Voraussetzung: USMC vorher als Dependency paketieren (PyPI-Publish oder vendored).

## P1 — Gegen Overflow + tatsächliche Nutzung

- [x] **Automatisches Decay / Konsolidierung (`hb_mem_consolidate`) — Basis erledigt 2026-06-27.**
      Neues Tool: senkt Confidence pro Eintrag um `decay` und prunt Einträge unter `min_confidence`
      (dry_run-Preview + Apply, agent-filterbar, getestet). Damit fallen Einträge mit sinkender
      Confidence von selbst heraus → wirkt dem „unsichtbaren Overflow" entgegen.
      **Offen (P2-Ausbau):** zeit-/altersbasiertes Decay und Facts→Lessons-Verdichtung
      (Vorbild BACH `system/hub/consolidation.py`).

- [ ] **Lifecycle-Verdrahtung — der eigentliche Grund, warum heute alle drei DBs leer sind.**
      Kein Tool nützt, wenn es nicht automatisch befüllt/gelesen wird. Drei Hooks definieren
      (clientseitig dokumentieren, da ein MCP-Server nicht selbst proaktiv injizieren kann):
      - [ ] Auto-Load beim Session-Start (`hb_mem_context` früh aufrufen) — in **allen**
            Session-Typen, nicht nur Home (sonst lebt das Silo-Problem weiter).
      - [ ] Write beim Session-Ende (Facts/Lessons/Handoff automatisch ablegen).
      - [ ] Decay periodisch (Cron / Session-Ende).
      → Für Claude Code via `SessionStart`/`Stop`-Hooks; für BACH via Startup/Shutdown-Handler.

- [x] **FTS5 statt LIKE in `hb_kb_search` und `hb_mem_query` (2026-06-27).**
      External-Content-FTS5-Index + Sync-Trigger in `storage.setup_fts()`, Query-Builder
      `storage.fts_match_query()` (Prefix + implizites AND), automatischer **LIKE-Fallback** wenn die
      SQLite-Build kein FTS5 hat. Tests in `test_registry.py`. Offen bleibt nur die optionale
      **semantische/Embedding-Suche** (Stretch-Goal).

- [x] **`hb_mem_merge` echt implementiert (2026-06-27).** `dry_run=false` führt Duplikatgruppen
      (content+category+agent_id) confidence-basiert zusammen: Survivor = höchste Confidence, redundante
      Zeilen gelöscht; idempotent. Unit-Test in `test_registry.py`. (Decay/Konsolidierung bleibt offen, P1.)

## P2 — Erinnerungshilfen: Injektoren als neues Modul (`hb_inject_`)

> Antwort auf die Frage „die Injektoren als Erinnerungshilfen — sollten die nach homebase?":
> **Ja, die Logik — aber mit einer wichtigen Architektur-Nuance.** Ein MCP-Server kann nicht
> von sich aus in den Prompt eines Agenten schreiben; er wird nur auf Anfrage aufgerufen.
> homebase hostet daher die **Auswahllogik** („welche Erinnerung ist bei diesem Trigger
> relevant?"), das eigentliche **Einschieben** macht ein clientseitiger Hook (Claude Code
> `UserPromptSubmit`-Hook bzw. BACHs Wrapper).

> **Strategie-Anschluss (2026-06-17):** Dies ist Cluster 8 „Kognitive Steuerung (Injektoren)"
> aus `.OS/sovereign-private/_concepts/BACH_HANDLER_CLUSTER_UND_ARCHITEKTUR.md` — der **einzige
> Handler-Cluster ohne Modul-Heimat** in der dortigen Deckungsanalyse/Bauplan. Die Extraktion
> folgt der etablierten Linie „**aus BACH generieren, nicht handpflegen**" (`exporter.py` +
> `dist_type`, Richtung BACH→GEN mit Auto-Regen), damit BACH Quelle der Wahrheit bleibt und sich
> das Modul mit BACH mitentwickelt. Diesen Punkt zugleich in der dortigen Substanz-Matrix
> nachtragen (aktuell fehlt Cluster 8 als Zeile).

- [ ] **Injektoren aus BACH als eigenständiges Modul generieren** (Arbeitsname
      z. B. `mnemo` / `recall-injectors`), via BACH `exporter.py`/`skill_export.py` (BACH→GEN,
      Auto-Regen) — NICHT als handgepflegte Parallelkopie. Quelle: `BACH/system/tools/injectors.py`,
      `hub/reminder_injector.py`, `hub/meta_feedback_injector.py`. Enthält:
      StrategyInjector (Trigger-Wort → Hinweis), ContextInjector (Auto-Kontext + Cooldown),
      TimeInjector (Zeit-Updates), BetweenInjector (Post-Task-Reminder),
      ReminderInjector (benutzerdefiniert), MetaFeedbackInjector (LLM-Tick-Korrektur).
      Zero-Dependency halten (wie USMC).

- [ ] **`hb_inject_` Modul in homebase**: `hb_inject_relevant(prompt|trigger)` →
      gibt passende Erinnerungen/Hinweise zurück (liest aus `hb_mem`). `hb_inject_reminder_add`,
      `hb_inject_list`. Das Modul *liefert* Injektionskandidaten; es injiziert nicht selbst.

- [ ] **Referenz-Hook ausliefern**, der `hb_inject_relevant` bei jedem Prompt aufruft und das
      Ergebnis voranstellt (ein Beispiel-Hook für Claude Code, einer für BACH). Erst damit wird
      aus „abrufbarer Memory" eine echte „Erinnerungshilfe".

## P3 — Roadmap (bereits in KONZEPT.md, hier nur referenziert)

- [ ] Phase-2-Module: `hb_auto_` (llmauto, Backend-Abstraktion), `hb_conn_` (connectors aus
      BACH — bereits als `.MODULES/connectors` v1.0.0 extrahiert, einbinden statt neu bauen),
      `hb_plug_` (Plugin-System).
- [ ] Phase 3: npm-Publish, ControlCenter-Integration, Status-Dashboard-Modul.

---

## Qualitäts-Schulden (aus Audit 2026-06-17)

- [ ] Modul-Unit-Tests: `test_registry.py` deckt inzwischen die wichtigsten Modulpfade ab,
      inklusive `agent_id`-Provenance für mem/kb/state; separate Modul-Unit-Tests und
      Migrations-Smokes für alle Module fehlen noch.
- [ ] Doku-Korrektheit: KONZEPT.md verspricht FTS5/semantische Suche/Merge, die der Code
      (noch) nicht hat — angleichen, sobald P1/P2 umgesetzt oder Doku ehrlich machen.
- [ ] Versions-Sync prüfen (package.json / pyproject.toml / server.json / `__version__`).

---

## Modul-Integrations-Audit (2026-06-27)

> Auslöser: Prüfung von 14 `.MODULES`-Kandidaten gegen homebase. Befund:
> Die acht Alpha-Module sind **eigenständige credential-freie Reimplementierungen**
> (verifiziert in `modules/routing.py`, `modules/connectors.py` — kein Import der realen
> `.MODULES`-Pakete). Es gibt also zwei Arbeitslinien: (A) reale `.MODULES`-Engines hinter
> die bestehenden Namespaces ziehen, (B) neue, bisher nicht im KONZEPT geführte Kandidaten
> bewerten/integrieren. Architektur-Entscheidung (Kandidat/abgelehnt) ist in `KONZEPT.md`
> in der Modul-Tabelle nachgetragen — hier stehen nur die ausführbaren Aufgaben.

### A — Bestehende Namespaces: Stub → reale `.MODULES`-Engine (Schichtung „Engine = .MODULES, homebase = MCP-Wrapper")

- [ ] **`hb_route_` auf `.MODULES/clutch` umstellen.** Aktuell reine Heuristik in `routing.py`
      (kein `clutch`-Import). clutch als optionale Routing-Engine einbinden (Epsilon-Greedy,
      Road-Types, Auto-Learning, Budget-Zonen) — credential-frei bleiben, Provider-Calls hinter
      expliziter Konfiguration. Knüpft an P0 (USMC-Schichtung) und P3 an.
      **Geprüft 2026-07-04 (Ticket T-20260704-01):** `Fahrer.kuppeln()` (nach
      `strecke_analysieren()`) ist tatsächlich credential-frei und DB-gestützt (`clutch.db`,
      kein Netzwerk-Call) — grundsätzlich seam-fähig wie Gardener/Rinnsal. Zurückgestellt, weil
      `Fahrer.__init__` eine `config_dir` mit Getriebe-/Kupplungs-/Fahrschule-Konfiguration
      voraussetzt (deutlich mehr Vorarbeit als die anderen beiden Seams). Bleibt bundled-only,
      Server loggt das explizit bei `[engines].mode=canonical`. Folgearbeit, kein neues Ticket
      nötig — hier weiterführen.
- [ ] **`hb_swarm_` auf `.MODULES/swarm_ai` umstellen.** Reale Schwarm-Patterns
      (parallel/consensus/hierarchy/stigmergy) statt Alpha-Stub; Backend konfigurierbar (Ollama-default).
- [ ] **`hb_api_` auf `.MODULES/ApiProber` umstellen.** Reale Probe-/Discovery-Engine (OpenAPI,
      Wordlist, HATEOAS) hinter den Namespace; stdlib-only, daher unkritisch.
- [ ] **`hb_conn_` auf `.MODULES/connectors` v1.0.0 binden** (bereits in P3 vermerkt — hier als
      A-Linie präzisiert: `connectors.py` ist Alpha-Stub ohne Netzwerk; v1.0.0 einbinden statt neu bauen).
- [ ] **`hb_auto_` auf `.MODULES/llmauto` mit Backend-Abstraktion** (Dublette zu P3/`.MCP/TODO`;
      hier nur Querverweis, nicht erneut auflisten).
- [x] **`hb_state_` auf reale `.AI/.OS/rinnsal`-Engine binden.** Erledigt 2026-07-04 (Ticket
      T-20260704-01): `hb_state_task_*` seam-fähig über `[engines.state].mode = "canonical"` →
      echte `rinnsal.tasks.client.TaskClient` (`rinnsal_tasks`-Tabelle). `hb_state_mem_*`/
      `hb_state_dispatch` bleiben bewusst bundled (war nicht Teil des Auftrags). Live-Roundtrip
      gegen die reale Engine verifiziert. Details: KONZEPT.md „Engine Seams".
- [x] **`hb_garden_` auf reale `.AI/.OS/gardener`-Engine binden** (find/get/put/run, eine `everything`-Tabelle
      + FTS5). Erledigt 2026-07-04 (Ticket T-20260704-01): `[engines.garden].mode = "canonical"` →
      echte `gardener.Gardener`; `allow_run`-Gate bleibt bestehen. Live-Roundtrip verifiziert.
      Gardeners FTS5 als Substrat für `hb_kb_`/`hb_mem_query` bleibt offen (siehe `hb_mem_`/`hb_kb_`
      Bundled-only-Vermerk in KONZEPT.md „Engine Seams" — Confidence/Tags-Schema passt nicht 1:1).

> **Bezugsweg + Reihenfolge (Entscheidung 2026-06-27): GitHub-first, PyPI als Endschritt.**
> Die realen Engines werden zunächst **per Install-Zeit-Git-Fetch** bezogen — für ALLE Nutzer, nicht
> nur Eigenbetrieb (`pip install "rinnsal @ git+https://…@<tag>"`). Jedes A-Modul bekommt eine **Seam**
> (reale Engine wenn importierbar, sonst eingebaute Impl.). **Reihenfolge: erst bauen, dann publishen** —
> Seams + Git-Install zuerst, lauffähig machen; **PyPI ist der letzte, koordinierte Schritt**, bei dem
> ALLE Engine-Pakete gemeinsam nachziehen (rinnsal, `ellmos-gardener`, clutch, swarm_ai, USMC), weil
> PyPI keine git-URL-Deps in publizierten Metadaten erlaubt (All-or-nothing). PyPI ist damit **nicht**
> gating. Details: `KONZEPT.md` → „Modul-Bezug / Distribution". (Ersetzt die frühere P0-Annahme
> „erst PyPI-paketieren".)

> **Hinweis Skill-/Config-Infrastruktur (2026-06-27):** Die geprüften Infrastruktur-Skills
> (`agent-config-sync`, `agents-bridge`, `ai-portable-setup`, `mcp-config-sync`, `skill-explorer`,
> `system-onboarding`) sind **ControlCenter-Domäne** (Skill-/MCP-/Config-Erkennung und -Sync), nicht
> homebase. Der gewünschte **Skill-Finder** wurde dort in ROADMAP/TODO ergänzt. homebase bleibt die
> kognitive Backend-Schicht (Memory/Routing/Wissen/State).

### B — Neue Integrationskandidaten (nicht im bisherigen KONZEPT)

- [ ] **`ellmos-agent-bridge` → neuer Namespace `hb_bridge_` / Delegations-Rückgrat (HOCH).**
      Sauberer stdlib-only BACH-Extrakt (Partner-Registry, `ComplexityScorer` 0–100 →
      Modell- + Partner-Empfehlung, Delegation, Health-Checks). Starke Überlappung mit `hb_route_`
      und `hb_swarm_`: kann das Partner-/Delegations-Backbone liefern, das homebase für echtes
      Multi-Agent-Routing fehlt. Prüfen, ob `hb_route_` darauf aufsetzt statt eigener Heuristik.
- [ ] **`llm-note` → Namespace `hb_note_` (MITTEL-HOCH).** Local-first Notiz-Engine (SQLite
      Thought-Log + Notebooks, brainstorm→task), stdlib-only, ebenfalls BACH-Extrakt. Ergänzt
      `hb_mem_`/`hb_kb_` um die „flüchtige Gedanke/Logbuch"-Ebene. Abgrenzung zu `hb_mem_` definieren
      (Note = unkonsolidiert, Memory = konsolidiert), Doppelspeicherung vermeiden.
- [ ] **`lock-master` → Namespace `hb_lock_` (MITTEL).** Portables Multi-Agent-Datei-Lock-System
      (zero-dep, `LOCK*.txt`, Team-Locks, Scan/Prune). homebase ist als *Team*-Gedächtnis gedacht
      (P0 Concurrency) — `hb_lock_check`/`hb_lock_acquire`/`hb_lock_release` würde LLMs erlauben,
      Schreibkollisionen vor `hb_mem_*`-Writes zu koordinieren. Mit dem systemweiten LOCK-System
      (`_scripts/LOCK-SYSTEM.md`) abstimmen, kein zweiter Standard.
- [ ] **`build-your-users-mind` → Namespace `hb_mind_` (MITTEL, an P2-Injektoren koppeln).**
      ToM/Feedback-Präkognition (Vorhersage der User-Reaktion + Konfidenz, Eskalation bei 🔴).
      Architektur-Nuance identisch zu P2: homebase hostet die **Auswahl-/Vorhersagelogik**
      (`hb_mind_predict`, liest aus `hb_mem_`), das **Einschieben** macht ein clientseitiger Hook.
      Gemeinsam mit dem `hb_inject_`-Modul (P2) entwerfen — selbe Schicht.
- [ ] **`ticket-master` → nur Scoring-/Routing-Logik in `hb_state_task_` prüfen (NIEDRIG-MITTEL).**
      ticket-master ist ein *prompt-getriebener Workflow* (kein importierbares Engine-Paket), daher
      NICHT als Modul übernehmen. Aber Intake→Score→Provider-Match-Logik bewerten, ob sie
      `hb_state_task_create/update` um Priorisierung/Provider-Empfehlung anreichern kann.

### C — Bewusst NICHT integrieren (Konsumenten/Deploy/Fremddomäne — Entscheidung, kein offener Task)

- [ ] (Dokumentations-Task) In `KONZEPT.md` festhalten, **warum** diese vier nicht in homebase gehören:
      - **`ellmos-chat`** — backend-agnostische Chat-*Runtime* (ChatRuntime, Tool-Use-Loop). Ist ein
        **Konsument** von homebase-Tools, keine Engine *in* homebase (würde homebase importieren).
      - **`ellmos-core`** — FastAPI/HTMX Web-UI + Auth/RBAC (On-Prem-Suite). **App/Frontend**, das
        homebase später als Backend nutzen könnte — nicht umgekehrt.
      - **`ellmos-stack`** — Self-hosted Deployment-Bundle (Ollama+n8n+Rinnsal+KnowledgeDigest,
        docker-compose). **Komposition/Deployment**; homebase wäre Teil *des Stacks*, nicht andersherum.
      - **`open-compute`** — Computer-Use-Core (Perception→Action GUI-Loop). **Andere Domäne** als
        homebases kognitive Infrastruktur (Memory/Routing/Wissen). Optionales Fernziel `hb_compute_`,
        aber außerhalb des aktuellen Konzepts „Zuhause für obdachlose LLMs".
