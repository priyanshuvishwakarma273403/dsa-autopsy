"""Concrete implementation of the sandboxed execution engine."""

import json
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from dsa_autopsy.interfaces.executor import BaseExecutor
from dsa_autopsy.models.domain import ExecutionResult, SolutionTestCase, SourceCode, TraceFrame


def _extract_exception_name(stderr_text: str) -> str | None:
    """Extract a concise exception name or message from stderr traceback."""
    if not stderr_text:
        return None
    if "Instruction limit exceeded" in stderr_text:
        return "Instruction limit exceeded"
    if "TimeoutExpired" in stderr_text:
        return "TimeoutExpired"
    m = re.search(r"([A-Za-z_]+Error(?:\s*:\s*[^\n]+)?)", stderr_text)
    if m:
        return m.group(0)
    for line in reversed(stderr_text.splitlines()):
        line = line.strip()
        if line:
            return line
    return None


class SandboxExecutor(BaseExecutor):
    """Executes Python source code in a restricted subprocess sandbox with trace collection."""

    def __init__(self, timeout_secs: float = 5.0, max_steps: int = 10000) -> None:
        """Initialize the executor with timeout and instruction step limit constraints."""
        self.timeout_secs = timeout_secs
        self.max_steps = max_steps

    def execute(self, code: SourceCode, test_case: SolutionTestCase) -> ExecutionResult:
        """Run the solution inside a sandboxed python process with trace capturing."""
        if code.language.lower() != "python":
            return ExecutionResult(
                test_case_id=test_case.id,
                stdout="",
                stderr=f"Unsupported language: {code.language}",
                exit_code=1,
                execution_time_seconds=0.0,
                trace_frames=[],
                error_message=f"Unsupported language: {code.language}",
            )

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_dir_path = Path(temp_dir)
            code_file = temp_dir_path / "solution.py"
            inputs_file = temp_dir_path / "inputs.json"
            output_file = temp_dir_path / "output.json"
            runner_file = temp_dir_path / "runner.py"

            # Write user code and test case inputs
            code_file.write_text(code.content, encoding="utf-8")
            input_data = {"inputs": test_case.inputs}
            inputs_file.write_text(json.dumps(input_data), encoding="utf-8")

            # Generate and write sandbox runner script
            runner_content = self._generate_runner_content()
            runner_file.write_text(runner_content, encoding="utf-8")

            start_time = time.perf_counter()

            try:
                # Launch subprocess
                process = subprocess.run(
                    [
                        sys.executable,
                        str(runner_file),
                        str(code_file),
                        str(inputs_file),
                        str(output_file),
                    ],
                    capture_output=True,
                    text=True,
                    timeout=self.timeout_secs,
                )
                end_time = time.perf_counter()
                elapsed = end_time - start_time

                if output_file.exists():
                    try:
                        with output_file.open(encoding="utf-8") as f:
                            result_data = json.load(f)

                        # Parse recorded trace frames
                        trace_frames = []
                        for frame_data in result_data.get("trace_frames", []):
                            trace_frames.append(
                                TraceFrame(
                                    line_number=frame_data["line_number"],
                                    local_variables=frame_data["local_variables"],
                                    instruction=frame_data["instruction"],
                                )
                            )

                        error_msg = result_data.get("error_message")
                        if (
                            not error_msg
                            or error_msg == "Sandbox process crashed or failed initialization"
                        ):
                            stderr_str = result_data.get("stderr", "") or process.stderr or ""
                            exc_name = _extract_exception_name(stderr_str)
                            if exc_name:
                                error_msg = exc_name

                        return ExecutionResult(
                            test_case_id=test_case.id,
                            stdout=result_data.get("stdout", ""),
                            stderr=result_data.get("stderr", ""),
                            exit_code=result_data.get("exit_code", 0),
                            execution_time_seconds=result_data.get("execution_time_seconds", 0.0),
                            trace_frames=trace_frames,
                            error_message=error_msg,
                        )
                    except Exception as e:
                        stderr_str = process.stderr or ""
                        exc_name = _extract_exception_name(stderr_str)
                        return ExecutionResult(
                            test_case_id=test_case.id,
                            stdout=process.stdout,
                            stderr=process.stderr + f"\nFailed to parse sandbox output: {e!s}",
                            exit_code=1,
                            execution_time_seconds=elapsed,
                            trace_frames=[],
                            error_message=exc_name or f"Sandbox serialization error: {e!s}",
                        )
                else:
                    stderr_str = process.stderr or ""
                    exc_name = _extract_exception_name(stderr_str)
                    return ExecutionResult(
                        test_case_id=test_case.id,
                        stdout=process.stdout,
                        stderr=stderr_str or "Sandbox process exited without generating report",
                        exit_code=process.returncode,
                        execution_time_seconds=elapsed,
                        trace_frames=[],
                        error_message=(
                            exc_name or "Sandbox process crashed or failed initialization"
                        ),
                    )

            except subprocess.TimeoutExpired as e:
                elapsed = time.perf_counter() - start_time
                stdout_str = (
                    e.stdout.decode("utf-8") if isinstance(e.stdout, bytes) else (e.stdout or "")
                )
                stderr_str = (
                    e.stderr.decode("utf-8") if isinstance(e.stderr, bytes) else (e.stderr or "")
                )
                return ExecutionResult(
                    test_case_id=test_case.id,
                    stdout=stdout_str,
                    stderr=stderr_str,
                    exit_code=1,
                    execution_time_seconds=elapsed,
                    trace_frames=[],
                    error_message=(
                        f"TimeoutExpired: Execution exceeded limit of {self.timeout_secs}s"
                    ),
                )

    def _generate_runner_content(self) -> str:
        """Return the runner script to execute inside the sandbox."""
        return f"""import sys
import json
import traceback
import builtins
import time
import ast
import socket
import os
from io import StringIO

try:
    import resource
except ImportError:
    resource = None

original_open = builtins.open

# List of modules that the user is allowed to import
whitelisted_modules = {{
    "math", "random", "collections", "itertools", "bisect", "heapq",
    "functools", "typing", "json", "datetime", "string", "re", "copy", "time",
}}

# Pre-import all whitelisted modules so they are cached in sys.modules
# and don't trigger disk access/file opening when imported by user code.
for module_name in whitelisted_modules:
    try:
        __import__(module_name)
    except Exception:
        pass

def make_safe(val):
    if isinstance(val, (int, float, bool, str)) or val is None:
        return val
    if isinstance(val, (list, tuple, set)):
        return [make_safe(x) for x in list(val)[:100]]
    if isinstance(val, dict):
        return {{str(k): make_safe(v) for k, v in list(val.items())[:100]}}
    try:
        return repr(val)
    except Exception:
        return str(type(val))

def find_entry_point(code_content):
    try:
        tree = ast.parse(code_content)
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.ClassDef) and node.name == "Solution":
                for sub_node in ast.iter_child_nodes(node):
                    if isinstance(sub_node, ast.FunctionDef) and not sub_node.name.startswith("__"):
                        return "Solution", sub_node.name
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.FunctionDef) and not node.name.startswith("__"):
                return None, node.name
    except Exception:
        pass
    return None, None

def run_sandbox():
    if len(sys.argv) < 4:
        sys.exit(1)

    code_path = sys.argv[1]
    inputs_path = sys.argv[2]
    output_path = sys.argv[3]

    with original_open(code_path, "r", encoding="utf-8") as f:
        code_content = f.read()

    with original_open(inputs_path, "r", encoding="utf-8") as f:
        test_case_data = json.load(f)

    inputs = test_case_data.get("inputs", {{}})

    class_name, func_name = find_entry_point(code_content)
    if not func_name:
        result = {{
            "stdout": "",
            "stderr": "No entry function found in source code.",
            "exit_code": 1,
            "execution_time_seconds": 0.0,
            "trace_frames": [],
            "error_message": "No entry function found in source code."
        }}
        with original_open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f)
        sys.exit(0)

    original_import = builtins.__import__

    def sandboxed_import(name, globals=None, locals=None, fromlist=(), level=0):
        top_name = name.split('.')[0]
        if top_name not in whitelisted_modules:
            raise PermissionError(f"Importing module '{{name}}' is disabled in the sandbox.")
        return original_import(name, globals, locals, fromlist, level)

    namespace = {{}}
    try:
        compiled_code = compile(code_content, code_path, "exec")
    except Exception as e:
        result = {{
            "stdout": "",
            "stderr": traceback.format_exc(),
            "exit_code": 1,
            "execution_time_seconds": 0.0,
            "trace_frames": [],
            "error_message": f"Compilation failed: {{str(e)}}"
        }}
        with original_open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f)
        sys.exit(0)

    # 1. Monkeypatch in-place all dangerous components to prevent subclass gadget bypasses
    def blocked_action(*args, **kwargs):
        raise PermissionError("Access to this function/operation is disabled in the sandbox.")

    # Patch builtins
    builtins.open = blocked_action

    # Patch socket
    for func in [
        'socket', 'socketpair', 'fromfd', 'create_connection',
        'create_server', 'getaddrinfo', 'getnameinfo', 'gethostname',
        'gethostbyname'
    ]:
        if hasattr(socket, func):
            setattr(socket, func, blocked_action)

    # Patch os
    dangerous_os = [
        'system', 'popen', 'fork', 'forkpty', 'execve', 'execv', 'execvp', 'execvpe',
        'execl', 'execle', 'execlp', 'execlpe', 'spawnv', 'spawnve', 'spawnvp', 'spawnvpe',
        'spawnl', 'spawnle', 'spawnlp', 'spawnlpe', 'posix_spawn', 'posix_spawnp',
        'kill', 'killpg', 'open', 'read', 'write', 'dup', 'dup2', 'listdir', 'scandir',
        'walk', 'remove', 'unlink', 'rmdir', 'removedirs', 'rename', 'renames',
        'replace', 'chmod', 'chown', 'lchown', 'symlink', 'link', 'mkdir', 'makedirs'
    ]
    for func in dangerous_os:
        if hasattr(os, func):
            setattr(os, func, blocked_action)

    # Clear environment variables
    if hasattr(os, 'environ'):
        os.environ.clear()

    # Patch subprocess
    try:
        import subprocess
        for func in [
            'Popen', 'run', 'call', 'check_call', 'check_output',
            'getstatusoutput', 'getoutput'
        ]:
            if hasattr(subprocess, func):
                setattr(subprocess, func, blocked_action)
    except Exception:
        pass

    # Clean up sys.modules to remove non-whitelisted modules (so subclass gadget can't access them)
    for mod in list(sys.modules.keys()):
        top_name = mod.split('.')[0]
        if top_name not in whitelisted_modules and top_name not in [
            'sys', 'builtins', 'json', 'traceback', 'time', 'ast', 'io', '_io'
        ]:
            sys.modules.pop(mod, None)

    # 2. Apply OS-level resource limits (RLIMITs) if available
    if resource is not None:
        # Limit memory (Address Space) to 512MB to prevent OOM
        try:
            resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024, 512 * 1024 * 1024))
        except Exception:
            pass

        # Limit CPU time to timeout + 2 seconds to terminate infinite/runaway C execution loops
        cpu_limit = int({self.timeout_secs}) + 2
        try:
            resource.setrlimit(resource.RLIMIT_CPU, (cpu_limit, cpu_limit))
        except Exception:
            pass

        # Limit number of open file descriptors to 10 (no new files
        # or network connections can be opened)
        try:
            resource.setrlimit(resource.RLIMIT_NOFILE, (10, 10))
        except Exception:
            pass

        # Disable process creation (no fork)
        try:
            resource.setrlimit(resource.RLIMIT_NPROC, (0, 0))
        except Exception:
            pass

    captured_stdout = StringIO()
    captured_stderr = StringIO()

    sys.stdout = captured_stdout
    sys.stderr = captured_stderr

    builtins.__import__ = sandboxed_import

    try:
        exec(compiled_code, namespace)
    except Exception as e:
        sys.stdout = sys.__stdout__
        sys.stderr = sys.__stderr__
        result = {{
            "stdout": captured_stdout.getvalue(),
            "stderr": captured_stderr.getvalue() + "\\n" + traceback.format_exc(),
            "exit_code": 1,
            "execution_time_seconds": 0.0,
            "trace_frames": [],
            "error_message": f"Execution failed during initialization: {{str(e)}}"
        }}
        with original_open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f)
        sys.exit(0)

    trace_frames = []
    step_count = 0
    max_steps = {self.max_steps}

    def trace_lines(frame, event, arg):
        nonlocal step_count
        try:
            if event == 'line':
                step_count += 1
                if step_count > max_steps:
                    sys.settrace(None)
                    frame.f_trace = None
                    raise RuntimeError("Instruction limit exceeded")

                local_vars = {{k: v for k, v in frame.f_locals.items() if not k.startswith("__")}}
                trace_frames.append({{
                    "line_number": frame.f_lineno,
                    "local_variables": make_safe(local_vars),
                    "instruction": frame.f_code.co_name
                }})
        except BaseException as e:
            sys.settrace(None)
            frame.f_trace = None
            if isinstance(e, RuntimeError) and "Instruction limit exceeded" in str(e):
                raise
        return trace_lines

    def trace_calls(frame, event, arg):
        if event == 'call':
            if frame.f_code.co_filename == code_path:
                return trace_lines
        return None

    target_callable = None
    if class_name:
        clazz = namespace.get(class_name)
        if clazz:
            try:
                instance = clazz()
                target_callable = getattr(instance, func_name, None)
            except Exception:
                pass
    else:
        target_callable = namespace.get(func_name)

    if not target_callable:
        sys.stdout = sys.__stdout__
        sys.stderr = sys.__stderr__
        result = {{
            "stdout": captured_stdout.getvalue(),
            "stderr": captured_stderr.getvalue() + f"\\nTarget function '{{func_name}}' not found.",
            "exit_code": 1,
            "execution_time_seconds": 0.0,
            "trace_frames": [],
            "error_message": f"Target function '{{func_name}}' not found."
        }}
        with original_open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f)
        sys.exit(0)

    exit_code = 0
    error_message = None

    builtins.open = original_open

    start_time = time.perf_counter()
    sys.settrace(trace_calls)
    try:
        builtins.open = blocked_action
        return_val = target_callable(**inputs)
        sys.settrace(None)
        if trace_frames:
            trace_frames[-1]["local_variables"]["return_value"] = make_safe(return_val)
    except BaseException as e:
        sys.settrace(None)
        builtins.open = original_open
        exit_code = 1
        error_message = f"Runtime Exception: {{type(e).__name__}}: {{str(e)}}"
        captured_stderr.write(traceback.format_exc())
    finally:
        sys.settrace(None)
        builtins.open = original_open
        end_time = time.perf_counter()

    sys.stdout = sys.__stdout__
    sys.stderr = sys.__stderr__

    result = {{
        "stdout": captured_stdout.getvalue(),
        "stderr": captured_stderr.getvalue(),
        "exit_code": exit_code,
        "execution_time_seconds": end_time - start_time,
        "trace_frames": trace_frames,
        "error_message": error_message
    }}

    with original_open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f)

def main():
    try:
        run_sandbox()
    except BaseException:
        sys.stdout = sys.__stdout__
        sys.stderr = sys.__stderr__
        raise

if __name__ == "__main__":
    main()
"""
