"""Tests for the CLI application."""

import pytest
from unittest.mock import MagicMock, patch

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
    from brinksmanship.models.actions import Action, ActionType
    from brinksmanship.opponents.base import Opponent, SettlementProposal, SettlementResponse

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
