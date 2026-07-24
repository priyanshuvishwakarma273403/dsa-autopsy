"""E2E test placeholder verifying full system flow and report generation."""

import pytest

from dsa_autopsy.models.domain import SolutionTestCase, SourceCode
from dsa_autopsy.services.orchestrator import AutopsyOrchestrator


@pytest.mark.e2e
def test_full_flow_report_generation(orchestrator: AutopsyOrchestrator) -> None:
    """Validate the end-to-end flow from source code input to report creation."""
    code = SourceCode(
        content="def search(arr, target):\n    return -1\n",
        language="python",
    )
    test_cases = [
        SolutionTestCase(id="TC-01", inputs={"x": -5}, expected_output=25),
    ]

    report = orchestrator.run_autopsy(code, test_cases)

    # Validate that we got a structured report with trace info
    assert report.id is not None
    assert len(report.failed_test_cases) == 1
    assert report.root_cause_explanation is not None
    assert "invariant" in report.root_cause_explanation.lower()
