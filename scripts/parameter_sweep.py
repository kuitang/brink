#!/usr/bin/env python3
"""Parameter Sweep Simulation for balance tuning.

Grid search over key parameters to find combinations that meet all balance criteria.
This automates the tuning process and helps identify optimal parameter settings.

Usage:
    uv run python scripts/parameter_sweep.py

    # Run with more games per pairing (slower but more accurate)
    uv run python scripts/parameter_sweep.py --games 200

    # Run with custom parameter ranges
    uv run python scripts/parameter_sweep.py --capture-rates 0.3,0.4,0.5 --dd-risks 1.5,1.8,2.0

    # Run with reproducible seed
    uv run python scripts/parameter_sweep.py --seed 42

See GAME_MANUAL.md Appendix C for parameter documentation.
"""

from __future__ import annotations

import argparse
import statistics
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from itertools import product
from typing import Optional

# Import for type hints only - actual imports happen in worker
from brinksmanship import parameters


@dataclass
class SweepResult:
    """Result for a single parameter combination."""

    capture_rate: float
    rejection_base_penalty: float
    dd_risk_increase: float

    # Metrics
    avg_total_value: float = 0.0
    vp_std_dev: float = 0.0
    settlement_rate: float = 0.0
    mutual_destruction_rate: float = 0.0
    avg_game_length: float = 0.0

    # Dominant strategy check
    dominant_strategies: list[str] = field(default_factory=list)

    # Pass/fail status
    passes_all: bool = False
    failed_checks: list[str] = field(default_factory=list)

    def check_criteria(self) -> None:
        """Check all balance criteria and update pass/fail status."""
        self.failed_checks = []

        # Check 1: No dominant strategy (>120 total AND >55% share)
        if self.dominant_strategies:
            self.failed_checks.append(f"Dominant: {', '.join(self.dominant_strategies)}")

        # Check 2: VP variance in 10-40 range
        if not (10 <= self.vp_std_dev <= 40):
            self.failed_checks.append(f"Variance {self.vp_std_dev:.1f} (need 10-40)")

        # Check 3: Settlement rate 30-70%
        if not (0.30 <= self.settlement_rate <= 0.70):
            self.failed_checks.append(f"Settle {self.settlement_rate*100:.0f}% (need 30-70%)")

        # Check 4: Mutual destruction rate <20%
        if self.mutual_destruction_rate >= 0.20:
            self.failed_checks.append(f"MD {self.mutual_destruction_rate*100:.0f}% (need <20%)")

        # Check 5: Average game length 10-16 turns
        if not (10 <= self.avg_game_length <= 16):
            self.failed_checks.append(f"Length {self.avg_game_length:.1f} (need 10-16)")

        self.passes_all = len(self.failed_checks) == 0

    @property
    def param_str(self) -> str:
        """Short parameter description."""
        return f"CAPT={self.capture_rate} REJ={self.rejection_base_penalty} DD={self.dd_risk_increase}"


def _run_sweep_combination(args: tuple) -> dict:
    """Worker function to run simulation for a single parameter combination.

    Runs in a subprocess to isolate parameter changes.

    Args:
        args: Tuple of (scenario_id, capture_rate, rejection_penalty, dd_risk,
                       num_games, seed, max_workers)

    Returns:
        Dict with sweep results
    """
    (scenario_id, capture_rate, rejection_penalty, dd_risk,
     num_games, seed, max_workers) = args

    # Monkey-patch the parameters module
    from brinksmanship import parameters as params
    original_capture = params.CAPTURE_RATE
    original_rejection = params.REJECTION_BASE_PENALTY
    original_dd = params.DD_RISK_INCREASE

    try:
        params.CAPTURE_RATE = capture_rate
        params.REJECTION_BASE_PENALTY = rejection_penalty
        params.DD_RISK_INCREASE = dd_risk

        # Run the simulation with patched parameters
        from collections import defaultdict
        from brinksmanship.testing.batch_runner import (
            BatchRunner,
            DETERMINISTIC_OPPONENTS,
            BatchResults,
        )

        runner = BatchRunner(scenario_id=scenario_id)

        # Run all pairings
        opponent_names = list(DETERMINISTIC_OPPONENTS.keys())

        results = BatchResults(
            scenario_id=scenario_id,
            timestamp=datetime.now().isoformat(),
        )

        # Generate all unique pairings
        pairings = []
        for i, name_a in enumerate(opponent_names):
            for name_b in opponent_names[i:]:
                pairings.append((name_a, name_b))

        # Run each pairing (sequentially in worker to avoid nested parallelism issues)
        for idx, (name_a, name_b) in enumerate(pairings):
            pairing_key = f"{name_a}:{name_b}"
            pairing_seed = (seed + idx * num_games) if seed is not None else None

            stats = runner.run_pairing(
                name_a,
                name_b,
                num_games=num_games,
                seed=pairing_seed,
                max_workers=1,  # Sequential within worker
            )
            results.pairings[pairing_key] = stats

        # Compute aggregates
        results.compute_aggregate()

        # Check for dominant strategies
        opponent_metrics: dict[str, dict] = defaultdict(
            lambda: {"total_value_sum": 0.0, "vp_share_sum": 0.0, "game_count": 0}
        )

        for pairing_key, stats in results.pairings.items():
            name_a, name_b = pairing_key.split(":")

            opponent_metrics[name_a]["total_value_sum"] += sum(stats.total_value_list)
            opponent_metrics[name_a]["vp_share_sum"] += sum(stats.vp_share_a_list)
            opponent_metrics[name_a]["game_count"] += len(stats.total_value_list)

            if name_a != name_b:
                opponent_metrics[name_b]["total_value_sum"] += sum(stats.total_value_list)
                opponent_metrics[name_b]["vp_share_sum"] += sum(1 - s for s in stats.vp_share_a_list)
                opponent_metrics[name_b]["game_count"] += len(stats.total_value_list)

        dominant_strategies = []
        for name, data in opponent_metrics.items():
            if data["game_count"] > 0:
                avg_total = data["total_value_sum"] / data["game_count"]
                avg_share = data["vp_share_sum"] / data["game_count"]
                if avg_total > 120 and avg_share > 0.55:
                    dominant_strategies.append(name)

        return {
            "capture_rate": capture_rate,
            "rejection_base_penalty": rejection_penalty,
            "dd_risk_increase": dd_risk,
            "avg_total_value": results.aggregate.get("avg_total_value", 0),
            "vp_std_dev": results.aggregate.get("vp_std_dev", 0),
            "settlement_rate": results.aggregate.get("settlement_rate", 0),
            "mutual_destruction_rate": results.aggregate.get("mutual_destruction_rate", 0),
            "avg_game_length": results.aggregate.get("avg_turns", 0),
            "dominant_strategies": dominant_strategies,
        }

    finally:
        # Restore original parameters
        params.CAPTURE_RATE = original_capture
        params.REJECTION_BASE_PENALTY = original_rejection
        params.DD_RISK_INCREASE = original_dd


def run_parameter_sweep(
    scenario_id: str = "cuban_missile_crisis",
    capture_rates: list[float] = None,
    rejection_penalties: list[float] = None,
    dd_risks: list[float] = None,
    num_games: int = 100,
    seed: Optional[int] = None,
    max_workers: int = 4,
    quiet: bool = False,
) -> list[SweepResult]:
    """Run the parameter sweep.

    Args:
        scenario_id: Scenario to use for simulation
        capture_rates: CAPTURE_RATE values to test
        rejection_penalties: REJECTION_BASE_PENALTY values to test
        dd_risks: DD_RISK_INCREASE values to test
        num_games: Games per opponent pairing
        seed: Base random seed
        max_workers: Number of parallel workers
        quiet: Suppress progress output

    Returns:
        List of SweepResult for each parameter combination
    """
    # Default parameter ranges
    if capture_rates is None:
        capture_rates = [0.3, 0.4, 0.5]
    if rejection_penalties is None:
        rejection_penalties = [1.0, 1.5, 2.0]
    if dd_risks is None:
        dd_risks = [1.5, 1.8, 2.0]

    # Generate all combinations
    combinations = list(product(capture_rates, rejection_penalties, dd_risks))
    total_combos = len(combinations)

    if not quiet:
        print(f"Testing {total_combos} parameter combinations...")
        print(f"  CAPTURE_RATE: {capture_rates}")
        print(f"  REJECTION_BASE_PENALTY: {rejection_penalties}")
        print(f"  DD_RISK_INCREASE: {dd_risks}")
        print()

    # Prepare arguments for workers
    all_args = []
    for idx, (capture, rejection, dd) in enumerate(combinations):
        combo_seed = (seed + idx * 1000) if seed is not None else None
        all_args.append((
            scenario_id, capture, rejection, dd,
            num_games, combo_seed, max_workers
        ))

    # Run combinations in parallel
    results: list[SweepResult] = []
    completed = 0

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_run_sweep_combination, args): args for args in all_args}

        for future in as_completed(futures):
            result_dict = future.result()

            sweep_result = SweepResult(
                capture_rate=result_dict["capture_rate"],
                rejection_base_penalty=result_dict["rejection_base_penalty"],
                dd_risk_increase=result_dict["dd_risk_increase"],
                avg_total_value=result_dict["avg_total_value"],
                vp_std_dev=result_dict["vp_std_dev"],
                settlement_rate=result_dict["settlement_rate"],
                mutual_destruction_rate=result_dict["mutual_destruction_rate"],
                avg_game_length=result_dict["avg_game_length"],
                dominant_strategies=result_dict["dominant_strategies"],
            )
            sweep_result.check_criteria()
            results.append(sweep_result)

            completed += 1
            if not quiet:
                status = "PASS" if sweep_result.passes_all else "FAIL"
                print(f"  [{completed}/{total_combos}] {sweep_result.param_str}: {status}")

    return results


def print_sweep_results(results: list[SweepResult]) -> None:
    """Print formatted sweep results.

    Args:
        results: List of SweepResult from the sweep
    """
    print()
    print("PARAMETER SWEEP RESULTS")
    print("=" * 95)

    # Sort by pass/fail, then by total value
    results_sorted = sorted(
        results,
        key=lambda r: (not r.passes_all, -r.avg_total_value)
    )

    # Print header
    print(f"{'Params':<25} | {'Total':>6} | {'Settle':>7} | {'MD':>6} | {'Var':>6} | {'Len':>5} | {'Status':>6} | {'Details'}")
    print("-" * 95)

    # Track passing combinations
    passing = []

    for result in results_sorted:
        status = "PASS" if result.passes_all else "FAIL"

        if result.passes_all:
            passing.append(result)
            details = ""
        else:
            details = "; ".join(result.failed_checks[:2])  # Show first 2 failures

        print(
            f"{result.param_str:<25} | "
            f"{result.avg_total_value:>6.1f} | "
            f"{result.settlement_rate*100:>6.1f}% | "
            f"{result.mutual_destruction_rate*100:>5.1f}% | "
            f"{result.vp_std_dev:>6.1f} | "
            f"{result.avg_game_length:>5.1f} | "
            f"{status:>6} | "
            f"{details}"
        )

    print("-" * 95)
    print()

    # Summary
    print("SUMMARY")
    print("-" * 50)
    print(f"Combinations tested: {len(results)}")
    print(f"Passing combinations: {len(passing)}")

    if passing:
        print()
        print("RECOMMENDED PARAMETER SETTINGS:")
        print("-" * 50)

        # Recommend the one with highest total value among passing
        best = max(passing, key=lambda r: r.avg_total_value)
        print(f"  CAPTURE_RATE = {best.capture_rate}")
        print(f"  REJECTION_BASE_PENALTY = {best.rejection_base_penalty}")
        print(f"  DD_RISK_INCREASE = {best.dd_risk_increase}")
        print()
        print(f"  Expected metrics:")
        print(f"    - Total Value: {best.avg_total_value:.1f}")
        print(f"    - Settlement Rate: {best.settlement_rate*100:.1f}%")
        print(f"    - Mutual Destruction: {best.mutual_destruction_rate*100:.1f}%")
        print(f"    - VP Variance: {best.vp_std_dev:.1f}")
        print(f"    - Game Length: {best.avg_game_length:.1f} turns")
    else:
        print()
        print("NO PASSING COMBINATIONS FOUND")
        print("-" * 50)
        print("Consider:")
        print("  - Expanding parameter ranges")
        print("  - Running with more games for stability")
        print("  - Reviewing balance criteria thresholds")

        # Show closest to passing
        by_failures = sorted(results, key=lambda r: len(r.failed_checks))
        if by_failures:
            closest = by_failures[0]
            print()
            print(f"Closest to passing: {closest.param_str}")
            print(f"  Failed checks: {'; '.join(closest.failed_checks)}")


def main() -> None:
    """Run the parameter sweep simulation."""
    parser = argparse.ArgumentParser(
        description="Parameter sweep for balance tuning",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
This script grid-searches over key balance parameters to find combinations
that meet all balance criteria.

Default parameter ranges:
  - CAPTURE_RATE: [0.3, 0.4, 0.5]
  - REJECTION_BASE_PENALTY: [1.0, 1.5, 2.0]
  - DD_RISK_INCREASE: [1.5, 1.8, 2.0]

Balance criteria (all must pass):
  - No dominant strategy (>120 total AND >55% share)
  - VP variance in 10-40 range
  - Settlement rate 30-70%
  - Mutual destruction rate <20%
  - Average game length 10-16 turns

Examples:
    uv run python scripts/parameter_sweep.py
    uv run python scripts/parameter_sweep.py --games 200
    uv run python scripts/parameter_sweep.py --capture-rates 0.35,0.4,0.45 --games 50
        """,
    )

    parser.add_argument(
        "--scenario",
        type=str,
        default="cuban_missile_crisis",
        help="Scenario ID to use (default: cuban_missile_crisis)",
    )
    parser.add_argument(
        "--games",
        type=int,
        default=100,
        help="Number of games per opponent pairing (default: 100)",
    )
    parser.add_argument(
        "--capture-rates",
        type=str,
        default=None,
        help="Comma-separated CAPTURE_RATE values (default: 0.3,0.4,0.5)",
    )
    parser.add_argument(
        "--rejection-penalties",
        type=str,
        default=None,
        help="Comma-separated REJECTION_BASE_PENALTY values (default: 1.0,1.5,2.0)",
    )
    parser.add_argument(
        "--dd-risks",
        type=str,
        default=None,
        help="Comma-separated DD_RISK_INCREASE values (default: 1.5,1.8,2.0)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Random seed for reproducibility",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=4,
        help="Number of parallel workers (default: 4)",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress progress output",
    )

    args = parser.parse_args()

    # Parse parameter ranges
    capture_rates = None
    if args.capture_rates:
        capture_rates = [float(x.strip()) for x in args.capture_rates.split(",")]

    rejection_penalties = None
    if args.rejection_penalties:
        rejection_penalties = [float(x.strip()) for x in args.rejection_penalties.split(",")]

    dd_risks = None
    if args.dd_risks:
        dd_risks = [float(x.strip()) for x in args.dd_risks.split(",")]

    print("=" * 80)
    print("BRINKSMANSHIP PARAMETER SWEEP SIMULATION")
    print("=" * 80)
    print(f"Scenario: {args.scenario}")
    print(f"Games per pairing: {args.games}")
    print(f"Workers: {args.workers}")
    if args.seed is not None:
        print(f"Seed: {args.seed}")
    print()

    start_time = time.time()

    results = run_parameter_sweep(
        scenario_id=args.scenario,
        capture_rates=capture_rates,
        rejection_penalties=rejection_penalties,
        dd_risks=dd_risks,
        num_games=args.games,
        seed=args.seed,
        max_workers=args.workers,
        quiet=args.quiet,
    )

    duration = time.time() - start_time

    print_sweep_results(results)

    print()
    print(f"Sweep completed in {duration:.1f} seconds")
    print("=" * 80)

    # Return exit code based on whether any combination passed
    passing_count = sum(1 for r in results if r.passes_all)
    sys.exit(0 if passing_count > 0 else 1)


if __name__ == "__main__":
    main()
