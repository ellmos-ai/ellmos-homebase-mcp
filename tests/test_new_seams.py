"""Tests for the three new hb_policy_*/hb_ticket_*/hb_lock_* seams
(T-20260825-196589547) and the source-resolver bare-import hint for
garden/mem.

These are CANONICAL-ONLY namespaces (no bundled mode to fall back to -- see
the module docstrings of policy.py/ticket.py/lock.py). Tests therefore focus
on: (a) fail-closed behavior when the engine cannot be resolved, (b) correct
delegation when it can, (c) engines.py's path/import wiring for the three
new names, reusing the existing fixture-directory pattern from
test_engine_seams.py.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest

from homebase import engines as engine_seams
from homebase.config import HomebaseConfig
from homebase.engines import CanonicalEngineUnavailable, engine_summary


@pytest.fixture(autouse=True)
def _no_real_engine_defaults(monkeypatch, tmp_path):
    """Same isolation as test_engine_seams.py, extended: this suite runs on
    a real dev box that HAS a real OneDrive module catalog (unlike CI), so
    blanking only `_DEFAULT_CANDIDATES` is not enough -- the catalog lookup
    would still find the real ticket-master/lock-master/policy-registry
    through the `OneDrive` env var. Also purge any module of the same
    dotted name cached in `sys.modules` from a previous test's fixture
    import, since `import_from_path` (unmodified existing code) reuses an
    already-imported module by name regardless of the new search path."""
    import sys

    monkeypatch.setattr(engine_seams, "_DEFAULT_CANDIDATES", {})
    # `_module_catalog_candidates()` has multiple hardcoded `~/OneDrive/...`
    # fallback entries that resolve via the real home directory regardless
    # of the `OneDrive` env var (this machine genuinely has that path) --
    # env-var isolation alone is not enough, so bypass the function outright.
    monkeypatch.setattr(engine_seams, "_module_catalog_candidates", lambda: [])
    monkeypatch.delenv("OneDrive", raising=False)
    monkeypatch.delenv("ONEDRIVE", raising=False)
    for name in ("lib", "lib.ticket_audit", "lock_scan", "lock_status", "policy_registry"):
        sys.modules.pop(name, None)
    yield
    for name in ("lib", "lib.ticket_audit", "lock_scan", "lock_status", "policy_registry"):
        sys.modules.pop(name, None)


def _run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# engines.py: path/import wiring for the three new names
# ---------------------------------------------------------------------------


def test_load_policy_registry_returns_none_when_unresolvable():
    assert engine_seams.load_policy_registry() is None


def test_load_ticket_master_returns_none_when_unresolvable():
    assert engine_seams.load_ticket_master() is None


def test_load_lock_master_returns_none_tuple_when_unresolvable():
    scan, status = engine_seams.load_lock_master()
    assert scan is None
    assert status is None


def test_load_policy_registry_imports_real_looking_package(tmp_path):
    pkg_dir = tmp_path / "engines" / "policy_registry"
    pkg_dir.mkdir(parents=True)
    (pkg_dir / "__init__.py").write_text(
        "class PolicyRegistry:\n"
        "    def __init__(self, path=None):\n"
        "        self.path = path\n"
        "    def resolve(self, **kw):\n"
        "        return {'status': 'resolved', 'kw': kw}\n"
        "    def search(self, *a, **kw):\n"
        "        return []\n"
    )
    cls = engine_seams.load_policy_registry(str(tmp_path / "engines"))
    assert cls is not None
    instance = cls()
    assert instance.resolve(scope="x") == {"status": "resolved", "kw": {"scope": "x"}}


def test_load_ticket_master_imports_real_looking_lib_package(tmp_path):
    repo = tmp_path / "engines" / "ticket-master"
    lib = repo / "lib"
    lib.mkdir(parents=True)
    (lib / "__init__.py").write_text("")
    (lib / "ticket_audit.py").write_text(
        "def collect_ids(base):\n    return {}\n\n"
        "def audit(base):\n    return {'collisions': {}}\n"
    )
    module = engine_seams.load_ticket_master(str(repo))
    assert module is not None
    assert module.collect_ids("x") == {}


def test_load_lock_master_prefers_pure_locking_subdir(tmp_path):
    repo = tmp_path / "engines" / "lock-master"
    pure = repo / "pure-locking"
    pure.mkdir(parents=True)
    (pure / "lock_scan.py").write_text(
        "def load_config(roots_file):\n    return {'roots_file': str(roots_file)}\n\n"
        "def collect_locks(config):\n    return [{'project': 'demo'}]\n"
    )
    (pure / "lock_status.py").write_text(
        "def check_project_status(project_dir):\n    return [{'project_dir': str(project_dir)}]\n"
    )
    scan, status = engine_seams.load_lock_master(str(repo))
    assert scan is not None and status is not None
    assert scan.collect_locks({}) == [{"project": "demo"}]
    assert status.check_project_status(Path("x")) == [{"project_dir": "x"}]


def test_resolve_tickets_root_prefers_env_override(tmp_path, monkeypatch):
    monkeypatch.delenv("HOMEBASE_TICKETS_ROOT", raising=False)
    monkeypatch.delenv("OneDrive", raising=False)
    monkeypatch.delenv("ONEDRIVE", raising=False)
    tickets = tmp_path / "_TICKETS"
    tickets.mkdir()
    monkeypatch.setenv("HOMEBASE_TICKETS_ROOT", str(tickets))
    assert engine_seams.resolve_tickets_root() == tickets


def test_resolve_tickets_root_none_when_nothing_matches(monkeypatch):
    monkeypatch.delenv("HOMEBASE_TICKETS_ROOT", raising=False)
    monkeypatch.delenv("OneDrive", raising=False)
    monkeypatch.delenv("ONEDRIVE", raising=False)
    monkeypatch.setattr(Path, "expanduser", lambda self: self)
    assert engine_seams.resolve_tickets_root("/does/not/exist") is None


def test_engine_summary_reports_canonical_only_namespaces():
    config = HomebaseConfig()
    lines = engine_summary(config)
    assert "policy=canonical-only (no bundled alternative for this namespace)" in lines
    assert "ticket=canonical-only (no bundled alternative for this namespace)" in lines
    assert "lock=canonical-only (no bundled alternative for this namespace)" in lines


# ---------------------------------------------------------------------------
# PolicyModule
# ---------------------------------------------------------------------------


def _make_policy_module(monkeypatch, registry_cls=None):
    from homebase.modules.policy import PolicyModule

    monkeypatch.setattr(engine_seams, "load_policy_registry", lambda path=None: registry_cls)
    return PolicyModule({})


def test_policy_module_fails_closed_when_engine_missing(monkeypatch):
    module = _make_policy_module(monkeypatch, registry_cls=None)
    tools = {t.name: t for t in module.get_tools()}
    with pytest.raises(CanonicalEngineUnavailable):
        _run(tools["hb_policy_resolve"].handler(scope="ai"))
    with pytest.raises(CanonicalEngineUnavailable):
        _run(tools["hb_policy_list"].handler())


def test_policy_module_delegates_to_real_registry(monkeypatch):
    class FakeRegistry:
        def resolve(self, *, scope, consumer=None, query="", required_kind=None):
            return {"status": "resolved", "selected": {"id": f"P-{scope}"}}

        def search(self, query="", *, scope=None, consumer=None, kind=None):
            return [{"id": "P-1"}]

    module = _make_policy_module(monkeypatch, registry_cls=FakeRegistry)
    tools = {t.name: t for t in module.get_tools()}
    result = _run(tools["hb_policy_resolve"].handler(scope="ai"))
    assert result["engine"] == "canonical"
    assert result["selected"]["id"] == "P-ai"
    listed = _run(tools["hb_policy_list"].handler())
    assert listed["count"] == 1


# ---------------------------------------------------------------------------
# TicketModule
# ---------------------------------------------------------------------------


def _make_ticket_module(monkeypatch, audit_mod=object(), tickets_root=None):
    from homebase.modules.ticket import TicketModule

    monkeypatch.setattr(engine_seams, "load_ticket_master", lambda path=None: audit_mod)
    monkeypatch.setattr(engine_seams, "resolve_tickets_root", lambda path=None: tickets_root)
    return TicketModule({})


def test_ticket_module_fails_closed_when_ticket_master_missing(monkeypatch):
    module = _make_ticket_module(monkeypatch, audit_mod=None, tickets_root=None)
    tools = {t.name: t for t in module.get_tools()}
    with pytest.raises(CanonicalEngineUnavailable):
        _run(tools["hb_ticket_list"].handler(category="INBOX"))


def test_ticket_module_fails_closed_when_root_missing_even_if_present(monkeypatch):
    module = _make_ticket_module(monkeypatch, audit_mod=object(), tickets_root=None)
    tools = {t.name: t for t in module.get_tools()}
    with pytest.raises(CanonicalEngineUnavailable):
        _run(tools["hb_ticket_show"].handler(ticket_id="T-20260825-196589547"))


def test_ticket_module_lists_and_shows_from_real_looking_folder(tmp_path, monkeypatch):
    root = tmp_path / "_TICKETS"
    (root / "INBOX").mkdir(parents=True)
    (root / "INBOX" / "T-20260825-196589547.txt").write_text(
        "==============================================================\n"
        "TICKET\n"
        "==============================================================\n"
        "ID:            T-20260825-196589547\n"
        "TITEL:         Demo\n"
        "STATUS:        INBOX\n"
        "PRIORITAET:    mittel\n"
        "--------------------------------------------------------------\n"
        "rest of the file is free text and must not leak into the header\n",
        encoding="utf-8",
    )
    module = _make_ticket_module(monkeypatch, audit_mod=object(), tickets_root=root)
    tools = {t.name: t for t in module.get_tools()}

    listed = _run(tools["hb_ticket_list"].handler(category="INBOX"))
    assert listed["count"] == 1
    assert listed["tickets"][0]["id"] == "T-20260825-196589547"
    assert listed["tickets"][0]["titel"] == "Demo"

    shown = _run(tools["hb_ticket_show"].handler(ticket_id="T-20260825-196589547"))
    assert shown["status"] == "found"
    assert shown["header"]["STATUS"] == "INBOX"
    # Only header fields, never the free-text body:
    assert "free text" not in str(shown["header"])

    missing = _run(tools["hb_ticket_show"].handler(ticket_id="T-20260101-000000000"))
    assert missing["status"] == "not_found"


# ---------------------------------------------------------------------------
# LockModule
# ---------------------------------------------------------------------------


def _make_lock_module(monkeypatch, scan_mod=None, status_mod=None):
    from homebase.modules.lock import LockModule

    monkeypatch.setattr(engine_seams, "load_lock_master", lambda path=None: (scan_mod, status_mod))
    monkeypatch.setattr("homebase.modules.lock._default_roots_file", lambda: None)
    return LockModule({})


def test_lock_module_fails_closed_when_scan_missing(monkeypatch):
    module = _make_lock_module(monkeypatch, scan_mod=None, status_mod=None)
    tools = {t.name: t for t in module.get_tools()}
    with pytest.raises(CanonicalEngineUnavailable):
        _run(tools["hb_lock_list"].handler())


def test_lock_module_fails_closed_when_roots_file_missing(monkeypatch):
    fake_scan = SimpleNamespace(
        load_config=lambda roots_file: {}, collect_locks=lambda config: []
    )
    module = _make_lock_module(monkeypatch, scan_mod=fake_scan, status_mod=None)
    tools = {t.name: t for t in module.get_tools()}
    with pytest.raises(CanonicalEngineUnavailable):
        _run(tools["hb_lock_list"].handler())


def test_lock_module_lists_and_checks_via_real_looking_engine(tmp_path, monkeypatch):
    roots_file = tmp_path / "lock_roots.json"
    roots_file.write_text("{}", encoding="utf-8")
    fake_scan = SimpleNamespace(
        load_config=lambda rf: {"roots_file": str(rf)},
        collect_locks=lambda config: [{"project": "demo", "path": "C:/demo"}],
    )
    fake_status = SimpleNamespace(
        check_project_status=lambda project_dir: [{"path": str(project_dir)}]
    )

    from homebase.modules.lock import LockModule

    monkeypatch.setattr(engine_seams, "load_lock_master", lambda path=None: (fake_scan, fake_status))
    monkeypatch.setattr("homebase.modules.lock._default_roots_file", lambda: roots_file)
    module = LockModule({})
    tools = {t.name: t for t in module.get_tools()}

    listed = _run(tools["hb_lock_list"].handler())
    assert listed["count"] == 1
    assert listed["locks"][0]["project"] == "demo"

    checked = _run(tools["hb_lock_check"].handler(project_dir=str(tmp_path)))
    assert checked["locked"] is True


# ---------------------------------------------------------------------------
# source-resolver bare-import hint for garden/mem (engines.py)
# ---------------------------------------------------------------------------


def test_bare_import_hint_returns_none_for_unmapped_engine():
    assert engine_seams._try_source_resolver_bare_import("state") is None


def test_bare_import_hint_returns_none_when_source_resolver_missing(monkeypatch):
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "source_resolver":
            raise ImportError("simulated: package not installed")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    assert engine_seams._try_source_resolver_bare_import("garden") is None


def test_bare_import_hint_returns_none_when_role_not_resolved(monkeypatch):
    fake_module = SimpleNamespace(
        resolve=lambda role: SimpleNamespace(status="not_found", quelle=None),
        ResolutionStatus=SimpleNamespace(RESOLVED="resolved"),
    )
    monkeypatch.setitem(__import__("sys").modules, "source_resolver", fake_module)
    assert engine_seams._try_source_resolver_bare_import("mem") is None
