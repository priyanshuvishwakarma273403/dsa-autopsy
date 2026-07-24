"""Production logging configuration supporting structured JSON and plain-text logging."""

import json
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from dsa_autopsy.config.settings import settings


class JSONFormatter(logging.Formatter):
    """Custom formatter to output logs in structured JSON format."""

    def format(self, record: logging.LogRecord) -> str:
        """Format the LogRecord as a JSON string.

        Args:
            record: The LogRecord instance to format.

        Returns:
            A string containing the serialized JSON log entry.
        """
        log_entry: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Include custom extra parameters if provided
        extra_fields = getattr(record, "extra_fields", None)
        if isinstance(extra_fields, dict):
            log_entry.update(extra_fields)

        # Include exception details if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry)


def setup_logging() -> None:
    """Initialize logging based on application settings.

    Sets up console logging and, optionally, file logging. Respects log levels
    and JSON formats configured in settings.
    """
    root_logger = logging.getLogger()

    # Avoid adding duplicate handlers if setup is called multiple times
    if root_logger.hasHandlers():
        return

    # Convert log level from settings string to logging constant
    level_map = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL,
    }
    level = level_map.get(settings.LOG_LEVEL, logging.INFO)
    root_logger.setLevel(level)

    # Determine Formatter
    formatter: logging.Formatter
    if settings.LOG_FORMAT == "json":
        formatter = JSONFormatter()
    else:
        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] %(name)s (%(filename)s:%(lineno)d) - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(level)
    root_logger.addHandler(console_handler)

    # File Handler (Optional)
    if settings.LOG_FILE_PATH:
        log_file = Path(settings.LOG_FILE_PATH)
        # Create directory structure if needed
        log_file.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(formatter)
        file_handler.setLevel(level)
        root_logger.addHandler(file_handler)


class StructuredLogger:
    """Wrapper logger that accepts contextual fields to log as structured JSON or plain text."""

    def __init__(self, name: str) -> None:
        """Initialize the structured logger.

        Args:
            name: Name of the logger, typically __name__.
        """
        self._logger = logging.getLogger(name)

    def _log(
        self,
        level: int,
        msg: str,
        extra: dict[str, Any] | None = None,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        if not self._logger.isEnabledFor(level):
            return

        # Inject extra parameters to be captured by the JSONFormatter
        kwargs["extra"] = {"extra_fields": extra} if extra else {}
        self._logger.log(level, msg, *args, **kwargs)

    def debug(
        self, msg: str, extra: dict[str, Any] | None = None, *args: Any, **kwargs: Any
    ) -> None:
        """Log a DEBUG level message."""
        self._log(logging.DEBUG, msg, extra, *args, **kwargs)

    def info(
        self, msg: str, extra: dict[str, Any] | None = None, *args: Any, **kwargs: Any
    ) -> None:
        """Log an INFO level message."""
        self._log(logging.INFO, msg, extra, *args, **kwargs)

    def warning(
        self, msg: str, extra: dict[str, Any] | None = None, *args: Any, **kwargs: Any
    ) -> None:
        """Log a WARNING level message."""
        self._log(logging.WARNING, msg, extra, *args, **kwargs)

    def error(
        self, msg: str, extra: dict[str, Any] | None = None, *args: Any, **kwargs: Any
    ) -> None:
        """Log an ERROR level message."""
        self._log(logging.ERROR, msg, extra, *args, **kwargs)

    def exception(
        self, msg: str, extra: dict[str, Any] | None = None, *args: Any, **kwargs: Any
    ) -> None:
        """Log an exception message at ERROR level with stack trace."""
        kwargs["exc_info"] = True
        self._log(logging.ERROR, msg, extra, *args, **kwargs)

    def critical(
        self, msg: str, extra: dict[str, Any] | None = None, *args: Any, **kwargs: Any
    ) -> None:
        """Log a CRITICAL level message."""
        self._log(logging.CRITICAL, msg, extra, *args, **kwargs)


def get_logger(name: str) -> StructuredLogger:
    """Retrieve a preconfigured structured logger instance.

    Args:
        name: Name of the logger.

    Returns:
        StructuredLogger: A wrapper around standard logging supporting key-value additions.
    """
    return StructuredLogger(name)
