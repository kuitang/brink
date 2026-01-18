"""Comprehensive tests for the storage module.

Tests cover:
- FileScenarioRepository and FileGameRecordRepository
- SQLiteScenarioRepository and SQLiteGameRecordRepository
- Storage configuration functions
- Parametrized integration tests to verify both backends pass identical tests
"""

import os
import uuid
from pathlib import Path

import pytest

from brinksmanship.storage.config import (
    StorageBackend,
    get_game_repository,
    get_scenario_repository,
    get_storage_backend,
)
from brinksmanship.storage.file_repo import (
    FileGameRecordRepository,
    FileScenarioRepository,
    slugify,
)
from brinksmanship.storage.sqlite_repo import (
    SQLiteGameRecordRepository,
    SQLiteScenarioRepository,
)


# ============================================================================
# Slugify Tests
# ============================================================================


class TestSlugify:
    """Tests for the slugify function."""

    def test_basic_slugify(self):
        """Test basic text is converted to lowercase hyphenated slug."""
        assert slugify("Cuban Missile Crisis") == "cuban-missile-crisis"

    def test_slugify_with_colon(self):
        """Test colons are removed."""
        assert slugify("The Cold War: 1962") == "the-cold-war-1962"

    def test_slugify_with_underscores(self):
        """Test underscores are converted to hyphens."""
        assert slugify("test_scenario_name") == "test-scenario-name"

    def test_slugify_multiple_spaces(self):
        """Test multiple spaces collapse to single hyphen."""
        assert slugify("hello    world") == "hello-world"

    def test_slugify_special_characters(self):
        """Test special characters are removed."""
        assert slugify("Hello! World?") == "hello-world"

    def test_slugify_leading_trailing_hyphens(self):
        """Test leading and trailing hyphens are stripped."""
        assert slugify("-hello-world-") == "hello-world"

    def test_slugify_numbers(self):
        """Test numbers are preserved."""
        assert slugify("Scenario 123") == "scenario-123"

    def test_slugify_empty_string(self):
        """Test empty string returns empty string."""
        assert slugify("") == ""

    def test_slugify_only_special_chars(self):
        """Test string of only special characters returns empty string."""
        assert slugify("!@#$%") == ""


# ============================================================================
# FileScenarioRepository Tests
# ============================================================================


class TestFileScenarioRepository:
    """Tests for the file-based scenario repository."""

    @pytest.fixture
    def repo(self, tmp_path):
        """Create a FileScenarioRepository with a temporary directory."""
        return FileScenarioRepository(tmp_path / "scenarios")

    def test_list_scenarios_empty(self, repo):
        """Test list_scenarios returns empty list initially."""
        assert repo.list_scenarios() == []

    def test_save_and_get_scenario(self, repo):
        """Test save_scenario and get_scenario round-trip."""
        scenario = {
            "name": "Cuban Missile Crisis",
            "setting": "Cold War era nuclear standoff",
            "max_turns": 14,
            "players": ["USA", "USSR"],
        }

        scenario_id = repo.save_scenario(scenario)
        assert scenario_id == "cuban-missile-crisis"

        loaded = repo.get_scenario(scenario_id)
        assert loaded is not None
        assert loaded["name"] == "Cuban Missile Crisis"
        assert loaded["setting"] == "Cold War era nuclear standoff"
        assert loaded["max_turns"] == 14
        assert loaded["players"] == ["USA", "USSR"]
        assert loaded["id"] == "cuban-missile-crisis"

    def test_get_scenario_not_found(self, repo):
        """Test get_scenario returns None for non-existent scenario."""
        assert repo.get_scenario("nonexistent") is None

    def test_get_scenario_by_name(self, repo):
        """Test get_scenario_by_name works with case-insensitive search."""
        scenario = {
            "name": "Cuban Missile Crisis",
            "setting": "Cold War",
            "max_turns": 14,
        }
        repo.save_scenario(scenario)

        # Exact match
        loaded = repo.get_scenario_by_name("Cuban Missile Crisis")
        assert loaded is not None
        assert loaded["name"] == "Cuban Missile Crisis"

        # Case-insensitive match
        loaded = repo.get_scenario_by_name("cuban missile crisis")
        assert loaded is not None
        assert loaded["name"] == "Cuban Missile Crisis"

        # Different case
        loaded = repo.get_scenario_by_name("CUBAN MISSILE CRISIS")
        assert loaded is not None
        assert loaded["name"] == "Cuban Missile Crisis"

    def test_get_scenario_by_name_not_found(self, repo):
        """Test get_scenario_by_name returns None for non-existent name."""
        assert repo.get_scenario_by_name("Nonexistent Scenario") is None

    def test_delete_scenario(self, repo):
        """Test delete_scenario removes the scenario."""
        scenario = {"name": "Test Scenario", "setting": "Test"}
        scenario_id = repo.save_scenario(scenario)

        assert repo.get_scenario(scenario_id) is not None
        assert repo.delete_scenario(scenario_id) is True
        assert repo.get_scenario(scenario_id) is None

    def test_delete_scenario_not_found(self, repo):
        """Test delete_scenario returns False for non-existent scenario."""
        assert repo.delete_scenario("nonexistent") is False

    def test_list_scenarios_multiple(self, repo):
        """Test list_scenarios returns sorted list of all scenarios."""
        scenarios = [
            {"name": "Zebra Crisis", "setting": "A"},
            {"name": "Alpha Scenario", "setting": "B"},
            {"name": "Beta Incident", "setting": "C"},
        ]

        for s in scenarios:
            repo.save_scenario(s)

        listed = repo.list_scenarios()
        assert len(listed) == 3
        # Should be sorted by name
        assert listed[0]["name"] == "Alpha Scenario"
        assert listed[1]["name"] == "Beta Incident"
        assert listed[2]["name"] == "Zebra Crisis"

    def test_save_scenario_no_name_raises(self, repo):
        """Test save_scenario raises ValueError if no name field."""
        with pytest.raises(ValueError, match="must have 'name' or 'title' field"):
            repo.save_scenario({"setting": "No name"})

    def test_save_scenario_with_title(self, repo):
        """Test save_scenario accepts 'title' as alternative to 'name'."""
        scenario = {"title": "Test Title", "setting": "Test"}
        scenario_id = repo.save_scenario(scenario)

        loaded = repo.get_scenario(scenario_id)
        assert loaded is not None
        # Should have both title and name after save
        assert loaded["name"] == "Test Title"

    def test_scenario_update_overwrites(self, repo):
        """Test saving a scenario with same name overwrites."""
        scenario1 = {"name": "Test Scenario", "setting": "Original"}
        scenario_id = repo.save_scenario(scenario1)

        scenario2 = {"name": "Test Scenario", "setting": "Updated"}
        scenario_id2 = repo.save_scenario(scenario2)

        assert scenario_id == scenario_id2
        loaded = repo.get_scenario(scenario_id)
        assert loaded["setting"] == "Updated"


# ============================================================================
# FileGameRecordRepository Tests
# ============================================================================


class TestFileGameRecordRepository:
    """Tests for the file-based game record repository."""

    @pytest.fixture
    def repo(self, tmp_path):
        """Create a FileGameRecordRepository with a temporary directory."""
        return FileGameRecordRepository(tmp_path / "games")

    def test_list_games_empty(self, repo):
        """Test list_games returns empty list initially."""
        assert repo.list_games() == []

    def test_save_and_load_game(self, repo):
        """Test save_game and load_game round-trip."""
        game_id = str(uuid.uuid4())
        state = {
            "scenario_id": "cuban-missile-crisis",
            "user_id": 1,
            "status": "in_progress",
            "turn": 5,
            "actions": ["action1", "action2"],
        }

        repo.save_game(game_id, state)
        loaded = repo.load_game(game_id)

        assert loaded is not None
        assert loaded["id"] == game_id
        assert loaded["scenario_id"] == "cuban-missile-crisis"
        assert loaded["user_id"] == 1
        assert loaded["status"] == "in_progress"
        assert loaded["turn"] == 5
        assert loaded["actions"] == ["action1", "action2"]

    def test_load_game_not_found(self, repo):
        """Test load_game returns None for non-existent game."""
        assert repo.load_game("nonexistent-id") is None

    def test_list_games_no_filter(self, repo):
        """Test list_games returns all games without filter."""
        game1_id = str(uuid.uuid4())
        game2_id = str(uuid.uuid4())

        repo.save_game(game1_id, {"scenario_id": "s1", "user_id": 1})
        repo.save_game(game2_id, {"scenario_id": "s2", "user_id": 2})

        games = repo.list_games()
        assert len(games) == 2

    def test_list_games_with_user_filter(self, repo):
        """Test list_games filters by user_id."""
        game1_id = str(uuid.uuid4())
        game2_id = str(uuid.uuid4())
        game3_id = str(uuid.uuid4())

        repo.save_game(game1_id, {"scenario_id": "s1", "user_id": 1})
        repo.save_game(game2_id, {"scenario_id": "s2", "user_id": 2})
        repo.save_game(game3_id, {"scenario_id": "s3", "user_id": 1})

        user1_games = repo.list_games(user_id=1)
        assert len(user1_games) == 2
        assert all(g["user_id"] == 1 for g in user1_games)

        user2_games = repo.list_games(user_id=2)
        assert len(user2_games) == 1
        assert user2_games[0]["user_id"] == 2

    def test_delete_game(self, repo):
        """Test delete_game removes the game."""
        game_id = str(uuid.uuid4())
        repo.save_game(game_id, {"scenario_id": "test"})

        assert repo.load_game(game_id) is not None
        assert repo.delete_game(game_id) is True
        assert repo.load_game(game_id) is None

    def test_delete_game_not_found(self, repo):
        """Test delete_game returns False for non-existent game."""
        assert repo.delete_game("nonexistent-id") is False

    def test_create_game(self, repo):
        """Test create_game creates a new game with UUID."""
        game_id = repo.create_game("cuban-missile-crisis", user_id=42)

        # Verify it's a valid UUID
        uuid.UUID(game_id)

        loaded = repo.load_game(game_id)
        assert loaded is not None
        assert loaded["scenario_id"] == "cuban-missile-crisis"
        assert loaded["user_id"] == 42
        assert loaded["status"] == "in_progress"
        assert loaded["turn"] == 1

    def test_create_game_no_user(self, repo):
        """Test create_game works without user_id."""
        game_id = repo.create_game("test-scenario")

        loaded = repo.load_game(game_id)
        assert loaded is not None
        assert loaded["user_id"] is None

    def test_game_update(self, repo):
        """Test saving a game with same ID updates it."""
        game_id = str(uuid.uuid4())
        repo.save_game(game_id, {"scenario_id": "test", "turn": 1})
        repo.save_game(game_id, {"scenario_id": "test", "turn": 5})

        loaded = repo.load_game(game_id)
        assert loaded["turn"] == 5


# ============================================================================
# SQLiteScenarioRepository Tests
# ============================================================================


class TestSQLiteScenarioRepository:
    """Tests for the SQLite-based scenario repository."""

    @pytest.fixture
    def repo(self, tmp_path):
        """Create a SQLiteScenarioRepository with a temporary database."""
        db_path = tmp_path / "test.db"
        return SQLiteScenarioRepository(str(db_path))

    def test_list_scenarios_empty(self, repo):
        """Test list_scenarios returns empty list initially."""
        assert repo.list_scenarios() == []

    def test_save_and_get_scenario(self, repo):
        """Test save_scenario and get_scenario round-trip."""
        scenario = {
            "name": "Cuban Missile Crisis",
            "setting": "Cold War era nuclear standoff",
            "max_turns": 14,
            "players": ["USA", "USSR"],
        }

        scenario_id = repo.save_scenario(scenario)
        assert scenario_id is not None

        loaded = repo.get_scenario(scenario_id)
        assert loaded is not None
        assert loaded["name"] == "Cuban Missile Crisis"
        assert loaded["setting"] == "Cold War era nuclear standoff"
        assert loaded["max_turns"] == 14
        assert loaded["players"] == ["USA", "USSR"]
        assert loaded["id"] == scenario_id

    def test_get_scenario_not_found(self, repo):
        """Test get_scenario returns None for non-existent scenario."""
        assert repo.get_scenario("nonexistent-uuid") is None

    def test_get_scenario_by_name(self, repo):
        """Test get_scenario_by_name works with case-insensitive search."""
        scenario = {
            "name": "Cuban Missile Crisis",
            "setting": "Cold War",
            "max_turns": 14,
        }
        repo.save_scenario(scenario)

        # Exact match
        loaded = repo.get_scenario_by_name("Cuban Missile Crisis")
        assert loaded is not None
        assert loaded["name"] == "Cuban Missile Crisis"

        # Case-insensitive match
        loaded = repo.get_scenario_by_name("cuban missile crisis")
        assert loaded is not None
        assert loaded["name"] == "Cuban Missile Crisis"

        # Different case
        loaded = repo.get_scenario_by_name("CUBAN MISSILE CRISIS")
        assert loaded is not None
        assert loaded["name"] == "Cuban Missile Crisis"

    def test_get_scenario_by_name_not_found(self, repo):
        """Test get_scenario_by_name returns None for non-existent name."""
        assert repo.get_scenario_by_name("Nonexistent Scenario") is None

    def test_delete_scenario(self, repo):
        """Test delete_scenario removes the scenario."""
        scenario = {"name": "Test Scenario", "setting": "Test"}
        scenario_id = repo.save_scenario(scenario)

        assert repo.get_scenario(scenario_id) is not None
        assert repo.delete_scenario(scenario_id) is True
        assert repo.get_scenario(scenario_id) is None

    def test_delete_scenario_not_found(self, repo):
        """Test delete_scenario returns False for non-existent scenario."""
        assert repo.delete_scenario("nonexistent-uuid") is False

    def test_list_scenarios_multiple(self, repo):
        """Test list_scenarios returns sorted list of all scenarios."""
        scenarios = [
            {"name": "Zebra Crisis", "setting": "A"},
            {"name": "Alpha Scenario", "setting": "B"},
            {"name": "Beta Incident", "setting": "C"},
        ]

        for s in scenarios:
            repo.save_scenario(s)

        listed = repo.list_scenarios()
        assert len(listed) == 3
        # Should be sorted by name
        assert listed[0]["name"] == "Alpha Scenario"
        assert listed[1]["name"] == "Beta Incident"
        assert listed[2]["name"] == "Zebra Crisis"

    def test_save_scenario_no_name_raises(self, repo):
        """Test save_scenario raises ValueError if no name field."""
        with pytest.raises(ValueError, match="must have 'name' or 'title' field"):
            repo.save_scenario({"setting": "No name"})

    def test_save_scenario_with_title(self, repo):
        """Test save_scenario accepts 'title' as alternative to 'name'."""
        scenario = {"title": "Test Title", "setting": "Test"}
        scenario_id = repo.save_scenario(scenario)

        loaded = repo.get_scenario(scenario_id)
        assert loaded is not None

    def test_scenario_upsert(self, repo):
        """Test saving a scenario with same ID updates it."""
        scenario = {"name": "Test Scenario", "setting": "Original"}
        scenario_id = repo.save_scenario(scenario)

        # Save with same ID
        scenario2 = {"id": scenario_id, "name": "Test Scenario", "setting": "Updated"}
        scenario_id2 = repo.save_scenario(scenario2)

        assert scenario_id == scenario_id2
        loaded = repo.get_scenario(scenario_id)
        assert loaded["setting"] == "Updated"


# ============================================================================
# SQLiteGameRecordRepository Tests
# ============================================================================


class TestSQLiteGameRecordRepository:
    """Tests for the SQLite-based game record repository."""

    @pytest.fixture
    def repo(self, tmp_path):
        """Create a SQLiteGameRecordRepository with a temporary database."""
        db_path = tmp_path / "test.db"
        return SQLiteGameRecordRepository(str(db_path))

    def test_list_games_empty(self, repo):
        """Test list_games returns empty list initially."""
        assert repo.list_games() == []

    def test_save_and_load_game(self, repo):
        """Test save_game and load_game round-trip."""
        game_id = str(uuid.uuid4())
        state = {
            "scenario_id": "cuban-missile-crisis",
            "user_id": 1,
            "status": "in_progress",
            "turn": 5,
            "actions": ["action1", "action2"],
        }

        repo.save_game(game_id, state)
        loaded = repo.load_game(game_id)

        assert loaded is not None
        assert loaded["scenario_id"] == "cuban-missile-crisis"
        assert loaded["user_id"] == 1
        assert loaded["status"] == "in_progress"
        assert loaded["turn"] == 5
        assert loaded["actions"] == ["action1", "action2"]

    def test_load_game_not_found(self, repo):
        """Test load_game returns None for non-existent game."""
        assert repo.load_game("nonexistent-id") is None

    def test_list_games_no_filter(self, repo):
        """Test list_games returns all games without filter."""
        game1_id = str(uuid.uuid4())
        game2_id = str(uuid.uuid4())

        repo.save_game(game1_id, {"scenario_id": "s1", "user_id": 1})
        repo.save_game(game2_id, {"scenario_id": "s2", "user_id": 2})

        games = repo.list_games()
        assert len(games) == 2

    def test_list_games_with_user_filter(self, repo):
        """Test list_games filters by user_id."""
        game1_id = str(uuid.uuid4())
        game2_id = str(uuid.uuid4())
        game3_id = str(uuid.uuid4())

        repo.save_game(game1_id, {"scenario_id": "s1", "user_id": 1})
        repo.save_game(game2_id, {"scenario_id": "s2", "user_id": 2})
        repo.save_game(game3_id, {"scenario_id": "s3", "user_id": 1})

        user1_games = repo.list_games(user_id=1)
        assert len(user1_games) == 2
        assert all(g["user_id"] == 1 for g in user1_games)

        user2_games = repo.list_games(user_id=2)
        assert len(user2_games) == 1
        assert user2_games[0]["user_id"] == 2

    def test_delete_game(self, repo):
        """Test delete_game removes the game."""
        game_id = str(uuid.uuid4())
        repo.save_game(game_id, {"scenario_id": "test"})

        assert repo.load_game(game_id) is not None
        assert repo.delete_game(game_id) is True
        assert repo.load_game(game_id) is None

    def test_delete_game_not_found(self, repo):
        """Test delete_game returns False for non-existent game."""
        assert repo.delete_game("nonexistent-id") is False

    def test_create_game(self, repo):
        """Test create_game creates a new game with UUID."""
        game_id = repo.create_game("cuban-missile-crisis", user_id=42)

        # Verify it's a valid UUID
        uuid.UUID(game_id)

        loaded = repo.load_game(game_id)
        assert loaded is not None
        assert loaded["scenario_id"] == "cuban-missile-crisis"
        assert loaded["user_id"] == 42
        assert loaded["status"] == "in_progress"
        assert loaded["turn"] == 1

    def test_create_game_no_user(self, repo):
        """Test create_game works without user_id."""
        game_id = repo.create_game("test-scenario")

        loaded = repo.load_game(game_id)
        assert loaded is not None
        assert loaded["user_id"] is None

    def test_game_upsert(self, repo):
        """Test saving a game with same ID updates it."""
        game_id = str(uuid.uuid4())
        repo.save_game(game_id, {"scenario_id": "test", "turn": 1})
        repo.save_game(game_id, {"scenario_id": "test", "turn": 5})

        loaded = repo.load_game(game_id)
        assert loaded["turn"] == 5


# ============================================================================
# Config Tests
# ============================================================================


class TestStorageConfig:
    """Tests for storage configuration functions."""

    def test_get_storage_backend_default(self, monkeypatch):
        """Test get_storage_backend returns FILE by default."""
        monkeypatch.delenv("BRINKSMANSHIP_STORAGE_BACKEND", raising=False)
        assert get_storage_backend() == StorageBackend.FILE

    def test_get_storage_backend_file(self, monkeypatch):
        """Test get_storage_backend returns FILE when set to 'file'."""
        monkeypatch.setenv("BRINKSMANSHIP_STORAGE_BACKEND", "file")
        assert get_storage_backend() == StorageBackend.FILE

    def test_get_storage_backend_sqlite(self, monkeypatch):
        """Test get_storage_backend returns SQLITE when set to 'sqlite'."""
        monkeypatch.setenv("BRINKSMANSHIP_STORAGE_BACKEND", "sqlite")
        assert get_storage_backend() == StorageBackend.SQLITE

    def test_get_storage_backend_case_insensitive(self, monkeypatch):
        """Test get_storage_backend is case-insensitive."""
        monkeypatch.setenv("BRINKSMANSHIP_STORAGE_BACKEND", "SQLITE")
        assert get_storage_backend() == StorageBackend.SQLITE

    def test_get_storage_backend_unknown_defaults_to_file(self, monkeypatch):
        """Test get_storage_backend defaults to FILE for unknown values."""
        monkeypatch.setenv("BRINKSMANSHIP_STORAGE_BACKEND", "unknown")
        assert get_storage_backend() == StorageBackend.FILE

    def test_factory_returns_file_repo(self, tmp_path, monkeypatch):
        """Test factory functions return File repositories for FILE backend."""
        monkeypatch.setenv("BRINKSMANSHIP_SCENARIOS_PATH", str(tmp_path / "scenarios"))
        monkeypatch.setenv("BRINKSMANSHIP_GAMES_PATH", str(tmp_path / "games"))

        scenario_repo = get_scenario_repository(StorageBackend.FILE)
        game_repo = get_game_repository(StorageBackend.FILE)

        assert isinstance(scenario_repo, FileScenarioRepository)
        assert isinstance(game_repo, FileGameRecordRepository)

    def test_factory_returns_sqlite_repo(self, tmp_path, monkeypatch):
        """Test factory functions return SQLite repositories for SQLITE backend."""
        db_path = str(tmp_path / "test.db")
        monkeypatch.setenv("BRINKSMANSHIP_DATABASE_URI", db_path)

        scenario_repo = get_scenario_repository(StorageBackend.SQLITE)
        game_repo = get_game_repository(StorageBackend.SQLITE)

        assert isinstance(scenario_repo, SQLiteScenarioRepository)
        assert isinstance(game_repo, SQLiteGameRecordRepository)

    def test_factory_uses_env_when_backend_not_specified(self, tmp_path, monkeypatch):
        """Test factory functions use environment config when backend is None."""
        monkeypatch.setenv("BRINKSMANSHIP_STORAGE_BACKEND", "sqlite")
        db_path = str(tmp_path / "test.db")
        monkeypatch.setenv("BRINKSMANSHIP_DATABASE_URI", db_path)

        scenario_repo = get_scenario_repository()
        game_repo = get_game_repository()

        assert isinstance(scenario_repo, SQLiteScenarioRepository)
        assert isinstance(game_repo, SQLiteGameRecordRepository)


# ============================================================================
# Integration Tests - Parametrized for Both Backends
# ============================================================================


@pytest.fixture
def file_scenario_repo(tmp_path):
    """Create a FileScenarioRepository for integration tests."""
    return FileScenarioRepository(tmp_path / "file_scenarios")


@pytest.fixture
def sqlite_scenario_repo(tmp_path):
    """Create a SQLiteScenarioRepository for integration tests."""
    return SQLiteScenarioRepository(str(tmp_path / "test_scenario.db"))


@pytest.fixture
def file_game_repo(tmp_path):
    """Create a FileGameRecordRepository for integration tests."""
    return FileGameRecordRepository(tmp_path / "file_games")


@pytest.fixture
def sqlite_game_repo(tmp_path):
    """Create a SQLiteGameRecordRepository for integration tests."""
    return SQLiteGameRecordRepository(str(tmp_path / "test_game.db"))


class TestScenarioRepositoryIntegration:
    """Integration tests that run against both file and SQLite backends."""

    @pytest.fixture(params=["file", "sqlite"])
    def scenario_repo(self, request, file_scenario_repo, sqlite_scenario_repo):
        """Parametrized fixture that provides both repository implementations."""
        if request.param == "file":
            return file_scenario_repo
        return sqlite_scenario_repo

    def test_empty_list(self, scenario_repo):
        """Both backends should return empty list initially."""
        assert scenario_repo.list_scenarios() == []

    def test_save_get_roundtrip(self, scenario_repo):
        """Both backends should save and retrieve scenarios correctly."""
        scenario = {
            "name": "Integration Test Scenario",
            "setting": "Test setting",
            "max_turns": 10,
            "custom_field": "custom_value",
        }

        scenario_id = scenario_repo.save_scenario(scenario)
        loaded = scenario_repo.get_scenario(scenario_id)

        assert loaded is not None
        assert loaded["name"] == "Integration Test Scenario"
        assert loaded["setting"] == "Test setting"
        assert loaded["max_turns"] == 10
        assert loaded["custom_field"] == "custom_value"

    def test_case_insensitive_name_lookup(self, scenario_repo):
        """Both backends should support case-insensitive name lookup."""
        scenario = {"name": "Test Scenario", "setting": "Test"}
        scenario_repo.save_scenario(scenario)

        # All these should find the scenario
        assert scenario_repo.get_scenario_by_name("Test Scenario") is not None
        assert scenario_repo.get_scenario_by_name("test scenario") is not None
        assert scenario_repo.get_scenario_by_name("TEST SCENARIO") is not None

    def test_delete(self, scenario_repo):
        """Both backends should delete scenarios correctly."""
        scenario = {"name": "To Delete", "setting": "Test"}
        scenario_id = scenario_repo.save_scenario(scenario)

        assert scenario_repo.get_scenario(scenario_id) is not None
        assert scenario_repo.delete_scenario(scenario_id) is True
        assert scenario_repo.get_scenario(scenario_id) is None
        assert scenario_repo.delete_scenario(scenario_id) is False

    def test_list_sorted_by_name(self, scenario_repo):
        """Both backends should return scenarios sorted by name."""
        scenarios = [
            {"name": "Zulu", "setting": "Z"},
            {"name": "Alpha", "setting": "A"},
            {"name": "Mike", "setting": "M"},
        ]

        for s in scenarios:
            scenario_repo.save_scenario(s)

        listed = scenario_repo.list_scenarios()
        names = [s["name"] for s in listed]
        assert names == ["Alpha", "Mike", "Zulu"]


class TestGameRecordRepositoryIntegration:
    """Integration tests that run against both file and SQLite backends."""

    @pytest.fixture(params=["file", "sqlite"])
    def game_repo(self, request, file_game_repo, sqlite_game_repo):
        """Parametrized fixture that provides both repository implementations."""
        if request.param == "file":
            return file_game_repo
        return sqlite_game_repo

    def test_empty_list(self, game_repo):
        """Both backends should return empty list initially."""
        assert game_repo.list_games() == []

    def test_save_load_roundtrip(self, game_repo):
        """Both backends should save and load game state correctly."""
        game_id = str(uuid.uuid4())
        state = {
            "scenario_id": "test-scenario",
            "user_id": 123,
            "status": "in_progress",
            "turn": 7,
            "custom_data": {"key": "value"},
        }

        game_repo.save_game(game_id, state)
        loaded = game_repo.load_game(game_id)

        assert loaded is not None
        assert loaded["scenario_id"] == "test-scenario"
        assert loaded["user_id"] == 123
        assert loaded["status"] == "in_progress"
        assert loaded["turn"] == 7
        assert loaded["custom_data"] == {"key": "value"}

    def test_user_filter(self, game_repo):
        """Both backends should filter games by user_id."""
        for i in range(3):
            game_repo.save_game(
                str(uuid.uuid4()),
                {"scenario_id": "s", "user_id": 1},
            )
        for i in range(2):
            game_repo.save_game(
                str(uuid.uuid4()),
                {"scenario_id": "s", "user_id": 2},
            )

        assert len(game_repo.list_games()) == 5
        assert len(game_repo.list_games(user_id=1)) == 3
        assert len(game_repo.list_games(user_id=2)) == 2
        assert len(game_repo.list_games(user_id=999)) == 0

    def test_delete(self, game_repo):
        """Both backends should delete games correctly."""
        game_id = str(uuid.uuid4())
        game_repo.save_game(game_id, {"scenario_id": "test"})

        assert game_repo.load_game(game_id) is not None
        assert game_repo.delete_game(game_id) is True
        assert game_repo.load_game(game_id) is None
        assert game_repo.delete_game(game_id) is False

    def test_create_game(self, game_repo):
        """Both backends should create games with proper defaults."""
        game_id = game_repo.create_game("my-scenario", user_id=42)

        # Should be a valid UUID
        uuid.UUID(game_id)

        loaded = game_repo.load_game(game_id)
        assert loaded is not None
        assert loaded["scenario_id"] == "my-scenario"
        assert loaded["user_id"] == 42
        assert loaded["status"] == "in_progress"
        assert loaded["turn"] == 1

    def test_update_game(self, game_repo):
        """Both backends should update existing games."""
        game_id = str(uuid.uuid4())
        game_repo.save_game(game_id, {"scenario_id": "test", "turn": 1, "status": "in_progress"})
        game_repo.save_game(game_id, {"scenario_id": "test", "turn": 10, "status": "completed"})

        loaded = game_repo.load_game(game_id)
        assert loaded["turn"] == 10
        assert loaded["status"] == "completed"
