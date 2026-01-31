"""Shared pytest fixtures and markers for all tests."""

import pytest


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "llm_integration: marks tests requiring LLM API calls"
    )
    config.addinivalue_line(
        "markers", "e2e: marks end-to-end Playwright tests"
    )
    config.addinivalue_line(
        "markers", "webapp: marks webapp-specific tests"
    )


@pytest.fixture
def sample_player_state():
    """Provide a default player state for testing."""
    from brinksmanship.models.state import PlayerState
    return PlayerState()


@pytest.fixture
def sample_game_state():
    """Provide a default game state for testing."""
    from brinksmanship.models.state import GameState
    return GameState()
