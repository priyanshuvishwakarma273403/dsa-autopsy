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
        trace_frames=[
            TraceFrame(line_number=2, local_variables={"x": 1, "res": 2}),
        ],
        matches_expected=True,
    )

    failing_result = ExecutionResult(
        test_case_id="tc_wrong_val",
        stdout="",
        stderr="",
        exit_code=0,
        execution_time_seconds=0.1,
        trace_frames=[
            TraceFrame(line_number=2, local_variables={"x": 2, "res": 2}),
        ],
        matches_expected=False,
    )

    violations = analyzer.analyze(code, [passing_result, failing_result])

    assert len(violations) >= 1
    violation = next(v for v in violations if "x < res" in v.invariant.expression)
    assert violation.invariant.location == "line:2"
    assert violation.trace_frame_index == 0
    assert violation.context_variables["x"] == 2
    assert violation.context_variables["res"] == 2
