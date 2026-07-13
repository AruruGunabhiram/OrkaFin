import io
import json
import logging

from orkafin.core.logging import JsonFormatter, RedactingFilter


def test_structured_log_filter_redacts_sensitive_values() -> None:
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.addFilter(RedactingFilter())
    handler.setFormatter(JsonFormatter())
    logger = logging.getLogger("test.redaction")
    logger.handlers = [handler]
    logger.propagate = False
    logger.setLevel(logging.INFO)

    logger.info(
        "safe_event",
        extra={
            "authorization": "Bearer top-secret-token",
            "payload": {"notes": "private candidate note", "safe_count": 1},
        },
    )

    output = stream.getvalue()
    event = json.loads(output)
    assert "top-secret-token" not in output
    assert "private candidate note" not in output
    assert event["authorization"] == "[REDACTED]"
    assert event["payload"]["notes"] == "[REDACTED]"
    assert event["payload"]["safe_count"] == 1
