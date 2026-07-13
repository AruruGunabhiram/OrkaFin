import asyncio

from httpx import ASGITransport, AsyncClient

from orkafin.api.app import create_app


async def request_health() -> tuple[int, dict[str, str]]:
    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/health")

    return response.status_code, response.json()


def test_health_returns_the_versioned_service_payload() -> None:
    status_code, payload = asyncio.run(request_health())

    assert status_code == 200
    assert payload == {"status": "ok", "service": "orkafin", "version": "v1"}
