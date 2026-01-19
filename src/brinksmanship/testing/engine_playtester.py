"""Engine-integrated playtester for Brinksmanship.

This module provides a playtester that uses the real GameEngine for game
simulation, supporting scenario loading and full game mechanics.

Unlike the simplified playtester in playtester.py (which uses hardcoded
Prisoner's Dilemma mechanics), this version:
- Loads scenarios from JSON files via ScenarioRepository
- Uses the full GameEngine with 8-phase turn structure
- Supports all matrix types (Chicken, Stag Hunt, etc.)
- Handles special actions (Reconnaissance, Inspection, Settlement)
- Tracks full InformationState

See ENGINEERING_DESIGN.md Milestone 5.2 for specifications.
"""

from __future__ import annotations

import json
import random
import statistics
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Literal, Optional

from brinksmanship.engine.game_engine import (
    EndingType,
    GameEngine,
    GameEnding,
    TurnResult,
)
from brinksmanship.models.actions import Action, ActionType
from brinksmanship.models.state import GameState
from brinksmanship.opponents.base import Opponent
from brinksmanship.storage import get_scenario_repository


# Type alias for engine-compatible strategy
# Takes full GameState and list of Actions, returns Action
EngineStrategy = Callable[[GameState, list[Action]], Action]


@dataclass
class EngineGameResult:
    """Result of a single game run through the engine.

    Attributes:
        winner: "A", "B", "tie", or "mutual_destruction"
        ending_type: How the game ended
        turns_played: Number of turns completed
        final_state: Final game state
        vp_a: Victory points for player A
        vp_b: Victory points for player B
        history: List of (action_a_name, action_b_name) tuples per turn
        scenario_id: ID of the scenario used
    """

    winner: str
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
    history: list[tuple[str, str]]
    scenario_id: str

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
        }


@dataclass
class EnginePairingStats:
    """Statistics for a single strategy pairing using engine."""

    wins_a: int = 0
    wins_b: int = 0
    ties: int = 0
    mutual_destructions: int = 0
    crisis_terminations: int = 0
    eliminations: int = 0
    natural_endings: int = 0
    settlements: int = 0
    total_games: int = 0
    total_turns: int = 0
    vp_a_list: list[float] = field(default_factory=list)
    vp_b_list: list[float] = field(default_factory=list)

    def add_result(self, result: EngineGameResult) -> None:
        """Add a game result to the statistics."""
        self.total_games += 1
        self.total_turns += result.turns_played
        self.vp_a_list.append(result.vp_a)
        self.vp_b_list.append(result.vp_b)

        # Track winner
        if result.winner == "A":
            self.wins_a += 1
        elif result.winner == "B":
            self.wins_b += 1
        elif result.winner == "tie":
            self.ties += 1

        # Track ending types
        if result.ending_type == "mutual_destruction":
            self.mutual_destructions += 1
        elif result.ending_type == "crisis_termination":
            self.crisis_terminations += 1
        elif result.ending_type == "natural_ending":
            self.natural_endings += 1
        elif result.ending_type == "settlement":
            self.settlements += 1
        elif "collapse" in result.ending_type or "exhaustion" in result.ending_type:
            self.eliminations += 1

    @property
    def win_rate_a(self) -> float:
        if self.total_games == 0:
            return 0.0
        return self.wins_a / self.total_games

    @property
    def win_rate_b(self) -> float:
        if self.total_games == 0:
            return 0.0
        return self.wins_b / self.total_games

    @property
    def avg_game_length(self) -> float:
        if self.total_games == 0:
            return 0.0
        return self.total_turns / self.total_games

    @property
    def avg_vp_a(self) -> float:
        if not self.vp_a_list:
            return 0.0
        return statistics.mean(self.vp_a_list)

    @property
    def avg_vp_b(self) -> float:
        if not self.vp_b_list:
            return 0.0
        return statistics.mean(self.vp_b_list)

    @property
    def vp_std_a(self) -> float:
        if len(self.vp_a_list) < 2:
            return 0.0
        return statistics.stdev(self.vp_a_list)

    @property
    def vp_std_b(self) -> float:
        if len(self.vp_b_list) < 2:
            return 0.0
        return statistics.stdev(self.vp_b_list)

    @property
    def settlement_rate(self) -> float:
        if self.total_games == 0:
            return 0.0
        return self.settlements / self.total_games

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "wins_a": self.wins_a,
            "wins_b": self.wins_b,
            "ties": self.ties,
            "mutual_destructions": self.mutual_destructions,
            "crisis_terminations": self.crisis_terminations,
            "eliminations": self.eliminations,
            "natural_endings": self.natural_endings,
            "settlements": self.settlements,
            "total_games": self.total_games,
            "total_turns": self.total_turns,
            "win_rate_a": round(self.win_rate_a, 4),
            "win_rate_b": round(self.win_rate_b, 4),
            "avg_game_length": round(self.avg_game_length, 2),
            "avg_vp_a": round(self.avg_vp_a, 2),
            "avg_vp_b": round(self.avg_vp_b, 2),
            "vp_std_a": round(self.vp_std_a, 2),
            "vp_std_b": round(self.vp_std_b, 2),
            "settlement_rate": round(self.settlement_rate, 4),
        }


@dataclass
class EnginePlaytestResults:
    """Results from engine-based playtest."""

    pairings: dict[str, EnginePairingStats] = field(default_factory=dict)
    aggregate: dict[str, float] = field(default_factory=dict)
    logs: list[str] = field(default_factory=list)
    scenario_id: str = ""
    timestamp: str = ""
    duration_seconds: float = 0.0

    def compute_aggregate(self) -> None:
        """Compute aggregate statistics across all pairings."""
        if not self.pairings:
            return

        all_vp_a = []
        all_vp_b = []
        total_games = 0
        total_turns = 0
        total_settlements = 0

        for stats in self.pairings.values():
            all_vp_a.extend(stats.vp_a_list)
            all_vp_b.extend(stats.vp_b_list)
            total_games += stats.total_games
            total_turns += stats.total_turns
            total_settlements += stats.settlements

        if total_games > 0:
            self.aggregate = {
                "total_games": total_games,
                "avg_turns": round(total_turns / total_games, 2),
                "avg_vp_a": round(statistics.mean(all_vp_a), 2) if all_vp_a else 0,
                "avg_vp_b": round(statistics.mean(all_vp_b), 2) if all_vp_b else 0,
                "vp_std_dev": round(statistics.stdev(all_vp_a + all_vp_b), 2) if len(all_vp_a) > 1 else 0,
                "settlement_rate": round(total_settlements / total_games, 4),
            }

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "pairings": {k: v.to_dict() for k, v in self.pairings.items()},
            "aggregate": self.aggregate,
            "logs": self.logs,
            "scenario_id": self.scenario_id,
            "timestamp": self.timestamp,
            "duration_seconds": round(self.duration_seconds, 2),
        }

    def to_json(self, indent: int = 2) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)


# =============================================================================
# Built-in Engine-Compatible Strategies
# =============================================================================


def engine_tit_for_tat(state: GameState, actions: list[Action]) -> Action:
    """TitForTat: cooperate first, then mirror opponent's last type."""
    # Check opponent's previous action type
    opponent_prev = state.previous_type_b if state.previous_type_a is None else state.previous_type_a

    # Find cooperative and competitive actions
    cooperative = [a for a in actions if a.action_type == ActionType.COOPERATIVE]
    competitive = [a for a in actions if a.action_type == ActionType.COMPETITIVE]

    if opponent_prev is None or opponent_prev == ActionType.COOPERATIVE:
        # Cooperate
        return cooperative[0] if cooperative else actions[0]
    else:
        # Mirror defection
        return competitive[0] if competitive else actions[0]


def engine_always_cooperate(state: GameState, actions: list[Action]) -> Action:
    """AlwaysCooperate: always choose cooperative action."""
    cooperative = [a for a in actions if a.action_type == ActionType.COOPERATIVE]
    return cooperative[0] if cooperative else actions[0]


def engine_always_defect(state: GameState, actions: list[Action]) -> Action:
    """AlwaysDefect: always choose competitive action."""
    competitive = [a for a in actions if a.action_type == ActionType.COMPETITIVE]
    return competitive[0] if competitive else actions[0]


def engine_opportunist(state: GameState, actions: list[Action]) -> Action:
    """Opportunist: defect when ahead, cooperate when behind."""
    pos_diff = state.position_a - state.position_b

    cooperative = [a for a in actions if a.action_type == ActionType.COOPERATIVE]
    competitive = [a for a in actions if a.action_type == ActionType.COMPETITIVE]

    # Risk awareness
    if state.risk_level >= 7:
        return cooperative[0] if cooperative else actions[0]

    if pos_diff > 1:
        return competitive[0] if competitive else actions[0]
    elif pos_diff < -1:
        return cooperative[0] if cooperative else actions[0]
    else:
        # Early game: cooperate; late game: defect
        if state.turn <= 6:
            return cooperative[0] if cooperative else actions[0]
        else:
            return competitive[0] if competitive else actions[0]


def engine_nash(state: GameState, actions: list[Action]) -> Action:
    """Nash: play Nash equilibrium (defect) with risk awareness."""
    competitive = [a for a in actions if a.action_type == ActionType.COMPETITIVE]
    cooperative = [a for a in actions if a.action_type == ActionType.COOPERATIVE]

    if state.risk_level >= 8:
        return cooperative[0] if cooperative else actions[0]
    return competitive[0] if competitive else actions[0]


def engine_random(state: GameState, actions: list[Action]) -> Action:
    """Random: uniform random choice."""
    return random.choice(actions)


ENGINE_STRATEGIES: dict[str, EngineStrategy] = {
    "TitForTat": engine_tit_for_tat,
    "AlwaysCooperate": engine_always_cooperate,
    "AlwaysDefect": engine_always_defect,
    "Opportunist": engine_opportunist,
    "Nash": engine_nash,
    "Random": engine_random,
}


# =============================================================================
# Opponent Adapter
# =============================================================================


class StrategyAdapter(Opponent):
    """Adapts an EngineStrategy function to the Opponent interface.

    This allows using simple strategy functions with the game engine
    while implementing the full Opponent interface.
    """

    def __init__(self, strategy: EngineStrategy, name: str = "Strategy"):
        super().__init__(name=name)
        self._strategy = strategy

    def choose_action(self, state: GameState, available_actions: list[Action]) -> Action:
        """Choose action using the wrapped strategy function."""
        return self._strategy(state, available_actions)

    def evaluate_settlement(self, proposal, state, is_final_offer):
        """Simple settlement evaluation - accept if fair."""
        from brinksmanship.opponents.base import SettlementResponse

        fair_vp = self.get_position_fair_vp(state, is_player_a=True)
        offered_to_me = 100 - proposal.offered_vp

        if offered_to_me >= fair_vp - 5:
            return SettlementResponse(action="accept")
        elif is_final_offer:
            return SettlementResponse(action="reject", rejection_reason="Unfair offer")
        else:
            return SettlementResponse(
                action="counter",
                counter_vp=fair_vp,
                counter_argument="Fair split based on positions"
            )

    def propose_settlement(self, state):
        """Don't propose settlements - let strategies focus on actions."""
        return None


# =============================================================================
# Engine Game Runner
# =============================================================================


def run_engine_game(
    scenario_id: str,
    strategy_a: EngineStrategy,
    strategy_b: EngineStrategy,
    seed: Optional[int] = None,
) -> EngineGameResult:
    """Run a single game using the real game engine.

    Args:
        scenario_id: ID of scenario to use
        strategy_a: Strategy function for player A
        strategy_b: Strategy function for player B
        seed: Random seed for reproducibility

    Returns:
        EngineGameResult with full game data
    """
    repo = get_scenario_repository()
    engine = GameEngine(scenario_id, repo, random_seed=seed)

    history = []

    while not engine.is_game_over():
        state = engine.get_current_state()
        actions_a = engine.get_available_actions("A")
        actions_b = engine.get_available_actions("B")

        # Get strategy decisions
        action_a = strategy_a(state, actions_a)
        action_b = strategy_b(state, actions_b)

        # Record history
        history.append((action_a.name, action_b.name))

        # Submit actions
        result = engine.submit_actions(action_a, action_b)

        if result.ending:
            break

    # Get final state and ending
    final_state = engine.get_current_state()
    ending = engine.get_ending()

    if ending:
        vp_a = ending.vp_a
        vp_b = ending.vp_b
        ending_type = ending.ending_type.value

        if vp_a > vp_b + 0.01:
            winner = "A"
        elif vp_b > vp_a + 0.01:
            winner = "B"
        else:
            winner = "tie"

        if ending.ending_type == EndingType.MUTUAL_DESTRUCTION:
            winner = "mutual_destruction"
    else:
        # Shouldn't happen, but handle gracefully
        vp_a, vp_b = 50.0, 50.0
        ending_type = "unknown"
        winner = "tie"

    return EngineGameResult(
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
        scenario_id=scenario_id,
    )


# =============================================================================
# Engine Playtest Runner
# =============================================================================


class EnginePlaytestRunner:
    """Playtest runner that uses the real game engine with scenarios.

    Unlike PlaytestRunner which uses simplified simulation, this version:
    - Loads scenarios from the repository
    - Uses full GameEngine mechanics
    - Supports all matrix types and special actions
    """

    def __init__(self, scenario_id: str):
        """Initialize with a scenario.

        Args:
            scenario_id: ID of scenario to use for all games
        """
        self.scenario_id = scenario_id
        self._custom_strategies: dict[str, EngineStrategy] = {}

    def register_strategy(self, name: str, strategy: EngineStrategy) -> None:
        """Register a custom strategy function."""
        self._custom_strategies[name] = strategy

    def get_strategy(self, name: str) -> EngineStrategy:
        """Get a strategy by name."""
        if name in self._custom_strategies:
            return self._custom_strategies[name]
        if name in ENGINE_STRATEGIES:
            return ENGINE_STRATEGIES[name]
        raise ValueError(f"Unknown strategy: {name}")

    def list_strategies(self) -> list[str]:
        """List all available strategy names."""
        return list(ENGINE_STRATEGIES.keys()) + list(self._custom_strategies.keys())

    def run_pairing(
        self,
        strategy_a: str | EngineStrategy,
        strategy_b: str | EngineStrategy,
        num_games: int = 100,
        seed: Optional[int] = None,
    ) -> EnginePairingStats:
        """Run games between two strategies using the engine.

        Args:
            strategy_a: Strategy name or function for player A
            strategy_b: Strategy name or function for player B
            num_games: Number of games to run
            seed: Base random seed for reproducibility

        Returns:
            EnginePairingStats with aggregated statistics
        """
        # Resolve strategies
        if isinstance(strategy_a, str):
            strat_a = self.get_strategy(strategy_a)
        else:
            strat_a = strategy_a

        if isinstance(strategy_b, str):
            strat_b = self.get_strategy(strategy_b)
        else:
            strat_b = strategy_b

        stats = EnginePairingStats()

        for i in range(num_games):
            game_seed = (seed + i) if seed is not None else None
            result = run_engine_game(
                self.scenario_id, strat_a, strat_b, seed=game_seed
            )
            stats.add_result(result)

        return stats

    def run_playtest(
        self,
        pairings: list[tuple[str, str]],
        games_per_pairing: int = 100,
        output_dir: str = "playtest_results",
        seed: Optional[int] = None,
        save_logs: bool = False,
    ) -> EnginePlaytestResults:
        """Run full playtest with multiple pairings.

        Args:
            pairings: List of (strategy_a_name, strategy_b_name) tuples
            games_per_pairing: Number of games per pairing
            output_dir: Directory for output files
            seed: Base random seed
            save_logs: Whether to save individual game logs

        Returns:
            EnginePlaytestResults with all statistics
        """
        import datetime

        start_time = time.time()
        timestamp = datetime.datetime.now().isoformat()

        results = EnginePlaytestResults(
            scenario_id=self.scenario_id,
            timestamp=timestamp,
        )
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        for idx, (strat_a, strat_b) in enumerate(pairings):
            pairing_name = f"{strat_a}:{strat_b}"
            pairing_seed = (seed + idx * games_per_pairing) if seed is not None else None

            stats = self.run_pairing(strat_a, strat_b, games_per_pairing, pairing_seed)
            results.pairings[pairing_name] = stats

        # Compute aggregates
        results.compute_aggregate()
        results.duration_seconds = time.time() - start_time

        # Save results
        results_path = output_path / "engine_playtest_results.json"
        with open(results_path, "w") as f:
            f.write(results.to_json())

        return results

    def run_all_pairings(
        self,
        strategies: Optional[list[str]] = None,
        games_per_pairing: int = 100,
        output_dir: str = "playtest_results",
        seed: Optional[int] = None,
    ) -> EnginePlaytestResults:
        """Run playtest for all unique pairings of given strategies."""
        if strategies is None:
            strategies = list(ENGINE_STRATEGIES.keys())

        # Generate all unique pairings (including self-play)
        pairings = []
        for i, strat_a in enumerate(strategies):
            for strat_b in strategies[i:]:
                pairings.append((strat_a, strat_b))

        return self.run_playtest(
            pairings,
            games_per_pairing=games_per_pairing,
            output_dir=output_dir,
            seed=seed,
        )


# =============================================================================
# CLI Interface
# =============================================================================


def main():
    """Command-line interface for engine-based playtests."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Run Brinksmanship playtests using the game engine"
    )
    parser.add_argument(
        "--scenario",
        type=str,
        required=True,
        help="Scenario ID to use",
    )
    parser.add_argument(
        "--strategies",
        type=str,
        default=None,
        help="Comma-separated list of strategies (default: all)",
    )
    parser.add_argument(
        "--pairings",
        type=str,
        default=None,
        help="Explicit pairings as 'A:B,C:D' (overrides --strategies)",
    )
    parser.add_argument(
        "--games",
        type=int,
        default=100,
        help="Number of games per pairing (default: 100)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="playtest_results",
        help="Output directory (default: playtest_results)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Random seed for reproducibility",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress output summary",
    )

    args = parser.parse_args()

    runner = EnginePlaytestRunner(args.scenario)

    if args.pairings:
        # Parse explicit pairings
        pairings = []
        for p in args.pairings.split(","):
            parts = p.strip().split(":")
            if len(parts) != 2:
                raise ValueError(f"Invalid pairing format: {p}")
            pairings.append((parts[0].strip(), parts[1].strip()))

        results = runner.run_playtest(
            pairings,
            games_per_pairing=args.games,
            output_dir=args.output,
            seed=args.seed,
        )
    else:
        strategies = None
        if args.strategies:
            strategies = [s.strip() for s in args.strategies.split(",")]

        results = runner.run_all_pairings(
            strategies=strategies,
            games_per_pairing=args.games,
            output_dir=args.output,
            seed=args.seed,
        )

    if not args.quiet:
        print(f"\nPlaytest completed in {results.duration_seconds:.2f} seconds")
        print(f"Scenario: {results.scenario_id}")
        print(f"Total games: {results.aggregate.get('total_games', 0)}")
        print(f"Average turns: {results.aggregate.get('avg_turns', 0):.1f}")
        print(f"Settlement rate: {results.aggregate.get('settlement_rate', 0):.1%}")
        print(f"\nResults saved to: {args.output}/engine_playtest_results.json")

    return results


if __name__ == "__main__":
    main()
