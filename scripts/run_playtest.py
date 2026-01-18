#!/usr/bin/env python3
"""Deterministic playtest runner - no LLM orchestration needed.

This script runs playtests between various strategy pairings with parallel
game execution using ProcessPoolExecutor. All game simulation is pure Python
with no LLM calls required for deterministic opponents.

Usage:
    python scripts/run_playtest.py \\
        --scenario scenarios/cold_war.json \\
        --pairings "Nash:Nash,TitForTat:Opportunist" \\
        --games 100 \\
        --output playtest_results.json

Available strategies (from balance_simulation.py):
    - TitForTat: Cooperate first, then mirror opponent
    - AlwaysDefect: Always defect
    - AlwaysCooperate: Always cooperate
    - Opportunist: Defect when ahead, cooperate when behind
    - Nash: Play Nash equilibrium (defect), with risk-awareness
"""

import argparse
import json
import os
import random
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Callable, Optional


# =============================================================================
# Game Types and State (adapted from balance_simulation.py)
# =============================================================================


class Action(Enum):
    """Game action: cooperate or defect."""
    COOPERATE = "C"
    DEFECT = "D"


class EndingType(Enum):
    """How the game ended."""
    MAX_TURNS = "max_turns"
    POSITION_LOSS_A = "position_loss_a"
    POSITION_LOSS_B = "position_loss_b"
    RESOURCE_LOSS_A = "resource_loss_a"
    RESOURCE_LOSS_B = "resource_loss_b"
    MUTUAL_DESTRUCTION = "mutual_destruction"
    CRISIS_TERMINATION = "crisis_termination"


@dataclass
class PlayerState:
    """State for a single player."""
    position: float = 5.0
    resources: float = 5.0

    def clamp(self):
        """Clamp values to valid ranges."""
        self.position = max(0.0, min(10.0, self.position))
        self.resources = max(0.0, min(10.0, self.resources))


@dataclass
class GameState:
    """Complete game state."""
    player_a: PlayerState = field(default_factory=PlayerState)
    player_b: PlayerState = field(default_factory=PlayerState)
    risk: float = 2.0
    turn: int = 1
    max_turns: int = 14
    history_a: list = field(default_factory=list)
    history_b: list = field(default_factory=list)

    def clamp(self):
        """Clamp all values to valid ranges."""
        self.player_a.clamp()
        self.player_b.clamp()
        self.risk = max(0.0, min(10.0, self.risk))

    def get_act_multiplier(self) -> float:
        """Return act scaling based on turn number."""
        if self.turn <= 4:
            return 0.7  # Act I
        elif self.turn <= 8:
            return 1.0  # Act II
        else:
            return 1.3  # Act III


@dataclass
class GameResult:
    """Result of a single game."""
    winner: Optional[str]  # "A", "B", "tie", or "mutual_destruction"
    ending_type: str
    turns_played: int
    final_pos_a: float
    final_pos_b: float
    final_res_a: float
    final_res_b: float
    final_risk: float
    history_a: list = field(default_factory=list)
    history_b: list = field(default_factory=list)


# =============================================================================
# Game Mechanics
# =============================================================================


def apply_outcome(state: GameState, action_a: Action, action_b: Action, add_noise: bool = True):
    """Apply outcome based on actions and state delta rules.

    State deltas from GAME_MANUAL.md Section 3.5:
    - CC: pos_a +0.5, pos_b +0.5, risk -0.5
    - CD: pos_a -1.0, pos_b +1.0, risk +0.5
    - DC: pos_a +1.0, pos_b -1.0, risk +0.5
    - DD: pos_a -0.3, pos_b -0.3, resource_cost each 0.5, risk +1.0
    """
    multiplier = state.get_act_multiplier()

    # Small random variance (+/- 10%) to make games less deterministic
    noise_factor = 1.0
    if add_noise:
        noise_factor = random.uniform(0.9, 1.1)

    if action_a == Action.COOPERATE and action_b == Action.COOPERATE:
        state.player_a.position += 0.5 * multiplier * noise_factor
        state.player_b.position += 0.5 * multiplier * noise_factor
        state.risk -= 0.5 * multiplier * noise_factor
    elif action_a == Action.COOPERATE and action_b == Action.DEFECT:
        state.player_a.position -= 1.0 * multiplier * noise_factor
        state.player_b.position += 1.0 * multiplier * noise_factor
        state.risk += 0.5 * multiplier * noise_factor
    elif action_a == Action.DEFECT and action_b == Action.COOPERATE:
        state.player_a.position += 1.0 * multiplier * noise_factor
        state.player_b.position -= 1.0 * multiplier * noise_factor
        state.risk += 0.5 * multiplier * noise_factor
    else:  # DD
        state.player_a.position -= 0.3 * multiplier * noise_factor
        state.player_b.position -= 0.3 * multiplier * noise_factor
        state.player_a.resources -= 0.5 * multiplier * noise_factor
        state.player_b.resources -= 0.5 * multiplier * noise_factor
        state.risk += 1.0 * multiplier * noise_factor

    state.clamp()


def check_crisis_termination(state: GameState) -> bool:
    """Check if crisis terminates this turn (probabilistic).

    From GAME_MANUAL.md:
    - Only checked for Turn >= 10 and Risk > 7
    - P(termination) = (Risk - 7) * 0.08
    """
    if state.turn < 10 or state.risk <= 7:
        return False

    p_termination = (state.risk - 7) * 0.08
    return random.random() < p_termination


def check_ending(state: GameState) -> Optional[EndingType]:
    """Check if game has ended."""
    if state.risk >= 10.0:
        return EndingType.MUTUAL_DESTRUCTION

    if state.player_a.position <= 0:
        return EndingType.POSITION_LOSS_A
    if state.player_b.position <= 0:
        return EndingType.POSITION_LOSS_B

    if state.player_a.resources <= 0:
        return EndingType.RESOURCE_LOSS_A
    if state.player_b.resources <= 0:
        return EndingType.RESOURCE_LOSS_B

    if check_crisis_termination(state):
        return EndingType.CRISIS_TERMINATION

    if state.turn > state.max_turns:
        return EndingType.MAX_TURNS

    return None


# =============================================================================
# Strategy Implementations
# =============================================================================

Strategy = Callable[[GameState, list, list, str], Action]


def tit_for_tat(state: GameState, my_history: list, opp_history: list, player: str) -> Action:
    """TitForTat: cooperate first, then mirror opponent's last move."""
    if not opp_history:
        return Action.COOPERATE
    return opp_history[-1]


def always_defect(state: GameState, my_history: list, opp_history: list, player: str) -> Action:
    """AlwaysDefect: always defect."""
    return Action.DEFECT


def always_cooperate(state: GameState, my_history: list, opp_history: list, player: str) -> Action:
    """AlwaysCooperate: always cooperate."""
    return Action.COOPERATE


def opportunist(state: GameState, my_history: list, opp_history: list, player: str) -> Action:
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

    pos_advantage = my_pos - opp_pos

    # Risk-aware: if risk is high, be more cautious
    if state.risk >= 7:
        return Action.COOPERATE

    # Resource-aware: if low on resources, defection is costly
    if my_res <= 2:
        return Action.COOPERATE

    if pos_advantage > 1.0:
        return Action.DEFECT
    elif pos_advantage < -1.0:
        return Action.COOPERATE
    else:
        # When roughly equal, mix based on turn
        if state.turn <= 6:
            return Action.COOPERATE
        else:
            return Action.DEFECT


def nash_equilibrium(state: GameState, my_history: list, opp_history: list, player: str) -> Action:
    """Nash: play Nash equilibrium (defect in Prisoner's Dilemma).

    But with risk-awareness: if risk is very high, cooperate to avoid mutual destruction.
    """
    if state.risk >= 8:
        return Action.COOPERATE
    return Action.DEFECT


STRATEGIES: dict[str, Strategy] = {
    "TitForTat": tit_for_tat,
    "AlwaysDefect": always_defect,
    "AlwaysCooperate": always_cooperate,
    "Opportunist": opportunist,
    "Nash": nash_equilibrium,
}


# =============================================================================
# Game Runner
# =============================================================================


def run_game(
    strategy_a: Strategy,
    strategy_b: Strategy,
    max_turns: Optional[int] = None,
    game_seed: Optional[int] = None,
) -> GameResult:
    """Run a single game between two strategies.

    Args:
        strategy_a: Strategy function for player A
        strategy_b: Strategy function for player B
        max_turns: Maximum turns (random 12-16 if not specified)
        game_seed: Random seed for this specific game

    Returns:
        GameResult with complete game data
    """
    if game_seed is not None:
        random.seed(game_seed)

    if max_turns is None:
        max_turns = random.randint(12, 16)

    state = GameState(max_turns=max_turns)

    while True:
        ending = check_ending(state)
        if ending:
            break

        action_a = strategy_a(state, state.history_a, state.history_b, "A")
        action_b = strategy_b(state, state.history_b, state.history_a, "B")

        state.history_a.append(action_a)
        state.history_b.append(action_b)

        apply_outcome(state, action_a, action_b)
        state.turn += 1

        ending = check_ending(state)
        if ending:
            break

    # Determine winner
    if ending == EndingType.MUTUAL_DESTRUCTION:
        winner = "mutual_destruction"
    elif ending in (EndingType.POSITION_LOSS_A, EndingType.RESOURCE_LOSS_A):
        winner = "B"
    elif ending in (EndingType.POSITION_LOSS_B, EndingType.RESOURCE_LOSS_B):
        winner = "A"
    else:
        if state.player_a.position > state.player_b.position:
            winner = "A"
        elif state.player_b.position > state.player_a.position:
            winner = "B"
        else:
            winner = "tie"

    return GameResult(
        winner=winner,
        ending_type=ending.value,
        turns_played=state.turn - 1,
        final_pos_a=state.player_a.position,
        final_pos_b=state.player_b.position,
        final_res_a=state.player_a.resources,
        final_res_b=state.player_b.resources,
        final_risk=state.risk,
        history_a=[a.value for a in state.history_a],
        history_b=[a.value for a in state.history_b],
    )


# =============================================================================
# Pairing Runner (for multiprocessing)
# =============================================================================


def run_single_game_for_worker(args: tuple) -> dict:
    """Worker function for running a single game.

    Args:
        args: Tuple of (strategy_a_name, strategy_b_name, game_id, seed, log_dir)

    Returns:
        Dictionary with game result and optional log path
    """
    strat_a_name, strat_b_name, game_id, seed, log_dir = args

    strategy_a = STRATEGIES[strat_a_name]
    strategy_b = STRATEGIES[strat_b_name]

    result = run_game(strategy_a, strategy_b, game_seed=seed)

    log_path = None
    if log_dir:
        log_path = os.path.join(
            log_dir,
            f"game_{strat_a_name}_{strat_b_name}_{game_id:04d}.json"
        )
        os.makedirs(log_dir, exist_ok=True)
        with open(log_path, "w") as f:
            json.dump(asdict(result), f, indent=2)

    return {
        "winner": result.winner,
        "ending_type": result.ending_type,
        "turns_played": result.turns_played,
        "final_pos_a": result.final_pos_a,
        "final_pos_b": result.final_pos_b,
        "log_path": log_path,
    }


def run_pairing(
    strat_a_name: str,
    strat_b_name: str,
    games: int,
    base_seed: Optional[int],
    log_dir: Optional[str],
    workers: int,
) -> dict:
    """Run a single pairing of strategies.

    Args:
        strat_a_name: Name of strategy for player A
        strat_b_name: Name of strategy for player B
        games: Number of games to run
        base_seed: Base random seed (game i uses seed base_seed + i)
        log_dir: Directory to save game logs (None to skip)
        workers: Number of parallel workers

    Returns:
        Dictionary with pairing statistics
    """
    # Prepare game arguments
    game_args = []
    for i in range(games):
        seed = (base_seed + i) if base_seed is not None else None
        game_args.append((strat_a_name, strat_b_name, i, seed, log_dir))

    # Run games in parallel
    results = []
    with ProcessPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(run_single_game_for_worker, args) for args in game_args]
        for future in as_completed(futures):
            results.append(future.result())

    # Aggregate statistics
    wins_a = sum(1 for r in results if r["winner"] == "A")
    wins_b = sum(1 for r in results if r["winner"] == "B")
    ties = sum(1 for r in results if r["winner"] == "tie")
    mutual_destructions = sum(1 for r in results if r["winner"] == "mutual_destruction")

    total_turns = sum(r["turns_played"] for r in results)
    avg_turns = total_turns / games if games > 0 else 0

    ending_counts = {}
    for r in results:
        et = r["ending_type"]
        ending_counts[et] = ending_counts.get(et, 0) + 1

    eliminations = sum(
        ending_counts.get(et, 0)
        for et in ["position_loss_a", "position_loss_b", "resource_loss_a", "resource_loss_b"]
    )

    log_paths = [r["log_path"] for r in results if r["log_path"]]

    return {
        "strategy_a": strat_a_name,
        "strategy_b": strat_b_name,
        "total_games": games,
        "wins_a": wins_a,
        "wins_b": wins_b,
        "ties": ties,
        "mutual_destructions": mutual_destructions,
        "win_rate_a": wins_a / games if games > 0 else 0,
        "win_rate_b": wins_b / games if games > 0 else 0,
        "tie_rate": ties / games if games > 0 else 0,
        "mutual_destruction_rate": mutual_destructions / games if games > 0 else 0,
        "avg_turns": avg_turns,
        "total_turns": total_turns,
        "ending_counts": ending_counts,
        "elimination_rate": eliminations / games if games > 0 else 0,
        "log_paths": log_paths,
    }


# =============================================================================
# Playtest Runner
# =============================================================================


def parse_pairings(pairings_str: str) -> list[tuple[str, str]]:
    """Parse pairings string into list of (strategy_a, strategy_b) tuples.

    Args:
        pairings_str: Comma-separated list of "StratA:StratB" pairs

    Returns:
        List of (strategy_a, strategy_b) tuples

    Raises:
        ValueError: If pairing format is invalid or strategy not found
    """
    pairings = []
    for pair in pairings_str.split(","):
        pair = pair.strip()
        if ":" not in pair:
            raise ValueError(f"Invalid pairing format: '{pair}'. Expected 'StratA:StratB'")

        parts = pair.split(":")
        if len(parts) != 2:
            raise ValueError(f"Invalid pairing format: '{pair}'. Expected exactly one ':'")

        strat_a, strat_b = parts[0].strip(), parts[1].strip()

        if strat_a not in STRATEGIES:
            raise ValueError(f"Unknown strategy: '{strat_a}'. Available: {list(STRATEGIES.keys())}")
        if strat_b not in STRATEGIES:
            raise ValueError(f"Unknown strategy: '{strat_b}'. Available: {list(STRATEGIES.keys())}")

        pairings.append((strat_a, strat_b))

    return pairings


def run_playtest(
    scenario_path: Optional[str],
    pairings: list[tuple[str, str]],
    games: int,
    output: str,
    workers: int,
    seed: Optional[int],
    log_dir: Optional[str],
) -> dict:
    """Run playtest with parallel game execution.

    Args:
        scenario_path: Path to scenario JSON (optional, not used for deterministic play)
        pairings: List of (strategy_a, strategy_b) tuples
        games: Number of games per pairing
        output: Output file path for results JSON
        workers: Number of parallel workers
        seed: Random seed for reproducibility
        log_dir: Directory for individual game logs

    Returns:
        Results dictionary
    """
    if seed is not None:
        random.seed(seed)

    # Note: scenario_path is accepted for API compatibility but not used
    # for deterministic opponents. Future LLM-based opponents would use it.
    if scenario_path and os.path.exists(scenario_path):
        print(f"Note: Scenario file '{scenario_path}' found but not used for deterministic play.")

    start_time = time.time()

    # Run each pairing
    pairing_results = {}
    all_logs = []

    for i, (strat_a, strat_b) in enumerate(pairings):
        pairing_key = f"{strat_a}:{strat_b}"
        print(f"Running pairing {i+1}/{len(pairings)}: {pairing_key} ({games} games)...", end=" ", flush=True)

        pairing_start = time.time()

        # Each pairing gets its own seed space
        pairing_seed = (seed + i * games) if seed is not None else None

        # Set up log directory for this pairing
        pairing_log_dir = None
        if log_dir:
            pairing_log_dir = os.path.join(log_dir, f"{strat_a}_vs_{strat_b}")

        result = run_pairing(
            strat_a, strat_b, games, pairing_seed, pairing_log_dir, workers
        )

        pairing_results[pairing_key] = result
        all_logs.extend(result.get("log_paths", []))

        pairing_elapsed = time.time() - pairing_start
        print(f"done ({pairing_elapsed:.1f}s)")

    # Compute aggregate statistics
    total_games = sum(r["total_games"] for r in pairing_results.values())
    total_turns = sum(r["total_turns"] for r in pairing_results.values())

    aggregate_ending_counts = {}
    for r in pairing_results.values():
        for et, count in r.get("ending_counts", {}).items():
            aggregate_ending_counts[et] = aggregate_ending_counts.get(et, 0) + count

    settlements = aggregate_ending_counts.get("settlement", 0)
    eliminations = sum(
        aggregate_ending_counts.get(et, 0)
        for et in ["position_loss_a", "position_loss_b", "resource_loss_a", "resource_loss_b"]
    )

    aggregate = {
        "total_games": total_games,
        "total_pairings": len(pairings),
        "games_per_pairing": games,
        "avg_turns": total_turns / total_games if total_games > 0 else 0,
        "settlement_rate": settlements / total_games if total_games > 0 else 0,
        "elimination_rate": eliminations / total_games if total_games > 0 else 0,
        "mutual_destruction_rate": aggregate_ending_counts.get("mutual_destruction", 0) / total_games if total_games > 0 else 0,
        "crisis_termination_rate": aggregate_ending_counts.get("crisis_termination", 0) / total_games if total_games > 0 else 0,
        "max_turns_rate": aggregate_ending_counts.get("max_turns", 0) / total_games if total_games > 0 else 0,
        "ending_counts": aggregate_ending_counts,
    }

    elapsed = time.time() - start_time

    # Build final results
    results = {
        "metadata": {
            "timestamp": datetime.now().isoformat(),
            "scenario_path": scenario_path,
            "games_per_pairing": games,
            "workers": workers,
            "seed": seed,
            "elapsed_seconds": round(elapsed, 2),
        },
        "pairings": pairing_results,
        "aggregate": aggregate,
        "logs": all_logs if all_logs else None,
    }

    # Write output
    os.makedirs(os.path.dirname(output) or ".", exist_ok=True)
    with open(output, "w") as f:
        json.dump(results, f, indent=2)

    return results


def print_summary(results: dict):
    """Print a summary of playtest results to stdout."""
    print("\n" + "=" * 80)
    print("PLAYTEST SUMMARY")
    print("=" * 80)

    metadata = results.get("metadata", {})
    print(f"\nGames per pairing: {metadata.get('games_per_pairing', 'N/A')}")
    print(f"Workers: {metadata.get('workers', 'N/A')}")
    print(f"Seed: {metadata.get('seed', 'None')}")
    print(f"Elapsed time: {metadata.get('elapsed_seconds', 'N/A')}s")

    print("\n" + "-" * 80)
    print("PAIRING RESULTS")
    print("-" * 80)
    print(f"{'Pairing':<30} {'Win A':>8} {'Win B':>8} {'Tie':>6} {'MD':>6} {'Avg Len':>8}")
    print("-" * 80)

    for pairing_key, stats in results.get("pairings", {}).items():
        win_a_pct = stats.get("win_rate_a", 0) * 100
        win_b_pct = stats.get("win_rate_b", 0) * 100
        tie_pct = stats.get("tie_rate", 0) * 100
        md_pct = stats.get("mutual_destruction_rate", 0) * 100
        avg_turns = stats.get("avg_turns", 0)

        print(f"{pairing_key:<30} {win_a_pct:>7.1f}% {win_b_pct:>7.1f}% {tie_pct:>5.1f}% {md_pct:>5.1f}% {avg_turns:>8.1f}")

    print("-" * 80)

    aggregate = results.get("aggregate", {})
    print("\n" + "-" * 80)
    print("AGGREGATE STATISTICS")
    print("-" * 80)
    print(f"Total games: {aggregate.get('total_games', 'N/A')}")
    print(f"Average game length: {aggregate.get('avg_turns', 0):.1f} turns")
    print(f"Settlement rate: {aggregate.get('settlement_rate', 0) * 100:.1f}%")
    print(f"Elimination rate: {aggregate.get('elimination_rate', 0) * 100:.1f}%")
    print(f"Mutual destruction rate: {aggregate.get('mutual_destruction_rate', 0) * 100:.1f}%")
    print(f"Crisis termination rate: {aggregate.get('crisis_termination_rate', 0) * 100:.1f}%")
    print(f"Games reaching max turns: {aggregate.get('max_turns_rate', 0) * 100:.1f}%")

    # Dominant strategy check
    print("\n" + "-" * 80)
    print("DOMINANT STRATEGY CHECK (>60% overall win rate)")
    print("-" * 80)

    strategy_wins = {}
    strategy_games = {}

    for pairing_key, stats in results.get("pairings", {}).items():
        strat_a, strat_b = pairing_key.split(":")

        strategy_wins[strat_a] = strategy_wins.get(strat_a, 0) + stats.get("wins_a", 0)
        strategy_games[strat_a] = strategy_games.get(strat_a, 0) + stats.get("total_games", 0)

        if strat_a != strat_b:
            strategy_wins[strat_b] = strategy_wins.get(strat_b, 0) + stats.get("wins_b", 0)
            strategy_games[strat_b] = strategy_games.get(strat_b, 0) + stats.get("total_games", 0)

    dominant = []
    for strat in sorted(strategy_wins.keys()):
        games = strategy_games.get(strat, 0)
        wins = strategy_wins.get(strat, 0)
        rate = wins / games if games > 0 else 0
        print(f"{strat:<20} {wins:>5} / {games:<5} = {rate * 100:>5.1f}%")
        if rate > 0.60:
            dominant.append((strat, rate))

    if dominant:
        print("\nWARNING: Dominant strategies detected:")
        for strat, rate in dominant:
            print(f"  - {strat}: {rate * 100:.1f}%")
    else:
        print("\nNo dominant strategy detected (no strategy exceeds 60% overall win rate)")

    print("=" * 80)


def main():
    """Main entry point for the playtest runner."""
    parser = argparse.ArgumentParser(
        description="Deterministic playtest runner for Brinksmanship.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Available strategies:
  - TitForTat: Cooperate first, then mirror opponent
  - AlwaysDefect: Always defect
  - AlwaysCooperate: Always cooperate
  - Opportunist: Defect when ahead, cooperate when behind
  - Nash: Play Nash equilibrium (defect), with risk-awareness

Examples:
  # Run 100 games for two pairings
  python scripts/run_playtest.py \\
      --pairings "Nash:Nash,TitForTat:Opportunist" \\
      --games 100 \\
      --output results.json

  # Run with reproducible seed and game logs
  python scripts/run_playtest.py \\
      --pairings "TitForTat:AlwaysDefect" \\
      --games 50 \\
      --seed 42 \\
      --log-dir logs/ \\
      --output results.json
        """
    )

    parser.add_argument(
        "--scenario",
        type=str,
        default=None,
        help="Path to scenario JSON (optional, uses default for deterministic play)"
    )

    parser.add_argument(
        "--pairings",
        type=str,
        required=True,
        help='Comma-separated list of "StratA:StratB" pairs (e.g., "Nash:Nash,TitForTat:Opportunist")'
    )

    parser.add_argument(
        "--games",
        type=int,
        default=100,
        help="Number of games per pairing (default: 100)"
    )

    parser.add_argument(
        "--output",
        type=str,
        required=True,
        help="Output file path for results JSON"
    )

    parser.add_argument(
        "--workers",
        type=int,
        default=4,
        help="Number of parallel workers (default: 4)"
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Random seed for reproducibility (optional)"
    )

    parser.add_argument(
        "--log-dir",
        type=str,
        default=None,
        help="Directory for individual game logs (optional)"
    )

    args = parser.parse_args()

    # Parse pairings
    try:
        pairings = parse_pairings(args.pairings)
    except ValueError as e:
        print(f"Error parsing pairings: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Running playtest with {len(pairings)} pairing(s), {args.games} games each...")
    print(f"Pairings: {[f'{a}:{b}' for a, b in pairings]}")
    print(f"Workers: {args.workers}")
    if args.seed is not None:
        print(f"Seed: {args.seed}")
    print()

    # Run playtest
    try:
        results = run_playtest(
            scenario_path=args.scenario,
            pairings=pairings,
            games=args.games,
            output=args.output,
            workers=args.workers,
            seed=args.seed,
            log_dir=args.log_dir,
        )
    except Exception as e:
        print(f"Error running playtest: {e}", file=sys.stderr)
        sys.exit(1)

    # Print summary
    print_summary(results)

    print(f"\nResults written to: {args.output}")
    if args.log_dir:
        print(f"Game logs written to: {args.log_dir}")

    sys.exit(0)


if __name__ == "__main__":
    main()
