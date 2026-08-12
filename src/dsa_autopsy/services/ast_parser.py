"""Concrete implementation of the AST-based code parser."""

import ast
import contextlib
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
        if code.language.lower() in ["cpp", "c++"]:
            import re

            metadata: dict[str, Any] = {}
            pattern = re.compile(r"(?:\w+::)?(\w+)\s+(\w+)\s*\(([^)]*)\)\s*\{")
            for match in pattern.finditer(code.content):
                _, name, args_str = match.groups()
                if name not in ("if", "for", "while", "switch", "catch"):
                    args = [
                        arg.strip().split()[-1].replace("*", "").replace("&", "")
                        for arg in args_str.split(",")
                        if arg.strip()
                    ]
                    metadata[name] = {
                        "name": name,
                        "start_line": code.content[: match.start()].count("\n") + 1,
                        "end_line": code.content[: match.end()].count("\n") + 1,
                        "arguments": args,
                        "loops": [],
                        "returns": [],
                    }
            return metadata

        if code.language.lower() == "java":
            import re

            metadata: dict[str, Any] = {}
            pattern = re.compile(
                r"(?:public|private|protected|static|\s)+\s+(\w+)\s+(\w+)\s*\(([^)]*)\)\s*(?:throws\s+[\w\s,]+)?\s*\{"
            )
            for match in pattern.finditer(code.content):
                _, name, args_str = match.groups()
                if name not in ("if", "for", "while", "switch", "catch", "Solution", "Main"):
                    args = [arg.strip().split()[-1] for arg in args_str.split(",") if arg.strip()]
                    metadata[name] = {
                        "name": name,
                        "start_line": code.content[: match.start()].count("\n") + 1,
                        "end_line": code.content[: match.end()].count("\n") + 1,
                        "arguments": args,
                        "loops": [],
                        "returns": [],
                    }
            return metadata

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


class ASTBoundExtractor(ast.NodeVisitor):
    """Extracts static boundaries and limits from AST to serve as seed invariants."""

    def __init__(self) -> None:
        """Initialize the ASTBoundExtractor."""
        self.bounds: dict[int, list[tuple[Any, ...]]] = {}
        self.current_function_lines: tuple[int, int] | None = None
        self.lower_vars: list[str] = []
        self.upper_vars: list[str] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Extract bounds from function definitions."""
        old_func_lines = self.current_function_lines
        old_lowers = self.lower_vars
        old_uppers = self.upper_vars

        self.current_function_lines = (node.lineno, getattr(node, "end_lineno", node.lineno))
        self.lower_vars = []
        self.upper_vars = []

        self.generic_visit(node)

        if self.current_function_lines:
            start_line, end_line = self.current_function_lines
            for low in self.lower_vars:
                for high in self.upper_vars:
                    if low != high:
                        for line in range(start_line, end_line + 1):
                            self.bounds.setdefault(line, []).append((low, "<=", high))

        self.current_function_lines = old_func_lines
        self.lower_vars = old_lowers
        self.upper_vars = old_uppers

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """Extract bounds from async function definitions."""
        old_func_lines = self.current_function_lines
        old_lowers = self.lower_vars
        old_uppers = self.upper_vars

        self.current_function_lines = (node.lineno, getattr(node, "end_lineno", node.lineno))
        self.lower_vars = []
        self.upper_vars = []

        self.generic_visit(node)

        if self.current_function_lines:
            start_line, end_line = self.current_function_lines
            for low in self.lower_vars:
                for high in self.upper_vars:
                    if low != high:
                        for line in range(start_line, end_line + 1):
                            self.bounds.setdefault(line, []).append((low, "<=", high))

        self.current_function_lines = old_func_lines
        self.lower_vars = old_lowers
        self.upper_vars = old_uppers

    def visit_For(self, node: ast.For) -> None:
        """Extract bounds from for loop iterators."""
        if isinstance(node.target, ast.Name):
            i_name = node.target.id
            if (
                isinstance(node.iter, ast.Call)
                and isinstance(node.iter.func, ast.Name)
                and node.iter.func.id == "range"
            ):
                args = node.iter.args
                start_val: Any = 0
                end_val: Any = None

                if len(args) == 1:
                    with contextlib.suppress(Exception):
                        end_val = ast.unparse(args[0])
                elif len(args) >= 2:
                    with contextlib.suppress(Exception):
                        start_val = ast.unparse(args[0])
                        if isinstance(args[0], ast.Constant) and isinstance(args[0].value, int):
                            start_val = args[0].value
                    with contextlib.suppress(Exception):
                        end_val = ast.unparse(args[1])
                        if isinstance(args[1], ast.Constant) and isinstance(args[1].value, int):
                            end_val = args[1].value

                with contextlib.suppress(Exception):
                    if isinstance(start_val, str) and start_val.isdigit():
                        start_val = int(start_val)

                with contextlib.suppress(Exception):
                    if isinstance(end_val, str) and end_val.isdigit():
                        end_val = int(end_val)

                if end_val is not None:
                    start_line = node.lineno
                    end_line = getattr(node, "end_lineno", node.lineno)
                    for line in range(start_line, end_line + 1):
                        self.bounds.setdefault(line, []).append((i_name, ">=", start_val))
                        self.bounds.setdefault(line, []).append((i_name, "<", end_val))

        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        """Scan assignments to track limits/boundaries."""
        for target in node.targets:
            if isinstance(target, ast.Name):
                var_name = target.id
                val_expr = node.value

                is_lower = False
                name_lower = any(k in var_name.lower() for k in ["low", "left", "start", "min"])
                if name_lower:
                    is_lower = True
                else:
                    if isinstance(val_expr, ast.Constant) and val_expr.value in (0, 1):
                        is_lower = True

                is_upper = False
                name_upper = any(k in var_name.lower() for k in ["high", "right", "end", "max"])
                if name_upper:
                    is_upper = True
                else:
                    val_str = ""
                    with contextlib.suppress(Exception):
                        val_str = ast.unparse(val_expr)
                    if "len(" in val_str or any(
                        k in val_str.lower() for k in ["size", "limit", "n"]
                    ):
                        is_upper = True

                if is_lower:
                    self.lower_vars.append(var_name)
                if is_upper and var_name not in self.lower_vars:
                    self.upper_vars.append(var_name)

        self.generic_visit(node)
