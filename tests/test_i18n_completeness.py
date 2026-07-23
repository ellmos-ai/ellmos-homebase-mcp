"""Regression guard: every locale must fully cover the tool descriptions.

The es/zh/ja/ru TRANSLATIONS shipped as silent 7-key stubs for months because
nothing compared locale key sets (unlike the TS servers, where the Translations
interface makes a gap a compile error — Python dicts stay quiet and fall back
to English). These tests fail loudly when a locale drifts or a new hb_* tool
ships without translations in every locale.
"""

from __future__ import annotations

from homebase.config import HomebaseConfig
from homebase.i18n import (
    DEFAULT_LOCALE,
    SCHEMA_TRANSLATIONS,
    SUPPORTED_LOCALES,
    TRANSLATIONS,
)
from homebase.registry import ModuleRegistry

ALL_MODULES = ["mem", "route", "kb", "swarm", "state", "garden", "api", "test", "conn", "auto", "plug"]


def _full_registry(tmp_path) -> ModuleRegistry:
    module_configs: dict[str, dict[str, object]] = {
        name: {"db_path": str(tmp_path / f"{name}.db")}
        for name in ("mem", "kb", "garden", "state", "api", "conn", "auto", "plug")
    }
    module_configs["plug"]["plugins_dir"] = str(tmp_path / "plugins")
    module_configs["test"] = {"test_root": str(tmp_path / "tests")}
    registry = ModuleRegistry(HomebaseConfig(enabled_modules=ALL_MODULES, module_configs=module_configs))
    loaded, skipped = registry.discover_and_load()
    assert skipped == [], f"modules failed to load: {skipped}"
    assert set(loaded) == set(ALL_MODULES)
    return registry


def test_locales_cover_identical_translation_keys():
    reference = set(TRANSLATIONS["de"])
    for locale in SUPPORTED_LOCALES:
        if locale == DEFAULT_LOCALE:
            continue
        missing = reference - set(TRANSLATIONS[locale])
        extra = set(TRANSLATIONS[locale]) - reference
        assert not missing, f"locale '{locale}' is missing translations: {sorted(missing)}"
        assert not extra, f"locale '{locale}' has keys unknown to 'de': {sorted(extra)}"


def test_schema_locales_cover_identical_keys():
    reference = set(SCHEMA_TRANSLATIONS["de"])
    for locale, entries in SCHEMA_TRANSLATIONS.items():
        assert set(entries) == reference, f"SCHEMA_TRANSLATIONS['{locale}'] diverges from 'de'"


def test_every_registered_tool_is_translated(tmp_path):
    registry = _full_registry(tmp_path)
    tool_keys = {f"tool.{tool.name}" for tool in registry.list_tools()}
    missing = tool_keys - set(TRANSLATIONS["de"])
    assert not missing, (
        f"tools without a 'tool.<name>' translation entry (add them to EVERY locale): {sorted(missing)}"
    )
