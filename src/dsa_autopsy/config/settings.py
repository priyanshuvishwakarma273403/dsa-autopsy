"""Central configuration management using Pydantic Settings."""

import tomllib
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


def load_sandbox_mode_from_toml() -> Literal["SubprocessSandbox", "ContainerizedSandbox"]:
    """Load sandbox mode from pyproject.toml if specified."""
    try:
        pyproject_path = Path("pyproject.toml")
        if pyproject_path.exists():
            with pyproject_path.open("rb") as f:
                data = tomllib.load(f)
            val = data.get("tool", {}).get("dsa_autopsy", {}).get("sandbox_mode")
            if val == "ContainerizedSandbox":
                return "ContainerizedSandbox"
    except Exception:
        pass
    return "SubprocessSandbox"


class Settings(BaseSettings):
    """Application settings, loaded from environment variables and optionally a .env file."""

    # Sandbox configuration settings
    SANDBOX_MODE: Literal["SubprocessSandbox", "ContainerizedSandbox"] = Field(
        default_factory=load_sandbox_mode_from_toml,
        description="The sandbox execution mode: SubprocessSandbox or ContainerizedSandbox.",
    )

    DOCKER_IMAGE: str = Field(
        default="python:3.12-slim",
        description="Docker image to use for the containerized sandbox.",
    )

    # Application Environment
    ENV: Literal["development", "testing", "production"] = Field(
        default="development",
        description="The environment the application is running in.",
    )

    # Logging Configuration
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO",
        description="Logging level for console and file loggers.",
    )

    LOG_FORMAT: Literal["text", "json"] = Field(
        default="text",
        description="Format of log outputs: plain text or structured JSON.",
    )

    LOG_FILE_PATH: str | None = Field(
        default=None,
        description="Optional file path to store logs.",
    )

    # Future AST / Tree-sitter Parser settings
    PARSER_ENGINE: Literal["native_ast", "tree_sitter"] = Field(
        default="native_ast",
        description="Underlying parser engine to use for analyzing code structure.",
    )

    # Future Sandbox Execution Timeout
    EXECUTION_TIMEOUT_SECS: int = Field(
        default=5,
        description="Timeout in seconds for running user solution test cases.",
    )

    # Future AI Explainer settings
    AI_PROVIDER: Literal["openai", "anthropic", "gemini", "mock"] = Field(
        default="mock",
        description="AI model provider for generating failure explanations.",
    )

    AI_API_KEY: SecretStr | None = Field(
        default=None,
        description="Secret API key for the AI provider.",
    )

    AI_MODEL_NAME: str = Field(
        default="gpt-4o-mini",
        description="Model name to target for analysis.",
    )

    # Pydantic Settings Configuration
    model_config = SettingsConfigDict(
        env_prefix="DSA_AUTOPSY_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


# Global instance of Settings
settings = Settings()
