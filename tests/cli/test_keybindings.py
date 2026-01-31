"""Tests for CLI input handling.

Since the CLI now uses simple-term-menu, the testing approach changes from
Textual's Pilot-based testing to simpler unit tests.
"""

import pytest
from unittest.mock import MagicMock, patch


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
                        "narrative_description": "Cooperate Action",
                        "action_type": "cooperative",
                        "resource_cost": 0,
                    },
                    {
                        "action_id": "defect",
                        "narrative_description": "Defect Action",
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
            for a in available_actions:
                if a.action_type == ActionType.COOPERATIVE:
                    return a
            return available_actions[0]

        async def evaluate_settlement(self, proposal, state, is_final_offer):
            return SettlementResponse(action="accept")

        async def propose_settlement(self, state):
            return None

    return MockOpponent(name="Mock")


class TestCLIGameFlow:
    """Tests for CLI game flow."""

    def test_game_initializes(self, mock_scenario_repo, mock_opponent):
        """Game should initialize with scenario and opponent."""
        from brinksmanship.cli.app import BrinksmanshipCLI

        with patch("brinksmanship.cli.app.get_scenario_repository", return_value=mock_scenario_repo):
            with patch("brinksmanship.cli.app.get_opponent_by_type", return_value=mock_opponent):
                cli = BrinksmanshipCLI()
                cli.repo = mock_scenario_repo

                # Manually initialize game components
                from brinksmanship.engine.game_engine import create_game
                cli.game = create_game("test-scenario", mock_scenario_repo)
                cli.opponent = mock_opponent
                cli.human_is_player_a = True
                cli.human_player = "A"
                cli.opponent_player = "B"

                assert cli.game is not None
                assert cli.opponent is not None

    def test_action_execution(self, mock_scenario_repo, mock_opponent):
        """Actions should be executed correctly."""
        from brinksmanship.cli.app import BrinksmanshipCLI, run_async
        from brinksmanship.engine.game_engine import create_game

        with patch("brinksmanship.cli.app.get_scenario_repository", return_value=mock_scenario_repo):
            with patch("brinksmanship.cli.app.get_opponent_by_type", return_value=mock_opponent):
                cli = BrinksmanshipCLI()
                cli.repo = mock_scenario_repo

                # Initialize game
                cli.game = create_game("test-scenario", mock_scenario_repo)
                cli.opponent = mock_opponent
                cli.human_is_player_a = True
                cli.human_player = "A"
                cli.opponent_player = "B"

                # Get initial state
                initial_turn = cli.game.get_current_state().turn

                # Get available actions
                actions = cli.game.get_available_actions("A")
                assert len(actions) > 0

                # Get opponent action
                state = cli.game.get_current_state()
                opponent_actions = cli.game.get_available_actions("B")
                opponent_action = run_async(
                    cli.opponent.choose_action(state, opponent_actions)
                )

                # Submit actions
                result = cli.game.submit_actions(actions[0], opponent_action)
                assert result.success

                # Turn should advance
                new_turn = cli.game.get_current_state().turn
                assert new_turn > initial_turn
