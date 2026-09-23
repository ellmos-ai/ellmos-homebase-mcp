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
    assert "Last-checked: 2026-09-21" in llms_text

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
    assert "concurrency:" in ci_text
    assert "cancel-in-progress: true" in ci_text


def test_ruff_config_in_pyproject():
    pyproject_file = REPO_ROOT / "pyproject.toml"
    assert pyproject_file.is_file(), "pyproject.toml must exist"
    pyproject = tomllib.loads(pyproject_file.read_text(encoding="utf-8"))

    assert "tool" in pyproject
    assert "ruff" in pyproject["tool"]
    assert pyproject["tool"]["ruff"]["line-length"] == 120
    assert "lint" in pyproject["tool"]["ruff"]
    assert "C4" in pyproject["tool"]["ruff"]["lint"]["select"]


def test_readme_and_readme_de_quick_navigation_and_mermaid_parity():
    readme_en = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    readme_de = (REPO_ROOT / "README_de.md").read_text(encoding="utf-8")

    assert "## Quick Navigation / Schnellnavigation" in readme_en
    assert "## Schnellnavigation / Quick Navigation" in readme_de

    # Sequence diagrams present in both
    assert "```mermaid\nsequenceDiagram" in readme_en
    assert "```mermaid\nsequenceDiagram" in readme_de
    assert "CanonicalEngineUnavailable" in readme_en and "CanonicalEngineUnavailable" in readme_de
    assert "hb_mem_store" in readme_en and "hb_mem_store" in readme_de

    # Quick navigation anchors present
    for anchor in (
        "#system-architecture",
        "#sequence-flow--lifecycle",
        "#core-capabilities--security-invariants",
        "#target-personas--discoverability",
        "#comparative-matrix-vs-alternatives",
        "#start-here",
        "#mcp-client-configuration",
        "#tools",
        "#discovery-context",
        "#security--vulnerability-reporting",
    ):
        assert anchor in readme_en, f"Missing anchor {anchor} in README.md"

    for anchor in (
        "#systemarchitektur",
        "#sequenzablauf--lebenszyklus",
        "#kernfähigkeiten--sicherheitsinvarianten",
        "#zielgruppen--auffindbarkeit",
        "#vergleichsmatrix-gegenüber-alternativen",
        "#einstieg",
        "#mcp-client-konfiguration",
        "#tools",
        "#discovery-kontext",
        "#sicherheit--schwachstellenmeldung",
    ):
        assert anchor in readme_de, f"Missing anchor {anchor} in README_de.md"


def test_capabilities_and_security_invariants_table_parity():
    readme_en = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    readme_de = (REPO_ROOT / "README_de.md").read_text(encoding="utf-8")

    assert "## Core Capabilities & Security Invariants" in readme_en
    assert "## Kernfähigkeiten & Sicherheitsinvarianten" in readme_de

    for key_term in ("100% Local-First & Zero-Egress", "Strict Engine Seams & Fail-Closed", "MODE-CONTRACT.md", "agent_id"):
        assert key_term in readme_en, f"Missing key term {key_term} in README.md"


def test_pyproject_pep621_classifiers_and_project_urls():
    pyproject_file = REPO_ROOT / "pyproject.toml"
    assert pyproject_file.is_file(), "pyproject.toml must exist"
    pyproject = tomllib.loads(pyproject_file.read_text(encoding="utf-8"))

    project = pyproject["project"]
    assert "urls" in project
    urls = project["urls"]
    assert "Homepage" in urls
    assert "Documentation" in urls
    assert "Repository" in urls
    assert "Issues" in urls
    assert "Bug Tracker" in urls
    assert "Changelog" in urls
    assert "LLM Ready" in urls
    assert "Third-Party Licenses" in urls
    assert "Marketing Log" in urls
    assert "Parent Organization" in urls
    assert "Umbrella Ecosystem" in urls

    classifiers = project["classifiers"]
    for expected_cls in (
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Operating System :: OS Independent",
    ):
        assert expected_cls in classifiers, f"Missing classifier {expected_cls}"


def test_security_policy_sla_and_reporting_contracts():
    security_file = REPO_ROOT / "SECURITY.md"
    assert security_file.is_file(), "SECURITY.md must exist in repository root"
    content = security_file.read_text(encoding="utf-8")

    assert "48 hours" in content
    assert "48 Stunden" in content
    assert "30 calendar days" in content
    assert "30 Kalendertagen" in content
    assert "support@lukasgeiger.com" in content
    assert "security@ellmos.ai" in content
    assert "Security Advisories" in content
    assert "0.1.0-alpha.x" in content


def test_readme_ecosystem_table_parity():
    readme_en = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    readme_de = (REPO_ROOT / "README_de.md").read_text(encoding="utf-8")

    sibling_tools = (
        "FileCommander",
        "CodeCommander",
        "Clatcher",
        "n8n-manager-mcp",
        "ControlCenter",
        "ServerCommander",
        "Blender Use",
        "Open Compute",
        "ProFiler",
        "DokuZen",
        "PDFtoPDFocr",
        "KnowledgeDigest",
        "DevCenter",
        "CodeBox",
        "MemoryHooker",
        "sqlite-transit-sync",
    )

    for tool in sibling_tools:
        assert tool in readme_en, f"Missing {tool} in README.md ecosystem"
        assert tool in readme_de, f"Missing {tool} in README_de.md ecosystem"


def test_package_json_repository_and_homepage_urls():
    package = json.loads((REPO_ROOT / "package.json").read_text(encoding="utf-8"))
    assert "repository" in package
    assert "ellmos-ai/ellmos-homebase-mcp" in str(package["repository"])
    assert "homepage" in package
    assert "ellmos-ai/ellmos-homebase-mcp" in str(package["homepage"])


def test_gitignore_hygiene():
    gitignore_path = REPO_ROOT / ".gitignore"
    assert gitignore_path.is_file(), ".gitignore must exist"
    content = gitignore_path.read_text(encoding="utf-8")

    patterns = (
        "*conflicted copy*",
        "* (kopie)*",
        "* (Kopie)*",
        "* (copy)*",
        "* (Copy)*",
        "*-WORKSTATION*",
        "*-ASUS*",
        "*-ASUS-GEI*",
        "*-LAPTOP*",
        "*-Mac Studio*",
        "*.sync-conflict-*",
        "*.conflict",
        "*-CONFLIT-*",
        "*-conflict-*",
        "*.sync-temp-*",
        "LOCK",
        "LOCK.*",
        "*.lock",
        "LOCK*.txt",
        "LOCK.permissions.json",
        "!package-lock.json",
        ".wheel-smoke/",
        "wheelhouse/",
        ".coverage.*",
        ".hypothesis/",
        ".nyc_output/",
        ".turbo/",
        ".tox/",
        "*.tmp",
        "*.bak",
        "*.orig",
        "*.rej",
        "*.crt",
        "*.cert",
        "*.csr",
        "id_rsa*",
        "id_ed25519*",
        "*.token",
        "*.secret",
        "*secret*.json",
        "CONFLICT_REVIEW_LOG*",
        "Thumbs.db",
        ".DS_Store",
    )
    for pattern in patterns:
        assert pattern in content, f"Missing pattern {pattern} in .gitignore"


def test_pyproject_pytest_configuration():
    pyproject_file = REPO_ROOT / "pyproject.toml"
    assert pyproject_file.is_file(), "pyproject.toml must exist"
    pyproject = tomllib.loads(pyproject_file.read_text(encoding="utf-8"))

    pytest_cfg = pyproject.get("tool", {}).get("pytest", {}).get("ini_options", {})
    assert "testpaths" in pytest_cfg
    assert "tests" in pytest_cfg["testpaths"]
    assert "-ra -v" in pytest_cfg.get("addopts", "")

    urls = pyproject.get("project", {}).get("urls", {})
    assert "Security" in urls
    assert "SECURITY.md" in urls["Security"]


def test_security_policy_umbrella_contact_and_triage():
    security_file = REPO_ROOT / "SECURITY.md"
    assert security_file.is_file(), "SECURITY.md must exist"
    content = security_file.read_text(encoding="utf-8")

    assert "security@open-bricks.org" in content
    assert "5 business days" in content
    assert "5 Werktagen" in content


def test_third_party_licenses_inventory_and_manifest_entry():
    licenses_file = REPO_ROOT / "THIRD_PARTY_LICENSES.md"
    assert licenses_file.is_file(), "THIRD_PARTY_LICENSES.md must exist in repository root"
    content = licenses_file.read_text(encoding="utf-8")
    assert "Third-Party License Review" in content
    assert "update-notifier" in content
    assert "mcp" in content
    assert "tomli" in content
    assert "pytest" in content
    assert "PSFL" in content or "Python Software Foundation" in content

    package = json.loads((REPO_ROOT / "package.json").read_text(encoding="utf-8"))
    assert "THIRD_PARTY_LICENSES.md" in package.get("files", []), "THIRD_PARTY_LICENSES.md must be in package.json files"


def test_marketing_log_and_manifest_entry():
    marketing_file = REPO_ROOT / "MARKETING-LOG.txt"
    assert marketing_file.is_file(), "MARKETING-LOG.txt must exist in repository root"
    content = marketing_file.read_text(encoding="utf-8")
    assert "DISCOVERABILITY & MARKETING LOG" in content
    assert "Persona 1" in content
    assert "Persona 2" in content
    assert "Persona 3" in content
    assert "Persona 4" in content
    assert "INV-LOCAL-01" in content
    assert "INV-SLA-10" in content

    package = json.loads((REPO_ROOT / "package.json").read_text(encoding="utf-8"))
    assert "MARKETING-LOG.txt" in package.get("files", []), "MARKETING-LOG.txt must be in package.json files"


def test_ten_governance_invariants_parity_in_readmes():
    readme_en = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    readme_de = (REPO_ROOT / "README_de.md").read_text(encoding="utf-8")

    assert "## Governance & Runtime Invariants" in readme_en
    assert "## Governance & Laufzeit-Invarianten" in readme_de

    invariants = [
        "INV-LOCAL-01",
        "INV-ENGINE-02",
        "INV-SEAM-03",
        "INV-PROV-04",
        "INV-CRED-05",
        "INV-STAGE-06",
        "INV-I18N-07",
        "INV-PERM-08",
        "INV-SYNC-09",
        "INV-SLA-10",
    ]
    for inv in invariants:
        assert inv in readme_en, f"Missing {inv} in README.md"
        assert inv in readme_de, f"Missing {inv} in README_de.md"


def test_glama_metadata_parity():
    glama_file = REPO_ROOT / "glama.json"
    assert glama_file.is_file(), "glama.json must exist"
    data = json.loads(glama_file.read_text(encoding="utf-8"))
    assert data["version"] == "0.1.0-alpha.29"
    assert data["tools"]["count"] == 51

def test_github_actions_ci_timeout_guardrails():
    ci_file = REPO_ROOT / ".github" / "workflows" / "tests.yml"
    assert ci_file.is_file(), "tests.yml must exist"
    ci_text = ci_file.read_text(encoding="utf-8")
    assert "timeout-minutes: 15" in ci_text
    assert ci_text.count("timeout-minutes: 15") >= 2


def test_stale_workflow_hardening():
    stale_file = REPO_ROOT / ".github" / "workflows" / "stale.yml"
    assert stale_file.is_file(), "stale.yml must exist"
    stale_text = stale_file.read_text(encoding="utf-8")
    assert "actions/stale@v9" in stale_text
    assert "timeout-minutes: 10" in stale_text
    assert "issues: write" in stale_text
    assert "pull-requests: write" in stale_text
    assert "cron: '30 1 * * *'" in stale_text


def test_changelog_release_entry_exists():
    changelog_file = REPO_ROOT / "CHANGELOG.md"
    assert changelog_file.is_file(), "CHANGELOG.md must exist"
    content = changelog_file.read_text(encoding="utf-8")
    assert "## 0.1.0-alpha.29" in content
    assert "2026-09-21" in content
    assert "## 0.1.0-alpha.28" in content


def test_target_personas_discoverability_parity():
    readme_en = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    readme_de = (REPO_ROOT / "README_de.md").read_text(encoding="utf-8")

    assert "## Target Personas & Discoverability" in readme_en
    assert "## Zielgruppen & Auffindbarkeit" in readme_de

    for persona in ("[PERSONA-01]", "[PERSONA-02]", "[PERSONA-03]", "[PERSONA-04]"):
        assert persona in readme_en, f"Missing {persona} in README.md"
        assert persona in readme_de, f"Missing {persona} in README_de.md"

    assert "Local LLM & Edge AI Developers" in readme_en
    assert "Entwickler lokaler LLMs & Edge-KI" in readme_de
    assert "Multi-Agent Swarm Orchestrators & Swarm Architects" in readme_en
    assert "Enterprise Security & Data Governance Officers" in readme_en
    assert "Cross-Framework AI Assistants & Pair Programmers" in readme_en


def test_comparative_matrix_vs_alternatives_parity():
    readme_en = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    readme_de = (REPO_ROOT / "README_de.md").read_text(encoding="utf-8")

    assert "## Comparative Matrix vs. Alternatives" in readme_en
    assert "## Vergleichsmatrix gegenüber Alternativen" in readme_de

    invariants = [
        "INV-LOCAL-01",
        "INV-ENGINE-02",
        "INV-SEAM-03",
        "INV-PROV-04",
        "INV-CRED-05",
        "INV-STAGE-06",
        "INV-I18N-07",
        "INV-PERM-08",
        "INV-SYNC-09",
        "INV-SLA-10",
    ]
    for inv in invariants:
        assert inv in readme_en, f"Missing invariant {inv} in README.md comparative matrix"
        assert inv in readme_de, f"Missing invariant {inv} in README_de.md comparative matrix"

    for alt in ("Cloud Memory SaaS", "Generic Memory MCPs", "Heavy Agent Frameworks"):
        assert alt in readme_en, f"Missing alternative {alt} in README.md"


def test_third_party_licenses_governance_invariants_verification():
    licenses_file = REPO_ROOT / "THIRD_PARTY_LICENSES.md"
    assert licenses_file.is_file(), "THIRD_PARTY_LICENSES.md must exist in repository root"
    content = licenses_file.read_text(encoding="utf-8")

    assert "Stand: 2026-09-21" in content
    assert "PEP 639" in content
    assert "## 10 Governance & Runtime Invariants Verification" in content
    assert "CONFIRMED / VERIFIED" in content
    assert "Zero-Copyleft & Permissive Licensing Affirmation" in content

    for inv in [
        "INV-LOCAL-01",
        "INV-ENGINE-02",
        "INV-SEAM-03",
        "INV-PROV-04",
        "INV-CRED-05",
        "INV-STAGE-06",
        "INV-I18N-07",
        "INV-PERM-08",
        "INV-SYNC-09",
        "INV-SLA-10",
    ]:
        assert inv in content, f"Missing invariant {inv} in THIRD_PARTY_LICENSES.md"


def test_project_urls_contain_only_urls():
    """Regression zu T-20260913-506582780.

    Commit aef6642 ("PEP 621 and metadata parity") haengte einen
    `[project.urls]`-Block direkt vor `dependencies`, wodurch die
    Abhaengigkeitsliste in die URL-Tabelle rutschte. `pip install -e .` brach
    danach mit "URL `dependencies` of field `project.urls` must be a string"
    ab -- ein Fehler, den kein Importtest sieht, weil er erst beim Bauen auftritt.
    """
    pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    for name, value in pyproject["project"].get("urls", {}).items():
        assert isinstance(value, str), f"[project.urls] enthaelt die Nicht-URL {name!r}"


def test_runtime_dependencies_are_declared():
    """Zweite Haelfte desselben Bugs: das Paket stand ohne Laufzeitabhaengigkeiten da."""
    pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    dependencies = pyproject["project"].get("dependencies", [])
    assert dependencies, "[project] deklariert keine dependencies"
    assert any(dep.startswith("mcp") for dep in dependencies)


def test_pep639_license_files_metadata():
    pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    project = pyproject.get("project", {})
    license_files = project.get("license-files", [])
    assert "LICENSE" in license_files, "LICENSE must be declared in [project].license-files"
    assert "NOTICE" in license_files, "NOTICE must be declared in [project].license-files"
    assert "THIRD_PARTY_LICENSES.md" in license_files, "THIRD_PARTY_LICENSES.md must be declared in [project].license-files"


def test_security_hygiene_zero_hardcoded_secrets_and_personal_paths():
    secret_patterns = [
        re.compile(r"""(?:api[_-]?key|secret|token|password|auth[_-]?token)\s*[:=]\s*["'][A-Za-z0-9_\-]{20,}["']""", re.IGNORECASE),
        re.compile(r"""-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"""),
        re.compile(r"""ghp_[A-Za-z0-9]{36}"""),
        re.compile(r"""xox[baprs]-[A-Za-z0-9\-]{10,}"""),
    ]
    path_pattern = re.compile(r"""[A-Za-z]:[\\/]Users[\\/][A-Za-z0-9_.\-]+""", re.IGNORECASE)

    ignored_dirs = {".git", ".pytest_cache", ".ruff_cache", "node_modules", "__pycache__"}
    ignored_suffixes = {".png", ".jpg", ".jpeg", ".gif", ".ico", ".woff", ".woff2", ".ttf", ".eot", ".db", ".sqlite", ".pyc"}

    for path in REPO_ROOT.rglob("*"):
        if not path.is_file():
            continue
        if any(part in ignored_dirs for part in path.parts):
            continue
        if path.suffix in ignored_suffixes:
            continue
        if path.name == "test_metadata.py":
            continue

        text = path.read_text(encoding="utf-8", errors="ignore")
        for pattern in secret_patterns:
            assert not pattern.search(text), f"Potential hardcoded secret in {path.relative_to(REPO_ROOT)}"
        assert not path_pattern.search(text), f"Hardcoded developer personal path in {path.relative_to(REPO_ROOT)}"


def test_root_notice_attribution_and_manifest_inclusion():
    notice_file = REPO_ROOT / "NOTICE"
    assert notice_file.is_file(), "NOTICE must exist in repository root"
    content = notice_file.read_text(encoding="utf-8")
    assert "ellmos-homebase-mcp" in content
    assert "Lukas Geiger" in content
    assert "ellmos-ai" in content
    assert "open-bricks" in content
    assert "MIT License" in content

    package = json.loads((REPO_ROOT / "package.json").read_text(encoding="utf-8"))
    assert "NOTICE" in package.get("files", []), "NOTICE must be listed in package.json files array"


def test_bilingual_18_point_dual_anchors_and_statutory_disclaimer():
    readme_en = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    readme_de = (REPO_ROOT / "README_de.md").read_text(encoding="utf-8")

    for i in range(1, 19):
        sec_tag = f'id="sec-{i:02d}"'
        assert sec_tag in readme_en, f"Missing {sec_tag} in README.md"
        assert sec_tag in readme_de, f"Missing {sec_tag} in README_de.md"

    # § 521 BGB German statutory notice & liability limitation
    assert "§ 521 BGB" in readme_en
    assert "§ 521 BGB" in readme_de
    assert "Gefälligkeitsrecht" in readme_en
    assert "Gefälligkeitsrecht" in readme_de
    assert "Vorsatz" in readme_en and "Vorsatz" in readme_de
    assert "grobe Fahrlässigkeit" in readme_en and "grobe Fahrlässigkeit" in readme_de
    assert "arglistiges Verschweigen" in readme_en and "arglistiges Verschweigen" in readme_de
    assert "48 hours" in readme_en
    assert "48 Stunden" in readme_de


def test_level_1_sbom_cross_reference_matrix_and_certifications():
    licenses_file = REPO_ROOT / "THIRD_PARTY_LICENSES.md"
    content = licenses_file.read_text(encoding="utf-8")

    assert "Stand: 2026-09-23" in content
    assert "## Level 1 SBOM Invariant Cross-Reference Matrix" in content
    assert "RunAsInvoker" in content
    assert "Zero-Copyleft & Permissive Licensing Affirmation" in content

    # All 10 invariants mapped in SBOM table
    for inv in (
        "INV-LOCAL-01",
        "INV-ENGINE-02",
        "INV-SEAM-03",
        "INV-PROV-04",
        "INV-CRED-05",
        "INV-STAGE-06",
        "INV-I18N-07",
        "INV-PERM-08",
        "INV-SYNC-09",
        "INV-SLA-10",
    ):
        assert inv in content, f"Missing invariant {inv} in THIRD_PARTY_LICENSES.md SBOM"


def test_keywords_saturation_across_manifests():
    pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    package = json.loads((REPO_ROOT / "package.json").read_text(encoding="utf-8"))

    py_keywords = pyproject.get("project", {}).get("keywords", [])
    pkg_keywords = package.get("keywords", [])

    assert len(py_keywords) >= 20, f"Expected >=20 keywords in pyproject.toml, got {len(py_keywords)}"
    assert len(pkg_keywords) >= 20, f"Expected >=20 keywords in package.json, got {len(pkg_keywords)}"

    required_keywords = {"zero-egress", "fail-closed", "open-bricks", "ellmos-ai", "local-first", "mcp"}
    assert required_keywords.issubset(set(py_keywords)), "pyproject.toml missing required high-intent keywords"
    assert required_keywords.issubset(set(pkg_keywords)), "package.json missing required high-intent keywords"
