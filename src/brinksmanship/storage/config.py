"""Storage configuration for Brinksmanship.

This module provides configuration for storage backends and factory functions
to create appropriate repository instances based on configuration.
"""

import os
from enum import Enum

from .file_repo import FileGameRecordRepository, FileScenarioRepository
from .repository import GameRecordRepository, ScenarioRepository
from .sqlite_repo import SQLiteGameRecordRepository, SQLiteScenarioRepository


class StorageBackend(Enum):
    """Available storage backends."""

    FILE = "file"
    SQLITE = "sqlite"


# Default configuration (can be overridden via environment variables)
DEFAULT_STORAGE_BACKEND = StorageBackend.FILE
DEFAULT_SCENARIOS_PATH = "scenarios"
DEFAULT_GAMES_PATH = "games"
DEFAULT_DATABASE_URI = "instance/brinksmanship.db"


def get_storage_backend() -> StorageBackend:
    """Get configured storage backend from environment.

    Returns:
        StorageBackend enum value
    """
    backend_str = os.environ.get("BRINKSMANSHIP_STORAGE_BACKEND", "file").lower()
    if backend_str == "sqlite":
        return StorageBackend.SQLITE
    return StorageBackend.FILE


def get_scenarios_path() -> str:
    """Get configured scenarios path from environment."""
    return os.environ.get("BRINKSMANSHIP_SCENARIOS_PATH", DEFAULT_SCENARIOS_PATH)


def get_games_path() -> str:
    """Get configured games path from environment."""
    return os.environ.get("BRINKSMANSHIP_GAMES_PATH", DEFAULT_GAMES_PATH)


def get_database_uri() -> str:
    """Get configured database URI from environment."""
    return os.environ.get("BRINKSMANSHIP_DATABASE_URI", DEFAULT_DATABASE_URI)


def get_scenario_repository(
    backend: StorageBackend | None = None,
) -> ScenarioRepository:
    """Factory function to create scenario repository.

    Args:
        backend: Storage backend to use. If None, uses environment config.

    Returns:
        ScenarioRepository instance
    """
    if backend is None:
        backend = get_storage_backend()

    if backend == StorageBackend.SQLITE:
        return SQLiteScenarioRepository(get_database_uri())
    return FileScenarioRepository(get_scenarios_path())


def get_game_repository(
    backend: StorageBackend | None = None,
) -> GameRecordRepository:
    """Factory function to create game record repository.

    Args:
        backend: Storage backend to use. If None, uses environment config.

    Returns:
        GameRecordRepository instance
    """
    if backend is None:
        backend = get_storage_backend()

    if backend == StorageBackend.SQLITE:
        return SQLiteGameRecordRepository(get_database_uri())
    return FileGameRecordRepository(get_games_path())
