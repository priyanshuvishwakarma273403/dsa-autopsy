"""Interface definition for explanation engines."""

from abc import ABC, abstractmethod

from dsa_autopsy.models.domain import AutopsyReport


class BaseExplainer(ABC):
    """Abstract base class representing an explanation generator.

    Implementations will convert raw debugging findings and trace violations
    into natural-language descriptions explaining why code failed.
    """

    @abstractmethod
    def explain(self, report: AutopsyReport) -> str:
        """Generate a human-readable explanation of why the solution failed.

        Args:
            report: The autopsy report compiled so far.

        Returns:
            A string containing the explanation (typically formatted in Markdown).

        Raises:
            ExplainerError: If interaction with the AI or rule engine fails.
        """
        pass
