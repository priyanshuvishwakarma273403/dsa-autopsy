"""Unit tests verifying logger configurations and structured JSON formatting."""

import io
import json
import logging

import pytest

from dsa_autopsy.telemetry.logging import JSONFormatter, get_logger, setup_logging


@pytest.mark.unit
def test_setup_logging_runs_idempotently() -> None:
    """Ensure that setup_logging runs without exception and is idempotent."""
    # Run once
    setup_logging()

    # Run again to ensure no crashes or duplicate handler issues occur
    setup_logging()


@pytest.mark.unit
def test_json_formatter_serializes_fields() -> None:
    """Validate that JSONFormatter converts a LogRecord to a valid JSON string."""
    formatter = JSONFormatter()

    # Create a dummy LogRecord
    record = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname="test_file.py",
        lineno=42,
        msg="A structured log message: %s",
        args=("hello",),
        exc_info=None,
        func="test_function",
    )

    formatted_str = formatter.format(record)
    data = json.loads(formatted_str)

    assert data["level"] == "INFO"
    assert data["message"] == "A structured log message: hello"
    assert data["logger"] == "test_logger"
    assert data["function"] == "test_function"
    assert data["line"] == 42
    assert "timestamp" in data


@pytest.mark.unit
def test_json_formatter_extra_fields() -> None:
    """Validate that extra context parameters are merged into the JSON output dictionary."""
    formatter = JSONFormatter()

    record = logging.LogRecord(
        name="test_logger",
        level=logging.WARNING,
        pathname="test_file.py",
        lineno=10,
        msg="Warning message",
        args=(),
        exc_info=None,
    )
    # Inject extra_fields
    record.extra_fields = {"user_id": 123, "session_token": "abc"}

    formatted_str = formatter.format(record)
    data = json.loads(formatted_str)

    assert data["level"] == "WARNING"
    assert data["user_id"] == 123
    assert data["session_token"] == "abc"


@pytest.mark.unit
def test_structured_logger_integration() -> None:
    """Ensure StructuredLogger wrapper forwards calls to logging handler."""
    logger = get_logger("test_structured")

    # Capture standard log stream
    log_capture = io.StringIO()
    handler = logging.StreamHandler(log_capture)
    handler.setFormatter(JSONFormatter())

    # Register handler
    logger._logger.addHandler(handler)
    logger._logger.setLevel(logging.DEBUG)

    try:
        logger.info("Message check", extra={"task": "bootstrap"})
        handler.flush()

        output = log_capture.getvalue().strip()
        data = json.loads(output)

        assert data["message"] == "Message check"
        assert data["task"] == "bootstrap"
    finally:
        logger._logger.removeHandler(handler)
