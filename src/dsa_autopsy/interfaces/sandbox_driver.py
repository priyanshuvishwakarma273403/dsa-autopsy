"""Interface definition for sandbox drivers."""

import subprocess
from abc import ABC, abstractmethod
from pathlib import Path


class BaseSandboxDriver(ABC):
    """Abstract base class representing a sandbox execution environment driver."""

    @abstractmethod
    def run(
        self,
        cmd: list[str],
        temp_dir: Path,
        timeout: float,
        cwd: Path | None = None,
    ) -> subprocess.CompletedProcess[str]:
        """Run a command within the sandboxed environment.

        Args:
            cmd: Command and its arguments as a list of strings.
            temp_dir: Host temporary directory mounted or used for execution.
            timeout: Timeout in seconds for the command.
            cwd: Optional working directory for the command.

        Returns:
            CompletedProcess containing returncode, stdout, and stderr.
        """
        pass
