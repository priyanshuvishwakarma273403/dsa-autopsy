"""Interface definition for code parsers."""

from abc import ABC, abstractmethod
from typing import Any

from dsa_autopsy.models.domain import SourceCode


class BaseParser(ABC):
    """Abstract base class representing a code parser."""

    @abstractmethod
    def parse(self, code: SourceCode) -> dict[str, Any]:
        """Parse source code into a structured representation."""
        pass
