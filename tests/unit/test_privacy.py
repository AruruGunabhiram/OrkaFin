"""Boundary-focused tests for recognizable sensitive-text minimization."""

from __future__ import annotations

import pytest

from orkafin.domain.privacy import contains_sensitive_text, redact_sensitive_text


@pytest.mark.parametrize(
    "sensitive_value",
    (
        "person.marker" + "@" + "example.invalid",
        "api_key=" + "sk-" + "A" * 24,
        'password="a quoted secret value"',
        "Bearer " + "B" * 24,
        "https://user:password@example.invalid/path",
        "AKIA" + "C" * 16,
        "-----BEGIN " + "PRIVATE KEY-----",
    ),
)
def test_recognizable_sensitive_values_are_removed(sensitive_value: str) -> None:
    redacted = redact_sensitive_text(f"before {sensitive_value} after")

    assert contains_sensitive_text(f"before {sensitive_value} after")
    assert sensitive_value not in redacted
    assert "[REDACTED]" in redacted


def test_benign_product_guidance_is_unchanged() -> None:
    guidance = "Explain the approved candidate profile and recruitment pipeline."

    assert redact_sensitive_text(guidance) == guidance
    assert not contains_sensitive_text(guidance)
