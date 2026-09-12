import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_node_launcher_ignores_same_name_package_in_working_directory(tmp_path: Path):
    malicious_package = tmp_path / "homebase"
    malicious_package.mkdir()
    marker = tmp_path / "launcher-hijacked.txt"
    (malicious_package / "__init__.py").write_text("", encoding="utf-8")
    (malicious_package / "server.py").write_text(
        "from pathlib import Path\n"
        f"Path({str(marker)!r}).write_text('hijacked', encoding='utf-8')\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        ["node", str(REPO_ROOT / "bin" / "ellmos-homebase.js")],
        check=False,
        cwd=tmp_path,
        env={**os.environ, "PYTHON": sys.executable},
        input="",
        capture_output=True,
        text=True,
        timeout=20,
    )

    assert not marker.exists(), (
        "The npm launcher imported attacker-controlled workspace code. "
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    assert result.returncode == 0, result.stderr
