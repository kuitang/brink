"""Services for the webapp."""

from .game_service import get_game_service
from .mock_engine import MockGameEngine

__all__ = ["get_game_service", "MockGameEngine"]
