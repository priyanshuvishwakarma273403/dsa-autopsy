"""Interface definition for execution engines."""

from abc import ABC, abstractmethod

from dsa_autopsy.models.domain import ExecutionResult, SolutionTestCase, SourceCode


class BaseExecutor(ABC):
    """Abstract base class representing an execution engine.

    Implementations will run solutions inside sandboxes and collect traces.
    """

    @abstractmethod
    def execute(self, code: SourceCode, test_case: SolutionTestCase) -> ExecutionResult:
        """Execute source code with a specific test case inside a sandbox.

        Args:
            code: The source code to run.
            test_case: Input parameters and expected outcomes.

        Returns:
            ExecutionResult containing exit code, stdout, stderr, and trace frames.

        Raises:
            ExecutionError: If execution setup or sandbox fails.
        """
        pass
