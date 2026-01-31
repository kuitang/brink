#!/usr/bin/env python3
"""Comprehensive LLM Playtesting for Brinksmanship.

Runs 3x3 comparison per scenario:
1. Historical Figure A vs Historical Figure B (appropriate to scenario sides)
2. Smart Rational Player vs Historical A
3. Smart Rational Player vs Historical B

Usage:
    uv run python scripts/comprehensive_llm_playtest.py --total-games 500

    # Quick test with fewer games
    uv run python scripts/comprehensive_llm_playtest.py --total-games 30 --scenarios cuban_missile_crisis
"""

import argparse
import asyncio
import json
import sys
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

# Add src and scripts to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent / "playtest"))

from run_matchup import GameResult, SmartRationalPlayer, run_single_game

from brinksmanship.opponents.historical import HistoricalPersona


# =============================================================================
# SCENARIO TO PERSONA MAPPING
# =============================================================================

SCENARIO_PERSONAS = {
    # Cold War scenarios
    "cuban_missile_crisis": {
        "historical_a": "nixon",
        "historical_b": "khrushchev",
        "role_a": "American President",
        "role_b": "Soviet Premier",
    },
    "berlin_blockade": {
        "historical_a": "nixon",
        "historical_b": "khrushchev",
        "role_a": "Western Allied Commander",
        "role_b": "Soviet Leadership",
    },
    "taiwan_strait_crisis": {
        "historical_a": "kissinger",
        "historical_b": "khrushchev",
        "role_a": "American Diplomat",
        "role_b": "Communist Leadership",
    },
    "cold_war_espionage": {
        "historical_a": "kissinger",
        "historical_b": "khrushchev",
        "role_a": "Western Intelligence Chief",
        "role_b": "Soviet Spymaster",
    },
    "nato_burden_sharing": {
        "historical_a": "nixon",
        "historical_b": "bismarck",
        "role_a": "American President",
        "role_b": "European Alliance Leader",
    },
    # Corporate scenarios
    "silicon_valley_tech_wars": {
        "historical_a": "gates",
        "historical_b": "jobs",
        "role_a": "Tech Company CEO",
        "role_b": "Rival Tech CEO",
    },
    "opec_oil_politics": {
        "historical_a": "kissinger",
        "historical_b": "bismarck",
        "role_a": "Western Energy Minister",
        "role_b": "OPEC Representative",
    },
    # European/Diplomatic scenarios
    "brexit_negotiations": {
        "historical_a": "bismarck",
        "historical_b": "metternich",
        "role_a": "British Negotiator",
        "role_b": "EU Chief Negotiator",
    },
    # Historical scenarios
    "byzantine_succession": {
        "historical_a": "theodora",
        "historical_b": "livia",
        "role_a": "Imperial Faction Leader",
        "role_b": "Challenger Faction",
    },
    "medici_banking_dynasty": {
        "historical_a": "richelieu",
        "historical_b": "metternich",
        "role_a": "Banking House Patriarch",
        "role_b": "Rival Banking House",
    },
}


# =============================================================================
# PLAYTEST RUNNER
# =============================================================================

async def run_playtest_batch(
    scenarios: list[str],
    games_per_matchup: int,
) -> dict:
    """Run comprehensive playtest with 3x3 comparison per scenario."""
    all_games = []

    for scenario_id in scenarios:
        config = SCENARIO_PERSONAS.get(scenario_id)
        if not config:
            print(f"Warning: No persona mapping for {scenario_id}, skipping")
            continue

        hist_a = config["historical_a"]
        hist_b = config["historical_b"]
        role_a = config.get("role_a", "Player A")
        role_b = config.get("role_b", "Player B")

        print(f"\n=== Scenario: {scenario_id} ===")
        print(f"  Historical A: {hist_a} ({role_a})")
        print(f"  Historical B: {hist_b} ({role_b})")

        matchups = [
            (f"historical:{hist_a}", f"historical:{hist_b}", f"{hist_a} vs {hist_b}"),
            ("smart", f"historical:{hist_b}", f"Smart vs {hist_b}"),
            (f"historical:{hist_a}", "smart", f"{hist_a} vs Smart"),
        ]

        for player_a_type, player_b_type, matchup_label in matchups:
            print(f"\n  Matchup: {matchup_label}")

            for game_num in range(games_per_matchup):
                # Create players
                if player_a_type == "smart":
                    player_a = SmartRationalPlayer(is_player_a=True)
                else:
                    persona_a = player_a_type.split(":")[1]
                    player_a = HistoricalPersona(persona_name=persona_a, is_player_a=True, role_name=role_a)

                if player_b_type == "smart":
                    player_b = SmartRationalPlayer(is_player_a=False)
                else:
                    persona_b = player_b_type.split(":")[1]
                    player_b = HistoricalPersona(persona_name=persona_b, is_player_a=False, role_name=role_b)

                result = await run_single_game(scenario_id, player_a, player_b)
                game_dict = asdict(result)
                game_dict["matchup"] = matchup_label
                all_games.append(game_dict)

                status = f"ERROR - {result.error}" if result.error else f"{result.winner} ({result.ending_type}, {result.turns} turns)"
                print(f"    Game {game_num + 1}: {status}")

    return {
        "timestamp": datetime.now().isoformat(),
        "total_games": len(all_games),
        "scenarios": scenarios,
        "games": all_games,
    }


def generate_markdown_report(results: dict, output_path: Path) -> None:
    """Generate comprehensive markdown report."""
    lines = [
        "# Comprehensive LLM Playtest Report",
        "",
        f"**Generated:** {results['timestamp']}",
        f"**Total Games:** {results['total_games']}",
        f"**Scenarios:** {len(results['scenarios'])}",
        "",
        "---",
        "",
    ]

    games = results.get("games", [])
    valid_games = [g for g in games if g.get("error") is None]

    if not valid_games:
        lines.append("No valid games completed.")
        output_path.write_text("\n".join(lines))
        return

    # Overall stats
    settlements = sum(1 for g in valid_games if g.get("ending_type") == "settlement")
    md = sum(1 for g in valid_games if g.get("ending_type") == "mutual_destruction")
    a_wins = sum(1 for g in valid_games if g.get("winner") == "A")
    b_wins = sum(1 for g in valid_games if g.get("winner") == "B")
    avg_turns = sum(g.get("turns", 0) for g in valid_games) / len(valid_games)
    avg_risk = sum(g.get("final_risk", 0) for g in valid_games) / len(valid_games)

    lines.extend([
        "## Overall Summary",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Valid Games | {len(valid_games)} |",
        f"| Settlement Rate | {settlements / len(valid_games) * 100:.1f}% |",
        f"| Mutual Destruction Rate | {md / len(valid_games) * 100:.1f}% |",
        f"| Player A Win Rate | {a_wins / len(valid_games) * 100:.1f}% |",
        f"| Player B Win Rate | {b_wins / len(valid_games) * 100:.1f}% |",
        f"| Average Game Length | {avg_turns:.1f} turns |",
        f"| Average Final Risk | {avg_risk:.2f} |",
        "",
    ])

    # Per-scenario breakdown
    lines.extend([
        "## Results by Scenario",
        "",
        "| Scenario | Games | Settlement % | MD % | Avg Turns |",
        "|----------|-------|--------------|------|-----------|",
    ])

    for scenario in results["scenarios"]:
        scenario_games = [g for g in valid_games if g.get("scenario_id") == scenario]
        if scenario_games:
            s = sum(1 for g in scenario_games if g.get("ending_type") == "settlement")
            m = sum(1 for g in scenario_games if g.get("ending_type") == "mutual_destruction")
            avg_t = sum(g.get("turns", 0) for g in scenario_games) / len(scenario_games)
            lines.append(
                f"| {scenario} | {len(scenario_games)} | "
                f"{s / len(scenario_games) * 100:.0f}% | "
                f"{m / len(scenario_games) * 100:.0f}% | "
                f"{avg_t:.1f} |"
            )

    lines.append("")

    # Error section
    error_games = [g for g in games if g.get("error")]
    if error_games:
        lines.extend(["## Errors", ""])
        for g in error_games[:10]:
            lines.append(f"- {g.get('scenario_id', 'unknown')}: {g.get('error', 'unknown error')}")
        if len(error_games) > 10:
            lines.append(f"- ... and {len(error_games) - 10} more errors")

    output_path.write_text("\n".join(lines))
    print(f"\nReport written to: {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Comprehensive LLM Playtesting")
    parser.add_argument("--total-games", type=int, default=500, help="Total games to run across all scenarios")
    parser.add_argument("--scenarios", type=str, help="Comma-separated scenario IDs (default: all)")
    parser.add_argument("--output", type=str, default="docs/COMPREHENSIVE_PLAYTEST_REPORT.md", help="Output markdown file")
    args = parser.parse_args()

    # Determine scenarios
    if args.scenarios:
        scenarios = [s.strip() for s in args.scenarios.split(",")]
    else:
        scenarios = list(SCENARIO_PERSONAS.keys())

    # Calculate games per matchup (3 matchups per scenario)
    total_matchups = len(scenarios) * 3
    games_per_matchup = max(1, args.total_games // total_matchups)

    print("Comprehensive LLM Playtest Configuration:")
    print(f"  Scenarios: {len(scenarios)}")
    print(f"  Matchups per scenario: 3")
    print(f"  Games per matchup: {games_per_matchup}")
    print(f"  Total games: {len(scenarios) * 3 * games_per_matchup}")

    # Run playtests
    results = asyncio.run(run_playtest_batch(scenarios, games_per_matchup))

    # Generate outputs
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    generate_markdown_report(results, output_path)

    json_path = output_path.with_suffix(".json")
    json_path.write_text(json.dumps(results, indent=2))
    print(f"JSON data written to: {json_path}")


if __name__ == "__main__":
    main()
