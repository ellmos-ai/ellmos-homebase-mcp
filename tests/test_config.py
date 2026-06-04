from homebase.config import DEFAULT_ENABLED_MODULES, load_config


def test_load_config_defaults_when_missing():
    config = load_config("missing-homebase.toml")

    assert config.enabled_modules == DEFAULT_ENABLED_MODULES
    assert config.module_configs == {}


def test_modules_section_without_enabled_uses_defaults(tmp_path):
    config_path = tmp_path / "homebase.toml"
    config_path.write_text(
        """
[server]
name = "ellmos-homebase"

[modules]

[mem]
db_path = "memory.db"
""".strip(),
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert config.enabled_modules == DEFAULT_ENABLED_MODULES
    assert config.module_config("mem") == {"db_path": "memory.db"}


def test_single_enabled_module_string_is_normalized(tmp_path):
    config_path = tmp_path / "homebase.toml"
    config_path.write_text('[modules]\nenabled = "mem"\n', encoding="utf-8")

    config = load_config(config_path)

    assert config.enabled_modules == ["mem"]
