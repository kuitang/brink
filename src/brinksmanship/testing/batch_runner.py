"""Batch runner for parallel game execution.

This module provides utilities for running many games in parallel for:
- Balance simulation (testing all opponent pairings)
- Playtesting (statistical validation)
- Matrix type analysis

Uses the unified GameRunner with actual opponent implementations.
"""

from __future__ import annotations

import asyncio
import json
import statistics
import time
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from brinksmanship.opponents.base import Opponent, get_opponent_by_type, list_opponent_types
from brinksmanship.opponents.deterministic import (
    DeterministicOpponent,
    Erratic,
    GrimTrigger,
    NashCalculator,
    Opportunist,
    SecuritySeeker,
    TitForTat,
)
from brinksmanship.storage import get_scenario_repository
from brinksmanship.testing.game_runner import GameResult, run_game_sync


# Registry of all deterministic opponents (for fast, non-LLM simulation)
DETERMINISTIC_OPPONENTS: dict[str, type[DeterministicOpponent]] = {
    "NashCalculator": NashCalculator,
    "SecuritySeeker": SecuritySeeker,
    "Opportunist": Opportunist,
    "Erratic": Erratic,
    "TitForTat": TitForTat,
    "GrimTrigger": GrimTrigger,
}

# All available opponent names (deterministic + historical personas)
ALL_OPPONENTS = list_opponent_types()


def create_opponent(name: str, is_player_a: bool = False) -> Opponent:
    """Create an opponent instance by name.

    Supports both deterministic opponents and historical personas.
    For fast simulation with deterministic opponents only, use
    DETERMINISTIC_OPPONENTS directly.

    Args:
        name: Name of the opponent type (deterministic or historical persona)
        is_player_a: Whether this opponent is player A (for historical personas)

    Returns:
        New opponent instance

    Raises:
        ValueError: If opponent name is not recognized
    """
    # Try deterministic opponents first (faster, no LLM)
    if name in DETERMINISTIC_OPPONENTS:
        opponent = DETERMINISTIC_OPPONENTS[name]()
        if hasattr(opponent, "set_player_side"):
            opponent.set_player_side(is_player_a)
        return opponent

    # Try historical personas via factory
    return get_opponent_by_type(name, is_player_a=is_player_a)


@dataclass
class PairingStats:
    """Statistics for a single opponent pairing."""

    opponent_a: str
    opponent_b: str
    wins_a: int = 0
    wins_b: int = 0
    ties: int = 0
    mutual_destructions: int = 0
    crisis_terminations: int = 0
    natural_endings: int = 0
    settlements: int = 0
    position_collapses: int = 0
    resource_exhaustions: int = 0
    total_games: int = 0
    total_turns: int = 0
    vp_a_list: list[float] = field(default_factory=list)
    vp_b_list: list[float] = field(default_factory=list)
    total_value_list: list[float] = field(default_factory=list)  # VP_A + VP_B per game
    vp_share_a_list: list[float] = field(default_factory=list)  # VP_A / Total per game
    final_risks: list[float] = field(default_factory=list)
    final_cooperations: list[float] = field(default_factory=list)

    def add_result(self, result: GameResult) -> None:
        """Add a game result to statistics."""
        self.total_games += 1
        self.total_turns += result.turns_played
        self.vp_a_list.append(result.vp_a)
        self.vp_b_list.append(result.vp_b)
        self.final_risks.append(result.final_risk)
        self.final_cooperations.append(result.final_cooperation)

        # Track Total Value and VP Share (dual metrics)
        total_value = result.vp_a + result.vp_b
        self.total_value_list.append(total_value)
        # Avoid division by zero for mutual destruction (0, 0)
        vp_share_a = result.vp_a / total_value if total_value > 0 else 0.5
        self.vp_share_a_list.append(vp_share_a)

        # Track winner
        if result.winner == "A":
            self.wins_a += 1
        elif result.winner == "B":
            self.wins_b += 1
        elif result.winner == "tie":
            self.ties += 1
        elif result.winner == "mutual_destruction":
            self.mutual_destructions += 1

        # Track ending types
        ending = result.ending_type
        if ending == "mutual_destruction":
            pass  # Already counted in mutual_destructions
        elif ending == "crisis_termination":
            self.crisis_terminations += 1
        elif ending == "natural_ending":
            self.natural_endings += 1
        elif ending == "settlement":
            self.settlements += 1
        elif "collapse" in ending:
            self.position_collapses += 1
        elif "exhaustion" in ending:
            self.resource_exhaustions += 1

    @property
    def win_rate_a(self) -> float:
        return self.wins_a / self.total_games if self.total_games > 0 else 0.0

    @property
    def win_rate_b(self) -> float:
        return self.wins_b / self.total_games if self.total_games > 0 else 0.0

    @property
    def avg_game_length(self) -> float:
        return self.total_turns / self.total_games if self.total_games > 0 else 0.0

    @property
    def avg_vp_a(self) -> float:
        return statistics.mean(self.vp_a_list) if self.vp_a_list else 0.0

    @property
    def avg_vp_b(self) -> float:
        return statistics.mean(self.vp_b_list) if self.vp_b_list else 0.0

    @property
    def avg_total_value(self) -> float:
        """Average Total Value (VP_A + VP_B) across all games."""
        return statistics.mean(self.total_value_list) if self.total_value_list else 0.0

    @property
    def total_value_std(self) -> float:
        """Standard deviation of Total Value."""
        return statistics.stdev(self.total_value_list) if len(self.total_value_list) > 1 else 0.0

    @property
    def total_value_min(self) -> float:
        """Minimum Total Value."""
        return min(self.total_value_list) if self.total_value_list else 0.0

    @property
    def total_value_max(self) -> float:
        """Maximum Total Value."""
        return max(self.total_value_list) if self.total_value_list else 0.0

    @property
    def avg_vp_share_a(self) -> float:
        """Average VP Share for opponent A."""
        return statistics.mean(self.vp_share_a_list) if self.vp_share_a_list else 0.5

    @property
    def avg_risk(self) -> float:
        return statistics.mean(self.final_risks) if self.final_risks else 0.0

    @property
    def mutual_destruction_rate(self) -> float:
        return self.mutual_destructions / self.total_games if self.total_games > 0 else 0.0

    @property
    def settlement_rate(self) -> float:
        """Settlement rate across all games."""
        return self.settlements / self.total_games if self.total_games > 0 else 0.0

    @property
    def crisis_rate(self) -> float:
        """Crisis termination rate across all games."""
        return self.crisis_terminations / self.total_games if self.total_games > 0 else 0.0

    @property
    def natural_ending_rate(self) -> float:
        """Natural ending rate across all games."""
        return self.natural_endings / self.total_games if self.total_games > 0 else 0.0

    @property
    def elimination_rate(self) -> float:
        elims = self.position_collapses + self.resource_exhaustions
        return elims / self.total_games if self.total_games > 0 else 0.0

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "opponent_a": self.opponent_a,
            "opponent_b": self.opponent_b,
            "total_games": self.total_games,
            "wins_a": self.wins_a,
            "wins_b": self.wins_b,
            "ties": self.ties,
            "mutual_destructions": self.mutual_destructions,
            "crisis_terminations": self.crisis_terminations,
            "natural_endings": self.natural_endings,
            "settlements": self.settlements,
            "position_collapses": self.position_collapses,
            "resource_exhaustions": self.resource_exhaustions,
            "win_rate_a": round(self.win_rate_a, 4),
            "win_rate_b": round(self.win_rate_b, 4),
            "avg_game_length": round(self.avg_game_length, 2),
            "avg_vp_a": round(self.avg_vp_a, 2),
            "avg_vp_b": round(self.avg_vp_b, 2),
            "avg_total_value": round(self.avg_total_value, 2),
            "total_value_std": round(self.total_value_std, 2),
            "total_value_min": round(self.total_value_min, 2),
            "total_value_max": round(self.total_value_max, 2),
            "avg_vp_share_a": round(self.avg_vp_share_a, 4),
            "avg_risk": round(self.avg_risk, 2),
            "mutual_destruction_rate": round(self.mutual_destruction_rate, 4),
            "settlement_rate": round(self.settlement_rate, 4),
            "crisis_rate": round(self.crisis_rate, 4),
            "natural_ending_rate": round(self.natural_ending_rate, 4),
            "elimination_rate": round(self.elimination_rate, 4),
        }


@dataclass
class BatchResults:
    """Results from a batch run of games."""

    pairings: dict[str, PairingStats] = field(default_factory=dict)
    aggregate: dict[str, float] = field(default_factory=dict)
    scenario_id: str = ""
    timestamp: str = ""
    duration_seconds: float = 0.0

    def compute_aggregate(self) -> None:
        """Compute aggregate statistics across all pairings."""
        if not self.pairings:
            return

        total_games = 0
        total_turns = 0
        all_vp_a = []
        all_vp_b = []
        all_total_value = []
        total_md = 0
        total_elim = 0
        total_settlements = 0
        total_crisis = 0
        total_natural = 0

        for stats in self.pairings.values():
            total_games += stats.total_games
            total_turns += stats.total_turns
            all_vp_a.extend(stats.vp_a_list)
            all_vp_b.extend(stats.vp_b_list)
            all_total_value.extend(stats.total_value_list)
            total_md += stats.mutual_destructions
            total_elim += stats.position_collapses + stats.resource_exhaustions
            total_settlements += stats.settlements
            total_crisis += stats.crisis_terminations
            total_natural += stats.natural_endings

        if total_games > 0:
            self.aggregate = {
                "total_games": total_games,
                "avg_turns": round(total_turns / total_games, 2),
                "avg_vp_a": round(statistics.mean(all_vp_a), 2) if all_vp_a else 0,
                "avg_vp_b": round(statistics.mean(all_vp_b), 2) if all_vp_b else 0,
                "vp_std_dev": round(statistics.stdev(all_vp_a + all_vp_b), 2) if len(all_vp_a) > 1 else 0,
                # New Total Value metrics
                "avg_total_value": round(statistics.mean(all_total_value), 2) if all_total_value else 0,
                "total_value_std": round(statistics.stdev(all_total_value), 2) if len(all_total_value) > 1 else 0,
                "total_value_min": round(min(all_total_value), 2) if all_total_value else 0,
                "total_value_max": round(max(all_total_value), 2) if all_total_value else 0,
                # Ending type rates
                "mutual_destruction_rate": round(total_md / total_games, 4),
                "settlement_rate": round(total_settlements / total_games, 4),
                "crisis_rate": round(total_crisis / total_games, 4),
                "natural_ending_rate": round(total_natural / total_games, 4),
                "elimination_rate": round(total_elim / total_games, 4),
            }

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "pairings": {k: v.to_dict() for k, v in self.pairings.items()},
            "aggregate": self.aggregate,
            "scenario_id": self.scenario_id,
            "timestamp": self.timestamp,
            "duration_seconds": round(self.duration_seconds, 2),
        }

    def to_json(self, indent: int = 2) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)


def _run_single_game(args: tuple) -> dict:
    """Worker function for running a single game in a subprocess.

    Args:
        args: Tuple of (scenario_id, opponent_a_name, opponent_b_name, seed)

    Returns:
        GameResult as dictionary
    """
    scenario_id, opponent_a_name, opponent_b_name, seed = args

    # Create fresh opponent instances (required for subprocess isolation)
    # Player A is first opponent, Player B is second
    opponent_a = create_opponent(opponent_a_name, is_player_a=True)
    opponent_b = create_opponent(opponent_b_name, is_player_a=False)

    # Run game synchronously
    result = run_game_sync(
        scenario_id=scenario_id,
        opponent_a=opponent_a,
        opponent_b=opponent_b,
        random_seed=seed,
    )

    return result.to_dict()


class BatchRunner:
    """Runs batches of games for playtesting and balance simulation.

    Uses the actual DeterministicOpponent implementations from
    brinksmanship.opponents.deterministic.

    Usage:
        runner = BatchRunner(scenario_id="cuban_missile_crisis")

        # Run single pairing
        stats = runner.run_pairing("NashCalculator", "TitForTat", num_games=100)

        # Run all pairings
        results = runner.run_all_pairings(num_games=100)
    """

    def __init__(self, scenario_id: str):
        """Initialize batch runner.

        Args:
            scenario_id: ID of scenario to use for all games
        """
        self.scenario_id = scenario_id

    def run_pairing(
        self,
        opponent_a_name: str,
        opponent_b_name: str,
        num_games: int = 100,
        seed: Optional[int] = None,
        max_workers: int = 4,
    ) -> PairingStats:
        """Run games between two opponent types.

        Args:
            opponent_a_name: Name of opponent for player A
            opponent_b_name: Name of opponent for player B
            num_games: Number of games to run
            seed: Base random seed (game i uses seed + i)
            max_workers: Maximum parallel workers

        Returns:
            PairingStats with aggregated statistics
        """
        stats = PairingStats(opponent_a=opponent_a_name, opponent_b=opponent_b_name)

        # Prepare game arguments
        game_args = []
        for i in range(num_games):
            game_seed = (seed + i) if seed is not None else None
            game_args.append((self.scenario_id, opponent_a_name, opponent_b_name, game_seed))

        # Run games in parallel
        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(_run_single_game, args) for args in game_args]

            for future in as_completed(futures):
                result_dict = future.result()
                # Reconstruct GameResult from dict
                result = GameResult(
                    winner=result_dict["winner"],
                    ending_type=result_dict["ending_type"],
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
                    history=result_dict["history"],
                    scenario_id=result_dict["scenario_id"],
                    opponent_a_name=result_dict["opponent_a_name"],
                    opponent_b_name=result_dict["opponent_b_name"],
                )
                stats.add_result(result)

        return stats

    def run_all_pairings(
        self,
        opponent_names: Optional[list[str]] = None,
        num_games: int = 100,
        seed: Optional[int] = None,
        max_workers: int = 4,
        output_dir: Optional[str] = None,
    ) -> BatchResults:
        """Run all unique pairings of opponents.

        Args:
            opponent_names: List of opponent names (default: all deterministic)
            num_games: Number of games per pairing
            seed: Base random seed
            max_workers: Maximum parallel workers
            output_dir: Optional directory to save results

        Returns:
            BatchResults with all statistics
        """
        if opponent_names is None:
            opponent_names = list(DETERMINISTIC_OPPONENTS.keys())

        start_time = time.time()
        timestamp = datetime.now().isoformat()

        results = BatchResults(
            scenario_id=self.scenario_id,
            timestamp=timestamp,
        )

        # Generate all unique pairings (including self-play)
        pairings = []
        for i, name_a in enumerate(opponent_names):
            for name_b in opponent_names[i:]:
                pairings.append((name_a, name_b))

        # Run each pairing
        for idx, (name_a, name_b) in enumerate(pairings):
            pairing_key = f"{name_a}:{name_b}"
            print(f"  [{idx + 1}/{len(pairings)}] {pairing_key}...", end=" ", flush=True)

            pairing_seed = (seed + idx * num_games) if seed is not None else None

            stats = self.run_pairing(
                name_a,
                name_b,
                num_games=num_games,
                seed=pairing_seed,
                max_workers=max_workers,
            )

            results.pairings[pairing_key] = stats
            print(f"A:{stats.win_rate_a * 100:.0f}% B:{stats.win_rate_b * 100:.0f}%")

        # Compute aggregates
        results.compute_aggregate()
        results.duration_seconds = time.time() - start_time

        # Save results if output_dir specified
        if output_dir:
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)
            results_path = output_path / "batch_results.json"
            with open(results_path, "w") as f:
                f.write(results.to_json())
            print(f"\nResults saved to: {results_path}")

        return results


def print_results_summary(results: BatchResults) -> None:
    """Print a human-readable summary of batch results."""
    print("\n" + "=" * 80)
    print("BATCH SIMULATION RESULTS")
    print("=" * 80)
    print(f"Scenario: {results.scenario_id}")
    print(f"Timestamp: {results.timestamp}")
    print(f"Duration: {results.duration_seconds:.2f} seconds")
    print(f"Total Games: {results.aggregate.get('total_games', 0)}")

    # Total Value Statistics
    print("\n" + "-" * 80)
    print("TOTAL VALUE STATISTICS")
    print("-" * 80)
    avg_tv = results.aggregate.get("avg_total_value", 0)
    tv_std = results.aggregate.get("total_value_std", 0)
    tv_min = results.aggregate.get("total_value_min", 0)
    tv_max = results.aggregate.get("total_value_max", 0)
    print(f"  Mean: {avg_tv:.1f} VP  Std: {tv_std:.1f}  Min: {tv_min:.0f}  Max: {tv_max:.0f}")

    # VP Variance check (target: 10-40)
    vp_std = results.aggregate.get("vp_std_dev", 0)
    vp_check = "OK" if 10 <= vp_std <= 40 else "WARN"
    print(f"  VP Variance: {vp_std:.1f} (target: 10-40) [{vp_check}]")

    # Average game length check (target: 8-16)
    avg_turns = results.aggregate.get("avg_turns", 0)
    turns_check = "OK" if 8 <= avg_turns <= 16 else "WARN"
    print(f"  Avg Game Length: {avg_turns:.1f} turns (target: 8-16) [{turns_check}]")

    # Ending Type Breakdown
    print("\n" + "-" * 80)
    print("ENDING TYPE BREAKDOWN")
    print("-" * 80)
    settlement_rate = results.aggregate.get("settlement_rate", 0) * 100
    natural_rate = results.aggregate.get("natural_ending_rate", 0) * 100
    crisis_rate = results.aggregate.get("crisis_rate", 0) * 100
    md_rate = results.aggregate.get("mutual_destruction_rate", 0) * 100
    elim_rate = results.aggregate.get("elimination_rate", 0) * 100

    # Settlement rate check (target: 30-70%)
    settle_check = "OK" if 30 <= settlement_rate <= 70 else "WARN"
    print(f"  Settlement: {settlement_rate:.1f}% (target: 30-70%) [{settle_check}]")
    print(f"  Natural: {natural_rate:.1f}%")
    print(f"  Crisis: {crisis_rate:.1f}%")

    # Mutual destruction check (must be <20%, target 10-18%)
    if md_rate < 20:
        md_check = "OK" if 10 <= md_rate <= 18 else "OK (<20%)"
    else:
        md_check = "FAIL (>20%)"
    print(f"  Mutual Destruction: {md_rate:.1f}% (target: 10-18%, must be <20%) [{md_check}]")
    print(f"  Elimination: {elim_rate:.1f}%")

    # Per-pairing results
    print("\n" + "-" * 80)
    print(f"{'Pairing':<35} {'Win A':>8} {'Win B':>8} {'Tie':>6} {'MD':>6} {'Len':>6}")
    print("-" * 80)

    for pairing_key, stats in sorted(results.pairings.items()):
        print(
            f"{pairing_key:<35} "
            f"{stats.win_rate_a * 100:>7.1f}% "
            f"{stats.win_rate_b * 100:>7.1f}% "
            f"{stats.ties / stats.total_games * 100 if stats.total_games > 0 else 0:>5.1f}% "
            f"{stats.mutual_destruction_rate * 100:>5.1f}% "
            f"{stats.avg_game_length:>6.1f}"
        )

    # Aggregate opponent performance with dual-metric dominance check
    print("\n" + "-" * 80)
    print("OPPONENT PERFORMANCE (Dual-Metric Dominance Check)")
    print("-" * 80)

    # Collect per-opponent metrics: total value and VP share
    opponent_metrics: dict[str, dict] = defaultdict(
        lambda: {"wins": 0, "games": 0, "total_value_sum": 0.0, "vp_share_sum": 0.0, "game_count": 0}
    )

    for pairing_key, stats in results.pairings.items():
        name_a, name_b = pairing_key.split(":")

        # Opponent A stats
        opponent_metrics[name_a]["wins"] += stats.wins_a
        opponent_metrics[name_a]["games"] += stats.total_games
        opponent_metrics[name_a]["total_value_sum"] += sum(stats.total_value_list)
        opponent_metrics[name_a]["vp_share_sum"] += sum(stats.vp_share_a_list)
        opponent_metrics[name_a]["game_count"] += len(stats.total_value_list)

        # Opponent B stats (if not self-play)
        if name_a != name_b:
            opponent_metrics[name_b]["wins"] += stats.wins_b
            opponent_metrics[name_b]["games"] += stats.total_games
            opponent_metrics[name_b]["total_value_sum"] += sum(stats.total_value_list)
            # VP share for B is 1 - share_a
            opponent_metrics[name_b]["vp_share_sum"] += sum(1 - s for s in stats.vp_share_a_list)
            opponent_metrics[name_b]["game_count"] += len(stats.total_value_list)

    print(f"{'Opponent':<20} {'Avg Total':>10} {'VP Share':>10} {'Win Rate':>10} {'Status':>12}")
    print("-" * 65)

    sorted_opponents = sorted(
        opponent_metrics.items(),
        key=lambda x: x[1]["wins"] / x[1]["games"] if x[1]["games"] > 0 else 0,
        reverse=True,
    )

    dominant_strategies = []
    for name, data in sorted_opponents:
        win_rate = data["wins"] / data["games"] if data["games"] > 0 else 0
        avg_total = data["total_value_sum"] / data["game_count"] if data["game_count"] > 0 else 0
        avg_share = data["vp_share_sum"] / data["game_count"] if data["game_count"] > 0 else 0.5

        # Dominance check: >120 total AND >55% share
        is_dominant = avg_total > 120 and avg_share > 0.55
        status = "DOMINANT" if is_dominant else "OK"
        if is_dominant:
            dominant_strategies.append((name, avg_total, avg_share))

        print(
            f"{name:<20} "
            f"{avg_total:>9.1f} "
            f"{avg_share * 100:>9.1f}% "
            f"{win_rate * 100:>9.1f}% "
            f"{status:>12}"
        )

    # Dominance Check Summary
    print("\n" + "-" * 80)
    print("DOMINANCE CHECK")
    print("-" * 80)
    print("  Criteria: Strategy is DOMINANT if Avg Total Value > 120 AND VP Share > 55%")
    print()
    if dominant_strategies:
        print("  DOMINANT STRATEGIES FOUND (BALANCE ISSUE):")
        for name, tv, share in dominant_strategies:
            print(f"    - {name}: Total={tv:.1f}, Share={share * 100:.1f}%")
    else:
        print("  No dominant strategy found. (OK)")

    # Balance Pass/Fail Summary
    print("\n" + "-" * 80)
    print("BALANCE PASS CRITERIA CHECK")
    print("-" * 80)
    checks = []

    # Check 1: No dominant strategy
    dom_pass = len(dominant_strategies) == 0
    checks.append(("No dominant strategy", dom_pass))
    print(f"  [{'OK' if dom_pass else 'FAIL'}] No dominant strategy (>120 total AND >55% share)")

    # Check 2: VP variance in 10-40 range
    var_pass = 10 <= vp_std <= 40
    checks.append(("VP variance 10-40", var_pass))
    print(f"  [{'OK' if var_pass else 'FAIL'}] VP variance in 10-40 range (actual: {vp_std:.1f})")

    # Check 3: Settlement rate 30-70%
    settle_pass = 30 <= settlement_rate <= 70
    checks.append(("Settlement rate 30-70%", settle_pass))
    print(f"  [{'OK' if settle_pass else 'FAIL'}] Settlement rate 30-70% (actual: {settlement_rate:.1f}%)")

    # Check 4: Mutual destruction rate <20%
    md_pass = md_rate < 20
    checks.append(("Mutual destruction <20%", md_pass))
    print(f"  [{'OK' if md_pass else 'FAIL'}] Mutual destruction rate <20% (actual: {md_rate:.1f}%)")

    # Check 5: Average game length 8-16 turns
    turns_pass = 8 <= avg_turns <= 16
    checks.append(("Game length 8-16 turns", turns_pass))
    print(f"  [{'OK' if turns_pass else 'FAIL'}] Average game length 8-16 turns (actual: {avg_turns:.1f})")

    # Overall pass/fail
    all_pass = all(p for _, p in checks)
    print()
    if all_pass:
        print("  OVERALL: PASS - All balance criteria met")
    else:
        failed = [name for name, passed in checks if not passed]
        print(f"  OVERALL: FAIL - Failed checks: {', '.join(failed)}")

    print("=" * 80)
