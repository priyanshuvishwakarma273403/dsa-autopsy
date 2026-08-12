"""Tests for sandbox drivers."""

import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from dsa_autopsy.services.sandbox_driver import DockerSandboxDriver, SubprocessSandboxDriver


def test_subprocess_sandbox_driver_run() -> None:
    """Test SubprocessSandboxDriver runs command locally."""
    driver = SubprocessSandboxDriver()
    temp_dir = Path("/dummy/temp")

    # Run a simple python inline code
    cmd = [sys.executable, "-c", "print('hello from subprocess')"]
    result = driver.run(cmd, temp_dir=temp_dir, timeout=2.0)

    assert result.returncode == 0
    assert "hello from subprocess" in result.stdout.strip()


def test_subprocess_sandbox_driver_timeout() -> None:
    """Test SubprocessSandboxDriver timeout handling."""
    driver = SubprocessSandboxDriver()
    temp_dir = Path("/dummy/temp")

    # Run python script that sleeps
    cmd = [sys.executable, "-c", "import time; time.sleep(10)"]
    with pytest.raises(subprocess.TimeoutExpired):
        driver.run(cmd, temp_dir=temp_dir, timeout=0.1)


def test_docker_sandbox_driver_translate_path() -> None:
    """Test path translation from host paths to container paths."""
    driver = DockerSandboxDriver()
    temp_dir = Path("/host/temp_dir").resolve()

    # Path under temp_dir
    p_inside = Path("/host/temp_dir/sub/file.py").resolve()
    assert driver._translate_path(str(p_inside), temp_dir) == "/workspace/sub/file.py"

    # Exact temp_dir
    assert driver._translate_path(str(temp_dir), temp_dir) == "/workspace"

    # Path outside temp_dir
    p_outside = Path("/other/path/file.py").resolve()
    assert driver._translate_path(str(p_outside), temp_dir) == str(p_outside)


@patch("subprocess.run")
def test_docker_sandbox_driver_run(mock_run: MagicMock) -> None:
    """Test DockerSandboxDriver builds and executes correct docker run command."""
    mock_run.return_value = subprocess.CompletedProcess(
        args=[], returncode=0, stdout="docker output", stderr=""
    )

    driver = DockerSandboxDriver(image="my-custom-image", memory_limit_mb=128)
    temp_dir = Path("/host/temp_dir").resolve()

    cmd = [
        sys.executable,
        str(temp_dir / "runner.py"),
        "arg1",
    ]

    result = driver.run(cmd, temp_dir=temp_dir, timeout=5.0)

    assert result.stdout == "docker output"

    # Check that subprocess.run was called with correct docker run arguments
    mock_run.assert_called_once()
    called_args = mock_run.call_args[0][0]

    assert called_args[0] == "docker"
    assert "run" in called_args
    assert "--runtime=runsc" in called_args
    assert "-m" in called_args
    assert "128m" in called_args
    assert "-v" in called_args
    assert f"{temp_dir.as_posix()}:/workspace" in called_args
    assert "-w" in called_args
    assert "/workspace" in called_args
    assert "my-custom-image" in called_args

    # Verify command mapping: sys.executable replaced by python, and paths mapped
    assert "python" in called_args
    assert "/workspace/runner.py" in called_args
    assert "arg1" in called_args


@patch("subprocess.run")
def test_docker_sandbox_driver_run_with_cwd(mock_run: MagicMock) -> None:
    """Test DockerSandboxDriver running with a custom working directory."""
    mock_run.return_value = subprocess.CompletedProcess(
        args=[], returncode=0, stdout="ok", stderr=""
    )

    driver = DockerSandboxDriver()
    temp_dir = Path("/host/temp_dir").resolve()
    cwd_dir = Path("/host/temp_dir/subdir").resolve()

    driver.run(["python", "script.py"], temp_dir=temp_dir, timeout=5.0, cwd=cwd_dir)

    mock_run.assert_called_once()
    called_args = mock_run.call_args[0][0]

    # Check that container working directory is set to translated cwd
    w_index = called_args.index("-w")
    assert called_args[w_index + 1] == "/workspace/subdir"
