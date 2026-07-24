"""Custom exception hierarchy for the DSA Autopsy project."""

from typing import Any


class DSAAutopsyError(Exception):
    """Base exception for all errors in the dsa-autopsy package."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        """Initialize the base exception with a message and optional structured details.

        Args:
            message: A human-readable description of the error.
            details: Optional dictionary containing error context (e.g. line numbers, variables).
        """
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def __str__(self) -> str:
        """Return the string representation of the exception."""
        if self.details:
            return f"{self.message} (Details: {self.details})"
        return self.message


class ConfigurationError(DSAAutopsyError):
    """Raised when there is an issue loading or parsing configuration settings."""


class ParserError(DSAAutopsyError):
    """Raised when parsing source code or AST structure fails."""


class ExecutionError(DSAAutopsyError):
    """Raised when executing solution code in the execution engine fails."""


class AnalysisError(DSAAutopsyError):
    """Raised when analysis, invariant detection, or debugging logic fails."""


class InvariantViolationError(AnalysisError):
    """Raised when a specific invariant assertion or property is violated during analysis."""


class ExplainerError(DSAAutopsyError):
    """Raised when generating natural language explanations or summaries fails."""
