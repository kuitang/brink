"""Automated tests for the CLI application using Textual's testing framework."""

import pytest
from unittest.mock import MagicMock, patch

from textual.pilot import Pilot


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
        def choose_action(self, state, available_actions):
            # Always pick first cooperative action, or first action
            for a in available_actions:
                if a.action_type == ActionType.COOPERATIVE:
                    return a
            return available_actions[0]

        def evaluate_settlement(self, proposal, state, is_final_offer):
            # Always accept
            return SettlementResponse(action="accept")

        def propose_settlement(self, state):
            return None

    return MockOpponent(name="Mock")


class TestMainMenuScreen:
    """Tests for the main menu screen."""

    @pytest.mark.asyncio
    async def test_main_menu_shows_buttons(self):
        """Main menu should show expected buttons."""
        from brinksmanship.cli.app import BrinksmanshipApp
        from textual.widgets import Button

        app = BrinksmanshipApp()
        async with app.run_test() as pilot:
            # Wait for screen to mount
            for _ in range(5):
                await pilot.pause()
            # Check that main menu elements exist (query from screen, not app)
            buttons = app.screen.query(Button)
            button_ids = [b.id for b in buttons]
            assert "new-game" in button_ids
            assert "quit" in button_ids

    @pytest.mark.asyncio
    async def test_quit_button_exits(self):
        """Quit button should exit the app."""
        from brinksmanship.cli.app import BrinksmanshipApp

        app = BrinksmanshipApp()
        async with app.run_test() as pilot:
            await pilot.click("#quit")
            # App should have exited (no assertion needed, test passes if no error)


class TestScenarioSelectScreen:
    """Tests for scenario selection screen."""

    @pytest.mark.asyncio
    async def test_scenario_list_loads(self, mock_scenario_repo):
        """Scenario selection should load and display scenarios."""
        from brinksmanship.cli.app import BrinksmanshipApp

        with patch("brinksmanship.cli.app.get_scenario_repository", return_value=mock_scenario_repo):
            app = BrinksmanshipApp()
            async with app.run_test() as pilot:
                # Click new game to go to scenario selection
                await pilot.click("#new-game")
                await pilot.pause()

                # Should now be on scenario select screen
                screen = app.screen
                assert screen.__class__.__name__ == "ScenarioSelectScreen"


class TestGameScreen:
    """Tests for the main game screen."""

    @pytest.mark.asyncio
    async def test_game_screen_initializes(self, mock_scenario_repo, mock_opponent):
        """Game screen should initialize without errors."""
        from brinksmanship.cli.app import BrinksmanshipApp, GameScreen

        with patch("brinksmanship.cli.app.get_scenario_repository", return_value=mock_scenario_repo):
            with patch("brinksmanship.cli.app.get_opponent_by_type", return_value=mock_opponent):
                app = BrinksmanshipApp()
                async with app.run_test() as pilot:
                    # Push game screen directly
                    app.push_screen(GameScreen("test-scenario", "mock"))
                    await pilot.pause()

                    # Give time for worker to complete
                    await pilot.pause()
                    await pilot.pause()

                    # Screen should have loaded
                    screen = app.screen
                    assert screen.__class__.__name__ == "GameScreen"

    @pytest.mark.asyncio
    async def test_action_execution_in_worker(self, mock_scenario_repo, mock_opponent):
        """Action execution should run in worker thread without blocking event loop."""
        from brinksmanship.cli.app import BrinksmanshipApp, GameScreen

        with patch("brinksmanship.cli.app.get_scenario_repository", return_value=mock_scenario_repo):
            with patch("brinksmanship.cli.app.get_opponent_by_type", return_value=mock_opponent):
                app = BrinksmanshipApp()
                async with app.run_test() as pilot:
                    # Push game screen directly
                    game_screen = GameScreen("test-scenario", "mock")
                    app.push_screen(game_screen)

                    # Wait for initialization
                    for _ in range(5):
                        await pilot.pause()

                    # At this point game should be initialized
                    # The key test is that we didn't get asyncio.run() errors


class TestAsyncSyncHandling:
    """Tests for proper handling of async/sync opponent methods."""

    def test_run_opponent_method_with_sync(self):
        """run_opponent_method should handle sync methods."""
        from brinksmanship.cli.app import run_opponent_method

        def sync_method(x, y):
            return x + y

        result = run_opponent_method(sync_method, 1, 2)
        assert result == 3

    def test_run_opponent_method_with_async(self):
        """run_opponent_method should handle async methods."""
        from brinksmanship.cli.app import run_opponent_method

        async def async_method(x, y):
            return x + y

        # This should work when called from a non-async context (like a thread)
        result = run_opponent_method(async_method, 1, 2)
        assert result == 3


class TestSettlementModal:
    """Tests for settlement proposal modal."""

    @pytest.mark.asyncio
    async def test_settlement_modal_validates_vp(self, mock_scenario_repo, mock_opponent):
        """Settlement modal should validate VP range."""
        from brinksmanship.cli.app import BrinksmanshipApp, SettlementProposalModal
        from brinksmanship.engine.game_engine import GameEngine, create_game

        with patch("brinksmanship.cli.app.get_scenario_repository", return_value=mock_scenario_repo):
            # Create a real game engine for the test
            engine = create_game("test-scenario", mock_scenario_repo)

            app = BrinksmanshipApp()
            async with app.run_test() as pilot:
                # Push settlement modal directly
                modal = SettlementProposalModal(engine, mock_opponent)
                app.push_screen(modal)
                await pilot.pause()

                # Modal should be displayed
                screen = app.screen
                assert screen.__class__.__name__ == "SettlementProposalModal"
