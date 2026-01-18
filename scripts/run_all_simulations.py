#!/usr/bin/env python3
"""
Simulation Orchestrator for Brinksmanship

Runs all simulation modules and produces a consolidated report.
Can run individual simulations or all at once.

Usage:
    # Run all simulations
    python scripts/run_all_simulations.py

    # Run specific simulations
    python scripts/run_all_simulations.py --only balance
    python scripts/run_all_simulations.py --only crisis
    python scripts/run_all_simulations.py --only stability
    python scripts/run_all_simulations.py --only variance
    python scripts/run_all_simulations.py --only settlement
    python scripts/run_all_simulations.py --only information

    # Run multiple specific simulations
    python scripts/run_all_simulations.py --only balance,crisis,stability
"""

import subprocess
import sys
import argparse
from pathlib import Path


SIMULATIONS = {
    "balance": {
        "script": "balance_simulation.py",
        "description": "Core game balance with strategy pairings",
        "args": ["--games", "200"],  # Reduced for orchestrator
    },
    "crisis": {
        "script": "sim_crisis_termination.py",
        "description": "Crisis termination probability mechanics",
        "args": [],
    },
    "stability": {
        "script": "sim_stability.py",
        "description": "Stability update and decay mechanics",
        "args": [],
    },
    "variance": {
        "script": "sim_variance.py",
        "description": "Variance formula and final resolution",
        "args": [],
    },
    "settlement": {
        "script": "sim_settlement.py",
        "description": "Settlement protocol and offer constraints",
        "args": [],
    },
    "information": {
        "script": "sim_information.py",
        "description": "Information games and decay mechanics",
        "args": [],
    },
}


def run_simulation(name: str, script: str, args: list, scripts_dir: Path) -> tuple:
    """Run a single simulation and return (success, output)."""
    script_path = scripts_dir / script

    if not script_path.exists():
        return False, f"Script not found: {script_path}"

    cmd = [sys.executable, str(script_path)] + args

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,  # 5 minute timeout
        )
        return result.returncode == 0, result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        return False, "Simulation timed out after 5 minutes"
    except Exception as e:
        return False, f"Error running simulation: {e}"


def print_header():
    print("=" * 80)
    print("BRINKSMANSHIP SIMULATION ORCHESTRATOR")
    print("=" * 80)
    print()


def print_summary(results: dict):
    print("\n" + "=" * 80)
    print("SIMULATION SUMMARY")
    print("=" * 80)

    print(f"\n{'Simulation':<20} {'Status':>10} {'Description':<45}")
    print("-" * 80)

    passed = 0
    failed = 0
    for name, (success, _) in results.items():
        status = "PASSED" if success else "FAILED"
        desc = SIMULATIONS.get(name, {}).get("description", "")[:45]
        print(f"{name:<20} {status:>10} {desc:<45}")
        if success:
            passed += 1
        else:
            failed += 1

    print("-" * 80)
    print(f"Total: {passed} passed, {failed} failed out of {passed + failed} simulations")

    if failed > 0:
        print("\nFailed simulations output:")
        for name, (success, output) in results.items():
            if not success:
                print(f"\n--- {name} ---")
                print(output[:1000])  # First 1000 chars of error


def main():
    parser = argparse.ArgumentParser(
        description="Run Brinksmanship simulations",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Available simulations:
  balance      Core game balance with strategy pairings
  crisis       Crisis termination probability mechanics
  stability    Stability update and decay mechanics
  variance     Variance formula and final resolution
  settlement   Settlement protocol and offer constraints
  information  Information games and decay mechanics

Examples:
  python scripts/run_all_simulations.py                    # Run all
  python scripts/run_all_simulations.py --only balance     # Run one
  python scripts/run_all_simulations.py --only crisis,stability  # Run subset
        """
    )
    parser.add_argument(
        "--only",
        type=str,
        default=None,
        help="Comma-separated list of simulations to run"
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducibility (default: 42)"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show full output from each simulation"
    )
    args = parser.parse_args()

    # Determine which simulations to run
    if args.only:
        sim_names = [s.strip() for s in args.only.split(",")]
        invalid = [s for s in sim_names if s not in SIMULATIONS]
        if invalid:
            print(f"Error: Unknown simulations: {invalid}")
            print(f"Available: {list(SIMULATIONS.keys())}")
            sys.exit(1)
    else:
        sim_names = list(SIMULATIONS.keys())

    scripts_dir = Path(__file__).parent

    print_header()
    print(f"Running simulations: {', '.join(sim_names)}")
    print(f"Random seed: {args.seed}")
    print()

    results = {}

    for name in sim_names:
        sim_info = SIMULATIONS[name]
        print(f"\n{'='*80}")
        print(f"RUNNING: {name} - {sim_info['description']}")
        print("=" * 80)

        # Add seed to args if supported
        sim_args = sim_info["args"] + ["--seed", str(args.seed)]

        success, output = run_simulation(
            name,
            sim_info["script"],
            sim_args,
            scripts_dir
        )

        results[name] = (success, output)

        if args.verbose or not success:
            print(output)
        else:
            # Print abbreviated output (first and last few lines)
            lines = output.strip().split("\n")
            if len(lines) > 20:
                print("\n".join(lines[:10]))
                print(f"... ({len(lines) - 20} lines omitted) ...")
                print("\n".join(lines[-10:]))
            else:
                print(output)

    print_summary(results)

    # Exit with error if any simulation failed
    if any(not success for success, _ in results.values()):
        sys.exit(1)


if __name__ == "__main__":
    main()
