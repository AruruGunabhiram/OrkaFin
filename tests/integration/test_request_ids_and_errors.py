import asyncio
from uuid import UUID, uuid4

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from orkafin.api.app import create_app
from orkafin.core.settings import Settings


async def get_response(
    application: FastAPI,
    path: str,
    *,
    headers: dict[str, str] | None = None,
) -> tuple[int, dict[str, object], str | None]:
    transport = ASGITransport(app=application, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get(path, headers=headers)
    return response.status_code, response.json(), response.headers.get("X-Request-ID")


def test_request_id_is_generated_and_returned() -> None:
    status_code, body, header_request_id = asyncio.run(get_response(create_app(), "/health"))

    assert status_code == 200
    assert body["status"] == "ok"
    assert header_request_id is not None
    assert str(UUID(header_request_id)) == header_request_id


def test_malformed_request_id_is_replaced() -> None:
    _, _, header_request_id = asyncio.run(
        get_response(create_app(), "/health", headers={"X-Request-ID": "not-a-request-id"})
    )

    assert header_request_id is not None
    assert header_request_id != "not-a-request-id"
    assert str(UUID(header_request_id)) == header_request_id


def test_valid_request_id_is_accepted_only_when_policy_allows() -> None:
    supplied_request_id = str(uuid4())
    _, _, accepted_request_id = asyncio.run(
        get_response(create_app(), "/health", headers={"X-Request-ID": supplied_request_id})
    )
    _, _, replaced_request_id = asyncio.run(
        get_response(
            create_app(settings=Settings(accept_incoming_request_ids=False)),
            "/health",
            headers={"X-Request-ID": supplied_request_id},
        )
    )

    assert accepted_request_id == supplied_request_id
    assert replaced_request_id is not None
    assert replaced_request_id != supplied_request_id


def test_validation_errors_use_the_safe_versioned_envelope() -> None:
    application = create_app()

    @application.get("/test/validation")
    def validation_probe(required_number: int) -> dict[str, int]:
        return {"required_number": required_number}

    status_code, body, header_request_id = asyncio.run(
        get_response(application, "/test/validation")
    )

    assert status_code == 422
    assert body == {
        "schema_version": "v1",
        "code": "validation_error",
        "message": "Request validation failed.",
        "request_id": header_request_id,
        "details": {"fields": ["query.required_number"]},
    }


def test_unexpected_errors_return_a_safe_envelope_without_exception_content() -> None:
    application = create_app()

    @application.get("/test/failure")
    def failure_probe() -> None:
        raise RuntimeError("password=do-not-return-this")

    status_code, body, header_request_id = asyncio.run(get_response(application, "/test/failure"))

    assert status_code == 500
    assert body == {
        "schema_version": "v1",
        "code": "internal_error",
        "message": "An unexpected error occurred.",
        "request_id": header_request_id,
    }
    assert "do-not-return-this" not in str(body)


def test_development_debug_details_remain_safe() -> None:
    application = create_app(settings=Settings(debug=True))

    @application.get("/test/debug-failure")
    def debug_failure_probe() -> None:
        raise RuntimeError("token=do-not-return-this")

    _, body, _ = asyncio.run(get_response(application, "/test/debug-failure"))

    assert body["details"] == {"error_type": "RuntimeError"}
    assert "do-not-return-this" not in str(body)
