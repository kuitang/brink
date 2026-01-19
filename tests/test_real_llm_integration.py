"""Real LLM integration tests for Brinksmanship.

These tests make ACTUAL LLM calls to verify the full end-to-end flow.
They are slow and cost money, so they're marked with @pytest.mark.slow
and @pytest.mark.llm_integration.

Run with: uv run pytest tests/test_real_llm_integration.py -v -s

The tests exercise the same code paths as the CLI:
1. Create a game with a scenario
2. Get available actions
3. Have opponent choose an action (calls LLM for historical personas)
4. Submit actions and process turn
5. Repeat for multiple turns
"""

import asyncio
import pytest
import logging

from brinksmanship.engine import create_game
from brinksmanship.models.actions import ActionType
from brinksmanship.opponents import get_opponent_by_type
from brinksmanship.opponents.deterministic import NashCalculator, TitForTat
from brinksmanship.opponents.historical import HistoricalPersona
from brinksmanship.storage import get_scenario_repository
from brinksmanship.cli.app import run_opponent_method

# Enable logging to see what's happening
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@pytest.fixture
def scenario_repo():
    """Get the scenario repository."""
    return get_scenario_repository()


@pytest.fixture
def cuban_missile_game(scenario_repo):
    """Create a Cuban Missile Crisis game."""
    return create_game("cuban-missile-crisis", scenario_repo)


class TestRealLLMOpponentChooseAction:
    """Test opponent.choose_action with real LLM calls."""

    @pytest.mark.slow
    @pytest.mark.llm_integration
    def test_deterministic_opponent_choose_action(self, cuban_missile_game):
        """Test deterministic opponent (no LLM for action selection)."""
        game = cuban_missile_game
        opponent = NashCalculator()

        state = game.get_current_state()
        actions = game.get_available_actions("B")

        # Should work without LLM
        action = run_opponent_method(opponent.choose_action, state, actions)

        assert action is not None
        assert action.name in [a.name for a in actions]
        logger.info(f"NashCalculator chose: {action.name}")

    @pytest.mark.slow
    @pytest.mark.llm_integration
    def test_historical_persona_choose_action_khrushchev(self, cuban_missile_game, scenario_repo):
        """Test Khrushchev persona choosing an action (requires LLM)."""
        game = cuban_missile_game

        # Get scenario role information for Player B (the opponent)
        scenario = scenario_repo.get_scenario("cuban-missile-crisis")
        role_name = scenario.get("player_b_role", "Premier Khrushchev")
        role_description = scenario.get("player_b_description", "You are the Soviet leader.")

        opponent = get_opponent_by_type(
            "khrushchev",
            is_player_a=False,
            role_name=role_name,
            role_description=role_description,
        )

        state = game.get_current_state()
        actions = game.get_available_actions("B")

        logger.info(f"Testing Khrushchev with {len(actions)} available actions")
        logger.info(f"Actions: {[a.name for a in actions]}")
        logger.info(f"Role: {role_name}")
        logger.info(f"Role description: {role_description[:100]}...")

        # This calls the real LLM
        action = run_opponent_method(opponent.choose_action, state, actions)

        assert action is not None
        assert action.name in [a.name for a in actions]
        logger.info(f"Khrushchev chose: {action.name}")

    @pytest.mark.slow
    @pytest.mark.llm_integration
    def test_historical_persona_choose_action_bismarck(self, cuban_missile_game):
        """Test Bismarck persona choosing an action (requires LLM)."""
        game = cuban_missile_game
        opponent = get_opponent_by_type("bismarck")

        state = game.get_current_state()
        actions = game.get_available_actions("B")

        action = run_opponent_method(opponent.choose_action, state, actions)

        assert action is not None
        assert action.name in [a.name for a in actions]
        logger.info(f"Bismarck chose: {action.name}")


class TestRealLLMFullGameFlow:
    """Test full game flow with real LLM calls."""

    @pytest.mark.slow
    @pytest.mark.llm_integration
    def test_play_3_turns_with_tit_for_tat(self, cuban_missile_game):
        """Play 3 turns with TitForTat opponent (minimal LLM usage)."""
        game = cuban_missile_game
        opponent = TitForTat()

        for turn in range(3):
            state = game.get_current_state()
            logger.info(f"Turn {state.turn}: Risk={state.risk_level:.1f}")

            # Get actions
            player_actions = game.get_available_actions("A")
            opponent_actions = game.get_available_actions("B")

            # Player always cooperates
            player_action = next(
                (a for a in player_actions if a.action_type == ActionType.COOPERATIVE),
                player_actions[0]
            )

            # Opponent chooses (TitForTat doesn't need LLM for action)
            opponent_action = run_opponent_method(
                opponent.choose_action, state, opponent_actions
            )

            logger.info(f"Player: {player_action.name}, Opponent: {opponent_action.name}")

            # Submit actions
            result = game.submit_actions(player_action, opponent_action)
            assert result.success

            if result.ending:
                logger.info(f"Game ended: {result.ending.ending_type}")
                break

        logger.info("3 turns completed successfully")

    @pytest.mark.slow
    @pytest.mark.llm_integration
    def test_play_3_turns_with_khrushchev(self, cuban_missile_game):
        """Play 3 turns with Khrushchev opponent (real LLM calls)."""
        game = cuban_missile_game
        opponent = get_opponent_by_type("khrushchev")

        for turn in range(3):
            state = game.get_current_state()
            logger.info(f"Turn {state.turn}: Risk={state.risk_level:.1f}")

            # Get actions
            player_actions = game.get_available_actions("A")
            opponent_actions = game.get_available_actions("B")

            # Player always cooperates
            player_action = next(
                (a for a in player_actions if a.action_type == ActionType.COOPERATIVE),
                player_actions[0]
            )

            # Opponent chooses (this calls the real LLM!)
            logger.info("Calling LLM for Khrushchev's action...")
            opponent_action = run_opponent_method(
                opponent.choose_action, state, opponent_actions
            )

            logger.info(f"Player: {player_action.name}, Opponent: {opponent_action.name}")

            # Submit actions
            result = game.submit_actions(player_action, opponent_action)
            assert result.success, f"Turn failed: {result.error}"

            if result.ending:
                logger.info(f"Game ended: {result.ending.ending_type}")
                break

        logger.info("3 turns with Khrushchev completed successfully")


class TestRealLLMSettlementEvaluation:
    """Test settlement evaluation with real LLM calls."""

    @pytest.mark.slow
    @pytest.mark.llm_integration
    def test_deterministic_evaluate_settlement(self, cuban_missile_game):
        """Test deterministic opponent evaluating settlement (uses LLM)."""
        from brinksmanship.opponents.base import SettlementProposal

        game = cuban_missile_game
        opponent = NashCalculator()

        # Advance game past turn 4
        state = game.get_current_state()
        state.turn = 5
        state.stability = 5.0

        proposal = SettlementProposal(
            offered_vp=50,
            argument="A fair 50-50 split to end this crisis peacefully."
        )

        logger.info("Evaluating settlement proposal...")
        response = run_opponent_method(
            opponent.evaluate_settlement, proposal, state, False
        )

        assert response is not None
        assert response.action in ["accept", "counter", "reject"]
        logger.info(f"Settlement response: {response.action}")

    @pytest.mark.slow
    @pytest.mark.llm_integration
    def test_khrushchev_evaluate_settlement(self, cuban_missile_game):
        """Test Khrushchev evaluating settlement (uses LLM)."""
        from brinksmanship.opponents.base import SettlementProposal

        game = cuban_missile_game
        opponent = get_opponent_by_type("khrushchev")

        # Advance game past turn 4
        state = game.get_current_state()
        state.turn = 5
        state.stability = 5.0

        proposal = SettlementProposal(
            offered_vp=55,
            argument="We propose removing the missiles in exchange for a US non-invasion pledge."
        )

        logger.info("Khrushchev evaluating settlement proposal...")
        response = run_opponent_method(
            opponent.evaluate_settlement, proposal, state, False
        )

        assert response is not None
        assert response.action in ["accept", "counter", "reject"]
        logger.info(f"Khrushchev's response: {response.action}")
        if response.counter_vp:
            logger.info(f"Counter VP: {response.counter_vp}")
        if response.rejection_reason:
            logger.info(f"Rejection reason: {response.rejection_reason}")


if __name__ == "__main__":
    # Run specific test
    pytest.main([__file__, "-v", "-s", "-k", "test_historical_persona_choose_action_khrushchev"])
