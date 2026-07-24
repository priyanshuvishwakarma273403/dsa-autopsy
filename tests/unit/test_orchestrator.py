"""Unit tests verifying the AutopsyOrchestrator coordination logic."""

import pytest

from dsa_autopsy.models.domain import SolutionTestCase, SourceCode
from dsa_autopsy.services.orchestrator import AutopsyOrchestrator


@pytest.mark.unit
def test_orchestrator_all_pass_workflow(orchestrator: AutopsyOrchestrator) -> None:
    """Validate orchestrator flow when all test cases compile and run successfully."""
    code = SourceCode(content="def solution(x): return x * 2", language="python")
    test_cases = [
        SolutionTestCase(id="TC-01", inputs={"x": 5}, expected_output=10),
        SolutionTestCase(id="TC-02", inputs={"x": 10}, expected_output=20),
    ]

    report = orchestrator.run_autopsy(code, test_cases)

    assert report.id is not None
    assert len(report.failed_test_cases) == 0
    assert len(report.violations) == 0
    assert report.root_cause_explanation is not None
    assert "All test cases passed" in report.root_cause_explanation


@pytest.mark.unit
def test_orchestrator_failure_workflow(orchestrator: AutopsyOrchestrator) -> None:
    """Validate orchestrator workflow when one of the test cases triggers a failure."""
    code = SourceCode(content="def solution(x): return x * 2", language="python")
    test_cases = [
        SolutionTestCase(id="TC-01", inputs={"x": 5}, expected_output=10),
        # Triggers dummy failure
        SolutionTestCase(id="TC-02", inputs={"x": -5}, expected_output=-10),
    ]

    report = orchestrator.run_autopsy(code, test_cases)

    # TC-02 should be captured as failed
    assert len(report.failed_test_cases) == 1
    assert report.failed_test_cases[0].id == "TC-02"
    assert report.failed_test_cases[0].is_failed is True

    # Analyzer should have flagged a violation
    assert len(report.violations) == 1
    assert report.violations[0].test_case_id == "TC-02"
    assert report.violations[0].invariant.expression == "x >= 0"

    # Explainer should have run
    assert report.root_cause_explanation is not None
    assert "violated" in report.root_cause_explanation.lower()
