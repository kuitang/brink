"""Services for the webapp."""

from .engine_adapter import RealGameEngine
from .game_service import get_game_service

__all__ = ["get_game_service", "RealGameEngine"]
