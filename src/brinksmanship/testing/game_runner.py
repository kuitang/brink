"""Unified game runner for Brinksmanship.

This module provides a single game runner that uses the actual GameEngine
and Opponent implementations. It serves as the foundation for:
- Balance simulations
- Playtesting
- Automated opponent testing

Key principle: One game runner, multiple controllers.
The GameEngine handles all game mechanics; this runner just orchestrates
the game loop between two Opponent instances.
"""

from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

from brinksmanship.engine.game_engine import (
    EndingType,
    GameEngine,
    GameEnding,
)
from brinksmanship.models.actions import Action, ActionType
from brinksmanship.models.state import GameState
from brinksmanship.opponents.base import Opponent, SettlementProposal
from brinksmanship.storage import get_scenario_repository

if TYPE_CHECKING:
    from brinksmanship.storage import ScenarioRepository


@dataclass
class GameResult:
    """Result of a completed game.

    Captures all relevant data for analysis and statistics.
    """

    winner: str  # "A", "B", "tie", or "mutual_destruction"
    ending_type: str
    turns_played: int
    final_pos_a: float
    final_pos_b: float
    final_res_a: float
    final_res_b: float
    final_risk: float
    final_cooperation: float
    final_stability: float
    vp_a: float
    vp_b: float
    history: list[tuple[str, str]]  # (action_a_name, action_b_name) per turn
    scenario_id: str
    opponent_a_name: str
    opponent_b_name: str

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "winner": self.winner,
            "ending_type": self.ending_type,
            "turns_played": self.turns_played,
            "final_pos_a": round(self.final_pos_a, 3),
            "final_pos_b": round(self.final_pos_b, 3),
            "final_res_a": round(self.final_res_a, 3),
            "final_res_b": round(self.final_res_b, 3),
            "final_risk": round(self.final_risk, 3),
            "final_cooperation": round(self.final_cooperation, 3),
            "final_stability": round(self.final_stability, 3),
            "vp_a": round(self.vp_a, 2),
            "vp_b": round(self.vp_b, 2),
            "history": self.history,
            "scenario_id": self.scenario_id,
            "opponent_a_name": self.opponent_a_name,
            "opponent_b_name": self.opponent_b_name,
        }


class GameRunner:
    """Runs a single game between two opponents using the real GameEngine.

    This class orchestrates a game between two Opponent instances, using
    the actual GameEngine for all game mechanics. It handles:
    - Async opponent action selection
    - Turn-by-turn game loop
    - Result collection

    Usage:
        opponent_a = NashCalculator()
        opponent_b = TitForTat()

        runner = GameRunner(
            scenario_id="cuban_missile_crisis",
            opponent_a=opponent_a,
            opponent_b=opponent_b,
        )

        result = await runner.run_game()
    """

    def __init__(
        self,
        scenario_id: str,
        opponent_a: Opponent,
        opponent_b: Opponent,
        repo: Optional[ScenarioRepository] = None,
        random_seed: Optional[int] = None,
    ):
        """Initialize the game runner.

        Args:
            scenario_id: ID of the scenario to use
            opponent_a: Opponent instance for player A
            opponent_b: Opponent instance for player B
            repo: Optional scenario repository (uses default if not provided)
            random_seed: Optional seed for reproducibility
        """
        self.scenario_id = scenario_id
        self.opponent_a = opponent_a
        self.opponent_b = opponent_b
        self.repo = repo or get_scenario_repository()
        self.random_seed = random_seed

        # Set player sides on opponents that support it
        if hasattr(opponent_a, "set_player_side"):
            opponent_a.set_player_side(is_player_a=True)
        if hasattr(opponent_b, "set_player_side"):
            opponent_b.set_player_side(is_player_a=False)

    async def run_game(self) -> GameResult:
        """Run a complete game between the two opponents.

        Returns:
            GameResult with all game data
        """
        # Create engine with optional seed
        engine = GameEngine(
            self.scenario_id,
            self.repo,
            random_seed=self.random_seed,
        )

        history: list[tuple[str, str]] = []
        settlement_ending: Optional[GameEnding] = None

        while not engine.is_game_over():
            state = engine.get_current_state()

            # Check for settlement opportunities (turn > 4 and stability > 2)
            if state.turn > 4 and state.stability > 2:
                settlement_ending = await self._try_settlement(state, engine)
                if settlement_ending:
                    break

            actions_a = engine.get_available_actions("A")
            actions_b = engine.get_available_actions("B")

            # Get actions from both opponents (async)
            action_a = await self.opponent_a.choose_action(state, actions_a)
            action_b = await self.opponent_b.choose_action(state, actions_b)

            # Record history
            history.append((action_a.name, action_b.name))

            # Submit actions to engine
            result = engine.submit_actions(action_a, action_b)

            # Notify opponents of result (for stateful strategies like GrimTrigger)
            if hasattr(self.opponent_a, "receive_result"):
                self.opponent_a.receive_result(result.action_result)
            if hasattr(self.opponent_b, "receive_result"):
                self.opponent_b.receive_result(result.action_result)

            if result.ending:
                break

        # Build result
        final_state = engine.get_current_state()
        ending = settlement_ending or engine.get_ending()

        return self._build_result(final_state, ending, history)

    async def _try_settlement(
        self,
        state: GameState,
        engine: GameEngine,
    ) -> Optional[GameEnding]:
        """Try settlement negotiation between opponents.

        Checks if either opponent wants to propose settlement, then
        evaluates the proposal. Returns GameEnding if settlement reached.
        """
        # Try A proposing to B, then B proposing to A
        for proposer, evaluator, proposer_is_a in [
            (self.opponent_a, self.opponent_b, True),
            (self.opponent_b, self.opponent_a, False),
        ]:
            ending = await self._negotiate_settlement(
                proposer, evaluator, proposer_is_a, state
            )
            if ending:
                return ending
        return None

    async def _negotiate_settlement(
        self,
        proposer: Opponent,
        evaluator: Opponent,
        proposer_is_a: bool,
        state: GameState,
    ) -> Optional[GameEnding]:
        """Handle settlement negotiation between proposer and evaluator."""
        if not hasattr(proposer, "propose_settlement"):
            return None

        proposal = await proposer.propose_settlement(state)
        if not proposal:
            return None

        if not hasattr(evaluator, "evaluate_settlement"):
            return None

        response = await evaluator.evaluate_settlement(proposal, state, is_final_offer=False)

        if response.action == "accept":
            # Proposer offers VP to evaluator
            if proposer_is_a:
                vp_b = proposal.offered_vp
                vp_a = 100 - vp_b
            else:
                vp_a = proposal.offered_vp
                vp_b = 100 - vp_a
            return GameEnding(
                ending_type=EndingType.SETTLEMENT,
                vp_a=vp_a,
                vp_b=vp_b,
                turn=state.turn,
                description="Settlement accepted",
            )

        if response.action == "counter" and response.counter_vp:
            # Counter-offer: evaluator offers back to proposer
            if not hasattr(proposer, "evaluate_settlement"):
                return None

            counter = SettlementProposal(
                offered_vp=response.counter_vp,
                argument=response.counter_argument or "",
            )
            counter_response = await proposer.evaluate_settlement(
                counter, state, is_final_offer=True
            )
            if counter_response.action == "accept":
                # Evaluator's counter-offer VP goes to proposer
                if proposer_is_a:
                    vp_a = counter.offered_vp
                    vp_b = 100 - vp_a
                else:
                    vp_b = counter.offered_vp
                    vp_a = 100 - vp_b
                return GameEnding(
                    ending_type=EndingType.SETTLEMENT,
                    vp_a=vp_a,
                    vp_b=vp_b,
                    turn=state.turn,
                    description="Counter-offer accepted",
                )

        return None

    def _build_result(
        self,
        final_state: GameState,
        ending: Optional[GameEnding],
        history: list[tuple[str, str]],
    ) -> GameResult:
        """Build a GameResult from the final state and ending."""
        if ending:
            vp_a = ending.vp_a
            vp_b = ending.vp_b
            ending_type = ending.ending_type.value

            if ending.ending_type == EndingType.MUTUAL_DESTRUCTION:
                winner = "mutual_destruction"
            elif vp_a > vp_b + 0.01:
                winner = "A"
            elif vp_b > vp_a + 0.01:
                winner = "B"
            else:
                winner = "tie"
        else:
            # Shouldn't happen, but handle gracefully
            vp_a, vp_b = 50.0, 50.0
            ending_type = "unknown"
            winner = "tie"

        return GameResult(
            winner=winner,
            ending_type=ending_type,
            turns_played=final_state.turn - 1,
            final_pos_a=final_state.position_a,
            final_pos_b=final_state.position_b,
            final_res_a=final_state.resources_a,
            final_res_b=final_state.resources_b,
            final_risk=final_state.risk_level,
            final_cooperation=final_state.cooperation_score,
            final_stability=final_state.stability,
            vp_a=vp_a,
            vp_b=vp_b,
            history=history,
            scenario_id=self.scenario_id,
            opponent_a_name=self.opponent_a.name,
            opponent_b_name=self.opponent_b.name,
        )


def run_game_sync(
    scenario_id: str,
    opponent_a: Opponent,
    opponent_b: Opponent,
    repo: Optional[ScenarioRepository] = None,
    random_seed: Optional[int] = None,
) -> GameResult:
    """Synchronous wrapper for running a single game.

    Useful for testing and batch processing where async isn't needed.

    Args:
        scenario_id: ID of the scenario to use
        opponent_a: Opponent instance for player A
        opponent_b: Opponent instance for player B
        repo: Optional scenario repository
        random_seed: Optional seed for reproducibility

    Returns:
        GameResult with all game data
    """
    runner = GameRunner(
        scenario_id=scenario_id,
        opponent_a=opponent_a,
        opponent_b=opponent_b,
        repo=repo,
        random_seed=random_seed,
    )
    return asyncio.run(runner.run_game())
