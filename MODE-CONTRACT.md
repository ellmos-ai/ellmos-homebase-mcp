# Modus-Vertrag: `canonical` und `bundled`

> Verbindlicher Vertrag für die Engine-Modi von Homebase. Ergänzt KONZEPT.md
> („Engine Seams") um die **Regel**, während KONZEPT.md den **Mechanismus**
> beschreibt. Bei Widerspruch gilt dieses Dokument.
>
> Stand: 2026-08-14 · gültig ab 0.1.0-alpha.21 (Ziel-DB des Task-Seams: alpha.22)

## 1. Die beiden Modi

Homebase ist ein **Stack-MCP** mit genau zwei Betriebsmodi. Der Modus wird pro
Namensraum aufgelöst (`[engines.<name>].mode` schlägt `[engines].mode`).

**`canonical`** — Homebase konsumiert die kanonischen Module des Stacks
(`.MEMORY`-Verbund, clutch und weitere) und delegiert an deren echte Engine und
deren echte Datenbank. Homebase hält in diesem Modus **keinen eigenen Speicher**
für den betroffenen Namensraum.

**`bundled`** — Homebase ist eine abgeschlossene, portable Distribution mit
**explizit eigener DB**. Ein nackter `npx`/`pip install` ohne jede weitere
Software funktioniert vollständig. Dieser Modus ist kein Notbehelf, sondern ein
gleichwertiger, vollwertiger Auslieferungsmodus.

## 2. Die verbindliche Regel

> **`mode = "canonical"` + kanonisches Ziel nicht erreichbar ⇒ Tool-Fehler mit
> klarer Meldung. NIEMALS stiller Wechsel auf `bundled`.**

Begründung (Baukasten-Regel, KONZEPT.md §8): Ein stiller Wechsel legt einen
**zweiten, unverbundenen Speicher** neben den kanonischen Store. Der Aufruf
meldet Erfolg, die Daten landen aber woanders — genau das, was der
`canonical`-Modus verhindern soll. Ein leiser Erfolg am falschen Ort ist
schädlicher als ein lauter Fehlschlag.

`bundled` bleibt jederzeit verfügbar — aber nur, wenn er **gewählt** wurde, nie
als unangekündigter Ersatz.

### Abgrenzung: Start vs. Aufruf

Die Regel gilt auf **Aufrufebene**, nicht beim Start:

| Zeitpunkt | Verhalten |
|---|---|
| Serverstart | Server startet **immer**. Modul lädt, Tools werden gelistet. Ein `ERROR` nennt den unerreichbaren Namensraum. |
| Tool-Aufruf | Betroffene Tool-Familie wirft `CanonicalEngineUnavailable` (MCP-`isError`). |

So bleibt die Zusage aus KONZEPT.md („der Server startet in jedem Fall")
erhalten, ohne den stillen Fallback zu behalten. Zusätzlich wird die bundled-DB
in diesem Zustand **gar nicht erst angelegt** — es entsteht keine Schattendatei.

Die Fehlermeldung nennt immer drei Dinge: betroffene Tool-Familie, gesuchtes
Ziel (Pfad und geprüfte Fundorte) und die zwei Auswege (Pfad korrigieren oder
`bundled` explizit wählen).

## 3. Seam-Status je Namensraum

| Namensraum | Kanonisches Ziel | Seam | Verhalten bei `canonical` + unerreichbar |
|---|---|---|---|
| `hb_garden_*` | GARDENER | **implementiert** | Fail-closed (alle 4 Tools) |
| `hb_state_task_*` | TASKPLAN (`taskplan.client.TaskClient` über die stabile Fassade `rinnsal.tasks.client`), Tabelle `rinnsal_tasks` in `~/.taskplan/taskplan.db` | **implementiert** | Fail-closed (3 Tools) |
| `hb_mem_*` | USMC | **implementiert** | Fail-closed (alle 5 Tools) |
| `hb_kb_*` | KnowledgeDigest | **offen** | Kein Seam — bleibt bundled, siehe unten |
| `hb_route_*` | clutch | **offen** | Kein Seam — bleibt bundled, siehe unten |
| `hb_policy_*` (read-only: `resolve`/`list`) | policy-registry (`policy_registry.PolicyRegistry`) | **implementiert, canonical-only** | Fail-closed IMMER (kein bundled-Modus existiert für diesen Namensraum) |
| `hb_ticket_*` (read-only: `list`/`show`) | `_control-center/_TICKETS`-Baum (Presence-Check über ticket-master, Lesezugriff direkt auf die Lifecycle-Ordner) | **implementiert, canonical-only** | Fail-closed IMMER (kein bundled-Modus) |
| `hb_lock_*` (read-only: `list`/`check`) | lock-master (`lock_scan`/`lock_status`) | **implementiert, canonical-only** | Fail-closed IMMER (kein bundled-Modus) |
| `hb_state_mem_*`, `hb_state_dispatch` | — | kein Ziel | Immer bundled, per Definition |
| `hb_swarm_*`, `hb_api_*`, `hb_test_*`, `hb_auto_*`, `hb_conn_*`, `hb_plug_*` | — | bundled by design | Immer bundled |

**Gating je Tool-Familie, nicht je Modul.** `state` trägt zwei Familien: nur
`hb_state_task_*` ist gegated; `hb_state_mem_*` und `hb_state_dispatch` hatten
nie ein kanonisches Gegenstück und bleiben in jedem Modus nutzbar.

**`hb_policy_*`/`hb_ticket_*`/`hb_lock_*` sind eine DRITTE Kategorie, weder
"implementiert" (garden/state/mem) noch "offen/bundled" (kb/route)
[T-20260825-196589547].** Diese drei Namensräume haben **kein bundled-Modus
zum Herunterfallen** — es gibt keine sinnvolle "kleinere, aber ehrliche"
lokale Kopie einer lebenden Policy-/Ticket-/Lock-Wahrheit (anders als bei
kb/route, wo eine kleinere Ersatzimplementierung immerhin ein eigenständig
nützliches Werkzeug ist). Eine leere/veraltete homebase-lokale Kopie sähe wie
eine echte Antwort über den aktuellen Governance-/Koordinationsstand aus,
wäre es aber nicht — das ist gefährlicher als ein klar fehlgeschlagener
Aufruf. `_engine_mode` wird von diesen drei Modulen daher gar nicht gelesen
(dieselbe "keine Umschaltung existiert"-Form wie bei kb/route, nur
umgekehrt: kb/route ignorieren `canonical` und bleiben bundled; diese drei
ignorieren `bundled` und bleiben canonical-only). v1-Scope ist bewusst
read-only: kein `hb_policy_register`/`register_rule` (Registry-Schreibpfad
existiert seit D2-R2 Stufe 1, ist hier aber ohne belegten Bedarf nicht
exponiert), kein `hb_ticket_move`/`create`, kein `hb_lock_create` — Locks
werden geprüft, nicht gesetzt.

## 3a. Bewusste Nicht-Seams

Aus der Lücken-Analyse (T-20260825-196589547) waren sechs weitere Module
Kandidaten; drei davon wurden bewusst NICHT geseamt:

- **roshambo** — überschneidet sich mit lock-master (`control.locks`) und ist
  laut Systemaudit bereits als choice-Bundle-Alternative zu lock-master
  legitimiert. Ein zweiter, paralleler `hb_*`-Namensraum für dieselbe Rolle
  würde die Auswahl, welche Locking-Implementierung gilt, aus dem
  choice-Bundle-Mechanismus heraus- und stillschweigend in Homebase
  hineinverlagern.
- **session-checkpoint** — `visibility: private`, `development`-Reifegrad;
  eigene ADRs (ADR-001/002) erklären bewusste Isolation ("ein State-Owner,
  nie in die DB einer anderen App schreiben", "keine Abhängigkeit der
  Bequemlichkeit halber"). Ein Homebase-Seam wäre ein von Homebase
  aufgezwungener externer Anschluss, den das Modul selbst nicht vorsieht.
  Falls gewünscht: session-checkpoints eigener Maintainer müsste zuerst einen
  Seam-Adapter deklarieren (Symmetrie zum policy-registry/decision-clicker-
  Präzedenzfall in dessen `ARCHITECTURE.md`).
- **grounding-seed** — Bootstrap-/Onboarding-Primitive
  (`bootstrap.standalone/self-knowledge/migration`), kein wiederholt
  abgefragter Laufzeitbestand. Passt nicht zum Stack-MCP-Zweck (Tools, die
  ein Agent während der Arbeit wiederholt aufruft), sondern zu einer
  einmaligen Setup-Phase davor.

**source-resolver/system-explorer** waren ebenfalls Kandidaten, wurden aber
nicht als neue `hb_*`-Namensräume behandelt, sondern als Umbau von Homebases
eigener interner Pfadauflösung — siehe Abschnitt 2 der Analyse und die
`_try_source_resolver_bare_import()`-Integration in `engines.py` für
`garden`/`mem`.

**Ziel-DB von `hb_state_task_*`.** Der Tabellenname `rinnsal_tasks` blieb bei der
Extraktion von TASKPLAN aus Rinnsal (2026-07-11) absichtlich stehen; die
**Datenbank** ist seither `~/.taskplan/taskplan.db`. Auflösung, spezifischstes
zuerst: `[state].task_db_path` → `$TASKPLAN_DB` → `$SCANNER_TASKS_DB` (Legacy,
benannte die stillgelegte `_tasks`-Scanner-Queue unter `~/.rinnsal/`) →
`~/.taskplan/taskplan.db`. `$TASKPLAN_DB` steht **vor** dem Legacy-Namen, weil es
die Auflösungs-Eingabe der kanonischen Engine selbst ist — wer damit die Task-DB
verlegt, darf nicht dazu führen, dass ausgerechnet Homebase in einen Speicher
schreibt, den kein anderer taskplan-Konsument liest.

**Fail-closed gilt auch für eine unerreichbare Ziel-DB.** Bis 0.1.0-alpha.21 war
nur die *Engine* gegated: Ließ sie sich importieren, zeigte der Zielpfad aber ins
Leere, kam ein nacktes `sqlite3.OperationalError: unable to open database file`
zurück — ohne Tool-Familie, ohne Ziel, ohne Ausweg. Seit 0.1.0-alpha.22 wirft die
Familie in diesem Fall `CanonicalEngineUnavailable` mit denselben drei Angaben.
Das Verzeichnis wird bewusst **nicht** angelegt: eine frische leere
`taskplan.db` wäre genau der zweite, unverbundene Speicher, den dieser Vertrag
verhindert.

**`hb_mem_merge` / `hb_mem_consolidate`** sind bundled-only *Fähigkeiten* (USMC
kennt keine Bulk-Hygiene) und melden unter erreichbarem `canonical`
`not_supported`. Ist `canonical` dagegen **unerreichbar**, sind auch sie
fail-closed: sonst würden sie Zeilen in der falschen Datenbank löschen.

**`kb` und `route`:** Hier gibt es keinen stillen Fallback, weil es keine
Umschaltung gibt — die Module lesen `_engine_mode` gar nicht. Ein
`mode = "canonical"` für sie wird also **stillschweigend ignoriert**, sichtbar
nur im Startlog (`engine_summary()`: `bundled-only (canonical requested, no seam
implemented yet)`). Das ist ein offener Punkt, kein Fail-closed-Fall; solange
kein Seam existiert, wird hier bewusst kein Verhalten erfunden.

## 4. Breaking Change ab 0.1.0-alpha.21

Bis 0.1.0-alpha.20 lieferten `hb_garden_*`, `hb_state_task_*` und `hb_mem_*` bei
unerreichbarem kanonischem Ziel still ein Ergebnis aus der bundled-DB
(`"engine": "bundled"`, Status `ok`/`stored`). Ab 0.1.0-alpha.21 werfen sie
stattdessen einen Fehler.

**Wen das trifft:** `[engines].mode` wirkt global auf `garden`, `state` **und**
`mem`. Wer global `canonical` gesetzt hat, aber nur einen Teil der kanonischen
Engines auf der Platte hat (z. B. GARDENER ja, USMC/Rinnsal nein), sieht die
bisher „funktionierenden" Namensräume jetzt fehlschlagen. Das ist die
beabsichtigte Semantik: Diese Aufrufe haben vorher in die falsche DB
geschrieben.

**Migration** — pro Namensraum entscheiden, statt global zu schalten:

```toml
[engines]
mode = "canonical"

[engines.garden]
mode = "canonical"           # GARDENER ist vorhanden

[engines.mem]
mode = "bundled"             # kein USMC auf diesem Host -> bewusst bundled

[engines.state]
mode = "bundled"             # kein Rinnsal auf diesem Host -> bewusst bundled
```

Wer die bisherige Vermischung tatsächlich will, wählt `bundled` explizit — der
Unterschied ist, dass die Wahl jetzt sichtbar in der Konfiguration steht.

## 5. Bekannte Kante

`engine_summary()` (Startlog) liest die **Konfiguration**, nicht den aufgelösten
Zustand. Es meldet daher `garden=canonical`, auch wenn die Engine unerreichbar
ist und Aufrufe fehlschlagen. Die danebenstehende `ERROR`-Zeile nennt den
tatsächlichen Zustand. Bewusst nicht geändert, um den Startbericht in diesem
Schritt nicht umzubauen.
