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


def test_security_policy_and_manifest_hygiene():
    security_file = REPO_ROOT / "SECURITY.md"
    assert security_file.is_file(), "SECURITY.md must exist in repository root"
    content = security_file.read_text(encoding="utf-8")
    assert "Security Policy" in content
    assert "Sicherheitsrichtlinie" in content
    assert "Local-First" in content or "local-first" in content
    assert "security@ellmos.ai" in content
    assert "Reporting a Vulnerability" in content

    package = json.loads((REPO_ROOT / "package.json").read_text(encoding="utf-8"))
    assert "SECURITY.md" in package.get("files", []), "SECURITY.md must be included in package.json files"


def test_llms_txt_and_discoverability_parity():
    llms_file = REPO_ROOT / "llms.txt"
    assert llms_file.is_file(), "llms.txt must exist in repository root"
    llms_text = llms_file.read_text(encoding="utf-8")
    assert "ellmos-homebase-mcp" in llms_text
    assert "Canonical repository:" in llms_text
    assert "Last-checked: 2026-08-21" in llms_text

    readme_en = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    readme_de = (REPO_ROOT / "README_de.md").read_text(encoding="utf-8")

    assert "open-bricks" in readme_en and "open-bricks" in readme_de
    assert "ellmos-ai" in readme_en and "ellmos-ai" in readme_de
    assert "llms.txt" in readme_en and "llms.txt" in readme_de


def test_github_actions_workflow_ci_matrix_and_lint():
    ci_file = REPO_ROOT / ".github" / "workflows" / "tests.yml"
    assert ci_file.is_file(), "CI workflow tests.yml must exist"
    ci_text = ci_file.read_text(encoding="utf-8")

    assert "3.10" in ci_text
    assert "3.11" in ci_text
    assert "3.12" in ci_text
    assert "3.13" in ci_text
    assert "ruff check ." in ci_text
    assert "compileall" in ci_text
    assert "npm run smoke" in ci_text


def test_ruff_config_in_pyproject():
    pyproject_file = REPO_ROOT / "pyproject.toml"
    assert pyproject_file.is_file(), "pyproject.toml must exist"
    pyproject = tomllib.loads(pyproject_file.read_text(encoding="utf-8"))

    assert "tool" in pyproject
    assert "ruff" in pyproject["tool"]
    assert pyproject["tool"]["ruff"]["line-length"] == 120
    assert "lint" in pyproject["tool"]["ruff"]

