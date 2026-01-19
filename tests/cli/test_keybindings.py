"""Tests for key bindings and loading modal in GameScreen."""

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
        def choose_action(self, state, available_actions):
            for a in available_actions:
                if a.action_type == ActionType.COOPERATIVE:
                    return a
            return available_actions[0]

        def evaluate_settlement(self, proposal, state, is_final_offer):
            return SettlementResponse(action="accept")

        def propose_settlement(self, state):
            return None

    return MockOpponent(name="Mock")


class TestNumberKeyBindings:
    """Tests for number key bindings in GameScreen."""

    @pytest.mark.asyncio
    async def test_number_key_1_triggers_action(self, mock_scenario_repo, mock_opponent):
        """Pressing '1' should trigger the first action and advance the turn."""
        from brinksmanship.cli.app import BrinksmanshipApp, GameScreen

        with patch("brinksmanship.cli.app.get_scenario_repository", return_value=mock_scenario_repo):
            with patch("brinksmanship.cli.app.get_opponent_by_type", return_value=mock_opponent):
                app = BrinksmanshipApp()
                async with app.run_test() as pilot:
                    game_screen = GameScreen("test-scenario", "mock")
                    app.push_screen(game_screen)

                    # Wait for initialization
                    for _ in range(10):
                        await pilot.pause()

                    assert game_screen.game is not None, "Game should be initialized"
                    assert len(game_screen.available_actions) > 0, "Should have available actions"

                    initial_turn = game_screen.game.get_current_state().turn

                    # Press key '1'
                    await pilot.press("1")

                    # Wait for async work to complete
                    for _ in range(10):
                        await pilot.pause()

                    new_turn = game_screen.game.get_current_state().turn
                    assert new_turn > initial_turn, "Turn should advance after pressing '1'"

    @pytest.mark.asyncio
    async def test_number_key_works_with_optionlist_focused(self, mock_scenario_repo, mock_opponent):
        """Number key should work even when OptionList has focus."""
        from brinksmanship.cli.app import BrinksmanshipApp, GameScreen
        from textual.widgets import OptionList

        with patch("brinksmanship.cli.app.get_scenario_repository", return_value=mock_scenario_repo):
            with patch("brinksmanship.cli.app.get_opponent_by_type", return_value=mock_opponent):
                app = BrinksmanshipApp()
                async with app.run_test() as pilot:
                    game_screen = GameScreen("test-scenario", "mock")
                    app.push_screen(game_screen)

                    for _ in range(10):
                        await pilot.pause()

                    # Focus the action list to simulate user clicking on it
                    action_list = game_screen.query_one("#action-list", OptionList)
                    action_list.focus()
                    await pilot.pause()

                    assert action_list.has_focus, "OptionList should have focus"

                    initial_turn = game_screen.game.get_current_state().turn
                    await pilot.press("1")

                    for _ in range(10):
                        await pilot.pause()

                    new_turn = game_screen.game.get_current_state().turn
                    assert new_turn > initial_turn, "Turn should advance even with OptionList focused"

    @pytest.mark.asyncio
    async def test_loading_modal_dismissed_after_action(self, mock_scenario_repo, mock_opponent):
        """Loading modal should be dismissed after action completes."""
        from brinksmanship.cli.app import BrinksmanshipApp, GameScreen, LoadingModal

        with patch("brinksmanship.cli.app.get_scenario_repository", return_value=mock_scenario_repo):
            with patch("brinksmanship.cli.app.get_opponent_by_type", return_value=mock_opponent):
                app = BrinksmanshipApp()
                async with app.run_test() as pilot:
                    game_screen = GameScreen("test-scenario", "mock")
                    app.push_screen(game_screen)

                    for _ in range(10):
                        await pilot.pause()

                    assert game_screen.game is not None

                    initial_turn = game_screen.game.get_current_state().turn
                    await pilot.press("1")

                    # Wait for action to complete
                    for _ in range(10):
                        await pilot.pause()

                    new_turn = game_screen.game.get_current_state().turn
                    assert new_turn > initial_turn, "Action should have advanced the turn"

                    # Verify we're back on the game screen (not the loading modal)
                    assert not isinstance(app.screen, LoadingModal), "Loading modal should be dismissed"
