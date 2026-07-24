"""Pytest configuration and shared fixtures for the test suite."""

from typing import Any

import pytest

from dsa_autopsy.interfaces.analyzer import BaseAnalyzer
from dsa_autopsy.interfaces.executor import BaseExecutor
from dsa_autopsy.interfaces.explainer import BaseExplainer
from dsa_autopsy.interfaces.parser import BaseParser
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


class DummyParser(BaseParser):
    """A dummy parser implementation for testing orchestration."""

    def parse(self, code: SourceCode) -> dict[str, Any]:
        return {"solution": {"type": "function", "start_line": 1}}

    def extract_functions(self, code: SourceCode) -> list[str]:
        return ["solution"]


class DummyExecutor(BaseExecutor):
    """A dummy executor implementation for testing orchestration."""

    def execute(self, code: SourceCode, test_case: SolutionTestCase) -> ExecutionResult:
        # Simulate execution failure for negative inputs
        has_failed = test_case.inputs.get("x", 0) < 0
        exit_code = 1 if has_failed else 0

        frames = [
            TraceFrame(line_number=1, local_variables={"x": test_case.inputs.get("x")}),
            TraceFrame(
                line_number=2,
                local_variables={
                    "return_value": test_case.expected_output if not has_failed else -999
                },
            ),
        ]

        return ExecutionResult(
            test_case_id=test_case.id,
            stdout="Running test...\n",
            stderr="Traceback...\n" if has_failed else "",
            exit_code=exit_code,
            execution_time_seconds=0.01,
            trace_frames=frames,
            error_message="Simulation failure" if has_failed else None,
        )


class DummyAnalyzer(BaseAnalyzer):
    """A dummy analyzer implementation for testing orchestration."""

    def analyze(
        self, code: SourceCode, execution_results: list[ExecutionResult]
    ) -> list[Violation]:
        violations = []
        for res in execution_results:
            if not res.is_success:
                inv = Invariant(
                    id="INV-001",
                    expression="x >= 0",
                    location="line:1",
                    description="Input value must be non-negative",
                )
                violations.append(
                    Violation(
                        invariant=inv,
                        test_case_id=res.test_case_id,
                        trace_frame_index=0,
                        context_variables=res.trace_frames[0].local_variables,
                        explanation="Input x violated x >= 0",
                    )
                )
        return violations


class DummyExplainer(BaseExplainer):
    """A dummy explainer implementation for testing orchestration."""

    def explain(self, report: AutopsyReport) -> str:
        return "Root Cause Analysis: The solution failed because invariant 'x >= 0' was violated."


@pytest.fixture
def dummy_parser() -> BaseParser:
    """Fixture providing a mock/dummy code parser."""
    return DummyParser()


@pytest.fixture
def dummy_executor() -> BaseExecutor:
    """Fixture providing a mock/dummy execution engine."""
    return DummyExecutor()


@pytest.fixture
def dummy_analyzer() -> BaseAnalyzer:
    """Fixture providing a mock/dummy trace analyzer."""
    return DummyAnalyzer()


@pytest.fixture
def dummy_explainer() -> BaseExplainer:
    """Fixture providing a mock/dummy explanation engine."""
    return DummyExplainer()


@pytest.fixture
def orchestrator(
    dummy_parser: BaseParser,
    dummy_executor: BaseExecutor,
    dummy_analyzer: BaseAnalyzer,
    dummy_explainer: BaseExplainer,
) -> AutopsyOrchestrator:
    """Fixture providing a fully-wired AutopsyOrchestrator."""
    return AutopsyOrchestrator(
        parser=dummy_parser,
        executor=dummy_executor,
        analyzer=dummy_analyzer,
        explainer=dummy_explainer,
    )
