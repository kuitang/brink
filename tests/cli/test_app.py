"""Tests for the CLI application."""

from unittest.mock import MagicMock, patch

import pytest

from brinksmanship.cli.app import BrinksmanshipCLI, run_async


@pytest.fixture
def mock_scenario_repo():
    """Mock scenario repository for testing."""
    mock_repo = MagicMock()
    mock_repo.list_scenarios.return_value = [
        {"id": "test-scenario", "name": "Test Scenario", "setting": "Test Setting"}
    ]
    mock_repo.get_scenario.return_value = {
        "id": "test-scenario",
        "name": "Test Scenario",
        "max_turns": 12,
        "turns": [
            {
                "turn": 1,
                "act": 1,
                "narrative_briefing": "Test briefing",
                "matrix_type": "prisoners_dilemma",
                "matrix_parameters": {"scale": 1.0},
                "actions": [
                    {
                        "action_id": "cooperate",
                        "narrative_description": "Cooperate",
                        "action_type": "cooperative",
                        "resource_cost": 0,
                    },
                    {
                        "action_id": "defect",
                        "narrative_description": "Defect",
                        "action_type": "competitive",
                        "resource_cost": 0,
                    },
                ],
            }
        ],
    }
    return mock_repo


@pytest.fixture
def mock_opponent():
    """Mock opponent that doesn't require LLM calls."""
    from brinksmanship.models.actions import ActionType
    from brinksmanship.opponents.base import Opponent, SettlementResponse

    class MockOpponent(Opponent):
        async def choose_action(self, state, available_actions):
            # Always pick first cooperative action, or first action
            for a in available_actions:
                if a.action_type == ActionType.COOPERATIVE:
                    return a
            return available_actions[0]

        async def evaluate_settlement(self, proposal, state, is_final_offer):
            # Always accept
            return SettlementResponse(action="accept")

        async def propose_settlement(self, state):
            return None

    return MockOpponent(name="Mock")


class TestBrinksmanshipCLI:
    """Tests for the BrinksmanshipCLI class."""

    def test_cli_instantiation(self):
        """CLI should instantiate without errors."""
        with patch("brinksmanship.cli.app.get_scenario_repository") as mock_get_repo:
            mock_get_repo.return_value = MagicMock()
            cli = BrinksmanshipCLI()
            assert cli.game is None
            assert cli.opponent is None
            assert cli.human_is_player_a is True

    def test_run_async_with_sync_value(self):
        """run_async should handle async functions."""

        async def async_add(x, y):
            return x + y

        result = run_async(async_add(1, 2))
        assert result == 3


class TestAsyncHandling:
    """Tests for proper handling of async opponent methods."""

    def test_run_async_basic(self):
        """run_async should work with basic async functions."""

        async def simple_async():
            return 42

        result = run_async(simple_async())
        assert result == 42

    def test_run_async_with_params(self):
        """run_async should work with async functions with parameters."""

        async def async_multiply(a, b):
            return a * b

        result = run_async(async_multiply(6, 7))
        assert result == 42


class TestScorecardCalculations:
    """Tests for the scorecard calculation methods."""

    @pytest.fixture
    def cli_with_mock_repo(self):
        """Create a CLI instance with mocked repository."""
        with patch("brinksmanship.cli.app.get_scenario_repository") as mock_get_repo:
            mock_get_repo.return_value = MagicMock()
            cli = BrinksmanshipCLI()
            return cli

    def test_calculate_max_streaks_empty_history(self, cli_with_mock_repo):
        """Max streaks should be 0 with empty history."""
        cli = cli_with_mock_repo
        cli.human_is_player_a = True

        your_max, opp_max = cli._calculate_max_streaks([])
        assert your_max == 0
        assert opp_max == 0

    def test_calculate_max_streaks_all_cc(self, cli_with_mock_repo):
        """Max streaks should count consecutive CC outcomes."""
        cli = cli_with_mock_repo
        cli.human_is_player_a = True

        # Create mock history with 5 consecutive CC outcomes
        mock_records = []
        for _i in range(5):
            record = MagicMock()
            record.outcome = MagicMock()
            record.outcome.outcome_code = "CC"
            mock_records.append(record)

        your_max, opp_max = cli._calculate_max_streaks(mock_records)
        assert your_max == 5
        assert opp_max == 5

    def test_calculate_max_streaks_broken_streak(self, cli_with_mock_repo):
        """Streak should reset on non-CC outcome."""
        cli = cli_with_mock_repo
        cli.human_is_player_a = True

        # 3 CC, then CD (breaks streak), then 2 CC
        mock_records = []
        codes = ["CC", "CC", "CC", "CD", "CC", "CC"]
        for code in codes:
            record = MagicMock()
            record.outcome = MagicMock()
            record.outcome.outcome_code = code
            mock_records.append(record)

        your_max, opp_max = cli._calculate_max_streaks(mock_records)
        assert your_max == 3  # Max was the first 3 CC
        assert opp_max == 3

    def test_calculate_times_exploited_player_a(self, cli_with_mock_repo):
        """Test exploitation counting when human is player A."""
        cli = cli_with_mock_repo
        cli.human_is_player_a = True

        # CD = A cooperated, B defected (you exploited)
        # DC = A defected, B cooperated (opponent exploited)
        mock_records = []
        codes = ["CC", "CD", "DC", "CD", "DD"]
        for code in codes:
            record = MagicMock()
            record.outcome = MagicMock()
            record.outcome.outcome_code = code
            mock_records.append(record)

        your_exploited, opp_exploited = cli._calculate_times_exploited(mock_records)
        assert your_exploited == 2  # Two CD outcomes
        assert opp_exploited == 1  # One DC outcome

    def test_calculate_times_exploited_player_b(self, cli_with_mock_repo):
        """Test exploitation counting when human is player B."""
        cli = cli_with_mock_repo
        cli.human_is_player_a = False

        # CD = A cooperated, B (you) defected (opponent exploited)
        # DC = A defected, B (you) cooperated (you exploited)
        mock_records = []
        codes = ["CC", "CD", "DC", "CD", "DD"]
        for code in codes:
            record = MagicMock()
            record.outcome = MagicMock()
            record.outcome.outcome_code = code
            mock_records.append(record)

        your_exploited, opp_exploited = cli._calculate_times_exploited(mock_records)
        assert your_exploited == 1  # One DC outcome
        assert opp_exploited == 2  # Two CD outcomes

    def test_get_settlement_initiator_no_attempts(self, cli_with_mock_repo):
        """Should return 'none' when no settlement attempts."""
        cli = cli_with_mock_repo
        cli.trace_logger = None

        result = cli._get_settlement_initiator()
        assert result == "none"

    def test_get_settlement_initiator_human_accepted(self, cli_with_mock_repo):
        """Should return 'you' when human's proposal was accepted."""
        cli = cli_with_mock_repo

        # Mock trace logger with settlement attempt
        mock_trace = MagicMock()
        mock_trace.trace.settlement_attempts = [{"proposer": "human", "response": "accept"}]
        cli.trace_logger = mock_trace

        result = cli._get_settlement_initiator()
        assert result == "you"

    def test_get_settlement_initiator_opponent_accepted(self, cli_with_mock_repo):
        """Should return 'opponent' when opponent's proposal was accepted."""
        cli = cli_with_mock_repo

        mock_trace = MagicMock()
        mock_trace.trace.settlement_attempts = [{"proposer": "opponent", "response": "accept"}]
        cli.trace_logger = mock_trace

        result = cli._get_settlement_initiator()
        assert result == "opponent"
