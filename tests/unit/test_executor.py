"""Tests for SandboxExecutor module."""

from dsa_autopsy.models.domain import SolutionTestCase, SourceCode
from dsa_autopsy.services.sandbox_executor import SandboxExecutor


def test_sandbox_executor_success() -> None:
    """Test successful execution with trace capturing."""
    executor = SandboxExecutor()
    code = SourceCode(
        content=("def add_numbers(a, b):\n    c = a + b\n    return c\n"),
        language="python",
    )
    test_case = SolutionTestCase(
        id="test-success",
        inputs={"a": 3, "b": 5},
        expected_output=8,
    )
    result = executor.execute(code, test_case)

    assert result.exit_code == 0
    assert result.error_message is None
    assert len(result.trace_frames) > 0

    last_frame = result.trace_frames[-1]
    assert last_frame.local_variables.get("c") == 8
    assert last_frame.local_variables.get("return_value") == 8


def test_sandbox_executor_runtime_exception() -> None:
    """Test runtime exception inside sandbox."""
    executor = SandboxExecutor()
    code = SourceCode(
        content=("def divide_numbers(a, b):\n    return a / b\n"),
        language="python",
    )
    test_case = SolutionTestCase(
        id="test-zero-division",
        inputs={"a": 10, "b": 0},
        expected_output=0,
    )
    result = executor.execute(code, test_case)

    assert result.exit_code == 1
    assert result.error_message is not None
    assert "ZeroDivisionError" in result.error_message


def test_sandbox_executor_timeout() -> None:
    """Test execution timeout using a sleep."""
    executor = SandboxExecutor(timeout_secs=0.5)
    code = SourceCode(
        content=("import time\ndef infinite_sleep(a):\n    time.sleep(2.0)\n    return a\n"),
        language="python",
    )
    test_case = SolutionTestCase(
        id="test-timeout",
        inputs={"a": 42},
        expected_output=42,
    )
    result = executor.execute(code, test_case)

    assert result.exit_code == 1
    assert result.error_message is not None
    assert "TimeoutExpired" in result.error_message


def test_sandbox_executor_infinite_loop() -> None:
    """Test loop termination via instruction step limit constraint."""
    executor = SandboxExecutor(max_steps=100)
    code = SourceCode(
        content=(
            "def infinite_loop(x):\n    y = 0\n    while True:\n        y += 1\n    return y\n"
        ),
        language="python",
    )
    test_case = SolutionTestCase(
        id="test-loop",
        inputs={"x": 1},
        expected_output=1,
    )
    result = executor.execute(code, test_case)

    assert result.exit_code == 1
    assert result.error_message is not None
    assert "Instruction limit exceeded" in result.error_message
