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

- [ ] **Automatisches Decay / Konsolidierung (`hb_mem_consolidate`).**
      Entscheidend gegen „unsichtbaren Overflow": eine DB, die still alles ansammelt, verlagert
      das Müll-Problem der `.md`-Dateien nur dorthin, wo es niemand sieht. Einträge müssen mit
      der Zeit / sinkender Confidence von selbst herausfallen, Facts zu Lessons verdichten.
      → Vorbild: BACH `system/hub/consolidation.py` (produktiv erprobt; USMC hat nur
      Confidence-Scores, kein Decay).

- [ ] **Lifecycle-Verdrahtung — der eigentliche Grund, warum heute alle drei DBs leer sind.**
      Kein Tool nützt, wenn es nicht automatisch befüllt/gelesen wird. Drei Hooks definieren
      (clientseitig dokumentieren, da ein MCP-Server nicht selbst proaktiv injizieren kann):
      - [ ] Auto-Load beim Session-Start (`hb_mem_context` früh aufrufen) — in **allen**
            Session-Typen, nicht nur Home (sonst lebt das Silo-Problem weiter).
      - [ ] Write beim Session-Ende (Facts/Lessons/Handoff automatisch ablegen).
      - [ ] Decay periodisch (Cron / Session-Ende).
      → Für Claude Code via `SessionStart`/`Stop`-Hooks; für BACH via Startup/Shutdown-Handler.

- [ ] **FTS5 statt LIKE in `hb_kb_*` und `hb_mem_query`.**
      KONZEPT.md wirbt mit „FTS5-Volltextsuche" und „semantisch/keyword-basiert", der Code nutzt
      aber plain `LIKE`. Entweder FTS5-Virtual-Table nachrüsten oder die Doku ehrlich auf
      Keyword-LIKE korrigieren. Optionale Embedding-Suche als Stretch-Goal.

- [ ] **`hb_mem_merge` echt implementieren (aktuell nur Dry-Run/Preview).**
      Für Konfliktauflösung zwischen Agenten nötig, sobald `agent_id` da ist.

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
