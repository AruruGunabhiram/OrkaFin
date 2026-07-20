"""Static widget regression coverage without adding a browser automation stack."""

from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from orkafin.api.app import create_app

WEB_ROOT = Path(__file__).resolve().parents[2] / "src" / "orkafin" / "web"


async def _get(application: FastAPI, path: str) -> str:
    transport = ASGITransport(app=application)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get(path)
    assert response.status_code == 200
    return response.text


def test_local_demo_and_static_widget_assets_are_served() -> None:
    application = create_app()

    demo = asyncio.run(_get(application, "/demo"))
    widget = asyncio.run(_get(application, "/_orkafin/static/widget.js"))
    renderer = asyncio.run(_get(application, "/_orkafin/static/widget-renderer.js"))

    assert "OrkaFin local test mode" in demo
    assert "mountAssistantWidget" in widget
    assert "Execution disabled" in renderer


def test_widget_static_files_do_not_contain_credentials_or_permission_claims() -> None:
    contents = "\n".join(
        path.read_text()
        for suffix in ("*.html", "*.js", "*.css")
        for path in WEB_ROOT.rglob(suffix)
    )
    lowered = contents.lower()

    assert "api_key" not in lowered
    assert "authorization:" not in lowered
    assert "permissions:" not in lowered
    assert "sk-" not in lowered
