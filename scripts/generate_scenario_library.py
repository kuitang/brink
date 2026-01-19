#!/usr/bin/env python3
"""Generate the complete Brinksmanship scenario library.

This script generates all 10 seed scenarios for the game, validating each
one before completion. Scenarios can be generated in parallel for speed.

Usage:
    # Generate all 10 scenarios
    python scripts/generate_scenario_library.py

    # Generate specific scenarios by number
    python scripts/generate_scenario_library.py --scenarios 1,2,3

    # Skip already-valid scenarios
    python scripts/generate_scenario_library.py --skip-valid

    # Parallel generation (multiple concurrent generations)
    python scripts/generate_scenario_library.py --parallel 3

    # Quick test with fewer simulation games
    python scripts/generate_scenario_library.py --games-per-test 25

Exit codes:
    0: All scenarios generated and validated successfully
    1: Some scenarios failed to validate
    2: Fatal error
"""

import argparse
import asyncio
import json
import logging
import sys
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path

# Add src to path for development
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from brinksmanship.generation.scenario_generator import ScenarioGenerator
from brinksmanship.generation.validator import ScenarioValidator, ValidationResult
from brinksmanship.generation.schemas import Scenario, save_scenario, load_scenario

# Set up logging to both console and file
LOG_DIR = Path("playtest_results")
LOG_DIR.mkdir(exist_ok=True)

log_file = LOG_DIR / f"generation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(log_file),
    ],
)
logger = logging.getLogger(__name__)
logger.info(f"Logging to: {log_file}")


# =============================================================================
# Scenario Library Definition
# =============================================================================

@dataclass
class ScenarioSpec:
    """Specification for a scenario to generate."""
    number: int
    title: str
    prompt: str
    theme: str
    filename: str


SCENARIO_LIBRARY: list[ScenarioSpec] = [
    ScenarioSpec(
        number=1,
        title="Cuban Missile Crisis",
        prompt="""Cuban Missile Crisis, October 1962. Kennedy vs Khrushchev. Nuclear brinkmanship
over Soviet missiles in Cuba. The world stands on the brink of nuclear war as two superpowers
face off in the most dangerous confrontation of the Cold War. Kennedy must balance domestic
political pressure with the risk of escalation, while Khrushchev seeks to protect his Cuban
ally without triggering armageddon.""",
        theme="crisis",
        filename="cuban_missile_crisis.json",
    ),
    ScenarioSpec(
        number=2,
        title="Berlin Blockade",
        prompt="""Berlin Blockade 1948-49. Stalin's blockade of West Berlin, Allied airlift response.
The Soviets cut off all ground access to West Berlin, attempting to force the Western powers
to abandon the city. The Allies must decide whether to confront, negotiate, or find a creative
solution. A test of wills that will shape the Cold War for decades.""",
        theme="crisis",
        filename="berlin_blockade.json",
    ),
    ScenarioSpec(
        number=3,
        title="Taiwan Strait Crisis",
        prompt="""Taiwan Strait Crisis. US-China tensions over Taiwan's status, ambiguity and deterrence.
The delicate balance of strategic ambiguity faces its greatest test as tensions rise in the
Taiwan Strait. Both sides must navigate between deterrence and reassurance, knowing that
miscalculation could lead to catastrophic conflict.""",
        theme="crisis",
        filename="taiwan_strait_crisis.json",
    ),
    ScenarioSpec(
        number=4,
        title="Silicon Valley Tech Wars",
        prompt="""Silicon Valley tech giants battling for market dominance. Acquisitions, platform wars,
antitrust threats. Two tech companies compete for dominance in a rapidly evolving market.
They must decide whether to compete, cooperate, or attempt to eliminate the competition
entirely. Regulatory threats loom as market power grows.""",
        theme="rivals",
        filename="silicon_valley_tech_wars.json",
    ),
    ScenarioSpec(
        number=5,
        title="OPEC Oil Politics",
        prompt="""OPEC oil politics. Cartel discipline, production quotas, price wars between Saudi Arabia
and rivals. The world's oil producers must balance their desire for high prices against the
temptation to cheat on quotas. Can the cartel maintain discipline, or will defection lead
to a price war that hurts everyone?""",
        theme="rivals",
        filename="opec_oil_politics.json",
    ),
    ScenarioSpec(
        number=6,
        title="Brexit Negotiations",
        prompt="""Brexit negotiations. UK-EU divorce terms, trade deals, Irish border question.
The UK and EU must negotiate the terms of their separation. Both sides have red lines,
but a no-deal outcome would hurt everyone. Can they find a mutually acceptable agreement,
or will negotiations collapse?""",
        theme="allies",
        filename="brexit_negotiations.json",
    ),
    ScenarioSpec(
        number=7,
        title="NATO Burden Sharing",
        prompt="""NATO burden sharing. Free-riding accusations, credible commitment to collective defense.
Alliance members must decide how much to contribute to collective defense. Some members
are accused of free-riding while others bear disproportionate costs. Can the alliance
maintain solidarity, or will disputes undermine collective security?""",
        theme="allies",
        filename="nato_burden_sharing.json",
    ),
    ScenarioSpec(
        number=8,
        title="Cold War Espionage",
        prompt="""Cold War espionage. Mole hunts, double agents, disinformation campaigns.
Intelligence services face off in a shadow war of spies and secrets. Each side tries to
penetrate the other while protecting their own agents. Trust is a commodity in short supply
as the specter of betrayal hangs over every interaction.""",
        theme="espionage",
        filename="cold_war_espionage.json",
    ),
    ScenarioSpec(
        number=9,
        title="Byzantine Succession",
        prompt="""Byzantine imperial succession. Palace factions, legitimacy claims, religious politics.
The Emperor is dying and the succession is contested. Powerful factions vie for control,
each claiming divine right and popular support. The empire's fate hangs in the balance
as intrigue and ambition clash in the corridors of power.""",
        theme="default",
        filename="byzantine_succession.json",
    ),
    ScenarioSpec(
        number=10,
        title="Medici Banking Dynasty",
        prompt="""Medici banking dynasty. 15th century Florence, papal politics, rival families.
The Medici face challenges to their banking empire and political influence. Rival families
seek to undermine them, while the Pope's favor could make or break their fortunes.
Navigate the treacherous waters of Renaissance politics and finance.""",
        theme="default",
        filename="medici_banking_dynasty.json",
    ),
]


# =============================================================================
# Trace Writing Functions
# =============================================================================


def save_validation_trace(
    spec: ScenarioSpec,
    iteration: int,
    result: ValidationResult,
    scenario: Scenario | None = None,
) -> Path:
    """Save validation result to a trace file.

    Args:
        spec: Scenario specification
        iteration: Iteration number
        result: Validation result
        scenario: Optional scenario object

    Returns:
        Path to the saved trace file
    """
    trace_dir = LOG_DIR / "traces"
    trace_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    trace_file = trace_dir / f"{spec.number:02d}_{spec.filename.replace('.json', '')}_{iteration}_{timestamp}.json"

    trace_data = {
        "scenario_number": spec.number,
        "scenario_title": spec.title,
        "iteration": iteration,
        "timestamp": timestamp,
        "validation_passed": result.overall_passed,
        "validation_result": result.to_dict(),
    }

    if scenario:
        trace_data["scenario_summary"] = {
            "turns": len(scenario.turns),
            "branches": len(scenario.branches),
            "matrix_types": sorted(t.value for t in scenario.get_all_matrix_types()),
        }

    with open(trace_file, "w") as f:
        json.dump(trace_data, f, indent=2)

    logger.info(f"[{spec.number}] Trace saved: {trace_file}")
    return trace_file


# =============================================================================
# Generation and Validation Functions
# =============================================================================


async def generate_single_scenario(
    spec: ScenarioSpec,
    output_dir: Path,
    max_iterations: int,
    games_per_test: int,
) -> tuple[bool, str]:
    """Generate and validate a single scenario with agentic error feedback.

    This function:
    1. Generates a scenario using LLM
    2. Runs DETERMINISTIC checks first (fast fail on structural issues)
    3. Only runs balance simulation if deterministic checks pass
    4. Feeds back errors to LLM for retry with context

    Args:
        spec: Scenario specification
        output_dir: Directory to save scenarios
        max_iterations: Maximum generation attempts
        games_per_test: Games per validation pairing

    Returns:
        Tuple of (success, message)
    """
    output_path = output_dir / spec.filename

    logger.info(f"[{spec.number}] Generating: {spec.title}")

    generator = ScenarioGenerator()
    validator = ScenarioValidator(simulation_games=games_per_test)

    previous_errors: list[str] = []
    reasoning_traces: list[dict] = []

    for iteration in range(max_iterations):
        try:
            # Generate scenario with previous error feedback
            logger.info(f"[{spec.number}] Iteration {iteration+1}: Calling LLM...")
            if previous_errors:
                logger.info(f"[{spec.number}] Feeding back {len(previous_errors)} errors from previous attempt")

            scenario = await generator.generate_scenario(
                theme=spec.theme,
                setting=spec.prompt,
                additional_context=f"Title: {spec.title}",
                num_turns=14,
                previous_errors=previous_errors if previous_errors else None,
            )

            # Update title if needed
            if scenario.title.startswith("Scenario:"):
                scenario_dict = scenario.model_dump(mode="json")
                scenario_dict["title"] = spec.title
                scenario = Scenario.model_validate(scenario_dict)

            logger.info(
                f"[{spec.number}] Generated: {len(scenario.turns)} turns, "
                f"{len(scenario.get_all_matrix_types())} types"
            )

            # STEP 1: Run DETERMINISTIC checks first (fast fail)
            logger.info(f"[{spec.number}] Running deterministic checks...")
            deterministic_result = validator.validate(
                scenario=scenario,
                run_simulation=False,  # Skip simulation for now
                check_narrative=False,
            )

            # Collect deterministic errors
            deterministic_errors = []
            for issue in deterministic_result.get_critical_issues() + deterministic_result.get_major_issues():
                deterministic_errors.append(issue.message)

            if deterministic_errors:
                logger.warning(
                    f"[{spec.number}] Deterministic checks failed ({len(deterministic_errors)} issues)"
                )
                for err in deterministic_errors[:5]:
                    logger.warning(f"[{spec.number}]   - {err}")

                # Save trace with deterministic failure
                save_validation_trace(spec, iteration + 1, deterministic_result, scenario)

                # Store reasoning trace
                reasoning_traces.append({
                    "iteration": iteration + 1,
                    "phase": "deterministic",
                    "passed": False,
                    "errors": deterministic_errors,
                    "action": "retry with error feedback",
                })

                # Feed back errors for next iteration
                previous_errors = deterministic_errors
                continue  # Skip simulation, retry immediately

            logger.info(f"[{spec.number}] Deterministic checks PASSED")

            # STEP 2: Run simulation checks (only if deterministic passed)
            logger.info(f"[{spec.number}] Running balance simulation ({games_per_test} games per pairing)...")
            full_result = validator.validate(
                scenario=scenario,
                run_simulation=True,
                check_narrative=False,
            )

            # Save trace for every iteration
            save_validation_trace(spec, iteration + 1, full_result, scenario)

            if full_result.overall_passed:
                # Save scenario
                save_scenario(scenario, str(output_path))
                logger.info(f"[{spec.number}] PASSED: Saved to {output_path}")

                # Save reasoning trace
                reasoning_traces.append({
                    "iteration": iteration + 1,
                    "phase": "simulation",
                    "passed": True,
                    "action": "saved scenario",
                })
                _save_reasoning_trace(spec, reasoning_traces)

                return True, f"Success: {spec.title}"

            # Collect simulation errors
            simulation_errors = []
            for issue in full_result.get_critical_issues() + full_result.get_major_issues():
                simulation_errors.append(issue.message)

            logger.warning(
                f"[{spec.number}] Simulation checks failed ({len(simulation_errors)} issues)"
            )
            for err in simulation_errors[:3]:
                logger.warning(f"[{spec.number}]   - {err}")

            # Store reasoning trace
            reasoning_traces.append({
                "iteration": iteration + 1,
                "phase": "simulation",
                "passed": False,
                "errors": simulation_errors,
                "action": "retry with error feedback",
            })

            # Feed back errors for next iteration
            previous_errors = simulation_errors

        except Exception as e:
            logger.error(f"[{spec.number}] Error in iteration {iteration+1}: {e}")
            import traceback
            logger.error(traceback.format_exc())

            # Store error in reasoning trace
            reasoning_traces.append({
                "iteration": iteration + 1,
                "phase": "generation",
                "passed": False,
                "errors": [str(e)],
                "action": "retry after exception",
            })

            previous_errors = [f"Generation error: {str(e)}"]

    # Save final reasoning trace even on failure
    _save_reasoning_trace(spec, reasoning_traces)

    return False, f"Failed after {max_iterations} iterations: {spec.title}"


def _save_reasoning_trace(spec: ScenarioSpec, traces: list[dict]) -> Path:
    """Save the full reasoning trace for a scenario generation.

    Args:
        spec: Scenario specification
        traces: List of reasoning trace entries

    Returns:
        Path to saved trace file
    """
    trace_dir = LOG_DIR / "reasoning"
    trace_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    trace_file = trace_dir / f"{spec.number:02d}_{spec.filename.replace('.json', '')}_reasoning_{timestamp}.json"

    trace_data = {
        "scenario_number": spec.number,
        "scenario_title": spec.title,
        "total_iterations": len(traces),
        "final_status": traces[-1]["passed"] if traces else False,
        "traces": traces,
    }

    with open(trace_file, "w") as f:
        json.dump(trace_data, f, indent=2)

    logger.info(f"[{spec.number}] Reasoning trace saved: {trace_file}")
    return trace_file


async def check_existing_scenario(
    spec: ScenarioSpec,
    output_dir: Path,
    games_per_test: int,
) -> bool:
    """Check if an existing scenario is valid.

    Args:
        spec: Scenario specification
        output_dir: Directory containing scenarios
        games_per_test: Games per validation pairing

    Returns:
        True if scenario exists and is valid
    """
    output_path = output_dir / spec.filename

    if not output_path.exists():
        return False

    try:
        scenario = load_scenario(str(output_path))
        validator = ScenarioValidator(simulation_games=games_per_test)
        result = validator.validate(scenario=scenario, run_simulation=True)
        return result.overall_passed
    except Exception as e:
        logger.warning(f"[{spec.number}] Error validating existing: {e}")
        return False


async def generate_scenarios_sequential(
    specs: list[ScenarioSpec],
    output_dir: Path,
    max_iterations: int,
    games_per_test: int,
    skip_valid: bool,
) -> list[tuple[int, bool, str]]:
    """Generate scenarios one at a time.

    Args:
        specs: List of scenario specifications
        output_dir: Directory to save scenarios
        max_iterations: Maximum generation attempts per scenario
        games_per_test: Games per validation pairing
        skip_valid: Whether to skip already-valid scenarios

    Returns:
        List of (scenario_number, success, message) tuples
    """
    results = []

    for spec in specs:
        if skip_valid:
            logger.info(f"[{spec.number}] Checking existing scenario...")
            if await check_existing_scenario(spec, output_dir, games_per_test):
                logger.info(f"[{spec.number}] Already valid, skipping")
                results.append((spec.number, True, f"Skipped (already valid): {spec.title}"))
                continue

        success, message = await generate_single_scenario(
            spec, output_dir, max_iterations, games_per_test
        )
        results.append((spec.number, success, message))

    return results


async def generate_scenarios_parallel(
    specs: list[ScenarioSpec],
    output_dir: Path,
    max_iterations: int,
    games_per_test: int,
    skip_valid: bool,
    parallel: int,
) -> list[tuple[int, bool, str]]:
    """Generate scenarios with limited concurrency.

    Args:
        specs: List of scenario specifications
        output_dir: Directory to save scenarios
        max_iterations: Maximum generation attempts per scenario
        games_per_test: Games per validation pairing
        skip_valid: Whether to skip already-valid scenarios
        parallel: Number of concurrent generations

    Returns:
        List of (scenario_number, success, message) tuples
    """
    # Filter out already-valid scenarios if requested
    to_generate = []
    skipped = []

    if skip_valid:
        for spec in specs:
            if await check_existing_scenario(spec, output_dir, games_per_test):
                logger.info(f"[{spec.number}] Already valid, skipping")
                skipped.append((spec.number, True, f"Skipped (already valid): {spec.title}"))
            else:
                to_generate.append(spec)
    else:
        to_generate = specs

    # Use semaphore to limit concurrency
    semaphore = asyncio.Semaphore(parallel)

    async def limited_generate(spec: ScenarioSpec) -> tuple[int, bool, str]:
        async with semaphore:
            success, message = await generate_single_scenario(
                spec, output_dir, max_iterations, games_per_test
            )
            return spec.number, success, message

    # Run with limited concurrency
    tasks = [limited_generate(spec) for spec in to_generate]
    generated = await asyncio.gather(*tasks)

    # Combine and sort results
    results = skipped + list(generated)
    results.sort(key=lambda x: x[0])

    return results


def run_playtest_for_scenario(
    scenario_path: Path,
    games: int = 100,
    seed: int | None = None,
) -> dict:
    """Run a comprehensive playtest for a scenario.

    Args:
        scenario_path: Path to scenario JSON
        games: Number of games per pairing
        seed: Random seed

    Returns:
        Playtest results dictionary
    """
    # Import here to avoid circular imports
    from scripts.run_playtest import (
        run_pairing,
        STRATEGIES,
    )

    strategy_names = list(STRATEGIES.keys())
    results = {}
    all_wins = {name: 0 for name in strategy_names}
    all_games = {name: 0 for name in strategy_names}

    # Run all pairings
    for i, name_a in enumerate(strategy_names):
        for name_b in strategy_names[i:]:
            pairing_key = f"{name_a}:{name_b}"
            pairing_result = run_pairing(
                name_a, name_b, games,
                base_seed=seed,
                log_dir=None,
                workers=4,
            )
            results[pairing_key] = pairing_result

            # Track wins
            all_wins[name_a] += pairing_result["wins_a"]
            all_games[name_a] += pairing_result["total_games"]
            if name_a != name_b:
                all_wins[name_b] += pairing_result["wins_b"]
                all_games[name_b] += pairing_result["total_games"]

    # Calculate overall win rates
    overall_win_rates = {
        name: all_wins[name] / all_games[name] if all_games[name] > 0 else 0
        for name in strategy_names
    }

    return {
        "scenario": str(scenario_path),
        "pairings": results,
        "overall_win_rates": overall_win_rates,
        "dominant_strategies": [
            name for name, rate in overall_win_rates.items() if rate > 0.60
        ],
    }


def print_summary(results: list[tuple[int, bool, str]]) -> None:
    """Print a summary of generation results."""
    print("\n" + "=" * 70)
    print("SCENARIO LIBRARY GENERATION SUMMARY")
    print("=" * 70)

    success_count = sum(1 for _, success, _ in results if success)
    total = len(results)

    for number, success, message in results:
        status = "OK" if success else "FAIL"
        print(f"  [{number:2d}] {status}: {message}")

    print("-" * 70)
    print(f"Total: {success_count}/{total} scenarios successfully generated")

    if success_count < total:
        print("\nFailed scenarios need manual intervention or more iterations.")

    print("=" * 70)


def main():
    parser = argparse.ArgumentParser(
        description="Generate the complete Brinksmanship scenario library",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument(
        "--scenarios",
        type=str,
        default=None,
        help="Comma-separated scenario numbers to generate (e.g., '1,2,3'). Default: all",
    )

    parser.add_argument(
        "--skip-valid",
        action="store_true",
        help="Skip scenarios that already exist and pass validation",
    )

    parser.add_argument(
        "--parallel",
        type=int,
        default=1,
        help="Number of scenarios to generate concurrently (default: 1)",
    )

    parser.add_argument(
        "--max-iterations",
        type=int,
        default=5,
        help="Maximum generation attempts per scenario (default: 5)",
    )

    parser.add_argument(
        "--games-per-test",
        type=int,
        default=50,
        help="Number of games per validation pairing (default: 50)",
    )

    parser.add_argument(
        "--output-dir",
        type=str,
        default="scenarios",
        help="Directory to save generated scenarios (default: scenarios)",
    )

    parser.add_argument(
        "--list",
        action="store_true",
        help="List all scenarios in the library and exit",
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Print verbose output",
    )

    args = parser.parse_args()

    # Set logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Handle --list
    if args.list:
        print("Brinksmanship Scenario Library:")
        print("-" * 70)
        for spec in SCENARIO_LIBRARY:
            print(f"  {spec.number:2d}. {spec.title}")
            print(f"      Theme: {spec.theme}")
            print(f"      File: {spec.filename}")
        return 0

    # Parse scenario numbers
    if args.scenarios:
        try:
            numbers = [int(n.strip()) for n in args.scenarios.split(",")]
            specs = [s for s in SCENARIO_LIBRARY if s.number in numbers]
            if not specs:
                print(f"Error: No valid scenario numbers in: {args.scenarios}", file=sys.stderr)
                return 2
        except ValueError as e:
            print(f"Error parsing scenario numbers: {e}", file=sys.stderr)
            return 2
    else:
        specs = SCENARIO_LIBRARY

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"Generating {len(specs)} scenarios to {output_dir}")
    logger.info(f"Max iterations: {args.max_iterations}, Games per test: {args.games_per_test}")
    if args.parallel > 1:
        logger.info(f"Parallel generations: {args.parallel}")

    start_time = time.time()

    # Run generation
    if args.parallel > 1:
        results = asyncio.run(
            generate_scenarios_parallel(
                specs=specs,
                output_dir=output_dir,
                max_iterations=args.max_iterations,
                games_per_test=args.games_per_test,
                skip_valid=args.skip_valid,
                parallel=args.parallel,
            )
        )
    else:
        results = asyncio.run(
            generate_scenarios_sequential(
                specs=specs,
                output_dir=output_dir,
                max_iterations=args.max_iterations,
                games_per_test=args.games_per_test,
                skip_valid=args.skip_valid,
            )
        )

    elapsed = time.time() - start_time

    # Print summary
    print_summary(results)
    print(f"\nTotal time: {elapsed:.1f} seconds")

    # Return appropriate exit code
    all_success = all(success for _, success, _ in results)
    return 0 if all_success else 1


if __name__ == "__main__":
    sys.exit(main())
