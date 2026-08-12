"""Concrete implementation of the sandboxed execution engine."""

import json
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from dsa_autopsy.interfaces.executor import BaseExecutor
from dsa_autopsy.models.domain import ExecutionResult, SolutionTestCase, SourceCode, TraceFrame
from dsa_autopsy.services.ast_parser import ASTParser


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


def to_cpp_type_and_val(val: Any) -> tuple[str, str]:
    """Convert Python value to C++ type and value string."""
    if isinstance(val, bool):
        return "bool", "true" if val else "false"
    if isinstance(val, int):
        return "int", str(val)
    if isinstance(val, float):
        return "double", str(val)
    if isinstance(val, str):
        return "std::string", f'"{val}"'
    if isinstance(val, list):
        if not val:
            return "std::vector<int>", "{}"
        elem_type, _ = to_cpp_type_and_val(val[0])
        elems = ", ".join(to_cpp_type_and_val(x)[1] for x in val)
        return f"std::vector<{elem_type}>", f"{{{elems}}}"
    return "auto", str(val)


def to_java_type_and_val(val: Any) -> tuple[str, str]:
    """Convert Python value to Java type and value string."""
    if isinstance(val, bool):
        return "boolean", "true" if val else "false"
    if isinstance(val, int):
        return "int", str(val)
    if isinstance(val, float):
        return "double", str(val)
    if isinstance(val, str):
        return "String", f'"{val}"'
    if isinstance(val, list):
        if not val:
            return "int[]", "new int[]{}"
        elem_type, _ = to_java_type_and_val(val[0])
        elems = ", ".join(to_java_type_and_val(x)[1] for x in val)
        return f"{elem_type}[]", f"new {elem_type}[]{{{elems}}}"
    return "Object", str(val)


def _parse_return_value(stdout: str) -> Any:
    """Parse return value from stdout RETURN_VALUE line."""
    if not stdout:
        return None
    m = re.search(r"RETURN_VALUE:\s*(.+)", stdout)
    if m:
        val_str = m.group(1).strip()
        if val_str == "void":
            return None
        if val_str == "true":
            return True
        if val_str == "false":
            return False
        if val_str == "null":
            return None
        try:
            if "." in val_str:
                return float(val_str)
            return int(val_str)
        except ValueError:
            pass
        if val_str.startswith("[") and val_str.endswith("]"):
            try:
                import json

                return json.loads(val_str)
            except Exception:
                pass
        return val_str
    return None


class SandboxExecutor(BaseExecutor):
    """Executes Python source code in a restricted subprocess sandbox with trace collection."""

    def __init__(self, timeout_secs: float = 5.0, max_steps: int = 10000) -> None:
        """Initialize the executor with timeout and instruction step limit constraints."""
        self.timeout_secs = timeout_secs
        self.max_steps = max_steps

    def execute(self, code: SourceCode, test_case: SolutionTestCase) -> ExecutionResult:
        """Run the solution inside a sandboxed process with trace capturing."""
        lang = code.language.lower()
        if lang in ["python", "py"]:
            return self._execute_python(code, test_case)
        if lang in ["cpp", "c++"]:
            return self._execute_cpp(code, test_case)
        if lang == "java":
            return self._execute_java(code, test_case)
        return ExecutionResult(
            test_case_id=test_case.id,
            stdout="",
            stderr=f"Unsupported language: {code.language}",
            exit_code=1,
            execution_time_seconds=0.0,
            matches_expected=False,
            trace_frames=[],
            error_message=f"Unsupported language: {code.language}",
        )

    def _execute_python(self, code: SourceCode, test_case: SolutionTestCase) -> ExecutionResult:
        """Run the solution inside a sandboxed python process with trace capturing."""
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
                            matches_expected=False,
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
                            matches_expected=False,
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
                        matches_expected=False,
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
                    matches_expected=False,
                    trace_frames=[],
                    error_message=(
                        f"TimeoutExpired: Execution exceeded limit of {self.timeout_secs}s"
                    ),
                )

    def _execute_cpp(self, code: SourceCode, test_case: SolutionTestCase) -> ExecutionResult:
        """Run the C++ solution inside a sandboxed process with GDB tracing."""
        parser = ASTParser()
        try:
            metadata = parser.parse(code)
            func_name = next(iter(metadata.keys()), "main")
        except Exception:
            func_name = "main"

        has_solution_class = "class Solution" in code.content

        # Generate inputs block
        inputs_decl = []
        args_list = []
        for name, val in test_case.inputs.items():
            cpp_type, cpp_val = to_cpp_type_and_val(val)
            inputs_decl.append(f"{cpp_type} {name} = {cpp_val};")
            args_list.append(name)
        inputs_block = "\n    ".join(inputs_decl)
        args_str = ", ".join(args_list)

        is_void = re.search(r"\bvoid\s+" + re.escape(func_name), code.content) is not None
        if has_solution_class:
            instantiation = "Solution solver;"
            if is_void:
                call = (
                    f"solver.{func_name}({args_str});\n"
                    f'    std::cout << "RETURN_VALUE: void" << std::endl;'
                )
            else:
                call = (
                    f"auto result = solver.{func_name}({args_str});\n"
                    f'    std::cout << "RETURN_VALUE: ";\n'
                    f"    print_value(result);\n"
                    f"    std::cout << std::endl;"
                )
        else:
            instantiation = ""
            if is_void:
                call = (
                    f"{func_name}({args_str});\n"
                    f'    std::cout << "RETURN_VALUE: void" << std::endl;'
                )
            else:
                call = (
                    f"auto result = {func_name}({args_str});\n"
                    f'    std::cout << "RETURN_VALUE: ";\n'
                    f"    print_value(result);\n"
                    f"    std::cout << std::endl;"
                )

        call_block = f"{instantiation}\n    {call}"

        wrapper_content = f"""#include <iostream>
#include <vector>
#include <string>

template<typename T>
void print_value(const T& val) {{
    std::cout << val;
}}

template<typename T>
void print_value(const std::vector<T>& val) {{
    std::cout << "[";
    for (size_t i = 0; i < val.size(); ++i) {{
        if (i > 0) std::cout << ", ";
        print_value(val[i]);
    }}
    std::cout << "]";
}}

#include "solution.cpp"

int main() {{
    {inputs_block}
    {call_block}
    return 0;
}}
"""

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_dir_path = Path(temp_dir)
            code_file = temp_dir_path / "solution.cpp"
            wrapper_file = temp_dir_path / "main.cpp"
            executable = temp_dir_path / "solution"
            trace_script = temp_dir_path / "trace.py"
            output_file = temp_dir_path / "output.json"

            code_file.write_text(code.content, encoding="utf-8")
            wrapper_file.write_text(wrapper_content, encoding="utf-8")

            # Compile code using GCC/G++ with debug symbols
            compile_proc = subprocess.run(
                ["g++", "-g", "-O0", str(wrapper_file), "-o", str(executable)],
                capture_output=True,
                text=True,
                timeout=30.0,
            )

            if compile_proc.returncode != 0:
                return ExecutionResult(
                    test_case_id=test_case.id,
                    stdout="",
                    stderr=compile_proc.stderr,
                    exit_code=compile_proc.returncode,
                    execution_time_seconds=0.0,
                    matches_expected=False,
                    trace_frames=[],
                    error_message=f"Compilation failed: {compile_proc.stderr}",
                )

            # Generate GDB script
            gdb_script = f"""import gdb
import json

try:
    gdb.execute("break Solution::{func_name}")
except Exception:
    try:
        gdb.execute("break {func_name}")
    except Exception:
        gdb.execute("break main")

gdb.execute("run")

trace_frames = []
steps = 0
max_steps = {self.max_steps}

while steps < max_steps:
    frame = gdb.selected_frame()
    if not frame:
        break
    sal = frame.find_sal()
    if sal and sal.symtab and sal.symtab.filename.endswith("solution.cpp"):
        line = sal.line
        local_vars = {{}}
        try:
            block = frame.block()
            while block:
                for symbol in block:
                    if symbol.is_argument or symbol.is_variable:
                        name = symbol.name
                        try:
                            val = symbol.value(frame)
                            if val.type.code == gdb.TYPE_CODE_INT:
                                local_vars[name] = int(val)
                            elif val.type.code == gdb.TYPE_CODE_FLT:
                                local_vars[name] = float(val)
                            elif val.type.code == gdb.TYPE_CODE_BOOL:
                                local_vars[name] = bool(val)
                            else:
                                local_vars[name] = str(val)
                        except Exception:
                            pass
                if block.function:
                    break
                block = block.outer
        except Exception:
            pass

        trace_frames.append({{
            "line_number": line,
            "local_variables": local_vars,
            "instruction": frame.name() or "{func_name}"
        }})
    try:
        gdb.execute("step", to_string=True)
        steps += 1
    except Exception:
        break

with open(r"{output_file}", "w") as f:
    json.dump({{"trace_frames": trace_frames}}, f)
"""
            trace_script.write_text(gdb_script, encoding="utf-8")

            # Run GDB
            start_time = time.perf_counter()
            try:
                proc = subprocess.run(
                    ["gdb", "-batch", "-q", "-x", str(trace_script), "--args", str(executable)],
                    capture_output=True,
                    text=True,
                    timeout=self.timeout_secs,
                )
                end_time = time.perf_counter()
                elapsed = end_time - start_time

                trace_frames = []
                if output_file.exists():
                    try:
                        with output_file.open(encoding="utf-8") as f:
                            res_data = json.load(f)
                        for frame_data in res_data.get("trace_frames", []):
                            trace_frames.append(
                                TraceFrame(
                                    line_number=frame_data["line_number"],
                                    local_variables=frame_data["local_variables"],
                                    instruction=frame_data["instruction"],
                                )
                            )
                    except Exception:
                        pass

                actual_output = _parse_return_value(proc.stdout)
                if trace_frames:
                    trace_frames[-1].local_variables["return_value"] = actual_output

                error_msg = None
                if proc.returncode != 0:
                    error_msg = f"Runtime Exception: {proc.stderr or proc.stdout}"

                return ExecutionResult(
                    test_case_id=test_case.id,
                    stdout=proc.stdout,
                    stderr=proc.stderr,
                    exit_code=proc.returncode,
                    execution_time_seconds=elapsed,
                    matches_expected=False,
                    trace_frames=trace_frames,
                    error_message=error_msg,
                )
            except Exception:
                start_time = time.perf_counter()
                proc = subprocess.run(
                    [str(executable)],
                    capture_output=True,
                    text=True,
                    timeout=self.timeout_secs,
                )
                elapsed = time.perf_counter() - start_time
                actual_output = _parse_return_value(proc.stdout)

                trace_frames = [
                    TraceFrame(
                        line_number=1,
                        local_variables={"return_value": actual_output},
                        instruction="main",
                    )
                ]

                error_msg = None
                if proc.returncode != 0:
                    error_msg = f"Runtime Exception: {proc.stderr or proc.stdout}"

                return ExecutionResult(
                    test_case_id=test_case.id,
                    stdout=proc.stdout,
                    stderr=proc.stderr,
                    exit_code=proc.returncode,
                    execution_time_seconds=elapsed,
                    matches_expected=False,
                    trace_frames=trace_frames,
                    error_message=error_msg,
                )

    def _execute_java(self, code: SourceCode, test_case: SolutionTestCase) -> ExecutionResult:
        """Run the Java solution inside a sandboxed process using JDI agent tracing."""
        parser = ASTParser()
        try:
            metadata = parser.parse(code)
            func_name = next(iter(metadata.keys()), "main")
        except Exception:
            func_name = "main"

        class_match = re.search(r"\bclass\s+(\w+)", code.content)
        class_name = class_match.group(1) if class_match else "Solution"

        # Generate inputs block
        inputs_decl = []
        args_list = []
        for name, val in test_case.inputs.items():
            java_type, java_val = to_java_type_and_val(val)
            inputs_decl.append(f"{java_type} {name} = {java_val};")
            args_list.append(name)
        inputs_block = "\n        ".join(inputs_decl)
        args_str = ", ".join(args_list)

        is_void = re.search(r"\bvoid\s+" + re.escape(func_name), code.content) is not None
        if is_void:
            call = (
                f"solver.{func_name}({args_str});\n"
                f'        System.out.print("RETURN_VALUE: void");'
            )
        else:
            call = (
                f"var result = solver.{func_name}({args_str});\n"
                f'        System.out.print("RETURN_VALUE: ");\n'
                f"        printValue(result);"
            )
        call_block = f"{call}\n        System.out.println();"

        runner_content = f"""import java.util.*;

public class SolutionRunner {{
    public static void main(String[] args) throws Exception {{
        {inputs_block}
        {class_name} solver = new {class_name}();
        {call_block}
    }}

    private static void printValue(Object val) {{
        if (val == null) {{
            System.out.print("null");
        }} else if (val instanceof int[]) {{
            System.out.print(Arrays.toString((int[]) val));
        }} else if (val instanceof double[]) {{
            System.out.print(Arrays.toString((double[]) val));
        }} else if (val instanceof boolean[]) {{
            System.out.print(Arrays.toString((boolean[]) val));
        }} else if (val instanceof Object[]) {{
            System.out.print(Arrays.deepToString((Object[]) val));
        }} else {{
            System.out.print(val);
        }}
    }}
}}
"""

        jdi_tracer_content = """import com.sun.jdi.*;
import com.sun.jdi.connect.*;
import com.sun.jdi.event.*;
import com.sun.jdi.request.*;
import java.io.*;
import java.util.*;

public class JdiTracer {
    public static void main(String[] args) throws Exception {
        if (args.length < 5) {
            System.err.println(
                "Usage: JdiTracer <className> <methodName> "
                + "<inputsPath> <outputPath> <runnerClassName>"
            );
            System.exit(1);
        }
        String className = args[0];
        String methodName = args[1];
        String inputsPath = args[2];
        String outputPath = args[3];
        String runnerClassName = args[4];

        VirtualMachineManager vmm = Bootstrap.virtualMachineManager();
        LaunchingConnector connector = null;
        for (LaunchingConnector lc : vmm.launchingConnectors()) {
            if (lc.name().equals("com.sun.jdi.CommandLineLaunch")) {
                connector = lc;
                break;
            }
        }
        if (connector == null) {
            throw new RuntimeException("CommandLineLaunch connector not found");
        }

        Map<String, Connector.Argument> arguments = connector.defaultArguments();
        arguments.get("main").setValue(
            runnerClassName + " " + className + " " + methodName
            + " " + inputsPath + " " + outputPath
        );
        arguments.get("options").setValue("-cp .");

        VirtualMachine vm = connector.launch(arguments);
        EventRequestManager erm = vm.eventRequestManager();

        ClassPrepareRequest cpr = erm.createClassPrepareRequest();
        cpr.addClassFilter(className);
        cpr.enable();

        EventQueue queue = vm.eventQueue();
        boolean run = true;
        List<Map<String, Object>> traceFrames = new ArrayList<>();

        while (run) {
            EventSet eventSet = queue.remove();
            for (Event event : eventSet) {
                if (event instanceof VMDisconnectEvent || event instanceof VMDeathEvent) {
                    run = false;
                } else if (event instanceof ClassPrepareEvent) {
                    ClassPrepareEvent cpe = (ClassPrepareEvent) event;
                    ReferenceType refType = cpe.referenceType();
                    for (Method method : refType.methodsByName(methodName)) {
                        BreakpointRequest bpr = erm.createBreakpointRequest(method.location());
                        bpr.enable();
                    }
                } else if (event instanceof BreakpointEvent) {
                    BreakpointEvent be = (BreakpointEvent) event;
                    ThreadReference thread = be.thread();
                    StepRequest sr = erm.createStepRequest(
                        thread, StepRequest.STEP_LINE, StepRequest.STEP_INTO
                    );
                    sr.addClassFilter(className);
                    sr.enable();
                } else if (event instanceof StepEvent) {
                    StepEvent se = (StepEvent) event;
                    Location loc = se.location();
                    if (loc.declaringType().name().equals(className)) {
                        Map<String, Object> frame = new HashMap<>();
                        frame.put("line_number", loc.lineNumber());
                        frame.put("instruction", loc.method().name());

                        Map<String, Object> localVars = new HashMap<>();
                        try {
                            StackFrame sf = se.thread().frame(0);
                            for (LocalVariable var : sf.visibleVariables()) {
                                Value val = sf.getValue(var);
                                localVars.put(var.name(), getJavaValue(val));
                            }
                        } catch (Exception e) {
                            // ignore
                        }
                        frame.put("local_variables", localVars);
                        traceFrames.add(frame);
                    }
                }
            }
            eventSet.resume();
        }

        writeJson(traceFrames, outputPath);
    }

    private static Object getJavaValue(Value val) {
        if (val == null) return null;
        if (val instanceof BooleanValue) return ((BooleanValue) val).value();
        if (val instanceof IntegerValue) return ((IntegerValue) val).value();
        if (val instanceof LongValue) return ((LongValue) val).value();
        if (val instanceof FloatValue) return ((FloatValue) val).value();
        if (val instanceof DoubleValue) return ((DoubleValue) val).value();
        if (val instanceof StringReference) return ((StringReference) val).value();
        if (val instanceof ArrayReference) {
            ArrayReference arr = (ArrayReference) val;
            List<Object> list = new ArrayList<>();
            for (Value v : arr.getValues()) {
                list.add(getJavaValue(v));
            }
            return list;
        }
        return val.toString();
    }

    private static void writeJson(List<Map<String, Object>> frames, String path) throws Exception {
        StringBuilder sb = new StringBuilder();
        sb.append("{\\"trace_frames\\": [");
        for (int i = 0; i < frames.size(); i++) {
            if (i > 0) sb.append(",");
            Map<String, Object> f = frames[i];
            sb.append("{{");
            sb.append("\\"line_number\\":").append(f.get("line_number")).append(",");
            sb.append("\\"instruction\\":\\"").append(f.get("instruction")).append("\\",");
            sb.append("\\"local_variables\\":{{");
            Map<String, Object> vars = (Map<String, Object>) f.get("local_variables");
            int j = 0;
            for (Map.Entry<String, Object> entry : vars.entrySet()) {
                if (j > 0) sb.append(",");
                sb.append("\\"").append(entry.getKey()).append("\\":").append(valueToJson(entry.getValue()));
                j++;
            }
            sb.append("}}");
            sb.append("}}");
        }
        sb.append("]}");
        try (FileWriter fw = new FileWriter(path)) {
            fw.write(sb.toString());
        }
    }

    private static String valueToJson(Object val) {
        if (val == null) return "null";
        if (val instanceof String) return "\\"" + val + "\\"";
        if (val instanceof Boolean) return val.toString();
        if (val instanceof Number) return val.toString();
        if (val instanceof List) {
            StringBuilder sb = new StringBuilder("[");
            List<?> l = (List<?>) val;
            for (int i = 0; i < l.size(); i++) {
                if (i > 0) sb.append(",");
                sb.append(valueToJson(l.get(i)));
            }
            sb.append("]");
            return sb.toString();
        }
        return "\\"" + val.toString() + "\\"";
    }
}
"""

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_dir_path = Path(temp_dir)
            code_file = temp_dir_path / f"{class_name}.java"
            runner_file = temp_dir_path / "SolutionRunner.java"
            tracer_file = temp_dir_path / "JdiTracer.java"
            inputs_file = temp_dir_path / "inputs.txt"
            output_file = temp_dir_path / "output.json"

            code_file.write_text(code.content, encoding="utf-8")
            runner_file.write_text(runner_content, encoding="utf-8")
            tracer_file.write_text(jdi_tracer_content, encoding="utf-8")
            inputs_file.write_text("", encoding="utf-8")

            # Compile files
            compile_proc = subprocess.run(
                ["javac", "-g", str(code_file), str(runner_file), str(tracer_file)],
                capture_output=True,
                text=True,
                cwd=temp_dir,
                timeout=30.0,
            )

            if compile_proc.returncode != 0:
                return ExecutionResult(
                    test_case_id=test_case.id,
                    stdout="",
                    stderr=compile_proc.stderr,
                    exit_code=compile_proc.returncode,
                    execution_time_seconds=0.0,
                    matches_expected=False,
                    trace_frames=[],
                    error_message=f"Compilation failed: {compile_proc.stderr}",
                )

            # Run JDI Tracer
            start_time = time.perf_counter()
            try:
                proc = subprocess.run(
                    [
                        "java",
                        "-cp",
                        ".",
                        "JdiTracer",
                        class_name,
                        func_name,
                        "inputs.txt",
                        "output.json",
                        "SolutionRunner",
                    ],
                    capture_output=True,
                    text=True,
                    cwd=temp_dir,
                    timeout=self.timeout_secs,
                )
                end_time = time.perf_counter()
                elapsed = end_time - start_time

                trace_frames = []
                if output_file.exists():
                    try:
                        with output_file.open(encoding="utf-8") as f:
                            res_data = json.load(f)
                        for frame_data in res_data.get("trace_frames", []):
                            trace_frames.append(
                                TraceFrame(
                                    line_number=frame_data["line_number"],
                                    local_variables=frame_data["local_variables"],
                                    instruction=frame_data["instruction"],
                                )
                            )
                    except Exception:
                        pass

                actual_output = _parse_return_value(proc.stdout)
                if trace_frames:
                    trace_frames[-1].local_variables["return_value"] = actual_output

                error_msg = None
                if proc.returncode != 0:
                    error_msg = f"Runtime Exception: {proc.stderr or proc.stdout}"

                return ExecutionResult(
                    test_case_id=test_case.id,
                    stdout=proc.stdout,
                    stderr=proc.stderr,
                    exit_code=proc.returncode,
                    execution_time_seconds=elapsed,
                    matches_expected=False,
                    trace_frames=trace_frames,
                    error_message=error_msg,
                )
            except Exception:
                start_time = time.perf_counter()
                proc = subprocess.run(
                    ["java", "-cp", ".", "SolutionRunner"],
                    capture_output=True,
                    text=True,
                    cwd=temp_dir,
                    timeout=self.timeout_secs,
                )
                elapsed = time.perf_counter() - start_time
                actual_output = _parse_return_value(proc.stdout)

                trace_frames = [
                    TraceFrame(
                        line_number=1,
                        local_variables={"return_value": actual_output},
                        instruction="main",
                    )
                ]

                error_msg = None
                if proc.returncode != 0:
                    error_msg = f"Runtime Exception: {proc.stderr or proc.stdout}"

                return ExecutionResult(
                    test_case_id=test_case.id,
                    stdout=proc.stdout,
                    stderr=proc.stderr,
                    exit_code=proc.returncode,
                    execution_time_seconds=elapsed,
                    matches_expected=False,
                    trace_frames=trace_frames,
                    error_message=error_msg,
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
