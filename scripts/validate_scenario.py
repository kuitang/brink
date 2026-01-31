#!/usr/bin/env python3
"""Deterministic scenario validation - no LLM required for core checks.

This script validates Brinksmanship scenarios against structural requirements
and optionally runs balance simulations to detect dominant strategies.

Usage:
    # Basic validation (structural checks only)
    python scripts/validate_scenario.py scenarios/my_scenario.json

    # With balance simulation
    python scripts/validate_scenario.py scenarios/my_scenario.json --simulate

    # With narrative consistency check (requires LLM)
    python scripts/validate_scenario.py scenarios/my_scenario.json --check-narrative

    # Full validation with custom simulation settings
    python scripts/validate_scenario.py scenarios/my_scenario.json \\
        --simulate --games 100 --seed 42 --output results.json
"""

import argparse
import json
import sys
from pathlib import Path

# Add src to path for development
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from brinksmanship.generation.validator import (
    ScenarioValidator,
    ValidationResult,
)


def format_check_result(name: str, result) -> str:
    """Format a single check result for display."""
    if result is None:
        return f"  {name}: SKIPPED"

    status = "PASS" if result.passed else "FAIL"
    lines = [f"  {name}: {status}"]

    # Add metrics
    for key, value in result.metrics.items():
        if isinstance(value, list) and len(value) > 5:
            lines.append(f"    {key}: [{len(value)} items]")
        elif isinstance(value, float):
            lines.append(f"    {key}: {value:.2f}")
        else:
            lines.append(f"    {key}: {value}")

    # Add issues
    for issue in result.issues:
        severity = issue.severity.value.upper()
        lines.append(f"    [{severity}] {issue.message}")

    return "\n".join(lines)


def print_validation_report(result: ValidationResult) -> None:
    """Print human-readable validation report."""
    print("\n" + "=" * 70)
    print("SCENARIO VALIDATION REPORT")
    print("=" * 70)

    if result.scenario_path:
        print(f"Scenario: {result.scenario_path}")
    if result.scenario_id:
        print(f"ID: {result.scenario_id}")

    overall = "PASSED" if result.overall_passed else "FAILED"
    print(f"\nOverall: {overall}")

    print("\n" + "-" * 70)
    print("CHECK RESULTS")
    print("-" * 70)

    print(format_check_result("Game Variety", result.game_variety))
    print(format_check_result("Act Structure", result.act_structure))
    print(format_check_result("Branching", result.branching))
    print(format_check_result("Settlement Config", result.settlement))
    print(format_check_result("Balance", result.balance))
    print(format_check_result("Narrative", result.narrative))

    if result.simulation_results:
        print("\n" + "-" * 70)
        print("SIMULATION STATISTICS")
        print("-" * 70)
        sim = result.simulation_results
        print(f"  Games played: {sim.games_played}")
        print(f"  Average game length: {sim.avg_game_length:.1f} turns")
        print(f"  Elimination rate: {sim.elimination_rate * 100:.1f}%")
        print(f"  Mutual destruction rate: {sim.mutual_destruction_rate * 100:.1f}%")
        print(f"  Crisis termination rate: {sim.crisis_termination_rate * 100:.1f}%")
        print(f"  VP std dev: {sim.vp_std_dev:.1f}")

        print("\n  Strategy Win Rates:")
        for strategy, rate in sorted(sim.strategy_win_rates.items()):
            print(f"    {strategy}: {rate * 100:.1f}%")

    # Summary
    critical = result.get_critical_issues()
    major = result.get_major_issues()

    print("\n" + "-" * 70)
    print("SUMMARY")
    print("-" * 70)
    print(f"  Critical issues: {len(critical)}")
    print(f"  Major issues: {len(major)}")
    print(f"  Total issues: {len(result.get_all_issues())}")

    if not result.overall_passed:
        print("\n  VALIDATION FAILED - Fix critical and major issues before use")

    print("\n" + "=" * 70)


def main():
    parser = argparse.ArgumentParser(
        description="Validate Brinksmanship scenario files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "scenario_path",
        help="Path to scenario JSON file",
    )
    parser.add_argument(
        "--simulate",
        action="store_true",
        help="Run balance simulation to detect dominant strategies",
    )
    parser.add_argument(
        "--games",
        type=int,
        default=50,
        help="Number of games per strategy pairing (default: 50)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Random seed for reproducibility",
    )
    parser.add_argument(
        "--check-narrative",
        action="store_true",
        help="Run narrative consistency check (requires LLM)",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default=None,
        help="Output JSON file for validation results",
    )
    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Only output JSON, no human-readable report",
    )

    args = parser.parse_args()

    # Validate file exists
    scenario_path = Path(args.scenario_path)
    if not scenario_path.exists():
        print(f"Error: Scenario file not found: {scenario_path}", file=sys.stderr)
        sys.exit(1)

    # Create validator
    validator = ScenarioValidator(
        simulation_games=args.games,
        simulation_seed=args.seed,
    )

    # Run validation
    try:
        result = validator.validate(
            scenario_path=str(scenario_path),
            run_simulation=args.simulate,
            check_narrative=args.check_narrative,
        )
    except Exception as e:
        print(f"Error during validation: {e}", file=sys.stderr)
        sys.exit(1)

    # Print report
    if not args.quiet:
        print_validation_report(result)

    # Write JSON output
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w") as f:
            json.dump(result.to_dict(), f, indent=2)
        if not args.quiet:
            print(f"\nResults written to: {output_path}")
    elif args.quiet:
        # If quiet and no output file, print JSON to stdout
        print(json.dumps(result.to_dict(), indent=2))

    # Exit with appropriate code
    sys.exit(0 if result.overall_passed else 1)


if __name__ == "__main__":
    main()
