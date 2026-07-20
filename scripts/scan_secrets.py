"""Scan tracked and untracked repository files for high-confidence secret material."""

from __future__ import annotations

import argparse
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

_PATTERNS = (
    ("aws_access_key", re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")),
    ("github_token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b")),
    ("github_fine_grained_token", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b")),
    ("gitlab_token", re.compile(r"\bglpat-[A-Za-z0-9_-]{20,}\b")),
    ("openai_key", re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{16,}\b")),
    ("stripe_live_key", re.compile(r"\b(?:sk|rk)_live_[A-Za-z0-9]{16,}\b")),
    ("slack_token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
    ("google_api_key", re.compile(r"\bAIza[0-9A-Za-z_-]{20,}\b")),
    ("npm_token", re.compile(r"\bnpm_[A-Za-z0-9]{20,}\b")),
    (
        "sendgrid_key",
        re.compile(r"\bSG\.[A-Za-z0-9_-]{16,}\.[A-Za-z0-9_-]{16,}\b"),
    ),
    (
        "private_key",
        re.compile(r"-----BEGIN (?:[A-Z0-9 ]+ )?PRIVATE KEY-----"),
    ),
)
_SENSITIVE_FILENAMES = frozenset(
    {".env", "credentials.json", "service-account.json", "service_account.json"}
)
_SENSITIVE_SUFFIXES = frozenset({".key", ".p12", ".pfx", ".pem"})
_SKIPPED_PARTS = frozenset({".git", ".mypy_cache", ".pytest_cache", ".ruff_cache", "__pycache__"})


@dataclass(frozen=True, slots=True)
class Finding:
    path: Path
    line_number: int
    rule: str


def _repository_files(root: Path) -> tuple[Path, ...]:
    result = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=root,
        check=True,
        capture_output=True,
    )
    return tuple(
        root / raw_path.decode("utf-8") for raw_path in result.stdout.split(b"\0") if raw_path
    )


def _explicit_files(paths: tuple[Path, ...]) -> tuple[Path, ...]:
    files: list[Path] = []
    for path in paths:
        if path.is_file():
            files.append(path)
        elif path.is_dir():
            files.extend(
                candidate
                for candidate in path.rglob("*")
                if candidate.is_file() and not set(candidate.parts).intersection(_SKIPPED_PARTS)
            )
    return tuple(files)


def scan_files(paths: tuple[Path, ...]) -> tuple[Finding, ...]:
    """Return locations and rule names without retaining or printing matching values."""
    findings: list[Finding] = []
    for path in sorted(set(paths)):
        if path.name in _SENSITIVE_FILENAMES or path.suffix.lower() in _SENSITIVE_SUFFIXES:
            findings.append(Finding(path=path, line_number=1, rule="sensitive_filename"))
        try:
            content = path.read_bytes()
        except OSError:
            findings.append(Finding(path=path, line_number=1, rule="unreadable_file"))
            continue
        if b"\0" in content:
            continue
        text = content.decode("utf-8", errors="ignore")
        for rule, pattern in _PATTERNS:
            for match in pattern.finditer(text):
                findings.append(
                    Finding(
                        path=path,
                        line_number=text.count("\n", 0, match.start()) + 1,
                        rule=rule,
                    )
                )
    return tuple(findings)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Scan repository files for private-key material and high-confidence credential formats."
        )
    )
    parser.add_argument(
        "paths",
        nargs="*",
        type=Path,
        help="Optional files/directories; default is tracked plus non-ignored untracked files.",
    )
    arguments = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    try:
        files = (
            _explicit_files(tuple(path.resolve() for path in arguments.paths))
            if arguments.paths
            else _repository_files(root)
        )
    except subprocess.CalledProcessError:
        print("Secret scan could not enumerate repository files.")
        return 2

    findings = scan_files(files)
    if findings:
        print("Potential secret material detected (values intentionally omitted):")
        for finding in findings:
            try:
                display_path = finding.path.resolve().relative_to(root)
            except ValueError:
                display_path = finding.path.resolve()
            safe_path = str(display_path).replace("\r", "\\r").replace("\n", "\\n")
            print(f"{safe_path}:{finding.line_number} [{finding.rule}]")
        return 1
    print(f"Secret scan passed: {len(files)} repository files checked.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
