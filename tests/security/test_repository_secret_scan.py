"""Regression coverage for the dependency-free repository secret scan."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def _scan(*paths: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "scripts/scan_secrets.py", *(str(path) for path in paths)],
        cwd=REPOSITORY_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def test_repository_contains_no_high_confidence_secret_material() -> None:
    result = _scan()

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Secret scan passed" in result.stdout


def test_secret_scan_detects_but_never_echoes_a_generated_credential(tmp_path: Path) -> None:
    credential = "sk-" + "R" * 24
    probe = tmp_path / "probe.txt"
    probe.write_text(f"credential={credential}\n", encoding="utf-8")

    result = _scan(probe)

    assert result.returncode == 1
    assert "openai_key" in result.stdout
    assert credential not in result.stdout
