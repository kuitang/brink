"""Playtester Framework for Brinksmanship.

This module implements automated playtesting for game balance validation.
It is a pure Python module with no agentic orchestration - parallelism is
achieved through Python's multiprocessing, not LLM subagents.

Key classes:
- PlaytestRunner: Orchestrates batch game execution
- PairingStats: Statistics for a single strategy pairing
- PlaytestResults: Aggregate results from a full playtest run

See ENGINEERING_DESIGN.md Milestone 5.2 for specifications.
"""

from __future__ import annotations

import json
import random
import statistics
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Callable, Optional
import time


class EndingType(Enum):
    """How a game ended."""

    MAX_TURNS = "max_turns"
    POSITION_LOSS_A = "position_loss_a"
    POSITION_LOSS_B = "position_loss_b"
    RESOURCE_LOSS_A = "resource_loss_a"
    RESOURCE_LOSS_B = "resource_loss_b"
    MUTUAL_DESTRUCTION = "mutual_destruction"
    CRISIS_TERMINATION = "crisis_termination"
    SETTLEMENT = "settlement"


class ActionChoice(Enum):
    """Simple action choice for strategies."""

    COOPERATE = "C"
    DEFECT = "D"


@dataclass
class SimplePlayerState:
    """Simplified player state for simulation.

    Uses the same mechanics as brinksmanship.models.PlayerState but
    optimized for fast simulation without Pydantic overhead.
    """

    position: float = 5.0
    resources: float = 5.0
    previous_type: Optional[ActionChoice] = None

    def clamp(self) -> None:
        """Clamp values to valid ranges."""
        self.position = max(0.0, min(10.0, self.position))
        self.resources = max(0.0, min(10.0, self.resources))


@dataclass
class SimpleGameState:
    """Simplified game state for fast simulation.

    Captures the essential state variables without Pydantic overhead.
    """

    player_a: SimplePlayerState = field(default_factory=SimplePlayerState)
    player_b: SimplePlayerState = field(default_factory=SimplePlayerState)
    cooperation_score: float = 5.0
    stability: float = 5.0
    risk_level: float = 2.0
    turn: int = 1
    max_turns: int = 14
    history_a: list[ActionChoice] = field(default_factory=list)
    history_b: list[ActionChoice] = field(default_factory=list)

    def clamp(self) -> None:
        """Clamp all values to valid ranges."""
        self.player_a.clamp()
        self.player_b.clamp()
        self.cooperation_score = max(0.0, min(10.0, self.cooperation_score))
        self.stability = max(1.0, min(10.0, self.stability))
        self.risk_level = max(0.0, min(10.0, self.risk_level))

    def get_act_multiplier(self) -> float:
        """Return act scaling based on turn number.

        From GAME_MANUAL.md:
        - Act I (turns 1-4): 0.7
        - Act II (turns 5-8): 1.0
        - Act III (turns 9+): 1.3
        """
        if self.turn <= 4:
            return 0.7
        elif self.turn <= 8:
            return 1.0
        else:
            return 1.3


# Type alias for strategy functions
Strategy = Callable[[SimpleGameState, list[ActionChoice], list[ActionChoice], str], ActionChoice]


def apply_outcome(
    state: SimpleGameState,
    action_a: ActionChoice,
    action_b: ActionChoice,
    add_noise: bool = True
) -> None:
    """Apply outcome based on actions using Prisoner's Dilemma state deltas.

    State deltas from GAME_MANUAL.md Section 3.5:
    - CC: pos_a +0.5, pos_b +0.5, risk -0.5
    - CD: pos_a -1.0, pos_b +1.0, risk +0.5
    - DC: pos_a +1.0, pos_b -1.0, risk +0.5
    - DD: pos_a -0.3, pos_b -0.3, resource_cost 0.5 each, risk +1.0

    Args:
        state: Current game state (modified in place)
        action_a: Action from player A
        action_b: Action from player B
        add_noise: If True, add small random variance (+/- 10%)
    """
    multiplier = state.get_act_multiplier()
    noise_factor = random.uniform(0.9, 1.1) if add_noise else 1.0

    if action_a == ActionChoice.COOPERATE and action_b == ActionChoice.COOPERATE:
        # CC: Mutual cooperation
        state.player_a.position += 0.5 * multiplier * noise_factor
        state.player_b.position += 0.5 * multiplier * noise_factor
        state.risk_level -= 0.5 * multiplier * noise_factor
        state.cooperation_score += 1.0
    elif action_a == ActionChoice.COOPERATE and action_b == ActionChoice.DEFECT:
        # CD: A exploited
        state.player_a.position -= 1.0 * multiplier * noise_factor
        state.player_b.position += 1.0 * multiplier * noise_factor
        state.risk_level += 0.5 * multiplier * noise_factor
    elif action_a == ActionChoice.DEFECT and action_b == ActionChoice.COOPERATE:
        # DC: B exploited
        state.player_a.position += 1.0 * multiplier * noise_factor
        state.player_b.position -= 1.0 * multiplier * noise_factor
        state.risk_level += 0.5 * multiplier * noise_factor
    else:  # DD
        # Mutual defection
        state.player_a.position -= 0.3 * multiplier * noise_factor
        state.player_b.position -= 0.3 * multiplier * noise_factor
        state.player_a.resources -= 0.5 * multiplier * noise_factor
        state.player_b.resources -= 0.5 * multiplier * noise_factor
        state.risk_level += 1.0 * multiplier * noise_factor
        state.cooperation_score -= 1.0

    # Update stability based on switches (from GAME_MANUAL.md Section 5.2)
    switches = 0
    if state.player_a.previous_type is not None and action_a != state.player_a.previous_type:
        switches += 1
    if state.player_b.previous_type is not None and action_b != state.player_b.previous_type:
        switches += 1

    # Decay toward neutral (5) plus consistency bonus/penalty
    state.stability = state.stability * 0.8 + 1.0
    if switches == 0:
        state.stability += 1.5
    elif switches == 1:
        state.stability -= 3.5
    else:
        state.stability -= 5.5

    # Update previous types
    state.player_a.previous_type = action_a
    state.player_b.previous_type = action_b

    state.clamp()


def check_crisis_termination(state: SimpleGameState) -> bool:
    """Check if crisis terminates this turn (probabilistic).

    From GAME_MANUAL.md:
    - Only checked for Turn >= 10 and Risk > 7
    - P(termination) = (Risk - 7) * 0.08
    """
    if state.turn < 10 or state.risk_level <= 7:
        return False

    p_termination = (state.risk_level - 7) * 0.08
    return random.random() < p_termination


def check_ending(state: SimpleGameState) -> Optional[EndingType]:
    """Check if game has ended.

    Checks in order:
    1. Mutual destruction (risk = 10)
    2. Position losses
    3. Resource losses
    4. Crisis termination (probabilistic, Turn >= 10, Risk > 7)
    5. Max turns
    """
    # Check mutual destruction (risk = 10)
    if state.risk_level >= 10.0:
        return EndingType.MUTUAL_DESTRUCTION

    # Check position losses
    if state.player_a.position <= 0:
        return EndingType.POSITION_LOSS_A
    if state.player_b.position <= 0:
        return EndingType.POSITION_LOSS_B

    # Check resource losses
    if state.player_a.resources <= 0:
        return EndingType.RESOURCE_LOSS_A
    if state.player_b.resources <= 0:
        return EndingType.RESOURCE_LOSS_B

    # Check crisis termination
    if check_crisis_termination(state):
        return EndingType.CRISIS_TERMINATION

    # Check max turns
    if state.turn > state.max_turns:
        return EndingType.MAX_TURNS

    return None


def final_resolution(state: SimpleGameState) -> tuple[float, float]:
    """Calculate final VP scores using variance formula.

    From GAME_MANUAL.md Section 4.3:
    - Expected value from position ratio
    - Symmetric noise application
    - Clamp and renormalize to sum to 100

    Returns:
        Tuple of (vp_a, vp_b)
    """
    total_pos = state.player_a.position + state.player_b.position
    if total_pos == 0:
        ev_a = 50.0
    else:
        ev_a = (state.player_a.position / total_pos) * 100.0
    ev_b = 100.0 - ev_a

    # Calculate shared variance
    base_sigma = 8.0 + (state.risk_level * 1.2)
    chaos_factor = 1.2 - (state.cooperation_score / 50.0)
    instability_factor = 1.0 + (10.0 - state.stability) / 20.0
    act_multiplier = 1.3  # Act III for final resolution

    shared_sigma = base_sigma * chaos_factor * instability_factor * act_multiplier

    # Symmetric noise
    noise = random.gauss(0, shared_sigma)

    vp_a_raw = ev_a + noise
    vp_b_raw = ev_b - noise

    # Clamp and renormalize
    vp_a_clamped = max(5.0, min(95.0, vp_a_raw))
    vp_b_clamped = max(5.0, min(95.0, vp_b_raw))

    total = vp_a_clamped + vp_b_clamped
    vp_a = vp_a_clamped * 100.0 / total
    vp_b = vp_b_clamped * 100.0 / total

    return vp_a, vp_b


# =============================================================================
# Built-in Strategies
# =============================================================================

def tit_for_tat(
    state: SimpleGameState,
    my_history: list[ActionChoice],
    opp_history: list[ActionChoice],
    player: str
) -> ActionChoice:
    """TitForTat: cooperate first, then mirror opponent's last move."""
    if not opp_history:
        return ActionChoice.COOPERATE
    return opp_history[-1]


def always_defect(
    state: SimpleGameState,
    my_history: list[ActionChoice],
    opp_history: list[ActionChoice],
    player: str
) -> ActionChoice:
    """AlwaysDefect: always defect."""
    return ActionChoice.DEFECT


def always_cooperate(
    state: SimpleGameState,
    my_history: list[ActionChoice],
    opp_history: list[ActionChoice],
    player: str
) -> ActionChoice:
    """AlwaysCooperate: always cooperate."""
    return ActionChoice.COOPERATE


def opportunist(
    state: SimpleGameState,
    my_history: list[ActionChoice],
    opp_history: list[ActionChoice],
    player: str
) -> ActionChoice:
    """Opportunist: defect when ahead in position, cooperate when behind.

    Also considers resources and risk for more nuanced decisions.
    """
    if player == "A":
        my_pos = state.player_a.position
        opp_pos = state.player_b.position
        my_res = state.player_a.resources
    else:
        my_pos = state.player_b.position
        opp_pos = state.player_a.position
        my_res = state.player_b.resources

    # Risk-aware: if risk is high, be more cautious
    if state.risk_level >= 7:
        return ActionChoice.COOPERATE

    # Resource-aware: if low on resources, avoid DD (costs resources)
    if my_res <= 2:
        return ActionChoice.COOPERATE

    pos_advantage = my_pos - opp_pos

    if pos_advantage > 1.0:
        return ActionChoice.DEFECT
    elif pos_advantage < -1.0:
        return ActionChoice.COOPERATE
    else:
        # When roughly equal, cooperate early, defect late
        if state.turn <= 6:
            return ActionChoice.COOPERATE
        else:
            return ActionChoice.DEFECT


def nash_equilibrium(
    state: SimpleGameState,
    my_history: list[ActionChoice],
    opp_history: list[ActionChoice],
    player: str
) -> ActionChoice:
    """Nash: play Nash equilibrium (defect in PD).

    But with risk-awareness: if risk is very high, cooperate to avoid mutual destruction.
    """
    if state.risk_level >= 8:
        return ActionChoice.COOPERATE
    return ActionChoice.DEFECT


def grim_trigger(
    state: SimpleGameState,
    my_history: list[ActionChoice],
    opp_history: list[ActionChoice],
    player: str
) -> ActionChoice:
    """GrimTrigger: cooperate until opponent defects, then defect forever."""
    if ActionChoice.DEFECT in opp_history:
        return ActionChoice.DEFECT
    return ActionChoice.COOPERATE


def random_strategy(
    state: SimpleGameState,
    my_history: list[ActionChoice],
    opp_history: list[ActionChoice],
    player: str
) -> ActionChoice:
    """Random: 50/50 mix of cooperate and defect."""
    return random.choice([ActionChoice.COOPERATE, ActionChoice.DEFECT])


# Registry of built-in strategies
STRATEGIES: dict[str, Strategy] = {
    "TitForTat": tit_for_tat,
    "AlwaysDefect": always_defect,
    "AlwaysCooperate": always_cooperate,
    "Opportunist": opportunist,
    "Nash": nash_equilibrium,
    "GrimTrigger": grim_trigger,
    "Random": random_strategy,
}


# =============================================================================
# Game Result Data Structures
# =============================================================================

@dataclass
class GameResult:
    """Result of a single game."""

    winner: str  # "A", "B", "tie", or "mutual_destruction"
    ending_type: EndingType
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
    history_a: list[str]
    history_b: list[str]

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "winner": self.winner,
            "ending_type": self.ending_type.value,
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
            "history_a": self.history_a,
            "history_b": self.history_b,
        }


@dataclass
class PairingStats:
    """Statistics for a single strategy pairing.

    Tracks win rates, VP distributions, and game outcomes.
    """

    wins_a: int = 0
    wins_b: int = 0
    ties: int = 0
    mutual_destructions: int = 0
    crisis_terminations: int = 0
    eliminations: int = 0
    max_turns_endings: int = 0
    total_games: int = 0
    total_turns: int = 0
    vp_a_list: list[float] = field(default_factory=list)
    vp_b_list: list[float] = field(default_factory=list)
    position_spreads: list[float] = field(default_factory=list)

    def add_result(self, result: GameResult) -> None:
        """Add a game result to the statistics."""
        self.total_games += 1
        self.total_turns += result.turns_played
        self.vp_a_list.append(result.vp_a)
        self.vp_b_list.append(result.vp_b)
        self.position_spreads.append(abs(result.final_pos_a - result.final_pos_b))

        # Track winner
        if result.winner == "A":
            self.wins_a += 1
        elif result.winner == "B":
            self.wins_b += 1
        elif result.winner == "tie":
            self.ties += 1

        # Track ending types
        if result.ending_type == EndingType.MUTUAL_DESTRUCTION:
            self.mutual_destructions += 1
        elif result.ending_type == EndingType.CRISIS_TERMINATION:
            self.crisis_terminations += 1
        elif result.ending_type == EndingType.MAX_TURNS:
            self.max_turns_endings += 1
        elif result.ending_type in (
            EndingType.POSITION_LOSS_A,
            EndingType.POSITION_LOSS_B,
            EndingType.RESOURCE_LOSS_A,
            EndingType.RESOURCE_LOSS_B,
        ):
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
    def tie_rate(self) -> float:
        if self.total_games == 0:
            return 0.0
        return self.ties / self.total_games

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
    def elimination_rate(self) -> float:
        if self.total_games == 0:
            return 0.0
        return self.eliminations / self.total_games

    @property
    def mutual_destruction_rate(self) -> float:
        if self.total_games == 0:
            return 0.0
        return self.mutual_destructions / self.total_games

    @property
    def crisis_termination_rate(self) -> float:
        if self.total_games == 0:
            return 0.0
        return self.crisis_terminations / self.total_games

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "wins_a": self.wins_a,
            "wins_b": self.wins_b,
            "ties": self.ties,
            "mutual_destructions": self.mutual_destructions,
            "crisis_terminations": self.crisis_terminations,
            "eliminations": self.eliminations,
            "max_turns_endings": self.max_turns_endings,
            "total_games": self.total_games,
            "total_turns": self.total_turns,
            "win_rate_a": round(self.win_rate_a, 4),
            "win_rate_b": round(self.win_rate_b, 4),
            "tie_rate": round(self.tie_rate, 4),
            "avg_game_length": round(self.avg_game_length, 2),
            "avg_vp_a": round(self.avg_vp_a, 2),
            "avg_vp_b": round(self.avg_vp_b, 2),
            "vp_std_a": round(self.vp_std_a, 2),
            "vp_std_b": round(self.vp_std_b, 2),
            "elimination_rate": round(self.elimination_rate, 4),
            "mutual_destruction_rate": round(self.mutual_destruction_rate, 4),
            "crisis_termination_rate": round(self.crisis_termination_rate, 4),
        }


@dataclass
class PlaytestResults:
    """Aggregate results from a full playtest run."""

    pairings: dict[str, PairingStats] = field(default_factory=dict)
    aggregate: dict[str, float] = field(default_factory=dict)
    logs: list[str] = field(default_factory=list)
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
        total_eliminations = 0
        total_mutual = 0
        total_crisis = 0
        total_max_turns = 0
        total_settlements = 0

        for stats in self.pairings.values():
            all_vp_a.extend(stats.vp_a_list)
            all_vp_b.extend(stats.vp_b_list)
            total_games += stats.total_games
            total_turns += stats.total_turns
            total_eliminations += stats.eliminations
            total_mutual += stats.mutual_destructions
            total_crisis += stats.crisis_terminations
            total_max_turns += stats.max_turns_endings

        if total_games > 0:
            self.aggregate = {
                "total_games": total_games,
                "avg_turns": round(total_turns / total_games, 2),
                "avg_vp_a": round(statistics.mean(all_vp_a), 2) if all_vp_a else 0,
                "avg_vp_b": round(statistics.mean(all_vp_b), 2) if all_vp_b else 0,
                "vp_std_dev": round(statistics.stdev(all_vp_a + all_vp_b), 2) if len(all_vp_a) > 1 else 0,
                "elimination_rate": round(total_eliminations / total_games, 4),
                "mutual_destruction_rate": round(total_mutual / total_games, 4),
                "crisis_termination_rate": round(total_crisis / total_games, 4),
                "max_turns_rate": round(total_max_turns / total_games, 4),
                "settlement_rate": round(total_settlements / total_games, 4),
            }

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "pairings": {k: v.to_dict() for k, v in self.pairings.items()},
            "aggregate": self.aggregate,
            "logs": self.logs,
            "timestamp": self.timestamp,
            "duration_seconds": round(self.duration_seconds, 2),
        }

    def to_json(self, indent: int = 2) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)


# =============================================================================
# Game Execution
# =============================================================================

def run_game(
    strategy_a: Strategy,
    strategy_b: Strategy,
    max_turns: Optional[int] = None,
    seed: Optional[int] = None,
) -> GameResult:
    """Run a single game between two strategies.

    Args:
        strategy_a: Strategy function for player A
        strategy_b: Strategy function for player B
        max_turns: Maximum turns (randomly 12-16 if not specified)
        seed: Random seed for reproducibility

    Returns:
        GameResult with all outcome data
    """
    if seed is not None:
        random.seed(seed)

    if max_turns is None:
        max_turns = random.randint(12, 16)

    state = SimpleGameState(max_turns=max_turns)

    while True:
        # Check for ending before actions
        ending = check_ending(state)
        if ending:
            break

        # Get actions from both players
        action_a = strategy_a(state, state.history_a, state.history_b, "A")
        action_b = strategy_b(state, state.history_b, state.history_a, "B")

        # Record history
        state.history_a.append(action_a)
        state.history_b.append(action_b)

        # Apply outcome
        apply_outcome(state, action_a, action_b)

        # Advance turn
        state.turn += 1

        # Check for ending after actions
        ending = check_ending(state)
        if ending:
            break

    # Calculate final VP
    if ending == EndingType.MUTUAL_DESTRUCTION:
        vp_a, vp_b = 20.0, 20.0
        winner = "mutual_destruction"
    elif ending in (EndingType.POSITION_LOSS_A, EndingType.RESOURCE_LOSS_A):
        vp_a, vp_b = 10.0, 90.0
        winner = "B"
    elif ending in (EndingType.POSITION_LOSS_B, EndingType.RESOURCE_LOSS_B):
        vp_a, vp_b = 90.0, 10.0
        winner = "A"
    else:
        # MAX_TURNS or CRISIS_TERMINATION: use final resolution
        vp_a, vp_b = final_resolution(state)
        if vp_a > vp_b + 0.01:
            winner = "A"
        elif vp_b > vp_a + 0.01:
            winner = "B"
        else:
            winner = "tie"

    return GameResult(
        winner=winner,
        ending_type=ending,
        turns_played=state.turn - 1,
        final_pos_a=state.player_a.position,
        final_pos_b=state.player_b.position,
        final_res_a=state.player_a.resources,
        final_res_b=state.player_b.resources,
        final_risk=state.risk_level,
        final_cooperation=state.cooperation_score,
        final_stability=state.stability,
        vp_a=vp_a,
        vp_b=vp_b,
        history_a=[a.value for a in state.history_a],
        history_b=[a.value for a in state.history_b],
    )


def _run_single_game_wrapper(args: tuple) -> dict:
    """Wrapper for running a single game in a subprocess.

    Args:
        args: Tuple of (strategy_a_name, strategy_b_name, game_index, seed)

    Returns:
        Dictionary with game result data
    """
    strategy_a_name, strategy_b_name, game_index, seed = args

    strategy_a = STRATEGIES.get(strategy_a_name)
    strategy_b = STRATEGIES.get(strategy_b_name)

    if strategy_a is None:
        raise ValueError(f"Unknown strategy: {strategy_a_name}")
    if strategy_b is None:
        raise ValueError(f"Unknown strategy: {strategy_b_name}")

    result = run_game(strategy_a, strategy_b, seed=seed)
    return result.to_dict()


def run_pairing_batch(
    strategy_a_name: str,
    strategy_b_name: str,
    num_games: int,
    base_seed: Optional[int] = None,
) -> list[dict]:
    """Run a batch of games for a pairing (for subprocess execution).

    Args:
        strategy_a_name: Name of strategy A
        strategy_b_name: Name of strategy B
        num_games: Number of games to run
        base_seed: Base random seed (each game gets base_seed + game_index)

    Returns:
        List of game result dictionaries
    """
    results = []
    for i in range(num_games):
        seed = (base_seed + i) if base_seed is not None else None
        args = (strategy_a_name, strategy_b_name, i, seed)
        result = _run_single_game_wrapper(args)
        results.append(result)
    return results


# =============================================================================
# PlaytestRunner Class
# =============================================================================

class PlaytestRunner:
    """Orchestrates batch game execution for playtesting.

    This is a pure Python class with no LLM orchestration.
    Parallelism is achieved through ProcessPoolExecutor.

    Usage:
        runner = PlaytestRunner()
        stats = runner.run_pairing("TitForTat", "Nash", num_games=100)
        results = runner.run_playtest(
            [("TitForTat", "Nash"), ("Nash", "AlwaysDefect")],
            games_per_pairing=100,
            output_dir="playtest_results",
        )
    """

    def __init__(self, scenario_path: Optional[str] = None):
        """Initialize the playtester.

        Args:
            scenario_path: Optional path to scenario JSON (for future use)
        """
        self.scenario_path = scenario_path
        self._custom_strategies: dict[str, Strategy] = {}

    def register_strategy(self, name: str, strategy: Strategy) -> None:
        """Register a custom strategy function.

        Args:
            name: Name for the strategy
            strategy: Strategy function
        """
        self._custom_strategies[name] = strategy

    def get_strategy(self, name: str) -> Strategy:
        """Get a strategy by name.

        Args:
            name: Strategy name

        Returns:
            Strategy function

        Raises:
            ValueError: If strategy is not found
        """
        if name in self._custom_strategies:
            return self._custom_strategies[name]
        if name in STRATEGIES:
            return STRATEGIES[name]
        raise ValueError(
            f"Unknown strategy: {name}. "
            f"Available: {list(STRATEGIES.keys()) + list(self._custom_strategies.keys())}"
        )

    def list_strategies(self) -> list[str]:
        """List all available strategy names."""
        return list(STRATEGIES.keys()) + list(self._custom_strategies.keys())

    def run_pairing(
        self,
        strategy_a: str | Strategy,
        strategy_b: str | Strategy,
        num_games: int = 100,
        seed: Optional[int] = None,
    ) -> PairingStats:
        """Run games between two strategies.

        Args:
            strategy_a: Strategy name or function for player A
            strategy_b: Strategy name or function for player B
            num_games: Number of games to run
            seed: Base random seed for reproducibility

        Returns:
            PairingStats with aggregated statistics
        """
        # Resolve strategy functions
        if isinstance(strategy_a, str):
            strat_a = self.get_strategy(strategy_a)
        else:
            strat_a = strategy_a

        if isinstance(strategy_b, str):
            strat_b = self.get_strategy(strategy_b)
        else:
            strat_b = strategy_b

        stats = PairingStats()

        for i in range(num_games):
            game_seed = (seed + i) if seed is not None else None
            result = run_game(strat_a, strat_b, seed=game_seed)
            stats.add_result(result)

        return stats

    def run_playtest(
        self,
        pairings: list[tuple[str, str]],
        games_per_pairing: int = 100,
        output_dir: str = "playtest_results",
        max_workers: int = 4,
        seed: Optional[int] = None,
        save_logs: bool = False,
    ) -> PlaytestResults:
        """Run full playtest with parallel execution.

        Args:
            pairings: List of (strategy_name_a, strategy_name_b) tuples
            games_per_pairing: Number of games per pairing
            output_dir: Directory for output files
            max_workers: Maximum parallel workers
            seed: Base random seed
            save_logs: If True, save individual game logs

        Returns:
            PlaytestResults with all statistics and logs
        """
        import datetime

        start_time = time.time()
        timestamp = datetime.datetime.now().isoformat()

        results = PlaytestResults(timestamp=timestamp)
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # For deterministic strategies, run sequentially for speed
        # (ProcessPoolExecutor overhead can exceed game computation time)
        if games_per_pairing <= 100 and max_workers == 1:
            # Sequential execution
            for strat_a, strat_b in pairings:
                pairing_name = f"{strat_a}:{strat_b}"
                pairing_seed = seed
                stats = self.run_pairing(strat_a, strat_b, games_per_pairing, pairing_seed)
                results.pairings[pairing_name] = stats
        else:
            # Parallel execution using ProcessPoolExecutor
            with ProcessPoolExecutor(max_workers=max_workers) as executor:
                futures = {}
                for idx, (strat_a, strat_b) in enumerate(pairings):
                    pairing_name = f"{strat_a}:{strat_b}"
                    pairing_seed = (seed + idx * games_per_pairing) if seed is not None else None

                    # Submit batch of games for this pairing
                    future = executor.submit(
                        run_pairing_batch,
                        strat_a,
                        strat_b,
                        games_per_pairing,
                        pairing_seed,
                    )
                    futures[future] = pairing_name

                # Collect results
                for future in as_completed(futures):
                    pairing_name = futures[future]
                    game_results = future.result()

                    stats = PairingStats()
                    for result_dict in game_results:
                        # Reconstruct GameResult from dict
                        result = GameResult(
                            winner=result_dict["winner"],
                            ending_type=EndingType(result_dict["ending_type"]),
                            turns_played=result_dict["turns_played"],
                            final_pos_a=result_dict["final_pos_a"],
                            final_pos_b=result_dict["final_pos_b"],
                            final_res_a=result_dict["final_res_a"],
                            final_res_b=result_dict["final_res_b"],
                            final_risk=result_dict["final_risk"],
                            final_cooperation=result_dict["final_cooperation"],
                            final_stability=result_dict["final_stability"],
                            vp_a=result_dict["vp_a"],
                            vp_b=result_dict["vp_b"],
                            history_a=result_dict["history_a"],
                            history_b=result_dict["history_b"],
                        )
                        stats.add_result(result)

                    results.pairings[pairing_name] = stats

                    # Optionally save individual game logs
                    if save_logs:
                        log_path = output_path / f"games_{pairing_name.replace(':', '_')}.json"
                        with open(log_path, "w") as f:
                            json.dump(game_results, f, indent=2)
                        results.logs.append(str(log_path))

        # Compute aggregate statistics
        results.compute_aggregate()
        results.duration_seconds = time.time() - start_time

        # Save results summary
        results_path = output_path / "playtest_results.json"
        with open(results_path, "w") as f:
            f.write(results.to_json())

        return results

    def run_all_pairings(
        self,
        strategies: Optional[list[str]] = None,
        games_per_pairing: int = 100,
        output_dir: str = "playtest_results",
        max_workers: int = 4,
        seed: Optional[int] = None,
    ) -> PlaytestResults:
        """Run playtest for all unique pairings of given strategies.

        Args:
            strategies: List of strategy names (default: all built-in)
            games_per_pairing: Number of games per pairing
            output_dir: Directory for output files
            max_workers: Maximum parallel workers
            seed: Base random seed

        Returns:
            PlaytestResults
        """
        if strategies is None:
            strategies = list(STRATEGIES.keys())

        # Generate all unique pairings (including self-play)
        pairings = []
        for i, strat_a in enumerate(strategies):
            for strat_b in strategies[i:]:
                pairings.append((strat_a, strat_b))

        return self.run_playtest(
            pairings,
            games_per_pairing=games_per_pairing,
            output_dir=output_dir,
            max_workers=max_workers,
            seed=seed,
        )


def print_results_summary(results: PlaytestResults) -> None:
    """Print a human-readable summary of playtest results.

    Args:
        results: PlaytestResults to summarize
    """
    print("\n" + "=" * 80)
    print("PLAYTEST RESULTS SUMMARY")
    print(f"Timestamp: {results.timestamp}")
    print(f"Duration: {results.duration_seconds:.2f} seconds")
    print("=" * 80)

    # Aggregate stats
    print("\nAGGREGATE STATISTICS:")
    print("-" * 40)
    for key, value in results.aggregate.items():
        if isinstance(value, float):
            if "rate" in key:
                print(f"  {key}: {value * 100:.1f}%")
            else:
                print(f"  {key}: {value:.2f}")
        else:
            print(f"  {key}: {value}")

    # Per-pairing stats
    print("\nPAIRING STATISTICS:")
    print("-" * 80)
    header = f"{'Pairing':<25} {'Win A':>8} {'Win B':>8} {'Tie':>6} {'Avg VP A':>9} {'Avg VP B':>9} {'Avg Len':>8}"
    print(header)
    print("-" * 80)

    for pairing, stats in sorted(results.pairings.items()):
        print(
            f"{pairing:<25} "
            f"{stats.win_rate_a * 100:>7.1f}% "
            f"{stats.win_rate_b * 100:>7.1f}% "
            f"{stats.tie_rate * 100:>5.1f}% "
            f"{stats.avg_vp_a:>9.1f} "
            f"{stats.avg_vp_b:>9.1f} "
            f"{stats.avg_game_length:>8.1f}"
        )

    # Dominant strategy analysis
    print("\n" + "=" * 80)
    print("DOMINANT STRATEGY ANALYSIS")
    print("=" * 80)

    # Compute overall win rates per strategy
    strategy_stats: dict[str, dict] = {}

    for pairing, stats in results.pairings.items():
        strat_a, strat_b = pairing.split(":")

        if strat_a not in strategy_stats:
            strategy_stats[strat_a] = {"wins": 0, "games": 0}
        if strat_b not in strategy_stats:
            strategy_stats[strat_b] = {"wins": 0, "games": 0}

        strategy_stats[strat_a]["wins"] += stats.wins_a
        strategy_stats[strat_a]["games"] += stats.total_games

        if strat_a != strat_b:
            strategy_stats[strat_b]["wins"] += stats.wins_b
            strategy_stats[strat_b]["games"] += stats.total_games

    print(f"\n{'Strategy':<20} {'Wins':>10} {'Games':>10} {'Win Rate':>12}")
    print("-" * 55)

    dominant = []
    for strat, data in sorted(strategy_stats.items()):
        win_rate = data["wins"] / data["games"] if data["games"] > 0 else 0
        print(f"{strat:<20} {data['wins']:>10} {data['games']:>10} {win_rate * 100:>11.1f}%")
        if win_rate > 0.60:
            dominant.append((strat, win_rate))

    print("-" * 55)
    if dominant:
        print("\nDOMINANT STRATEGIES DETECTED (>60% win rate):")
        for strat, rate in dominant:
            print(f"  - {strat}: {rate * 100:.1f}%")
    else:
        print("\nNO DOMINANT STRATEGY DETECTED")


# =============================================================================
# CLI Interface
# =============================================================================

def main():
    """Command-line interface for running playtests."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Run Brinksmanship game balance playtests"
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
        "--workers",
        type=int,
        default=4,
        help="Number of parallel workers (default: 4)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Random seed for reproducibility",
    )
    parser.add_argument(
        "--save-logs",
        action="store_true",
        help="Save individual game logs",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress output summary",
    )

    args = parser.parse_args()

    runner = PlaytestRunner()

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
            max_workers=args.workers,
            seed=args.seed,
            save_logs=args.save_logs,
        )
    else:
        # Run all pairings
        strategies = None
        if args.strategies:
            strategies = [s.strip() for s in args.strategies.split(",")]

        results = runner.run_all_pairings(
            strategies=strategies,
            games_per_pairing=args.games,
            output_dir=args.output,
            max_workers=args.workers,
            seed=args.seed,
        )

    if not args.quiet:
        print_results_summary(results)

    print(f"\nResults saved to: {args.output}/playtest_results.json")
    return results


if __name__ == "__main__":
    main()
