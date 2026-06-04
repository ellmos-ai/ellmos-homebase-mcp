"""Locale helpers for Homebase MCP tool metadata."""

from __future__ import annotations

from dataclasses import dataclass

DEFAULT_LOCALE = "en"
SUPPORTED_LOCALES = ("en", "de", "es", "zh", "ja", "ru")

ALIASES = {
    "en-us": "en",
    "en-gb": "en",
    "de-de": "de",
    "de-at": "de",
    "de-ch": "de",
    "es-es": "es",
    "es-mx": "es",
    "zh-cn": "zh",
    "zh-hans": "zh",
    "ja-jp": "ja",
    "ru-ru": "ru",
}

TRANSLATIONS: dict[str, dict[str, str]] = {
    "de": {
        "tool.hb_mem_store": "Speichert einen Fakt, eine Lektion oder einen Working-Memory-Eintrag.",
        "tool.hb_mem_query": "Sucht Memory-Einträge per Schlüsselwort.",
        "tool.hb_mem_context": "Erzeugt kompakten Kontext für Prompt-Injektion.",
        "tool.hb_mem_merge": "Zeigt mögliche Zusammenführungen überlappender Memories an.",
        "tool.hb_route_select": "Analysiert einen Prompt und empfiehlt Modell oder Provider.",
        "tool.hb_route_evaluate": "Speichert Qualitätsfeedback für eine Routing-Entscheidung.",
        "tool.hb_route_stats": "Gibt Routing-Statistiken und Lernfortschritt aus.",
        "tool.hb_kb_search": "Sucht in der Knowledge-Datenbank.",
        "tool.hb_kb_ingest": "Nimmt neues Wissen als Text, URL oder Dateiinhalte auf.",
        "tool.hb_kb_get": "Ruft einen Knowledge-Eintrag mit Metadaten ab.",
        "tool.hb_kb_list": "Listet Tags in der Knowledge-Datenbank.",
        "tool.hb_swarm_parallel": "Teilt eine Aufgabe in Chunks und verarbeitet sie parallel.",
        "tool.hb_swarm_consensus": "Holt eine Mehrheitsentscheidung mehrerer unabhängiger Agenten ein.",
        "tool.hb_swarm_hierarchy": "Nutzt ein Boss-Worker-Delegationsmuster.",
        "tool.hb_swarm_stigmergy": "Koordiniert indirekt über geteilten Zustand.",
        "tool.hb_state_mem_get": "Ruft State-Memory-Einträge ab.",
        "tool.hb_state_mem_set": "Speichert einen State-Memory-Eintrag.",
        "tool.hb_state_task_list": "Listet Tasks mit optionalem Statusfilter.",
        "tool.hb_state_task_create": "Erstellt einen neuen Task.",
        "tool.hb_state_task_update": "Aktualisiert Status, Beschreibung oder Priorität eines Tasks.",
        "tool.hb_state_dispatch": "Gibt den Status eines Connector-Dispatchs zurück.",
        "tool.hb_garden_find": "Sucht im kleinen Garden-Store.",
        "tool.hb_garden_get": "Ruft einen Garden-Eintrag per Schlüssel ab.",
        "tool.hb_garden_put": "Speichert oder aktualisiert einen Garden-Eintrag.",
        "tool.hb_garden_run": "Führt einen gespeicherten Befehl aus, wenn Ausführung aktiviert ist.",
        "tool.hb_api_probe": "Prüft eine URL mit API-Discovery-Strategien.",
        "tool.hb_api_discover": "Erkennt API-Schemata aus einer Basis-URL.",
        "tool.hb_api_export": "Exportiert Probe-Ergebnisse als Markdown oder JSON.",
        "tool.hb_api_history": "Listet frühere Probe-Ergebnisse.",
        "tool.hb_test_list": "Listet verfügbare Test-Batterien.",
        "tool.hb_test_run": "Führt eine Test-Batterie oder einen Einzeltest aus.",
        "tool.hb_test_results": "Ruft Ergebnisse des letzten Testlaufs ab.",
        "tool.hb_auto_list_chains": "Listet verfügbare Automatisierungsketten.",
        "tool.hb_auto_run": "Startet eine Automatisierungskette.",
        "tool.hb_auto_status": "Prüft den Status einer laufenden Kette.",
        "tool.hb_auto_result": "Ruft das Ergebnis einer Kette ab.",
        "tool.hb_conn_list": "Listet konfigurierte Connectors.",
        "tool.hb_conn_send": "Sendet eine Nachricht über einen Connector.",
        "tool.hb_conn_receive": "Ruft neue Nachrichten eines Connectors ab.",
        "tool.hb_conn_status": "Prüft den Zustand eines Connectors.",
        "tool.hb_plug_list": "Listet installierte Plugins.",
        "tool.hb_plug_info": "Ruft Plugin-Metadaten ab.",
        "tool.hb_plug_run": "Führt ein Plugin aus.",
        "tool.hb_plug_discover": "Sucht neue Plugins in einem Verzeichnis.",
    },
    "es": {
        "tool.hb_mem_store": "Guarda un dato, una lección o una entrada de memoria de trabajo.",
        "tool.hb_mem_query": "Busca entradas de memoria por palabra clave.",
        "tool.hb_mem_context": "Genera contexto compacto para inyección en prompts.",
        "tool.hb_kb_search": "Busca en la base de conocimiento.",
        "tool.hb_kb_ingest": "Añade conocimiento nuevo como texto, URL o archivo.",
        "tool.hb_state_task_create": "Crea una tarea nueva.",
        "tool.hb_garden_put": "Guarda o actualiza una entrada del Garden.",
    },
    "zh": {
        "tool.hb_mem_store": "保存事实、经验或工作记忆条目。",
        "tool.hb_mem_query": "按关键词搜索记忆条目。",
        "tool.hb_mem_context": "生成用于提示注入的紧凑上下文。",
        "tool.hb_kb_search": "搜索知识库。",
        "tool.hb_kb_ingest": "接收文本、URL 或文件形式的新知识。",
        "tool.hb_state_task_create": "创建新任务。",
        "tool.hb_garden_put": "保存或更新 Garden 条目。",
    },
    "ja": {
        "tool.hb_mem_store": "事実、学習内容、作業メモリの項目を保存します。",
        "tool.hb_mem_query": "キーワードでメモリ項目を検索します。",
        "tool.hb_mem_context": "プロンプト注入用の短いコンテキストを生成します。",
        "tool.hb_kb_search": "ナレッジベースを検索します。",
        "tool.hb_kb_ingest": "テキスト、URL、ファイルから新しい知識を取り込みます。",
        "tool.hb_state_task_create": "新しいタスクを作成します。",
        "tool.hb_garden_put": "Garden エントリを保存または更新します。",
    },
    "ru": {
        "tool.hb_mem_store": "Сохраняет факт, урок или запись рабочей памяти.",
        "tool.hb_mem_query": "Ищет записи памяти по ключевому слову.",
        "tool.hb_mem_context": "Создает компактный контекст для вставки в prompt.",
        "tool.hb_kb_search": "Ищет в базе знаний.",
        "tool.hb_kb_ingest": "Добавляет новое знание из текста, URL или файла.",
        "tool.hb_state_task_create": "Создает новую задачу.",
        "tool.hb_garden_put": "Сохраняет или обновляет запись Garden.",
    },
}


def normalize_locale(locale: str | None) -> str:
    if not locale:
        return DEFAULT_LOCALE
    normalized = locale.strip().lower().replace("_", "-")
    normalized = ALIASES.get(normalized, normalized.split("-", 1)[0])
    if normalized in SUPPORTED_LOCALES:
        return normalized
    return DEFAULT_LOCALE


@dataclass(frozen=True)
class I18n:
    locale: str = DEFAULT_LOCALE

    def __post_init__(self) -> None:
        object.__setattr__(self, "locale", normalize_locale(self.locale))

    def t(self, key: str, default: str | None = None) -> str:
        if self.locale == DEFAULT_LOCALE:
            return default or key
        return TRANSLATIONS.get(self.locale, {}).get(key) or default or key
