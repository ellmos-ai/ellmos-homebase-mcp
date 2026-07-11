from __future__ import annotations

import json
import re
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.10
    import tomli as tomllib


REPO_ROOT = Path(__file__).resolve().parents[1]


def _pep440_alpha_to_npm(version: str) -> str:
    match = re.fullmatch(r"(\d+\.\d+\.\d+)a(\d+)", version)
    if match:
        return f"{match.group(1)}-alpha.{match.group(2)}"
    return version


def test_release_metadata_versions_stay_in_sync():
    package = json.loads((REPO_ROOT / "package.json").read_text(encoding="utf-8"))
    server = json.loads((REPO_ROOT / "server.json").read_text(encoding="utf-8"))
    pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    init_py = (REPO_ROOT / "src" / "homebase" / "__init__.py").read_text(encoding="utf-8")

    package_version = package["version"]
    pyproject_version = _pep440_alpha_to_npm(pyproject["project"]["version"])
    init_version = _pep440_alpha_to_npm(re.search(r'__version__ = "([^"]+)"', init_py).group(1))

    assert package["name"] == "ellmos-homebase-mcp"
    assert package_version == pyproject_version == init_version
    assert server["version"] == package_version
    assert server["packages"][0]["identifier"] == package["name"]
    assert server["packages"][0]["version"] == package_version


def test_homebase_concept_keeps_non_module_boundaries_documented():
    concept = (REPO_ROOT / "KONZEPT.md").read_text(encoding="utf-8")

    section_match = re.search(
        r"### Bewusst nicht integriert \(Audit 2026-06-27\)(?P<section>.*?)(?:\n## |\Z)",
        concept,
        flags=re.S,
    )
    assert section_match, "KONZEPT.md must keep the explicit non-integration section"
    section = section_match.group("section")

    for module_name in ("ellmos-chat", "ellmos-core", "ellmos-stack", "open-compute"):
        assert module_name in section

    assert "Konsument" in section
    assert "Deployment" in section
    assert "andere Domäne" in section
