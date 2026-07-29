"""Custom exception hierarchy for the DSA Autopsy project."""


class DSAAutopsyError(Exception):
    """Base exception for all errors in the dsa-autopsy package."""


class ParsingError(DSAAutopsyError):
    """Raised when parsing source code fails due to syntax or structural errors."""
