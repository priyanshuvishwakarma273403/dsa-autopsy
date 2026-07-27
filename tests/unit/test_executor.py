"""Tests for SandboxExecutor module."""

import sys

import pytest

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


def test_sandbox_executor_disallowed_file_access() -> None:
    """Test that file system access (open) inside sandbox raises PermissionError."""
    executor = SandboxExecutor()
    code = SourceCode(
        content=(
            "def read_file(x):\n    with open('/etc/passwd', 'r') as f:\n        return f.read()\n"
        ),
        language="python",
    )
    test_case = SolutionTestCase(
        id="test-file-access",
        inputs={"x": 1},
        expected_output=None,
    )
    result = executor.execute(code, test_case)
    assert result.exit_code == 1
    assert result.error_message is not None
    assert any(
        err in result.error_message
        for err in ["PermissionError", "disabled in the sandbox", "File system access is disabled"]
    )


def test_sandbox_executor_disallowed_network_access() -> None:
    """Test that network access (socket.socket) inside sandbox raises PermissionError."""
    executor = SandboxExecutor()
    code = SourceCode(
        content=("import socket\ndef make_conn(x):\n    s = socket.socket()\n    return x\n"),
        language="python",
    )
    test_case = SolutionTestCase(
        id="test-net-access",
        inputs={"x": 1},
        expected_output=None,
    )
    result = executor.execute(code, test_case)
    assert result.exit_code == 1
    assert result.error_message is not None
    assert any(
        err in result.error_message for err in ["PermissionError", "disabled in the sandbox"]
    )


def test_sandbox_executor_disallowed_import() -> None:
    """Test that importing a disallowed module raises PermissionError."""
    executor = SandboxExecutor()
    code = SourceCode(
        content=("import subprocess\ndef run_cmd(x):\n    return x\n"),
        language="python",
    )
    test_case = SolutionTestCase(
        id="test-bad-import",
        inputs={"x": 1},
        expected_output=None,
    )
    result = executor.execute(code, test_case)
    assert result.exit_code == 1
    assert result.error_message is not None
    assert any(
        err in result.error_message for err in ["PermissionError", "disabled in the sandbox"]
    )


def test_sandbox_executor_subclass_gadget_escape() -> None:
    """Test that subclass gadget escapes are blocked by the sandbox."""
    executor = SandboxExecutor()
    code = SourceCode(
        content=(
            "def escape(x):\n"
            "    # Attempt to retrieve os.system via subclass gadget\n"
            "    for c in ().__class__.__bases__[0].__subclasses__():\n"
            "        if c.__name__ == '_wrap_close':\n"
            "            c.__init__.__globals__['system']('echo hacked')\n"
            "    return x\n"
        ),
        language="python",
    )
    test_case = SolutionTestCase(
        id="test-escape",
        inputs={"x": 1},
        expected_output=None,
    )
    result = executor.execute(code, test_case)
    assert result.exit_code == 1
    assert result.error_message is not None
    assert any(
        err in result.error_message for err in ["PermissionError", "AttributeError", "disabled"]
    )


@pytest.mark.skipif(sys.platform == "win32", reason="Resource limits not supported on Windows")
def test_sandbox_executor_memory_limit() -> None:
    """Test that extremely large memory allocations are prevented or trigger errors."""
    executor = SandboxExecutor(timeout_secs=2.0)
    code = SourceCode(
        content=(
            "def oom(x):\n"
            "    # This will allocate a huge list and exceed the memory limit (AS rlimit)\n"
            "    y = [0] * (10 ** 8)\n"
            "    return len(y)\n"
        ),
        language="python",
    )
    test_case = SolutionTestCase(
        id="test-oom",
        inputs={"x": 1},
        expected_output=None,
    )
    result = executor.execute(code, test_case)
    assert result.exit_code == 1
    assert result.error_message is not None
    assert any(
        err in result.error_message
        for err in [
            "MemoryError",
            "TimeoutExpired",
            "Instruction limit exceeded",
            "crashed",
            "failed initialization",
        ]
    )
