"""Content-based minimization for text that may cross persistence or provider boundaries."""

from __future__ import annotations

import re

REDACTED_TEXT = "[REDACTED]"

_EMAIL_PATTERN = re.compile(
    r"(?<![A-Za-z0-9._%+-])"
    r"[A-Za-z0-9._%+-]{1,64}@[A-Za-z0-9.-]{1,253}\.[A-Za-z]{2,63}"
    r"(?![A-Za-z0-9._%+-])"
)
_AUTHORIZATION_PATTERN = re.compile(
    r"\b(?:bearer|basic)\s+[A-Za-z0-9._~+/=-]{8,}",
    re.IGNORECASE,
)
_CREDENTIAL_ASSIGNMENT_PATTERN = re.compile(
    r"\b(?P<label>api[_-]?key|access[_-]?token|auth(?:orization)?|password|secret|token)"
    r"\s*[:=]\s*(?P<value>\"[^\"\r\n]{1,256}\"|'[^'\r\n]{1,256}'|[^\s,;]{1,256})",
    re.IGNORECASE,
)
_CREDENTIAL_URL_PATTERN = re.compile(
    r"(?P<scheme>[a-z][a-z0-9+.-]*://)[^\s/@:]+:[^\s/@]+@",
    re.IGNORECASE,
)
_HIGH_CONFIDENCE_SECRET_PATTERNS = (
    re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{16,}\b"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),
    re.compile(r"\bAIza[0-9A-Za-z_-]{20,}\b"),
    re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----"),
)


def redact_sensitive_text(value: str) -> str:
    """Replace recognizable credentials and email addresses without retaining their values."""
    redacted = _CREDENTIAL_ASSIGNMENT_PATTERN.sub(
        lambda match: f"{match.group('label')}={REDACTED_TEXT}", value
    )
    redacted = _CREDENTIAL_URL_PATTERN.sub(
        lambda match: f"{match.group('scheme')}{REDACTED_TEXT}@", redacted
    )
    redacted = _AUTHORIZATION_PATTERN.sub(REDACTED_TEXT, redacted)
    redacted = _EMAIL_PATTERN.sub(REDACTED_TEXT, redacted)
    for pattern in _HIGH_CONFIDENCE_SECRET_PATTERNS:
        redacted = pattern.sub(REDACTED_TEXT, redacted)
    return redacted


def contains_sensitive_text(value: str) -> bool:
    """Return whether text contains a recognizable value that must not cross the boundary."""
    return redact_sensitive_text(value) != value
