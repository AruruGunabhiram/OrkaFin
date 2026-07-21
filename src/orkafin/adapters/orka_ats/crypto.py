"""HMAC authentication envelope for OrkaATS Apps Script requests."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from collections.abc import Mapping
from typing import TypedDict, cast
from uuid import uuid4

from pydantic import JsonValue, SecretStr


class SignedPayloadEnvelope(TypedDict):
    """JSON shape accepted by the OrkaATS Apps Script ``doPost`` receiver."""

    version: int
    keyId: str
    nonce: str
    timestamp: int
    payload: dict[str, JsonValue]
    signature: str


def canonical_payload_json(payload: Mapping[str, JsonValue]) -> str:
    """Serialize payload deterministically for cross-runtime signature verification."""

    return json.dumps(
        dict(payload),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def create_signed_envelope(
    payload: Mapping[str, JsonValue],
    *,
    version: int,
    key_id: str,
    shared_secret: SecretStr | str,
) -> SignedPayloadEnvelope:
    """Wrap one payload in a fresh timestamped HMAC-SHA-256 envelope.

    The 64-character hexadecimal secret is treated as the shared UTF-8 key, matching
    Apps Script's string-key HMAC API. It is never included in the returned envelope.
    """

    payload_copy = cast(dict[str, JsonValue], json.loads(canonical_payload_json(payload)))
    nonce = str(uuid4())
    timestamp = int(time.time())
    payload_json = canonical_payload_json(payload_copy)
    signing_input = f"{version}:{key_id}:{nonce}:{timestamp}:{payload_json}"
    secret_value = (
        shared_secret.get_secret_value() if isinstance(shared_secret, SecretStr) else shared_secret
    )
    signature = hmac.new(
        secret_value.encode("utf-8"),
        signing_input.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return {
        "version": version,
        "keyId": key_id,
        "nonce": nonce,
        "timestamp": timestamp,
        "payload": payload_copy,
        "signature": signature,
    }
