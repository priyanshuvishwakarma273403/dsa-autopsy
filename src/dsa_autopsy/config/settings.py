"""Central configuration management using Pydantic Settings."""

from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings, loaded from environment variables and optionally a .env file."""

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
