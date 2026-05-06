import json

import structlog
from app.core.logging import configure_logging
from pytest import CaptureFixture


def test_configure_logging_supports_logger_name_processor(capsys: CaptureFixture[str]) -> None:
    configure_logging(log_level="INFO", log_format="json")

    logger = structlog.get_logger("test.logging")
    logger.info("logging_smoke", request_id="req_123")

    output = capsys.readouterr().out.strip()
    payload = json.loads(output)

    assert payload["event"] == "logging_smoke"
    assert payload["logger"] == "test.logging"
    assert payload["request_id"] == "req_123"


def test_configure_logging_redacts_sensitive_fields(capsys: CaptureFixture[str]) -> None:
    configure_logging(log_level="INFO", log_format="json")

    logger = structlog.get_logger("test.redaction")
    sensitive_payload = {
        "access_token": "access-token-value",
        "stripe_secret_key": "sk_test_value",
        "openai_api_key": "openai-key-value",
        "authorization": "Bearer auth-value",
    }
    logger.info(
        "redaction_smoke",
        **sensitive_payload,
    )

    output = capsys.readouterr().out.strip()
    payload = json.loads(output)

    assert payload["access_token"] == "[REDACTED]"
    assert payload["stripe_secret_key"] == "[REDACTED]"
    assert payload["openai_api_key"] == "[REDACTED]"
    assert payload["authorization"] == "[REDACTED]"
    assert "access-token-value" not in output
    assert "sk_test_value" not in output
    assert "openai-key-value" not in output
