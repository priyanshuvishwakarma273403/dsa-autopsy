"""Example demonstrating how to bootstrap and run a mock autopsy debugging session."""

from dsa_autopsy.models.domain import SolutionTestCase, SourceCode
from dsa_autopsy.services.orchestrator import AutopsyOrchestrator
from dsa_autopsy.telemetry.logging import get_logger, setup_logging
from tests.conftest import DummyAnalyzer, DummyExecutor, DummyExplainer, DummyParser

logger = get_logger(__name__)


def main() -> None:
    """Bootstrap components and execute an autopsy session."""
    # 1. Initialize logging system
    setup_logging()
    
    logger.info("Initializing DSA Autopsy bootstrap components...")

    # 2. Wire up interface implementations (using dummy/mock wrappers for demo)
    parser = DummyParser()
    executor = DummyExecutor()
    analyzer = DummyAnalyzer()
    explainer = DummyExplainer()

    orchestrator = AutopsyOrchestrator(
        parser=parser,
        executor=executor,
        analyzer=analyzer,
        explainer=explainer,
    )

    # 3. Define target source code and test cases
    # We pass target inputs, including a failing input (x = -5)
    source_code = SourceCode(
        content=(
            "def square_root(x):\n"
            "    # This is a buggy implementation for demonstrating debugging flow\n"
            "    return x ** 0.5\n"
        ),
        language="python",
    )

    test_cases = [
        SolutionTestCase(id="test-positive-value", inputs={"x": 9}, expected_output=3.0),
        SolutionTestCase(id="test-negative-value-buggy", inputs={"x": -9}, expected_output=-1.0),
    ]

    # 4. Execute orchestrator run
    logger.info("Starting debugging autopsy session...")
    report = orchestrator.run_autopsy(source_code, test_cases)

    # 5. Output results
    print("\n" + "=" * 50)
    print("               AUTOPSY SESSION REPORT")
    print("=" * 50)
    print(f"Report ID:             {report.id}")
    print(f"Timestamp:             {report.created_at.isoformat()}")
    print(f"Failed Test Cases:     {len(report.failed_test_cases)}")
    print(f"Detected Violations:   {len(report.violations)}")
    print("\n--- Root Cause Analysis ---")
    print(report.root_cause_explanation)
    print("=" * 50)


if __name__ == "__main__":
    main()
