"""Developer environment setup script for dsa-autopsy."""

import shutil
import subprocess
import sys
from pathlib import Path

# Color formatting helpers
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
RESET = "\033[0m"


def log_info(msg: str) -> None:
    print(f"{GREEN}[INFO]{RESET} {msg}")


def log_warn(msg: str) -> None:
    print(f"{YELLOW}[WARN]{RESET} {msg}")


def log_error(msg: str) -> None:
    print(f"{RED}[ERROR]{RESET} {msg}")


def check_python_version() -> None:
    """Ensure python version is 3.12+."""
    major, minor = sys.version_info.major, sys.version_info.minor
    if major < 3 or (major == 3 and minor < 12):
        log_error(f"Python 3.12+ is required. Found Python {major}.{minor}.")
        sys.exit(1)
    log_info(f"Python version check passed: Python {major}.{minor} detected.")


def install_dependencies() -> None:
    """Install package dependencies using uv if available, falling back to pip."""
    root_path = Path(__file__).resolve().parents[1]
    
    # Check if uv is installed
    uv_path = shutil.which("uv")
    if uv_path:
        log_info("Detected 'uv' package manager. Installing dependencies with uv...")
        try:
            subprocess.run([uv_path, "sync", "--all-extras"], cwd=root_path, check=True)
            log_info("Dependencies successfully installed via uv sync.")
            return
        except subprocess.CalledProcessError as e:
            log_warn(f"Failed to sync with uv: {e}. Falling back to standard virtualenv + pip.")
    
    # Fallback to pip
    log_info("Using standard 'pip' package manager...")
    venv_dir = root_path / ".venv"
    if not venv_dir.exists():
        log_info("Creating virtual environment in .venv...")
        subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], check=True)

    # Determine pip path inside venv
    if sys.platform == "win32":
        pip_path = venv_dir / "Scripts" / "pip.exe"
    else:
        pip_path = venv_dir / "bin" / "pip"

    log_info("Installing package with dev dependencies...")
    subprocess.run([str(pip_path), "install", "-e", ".[dev]"], check=True)
    log_info("Dependencies successfully installed via pip.")


def setup_pre_commit() -> None:
    """Install pre-commit git hooks."""
    root_path = Path(__file__).resolve().parents[1]
    pre_commit_path = shutil.which("pre-commit")
    
    # If not found globally, check in venv
    if not pre_commit_path:
        if sys.platform == "win32":
            pre_commit_path = str(root_path / ".venv" / "Scripts" / "pre-commit.exe")
        else:
            pre_commit_path = str(root_path / ".venv" / "bin" / "pre-commit")

    if Path(pre_commit_path).exists() or shutil.which("pre-commit"):
        log_info("Installing pre-commit git hooks...")
        try:
            subprocess.run([pre_commit_path, "install"], cwd=root_path, check=True)
            log_info("Pre-commit hooks configured.")
        except subprocess.CalledProcessError as e:
            log_warn(f"Failed to install pre-commit: {e}")
    else:
        log_warn("Pre-commit binary not found. Skipping hook installation.")


def run_test_suite() -> None:
    """Run pytest suite to verify setup."""
    root_path = Path(__file__).resolve().parents[1]
    pytest_path = shutil.which("pytest")
    
    if not pytest_path:
        if sys.platform == "win32":
            pytest_path = str(root_path / ".venv" / "Scripts" / "pytest.exe")
        else:
            pytest_path = str(root_path / ".venv" / "bin" / "pytest")

    if Path(pytest_path).exists() or shutil.which("pytest"):
        log_info("Running test suite to verify bootstrap correctness...")
        subprocess.run([pytest_path], cwd=root_path)
    else:
        log_warn("pytest binary not found. Skipping test execution.")


def main() -> None:
    """Orchestrate setup steps."""
    check_python_version()
    install_dependencies()
    setup_pre_commit()
    run_test_suite()
    log_info("Development setup complete!")


if __name__ == "__main__":
    main()
