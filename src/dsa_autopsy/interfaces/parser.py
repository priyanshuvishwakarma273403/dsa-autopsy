"""Interface definition for code parsers."""

from abc import ABC, abstractmethod
from typing import Any

from dsa_autopsy.models.domain import SourceCode


class BaseParser(ABC):
    """Abstract base class representing an AST parser or source analyzer.

    Implementations can wrap native Python AST or Tree-sitter libraries.
    """

    @abstractmethod
    def parse(self, code: SourceCode) -> dict[str, Any]:
        """Parse source code into a structured dictionary/AST representation.

        Args:
            code: The source code object to parse.

        Returns:
            A structured dict representation of the AST.

        Raises:
            ParserError: If parsing fails.
        """
        pass

    @abstractmethod
    def extract_functions(self, code: SourceCode) -> list[str]:
        """Extract defined function names or signatures from source code.

        Args:
            code: The source code object.

        Returns:
            A list of function names or structural metadata.
        """
        pass
