"""Domain models (entities) for the DSA Autopsy engine.

These are pure dataclasses representing code, test cases, execution traces,
invariants, violations, and debugging reports. They contain no external
framework dependencies or infrastructure logic.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class SourceCode:
    """Represents the user's algorithm source code under test."""

    content: str
    language: str
    file_path: Path | None = None

    @property
    def lines(self) -> list[str]:
        """Split the source code content into individual lines."""
        return self.content.splitlines()


@dataclass(frozen=True)
class SolutionTestCase:
    """Represents a test case used to validate the algorithm."""

    id: str
    inputs: dict[str, Any]
    expected_output: Any
    actual_output: Any | None = None
    is_failed: bool = False


@dataclass(frozen=True)
class TraceFrame:
    """Represents state of variables and execution pointer at a specific step in time."""

    line_number: int
    local_variables: dict[str, Any] = field(default_factory=dict)
    global_variables: dict[str, Any] = field(default_factory=dict)
    instruction: str | None = None


@dataclass(frozen=True)
class ExecutionResult:
    """Represents the result of running a test case through the execution engine."""

    test_case_id: str
    stdout: str
    stderr: str
    exit_code: int
    execution_time_seconds: float
    matches_expected: bool
    trace_frames: list[TraceFrame] = field(default_factory=list)
    error_message: str | None = None

    @property
    def is_success(self) -> bool:
        """Check if execution completed without errors (exit code 0)."""
        return self.exit_code == 0 and self.error_message is None


@dataclass(frozen=True)
class Invariant:
    """Represents a loop or function invariant that must hold during execution."""

    id: str
    expression: str
    location: str  # e.g., "loop_head", "function_exit", "line:12"
    description: str | None = None


@dataclass(frozen=True)
class Violation:
    """Represents a specific instance where an invariant was broken during execution."""

    invariant: Invariant
    test_case_id: str
    trace_frame_index: int
    context_variables: dict[str, Any] = field(default_factory=dict)
    explanation: str | None = None


@dataclass(frozen=True)
class AutopsyReport:
    """The final structured debugging report returned by the engine."""

    id: str
    source_code: SourceCode
    failed_test_cases: list[SolutionTestCase] = field(default_factory=list)
    execution_results: list[ExecutionResult] = field(default_factory=list)
    identified_invariants: list[Invariant] = field(default_factory=list)
    violations: list[Violation] = field(default_factory=list)
    root_cause_explanation: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
