"""Adversarial CORS configuration and middleware behavior."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient, Response
from pydantic import ValidationError

from orkafin.api.app import create_app
from orkafin.core.settings import Settings

ALLOWED_ORIGIN = "http://localhost:8000"


async def _request(
    application: FastAPI,
    method: str,
    *,
    origin: str,
    request_method: str | None = None,
    request_headers: str | None = None,
) -> Response:
    headers = {"Origin": origin}
    if request_method is not None:
        headers["Access-Control-Request-Method"] = request_method
    if request_headers is not None:
        headers["Access-Control-Request-Headers"] = request_headers
    async with AsyncClient(
        transport=ASGITransport(app=application, raise_app_exceptions=False),
        base_url="http://testserver",
    ) as client:
        return await client.request(method, "/health", headers=headers)


def _application(database_path: Path) -> FastAPI:
    return create_app(
        settings=Settings(
            environment="test",
            database_url=f"sqlite:///{database_path}",
            allowed_origins=(ALLOWED_ORIGIN,),
        )
    )


def test_exact_allowed_origin_receives_only_the_configured_cors_grant(tmp_path: Path) -> None:
    application = _application(tmp_path / "cors-allowed.db")

    response = asyncio.run(_request(application, "GET", origin=ALLOWED_ORIGIN))

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == ALLOWED_ORIGIN
    assert "access-control-allow-credentials" not in response.headers


@pytest.mark.parametrize(
    "origin",
    (
        "null",
        "https://attacker.invalid",
        "http://localhost.attacker.invalid:8000",
        "http://127.0.0.1.attacker.invalid:8000",
        "http://localhost:8000.attacker.invalid",
    ),
)
def test_arbitrary_null_and_loopback_lookalike_origins_receive_no_grant(
    tmp_path: Path, origin: str
) -> None:
    application = _application(tmp_path / "cors-denied.db")

    response = asyncio.run(_request(application, "GET", origin=origin))

    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers


@pytest.mark.parametrize(
    ("origin", "method", "headers"),
    (
        ("https://attacker.invalid", "POST", "content-type"),
        (ALLOWED_ORIGIN, "DELETE", "content-type"),
        (ALLOWED_ORIGIN, "POST", "authorization"),
    ),
)
def test_preflight_rejects_unapproved_origin_method_or_header(
    tmp_path: Path, origin: str, method: str, headers: str
) -> None:
    application = _application(tmp_path / "cors-preflight-denied.db")

    response = asyncio.run(
        _request(
            application,
            "OPTIONS",
            origin=origin,
            request_method=method,
            request_headers=headers,
        )
    )

    assert response.status_code == 400
    if origin != ALLOWED_ORIGIN:
        assert "access-control-allow-origin" not in response.headers


def test_preflight_allows_only_required_post_headers(tmp_path: Path) -> None:
    application = _application(tmp_path / "cors-preflight-allowed.db")

    response = asyncio.run(
        _request(
            application,
            "OPTIONS",
            origin=ALLOWED_ORIGIN,
            request_method="POST",
            request_headers="content-type,x-request-id",
        )
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == ALLOWED_ORIGIN
    assert set(response.headers["access-control-allow-methods"].replace(" ", "").split(",")) == {
        "GET",
        "POST",
    }
    allowed_headers = response.headers["access-control-allow-headers"].lower()
    assert "content-type" in allowed_headers
    assert "x-request-id" in allowed_headers
    assert "authorization" not in allowed_headers


@pytest.mark.parametrize(
    "origin",
    (
        "http://user@localhost:8000",
        "http://user:password@localhost:8000",
        "http://localhost:not-a-port",
    ),
)
def test_cors_configuration_rejects_userinfo_and_invalid_ports(origin: str) -> None:
    with pytest.raises(ValidationError, match="allowed_origins"):
        Settings(allowed_origins=(origin,))
