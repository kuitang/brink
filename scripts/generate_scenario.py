#!/usr/bin/env python3
"""Generate Brinksmanship scenarios using LLM-based scenario generation.

This script generates complete game scenarios with narrative briefings, matrix
selections, and branching structures appropriate to the theme and setting.

Usage:
    # Generate a Cold War crisis scenario
    python scripts/generate_scenario.py --theme crisis --title "Cuban Missile Crisis"

    # Generate with custom settings
    python scripts/generate_scenario.py \\
        --title "Market Dominance" \\
        --theme rivals \\
        --setting "Silicon Valley tech rivalry" \\
        --time-period "2010s" \\
        --player-a "Established tech giant" \\
        --player-b "Disruptive startup" \\
        --output scenarios/tech_rivalry.json

    # Generate and validate
    python scripts/generate_scenario.py --theme crisis --validate

Exit codes:
    0: Success
    1: Generation failed or validation failed
"""

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

# Add src to path for development
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from brinksmanship.generation.scenario_generator import ScenarioGenerator
from brinksmanship.generation.validator import ScenarioValidator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def create_default_settings(theme: str) -> dict:
    """Create default settings based on theme.

    Args:
        theme: The scenario theme (crisis, rivals, allies, espionage)

    Returns:
        Dictionary with default setting, time_period, player_a_role, player_b_role
    """
    defaults = {
        "crisis": {
            "setting": "Superpower confrontation during heightened global tensions",
            "time_period": "Cold War era",
            "player_a_role": "Western bloc leader managing alliance stability",
            "player_b_role": "Eastern bloc leader pursuing strategic advantage",
        },
        "rivals": {
            "setting": "Intense commercial competition for market dominance",
            "time_period": "Modern era",
            "player_a_role": "Established market leader defending position",
            "player_b_role": "Aggressive challenger seeking disruption",
        },
        "allies": {
            "setting": "Alliance partners navigating shared challenges",
            "time_period": "Contemporary",
            "player_a_role": "Senior alliance partner with more resources",
            "player_b_role": "Junior partner seeking greater influence",
        },
        "espionage": {
            "setting": "Intelligence agencies engaged in shadow warfare",
            "time_period": "Modern era",
            "player_a_role": "Counterintelligence director protecting secrets",
            "player_b_role": "Foreign intelligence chief seeking penetration",
        },
        "default": {
            "setting": "Two powers navigating complex strategic landscape",
            "time_period": "Unspecified",
            "player_a_role": "Strategic actor pursuing national interest",
            "player_b_role": "Rival actor with competing objectives",
        },
    }
    return defaults.get(theme.lower(), defaults["default"])


async def generate_scenario_async(
    title: str,
    theme: str,
    setting: str,
    time_period: str,
    player_a_role: str,
    player_b_role: str,
    additional_context: str,
    num_turns: int,
) -> dict:
    """Generate a scenario asynchronously.

    Args:
        title: Scenario title
        theme: Scenario theme
        setting: Setting description
        time_period: Time period for the scenario
        player_a_role: Player A's role description
        player_b_role: Player B's role description
        additional_context: Additional generation context
        num_turns: Number of turns to generate

    Returns:
        Generated scenario dictionary
    """
    generator = ScenarioGenerator()

    logger.info(f"Generating scenario: '{title}'")
    logger.info(f"  Theme: {theme}")
    logger.info(f"  Setting: {setting}")
    logger.info(f"  Turns: {num_turns}")

    scenario = await generator.generate_scenario(
        title=title,
        theme=theme,
        setting=setting,
        time_period=time_period,
        player_a_role=player_a_role,
        player_b_role=player_b_role,
        additional_context=additional_context,
        num_turns=num_turns,
    )

    return scenario


def validate_generated_scenario(scenario: dict, run_simulation: bool = False) -> bool:
    """Validate a generated scenario.

    Args:
        scenario: The generated scenario dictionary
        run_simulation: Whether to run balance simulation

    Returns:
        True if validation passed, False otherwise
    """
    validator = ScenarioValidator()

    logger.info("Validating generated scenario...")

    result = validator.validate_dict(
        scenario_data=scenario,
        run_simulation=run_simulation,
    )

    if result.overall_passed:
        logger.info("Validation PASSED")
    else:
        logger.error("Validation FAILED")
        for issue in result.get_critical_issues():
            logger.error(f"  CRITICAL: {issue.message}")
        for issue in result.get_major_issues():
            logger.warning(f"  MAJOR: {issue.message}")

    return result.overall_passed


def main():
    parser = argparse.ArgumentParser(
        description="Generate Brinksmanship scenarios",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    # Required arguments
    parser.add_argument(
        "--title",
        "-t",
        type=str,
        required=True,
        help="Title for the scenario",
    )

    # Theme selection
    parser.add_argument(
        "--theme",
        type=str,
        choices=["crisis", "rivals", "allies", "espionage", "default"],
        default="default",
        help="Scenario theme (affects game type selection)",
    )

    # Optional customization
    parser.add_argument(
        "--setting",
        "-s",
        type=str,
        default=None,
        help="Setting description (uses theme default if not specified)",
    )
    parser.add_argument(
        "--time-period",
        type=str,
        default=None,
        help="Time period for the scenario",
    )
    parser.add_argument(
        "--player-a",
        type=str,
        default=None,
        help="Player A's role description",
    )
    parser.add_argument(
        "--player-b",
        type=str,
        default=None,
        help="Player B's role description",
    )
    parser.add_argument(
        "--context",
        type=str,
        default="",
        help="Additional context for generation",
    )

    # Turn configuration
    parser.add_argument(
        "--turns",
        type=int,
        default=14,
        choices=range(12, 17),
        metavar="12-16",
        help="Number of turns (12-16, default: 14)",
    )

    # Output options
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default=None,
        help="Output file path (default: scenarios/<slugified-title>.json)",
    )

    # Validation options
    parser.add_argument(
        "--validate",
        "-v",
        action="store_true",
        help="Validate the generated scenario",
    )
    parser.add_argument(
        "--simulate",
        action="store_true",
        help="Run balance simulation during validation (implies --validate)",
    )

    # Other options
    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Only output JSON, no progress messages",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be generated without calling LLM",
    )

    args = parser.parse_args()

    # Set up logging
    if args.quiet:
        logging.disable(logging.CRITICAL)

    # Get default settings for theme
    defaults = create_default_settings(args.theme)

    # Use provided values or defaults
    setting = args.setting or defaults["setting"]
    time_period = args.time_period or defaults["time_period"]
    player_a_role = args.player_a or defaults["player_a_role"]
    player_b_role = args.player_b or defaults["player_b_role"]

    # Determine output path
    if args.output:
        output_path = Path(args.output)
    else:
        # Slugify title for filename
        slug = args.title.lower().replace(" ", "_").replace("-", "_")
        slug = "".join(c for c in slug if c.isalnum() or c == "_")
        output_path = Path(f"scenarios/{slug}.json")

    # Dry run - show configuration
    if args.dry_run:
        print("Would generate scenario with:")
        print(f"  Title: {args.title}")
        print(f"  Theme: {args.theme}")
        print(f"  Setting: {setting}")
        print(f"  Time Period: {time_period}")
        print(f"  Player A: {player_a_role}")
        print(f"  Player B: {player_b_role}")
        print(f"  Turns: {args.turns}")
        print(f"  Output: {output_path}")
        print(f"  Validate: {args.validate or args.simulate}")
        print(f"  Simulate: {args.simulate}")
        return 0

    # Generate scenario
    try:
        scenario = asyncio.run(
            generate_scenario_async(
                title=args.title,
                theme=args.theme,
                setting=setting,
                time_period=time_period,
                player_a_role=player_a_role,
                player_b_role=player_b_role,
                additional_context=args.context,
                num_turns=args.turns,
            )
        )
    except Exception as e:
        logger.error(f"Generation failed: {e}")
        if not args.quiet:
            import traceback

            traceback.print_exc()
        return 1

    # Validate if requested
    if args.validate or args.simulate:
        valid = validate_generated_scenario(scenario, run_simulation=args.simulate)
        if not valid:
            logger.error("Generated scenario failed validation. Not saving.")
            return 1

    # Write output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w") as f:
        json.dump(scenario, f, indent=2)

    logger.info(f"Scenario saved to: {output_path}")

    # Output JSON to stdout if quiet mode
    if args.quiet:
        print(json.dumps(scenario, indent=2))

    return 0


if __name__ == "__main__":
    sys.exit(main())
