"""Abstract repository interfaces for Brinksmanship storage.

This module defines the abstract base classes for scenario and game record
repositories. Both file-based (JSON) and SQLite backends implement these
interfaces, allowing the CLI and webapp to use storage without knowing
which backend is active.
"""

from abc import ABC, abstractmethod
from typing import Optional


class ScenarioRepository(ABC):
    """Abstract base class for scenario storage."""

    @abstractmethod
    def list_scenarios(self) -> list[dict]:
        """Return metadata for all available scenarios.

        Returns:
            List of dicts containing: {id, name, setting, max_turns}
        """
        pass

    @abstractmethod
    def get_scenario(self, scenario_id: str) -> Optional[dict]:
        """Load complete scenario by ID.

        Args:
            scenario_id: Unique identifier for the scenario

        Returns:
            Complete scenario dict, or None if not found
        """
        pass

    @abstractmethod
    def get_scenario_by_name(self, name: str) -> Optional[dict]:
        """Load scenario by name (case-insensitive search).

        Args:
            name: Scenario name to search for

        Returns:
            Complete scenario dict, or None if not found
        """
        pass

    @abstractmethod
    def save_scenario(self, scenario: dict) -> str:
        """Save scenario, return ID.

        Scenario must have 'name' field. For file backend, ID is
        slugified name (e.g., 'Cuban Missile Crisis' -> 'cuban-missile-crisis').
        For SQLite, ID is auto-generated but name is indexed.

        Args:
            scenario: Complete scenario dict with required 'name' field

        Returns:
            ID of saved scenario

        Raises:
            ValueError: If scenario lacks required 'name' field
        """
        pass

    @abstractmethod
    def delete_scenario(self, scenario_id: str) -> bool:
        """Delete scenario.

        Args:
            scenario_id: ID of scenario to delete

        Returns:
            True if deleted, False if not found
        """
        pass


class GameRecordRepository(ABC):
    """Abstract base class for game record storage."""

    @abstractmethod
    def save_game(self, game_id: str, state: dict) -> None:
        """Persist complete game state.

        Args:
            game_id: Unique identifier for the game
            state: Complete game state dict
        """
        pass

    @abstractmethod
    def load_game(self, game_id: str) -> Optional[dict]:
        """Load game state by ID.

        Args:
            game_id: ID of game to load

        Returns:
            Game state dict, or None if not found
        """
        pass

    @abstractmethod
    def list_games(self, user_id: Optional[int] = None) -> list[dict]:
        """List games, optionally filtered by user.

        Args:
            user_id: Optional user ID to filter by

        Returns:
            List of game metadata dicts
        """
        pass

    @abstractmethod
    def delete_game(self, game_id: str) -> bool:
        """Delete game record.

        Args:
            game_id: ID of game to delete

        Returns:
            True if deleted, False if not found
        """
        pass
