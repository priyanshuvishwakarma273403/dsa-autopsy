"""Interface definition for algorithm debugging analyzers."""

from abc import ABC, abstractmethod

from dsa_autopsy.models.domain import ExecutionResult, SourceCode, Violation


class BaseAnalyzer(ABC):
    """Abstract base class representing a debug analyzer.

    Implementations will inspect traces, detect broken assertions, loop
    invariants, or bad states.
    """

    @abstractmethod
    def analyze(
        self, code: SourceCode, execution_results: list[ExecutionResult]
    ) -> list[Violation]:
        """Analyze execution traces to locate broken invariants or logic bugs.

        Args:
            code: The original source code.
            execution_results: Traces and execution results of running test cases.

        Returns:
            A list of detected violations and invariant breaks.

        Raises:
            AnalysisError: If the analysis process runs into logic or configuration issues.
        """
        pass
