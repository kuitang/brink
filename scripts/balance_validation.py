#!/usr/bin/env python3
"""E2E Balance Validation for Brinksmanship.

Runs comprehensive balance testing across all scenarios using dual-metric evaluation.
Validates that no strategy dominates and that cooperation incentives create balanced gameplay.

Usage:
    uv run python scripts/balance_validation.py

    # Run with more games (slower but more accurate)
    uv run python scripts/balance_validation.py --games 500

    # Run with reproducible seed
    uv run python scripts/balance_validation.py --games 100 --seed 42

    # Test specific scenarios only
    uv run python scripts/balance_validation.py --scenarios cuban_missile_crisis,berlin_blockade

See GAME_MANUAL.md Appendix C.6 for validation specifications.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from brinksmanship.storage import get_scenario_repository
from brinksmanship.testing.batch_runner import (
    BatchRunner,
    BatchResults,
    DETERMINISTIC_OPPONENTS,
    print_results_summary,
)


@dataclass
class ValidationResult:
    """Result of validating a single scenario."""

    scenario_id: str
    results: BatchResults
    checks: list[tuple[str, bool, str]] = field(default_factory=list)
    passed: bool = False

    def run_checks(self) -> None:
        """Run all balance checks and populate results."""
        self.checks = []
        agg = self.results.aggregate

        # Check 1: No strategy achieves >60% win rate (checked per-pairing)
        max_winrate = 0.0
        max_winrate_pairing = ""
        for pairing_key, stats in self.results.pairings.items():
            if stats.win_rate_a > max_winrate:
                max_winrate = stats.win_rate_a
                max_winrate_pairing = f"{pairing_key} (A)"
            if stats.win_rate_b > max_winrate:
                max_winrate = stats.win_rate_b
                max_winrate_pairing = f"{pairing_key} (B)"

        win_rate_pass = max_winrate <= 0.60
        self.checks.append((
            "No strategy >60% win rate",
            win_rate_pass,
            f"Max: {max_winrate*100:.1f}% ({max_winrate_pairing})"
        ))

        # Check 2: Mutual destruction rate in acceptable range (target: 10-20%, must be <25%)
        md_rate = agg.get("mutual_destruction_rate", 0)
        md_pass = md_rate < 0.25
        self.checks.append((
            "Mutual destruction <25%",
            md_pass,
            f"{md_rate*100:.1f}%"
        ))

        # Check 3: Settlement rate in acceptable range (30-70%)
        settle_rate = agg.get("settlement_rate", 0)
        settle_pass = 0.30 <= settle_rate <= 0.70
        self.checks.append((
            "Settlement rate 30-70%",
            settle_pass,
            f"{settle_rate*100:.1f}%"
        ))

        # Check 4: Positive-sum outcomes (total VP > 100 in cooperative games)
        avg_total = agg.get("avg_total_value", 0)
        total_pass = avg_total >= 80  # Allow some destruction loss
        self.checks.append((
            "Positive-sum outcomes (>80 avg)",
            total_pass,
            f"{avg_total:.1f}"
        ))

        # Check 5: Game length reasonable (8-16 turns)
        avg_turns = agg.get("avg_turns", 0)
        turns_pass = 8 <= avg_turns <= 16
        self.checks.append((
            "Game length 8-16 turns",
            turns_pass,
            f"{avg_turns:.1f}"
        ))

        # Check 6: VP variance in range (10-40)
        vp_std = agg.get("vp_std_dev", 0)
        var_pass = 10 <= vp_std <= 40
        self.checks.append((
            "VP variance 10-40",
            var_pass,
            f"{vp_std:.1f}"
        ))

        # Overall pass
        self.passed = all(c[1] for c in self.checks)


def get_all_scenarios() -> list[str]:
    """Get list of all available scenario IDs."""
    repo = get_scenario_repository()
    scenarios = repo.list_scenarios()
    return [s.id for s in scenarios]


def run_balance_validation(
    scenario_ids: Optional[list[str]] = None,
    num_games: int = 100,
    seed: Optional[int] = None,
    max_workers: int = 4,
    output_dir: Optional[str] = None,
    quiet: bool = False,
) -> list[ValidationResult]:
    """Run balance validation on specified scenarios.

    Args:
        scenario_ids: Scenarios to test (default: all)
        num_games: Games per opponent pairing
        seed: Base random seed
        max_workers: Parallel workers
        output_dir: Optional directory to save results
        quiet: Suppress progress output

    Returns:
        List of ValidationResult for each scenario
    """
    if scenario_ids is None:
        scenario_ids = get_all_scenarios()

    validation_results: list[ValidationResult] = []

    for idx, scenario_id in enumerate(scenario_ids):
        if not quiet:
            print(f"\n[{idx+1}/{len(scenario_ids)}] Validating: {scenario_id}")
            print("-" * 60)

        # Run batch simulation for this scenario
        runner = BatchRunner(scenario_id=scenario_id)

        scenario_seed = (seed + idx * 10000) if seed is not None else None

        batch_results = runner.run_all_pairings(
            num_games=num_games,
            seed=scenario_seed,
            max_workers=max_workers,
        )

        # Create validation result
        validation = ValidationResult(
            scenario_id=scenario_id,
            results=batch_results,
        )
        validation.run_checks()
        validation_results.append(validation)

        # Print summary for this scenario
        if not quiet:
            status = "PASS" if validation.passed else "FAIL"
            print(f"\n{scenario_id}: {status}")
            for check_name, check_pass, check_detail in validation.checks:
                mark = "OK" if check_pass else "FAIL"
                print(f"  [{mark}] {check_name}: {check_detail}")

    # Save detailed results if output_dir specified
    if output_dir:
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        for validation in validation_results:
            results_file = output_path / f"{validation.scenario_id}_validation.json"
            with open(results_file, "w") as f:
                json.dump({
                    "scenario_id": validation.scenario_id,
                    "passed": validation.passed,
                    "checks": [
                        {"name": c[0], "passed": c[1], "detail": c[2]}
                        for c in validation.checks
                    ],
                    "aggregate": validation.results.aggregate,
                }, f, indent=2)

        if not quiet:
            print(f"\nDetailed results saved to: {output_dir}")

    return validation_results


def print_validation_summary(results: list[ValidationResult]) -> None:
    """Print summary of all validation results."""
    print("\n" + "=" * 80)
    print("BALANCE VALIDATION SUMMARY")
    print("=" * 80)

    passing = [r for r in results if r.passed]
    failing = [r for r in results if not r.passed]

    print(f"\nScenarios tested: {len(results)}")
    print(f"Passing: {len(passing)}")
    print(f"Failing: {len(failing)}")

    # Table of results
    print("\n" + "-" * 80)
    print(f"{'Scenario':<30} | {'MD%':>6} | {'Settle%':>8} | {'Total':>6} | {'Turns':>6} | {'Status':>6}")
    print("-" * 80)

    for result in results:
        agg = result.results.aggregate
        status = "PASS" if result.passed else "FAIL"
        print(
            f"{result.scenario_id:<30} | "
            f"{agg.get('mutual_destruction_rate', 0)*100:>5.1f}% | "
            f"{agg.get('settlement_rate', 0)*100:>7.1f}% | "
            f"{agg.get('avg_total_value', 0):>6.1f} | "
            f"{agg.get('avg_turns', 0):>6.1f} | "
            f"{status:>6}"
        )

    print("-" * 80)

    # Detail failing scenarios
    if failing:
        print("\nFAILING SCENARIOS:")
        print("-" * 50)
        for result in failing:
            print(f"\n{result.scenario_id}:")
            for check_name, check_pass, check_detail in result.checks:
                if not check_pass:
                    print(f"  [FAIL] {check_name}: {check_detail}")

    # Overall verdict
    print("\n" + "=" * 80)
    if len(failing) == 0:
        print("OVERALL: PASS - All scenarios meet balance criteria")
    else:
        print(f"OVERALL: FAIL - {len(failing)} scenario(s) failed validation")
    print("=" * 80)


def main() -> None:
    """Run balance validation."""
    parser = argparse.ArgumentParser(
        description="E2E Balance Validation for all scenarios",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Runs comprehensive balance testing across all scenarios using dual-metric
evaluation. Validates that no strategy dominates and cooperation incentives
create balanced gameplay.

Validation Checks:
  - No strategy achieves >60% win rate against any other
  - Mutual destruction rate <25%
  - Settlement rate 30-70%
  - Positive-sum outcomes (avg total VP > 80)
  - Game length 8-16 turns
  - VP variance 10-40

Examples:
    uv run python scripts/balance_validation.py
    uv run python scripts/balance_validation.py --games 500 --seed 42
    uv run python scripts/balance_validation.py --scenarios cuban_missile_crisis
        """,
    )

    parser.add_argument(
        "--scenarios",
        type=str,
        default=None,
        help="Comma-separated scenario IDs (default: all)",
    )
    parser.add_argument(
        "--games",
        type=int,
        default=100,
        help="Games per opponent pairing (default: 100)",
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
        "--output",
        type=str,
        default=None,
        help="Output directory for detailed results",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress per-scenario output",
    )

    args = parser.parse_args()

    # Parse scenarios
    scenario_ids = None
    if args.scenarios:
        scenario_ids = [s.strip() for s in args.scenarios.split(",")]

    print("=" * 80)
    print("BRINKSMANSHIP E2E BALANCE VALIDATION")
    print("=" * 80)
    print(f"Games per pairing: {args.games}")
    print(f"Workers: {args.workers}")
    if args.seed is not None:
        print(f"Seed: {args.seed}")
    if scenario_ids:
        print(f"Scenarios: {', '.join(scenario_ids)}")
    else:
        print("Scenarios: all")

    start_time = time.time()

    results = run_balance_validation(
        scenario_ids=scenario_ids,
        num_games=args.games,
        seed=args.seed,
        max_workers=args.workers,
        output_dir=args.output,
        quiet=args.quiet,
    )

    duration = time.time() - start_time

    print_validation_summary(results)

    print(f"\nValidation completed in {duration:.1f} seconds")

    # Exit code based on pass/fail
    failing = [r for r in results if not r.passed]
    sys.exit(0 if len(failing) == 0 else 1)


if __name__ == "__main__":
    main()
