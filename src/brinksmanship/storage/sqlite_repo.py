"""SQLite-based repository implementations.

This module provides SQLite storage for scenarios and game records,
suitable for the webapp. Uses SQLAlchemy for database operations.
"""

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from .repository import GameRecordRepository, ScenarioRepository

# SQLite storage using standard library sqlite3
# This avoids the SQLAlchemy dependency while still providing database storage
import sqlite3


def dict_factory(cursor: sqlite3.Cursor, row: tuple) -> dict:
    """Convert sqlite3 row to dict."""
    return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}


class SQLiteScenarioRepository(ScenarioRepository):
    """SQLite-based scenario repository.

    Stores scenarios in a SQLite database with JSON serialization for
    complex fields.
    """

    def __init__(self, database_uri: str = "instance/brinksmanship.db"):
        """Initialize repository.

        Args:
            database_uri: Path to SQLite database file
        """
        self.database_path = Path(database_uri)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection."""
        conn = sqlite3.connect(self.database_path)
        conn.row_factory = dict_factory
        return conn

    def _init_db(self) -> None:
        """Initialize database schema."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS scenarios (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                setting TEXT,
                max_turns INTEGER,
                data TEXT NOT NULL,
                created_at TEXT,
                updated_at TEXT
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_scenarios_name ON scenarios(name)")
        conn.commit()
        conn.close()

    def list_scenarios(self) -> list[dict]:
        """Return metadata for all available scenarios."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, setting, max_turns FROM scenarios ORDER BY name")
        rows = cursor.fetchall()
        conn.close()
        return rows

    def get_scenario(self, scenario_id: str) -> Optional[dict]:
        """Load complete scenario by ID."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT data FROM scenarios WHERE id = ?", (scenario_id,))
        row = cursor.fetchone()
        conn.close()

        if row is None:
            return None

        data = json.loads(row["data"])
        data["id"] = scenario_id
        return data

    def get_scenario_by_name(self, name: str) -> Optional[dict]:
        """Load scenario by name (case-insensitive search)."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, data FROM scenarios WHERE LOWER(name) = LOWER(?)",
            (name,)
        )
        row = cursor.fetchone()
        conn.close()

        if row is None:
            return None

        data = json.loads(row["data"])
        data["id"] = row["id"]
        return data

    def save_scenario(self, scenario: dict) -> str:
        """Save scenario, return ID."""
        name = scenario.get("name") or scenario.get("title")
        if not name:
            raise ValueError("Scenario must have 'name' or 'title' field")

        # Generate ID if not present
        scenario_id = scenario.get("id") or str(uuid.uuid4())
        now = datetime.utcnow().isoformat()

        conn = self._get_connection()
        cursor = conn.cursor()

        # Upsert scenario
        cursor.execute("""
            INSERT INTO scenarios (id, name, setting, max_turns, data, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name = excluded.name,
                setting = excluded.setting,
                max_turns = excluded.max_turns,
                data = excluded.data,
                updated_at = excluded.updated_at
        """, (
            scenario_id,
            name,
            scenario.get("setting", ""),
            scenario.get("max_turns", 14),
            json.dumps(scenario),
            now,
            now,
        ))

        conn.commit()
        conn.close()
        return scenario_id

    def delete_scenario(self, scenario_id: str) -> bool:
        """Delete scenario."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM scenarios WHERE id = ?", (scenario_id,))
        deleted = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return deleted


class SQLiteGameRecordRepository(GameRecordRepository):
    """SQLite-based game record repository.

    Stores game records in a SQLite database with JSON serialization
    for game state.
    """

    def __init__(self, database_uri: str = "instance/brinksmanship.db"):
        """Initialize repository.

        Args:
            database_uri: Path to SQLite database file
        """
        self.database_path = Path(database_uri)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection."""
        conn = sqlite3.connect(self.database_path)
        conn.row_factory = dict_factory
        return conn

    def _init_db(self) -> None:
        """Initialize database schema."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS games (
                id TEXT PRIMARY KEY,
                scenario_id TEXT NOT NULL,
                user_id INTEGER,
                status TEXT DEFAULT 'in_progress',
                turn INTEGER DEFAULT 1,
                data TEXT NOT NULL,
                created_at TEXT,
                updated_at TEXT
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_games_user_id ON games(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_games_scenario_id ON games(scenario_id)")
        conn.commit()
        conn.close()

    def save_game(self, game_id: str, state: dict) -> None:
        """Persist complete game state."""
        now = datetime.utcnow().isoformat()

        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO games (id, scenario_id, user_id, status, turn, data, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                status = excluded.status,
                turn = excluded.turn,
                data = excluded.data,
                updated_at = excluded.updated_at
        """, (
            game_id,
            state.get("scenario_id", ""),
            state.get("user_id"),
            state.get("status", "in_progress"),
            state.get("turn", 1),
            json.dumps(state),
            state.get("created_at", now),
            now,
        ))

        conn.commit()
        conn.close()

    def load_game(self, game_id: str) -> Optional[dict]:
        """Load game state by ID."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT data FROM games WHERE id = ?", (game_id,))
        row = cursor.fetchone()
        conn.close()

        if row is None:
            return None

        return json.loads(row["data"])

    def list_games(self, user_id: Optional[int] = None) -> list[dict]:
        """List games, optionally filtered by user."""
        conn = self._get_connection()
        cursor = conn.cursor()

        if user_id is not None:
            cursor.execute("""
                SELECT id, scenario_id, user_id, status, turn, updated_at
                FROM games
                WHERE user_id = ?
                ORDER BY updated_at DESC
            """, (user_id,))
        else:
            cursor.execute("""
                SELECT id, scenario_id, user_id, status, turn, updated_at
                FROM games
                ORDER BY updated_at DESC
            """)

        rows = cursor.fetchall()
        conn.close()
        return rows

    def delete_game(self, game_id: str) -> bool:
        """Delete game record."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM games WHERE id = ?", (game_id,))
        deleted = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return deleted

    def create_game(self, scenario_id: str, user_id: Optional[int] = None) -> str:
        """Create a new game and return its ID.

        Args:
            scenario_id: ID of scenario to use
            user_id: Optional user ID

        Returns:
            New game ID (UUID)
        """
        game_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        initial_state = {
            "id": game_id,
            "scenario_id": scenario_id,
            "user_id": user_id,
            "status": "in_progress",
            "turn": 1,
            "created_at": now,
        }
        self.save_game(game_id, initial_state)
        return game_id
