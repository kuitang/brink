"""Game service - abstraction over mock/real engine."""

from typing import Any

from flask import current_app

from .mock_engine import MockGameEngine

_mock_engine = MockGameEngine()


def get_game_service() -> MockGameEngine:
    """Get the game service (mock or real based on config)."""
    # For now, always return mock engine
    # When real engine is ready, check current_app.config["USE_MOCK_ENGINE"]
    return _mock_engine
