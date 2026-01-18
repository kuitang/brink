"""File-based repository implementations using JSON files.

This module provides JSON file-based storage for scenarios and game records.
Scenarios are stored in the scenarios/ directory, game records in games/.
"""

import json
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from .repository import GameRecordRepository, ScenarioRepository


def slugify(text: str) -> str:
    """Convert text to URL-friendly slug.

    Args:
        text: Text to convert

    Returns:
        Lowercase, hyphenated slug

    Examples:
        >>> slugify("Cuban Missile Crisis")
        'cuban-missile-crisis'
        >>> slugify("The Cold War: 1962")
        'the-cold-war-1962'
    """
    # Convert to lowercase
    text = text.lower()
    # Replace spaces and underscores with hyphens
    text = re.sub(r"[\s_]+", "-", text)
    # Remove non-alphanumeric characters except hyphens
    text = re.sub(r"[^a-z0-9-]", "", text)
    # Collapse multiple hyphens
    text = re.sub(r"-+", "-", text)
    # Strip leading/trailing hyphens
    text = text.strip("-")
    return text


class FileScenarioRepository(ScenarioRepository):
    """JSON file-based scenario repository.

    Stores scenarios as individual JSON files in the scenarios directory.
    Scenario IDs are slugified names (e.g., 'cuban-missile-crisis.json').
    """

    def __init__(self, scenarios_path: str | Path = "scenarios"):
        """Initialize repository.

        Args:
            scenarios_path: Path to scenarios directory
        """
        self.scenarios_path = Path(scenarios_path)
        self.scenarios_path.mkdir(parents=True, exist_ok=True)

    def _get_scenario_path(self, scenario_id: str) -> Path:
        """Get path to scenario file."""
        return self.scenarios_path / f"{scenario_id}.json"

    def list_scenarios(self) -> list[dict]:
        """Return metadata for all available scenarios."""
        scenarios = []
        for path in self.scenarios_path.glob("*.json"):
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
                scenarios.append({
                    "id": path.stem,
                    "name": data.get("name", data.get("title", path.stem)),
                    "setting": data.get("setting", ""),
                    "max_turns": data.get("max_turns", 14),
                })
        return sorted(scenarios, key=lambda x: x["name"])

    def get_scenario(self, scenario_id: str) -> Optional[dict]:
        """Load complete scenario by ID."""
        path = self._get_scenario_path(scenario_id)
        if not path.exists():
            return None
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
            data["id"] = scenario_id
            return data

    def get_scenario_by_name(self, name: str) -> Optional[dict]:
        """Load scenario by name (case-insensitive search)."""
        name_lower = name.lower()
        for path in self.scenarios_path.glob("*.json"):
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
                scenario_name = data.get("name", data.get("title", ""))
                if scenario_name.lower() == name_lower:
                    data["id"] = path.stem
                    return data
        return None

    def save_scenario(self, scenario: dict) -> str:
        """Save scenario, return ID."""
        name = scenario.get("name") or scenario.get("title")
        if not name:
            raise ValueError("Scenario must have 'name' or 'title' field")

        scenario_id = slugify(name)
        path = self._get_scenario_path(scenario_id)

        # Add metadata
        scenario_with_meta = {
            **scenario,
            "id": scenario_id,
            "name": name,
            "updated_at": datetime.utcnow().isoformat(),
        }

        with open(path, "w", encoding="utf-8") as f:
            json.dump(scenario_with_meta, f, indent=2)

        return scenario_id

    def delete_scenario(self, scenario_id: str) -> bool:
        """Delete scenario."""
        path = self._get_scenario_path(scenario_id)
        if path.exists():
            path.unlink()
            return True
        return False


class FileGameRecordRepository(GameRecordRepository):
    """JSON file-based game record repository.

    Stores game records as individual JSON files in the games directory.
    Game IDs are UUIDs.
    """

    def __init__(self, games_path: str | Path = "games"):
        """Initialize repository.

        Args:
            games_path: Path to games directory
        """
        self.games_path = Path(games_path)
        self.games_path.mkdir(parents=True, exist_ok=True)

    def _get_game_path(self, game_id: str) -> Path:
        """Get path to game file."""
        return self.games_path / f"{game_id}.json"

    def save_game(self, game_id: str, state: dict) -> None:
        """Persist complete game state."""
        path = self._get_game_path(game_id)

        state_with_meta = {
            **state,
            "id": game_id,
            "updated_at": datetime.utcnow().isoformat(),
        }

        with open(path, "w", encoding="utf-8") as f:
            json.dump(state_with_meta, f, indent=2)

    def load_game(self, game_id: str) -> Optional[dict]:
        """Load game state by ID."""
        path = self._get_game_path(game_id)
        if not path.exists():
            return None
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    def list_games(self, user_id: Optional[int] = None) -> list[dict]:
        """List games, optionally filtered by user."""
        games = []
        for path in self.games_path.glob("*.json"):
            with open(path, encoding="utf-8") as f:
                data = json.load(f)

                # Filter by user if specified
                if user_id is not None and data.get("user_id") != user_id:
                    continue

                games.append({
                    "id": data.get("id", path.stem),
                    "scenario_id": data.get("scenario_id", ""),
                    "status": data.get("status", "in_progress"),
                    "turn": data.get("turn", 1),
                    "updated_at": data.get("updated_at", ""),
                    "user_id": data.get("user_id"),
                })
        return sorted(games, key=lambda x: x.get("updated_at", ""), reverse=True)

    def delete_game(self, game_id: str) -> bool:
        """Delete game record."""
        path = self._get_game_path(game_id)
        if path.exists():
            path.unlink()
            return True
        return False

    def create_game(self, scenario_id: str, user_id: Optional[int] = None) -> str:
        """Create a new game and return its ID.

        Args:
            scenario_id: ID of scenario to use
            user_id: Optional user ID

        Returns:
            New game ID (UUID)
        """
        game_id = str(uuid.uuid4())
        initial_state = {
            "id": game_id,
            "scenario_id": scenario_id,
            "user_id": user_id,
            "status": "in_progress",
            "turn": 1,
            "created_at": datetime.utcnow().isoformat(),
        }
        self.save_game(game_id, initial_state)
        return game_id
