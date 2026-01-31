#!/usr/bin/env python3
"""Game Balance Simulation for Brinksmanship.

Runs comprehensive simulations using the ACTUAL deterministic opponent
implementations from brinksmanship.opponents.deterministic.

This script uses the unified game runner framework to ensure simulation
results match actual gameplay behavior exactly.

Usage:
    # Run all opponent pairings with default scenario
    uv run python scripts/balance_simulation.py --games 100

    # Run with specific scenario
    uv run python scripts/balance_simulation.py --scenario cuban_missile_crisis --games 100

    # Run specific pairings only
    uv run python scripts/balance_simulation.py --pairings "NashCalculator:TitForTat,Opportunist:GrimTrigger"

    # Run with reproducible seed
    uv run python scripts/balance_simulation.py --games 100 --seed 42

Opponents tested (from brinksmanship.opponents.deterministic):
    - NashCalculator: Pure game theorist, plays Nash equilibrium with risk awareness
    - SecuritySeeker: Spiral model actor, prefers cooperation unless threatened
    - Opportunist: Deterrence model, probes for weakness and exploits when ahead
    - Erratic: Unpredictable, ~40% cooperative / 60% competitive random
    - TitForTat: Classic reciprocator, mirrors opponent's last action
    - GrimTrigger: Cooperates until betrayed, then defects forever
"""

import argparse
import sys
from pathlib import Path

from brinksmanship.testing.batch_runner import (
    DETERMINISTIC_OPPONENTS,
    BatchRunner,
    print_results_summary,
)


def parse_pairings(pairings_str: str) -> list[tuple[str, str]]:
    """Parse pairings string into list of (opponent_a, opponent_b) tuples.

    Args:
        pairings_str: Comma-separated "A:B" pairs (e.g., "Nash:TitForTat,Opportunist:Erratic")

    Returns:
        List of (opponent_a_name, opponent_b_name) tuples
    """
    pairings = []
    for pair in pairings_str.split(","):
        pair = pair.strip()
        if ":" not in pair:
            raise ValueError(f"Invalid pairing format: '{pair}'. Expected 'OpponentA:OpponentB'")

        parts = pair.split(":")
        if len(parts) != 2:
            raise ValueError(f"Invalid pairing format: '{pair}'. Expected exactly one ':'")

        name_a, name_b = parts[0].strip(), parts[1].strip()

        if name_a not in DETERMINISTIC_OPPONENTS:
            raise ValueError(f"Unknown opponent: '{name_a}'. Available: {list(DETERMINISTIC_OPPONENTS.keys())}")
        if name_b not in DETERMINISTIC_OPPONENTS:
            raise ValueError(f"Unknown opponent: '{name_b}'. Available: {list(DETERMINISTIC_OPPONENTS.keys())}")

        pairings.append((name_a, name_b))

    return pairings


def main():
    """Run the balance simulation."""
    parser = argparse.ArgumentParser(
        description="Run game balance simulation using actual opponent implementations",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Available opponents:
  - NashCalculator: Pure game theorist, plays Nash equilibrium with risk awareness
  - SecuritySeeker: Spiral model actor, prefers cooperation unless threatened
  - Opportunist: Deterrence model, probes for weakness and exploits when ahead
  - Erratic: Unpredictable, ~40% cooperative / 60% competitive random
  - TitForTat: Classic reciprocator, mirrors opponent's last action
  - GrimTrigger: Cooperates until betrayed, then defects forever

Examples:
  # Run all pairings
  uv run python scripts/balance_simulation.py --games 100

  # Run specific pairings
  uv run python scripts/balance_simulation.py --pairings "NashCalculator:TitForTat"

  # Run with reproducible seed
  uv run python scripts/balance_simulation.py --games 100 --seed 42
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
        help="Number of games per pairing (default: 100)",
    )
    parser.add_argument(
        "--pairings",
        type=str,
        default=None,
        help="Specific pairings to test (e.g., 'NashCalculator:TitForTat,Opportunist:Erratic')",
    )
    parser.add_argument(
        "--opponents",
        type=str,
        default=None,
        help="Comma-separated list of opponents to test (default: all)",
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
        help="Output directory for results JSON",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress detailed output",
    )

    args = parser.parse_args()

    print("=" * 80)
    print("BRINKSMANSHIP BALANCE SIMULATION")
    print("=" * 80)
    print(f"Scenario: {args.scenario}")
    print(f"Games per pairing: {args.games}")
    print(f"Workers: {args.workers}")
    if args.seed is not None:
        print(f"Seed: {args.seed}")
    print()

    runner = BatchRunner(scenario_id=args.scenario)

    if args.pairings:
        # Run specific pairings
        try:
            pairings = parse_pairings(args.pairings)
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)

        print(f"Running {len(pairings)} pairing(s)...")
        import time
        from datetime import datetime

        from brinksmanship.testing.batch_runner import BatchResults

        start_time = time.time()
        results = BatchResults(
            scenario_id=args.scenario,
            timestamp=datetime.now().isoformat(),
        )

        for idx, (name_a, name_b) in enumerate(pairings):
            pairing_key = f"{name_a}:{name_b}"
            print(f"  [{idx + 1}/{len(pairings)}] {pairing_key}...", end=" ", flush=True)

            pairing_seed = (args.seed + idx * args.games) if args.seed is not None else None

            stats = runner.run_pairing(
                name_a,
                name_b,
                num_games=args.games,
                seed=pairing_seed,
                max_workers=args.workers,
            )

            results.pairings[pairing_key] = stats
            print(f"A:{stats.win_rate_a * 100:.0f}% B:{stats.win_rate_b * 100:.0f}%")

        results.compute_aggregate()
        results.duration_seconds = time.time() - start_time

    else:
        # Run all pairings
        opponent_names = None
        if args.opponents:
            opponent_names = [name.strip() for name in args.opponents.split(",")]
            # Validate names
            for name in opponent_names:
                if name not in DETERMINISTIC_OPPONENTS:
                    print(f"Error: Unknown opponent '{name}'", file=sys.stderr)
                    print(f"Available: {list(DETERMINISTIC_OPPONENTS.keys())}", file=sys.stderr)
                    sys.exit(1)

        print(f"Running all pairings of {len(opponent_names or DETERMINISTIC_OPPONENTS)} opponents...")

        results = runner.run_all_pairings(
            opponent_names=opponent_names,
            num_games=args.games,
            seed=args.seed,
            max_workers=args.workers,
            output_dir=args.output,
        )

    if not args.quiet:
        print_results_summary(results)

    # Save results if output specified
    if args.output:
        output_path = Path(args.output)
        output_path.mkdir(parents=True, exist_ok=True)
        results_file = output_path / "balance_simulation_results.json"
        with open(results_file, "w") as f:
            f.write(results.to_json())
        print(f"\nResults saved to: {results_file}")

    print("\n" + "=" * 80)
    print("SIMULATION COMPLETE")
    print("=" * 80)

    return results


if __name__ == "__main__":
    main()
