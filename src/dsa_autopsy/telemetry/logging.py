"""Logging setup for the dsa-autopsy project."""

import logging
import sys

from dsa_autopsy.config.settings import settings


def setup_logging() -> None:
    """Initialize standard library logging configuration."""
    level = getattr(logging, settings.LOG_LEVEL, logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
        force=True,
    )
