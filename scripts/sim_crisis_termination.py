#!/usr/bin/env python3
"""
Crisis Termination Simulation for Brinksmanship

Tests the crisis termination mechanic from GAME_MANUAL.md:
- Starting Turn 10, if Risk > 7: P(Termination) = (Risk - 7) * 0.08
- Risk 8 = 8% per turn, Risk 9 = 16% per turn, Risk 10 = 100% (mutual destruction)

This simulation verifies that the probability calculation works correctly
and tracks termination statistics by risk level.
"""

import argparse
import random
from collections import defaultdict
from dataclasses import dataclass, field


@dataclass
class TerminationStats:
    """Statistics for crisis termination at a specific risk level."""
    trials: int = 0
    terminations: int = 0
    turns_when_terminated: list = field(default_factory=list)

    @property
    def termination_rate(self) -> float:
        if self.trials == 0:
            return 0.0
        return self.terminations / self.trials

    @property
    def avg_termination_turn(self) -> float:
        if not self.turns_when_terminated:
            return 0.0
        return sum(self.turns_when_terminated) / len(self.turns_when_terminated)


def calculate_termination_probability(risk_level: float) -> float:
    """Calculate P(Termination) based on risk level.

    From GAME_MANUAL.md Section 4.6:
        if Risk_Level > 7:
            P(Crisis_Termination) = (Risk_Level - 7) * 0.08
    """
    if risk_level <= 7:
        return 0.0
    return (risk_level - 7) * 0.08


def simulate_crisis_turn(risk_level: float) -> bool:
    """Simulate a single turn's crisis termination check.

    Returns True if crisis termination is triggered.
    """
    prob = calculate_termination_probability(risk_level)
    return random.random() < prob


def simulate_game_from_turn_10(risk_level: float, max_turns: int = 16) -> tuple[bool, int]:
    """Simulate a game starting from Turn 10 with a fixed risk level.

    Returns:
        (terminated, turn_terminated_or_max)
        - terminated: True if crisis termination triggered
        - turn: The turn when terminated, or max_turns if not terminated
    """
    for turn in range(10, max_turns + 1):
        if simulate_crisis_turn(risk_level):
            return True, turn
    return False, max_turns


def run_per_turn_simulation(num_trials: int = 10000) -> dict[int, TerminationStats]:
    """Run simulation to verify per-turn termination rates.

    Tests that each individual turn has the expected termination probability.
    """
    results = {}

    for risk in range(8, 10):  # Risk 8 and 9 (10 is automatic destruction)
        stats = TerminationStats()

        for _ in range(num_trials):
            stats.trials += 1
            if simulate_crisis_turn(risk):
                stats.terminations += 1

        results[risk] = stats

    return results


def run_cumulative_simulation(num_games: int = 5000) -> dict[int, TerminationStats]:
    """Run simulation to track when games terminate over multiple turns.

    Simulates games from Turn 10 to Turn 16 with various risk levels.
    """
    results = {}

    for risk in range(8, 10):  # Risk 8 and 9
        stats = TerminationStats()

        for _ in range(num_games):
            stats.trials += 1
            terminated, turn = simulate_game_from_turn_10(risk)
            if terminated:
                stats.terminations += 1
                stats.turns_when_terminated.append(turn)

        results[risk] = stats

    return results


def run_reach_turn_simulation(num_games: int = 5000) -> dict[int, dict[int, float]]:
    """Calculate probability of reaching specific turns from Turn 10.

    This verifies the values given in GAME_MANUAL.md Section 4.6:
    - At Risk 8: P(reaching Turn 12) = 85%, P(reaching Turn 14) = 72%
    - At Risk 9: P(reaching Turn 12) = 70%, P(reaching Turn 14) = 49%
    """
    results = {}

    for risk in range(8, 10):
        turn_counts = defaultdict(int)

        for _ in range(num_games):
            for turn in range(10, 17):  # Check turns 10-16
                turn_counts[turn] += 1
                if simulate_crisis_turn(risk):
                    break  # Game terminated

        # Calculate probability of reaching each turn
        results[risk] = {
            turn: turn_counts[turn] / num_games
            for turn in range(10, 17)
        }

    return results


def print_results(per_turn: dict, cumulative: dict, reach_turn: dict, num_trials: int, num_games: int):
    """Print formatted results tables."""
    print("\n" + "=" * 80)
    print("CRISIS TERMINATION SIMULATION RESULTS")
    print("=" * 80)

    # Per-turn verification
    print("\n" + "-" * 80)
    print("PER-TURN TERMINATION RATE VERIFICATION")
    print(f"Trials per risk level: {num_trials}")
    print("-" * 80)
    print(f"\n{'Risk Level':<15} {'Expected Rate':>15} {'Observed Rate':>15} {'Difference':>15}")
    print("-" * 60)

    for risk in range(8, 10):
        expected = calculate_termination_probability(risk) * 100
        observed = per_turn[risk].termination_rate * 100
        diff = observed - expected
        print(f"{risk:<15} {expected:>14.1f}% {observed:>14.2f}% {diff:>+14.2f}%")

    # Cumulative game termination
    print("\n" + "-" * 80)
    print("CUMULATIVE TERMINATION (Games from Turn 10 to Turn 16)")
    print(f"Games per risk level: {num_games}")
    print("-" * 80)
    print(f"\n{'Risk Level':<15} {'Games Terminated':>18} {'Termination Rate':>18} {'Avg Turn':>12}")
    print("-" * 70)

    for risk in range(8, 10):
        stats = cumulative[risk]
        print(f"{risk:<15} {stats.terminations:>18} {stats.termination_rate * 100:>17.1f}% "
              f"{stats.avg_termination_turn:>12.1f}")

    # Probability of reaching specific turns
    print("\n" + "-" * 80)
    print("PROBABILITY OF REACHING TURN (from Turn 10)")
    print("-" * 80)

    # Calculate theoretical probabilities
    # P(reach turn N) = (1 - p)^(N - 10) where p = (Risk - 7) * 0.08
    def theoretical_reach_prob(risk: int, target_turn: int) -> float:
        p = calculate_termination_probability(risk)
        turns_to_survive = target_turn - 10
        return (1 - p) ** turns_to_survive

    print(f"\n{'Turn':<8}", end="")
    for risk in range(8, 10):
        print(f"{'Risk ' + str(risk) + ' (Sim)':>14} {'(Theory)':>12}", end="")
    print()
    print("-" * 56)

    for turn in [10, 11, 12, 13, 14, 15, 16]:
        print(f"{turn:<8}", end="")
        for risk in range(8, 10):
            simulated = reach_turn[risk][turn] * 100
            theoretical = theoretical_reach_prob(risk, turn) * 100
            print(f"{simulated:>13.1f}% {theoretical:>11.1f}%", end="")
        print()

    # Comparison with GAME_MANUAL.md values
    print("\n" + "-" * 80)
    print("COMPARISON WITH GAME_MANUAL.md STATED VALUES")
    print("-" * 80)
    print(f"\n{'Metric':<40} {'Manual':>12} {'Simulated':>12}")
    print("-" * 65)

    manual_values = [
        ("Risk 8: P(reaching Turn 12)", 85, reach_turn[8].get(12, 0) * 100),
        ("Risk 8: P(reaching Turn 14)", 72, reach_turn[8].get(14, 0) * 100),
        ("Risk 8: P(reaching Turn 16)", 61, reach_turn[8].get(16, 0) * 100),
        ("Risk 9: P(reaching Turn 12)", 70, reach_turn[9].get(12, 0) * 100),
        ("Risk 9: P(reaching Turn 14)", 49, reach_turn[9].get(14, 0) * 100),
        ("Risk 9: P(reaching Turn 16)", 35, reach_turn[9].get(16, 0) * 100),
    ]

    for metric, manual, simulated in manual_values:
        print(f"{metric:<40} {manual:>11}% {simulated:>11.1f}%")

    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print("\nThe crisis termination formula P(Termination) = (Risk - 7) * 0.08 produces:")
    print("  - Risk 8: ~8% per-turn termination rate")
    print("  - Risk 9: ~16% per-turn termination rate")
    print("\nThis creates meaningful uncertainty about game length while keeping")
    print("termination probabilities low enough for strategic planning.")


def main():
    """Run the crisis termination simulation."""
    parser = argparse.ArgumentParser(
        description="Simulate crisis termination mechanic"
    )
    parser.add_argument(
        "--trials", type=int, default=10000,
        help="Number of trials for per-turn simulation (default: 10000)"
    )
    parser.add_argument(
        "--games", type=int, default=5000,
        help="Number of games for cumulative simulation (default: 5000)"
    )
    parser.add_argument(
        "--seed", type=int, default=None,
        help="Random seed for reproducibility"
    )
    args = parser.parse_args()

    if args.seed is not None:
        random.seed(args.seed)

    print(f"Running crisis termination simulation...")
    print(f"  Per-turn trials: {args.trials}")
    print(f"  Cumulative games: {args.games}")

    per_turn = run_per_turn_simulation(args.trials)
    cumulative = run_cumulative_simulation(args.games)
    reach_turn = run_reach_turn_simulation(args.games)

    print_results(per_turn, cumulative, reach_turn, args.trials, args.games)


if __name__ == "__main__":
    main()
