"""Concrete implementation of the execution trace analyzer."""

from typing import Any

from dsa_autopsy.interfaces.analyzer import BaseAnalyzer
from dsa_autopsy.models.domain import ExecutionResult, Invariant, SourceCode, Violation


class TraceAnalyzer(BaseAnalyzer):
    """Analyzes execution traces to identify violated loop/function invariants."""

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
        _ = code
        # 1. Classify execution results into passing and failing runs
        passing_results = []

        failing_results = []
        for res in execution_results:
            is_failing = False
            if res.matches_expected is not None:
                is_failing = not res.matches_expected
            else:
                is_failing = (
                    res.exit_code != 0
                    or res.error_message is not None
                    or "fail" in res.test_case_id.lower()
                )

            if is_failing:
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
                if not isinstance(val, (list, tuple)):
                    return False
                return all(val[i] <= val[i + 1] for i in range(len(val) - 1))
            except Exception:
                return False

        def eval_candidate(rel: tuple[str, str, Any], locals_dict: dict[str, Any]) -> bool:
            left, op, right = rel
            if left not in locals_dict:
                return False

            left_val = locals_dict[left]

            if isinstance(right, str) and right.startswith("len(") and right.endswith(")"):
                seq_name = right[4:-1]
                if seq_name not in locals_dict:
                    return False
                seq_val = locals_dict[seq_name]
                try:
                    right_val = len(seq_val)
                except Exception:
                    return False
            elif right == "is_sorted":
                return is_sorted(left_val)
            elif isinstance(right, str) and right in locals_dict:
                right_val = locals_dict[right]
            else:
                right_val = right

            try:
                if op == "<":
                    return bool(left_val < right_val)
                if op == "<=":
                    return bool(left_val <= right_val)
                if op == ">":
                    return bool(left_val > right_val)
                if op == ">=":
                    return bool(left_val >= right_val)
                if op == "==":
                    return bool(left_val == right_val)
                if op == "!=":
                    return bool(left_val != right_val)
                if op == "is_sorted":
                    return bool(is_sorted(left_val))
            except Exception:
                pass
            return False

        # 4. Generate and filter invariants that hold across all passing runs
        invariants_by_line: dict[int, list[tuple[str, str, Any]]] = {}

        for line_num, frames in passing_frames_by_line.items():
            if not frames:
                continue

            # Find common variables present in all frames at this line
            common_vars = set(frames[0].keys())
            for f in frames[1:]:
                common_vars.intersection_update(f.keys())

            # Exclude internal variables and return_value
            common_vars = {v for v in common_vars if not v.startswith("__") and v != "return_value"}

            candidates: list[tuple[str, str, Any]] = []
            for var in common_vars:
                val = frames[0][var]
                if isinstance(val, (int, float)):
                    candidates.append((var, ">=", 0))
                    candidates.append((var, ">", 0))

                if isinstance(val, (list, tuple, str)):
                    candidates.append((var, "is_sorted", "is_sorted"))

                for other in common_vars:
                    if other == var:
                        continue
                    other_val = frames[0][other]

                    if isinstance(val, (int, float)) and isinstance(other_val, (int, float)):
                        candidates.append((var, "<", other))
                        candidates.append((var, "<=", other))
                        candidates.append((var, ">", other))
                        candidates.append((var, ">=", other))
                        candidates.append((var, "==", other))
                        candidates.append((var, "!=", other))

                    if isinstance(val, (int, float)) and isinstance(other_val, (list, tuple, str)):
                        candidates.append((var, "<", f"len({other})"))
                        candidates.append((var, "<=", f"len({other})"))
                        candidates.append((var, ">", f"len({other})"))
                        candidates.append((var, ">=", f"len({other})"))
                        candidates.append((var, "==", f"len({other})"))
                        candidates.append((var, "!=", f"len({other})"))

            valid_invariants = []
            for cand in candidates:
                if all(eval_candidate(cand, f) for f in frames):
                    valid_invariants.append(cand)

            if valid_invariants:
                invariants_by_line[line_num] = valid_invariants

        # 5. Check failing runs to locate the first violation
        violations: list[Violation] = []
        invariant_counter = 1

        for res in failing_results:
            for idx, frame in enumerate(res.trace_frames):
                line_num = frame.line_number
                if line_num not in invariants_by_line:
                    continue

                locals_dict = frame.local_variables
                for cand in invariants_by_line[line_num]:
                    if not eval_candidate(cand, locals_dict):
                        left, op, right = cand
                        expr = f"is_sorted({left})" if op == "is_sorted" else f"{left} {op} {right}"

                        inv = Invariant(
                            id=f"inv_line{line_num}_{invariant_counter}",
                            expression=expr,
                            location=f"line:{line_num}",
                            description=f"Invariant '{expr}' violated in failing run",
                        )
                        invariant_counter += 1

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

                        violation = Violation(
                            invariant=inv,
                            test_case_id=res.test_case_id,
                            trace_frame_index=idx,
                            context_variables=context_vars,
                            explanation=f"Invariant '{expr}' violated. Context: {context_vars}",
                        )
                        violations.append(violation)

        return violations
