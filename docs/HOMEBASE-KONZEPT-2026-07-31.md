# Homebase-Konzept: Config + Heim-Modi

**Ticket:** T-20260731-11 | **Stand:** 2026-07-31 | **Status:** KONZEPT (noch nicht implementiert)
**Auslöser:** User-Entscheidung D4 (2026-07-31): „homebase braucht ein Konzept … eine Art Config
und verschiedene Modi."

> Homebase ist „ein Zuhause für obdachlose LLMs" (siehe KONZEPT.md). Dieses Dokument definiert,
> was dieses Zuhause ist, wenn es **neben einem bestehenden lokalen Home** (dem kanonischen
> ellmos-Stack aus Gardener, USMC, task-master/TASKPLAN, clutch) existiert: fünf Beziehungs-Modi,
> eine Config, in der sie eingestellt werden — auch dialogisch durch den Assistenten — und
> Entscheidungs-Flows für den Fall, dass beide Homes auf einem System aufeinandertreffen.
> **Kernregel: Bei Koexistenz wird der Nutzer zur Entscheidung aufgefordert. Es gibt kein
> stilles Default-Verhalten.**

---

## 1. Begriffe

| Begriff | Bedeutung |
|---|---|
| **Lokales Home** | Der kanonische Stack auf einem Rechner: Gardener (`~/.gardener/gardener.db` System + `~/.gardener/user.db` User), USMC (`~/.usmc/usmc_memory.db`), task-master (`~/.rinnsal/scanner_tasks.db`), clutch. Verbindlich gemäß `~/OneDrive/SYSTEM-MANIFEST.md` §3.2. |
| **Homebase-Home** | Die Instanz dieses MCP-Servers mit ihren eigenen Stores unter `~/.homebase/` (bundled) bzw. ihren Engine-Seams auf das lokale Home (canonical). |
| **Modus** | Die konfigurierte Beziehung zwischen Homebase-Home und lokalem Home. Fünf Werte, siehe Kapitel 4. |
| **Koexistenz** | Homebase läuft auf einem System, auf dem zusätzlich ein lokales Home erkennbar ist. |
| **Autorität** | Der Store, der im Konfliktfall gewinnt bzw. als „die Wahrheit" gilt. |

---

## 2. Fund: Das alte BACH-Konzept (Basis und Bezug)

Recherche read-only in `.TOPICS/.AI/.OS/BACH` (User-Lock `buildweek-no-push` beachtet; `bach.py`
wurde **nicht** ausgeführt — alle Help-Texte liegen statisch unter `system/docs/help/*.txt` und
sind Deckungsgleich mit dem, was `bach help <thema>` ausgibt; die BACH-Suchseite selbst ist der
FTS5-Handler `bach search` bzw. das Tool `tools/bach_db_viewer.py` auf SQLiteViewer-Basis — für
diese Recherche nicht nötig, da die Help-Texte als Dateien vorliegen).

**Fundstellen:**

| Fundstelle | Inhalt |
|---|---|
| `.dev/docs/INSTALL_KONZEPT.md` (2026-02-19, ENT-28) | Drei-Säulen-Installation (SCRIPT / LLM-TASKS / USER); Installations-Varianten Fresh Start / **New Home** / Selective Migrate / Update; offene Frage: „Wie geht portable-bach.md (USB-Stick) mit dem Installationskonzept zusammen?" |
| `.dev/docs/HQ7_NEUINSTALLATION_KONZEPT.md` (2026-02-21) | Variante B „New Home": neue Installation, bestehende DB migrieren (`setup.py --migrate-db`); Variante C „Selective Migrate": interaktiver Wizard mit Preview + Bestätigung (`bach migrate select`). Status: KONZEPT, nicht implementiert. |
| `system/docs/help/install.txt` + `setup.txt` + `system/hub/setup.py` | „BACH hat **eine** Installation. Nach der Installation entscheiden Konfigurationsoptionen über das Deployment-Szenario": Single-System (**Default**) / Multi-System mit OneDrive-ProSync / Server-Headless. Konfiguriert per `bach setup prosync --multi-system/--single-system`, Flag `data/config/db_sync_enabled`. |
| `system/docs/help/db_sync.txt` + `system/hub/bach_paths.py` | ProSync: lokale DB pro System (`~/.bach/bach.db`, lokal autoritativ), OneDrive-Ordner als Transit-Hub (`.SYNC/bach_db_transit/`), Pull bei Start / Push bei Exit, Last-Write-Wins per Timestamp mit Heartbeat-Konflikt-Check (5-Min-Fenster), **Secrets werden aus Backups entfernt**. |
| `system/docs/help/identity.txt` | `system_identity`-Tabelle (Singleton): `instance_id` (UUID), `instance_name`, `current_mode` — jede Instanz ist unterscheidbar. |
| `system/docs/help/modes.txt` | 4 Startup-Modi (gui/text/dual/silent), persistent in `user_config.json`, dauerhaft per Befehl oder einmalig per Flag setzbar. |
| `system/docs/help/mount.txt` / `bach_user_mounts.txt` | User-Mounts: externe Speicher (NAS, USB, Cloud) per Junction/Symlink einbinden, in DB persistiert, `restore` nach Umzug. |
| `system/docs/help/user_sync.txt` | Bidirektionale Sync-Semantik mit Richtung je Lifecycle (Startup: Datei→DB, Shutdown: DB→Datei). |

**Kernaussagen (5):**

1. **Eine Installation, Verhalten per Config.** BACH kennt keine harten Installationsvarianten,
   sondern Szenarien, die über Konfigurationsoptionen gewählt werden; der Default ist immer der
   sicherste Modus (single-system, ProSync aus).
2. **„New Home" ist ein Migrationsfall, kein Betriebsmodus.** Neue Umgebung + bestehende Daten =
   Schema-Migration + Pfad-Anpassung; selektive Übernahme nur per Wizard mit Preview und
   ausdrücklicher Bestätigung (HQ7, nie implementiert).
3. **Lokale Autorität + Transit statt Live-Teilung.** ProSync: jedes System besitzt seine lokale
   DB; Synchronisation läuft über Snapshot-Dateien durch einen Transit-Ordner (pull bei Start,
   push bei Exit), Merge per Last-Write-Wins mit Heartbeat-Konflikt-Check.
4. **Privacy-Grenze ist hart kodiert:** Secrets werden aus den Sync-Backups entfernt, bevor etwas
   den lokalen Speicher verlässt.
5. **Identität ist Voraussetzung für Mehr-Instanz-Betrieb:** `instance_id`/`instance_name` pro
   Installation; das USB-Stick-Szenario („portable-bach") blieb in BACH eine offene Frage.

**Übernahme / Abweichung für homebase:** siehe Kapitel 8.

---

## 3. Config-Schema

Ort: `~/.homebase/homebase.toml` (bestehender Config-Mechanismus `src/homebase/config.py`;
unbekannte Sektionen landen unverändert in `HomebaseConfig.raw`, die `[home]`-Sektion ist also
ohne Schema-Bruch ergänzbar). ENV-Override: `HOMEBASE_CONFIG` für den Dateipfad, künftig
`HOMEBASE_HOME_MODE` für den Modus.

```toml
# --- Home / Heim-Modus (Konzept T-20260731-11) ---
[home]
# Der Beziehungsmodus zum lokalen Home. Default = "lonely" (sicherster Modus,
# analog BACH single-system). Wird NIE still geändert.
mode = "lonely"            # lonely | landed | second | little_brother | portable

# Instanz-Identität (Vorbild BACH system_identity): wird beim ersten Start
# erzeugt und macht dieses Home unterscheidbar/adressierbar.
instance_id = ""           # UUID, auto-generiert wenn leer
instance_name = ""         # Default: "homebase@<HOSTNAME>"

[home.coexistence]
# Erkennung eines lokalen Homes beim Server-Start.
detect = true              # prüft ~/.gardener/, ~/.usmc/, ~/.rinnsal/
# Verhalten bei Erkennung: "ask" ist der einzige Default und fragt den Nutzer
# (LLM-dialogisch oder beim nächsten Start). "ignore" ist nur als explizite,
# vom Nutzer gesetzte Festlegung erlaubt — nie als Fallback.
on_detect = "ask"          # ask | ignore   (Default: ask — kein stilles Default)
# Die getroffene Entscheidung (LANDED-Modus, Kapitel 5.2):
decision = "unset"         # unset | sync | offload | import_export | search_takeover

[home.sync]
direction = "none"         # none | push | pull | bidirectional
transport = "export_file"  # export_file | sync_slot | direct_attach
# export_file: Snapshot-Paket (empfohlen, Vorbild ProSync-Transit)
# sync_slot:   über einen Slot in ~/OneDrive/.SYNC/ (Manifest §5)
# direct_attach: ATTACH auf die Home-DBs (nur read, nur lokal)
conflict = "ask"           # ask | last_write_wins (nur mit Log + Heartbeat-Check)
scope = ["mem", "kb"]      # welche homebase-Stores überhaupt syncfähig sind
auto_on_start = false      # Pull beim Start (Vorbild ProSync); Default aus
auto_on_exit = false       # Push beim Beenden; Default aus

[home.privacy]
# Privacy-Grenzen gemäß SYSTEM-MANIFEST §3.1 (Gardener-Trennung System/User):
# Was den lokalen Speicher verlässt, enthält standardmäßig KEINE Personendaten.
export_personal = false    # true nur nach expliziter Nutzerentscheidung
secrets = "never"          # Secrets/Credentials: nie exportieren/synchronisieren
                           # (Vorbild ProSync: Secrets werden aus Backups entfernt)
privacy_guard = true       # Personendaten-Filter vor jedem Export
                           # (Analogie zu _scripts/gardener_privacy_guard.py)
```

**Leitplanken des Schemas:**

- **Laufzeitdaten nie in OneDrive** (SYSTEM-MANIFEST §4, Prinzip 3): Live-DBs von homebase bleiben
  unter `~/.homebase/`. Über `sync_slot` wandern ausschließlich Export-Snapshots, keine SQLite-/
  WAL-Dateien im laufenden Betrieb.
- **Der Modus gehört der Instanz, nicht dem Modul.** `[engines]` (bundled/canonical) bleibt davon
  unberührt und orthogonal: `mode = "landed"` + `decision = "offload"` *empfiehlt* `canonical`-
  Seams, erzwingt sie aber nicht implizit (siehe Kapitel 5.2).
- **Default ist immer der sicherste Zustand** (Vorbild BACH): `lonely`, `direction = "none"`,
  `export_personal = false`, `auto_* = false`.

---

## 4. Die fünf Modi

### 4.1 LONELY HOME — strikt getrennt

Homebase ist das einzige Home bzw. bleibt bewusst für sich. **Kein Austausch** mit einem lokalen
Home: keine Synchronisation, kein Import, kein Export, keine Reads über die Grenze.

- `direction = "none"`, Erkennung darf laufen (`on_detect = "ask"`), aber die Antwort des Nutzers
  auf „lokales Home gefunden" ist hier bereits gesetzt: Koexistenz ignorieren.
- Autorität: Homebase-Stores (`~/.homebase/`).
- Zweck: Fremd-/Dritt-Installationen, Testsysteme, bewusste Trennung von Welten.
- **Das ist der Default.**

### 4.2 LANDED ON BIGGER HOME — das USB-Stick-Bild

Homebase „landet" auf einem System, das bereits ein lokales Home hat (Erkennung:
`~/.gardener/`, `~/.usmc/`, `~/.rinnsal/` vorhanden und nicht leer). Wie ein USB-Stick, der an
einen eingerichteten Rechner gesteckt wird, **meldet homebase die Lage und fordert zur
Entscheidung auf** — beim ersten Start nach Erkennung, dialogisch über den verbundenen
Assistenten, sonst beim nächsten Aufruf. Vier Optionen:

| `decision` | Bedeutung | Technik |
|---|---|---|
| `sync` | **Synchronisation**: beide Homes gleichen sich regelmäßig ab. | `[home.sync] direction = "bidirectional"`, Transport `export_file`/`sync_slot`, Konfliktregel `ask` (oder `last_write_wins` nur mit Log). Vorbild ProSync. |
| `offload` | **Alles auf die Home-Module auslagern**: homebase hält selbst keine Bestände mehr, sondern arbeitet auf den kanonischen Modulen. | Empfehlung `[engines] mode = "canonical"` für `garden`, `state`, `mem`; bundled-Stores werden archiviert, nicht weiter beschrieben. |
| `import_export` | **Import und Export nach Bedarf**: gezielte, einzelne Übernahmen in beide Richtungen, jeweils mit Preview + Bestätigung. | `hb_home_export` / `hb_home_import` (Kapitel 6) auf Nutzeranweisung; Vorbild HQ7 „Selective Migrate". |
| `search_takeover` | **Gezielte Suchen mit Übernahme**: suchen in den lokalen Modulen, Treffer gezielt in homebase übernehmen. | Read-only `direct_attach` auf Home-DBs + einzelne, bestätigte `put`-Operationen; kein Bulk. |

Ohne getroffene Entscheidung (`decision = "unset"`) verhält sich homebase wie `lonely` und
**fragt erneut** — es richtet keinen Datenfluss ein.

### 4.3 SECOND HOME — gleichberechtigt

Homebase steht **neben** dem lokalen Home als ebenbürtige zweite Instanz. Beide Homes sind
autoritativ für ihren Bereich; Abgleich ist bidirektional und peer-to-peer (kein Master).

- `direction = "bidirectional"`, `conflict = "ask"`; `last_write_wins` nur mit Heartbeat-Check
  und Merge-Log (Vorbild ProSync, 5-Minuten-Fenster).
- Identität entscheidet: `instance_id`/`instance_name` beider Seiten werden in jeder
  Sync-Quittung festgehalten (wer hat was wann geliefert).
- Zweck: dauerhafter Zwei-System-Alltag (z. B. Workstation + Laptop), wo kein Home „das große"
  ist.

### 4.4 LITTLE BROTHER — liefert überwiegend AN das lokale Home

Homebase ist der kleinere Bruder: es sammelt und arbeitet lokal, **liefert seine Ergebnisse
überwiegend an das lokale Home ab** (Richtung: homebase → Home). Der umgekehrte Weg ist
Ausnahme (Referenz-Reads, gezielte Abfragen).

- `direction = "push"`; `auto_on_exit = true` ist hier erlaubt (Push der angebrochenen
  Ergebnisse beim Beenden, weiterhin ohne Secrets und mit Privacy-Guard).
- Autorität für übernommene Daten liegt danach beim lokalen Home; homebase behält seine Kopie
  als Arbeitsstand.
- Zweck: Satelliten-Systeme, temporäre Arbeitsumgebungen, „unterwegs sammeln, zuhause
  einliefern".

### 4.5 PORTABLE HOME — gezielt Wissen einsammeln für anderswo

Homebase ist die transportable Hülle: es **sammelt gezielt Wissen ein, das an einem anderen
Ort gebraucht wird** — kuratiert, nicht vollständig. Der Modus ist auf das Ausfüllen eines
Export-Auftrags ausgerichtet: Was gesammelt wird, wird markiert (Scope), am Ende als Paket
schnürbar und an ein Ziel-Home übergebbar.

- `direction = "none"` im Dauerzustand; Export ist ein **Ereignis** (Paket schnüren), kein
  Dauer-Sync.
- `[home.sync].scope` bestimmt, welche Stores überhaupt aufgenommen werden; `privacy_guard`
  läuft beim Schnüren immer (Personendaten nur nach expliziter Freigabe).
- Zweck: Wissen von A nach B tragen (Vortrag, zweiter Rechner, Weitergabe an Dritte — bei
  Weitergabe gilt zusammen mit `export_personal = false` faktisch das Gardener-Modell aus
  SYSTEM-MANIFEST §3.1: der Stack ist weitergebbar, das Private bleibt).

### Modi-Matrix

| Modus | Richtung | Autorität | Koexistenz-Verhalten |
|---|---|---|---|
| LONELY | keine | homebase | ignoriert lokales Home (festgelegte Antwort) |
| LANDED | je nach `decision` | je nach `decision` | **fordert zur Entscheidung auf** |
| SECOND | bidirektional | beide (Peers) | Sync mit Konfliktdialog |
| LITTLE BROTHER | push (an Home) | lokales Home | liefert ein, liest nur gezielt |
| PORTABLE | keine (Export-Ereignis) | homebase bis Übergabe | sammelt scoped, schnürt Paket |

---

## 5. Koexistenz-Entscheidungsflows (kein stilles Default)

### 5.1 Erkennung

Beim Server-Start prüft homebase (`[home.coexistence].detect = true`), ob ein lokales Home
existiert. Erkennungskriterien (read-only, ohne Schreibzugriff auf fremde Stores):

1. `~/.gardener/gardener.db` **und** `~/.gardener/user.db` vorhanden, oder
2. `~/.usmc/usmc_memory.db` vorhanden und nicht leer, oder
3. `~/.rinnsal/scanner_tasks.db` vorhanden und nicht leer.

### 5.2 Entscheidungsaufforderung

```
Start
  │
  ├─ [home].mode = lonely ──────────────► kein Flow (festgelegt)
  │
  ├─ Erkennung: kein lokales Home ──────► normaler Betrieb, kein Flow
  │
  └─ Erkennung: lokales Home gefunden
        │
        ├─ mode = landed, decision = unset
        │     ► AUFFORDERUNG an den Nutzer (über den Assistenten, sonst Start-Log):
        │       „Lokales Home gefunden (gardener/usmc/rinnsal). Wie soll homebase
        │        sich verhalten?" — Optionen: sync / offload / import_export /
        │        search_takeover / lonely bleiben
        │     ► Antwort wird in decision persistiert; bis dahin: lonely-Verhalten
        │
        ├─ on_detect = ask (Modi second/little_brother/portable, erstmalig)
        │     ► einmalige Bestätigung des konfigurierten Modus, dann Ruhe
        │
        └─ on_detect = ignore ──────────► kein Flow (explizite Nutzerfestlegung)
```

**Regeln:**

- Jede Aufforderung zeigt **Konsequenz und Reversibilität** der Optionen (was fließt wohin, was
  bleibt lokal, wie wird es rückgängig gemacht).
- Keine Option löscht Bestände. `offload` archiviert bundled-Stores (`~/.homebase/_archive/`),
  statt sie zu löschen.
- Eine getroffene Entscheidung ist jederzeit per Config oder Dialog revidierbar; der Wechsel
  selbst ist wieder eine Entscheidung mit Aufforderung (Moduswechsel weg von `lonely` erfordert
  ausdrückliche Bestätigung).

---

## 6. Import / Export / Sync-Semantik

- **Export-Paket (Transport `export_file`):** Zip/Ordner mit JSONL-Dumps der Scoped-Stores plus
  `manifest.json` (instance_id, instance_name, Zeitpunkt, Scope, counts, privacy-Flags).
  Erzeugung **immer** durch den Privacy-Guard (`export_personal`, `secrets = "never"`).
- **Import:** liest ein Export-Paket, zeigt **Preview** (counts, Kategorien, Zeitraum,
  Herkunfts-Instanz) und schreibt erst nach Bestätigung. Idempotent: Wiederholung erzeugt keine
  Duplikate (Vorbild BACH-Kernprinzip; Dedupe über Content-Hash wie `bach search dupes`).
- **Sync (second/little_brother):** beidseitige Snapshots, Merge je Eintrag nach `updated_at`
  (Last-Write-Wins) — aber nur, wenn kein gleichzeitiger aktiver Peer im Heartbeat-Fenster ist;
  sonst Konfliktdialog (`conflict = "ask"`). Jeder Lauf schreibt ein Merge-Log.
- **Gezielte Suche mit Übernahme (search_takeover):** Read-only-`ATTACH` auf die Home-DBs,
  Suche (FTS5), Trefferliste dem Nutzer, Übernahme einzelner Treffer per Bestätigung.
- **Niemals:** Live-DB des anderen Homes beschreiben, DB-Dateien durch OneDrive o. ä. im
  laufenden Betrieb teilen (Manifest §4.3), Secrets oder Personendaten ohne Freigabe bewegen.

---

## 7. LLM-dialogische Config

Der Assistent kann die Config **im Gespräch** lesen und setzen — sie bleibt dieselbe
`homebase.toml`, der Dialog ist ein weiterer Zugangsweg neben dem Texteditor (Vorbild BACH:
Modus per CLI-Befehl *und* per Datei setzbar).

**Geplante Tools (Phase 2, noch nicht implementiert):**

| Tool | Zweck |
|---|---|
| `hb_config_get` | Effektive Config anzeigen (auf Wunsch eine Sektion) |
| `hb_config_set` | Einzelnen Wert setzen, mit Read-back der Änderung |
| `hb_home_status` | Modus, Instanz-Identität, Erkennungslage, letzte Sync-/Export-Ereignisse |
| `hb_home_detect` | Koexistenz-Erkennung manuell auslösen, Ergebnis erklären |
| `hb_home_decide` | LANDED-Entscheidung dialogisch führen und persistieren |
| `hb_home_export` / `hb_home_import` | Paket schnüren / übernehmen (mit Preview + Bestätigung) |

**Dialog-Regeln (Guardrails):**

1. **Vorlesen vor Schreiben.** Der Assistent nennt Wert und Konsequenz, bevor er setzt
   („Ich stelle `home.mode` von `lonely` auf `little_brother` — dann fließen Ergebnisse
   künftig an das lokale Home. Einverstanden?").
2. **Sicherheitsrelevante Änderungen nur mit ausdrücklicher Bestätigung des Nutzers:**
   Moduswechsel weg von `lonely`, `export_personal = true`, `direction` ≠ `none`,
   `on_detect = "ignore"`.
3. **Nie per Dialog setzbar:** `secrets` (fix `never`), fremde `instance_id`.
4. Jede dialogische Änderung landet als normaler Eintrag in `homebase.toml` (kein Seitenkanal)
   und wird vom Stop-Gate-/Review-Prozess wie eine manuelle Änderung behandelt.

---

## 8. Abgrenzung und Bezüge

**Zu bundled-only `hb_mem_*` / `hb_kb_*` / `hb_route_*`:** Diese Module bleiben, was sie sind —
eigene, credential-freie Implementierungen mit eigenen SQLite-Stores unter `~/.homebase/`
(KONZEPT.md „Engine Seams"; SYSTEM-MANIFEST §3.3 führt sie als *ausdrücklich nicht kanonisch*).
Das Heim-Konzept ändert daran nichts: Die Modi regeln das **Verhältnis** dieser Stores zum
lokalen Home; sie machen die bundled-Stores nicht kanonisch. Umgekehrt gibt erst dieses Konzept
den bundled-Stores eine saubere Rolle im Mehr-Homes-Fall (Scope der Sync/Export-Ströme).

**Zum kanonischen Stack (Gardener / TASKPLAN / clutch):** Kanonisch bleibt, was das Manifest in
§3.2 festlegt: Wissen in Gardener (`gardener.db` System, `user.db` User), Tasks in task-master,
Routing-Logik in clutch. Homebase nähert sich dem kanonischen Stack ausschließlich über die
bestehenden Engine-Seams (`[engines] mode = "canonical"`); `LANDED` + `offload` ist genau diese
Richtung als Modus-Entscheidung formuliert. Kein Modus dupliziert kanonische Register unter
eigenem Namen (Manifest §4, Prinzip 1: keine parallelen Standards).

**Zum alten BACH-Konzept (Kapitel 2):**

| Übernommen | Abweichend / neu |
|---|---|
| „Eine Installation, Verhalten per Config", Default = sicherster Modus | BACHs Szenarien (Single/Multi/Server) werden zu fünf **Beziehungs**-Modi zum lokalen Home |
| Instanz-Identität (`instance_id`/`instance_name`) | Koexistenz-**Erkennung** eines zweiten Homes mit Entscheidungsaufforderung — BACH kennt das nicht |
| Transit-Prinzip: Snapshot-Dateien statt Live-DB-Teilung; pull/push am Lebenszyklus | BACHs USB-Stick-Frage (`portable-bach.md`, in BACH offen geblieben) wird mit LANDED und PORTABLE beantwortet |
| Secrets verlassen den lokalen Speicher nie (ProSync-Backups bereinigt) | LLM-**dialogische** Config zusätzlich zu Datei/CLI — BACH setzt nur per Befehl |
| Selektive Übernahme mit Wizard, Preview, Bestätigung (HQ7 C) | Privacy-Grenzen nicht nur für Secrets, sondern gemäß Manifest §3.1 für Personendaten generell (Privacy-Guard vor jedem Export) |
| Lokale Autorität je System; Konflikt-Check per Heartbeat | Explizites „kein stilles Default" als Kohärenzregel (Ticket-Anforderung) |

---

## 9. Offene Fragen / nächste Schritte

- [ ] `[home]`-Sektion in `config.py` als typisierte Felder nachziehen (heute: `raw`-Durchgriff)
- [ ] Erkennungslauf (`hb_home_detect`) implementieren (read-only Kriterien Kapitel 5.1)
- [ ] Export-Paket-Format + Privacy-Guard (Anlehnung an `gardener_privacy_guard.py`)
- [ ] Dialog-Tools `hb_config_*` / `hb_home_*` (Phase 2, Kapitel 7)
- [ ] Heartbeat/Merge-Log für `second` (erst wenn erster Zweit-Host real angebunden wird)
- [ ] Verhältnis zu `.SYNC/`-Slots präzisieren, sobald `sync_slot` genutzt wird (Manifest §5)

---

*Erstellt: 2026-07-31 für Ticket T-20260731-11. Referenzen: KONZEPT.md (Engine Seams),
SYSTEM-MANIFEST.md §3.1/§3.3/§4/§5, BACH INSTALL_KONZEPT.md, HQ7_NEUINSTALLATION_KONZEPT.md,
BACH-Help install/setup/db_sync/identity/modes/mount/user_sync.*
