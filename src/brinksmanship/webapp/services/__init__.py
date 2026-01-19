"""Services for the webapp."""

from .game_service import get_game_service
from .engine_adapter import RealGameEngine

__all__ = ["get_game_service", "RealGameEngine"]
