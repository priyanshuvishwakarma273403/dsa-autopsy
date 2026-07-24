"""DSA Autopsy package.

An AI-powered algorithm debugging engine designed to analyze solution failures,
invariant violations, and edge cases.
"""

from dsa_autopsy.models.domain import (
    AutopsyReport,
    ExecutionResult,
    Invariant,
    SolutionTestCase,
    SourceCode,
    TraceFrame,
    Violation,
)
from dsa_autopsy.services.orchestrator import AutopsyOrchestrator

__version__ = "0.1.0"
__author__ = "DSA Collective"

__all__ = [
    "AutopsyOrchestrator",
    "AutopsyReport",
    "ExecutionResult",
    "Invariant",
    "SolutionTestCase",
    "SourceCode",
    "TraceFrame",
    "Violation",
]
