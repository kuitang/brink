"""Tests for the storage module.

Tests cover:
- FileScenarioRepository error boundaries and edge cases
- Storage configuration functions
- Parametrized integration tests to verify both backends pass identical tests

Redundancy Reduction (see tests/test_removal_log.md for rationale):
- Removed TestSlugify (9 tests) - trivial utility function tested implicitly by save operations
- Removed most of TestFileScenarioRepository - subsumed by parametrized integration tests
- Removed TestSQLiteScenarioRepository (10 tests) - fully subsumed by parametrized tests
- Removed TestFileGameRecordRepository (10 tests) - fully subsumed by parametrized tests
- Removed TestSQLiteGameRecordRepository (10 tests) - fully subsumed by parametrized tests
- Removed redundant TestStorageConfig tests - kept only essential factory and default tests
"""

import uuid

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
)
from brinksmanship.storage.sqlite_repo import (
    SQLiteGameRecordRepository,
    SQLiteScenarioRepository,
)


# ============================================================================
# FileScenarioRepository Tests - Error Boundaries Only
# ============================================================================


class TestFileScenarioRepository:
    """Tests for file-based scenario repository error boundaries and edge cases.

    Most functionality is covered by TestScenarioRepositoryIntegration which runs
    parametrized tests against both File and SQLite backends.
    """

    @pytest.fixture
    def repo(self, tmp_path):
        """Create a FileScenarioRepository with a temporary directory."""
        return FileScenarioRepository(tmp_path / "scenarios")

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
# Config Tests
# ============================================================================


class TestStorageConfig:
    """Tests for storage configuration functions.

    Focuses on factory functions and default behavior.
    """

    def test_get_storage_backend_default(self, monkeypatch):
        """Test get_storage_backend returns FILE by default."""
        monkeypatch.delenv("BRINKSMANSHIP_STORAGE_BACKEND", raising=False)
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
