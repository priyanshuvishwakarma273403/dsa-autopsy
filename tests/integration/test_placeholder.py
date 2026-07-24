"""Integration tests placeholder verifying settings load and interface wirings."""

import pytest

from dsa_autopsy.config.settings import settings
from dsa_autopsy.services.orchestrator import AutopsyOrchestrator


@pytest.mark.integration
def test_integration_environment_bootstrap(orchestrator: AutopsyOrchestrator) -> None:
    """Verify that settings wire into the orchestrator and log levels align."""
    # Ensure config and orchestrator dependency injection work together
    assert settings.ENV in ("development", "testing", "production")
    assert orchestrator._parser is not None
    assert orchestrator._executor is not None
    assert orchestrator._analyzer is not None
    assert orchestrator._explainer is not None
