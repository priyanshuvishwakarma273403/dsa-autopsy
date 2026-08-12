"""Concrete implementation of the execution trace analyzer."""

import ast
from typing import Any

from dsa_autopsy.interfaces.analyzer import BaseAnalyzer
from dsa_autopsy.models.domain import ExecutionResult, Invariant, SourceCode, Violation
from dsa_autopsy.services.ast_parser import ASTBoundExtractor


class TraceAnalyzer(BaseAnalyzer):
    """Analyzes execution traces to identify violated loop/function invariants.

    Note on source-agnostic design:
    This analyzer is deliberately source-agnostic to decouple its analysis logic from
    language-specific AST schemas or parsing subtleties. It infers loop/function invariants
    solely from value states recorded in execution trace frames, making it robust to variations in
    source structure.
    """

    def __init__(self, min_observations: int = 1, max_candidates: int = 1000) -> None:
        """Initialize the trace analyzer.

        Args:
            min_observations: Minimum number of passing frames required at a line
                before mining invariants for that line.
            max_candidates: Maximum number of candidate invariants to evaluate per line.
        """
        self.min_observations = min_observations
        self.max_candidates = max_candidates

    def analyze(
        self, code: SourceCode, execution_results: list[ExecutionResult]
    ) -> list[Violation]:
        """Analyze execution traces to locate broken invariants.

        Args:
            code: The original source code.
            execution_results: Traces and execution results of running test cases.

        Returns:
            A list of detected violations and invariant breaks.
        """
        code_lines = code.lines

        # 1. Classify execution results into passing and failing runs
        passing_results = []
        failing_results = []
        for res in execution_results:
            if not res.matches_expected:
                failing_results.append(res)
            else:
                passing_results.append(res)

        if not failing_results:
            return []

        # 2. Group trace frames from passing runs by line number
        passing_frames_by_line: dict[int, list[dict[str, Any]]] = {}
        for res in passing_results:
            for frame in res.trace_frames:
                passing_frames_by_line.setdefault(frame.line_number, []).append(
                    frame.local_variables
                )

        # 3. Helper functions to evaluate candidate invariants
        def is_sorted(val: Any) -> bool:
            try:
                if not isinstance(val, (list, tuple, str)):
                    return False
                return all(val[i] <= val[i + 1] for i in range(len(val) - 1))
            except Exception:
                return False

        def eval_candidate(rel: tuple[Any, ...], locals_dict: dict[str, Any]) -> int:
            # Returns:
            #  1: Holds (True)
            #  0: Violated (False)
            # -1: Not Applicable (missing variables or type errors/exceptions)
            if len(rel) == 5:
                left, op, right, op2, right2 = rel
                if left not in locals_dict:
                    return -1
                left_val = locals_dict[left]

                if isinstance(right, str) and right in locals_dict:
                    right_val = locals_dict[right]
                else:
                    right_val = right

                if isinstance(right2, str) and right2 in locals_dict:
                    right2_val = locals_dict[right2]
                else:
                    right2_val = right2

                try:
                    if op == "%":
                        temp_val = left_val % right_val
                        if op2 == "==":
                            return 1 if temp_val == right2_val else 0
                        if op2 == "!=":
                            return 1 if temp_val != right2_val else 0
                except (TypeError, ValueError, ZeroDivisionError, AttributeError):
                    return -1
                except Exception:
                    return -1
                return -1

            left, op, right = rel
            if left not in locals_dict:
                return -1

            left_val = locals_dict[left]

            if right == "is_sorted" or op == "is_sorted":
                if not isinstance(left_val, (list, tuple, str)):
                    return -1
                return 1 if is_sorted(left_val) else 0

            if isinstance(right, str):
                if right in locals_dict:
                    right_val = locals_dict[right]
                else:
                    try:
                        eval_globals = {"len": len, "range": range, "set": set, "list": list}
                        right_val = eval(right, eval_globals, locals_dict)
                    except Exception:
                        right_val = right
            else:
                right_val = right

            try:
                if op == "<":
                    return 1 if left_val < right_val else 0
                if op == "<=":
                    return 1 if left_val <= right_val else 0
                if op == ">":
                    return 1 if left_val > right_val else 0
                if op == ">=":
                    return 1 if left_val >= right_val else 0
                if op == "==":
                    return 1 if left_val == right_val else 0
                if op == "!=":
                    return 1 if left_val != right_val else 0
                if op == "in":
                    return 1 if left_val in right_val else 0
                if op == "issubset":
                    return 1 if set(left_val).issubset(set(right_val)) else 0
                if op == "keys_match_indices":
                    if isinstance(right_val, int):
                        return 1 if set(left_val.keys()) == set(range(right_val)) else 0
                    return 1 if set(left_val.keys()) == set(range(len(right_val))) else 0
                if op == "values_are_frequencies":

                    def get_count(coll: Any, item: Any) -> int:
                        if hasattr(coll, "count"):
                            return int(coll.count(item))
                        return 1 if item in coll else 0

                    return 1 if all(left_val[k] == get_count(right_val, k) for k in left_val) else 0
            except (TypeError, ValueError, AttributeError):
                return -1
            except Exception:
                return -1
            return -1

        # Extract seed invariants from source code AST
        seed_bounds: dict[int, list[tuple[Any, ...]]] = {}
        if code.language.lower() in ["python", "py"]:
            try:
                tree = ast.parse(code.content)
                extractor = ASTBoundExtractor()
                extractor.visit(tree)
                seed_bounds = extractor.bounds
            except Exception:
                pass

        # 4. Generate and filter invariants that hold across all passing runs
        invariants_by_line: dict[int, list[tuple[Any, ...]]] = {}

        for line_num, frames in passing_frames_by_line.items():
            if len(frames) < self.min_observations:
                continue

            # Find common variables present in all frames at this line
            common_vars = set(frames[0].keys())
            for f in frames[1:]:
                common_vars.intersection_update(f.keys())

            # Exclude internal variables and return_value
            common_vars = {v for v in common_vars if not v.startswith("__") and v != "return_value"}

            sorted_vars = sorted(common_vars)
            candidates: list[tuple[Any, ...]] = []

            # Add seed invariants for this line
            if line_num in seed_bounds:
                for bound in seed_bounds[line_num]:
                    left = bound[0]
                    right = bound[2]
                    if left in common_vars:
                        # Validate that all variables inside right (if it's a
                        # string expression) are in common_vars
                        is_valid = True
                        if isinstance(right, str):
                            try:
                                expr_tree = ast.parse(right)
                                builtins = {
                                    "len",
                                    "range",
                                    "set",
                                    "list",
                                    "dict",
                                    "str",
                                    "int",
                                    "float",
                                    "abs",
                                    "max",
                                    "min",
                                    "sum",
                                }
                                for node in ast.walk(expr_tree):
                                    if (
                                        isinstance(node, ast.Name)
                                        and node.id not in common_vars
                                        and node.id not in builtins
                                    ):
                                        is_valid = False
                                        break
                            except Exception:
                                is_valid = False
                        if is_valid and bound not in candidates:
                            candidates.append(bound)

            for var in sorted_vars:
                val = frames[0][var]
                if isinstance(val, (int, float)):
                    candidates.append((var, ">", 0))
                    candidates.append((var, ">=", 0))

                if isinstance(val, int):
                    candidates.append((var, "%", 2, "==", 0))

                if isinstance(val, (list, tuple, str)):
                    candidates.append((var, "is_sorted", "is_sorted"))

                for other in sorted_vars:
                    if other == var:
                        continue
                    other_val = frames[0][other]

                    # Enforce a canonical order for variable-to-variable comparison
                    # to generate only one direction for each unordered pair.
                    if (
                        var < other
                        and isinstance(val, (int, float))
                        and isinstance(other_val, (int, float))
                    ):
                        candidates.append((var, "<", other))
                        candidates.append((var, "<=", other))
                        candidates.append((var, ">", other))
                        candidates.append((var, ">=", other))
                        candidates.append((var, "==", other))
                        candidates.append((var, "!=", other))

                    # Variable-to-length comparison
                    if isinstance(val, (int, float)) and isinstance(other_val, (list, tuple, str)):
                        candidates.append((var, "<", f"len({other})"))
                        candidates.append((var, "<=", f"len({other})"))
                        candidates.append((var, ">", f"len({other})"))
                        candidates.append((var, ">=", f"len({other})"))
                        candidates.append((var, "==", f"len({other})"))
                        candidates.append((var, "!=", f"len({other})"))

                    # Mathematical alignment (variable multiples)
                    if isinstance(val, int) and isinstance(other_val, int):
                        candidates.append((var, "%", other, "==", 0))

                    # Set Containment
                    if isinstance(val, (list, tuple, set, dict)) and isinstance(
                        other_val, (int, float, str)
                    ):
                        candidates.append((other, "in", var))

                    # Sublist & Subset relations
                    if isinstance(val, (list, tuple, set, dict)) and isinstance(
                        other_val, (list, tuple, set, dict)
                    ):
                        candidates.append((other, "issubset", var))

                    # Key-Value Invariants
                    if isinstance(val, dict):
                        if isinstance(other_val, (list, tuple, set)):
                            candidates.append((var, "keys_match_indices", other))
                            candidates.append((var, "values_are_frequencies", other))
                        elif isinstance(other_val, int):
                            candidates.append((var, "keys_match_indices", other))

            # Limit the total number of candidates evaluated per line
            if len(candidates) > self.max_candidates:
                candidates = candidates[: self.max_candidates]

            valid_invariants = []
            for cand in candidates:
                if all(eval_candidate(cand, f) == 1 for f in frames):
                    valid_invariants.append(cand)

            # Group valid invariants by (left, right) to prune implied/redundant relationships
            grouped: dict[tuple[str, Any], set[str]] = {}
            pruned_invariants: list[tuple[Any, ...]] = []
            for cand in valid_invariants:
                if len(cand) == 3:
                    left, op, right = cand
                    grouped.setdefault((left, right), set()).add(op)
                else:
                    pruned_invariants.append(cand)

            for (left, right), ops in grouped.items():
                if "<" in ops:
                    ops.discard("<=")
                    ops.discard("!=")
                if ">" in ops:
                    ops.discard(">=")
                    ops.discard("!=")
                if "==" in ops:
                    ops.discard("<=")
                    ops.discard(">=")
                if right == 0 and ">" in ops:
                    ops.discard(">=")

                for op in ops:
                    pruned_invariants.append((left, op, right))

            if pruned_invariants:
                invariants_by_line[line_num] = pruned_invariants

        # 5. Check failing runs to locate the first violation
        violations: list[Violation] = []

        op_map = {
            "<": "lt",
            "<=": "lte",
            ">": "gt",
            ">=": "gte",
            "==": "eq",
            "!=": "neq",
            "is_sorted": "is_sorted",
            "in": "in",
            "issubset": "issubset",
            "keys_match_indices": "keys_match_indices",
            "values_are_frequencies": "values_are_frequencies",
            "%": "mod",
        }

        for res in failing_results:
            for idx, frame in enumerate(res.trace_frames):
                line_num = frame.line_number
                if line_num not in invariants_by_line:
                    continue

                locals_dict = frame.local_variables
                for cand in invariants_by_line[line_num]:
                    if eval_candidate(cand, locals_dict) == 0:
                        if len(cand) == 5:
                            left, op, right, op2, right2 = cand
                            expr = f"{left} {op} {right} {op2} {right2}"

                            clean_op = f"{op_map.get(op, op)}_{op_map.get(op2, op2)}"
                            clean_right = f"{right}_{right2}"
                            clean_left = "".join(c for c in left if c.isalnum() or c == "_")
                            clean_right = "".join(c for c in clean_right if c.isalnum() or c == "_")
                            expr_part = f"{clean_left}_{clean_op}_{clean_right}"
                        else:
                            left, op, right = cand
                            if op == "is_sorted":
                                expr = f"is_sorted({left})"
                            elif op == "issubset":
                                expr = f"set({left}).issubset(set({right}))"
                            elif op == "keys_match_indices":
                                is_int = isinstance(right, int) or (
                                    isinstance(right, str)
                                    and right in locals_dict
                                    and isinstance(locals_dict[right], int)
                                )
                                if is_int:
                                    expr = f"set({left}.keys()) == set(range({right}))"
                                else:
                                    expr = f"set({left}.keys()) == set(range(len({right})))"
                            elif op == "values_are_frequencies":
                                expr = f"all({left}[k] == {right}.count(k) for k in {left})"
                            else:
                                expr = f"{left} {op} {right}"

                            clean_op = op_map.get(op, op)
                            clean_right = str(right).replace("(", "_").replace(")", "_")
                            clean_left = "".join(c for c in left if c.isalnum() or c == "_")
                            clean_right = "".join(c for c in clean_right if c.isalnum() or c == "_")
                            expr_part = f"{clean_left}_{clean_op}_{clean_right}"

                        while "__" in expr_part:
                            expr_part = expr_part.replace("__", "_")
                        expr_part = expr_part.strip("_")
                        inv_id = f"inv_line{line_num}_{expr_part}"

                        # Get source code line for descriptive info
                        line_content = ""
                        if 1 <= line_num <= len(code_lines):
                            line_content = code_lines[line_num - 1].strip()

                        desc = f"Invariant '{expr}' violated in failing run"
                        if line_content:
                            desc += f" at: {line_content}"

                        inv = Invariant(
                            id=inv_id,
                            expression=expr,
                            location=f"line:{line_num}",
                            description=desc,
                        )

                        context_vars: dict[str, Any] = {}
                        if left in locals_dict:
                            context_vars[left] = locals_dict[left]
                        if isinstance(right, str) and right in locals_dict:
                            context_vars[right] = locals_dict[right]
                        elif (
                            isinstance(right, str)
                            and right.startswith("len(")
                            and right.endswith(")")
                        ):
                            seq_name = right[4:-1]
                            if seq_name in locals_dict:
                                context_vars[seq_name] = locals_dict[seq_name]
                                context_vars[f"len({seq_name})"] = len(locals_dict[seq_name])

                        if len(cand) == 5 and isinstance(right2, str) and right2 in locals_dict:
                            context_vars[right2] = locals_dict[right2]

                        violation = Violation(
                            invariant=inv,
                            test_case_id=res.test_case_id,
                            trace_frame_index=idx,
                            context_variables=context_vars,
                            explanation=f"Invariant '{expr}' violated.",
                        )
                        violations.append(violation)

        return violations
