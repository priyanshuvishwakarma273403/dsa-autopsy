"""Concrete implementations of sandbox drivers."""

import subprocess
import sys
from pathlib import Path

from dsa_autopsy.config.settings import settings
from dsa_autopsy.interfaces.sandbox_driver import BaseSandboxDriver


class SubprocessSandboxDriver(BaseSandboxDriver):
    """Driver that executes commands directly in local subprocesses."""

    def run(
        self,
        cmd: list[str],
        temp_dir: Path,
        timeout: float,
        cwd: Path | None = None,
    ) -> subprocess.CompletedProcess[str]:
        """Run the command in a local subprocess."""
        _ = temp_dir
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=timeout,
        )


class DockerSandboxDriver(BaseSandboxDriver):
    """Driver that executes commands inside a gVisor-sandboxed Docker container."""

    def __init__(self, image: str | None = None, memory_limit_mb: int = 100) -> None:
        """Initialize the Docker driver.

        Args:
            image: Docker image name. Defaults to settings.DOCKER_IMAGE or a default fallback.
            memory_limit_mb: Maximum memory allowed for the container. Defaults to 100MB.
        """
        # Read from settings if available, else default to a lightweight python image
        img = image or getattr(settings, "DOCKER_IMAGE", "python:3.12-slim")
        self.image: str = str(img) if img else "python:3.12-slim"
        self.memory_limit_mb = memory_limit_mb

    def _translate_path(self, p: str, temp_dir: Path) -> str:
        """Translate a host path under temp_dir to a container path under /workspace."""
        try:
            path_obj = Path(p).resolve()
            temp_dir_resolved = temp_dir.resolve()
            if path_obj == temp_dir_resolved:
                return "/workspace"
            if temp_dir_resolved in path_obj.parents:
                rel = path_obj.relative_to(temp_dir_resolved)
                return f"/workspace/{rel.as_posix()}"
        except Exception:
            pass

        # String fallback translation
        temp_dir_str = temp_dir.resolve().as_posix()
        p_posix = Path(p).as_posix()
        if p_posix.startswith(temp_dir_str):
            rel_str = p_posix[len(temp_dir_str) :].lstrip("/")
            return f"/workspace/{rel_str}"
        return p

    def run(
        self,
        cmd: list[str],
        temp_dir: Path,
        timeout: float,
        cwd: Path | None = None,
    ) -> subprocess.CompletedProcess[str]:
        """Run the command in a Docker container with gVisor and memory constraints."""
        temp_dir_posix = temp_dir.resolve().as_posix()

        # Build base docker run command
        docker_cmd = [
            "docker",
            "run",
            "--rm",
            "--runtime=runsc",
            "-m",
            f"{self.memory_limit_mb}m",
            "-v",
            f"{temp_dir_posix}:/workspace",
        ]

        # Set working directory inside container
        if cwd:
            container_cwd = self._translate_path(str(cwd), temp_dir)
            docker_cmd.extend(["-w", container_cwd])
        else:
            docker_cmd.extend(["-w", "/workspace"])

        docker_cmd.append(self.image)

        # Map executable: if running host sys.executable, use "python"
        cmd_for_container = []
        for idx, arg in enumerate(cmd):
            if idx == 0 and arg == sys.executable:
                cmd_for_container.append("python")
            else:
                cmd_for_container.append(self._translate_path(arg, temp_dir))

        docker_cmd.extend(cmd_for_container)

        # Run via subprocess
        return subprocess.run(
            docker_cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
