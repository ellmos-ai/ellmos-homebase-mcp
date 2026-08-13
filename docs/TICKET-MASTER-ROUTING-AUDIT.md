# ticket-master: Scoring-/Routing-Audit

Stand: 2026-08-13
Scope: Task 1593, Homebase `hb_state_task_*`

## Befund

`ticket-master` ist in der Homebase-Architektur als prompt-getriebener Workflow
beschrieben, nicht als importierbares Engine-Paket. Deshalb wird kein eigenes
`hb_ticket_*`-Modul daraus abgeleitet. Die Abgrenzung steht in
`KONZEPT.md` (Integrationskandidaten) und `TODO.md` (Modul-Integrations-Audit).

Der aktuelle Code wurde gegen diese Schnittstellen geprüft:

| Workflow-Schritt | Vorhandene Homebase-Schnittstelle | Ergebnis |
| --- | --- | --- |
| Intake | `hb_state_task_create(title, description, agent_id)` | Kann Titel, Beschreibung und Herkunft persistieren. |
| Score | `priority = low \| medium \| high` in create/update | Es gibt eine grobe Priorität, aber keinen numerischen Complexity-/Impact-Score und keine Score-Begründung. |
| Provider-Match | `hb_route_select(prompt, constraints)` | Kann aus einer Aufgabenbeschreibung eine credential-freie Provider-/Modell-Empfehlung liefern. |
| Persistenz des Matches | `hb_state_task_update` | Kein Feld für Provider, Modell, Konfidenz oder Bewertungszeitpunkt. Die Routing-Historie ist nur modul-intern und flüchtig. |

## Entscheidung

Die Logik wird in diesem Task **nicht** in `hb_state_task_create/update`
eingebaut. Der State-Task-Seam kann im Canonical-Modus an Rinnsal delegieren;
ein neues Pflichtfeld oder ein undurchsichtiges JSON-Feld würde diese bestehende
Kompatibilität ohne abgestimmten Adapter brechen. `priority` bleibt damit die
einzige bewusst unterstützte Priorisierung.

Die sichere, additive Folgeoption ist eine separate Erweiterungstabelle (oder
ein abgestimmter Canonical-Adapter), zum Beispiel mit:

* `task_id`
* `score` und `score_basis`
* `provider`, `model` und `confidence`
* `assessed_at` und `assessor`

Sie sollte nur über einen ausdrücklich versionierten Contract geschrieben
werden. Bis dahin kann ein Client `hb_route_select` separat aufrufen und die
Empfehlung selbst verwalten; Homebase behauptet keine dauerhafte Provider-
Zuweisung. Damit ist die Intake→Score→Provider-Match-Frage geprüft, ohne die
Task-CRUD- oder Canonical-Engine-Semantik zu verändern.

## Nachweis

`tests/test_module_contracts.py` stellt sicher, dass alle elf Module ihren
Tool-Vertrag und einen wiederholbaren Start gegen vorhandene SQLite-Stores
erfüllen. Die Legacy-Smokes prüfen insbesondere die `agent_id`-Migrationen von
Memory, Knowledge und State sowie die Bestandserhaltung der übrigen
persistenten Module.
