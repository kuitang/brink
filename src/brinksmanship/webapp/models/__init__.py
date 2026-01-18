"""SQLAlchemy models for the webapp."""

from .game_record import GameRecord
from .user import User

__all__ = ["User", "GameRecord"]
