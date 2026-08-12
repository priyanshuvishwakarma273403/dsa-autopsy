"""Unit tests for the TraceAnalyzer."""

from dsa_autopsy.models.domain import ExecutionResult, SourceCode, TraceFrame
from dsa_autopsy.services.trace_analyzer import TraceAnalyzer


def test_analyzer_off_by_one_boundary_bug() -> None:
    """Test analyzer detects off-by-one loop bound invariants that break in failing runs."""
    analyzer = TraceAnalyzer()
    code = SourceCode(
        content=(
            "def find_element(arr, target):\n"
            "    i = 0\n"
            "    while i <= len(arr):\n"
            "        if arr[i] == target:\n"
            "            return i\n"
            "        i += 1\n"
        ),
        language="python",
    )

    # Passing run: target is found before index reaches len(arr)
    passing_result = ExecutionResult(
        test_case_id="passing_test",
        stdout="",
        stderr="",
        exit_code=0,
        execution_time_seconds=0.1,
        matches_expected=True,
        trace_frames=[
            # Loop condition evaluation at line 3 (i=0)
            TraceFrame(line_number=3, local_variables={"i": 0, "arr": [10, 20], "target": 10}),
            # Inside loop body, returns index 0
            TraceFrame(line_number=4, local_variables={"i": 0, "arr": [10, 20], "target": 10}),
        ],
    )

    # Failing run: target is not in array, causes IndexError at i = len(arr)
    failing_result = ExecutionResult(
        test_case_id="fail_not_found",
        stdout="",
        stderr="IndexError: list index out of range",
        exit_code=1,
        execution_time_seconds=0.1,
        matches_expected=False,
        trace_frames=[
            TraceFrame(line_number=3, local_variables={"i": 0, "arr": [10, 20], "target": 30}),
            TraceFrame(line_number=3, local_variables={"i": 1, "arr": [10, 20], "target": 30}),
            TraceFrame(
                line_number=3, local_variables={"i": 2, "arr": [10, 20], "target": 30}
            ),  # i == len(arr)
        ],
    )

    violations = analyzer.analyze(code, [passing_result, failing_result])

    assert len(violations) >= 1
    # Find the violation for the loop boundary check
    violation = next(v for v in violations if "i < len(arr)" in v.invariant.expression)
    assert violation.invariant.location == "line:3"
    # The violation should happen at the third frame index of the failing run (where i = 2)
    assert violation.trace_frame_index == 2
    assert violation.context_variables["i"] == 2
    assert violation.context_variables["len(arr)"] == 2


def test_analyzer_incorrect_loop_termination() -> None:
    """Test analyzer detects incorrect loop termination invariants (e.g. left < right)."""
    analyzer = TraceAnalyzer()
    code = SourceCode(
        content=(
            "def binary_search(arr, target):\n"
            "    left = 0\n"
            "    right = len(arr) - 1\n"
            "    while left < right:\n"
            "        mid = (left + right) // 2\n"
            "        if arr[mid] == target:\n"
            "            return mid\n"
            "        elif arr[mid] < target:\n"
            "            left = mid + 1\n"
            "        else:\n"
            "            right = mid - 1\n"
            "    return -1\n"
        ),
        language="python",
    )

    # Passing run: target in the middle, found while left < right
    passing_result = ExecutionResult(
        test_case_id="pass_mid",
        stdout="",
        stderr="",
        exit_code=0,
        execution_time_seconds=0.1,
        matches_expected=True,
        trace_frames=[
            TraceFrame(
                line_number=4,
                local_variables={"left": 0, "right": 2, "arr": [1, 3, 5], "target": 3},
            ),
        ],
    )

    # Failing run: target is at the right boundary, loop exits with left == right, misses target
    failing_result = ExecutionResult(
        test_case_id="fail_right_boundary",
        stdout="",
        stderr="",
        exit_code=0,
        execution_time_seconds=0.1,
        matches_expected=False,
        trace_frames=[
            TraceFrame(
                line_number=4,
                local_variables={"left": 0, "right": 2, "arr": [1, 3, 5], "target": 5},
            ),
            TraceFrame(
                line_number=4,
                local_variables={"left": 2, "right": 2, "arr": [1, 3, 5], "target": 5},
            ),
        ],
    )

    violations = analyzer.analyze(code, [passing_result, failing_result])

    assert len(violations) >= 1
    violation = next(v for v in violations if "left < right" in v.invariant.expression)
    assert violation.invariant.location == "line:4"
    assert violation.trace_frame_index == 1
    assert violation.context_variables["left"] == 2
    assert violation.context_variables["right"] == 2


def test_analyzer_false_assumption_ordering() -> None:
    """Test analyzer detects invariants representing false assumptions about input ordering."""
    analyzer = TraceAnalyzer()
    code = SourceCode(
        content=("def search(arr, target):\n    # Assumes arr is sorted\n    pass\n"),
        language="python",
    )

    passing_result = ExecutionResult(
        test_case_id="pass_sorted",
        stdout="",
        stderr="",
        exit_code=0,
        execution_time_seconds=0.1,
        matches_expected=True,
        trace_frames=[
            TraceFrame(line_number=1, local_variables={"arr": [1, 2, 3], "target": 2}),
        ],
    )

    failing_result = ExecutionResult(
        test_case_id="fail_unsorted",
        stdout="",
        stderr="",
        exit_code=0,
        execution_time_seconds=0.1,
        matches_expected=False,
        trace_frames=[
            TraceFrame(line_number=1, local_variables={"arr": [3, 1, 2], "target": 2}),
        ],
    )

    violations = analyzer.analyze(code, [passing_result, failing_result])

    assert len(violations) >= 1
    violation = next(v for v in violations if "is_sorted(arr)" in v.invariant.expression)
    assert violation.invariant.location == "line:1"
    assert violation.trace_frame_index == 0
    assert violation.context_variables["arr"] == [3, 1, 2]


def test_analyzer_wrong_answer_bug() -> None:
    """Test analyzer detects violations when failing run has wrong answer.

    Uses matches_expected=False.
    """
    analyzer = TraceAnalyzer()
    code = SourceCode(
        content=("def add_one(x):\n    res = x + 1\n    return res\n"),
        language="python",
    )

    passing_result = ExecutionResult(
        test_case_id="tc_pass",
        stdout="",
        stderr="",
        exit_code=0,
        execution_time_seconds=0.1,
        matches_expected=True,
        trace_frames=[
            TraceFrame(line_number=2, local_variables={"x": 1, "res": 2}),
        ],
    )

    failing_result = ExecutionResult(
        test_case_id="tc_wrong_val",
        stdout="",
        stderr="",
        exit_code=0,
        execution_time_seconds=0.1,
        matches_expected=False,
        trace_frames=[
            TraceFrame(line_number=2, local_variables={"x": 2, "res": 2}),
        ],
    )

    violations = analyzer.analyze(code, [passing_result, failing_result])

    assert len(violations) >= 1
    # Note: 'res' comes alphabetically before 'x', so the canonical direction is 'res > x'
    violation = next(v for v in violations if "res > x" in v.invariant.expression)
    assert violation.invariant.location == "line:2"
    assert violation.trace_frame_index == 0
    assert violation.context_variables["x"] == 2
    assert violation.context_variables["res"] == 2


def test_analyzer_exact_set_of_violations_and_pruning() -> None:
    """Test that redundant/implied relations are successfully pruned."""
    analyzer = TraceAnalyzer()
    code = SourceCode(content="def dummy(): pass", language="python")

    passing_result = ExecutionResult(
        test_case_id="tc_pass",
        stdout="",
        stderr="",
        exit_code=0,
        execution_time_seconds=0.1,
        matches_expected=True,
        trace_frames=[
            TraceFrame(line_number=1, local_variables={"a": 1, "b": 5}),
        ],
    )

    failing_result = ExecutionResult(
        test_case_id="tc_fail",
        stdout="",
        stderr="",
        exit_code=0,
        execution_time_seconds=0.1,
        matches_expected=False,
        trace_frames=[
            TraceFrame(line_number=1, local_variables={"a": 5, "b": 5}),
        ],
    )

    violations = analyzer.analyze(code, [passing_result, failing_result])

    # In passing run: a=1, b=5.
    # Candidates generated: a < b, a <= b, a != b.
    # Since a < b holds, the stronger relation is kept, and a <= b and a != b are pruned.
    # Therefore, only one violation (for 'a < b') should be reported!
    expressions = [v.invariant.expression for v in violations]
    assert expressions == ["a < b"]


def test_analyzer_three_state_evaluation() -> None:
    """Test that missing variables or incompatible types do not trigger spurious violations."""
    analyzer = TraceAnalyzer()
    code = SourceCode(content="def dummy(): pass", language="python")

    passing_result = ExecutionResult(
        test_case_id="tc_pass",
        stdout="",
        stderr="",
        exit_code=0,
        execution_time_seconds=0.1,
        matches_expected=True,
        trace_frames=[
            TraceFrame(line_number=1, local_variables={"x": 5.5, "y": 10.5}),
        ],
    )

    failing_result = ExecutionResult(
        test_case_id="tc_fail",
        stdout="",
        stderr="",
        exit_code=0,
        execution_time_seconds=0.1,
        matches_expected=False,
        trace_frames=[
            # Frame 0: y is missing (not bound yet). Should not violate x < y.
            TraceFrame(line_number=1, local_variables={"x": 5.5}),
            # Frame 1: y is None (raises TypeError on comparison). Should not violate x < y.
            TraceFrame(line_number=1, local_variables={"x": 5.5, "y": None}),
            # Frame 2: x is 10.5, y is 5.5. Actually violates x < y!
            TraceFrame(line_number=1, local_variables={"x": 10.5, "y": 5.5}),
        ],
    )

    violations = analyzer.analyze(code, [passing_result, failing_result])

    assert len(violations) == 1
    assert violations[0].trace_frame_index == 2
    assert violations[0].invariant.expression == "x < y"


def test_analyzer_min_observations() -> None:
    """Test that min_observations skips lines with insufficient passing observations."""
    # Analyzer requiring at least 2 passing frames per line
    analyzer = TraceAnalyzer(min_observations=2)
    code = SourceCode(content="def dummy(): pass", language="python")

    passing_result = ExecutionResult(
        test_case_id="tc_pass",
        stdout="",
        stderr="",
        exit_code=0,
        execution_time_seconds=0.1,
        matches_expected=True,
        trace_frames=[
            # Line 1 has 2 observations across the trace
            TraceFrame(line_number=1, local_variables={"x": 5, "y": 10}),
            TraceFrame(line_number=1, local_variables={"x": 6, "y": 10}),
            # Line 2 has only 1 observation
            TraceFrame(line_number=2, local_variables={"a": 1, "b": 2}),
        ],
    )

    failing_result = ExecutionResult(
        test_case_id="tc_fail",
        stdout="",
        stderr="",
        exit_code=0,
        execution_time_seconds=0.1,
        matches_expected=False,
        trace_frames=[
            TraceFrame(line_number=1, local_variables={"x": 12, "y": 10}),
            TraceFrame(line_number=2, local_variables={"a": 5, "b": 2}),
        ],
    )

    violations = analyzer.analyze(code, [passing_result, failing_result])

    # Only line 1 violations should be found because line 2 had only
    # 1 observation (< min_observations)
    assert len(violations) > 0
    for v in violations:
        assert v.invariant.location == "line:1"


def test_analyzer_stable_invariant_id() -> None:
    """Test that invariant IDs are derived stably from expression and location."""
    analyzer = TraceAnalyzer()
    code = SourceCode(content="def dummy(): pass", language="python")

    passing_result = ExecutionResult(
        test_case_id="tc_pass",
        stdout="",
        stderr="",
        exit_code=0,
        execution_time_seconds=0.1,
        matches_expected=True,
        trace_frames=[
            TraceFrame(line_number=4, local_variables={"left": 0, "right": 2}),
        ],
    )

    failing_result = ExecutionResult(
        test_case_id="tc_fail",
        stdout="",
        stderr="",
        exit_code=0,
        execution_time_seconds=0.1,
        matches_expected=False,
        trace_frames=[
            TraceFrame(line_number=4, local_variables={"left": 2, "right": 2}),
        ],
    )

    violations = analyzer.analyze(code, [passing_result, failing_result])

    assert len(violations) == 1
    assert violations[0].invariant.id == "inv_line4_left_lt_right"


def test_analyzer_mathematical_alignment() -> None:
    """Test analyzer detects mathematical alignment invariant violations."""
    analyzer = TraceAnalyzer()
    code = SourceCode(content="def dummy(): pass", language="python")

    # In passing runs, x % 2 == 0 and index % step == 0 always hold
    passing_result = ExecutionResult(
        test_case_id="tc_pass",
        stdout="",
        stderr="",
        exit_code=0,
        execution_time_seconds=0.1,
        matches_expected=True,
        trace_frames=[
            TraceFrame(line_number=2, local_variables={"x": 2, "step": 2, "index": 4}),
            TraceFrame(line_number=2, local_variables={"x": 4, "step": 2, "index": 6}),
        ],
    )

    # In failing run, x is 3 (odd) and index is 5 (not multiple of step=2)
    failing_result = ExecutionResult(
        test_case_id="tc_fail",
        stdout="",
        stderr="",
        exit_code=0,
        execution_time_seconds=0.1,
        matches_expected=False,
        trace_frames=[
            TraceFrame(line_number=2, local_variables={"x": 3, "step": 2, "index": 5}),
        ],
    )

    violations = analyzer.analyze(code, [passing_result, failing_result])

    expressions = [v.invariant.expression for v in violations]
    assert "x % 2 == 0" in expressions
    assert "index % step == 0" in expressions


def test_analyzer_set_containment() -> None:
    """Test analyzer detects set containment invariant violations."""
    analyzer = TraceAnalyzer()
    code = SourceCode(content="def dummy(): pass", language="python")

    passing_result = ExecutionResult(
        test_case_id="tc_pass",
        stdout="",
        stderr="",
        exit_code=0,
        execution_time_seconds=0.1,
        matches_expected=True,
        trace_frames=[
            TraceFrame(line_number=3, local_variables={"item": 2, "visited": {1, 2, 3}}),
            TraceFrame(line_number=3, local_variables={"item": 3, "visited": {2, 3, 4}}),
        ],
    )

    failing_result = ExecutionResult(
        test_case_id="tc_fail",
        stdout="",
        stderr="",
        exit_code=0,
        execution_time_seconds=0.1,
        matches_expected=False,
        trace_frames=[
            TraceFrame(line_number=3, local_variables={"item": 5, "visited": {2, 3, 4}}),
        ],
    )

    violations = analyzer.analyze(code, [passing_result, failing_result])

    expressions = [v.invariant.expression for v in violations]
    assert "item in visited" in expressions


def test_analyzer_sublist_subset_relations() -> None:
    """Test analyzer detects subset and sublist invariant violations."""
    analyzer = TraceAnalyzer()
    code = SourceCode(content="def dummy(): pass", language="python")

    passing_result = ExecutionResult(
        test_case_id="tc_pass",
        stdout="",
        stderr="",
        exit_code=0,
        execution_time_seconds=0.1,
        matches_expected=True,
        trace_frames=[
            TraceFrame(line_number=4, local_variables={"sub": [1, 2], "parent": [1, 2, 3]}),
            TraceFrame(line_number=4, local_variables={"sub": [2, 3], "parent": [1, 2, 3, 4]}),
        ],
    )

    failing_result = ExecutionResult(
        test_case_id="tc_fail",
        stdout="",
        stderr="",
        exit_code=0,
        execution_time_seconds=0.1,
        matches_expected=False,
        trace_frames=[
            TraceFrame(line_number=4, local_variables={"sub": [2, 5], "parent": [1, 2, 3, 4]}),
        ],
    )

    violations = analyzer.analyze(code, [passing_result, failing_result])

    expressions = [v.invariant.expression for v in violations]
    assert "set(sub).issubset(set(parent))" in expressions


def test_analyzer_key_value_invariants() -> None:
    """Test analyzer detects key-value (indices match / values are frequencies) violations."""
    analyzer = TraceAnalyzer()
    code = SourceCode(content="def dummy(): pass", language="python")

    passing_result = ExecutionResult(
        test_case_id="tc_pass",
        stdout="",
        stderr="",
        exit_code=0,
        execution_time_seconds=0.1,
        matches_expected=True,
        trace_frames=[
            TraceFrame(
                line_number=5,
                local_variables={
                    "d_ind": {0: "a", 1: "b"},
                    "d_freq": {10: 1, 20: 2},
                    "arr": [10, 20, 20],
                    "size": 2,
                },
            ),
        ],
    )

    failing_result = ExecutionResult(
        test_case_id="tc_fail",
        stdout="",
        stderr="",
        exit_code=0,
        execution_time_seconds=0.1,
        matches_expected=False,
        trace_frames=[
            TraceFrame(
                line_number=5,
                local_variables={
                    "d_ind": {0: "a", 2: "b"},
                    "d_freq": {10: 2, 20: 2},
                    "arr": [10, 20, 20],
                    "size": 2,
                },
            ),
        ],
    )

    violations = analyzer.analyze(code, [passing_result, failing_result])

    expressions = [v.invariant.expression for v in violations]
    assert "set(d_ind.keys()) == set(range(size))" in expressions or "set(d_ind.keys()) == set(range(len(size)))" in expressions
    assert "all(d_freq[k] == arr.count(k) for k in d_freq)" in expressions

