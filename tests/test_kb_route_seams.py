"""Tests for the canonical seams of hb_kb_* (KnowledgeDigest) and hb_route_* (clutch).

Everything here runs against FIXTURE engines written to ``tmp_path``: the fixtures mirror
the public signatures of the real engines (read 2026-10-31 from KnowledgeDigest
``digest.py``/``config.py`` and clutch ``fahrer.py``/``scorer.py``/``user_overrides.py``) closely
enough to validate the seam wiring, not to reimplement them. The real engines were exercised
separately by a manual smoke run (see CHANGELOG); nothing in this file touches them.

The central negative control is the MODE-CONTRACT rule: ``canonical`` + unreachable target
=> ``CanonicalEngineUnavailable`` for the whole tool family and NO shadow store on disk.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

from homebase import engines as engine_seams
from homebase.config import HomebaseConfig
from homebase.engines import CanonicalEngineUnavailable, engine_summary
from homebase.registry import ModuleRegistry

KB_TOOLS = ("hb_kb_search", "hb_kb_ingest", "hb_kb_get", "hb_kb_list")
KB_ARGS = {
    "hb_kb_search": {"query": "alpha"},
    "hb_kb_ingest": {"content": "alpha text"},
    "hb_kb_get": {"id": 1},
    "hb_kb_list": {},
}
ROUTE_ARGS = {
    "hb_route_select": {"prompt": "Fix the bug in auth.py"},
    "hb_route_evaluate": {"route_id": "r1", "quality": 0.5},
    "hb_route_stats": {},
}
_FIXTURE_MODULES = ("KnowledgeDigest", "clutch")


def _purge_fixture_modules() -> None:
    for name in list(sys.modules):
        if name in _FIXTURE_MODULES or name.startswith(tuple(f"{m}." for m in _FIXTURE_MODULES)):
            sys.modules.pop(name, None)


@pytest.fixture(autouse=True)
def _isolated_engines(monkeypatch):
    """Host-independent: no default candidates, no module catalog, no cached fixture imports.

    This suite runs on dev boxes that really have KnowledgeDigest and clutch installed
    (editable), so blanking only the default candidates is not enough: cached modules of the
    same dotted name from an earlier test would be reused by ``import_from_path``.
    """
    monkeypatch.setattr(engine_seams, "_DEFAULT_CANDIDATES", {})
    monkeypatch.setattr(engine_seams, "_module_catalog_candidates", lambda: [])
    for name in ("OneDrive", "ONEDRIVE", "HOMEBASE_ENGINE_KB_PATH", "HOMEBASE_ENGINE_ROUTE_PATH", "CLUTCH_HOME"):
        monkeypatch.delenv(name, raising=False)
    _purge_fixture_modules()
    yield
    _purge_fixture_modules()


def _run(coro):
    return asyncio.run(coro)


def _tools(module) -> dict:
    return {tool.name: tool.handler for tool in module.get_tools()}


# ---------------------------------------------------------------------------
# Fixture engines
# ---------------------------------------------------------------------------


def _write_fixture_knowledgedigest(tmp_path: Path, *, calls_log: Path | None = None) -> Path:
    """A package directory named ``KnowledgeDigest`` (as in the real repo: the root IS the package)."""
    pkg = tmp_path / "engines" / "KnowledgeDigest"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("from .digest import KnowledgeDigest\n", encoding="utf-8")
    (pkg / "digest.py").write_text(
        f'''
from pathlib import Path

CALLS = {str(calls_log)!r}


def _log(line):
    if CALLS != "None":
        with open(CALLS, "a", encoding="utf-8") as handle:
            handle.write(line + "\\n")


class KnowledgeDigest:
    def __init__(self, db_path=None, config=None):
        self.db_path = Path(db_path) if db_path else None
        _log(f"init {{self.db_path}}")

    def search_all(self, query, *, limit=20):
        _log(f"search_all {{query}} {{limit}}")
        return [
            {{"source": "document", "name": "alpha.md", "type": "md", "snippet": f">>>{{query}}<<<",
              "relevance": -1.0, "word_count": 3}},
            {{"source": "wiki", "name": "Beta", "type": "help", "snippet": "b", "relevance": -0.5,
              "word_count": 9}},
        ][:limit]

    def ingest(self, path, **kwargs):
        _log("ingest CALLED")
        return {{}}

    def close(self):
        _log("close")
''',
        encoding="utf-8",
    )
    default_db = tmp_path / "kd_data" / "knowledge.db"
    (pkg / "config.py").write_text(
        f'''
from pathlib import Path


class _Config:
    def get_db_path(self):
        return Path({str(default_db)!r})


def get_config(config_path=None):
    return _Config()
''',
        encoding="utf-8",
    )
    return pkg


def _write_fixture_clutch(tmp_path: Path, *, with_model_override: bool = True, calls_log: Path | None = None) -> Path:
    root = tmp_path / "engines" / "clutch_repo"
    pkg = root / "clutch"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "user_overrides.py").write_text(
        '''
import os
from pathlib import Path


def clutch_home():
    override = os.environ.get("CLUTCH_HOME")
    return Path(override).expanduser() if override else Path.home() / ".clutch"
''',
        encoding="utf-8",
    )
    (pkg / "scorer.py").write_text(
        '''
from types import SimpleNamespace


class _Scorer:
    def bewerte(self, task, hat_bild=False):
        return SimpleNamespace(score=5, zweck="coding")


def get_scorer():
    return _Scorer()
''',
        encoding="utf-8",
    )
    override_param = ", model_override=None" if with_model_override else ""
    override_use = "model_override" if with_model_override else "None"
    (pkg / "fahrer.py").write_text(
        f'''
from pathlib import Path
from types import SimpleNamespace

CALLS = {str(calls_log)!r}


def _log(line):
    if CALLS != "None":
        with open(CALLS, "a", encoding="utf-8") as handle:
            handle.write(line + "\\n")


class Fahrer:
    def __init__(self, base_dir=None, db_path=None, **kwargs):
        self.db_path = Path(db_path)
        _log(f"init {{self.db_path}}")

    def strecke_analysieren(self, beschreibung, kontext=None):
        return SimpleNamespace(typ=SimpleNamespace(value="bundesstrasse"), konfidenz=0.9)

    def kuppeln(self, profil, zweck=None, vertrauenswuerdig=True, effort_override=None,
                ausschluss=None, praeferenz=None{override_param}, rolle=None):
        _log(f"kuppeln zweck={{zweck}} praeferenz={{praeferenz}} model_override={{{override_use}}}")
        provider = (praeferenz or ["anthropic"])[0]
        model = {override_use} or "model-default"
        gang = SimpleNamespace(name="gang-" + provider, provider=provider, model_id=model)
        return SimpleNamespace(
            gang=gang,
            to_dict=lambda: {{"gang": gang.name, "provider": provider, "model_id": model, "gas": 0.7}},
        )

    def feedback(self, *args, **kwargs):
        _log("feedback CALLED")

    def status(self):
        return {{"bordcomputer": {{"gesund": True}}, "tacho": {{"gesamte_fahrten": 7}}}}
''',
        encoding="utf-8",
    )
    return root


def _kb_module(config: dict):
    from homebase.modules.knowledge import create_module

    return create_module(config)


def _route_module(config: dict):
    from homebase.modules.routing import create_module

    return create_module(config)


# ---------------------------------------------------------------------------
# hb_kb_*: canonical, reachable
# ---------------------------------------------------------------------------


def test_kb_canonical_search_delegates_and_builds_no_bundled_store(tmp_path):
    calls = tmp_path / "kd_calls.log"
    engine = _write_fixture_knowledgedigest(tmp_path, calls_log=calls)
    kd_db = tmp_path / "kd_data" / "knowledge.db"
    kd_db.parent.mkdir()
    kd_db.write_bytes(b"")  # the DB exists (the fixture engine never opens it)
    bundled = tmp_path / "bundled" / "knowledge.db"
    module = _kb_module({"db_path": str(bundled), "_engine_mode": "canonical", "_engine_path": str(engine)})

    result = _run(_tools(module)["hb_kb_search"](query="alpha", limit=1))

    assert module.engine_mode == "canonical"
    assert result["status"] == "ok" and result["engine"] == "canonical"
    assert result["count"] == 1
    assert result["results"][0]["name"] == "alpha.md"
    log = calls.read_text(encoding="utf-8")
    assert f"init {kd_db}" in log, "the engine must be opened on ITS OWN default database"
    assert "search_all alpha 1" in log
    assert log.rstrip().endswith("close"), "the per-call engine instance must be closed"
    assert not bundled.exists() and not bundled.parent.exists(), "no bundled store in canonical mode"


def test_kb_explicit_kd_db_wins_over_engine_default(tmp_path):
    calls = tmp_path / "kd_calls.log"
    engine = _write_fixture_knowledgedigest(tmp_path, calls_log=calls)
    explicit = tmp_path / "elsewhere" / "kd.db"
    explicit.parent.mkdir()
    explicit.write_bytes(b"")
    module = _kb_module(
        {"db_path": str(tmp_path / "b.db"), "kd_db": str(explicit), "_engine_mode": "canonical", "_engine_path": str(engine)}
    )

    _run(_tools(module)["hb_kb_search"](query="x"))

    assert f"init {explicit}" in calls.read_text(encoding="utf-8")


@pytest.mark.parametrize("filter_name", ["category", "agent_id"])
def test_kb_canonical_search_reports_unsupported_filters_instead_of_ignoring_them(tmp_path, filter_name):
    calls = tmp_path / "kd_calls.log"
    engine = _write_fixture_knowledgedigest(tmp_path, calls_log=calls)
    (tmp_path / "kd_data").mkdir()
    (tmp_path / "kd_data" / "knowledge.db").write_bytes(b"")
    module = _kb_module({"db_path": str(tmp_path / "b.db"), "_engine_mode": "canonical", "_engine_path": str(engine)})

    result = _run(_tools(module)["hb_kb_search"](query="alpha", **{filter_name: "x"}))

    assert result["status"] == "not_supported" and result["engine"] == "canonical"
    assert filter_name in result["message"]
    assert not calls.exists(), "an unfiltered engine search must not have run"


@pytest.mark.parametrize("tool", ["hb_kb_ingest", "hb_kb_get", "hb_kb_list"])
def test_kb_canonical_gap_tools_report_not_supported_without_touching_the_engine(tmp_path, tool):
    calls = tmp_path / "kd_calls.log"
    engine = _write_fixture_knowledgedigest(tmp_path, calls_log=calls)
    (tmp_path / "kd_data").mkdir()
    (tmp_path / "kd_data" / "knowledge.db").write_bytes(b"")
    bundled = tmp_path / "bundled" / "knowledge.db"
    module = _kb_module({"db_path": str(bundled), "_engine_mode": "canonical", "_engine_path": str(engine)})

    result = _run(_tools(module)[tool](**KB_ARGS[tool]))

    assert result["status"] == "not_supported" and result["operation"] == tool.removeprefix("hb_kb_")
    assert not calls.exists(), "the gap must be reported, not worked around via the engine"
    assert not bundled.parent.exists()


# ---------------------------------------------------------------------------
# hb_kb_*: canonical, unreachable  (NEGATIVE CONTROL)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("tool", KB_TOOLS)
def test_kb_fails_closed_when_engine_missing_and_creates_no_bundled_db(tmp_path, tool):
    bundled = tmp_path / "shadow" / "knowledge.db"
    module = _kb_module(
        {"db_path": str(bundled), "_engine_mode": "canonical", "_engine_path": str(tmp_path / "does-not-exist")}
    )

    with pytest.raises(CanonicalEngineUnavailable) as excinfo:
        _run(_tools(module)[tool](**KB_ARGS[tool]))

    message = str(excinfo.value)
    assert "hb_kb_*" in message and "bundled" in message and "KnowledgeDigest" in message
    assert not bundled.exists() and not bundled.parent.exists(), "no shadow bundled DB may be created"


@pytest.mark.parametrize("tool", KB_TOOLS)
def test_kb_fails_closed_when_engine_is_present_but_database_is_missing(tmp_path, tool):
    calls = tmp_path / "kd_calls.log"
    engine = _write_fixture_knowledgedigest(tmp_path, calls_log=calls)
    bundled = tmp_path / "shadow" / "knowledge.db"
    module = _kb_module({"db_path": str(bundled), "_engine_mode": "canonical", "_engine_path": str(engine)})

    with pytest.raises(CanonicalEngineUnavailable) as excinfo:
        _run(_tools(module)[tool](**KB_ARGS[tool]))

    assert "database does not exist" in str(excinfo.value)
    assert str(tmp_path / "kd_data" / "knowledge.db") in str(excinfo.value)
    assert not calls.exists(), "the engine must not even be instantiated (it would create the DB)"
    assert not (tmp_path / "kd_data").exists(), "the engine's data directory must not be created"
    assert not bundled.exists() and not bundled.parent.exists()


# ---------------------------------------------------------------------------
# hb_kb_*: bundled stays unchanged
# ---------------------------------------------------------------------------


def test_kb_bundled_mode_roundtrip_is_unchanged(tmp_path):
    db = tmp_path / "bundled" / "knowledge.db"
    module = _kb_module({"db_path": str(db)})
    tools = _tools(module)

    ingested = _run(tools["hb_kb_ingest"](content="alpha knowledge", source="s", tags=["t1"], agent_id="a"))
    found = _run(tools["hb_kb_search"](query="alpha"))
    got = _run(tools["hb_kb_get"](id=ingested["id"]))
    listed = _run(tools["hb_kb_list"]())

    assert db.exists() and module.engine_mode == "bundled"
    assert ingested["status"] == "ingested"
    assert found["status"] == "ok" and found["count"] == 1 and "engine" not in found
    assert got["entry"]["content"] == "alpha knowledge"
    assert listed["tags"] == ["t1"]


def test_kb_explicit_bundled_ignores_an_available_engine(tmp_path):
    calls = tmp_path / "kd_calls.log"
    engine = _write_fixture_knowledgedigest(tmp_path, calls_log=calls)
    db = tmp_path / "bundled" / "knowledge.db"
    module = _kb_module({"db_path": str(db), "_engine_mode": "bundled", "_engine_path": str(engine)})

    _run(_tools(module)["hb_kb_ingest"](content="x"))

    assert db.exists() and not calls.exists()


# ---------------------------------------------------------------------------
# hb_route_*: canonical, reachable
# ---------------------------------------------------------------------------


def test_route_canonical_select_delegates_to_clutch_dry_run(tmp_path, monkeypatch):
    calls = tmp_path / "clutch_calls.log"
    engine = _write_fixture_clutch(tmp_path, calls_log=calls)
    home = tmp_path / "clutch_home"
    home.mkdir()
    (home / "clutch.db").write_bytes(b"")
    monkeypatch.setenv("CLUTCH_HOME", str(home))
    module = _route_module({"_engine_mode": "canonical", "_engine_path": str(engine)})

    result = _run(
        _tools(module)["hb_route_select"](
            prompt="Fix the bug", constraints={"provider": "google", "model": "m-x", "max_tokens": 10, "speed": "fast"}
        )
    )

    assert module.engine_mode == "canonical"
    assert result["status"] == "ok" and result["engine"] == "canonical"
    assert result["provider"] == "google" and result["model"] == "m-x"
    assert result["strategy"] == "bundesstrasse" and result["zweck"] == "coding"
    assert result["unsupported_constraints"] == ["max_tokens", "speed"]
    assert result["clutch"]["gang"] == "gang-google"
    log = calls.read_text(encoding="utf-8")
    assert f"init {home / 'clutch.db'}" in log
    assert "kuppeln zweck=coding praeferenz=['google'] model_override=m-x" in log


def test_route_canonical_reports_model_constraint_as_unsupported_on_older_clutch(tmp_path, monkeypatch):
    engine = _write_fixture_clutch(tmp_path, with_model_override=False)
    home = tmp_path / "clutch_home"
    home.mkdir()
    (home / "clutch.db").write_bytes(b"")
    monkeypatch.setenv("CLUTCH_HOME", str(home))
    module = _route_module({"_engine_mode": "canonical", "_engine_path": str(engine)})

    result = _run(_tools(module)["hb_route_select"](prompt="x", constraints={"model": "wanted"}))

    assert result["status"] == "ok"
    assert result["model"] != "wanted"
    assert "model" in result["unsupported_constraints"], "an ignored constraint must be reported, not hidden"


def test_route_canonical_explicit_clutch_db_wins_over_clutch_home(tmp_path, monkeypatch):
    calls = tmp_path / "clutch_calls.log"
    engine = _write_fixture_clutch(tmp_path, calls_log=calls)
    explicit = tmp_path / "journal" / "my.db"
    explicit.parent.mkdir()
    explicit.write_bytes(b"")
    monkeypatch.setenv("CLUTCH_HOME", str(tmp_path / "ignored_home"))
    module = _route_module({"_engine_mode": "canonical", "_engine_path": str(engine), "clutch_db": str(explicit)})

    _run(_tools(module)["hb_route_stats"]())

    assert f"init {explicit}" in calls.read_text(encoding="utf-8")


def test_route_canonical_evaluate_reports_gap_and_records_nothing(tmp_path, monkeypatch):
    calls = tmp_path / "clutch_calls.log"
    engine = _write_fixture_clutch(tmp_path, calls_log=calls)
    home = tmp_path / "clutch_home"
    home.mkdir()
    (home / "clutch.db").write_bytes(b"")
    monkeypatch.setenv("CLUTCH_HOME", str(home))
    module = _route_module({"_engine_mode": "canonical", "_engine_path": str(engine)})

    result = _run(_tools(module)["hb_route_evaluate"](route_id="r1", quality=0.9))

    assert result["status"] == "not_supported" and result["operation"] == "evaluate"
    assert "fahrt_id" in result["message"]
    assert not calls.exists(), "no fake drive / feedback may be written into clutch's journal"


def test_route_canonical_stats_delegates_to_status(tmp_path, monkeypatch):
    engine = _write_fixture_clutch(tmp_path)
    home = tmp_path / "clutch_home"
    home.mkdir()
    (home / "clutch.db").write_bytes(b"")
    monkeypatch.setenv("CLUTCH_HOME", str(home))
    module = _route_module({"_engine_mode": "canonical", "_engine_path": str(engine)})

    result = _run(_tools(module)["hb_route_stats"]())

    assert result["status"] == "ok" and result["engine"] == "canonical"
    assert result["routes"] == 7 and result["clutch"]["bordcomputer"]["gesund"] is True


# ---------------------------------------------------------------------------
# hb_route_*: canonical, unreachable  (NEGATIVE CONTROL)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("tool", list(ROUTE_ARGS))
def test_route_fails_closed_when_engine_missing(tmp_path, tool):
    module = _route_module({"_engine_mode": "canonical", "_engine_path": str(tmp_path / "does-not-exist")})

    with pytest.raises(CanonicalEngineUnavailable) as excinfo:
        _run(_tools(module)[tool](**ROUTE_ARGS[tool]))

    assert "hb_route_*" in str(excinfo.value) and "clutch" in str(excinfo.value)


@pytest.mark.parametrize("tool", list(ROUTE_ARGS))
def test_route_fails_closed_when_journal_missing_and_creates_nothing(tmp_path, monkeypatch, tool):
    calls = tmp_path / "clutch_calls.log"
    engine = _write_fixture_clutch(tmp_path, calls_log=calls)
    ghost_home = tmp_path / "ghost_clutch_home"
    monkeypatch.setenv("CLUTCH_HOME", str(ghost_home))
    module = _route_module({"_engine_mode": "canonical", "_engine_path": str(engine)})

    with pytest.raises(CanonicalEngineUnavailable) as excinfo:
        _run(_tools(module)[tool](**ROUTE_ARGS[tool]))

    assert "database does not exist" in str(excinfo.value) and str(ghost_home / "clutch.db") in str(excinfo.value)
    assert not calls.exists(), "Fahrer() must not be constructed: it would create the routing journal"
    assert not ghost_home.exists(), "clutch's home directory must not be created"


# ---------------------------------------------------------------------------
# hb_route_*: bundled stays unchanged
# ---------------------------------------------------------------------------


def test_route_bundled_mode_is_unchanged(tmp_path):
    engine = _write_fixture_clutch(tmp_path)  # present but not requested
    module = _route_module({"_engine_path": str(engine)})
    tools = _tools(module)

    selected = _run(tools["hb_route_select"](prompt="Fix the bug in auth.py", constraints={"speed": "fast"}))
    recorded = _run(tools["hb_route_evaluate"](route_id=selected["route_id"], quality=0.8))
    stats = _run(tools["hb_route_stats"]())

    assert module.engine_mode == "bundled"
    assert selected["status"] == "ok" and selected["strategy"] == "fast" and "engine" not in selected
    assert recorded == {"status": "recorded", "route_id": selected["route_id"], "quality": 0.8}
    assert stats["routes"] == 1 and stats["feedback"] == 1 and stats["average_quality"] == 0.8


# ---------------------------------------------------------------------------
# Wiring: summary, startup, loader
# ---------------------------------------------------------------------------


def test_engine_summary_reports_kb_and_route_as_canonical_now():
    summary = engine_summary(HomebaseConfig(engine_mode="canonical"))

    assert "kb=canonical" in summary and "route=canonical" in summary
    assert not any("bundled-only" in line for line in summary)


def test_engine_summary_still_marks_a_namespace_without_seam_as_bundled_only(monkeypatch):
    monkeypatch.setattr(engine_seams, "SEAM_IMPLEMENTED", engine_seams.SEAM_IMPLEMENTED - {"kb"})

    summary = engine_summary(HomebaseConfig(engine_mode="canonical"))

    assert "kb=bundled-only (canonical requested, no seam implemented yet)" in summary
    assert "route=canonical" in summary


def test_server_still_starts_and_lists_tools_when_canonical_targets_are_unreachable(tmp_path):
    shadow_kb = tmp_path / "shadow" / "knowledge.db"
    config = HomebaseConfig(
        enabled_modules=["kb", "route"],
        engine_mode="canonical",
        engine_configs={
            "kb": {"path": str(tmp_path / "nope-kb")},
            "route": {"path": str(tmp_path / "nope-route")},
        },
        module_configs={"kb": {"db_path": str(shadow_kb)}},
    )
    registry = ModuleRegistry(config)

    loaded, skipped = registry.discover_and_load()

    assert sorted(loaded) == ["kb", "route"] and skipped == []
    names = {tool.name for tool in registry.list_tools()}
    assert set(KB_TOOLS) <= names and set(ROUTE_ARGS) <= names
    assert not shadow_kb.parent.exists()


def test_load_knowledgedigest_imports_from_the_parent_of_the_package_dir(tmp_path):
    package_dir = _write_fixture_knowledgedigest(tmp_path)

    handle = engine_seams.load_knowledgedigest(str(package_dir))

    assert handle is not None
    assert handle.cls.__name__ == "KnowledgeDigest"
    assert handle.default_db_path == tmp_path / "kd_data" / "knowledge.db"


def test_load_knowledgedigest_and_clutch_return_none_when_unresolvable(tmp_path):
    assert engine_seams.load_knowledgedigest(str(tmp_path / "missing")) is None
    assert engine_seams.load_clutch(str(tmp_path / "missing")) is None


def test_load_clutch_exposes_class_scorer_and_home_derived_journal(tmp_path, monkeypatch):
    engine = _write_fixture_clutch(tmp_path)
    monkeypatch.setenv("CLUTCH_HOME", str(tmp_path / "h"))

    handle = engine_seams.load_clutch(str(engine))

    assert handle is not None
    assert handle.Fahrer.__name__ == "Fahrer" and callable(handle.get_scorer)
    assert handle.default_db_path == tmp_path / "h" / "clutch.db"
