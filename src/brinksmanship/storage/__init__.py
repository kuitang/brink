"""Storage module for Brinksmanship.

This module provides repository interfaces and implementations for
persisting scenarios and game records.

Usage:
    from brinksmanship.storage import get_scenario_repository, get_game_repository

    # Get repository using configured backend (from environment)
    scenarios = get_scenario_repository()
    games = get_game_repository()

    # Or specify backend explicitly
    from brinksmanship.storage import StorageBackend
    scenarios = get_scenario_repository(StorageBackend.SQLITE)

Configuration via environment variables:
    BRINKSMANSHIP_STORAGE_BACKEND: "file" or "sqlite" (default: "file")
    BRINKSMANSHIP_SCENARIOS_PATH: Path to scenarios directory (default: "scenarios")
    BRINKSMANSHIP_GAMES_PATH: Path to games directory (default: "games")
    BRINKSMANSHIP_DATABASE_URI: SQLite database path (default: "instance/brinksmanship.db")
"""

from .config import (
    StorageBackend,
    get_database_uri,
    get_game_repository,
    get_games_path,
    get_scenario_repository,
    get_scenarios_path,
    get_storage_backend,
)
from .file_repo import FileGameRecordRepository, FileScenarioRepository
from .repository import GameRecordRepository, ScenarioRepository
from .sqlite_repo import SQLiteGameRecordRepository, SQLiteScenarioRepository

__all__ = [
    # Abstract interfaces
    "ScenarioRepository",
    "GameRecordRepository",
    # File implementations
    "FileScenarioRepository",
    "FileGameRecordRepository",
    # SQLite implementations
    "SQLiteScenarioRepository",
    "SQLiteGameRecordRepository",
    # Configuration
    "StorageBackend",
    "get_storage_backend",
    "get_scenarios_path",
    "get_games_path",
    "get_database_uri",
    # Factory functions
    "get_scenario_repository",
    "get_game_repository",
]
