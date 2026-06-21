from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _check_ignore(path: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "check-ignore", "--quiet", path],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def test_local_secret_and_credential_files_are_ignored():
    ignored = [
        ".env",
        ".env.local",
        "homebase.toml",
        "config/homebase.toml",
        "config/user.local.toml",
        "profile.secret.toml",
        "secrets.json",
        "credentials.json",
        "token.json",
        "tokens.json",
        "github.token.json",
        ".npmrc",
        ".pypirc",
        "npm_recovery_codes.txt",
        "id_rsa",
        "id_ed25519",
        "id_ecdsa",
        "id_dsa",
        "private.pem",
        "client.key",
        ".homebase/memory.db",
    ]

    for path in ignored:
        assert _check_ignore(path).returncode == 0, path


def test_public_examples_and_package_metadata_stay_trackable():
    trackable = [
        ".env.example",
        "config/homebase.example.toml",
        "package.json",
        "package-lock.json",
        "pyproject.toml",
        "server.json",
    ]

    for path in trackable:
        assert _check_ignore(path).returncode == 1, path


def test_npm_package_config_allowlist_is_narrow():
    package = json.loads((REPO_ROOT / "package.json").read_text(encoding="utf-8"))
    package_files = package["files"]

    assert "config/homebase.example.toml" in package_files
    assert "config/" not in package_files


def test_npmignore_blocks_local_config_and_secret_artifacts():
    npmignore = (REPO_ROOT / ".npmignore").read_text(encoding="utf-8").splitlines()
    ignored = set(npmignore)

    expected = {
        "homebase.toml",
        "config/homebase.toml",
        "config/*.local.toml",
        "config/*.secret.toml",
        "token.json",
        "tokens.json",
        "*.token.json",
        ".npmrc",
        ".pypirc",
        "*recovery*codes*.txt",
        "id_rsa",
        "id_ed25519",
        "id_ecdsa",
        "id_dsa",
        "*.pem",
        "*.key",
    }

    assert expected <= ignored


def test_npm_pack_excludes_local_config_and_secret_artifacts_when_present():
    local_artifacts = [
        REPO_ROOT / "homebase.toml",
        REPO_ROOT / "config" / "homebase.toml",
        REPO_ROOT / "config" / "operator.local.toml",
        REPO_ROOT / "config" / "operator.secret.toml",
        REPO_ROOT / "token.json",
        REPO_ROOT / "github.token.json",
        REPO_ROOT / "id_ed25519",
        REPO_ROOT / "private.pem",
    ]

    for path in local_artifacts:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("local test artifact\n", encoding="utf-8")

    try:
        npm_bin = "npm.cmd" if os.name == "nt" else "npm"
        result = subprocess.run(
            [npm_bin, "pack", "--dry-run", "--json"],
            cwd=REPO_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        assert result.returncode == 0, result.stderr

        pack_info = json.loads(result.stdout)[0]
        packed_paths = {entry["path"] for entry in pack_info["files"]}

        assert "config/homebase.example.toml" in packed_paths
        for path in local_artifacts:
            assert path.relative_to(REPO_ROOT).as_posix() not in packed_paths
    finally:
        for path in local_artifacts:
            path.unlink(missing_ok=True)
