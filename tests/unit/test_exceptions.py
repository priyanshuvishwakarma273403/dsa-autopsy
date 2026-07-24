"""Unit tests validating custom exception behaviors."""

import pytest

from dsa_autopsy.exceptions import (
    AnalysisError,
    ConfigurationError,
    DSAAutopsyError,
    InvariantViolationError,
    ParserError,
)


@pytest.mark.unit
def test_base_exception_str_representation() -> None:
    """Validate string conversion of the base exception without details."""
    err = DSAAutopsyError("System failure")
    assert str(err) == "System failure"


@pytest.mark.unit
def test_base_exception_with_details() -> None:
    """Validate string conversion and property extraction when error details are supplied."""
    details = {"line": 12, "expr": "x > 0"}
    err = DSAAutopsyError("Invariant violation", details=details)

    assert err.message == "Invariant violation"
    assert err.details == details
    assert "Details:" in str(err)
    assert "x > 0" in str(err)


@pytest.mark.unit
def test_derived_exceptions_inheritance() -> None:
    """Verify that all derived exception types inherit from DSAAutopsyError."""
    assert issubclass(ConfigurationError, DSAAutopsyError)
    assert issubclass(ParserError, DSAAutopsyError)
    assert issubclass(AnalysisError, DSAAutopsyError)
    assert issubclass(InvariantViolationError, AnalysisError)
