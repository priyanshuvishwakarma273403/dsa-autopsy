"""Concrete implementation of the AST-based code parser."""

import ast
from typing import Any

from dsa_autopsy.exceptions import ParsingError
from dsa_autopsy.interfaces.parser import BaseParser
from dsa_autopsy.models.domain import SourceCode


class ASTParser(BaseParser):
    """Parses Python source code into structural AST metadata."""

    def parse(self, code: SourceCode) -> dict[str, Any]:
        """Parse source code into a structured representation of functions and loops.

        Args:
            code: SourceCode model containing code content and language.

        Returns:
            A dictionary of function metadata keyed by function name.

        Raises:
            ParsingError: If the source code language is not Python or contains syntax errors.
        """
        if code.language.lower() not in ["python", "py"]:
            raise ParsingError(f"Unsupported language: '{code.language}'")

        try:
            tree = ast.parse(code.content, filename=str(code.file_path or "<string>"))
        except SyntaxError as e:
            raise ParsingError(f"Syntax error in source code: {e.msg} at line {e.lineno}") from e
        except Exception as e:
            raise ParsingError(f"Failed to parse source code: {e}") from e

        metadata: dict[str, Any] = {}

        class FunctionVisitor(ast.NodeVisitor):
            def __init__(self) -> None:
                self.current_function: dict[str, Any] | None = None
                self.loop_stack: list[dict[str, Any]] = []

            def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
                outer_function = self.current_function
                outer_loops = self.loop_stack

                func_meta: dict[str, Any] = {
                    "name": node.name,
                    "start_line": node.lineno,
                    "end_line": getattr(node, "end_lineno", node.lineno),
                    "arguments": [arg.arg for arg in node.args.args],
                    "loops": [],
                    "returns": [],
                }

                self.current_function = func_meta
                self.loop_stack = []

                self.generic_visit(node)

                metadata[node.name] = func_meta

                self.current_function = outer_function
                self.loop_stack = outer_loops

            def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
                outer_function = self.current_function
                outer_loops = self.loop_stack

                func_meta: dict[str, Any] = {
                    "name": node.name,
                    "start_line": node.lineno,
                    "end_line": getattr(node, "end_lineno", node.lineno),
                    "arguments": [arg.arg for arg in node.args.args],
                    "loops": [],
                    "returns": [],
                }

                self.current_function = func_meta
                self.loop_stack = []

                self.generic_visit(node)

                metadata[node.name] = func_meta

                self.current_function = outer_function
                self.loop_stack = outer_loops

            def _visit_loop(self, node: ast.For | ast.While, loop_type: str) -> None:
                if self.current_function is not None:
                    loop_meta: dict[str, Any] = {
                        "type": loop_type,
                        "start_line": node.lineno,
                        "end_line": getattr(node, "end_lineno", node.lineno),
                        "nesting_level": len(self.loop_stack),
                    }
                    self.current_function["loops"].append(loop_meta)
                    self.loop_stack.append(loop_meta)

                    self.generic_visit(node)

                    self.loop_stack.pop()
                else:
                    self.generic_visit(node)

            def visit_For(self, node: ast.For) -> None:
                self._visit_loop(node, "For")

            def visit_While(self, node: ast.While) -> None:
                self._visit_loop(node, "While")

            def visit_Return(self, node: ast.Return) -> None:
                if self.current_function is not None:
                    val_str = None
                    if node.value is not None:
                        try:
                            val_str = ast.unparse(node.value)
                        except Exception:
                            val_str = repr(node.value)

                    self.current_function["returns"].append(
                        {
                            "line_number": node.lineno,
                            "value": val_str,
                        }
                    )
                self.generic_visit(node)

        FunctionVisitor().visit(tree)
        return metadata
