"""Minimal OpenAI-compatible adapter, disabled unless explicitly configured."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Protocol
from urllib.request import Request, urlopen

from pydantic import SecretStr, ValidationError

from orkafin.providers.contracts import ProviderDraft, ProviderRequest
from orkafin.providers.prompts import build_prompt_messages


class ProviderError(RuntimeError):
    """Safe category for remote provider timeout, transport, and output failures."""


class ExternalProviderTransport(Protocol):
    """Injectable minimal transport used to keep adapter tests fully offline."""

    def post_json(
        self, *, url: str, headers: Mapping[str, str], payload: Mapping[str, object], timeout: float
    ) -> Mapping[str, object]:
        """Send a JSON request and return a parsed JSON object."""


class UrllibExternalProviderTransport:
    """Standard-library HTTPS transport used only in explicitly external mode."""

    def post_json(
        self, *, url: str, headers: Mapping[str, str], payload: Mapping[str, object], timeout: float
    ) -> Mapping[str, object]:
        request = Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=dict(headers),
            method="POST",
        )
        try:
            with urlopen(request, timeout=timeout) as response:  # noqa: S310 - configured HTTPS URL
                body = json.loads(response.read().decode("utf-8"))
        except (OSError, TimeoutError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ProviderError("external provider request failed") from error
        if not isinstance(body, dict):
            raise ProviderError("external provider returned a non-object response")
        return body


class OpenAICompatibleResponseProvider:
    """One optional adapter that can improve wording but owns no application decisions."""

    def __init__(
        self,
        *,
        api_key: SecretStr,
        base_url: str,
        model: str,
        timeout_seconds: float,
        transport: ExternalProviderTransport | None = None,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url
        self._model = model
        self._timeout_seconds = timeout_seconds
        self._transport = transport or UrllibExternalProviderTransport()

    def generate(self, request: ProviderRequest) -> ProviderDraft:
        """Request JSON-only draft output; validation remains outside this adapter."""
        payload = self.build_payload(request)
        try:
            response = self._transport.post_json(
                url=self._base_url,
                headers={
                    "Authorization": f"Bearer {self._api_key.get_secret_value()}",
                    "Content-Type": "application/json",
                },
                payload=payload,
                timeout=self._timeout_seconds,
            )
            content = _extract_message_content(response)
            return ProviderDraft.model_validate_json(content)
        except (KeyError, TypeError, ValidationError) as error:
            raise ProviderError("external provider returned malformed draft output") from error

    def build_payload(self, request: ProviderRequest) -> dict[str, object]:
        """Expose the exact minimized remote payload for review and contract tests."""
        return {
            "model": self._model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": build_prompt_messages(request),
        }


def _extract_message_content(response: Mapping[str, object]) -> str:
    choices = response["choices"]
    if not isinstance(choices, list) or not choices:
        raise KeyError("choices")
    first = choices[0]
    if not isinstance(first, dict):
        raise TypeError("choice")
    message = first["message"]
    if not isinstance(message, dict):
        raise TypeError("message")
    content = message["content"]
    if not isinstance(content, str):
        raise TypeError("content")
    return content
