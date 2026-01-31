#!/usr/bin/env python3
"""Generate and validate Brinksmanship scenarios using an agentic pipeline.

This script generates scenarios from user prompts and iteratively refines them
until they pass all validation checks. It uses the existing scenario generator
and validator infrastructure.

Usage:
    # Generate from simple prompt
    python scripts/generate_and_validate_scenario.py "Medici family"

    # Generate from detailed prompt
    python scripts/generate_and_validate_scenario.py "The Medici banking family in 15th century Florence,
        focusing on Lorenzo de' Medici's rivalry with the Pazzi family."

    # Generate from prompt file
    python scripts/generate_and_validate_scenario.py --prompt-file prompts/medici_detailed.txt

    # Validate/refine existing scenario (skip generation)
    python scripts/generate_and_validate_scenario.py --validate-only scenarios/medici_banking.json

    # With options
    python scripts/generate_and_validate_scenario.py "Cuban Missile Crisis" \\
        --max-iterations 5 \\
        --games-per-test 50 \\
        --output scenarios/cuban_missile_crisis.json \\
        --verbose

Exit codes:
    0: Success (scenario validated)
    1: Failed after max iterations
    2: Fatal error during generation
"""

import argparse
import asyncio
import logging
import re
import sys
from pathlib import Path

# Add src to path for development
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from brinksmanship.generation.scenario_generator import ScenarioGenerator
from brinksmanship.generation.schemas import Scenario, save_scenario
from brinksmanship.generation.validator import (
    ScenarioValidator,
    ValidationResult,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def slugify(text: str) -> str:
    """Convert text to a valid filename slug."""
    text = text.lower().replace(" ", "_").replace("-", "_")
    text = re.sub(r"[^a-z0-9_]", "", text)
    return text[:50]  # Limit length


def parse_prompt(prompt: str) -> dict:
    """Parse a user prompt to extract scenario parameters.

    Handles both brief prompts (just a title) and detailed prompts
    (with additional context).

    Args:
        prompt: The user-provided prompt

    Returns:
        Dictionary with title, theme, setting, and additional_context
    """
    lines = [line.strip() for line in prompt.strip().split("\n") if line.strip()]

    # First line (or entire prompt if short) is the title
    title = lines[0] if lines else "Untitled Scenario"

    # Truncate title if too long
    if len(title) > 100:
        title = title[:100] + "..."

    # Rest is additional context
    additional_context = "\n".join(lines[1:]) if len(lines) > 1 else ""

    # Try to infer theme from keywords
    prompt_lower = prompt.lower()
    if any(kw in prompt_lower for kw in ["crisis", "war", "nuclear", "missile", "blockade", "standoff"]):
        theme = "crisis"
    elif any(kw in prompt_lower for kw in ["rival", "competitor", "tech", "silicon", "company", "market"]):
        theme = "rivals"
    elif any(kw in prompt_lower for kw in ["ally", "alliance", "nato", "partner", "union", "negotiat"]):
        theme = "allies"
    elif any(kw in prompt_lower for kw in ["spy", "espionage", "intelligence", "agent", "mole"]):
        theme = "espionage"
    else:
        theme = "default"

    # Infer setting from prompt
    setting = prompt.strip()[:500] if len(prompt) > 50 else f"{title} - strategic confrontation"

    return {
        "title": title,
        "theme": theme,
        "setting": setting,
        "additional_context": additional_context,
    }


def analyze_validation_failures(result: ValidationResult) -> list[str]:
    """Analyze validation result and return suggested fixes.

    Args:
        result: The validation result

    Returns:
        List of suggested fixes/changes
    """
    suggestions = []

    # Check game variety
    if result.game_variety and not result.game_variety.passed:
        suggestions.append(
            f"Increase game type variety: use at least 8 distinct types "
            f"(currently {result.game_variety.metrics.get('distinct_types', 0)})"
        )

    # Check act structure
    if result.act_structure and not result.act_structure.passed:
        violations = result.act_structure.metrics.get("violations", [])
        if violations:
            suggestions.append(f"Fix act structure violations: {len(violations)} turns have incorrect act numbers")

    # Check branching
    if result.branching and not result.branching.passed:
        for issue in result.branching.issues:
            suggestions.append(f"Fix branching: {issue.message}")

    # Check balance
    if result.balance and not result.balance.passed:
        for issue in result.balance.issues:
            if "Dominant strategy" in issue.message:
                suggestions.append("Adjust matrix parameters to reduce dominant strategy advantage")
            elif "Variance too" in issue.message:
                suggestions.append("Adjust game parameters to bring variance into expected range")

    return suggestions


async def generate_scenario_from_prompt(
    prompt: str,
    num_turns: int = 14,
) -> Scenario:
    """Generate a scenario from a user prompt.

    Args:
        prompt: The user prompt (brief or detailed)
        num_turns: Target number of turns (12-16)

    Returns:
        Generated Scenario object
    """
    parsed = parse_prompt(prompt)

    generator = ScenarioGenerator()

    logger.info(f"Generating scenario: '{parsed['title']}'")
    logger.info(f"  Theme: {parsed['theme']}")
    logger.info(f"  Turns: {num_turns}")

    scenario = await generator.generate_scenario(
        theme=parsed["theme"],
        setting=parsed["setting"],
        additional_context=parsed["additional_context"],
        num_turns=num_turns,
    )

    # Update title if generator used a generic one
    if scenario.title.startswith("Scenario:"):
        # Create new scenario with proper title
        scenario_dict = scenario.model_dump(mode="json")
        scenario_dict["title"] = parsed["title"]
        scenario = Scenario.model_validate(scenario_dict)

    return scenario


def validate_scenario(
    scenario: Scenario | dict,
    games_per_test: int = 50,
    seed: int | None = None,
) -> ValidationResult:
    """Validate a scenario with balance simulation.

    Args:
        scenario: Scenario object or dict
        games_per_test: Number of games per strategy pairing
        seed: Random seed for reproducibility

    Returns:
        ValidationResult with all check results
    """
    validator = ScenarioValidator(
        simulation_games=games_per_test,
        simulation_seed=seed,
    )

    return validator.validate(
        scenario=scenario,
        run_simulation=True,
        check_narrative=False,  # Skip LLM narrative check for speed
    )


def print_validation_summary(result: ValidationResult) -> None:
    """Print a concise validation summary."""
    status = "PASSED" if result.overall_passed else "FAILED"
    print(f"\nValidation: {status}")

    checks = [
        ("Game Variety", result.game_variety),
        ("Act Structure", result.act_structure),
        ("Branching", result.branching),
        ("Settlement", result.settlement),
        ("Balance", result.balance),
    ]

    for name, check in checks:
        if check:
            check_status = "PASS" if check.passed else "FAIL"
            print(f"  {name}: {check_status}")

            # Show key metrics
            for key, value in list(check.metrics.items())[:3]:
                if isinstance(value, float):
                    print(f"    {key}: {value:.2f}")
                elif isinstance(value, list) and len(value) > 5:
                    print(f"    {key}: [{len(value)} items]")
                else:
                    print(f"    {key}: {value}")

    if result.simulation_results:
        sim = result.simulation_results
        print(f"\n  Simulation ({sim.games_played} games):")
        print(f"    Avg length: {sim.avg_game_length:.1f} turns")
        print(f"    VP std dev: {sim.vp_std_dev:.1f}")
        print(f"    Elimination rate: {sim.elimination_rate * 100:.1f}%")
        print(f"    Mutual destruction: {sim.mutual_destruction_rate * 100:.1f}%")

        # Check for dominant strategies
        dominant = [(name, rate) for name, rate in sim.strategy_win_rates.items() if rate > 0.60]
        if dominant:
            print(f"    WARNING: Dominant strategies: {dominant}")


async def generate_and_validate(
    prompt: str,
    output_path: Path,
    max_iterations: int = 5,
    games_per_test: int = 50,
    num_turns: int = 14,
    verbose: bool = False,
) -> tuple[bool, Scenario | None]:
    """Generate and iteratively validate a scenario.

    Args:
        prompt: User prompt for scenario generation
        output_path: Path to save the validated scenario
        max_iterations: Maximum validation/refinement iterations
        games_per_test: Number of games per validation pairing
        num_turns: Target number of turns
        verbose: Whether to print detailed output

    Returns:
        Tuple of (success, scenario or None)
    """
    scenario = None

    for iteration in range(max_iterations):
        logger.info(f"\n{'=' * 60}")
        logger.info(f"Iteration {iteration + 1}/{max_iterations}")
        logger.info(f"{'=' * 60}")

        # Generate or regenerate scenario
        if scenario is None or iteration > 0:
            try:
                scenario = await generate_scenario_from_prompt(prompt, num_turns)
                logger.info(f"Generated scenario: {scenario.title}")
                logger.info(f"  {len(scenario.turns)} turns, {len(scenario.branches)} branches")
                logger.info(f"  Matrix types: {sorted(t.value for t in scenario.get_all_matrix_types())}")
            except Exception as e:
                logger.error(f"Generation failed: {e}")
                if verbose:
                    import traceback

                    traceback.print_exc()
                continue

        # Validate
        logger.info("\nValidating scenario...")
        result = validate_scenario(scenario, games_per_test)

        if verbose:
            print_validation_summary(result)

        if result.overall_passed:
            logger.info("Validation PASSED!")

            # Save scenario
            output_path.parent.mkdir(parents=True, exist_ok=True)
            save_scenario(scenario, str(output_path))
            logger.info(f"Scenario saved to: {output_path}")

            return True, scenario

        # Analyze failures and log suggestions
        suggestions = analyze_validation_failures(result)
        logger.warning("Validation FAILED. Issues:")
        for issue in result.get_critical_issues():
            logger.warning(f"  CRITICAL: {issue.message}")
        for issue in result.get_major_issues():
            logger.warning(f"  MAJOR: {issue.message}")

        if suggestions:
            logger.info("Suggested fixes:")
            for suggestion in suggestions:
                logger.info(f"  - {suggestion}")

        # For now, regenerate completely
        # Future: use agent to make targeted edits
        logger.info("Regenerating scenario...")
        scenario = None

    logger.error(f"Failed to validate after {max_iterations} iterations")
    return False, None


async def validate_only(
    scenario_path: Path,
    games_per_test: int = 50,
    verbose: bool = False,
) -> tuple[bool, ValidationResult]:
    """Validate an existing scenario file.

    Args:
        scenario_path: Path to scenario JSON file
        games_per_test: Number of games per validation pairing
        verbose: Whether to print detailed output

    Returns:
        Tuple of (passed, ValidationResult)
    """
    from brinksmanship.generation.schemas import load_scenario

    logger.info(f"Loading scenario: {scenario_path}")
    scenario = load_scenario(str(scenario_path))

    logger.info(f"Scenario: {scenario.title}")
    logger.info(f"  {len(scenario.turns)} turns, {len(scenario.branches)} branches")

    logger.info("\nValidating...")
    result = validate_scenario(scenario, games_per_test)

    if verbose:
        print_validation_summary(result)

    return result.overall_passed, result


def main():
    parser = argparse.ArgumentParser(
        description="Generate and validate Brinksmanship scenarios",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument(
        "prompt",
        nargs="?",
        type=str,
        default=None,
        help="Scenario prompt (brief title or detailed description)",
    )

    parser.add_argument(
        "--prompt-file",
        type=str,
        default=None,
        help="Read prompt from file instead of command line",
    )

    parser.add_argument(
        "--validate-only",
        type=str,
        default=None,
        metavar="SCENARIO_FILE",
        help="Validate existing scenario file (skip generation)",
    )

    parser.add_argument(
        "--max-iterations",
        type=int,
        default=5,
        help="Maximum validation/refinement iterations (default: 5)",
    )

    parser.add_argument(
        "--games-per-test",
        type=int,
        default=50,
        help="Number of games per strategy pairing in simulation (default: 50)",
    )

    parser.add_argument(
        "--turns",
        type=int,
        default=14,
        choices=range(12, 17),
        metavar="12-16",
        help="Target number of turns (default: 14)",
    )

    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default=None,
        help="Output file path (default: scenarios/<slugified-prompt>.json)",
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Print detailed validation output",
    )

    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Only output errors and final result",
    )

    args = parser.parse_args()

    # Set up logging
    if args.quiet:
        logging.getLogger().setLevel(logging.ERROR)
    elif args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Handle validate-only mode
    if args.validate_only:
        scenario_path = Path(args.validate_only)
        if not scenario_path.exists():
            print(f"Error: Scenario file not found: {scenario_path}", file=sys.stderr)
            return 1

        passed, result = asyncio.run(
            validate_only(
                scenario_path,
                games_per_test=args.games_per_test,
                verbose=args.verbose,
            )
        )

        return 0 if passed else 1

    # Get prompt
    if args.prompt_file:
        prompt_path = Path(args.prompt_file)
        if not prompt_path.exists():
            print(f"Error: Prompt file not found: {prompt_path}", file=sys.stderr)
            return 2
        prompt = prompt_path.read_text()
    elif args.prompt:
        prompt = args.prompt
    else:
        print("Error: Must provide prompt or --prompt-file or --validate-only", file=sys.stderr)
        parser.print_help()
        return 2

    # Determine output path
    if args.output:
        output_path = Path(args.output)
    else:
        parsed = parse_prompt(prompt)
        slug = slugify(parsed["title"])
        output_path = Path(f"scenarios/{slug}.json")

    # Run generation and validation
    success, scenario = asyncio.run(
        generate_and_validate(
            prompt=prompt,
            output_path=output_path,
            max_iterations=args.max_iterations,
            games_per_test=args.games_per_test,
            num_turns=args.turns,
            verbose=args.verbose,
        )
    )

    if success:
        print(f"\nSuccess! Scenario saved to: {output_path}")
        return 0
    else:
        print(f"\nFailed to generate valid scenario after {args.max_iterations} iterations", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
