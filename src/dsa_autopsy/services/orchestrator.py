"""Service layer orchestrating the algorithm debugging (autopsy) workflow."""

import dataclasses
import logging
import uuid

from dsa_autopsy.interfaces.analyzer import BaseAnalyzer
from dsa_autopsy.interfaces.executor import BaseExecutor
from dsa_autopsy.interfaces.explainer import BaseExplainer
from dsa_autopsy.interfaces.parser import BaseParser
from dsa_autopsy.models.domain import (
    AutopsyReport,
    ExecutionResult,
    SolutionTestCase,
    SourceCode,
    Violation,
)

logger = logging.getLogger(__name__)


class AutopsyOrchestrator:
    """Orchestrates the lifecycle of parsing, executing, analyzing, and explaining solution bugs."""

    def __init__(
        self,
        parser: BaseParser,
        executor: BaseExecutor,
        analyzer: BaseAnalyzer,
        explainer: BaseExplainer,
    ) -> None:
        """Initialize the orchestrator with its required engine dependencies.

        Args:
            parser: BaseParser instance to understand code structure.
            executor: BaseExecutor instance to run code inside a sandbox.
            analyzer: BaseAnalyzer instance to find invariant violations.
            explainer: BaseExplainer instance to generate root-cause reports.
        """
        self._parser = parser
        self._executor = executor
        self._analyzer = analyzer
        self._explainer = explainer

    def run_autopsy(
        self,
        code: SourceCode,
        test_cases: list[SolutionTestCase],
    ) -> AutopsyReport:
        """Run the end-to-end debugging autopsy on the provided code.

        Args:
            code: SourceCode structure holding the program under test.
            test_cases: A list of SolutionTestCase structures to run.

        Returns:
            AutopsyReport detailing execution outcomes, failures, violations,
            and the AI root-cause explanation.
        """
        report_id = str(uuid.uuid4())
        logger.info(f"Starting autopsy process (ID: {report_id}) with {len(test_cases)} test cases")

        # 1. Parse code structure
        try:
            logger.debug(f"Parsing source code structure for report {report_id}")
            ast_metadata = self._parser.parse(code)
            logger.debug(
                f"Parsed code structure successfully. Functions: {list(ast_metadata.keys())}"
            )
        except Exception:
            logger.exception(f"Failed during parse step for report {report_id}")
            raise

        # 2. Execute test cases
        execution_results: list[ExecutionResult] = []
        failed_test_cases: list[SolutionTestCase] = []

        for test_case in test_cases:
            logger.info(f"Executing test case {test_case.id} for report {report_id}")
            try:
                result = self._executor.execute(code, test_case)

                # Determine failure: either execution engine returned an exit code/error
                # or output does not match expected output.
                actual_output = (
                    result.trace_frames[-1].local_variables.get("return_value")
                    if result.trace_frames
                    else None
                )

                is_failed = not result.is_success or actual_output != test_case.expected_output
                result = dataclasses.replace(result, matches_expected=not is_failed)
                execution_results.append(result)

                if is_failed:
                    logger.warning(
                        f"Test case {test_case.id} failed. Expected: "
                        f"{test_case.expected_output}, Got: {actual_output}"
                    )
                    # Create an updated SolutionTestCase marking failure
                    updated_case = SolutionTestCase(
                        id=test_case.id,
                        inputs=test_case.inputs,
                        expected_output=test_case.expected_output,
                        actual_output=actual_output,
                        is_failed=True,
                    )
                    failed_test_cases.append(updated_case)
                else:
                    logger.debug(f"Test case {test_case.id} passed")

            except Exception:
                logger.exception(f"Error executing test case {test_case.id} for report {report_id}")
                raise

        # 3. Analyze trace violations
        violations: list[Violation] = []
        if failed_test_cases:
            logger.info(f"Running trace analysis on {len(failed_test_cases)} failed runs")
            try:
                violations = self._analyzer.analyze(code, execution_results)
                logger.info(f"Analysis completed. Violations detected: {len(violations)}")
            except Exception:
                logger.exception(f"Error during trace analysis for report {report_id}")
                raise
        else:
            logger.info("No test cases failed. Skipping trace analysis.")

        # 4. Draft report & explain failures
        initial_report = AutopsyReport(
            id=report_id,
            source_code=code,
            failed_test_cases=failed_test_cases,
            execution_results=execution_results,
            violations=violations,
            root_cause_explanation=None,
        )

        root_cause: str | None = None
        if failed_test_cases:
            try:
                logger.info(f"Generating root-cause failure explanation for report {report_id}")
                root_cause = self._explainer.explain(initial_report)
                logger.info("Explanation generated successfully")
            except Exception:
                logger.exception(f"Error generating failure explanation for report {report_id}")
                raise
        else:
            root_cause = "All test cases passed. No failures to diagnose."

        # Compile and return the complete report
        final_report = AutopsyReport(
            id=report_id,
            source_code=code,
            failed_test_cases=failed_test_cases,
            execution_results=execution_results,
            violations=violations,
            root_cause_explanation=root_cause,
        )

        logger.info(f"Autopsy process completed successfully for report {report_id}")
        return final_report
