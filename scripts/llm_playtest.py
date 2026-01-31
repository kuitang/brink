#!/usr/bin/env python3
"""LLM Opponent Playtesting for Brinksmanship.

Runs games with LLM-based historical persona opponents across all scenarios.
Collects metrics on gameplay quality, narrative coherence, and strategic behavior.

Usage:
    # Run 50 games per scenario with a single persona vs deterministic opponent
    uv run python scripts/llm_playtest.py --games 50 --persona nixon

    # Run with all personas (expensive!)
    uv run python scripts/llm_playtest.py --games 10 --all-personas

    # Run specific scenarios only
    uv run python scripts/llm_playtest.py --games 50 --scenarios cuban_missile_crisis,berlin_blockade

Note: LLM playtesting requires API keys and incurs costs. Estimate ~20 API calls per game.
"""

import argparse
import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from brinksmanship.engine.game_engine import GameEngine
from brinksmanship.opponents import get_opponent_by_type
from brinksmanship.opponents.base import Opponent
from brinksmanship.opponents.historical import PERSONA_DISPLAY_NAMES
from brinksmanship.storage import get_scenario_repository


@dataclass
class GameMetrics:
    """Metrics collected from a single game."""

    scenario_id: str
    persona_name: str
    opponent_name: str
    winner: str
    ending_type: str
    turns_played: int
    vp_persona: float
    vp_opponent: float
    settlement_proposed: bool = False
    settlement_accepted: bool = False
    cooperation_final: float = 0.0
    risk_final: float = 0.0
    error: str | None = None


@dataclass
class PlaytestResults:
    """Aggregated results from a playtest batch."""

    timestamp: str
    total_games: int
    scenarios: list[str]
    personas: list[str]
    games: list[GameMetrics] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "total_games": self.total_games,
            "scenarios": self.scenarios,
            "personas": self.personas,
            "games": [
                {
                    "scenario_id": g.scenario_id,
                    "persona_name": g.persona_name,
                    "opponent_name": g.opponent_name,
                    "winner": g.winner,
                    "ending_type": g.ending_type,
                    "turns_played": g.turns_played,
                    "vp_persona": g.vp_persona,
                    "vp_opponent": g.vp_opponent,
                    "settlement_proposed": g.settlement_proposed,
                    "settlement_accepted": g.settlement_accepted,
                    "cooperation_final": g.cooperation_final,
                    "risk_final": g.risk_final,
                    "error": g.error,
                }
                for g in self.games
            ],
        }


async def run_single_game(
    scenario_id: str,
    persona: Opponent,
    opponent: Opponent,
    persona_name: str,
) -> GameMetrics:
    """Run a single game between persona and opponent."""
    repo = get_scenario_repository()
    engine = GameEngine(scenario_id, repo)

    if hasattr(persona, "set_player_side"):
        persona.set_player_side(is_player_a=True)
    if hasattr(opponent, "set_player_side"):
        opponent.set_player_side(is_player_a=False)

    settlement_proposed = False
    settlement_accepted = False

    try:
        while not engine.is_game_over():
            state = engine.get_current_state()

            # Check for settlement (turn > 4, stability > 2)
            if state.turn > 4 and state.stability > 2:
                # Check if persona wants to propose
                if hasattr(persona, "propose_settlement"):
                    proposal = await persona.propose_settlement(state)
                    if proposal:
                        settlement_proposed = True
                        if hasattr(opponent, "evaluate_settlement"):
                            response = await opponent.evaluate_settlement(proposal, state, is_final_offer=False)
                            if response.action == "accept":
                                settlement_accepted = True
                                # End game via settlement
                                vp_opponent = proposal.offered_vp
                                vp_persona = 100 - vp_opponent
                                return GameMetrics(
                                    scenario_id=scenario_id,
                                    persona_name=persona_name,
                                    opponent_name=opponent.name,
                                    winner="persona" if vp_persona > vp_opponent else "opponent",
                                    ending_type="settlement",
                                    turns_played=state.turn,
                                    vp_persona=vp_persona,
                                    vp_opponent=vp_opponent,
                                    settlement_proposed=True,
                                    settlement_accepted=True,
                                    cooperation_final=state.cooperation_score,
                                    risk_final=state.risk_level,
                                )

            # Get actions
            actions_a = engine.get_available_actions("A")
            actions_b = engine.get_available_actions("B")

            action_a = await persona.choose_action(state, actions_a)
            action_b = await opponent.choose_action(state, actions_b)

            result = engine.submit_actions(action_a, action_b)

            if hasattr(persona, "receive_result") and result.action_result:
                persona.receive_result(result.action_result)
            if hasattr(opponent, "receive_result") and result.action_result:
                opponent.receive_result(result.action_result)

            if result.ending:
                break

        final_state = engine.get_current_state()
        ending = engine.get_ending()

        if ending:
            vp_persona = ending.vp_a
            vp_opponent = ending.vp_b
            ending_type = ending.ending_type.value
            winner = "persona" if vp_persona > vp_opponent else ("opponent" if vp_opponent > vp_persona else "tie")
        else:
            vp_persona = vp_opponent = 50
            ending_type = "unknown"
            winner = "tie"

        return GameMetrics(
            scenario_id=scenario_id,
            persona_name=persona_name,
            opponent_name=opponent.name,
            winner=winner,
            ending_type=ending_type,
            turns_played=final_state.turn,
            vp_persona=vp_persona,
            vp_opponent=vp_opponent,
            settlement_proposed=settlement_proposed,
            settlement_accepted=settlement_accepted,
            cooperation_final=final_state.cooperation_score,
            risk_final=final_state.risk_level,
        )
    except Exception as e:
        return GameMetrics(
            scenario_id=scenario_id,
            persona_name=persona_name,
            opponent_name=opponent.name,
            winner="error",
            ending_type="error",
            turns_played=0,
            vp_persona=0,
            vp_opponent=0,
            error=str(e),
        )


async def run_playtest_batch(
    scenarios: list[str],
    personas: list[str],
    games_per_combo: int,
    deterministic_opponent: str = "tit_for_tat",
) -> PlaytestResults:
    """Run a batch of playtests."""
    results = PlaytestResults(
        timestamp=datetime.now().isoformat(),
        total_games=len(scenarios) * len(personas) * games_per_combo,
        scenarios=scenarios,
        personas=personas,
    )

    total = len(scenarios) * len(personas) * games_per_combo
    completed = 0

    for scenario_id in scenarios:
        for persona_name in personas:
            print(f"\n[{completed}/{total}] {scenario_id} vs {PERSONA_DISPLAY_NAMES.get(persona_name, persona_name)}")

            for game_num in range(games_per_combo):
                # Create fresh opponents for each game
                persona = get_opponent_by_type(persona_name)
                opponent = get_opponent_by_type(deterministic_opponent)

                metric = await run_single_game(
                    scenario_id=scenario_id,
                    persona=persona,
                    opponent=opponent,
                    persona_name=persona_name,
                )
                results.games.append(metric)
                completed += 1

                if metric.error:
                    print(f"  Game {game_num + 1}: ERROR - {metric.error}")
                else:
                    print(
                        f"  Game {game_num + 1}: {metric.winner} won ({metric.ending_type}, {metric.turns_played} turns)"
                    )

    return results


def generate_markdown_report(results: PlaytestResults, output_path: Path) -> None:
    """Generate a markdown report from playtest results."""
    lines = [
        "# LLM Playtest Report",
        "",
        f"**Generated:** {results.timestamp}",
        f"**Total Games:** {results.total_games}",
        f"**Scenarios:** {', '.join(results.scenarios)}",
        f"**Personas:** {', '.join([PERSONA_DISPLAY_NAMES.get(p, p) for p in results.personas])}",
        "",
        "---",
        "",
        "## Summary Statistics",
        "",
    ]

    # Calculate aggregates
    valid_games = [g for g in results.games if g.error is None]
    if not valid_games:
        lines.append("No valid games completed.")
    else:
        persona_wins = sum(1 for g in valid_games if g.winner == "persona")
        opponent_wins = sum(1 for g in valid_games if g.winner == "opponent")
        sum(1 for g in valid_games if g.winner == "tie")

        settlements = sum(1 for g in valid_games if g.ending_type == "settlement")
        md = sum(1 for g in valid_games if g.ending_type == "mutual_destruction")

        avg_turns = sum(g.turns_played for g in valid_games) / len(valid_games)
        avg_vp_persona = sum(g.vp_persona for g in valid_games) / len(valid_games)

        lines.extend(
            [
                "| Metric | Value |",
                "|--------|-------|",
                f"| Valid Games | {len(valid_games)} |",
                f"| Persona Win Rate | {persona_wins / len(valid_games) * 100:.1f}% |",
                f"| Opponent Win Rate | {opponent_wins / len(valid_games) * 100:.1f}% |",
                f"| Settlement Rate | {settlements / len(valid_games) * 100:.1f}% |",
                f"| Mutual Destruction Rate | {md / len(valid_games) * 100:.1f}% |",
                f"| Avg Game Length | {avg_turns:.1f} turns |",
                f"| Avg Persona VP | {avg_vp_persona:.1f} |",
                "",
            ]
        )

        # Per-persona breakdown
        lines.extend(["## Per-Persona Results", ""])
        lines.append("| Persona | Games | Win Rate | Avg VP | Settlement % |")
        lines.append("|---------|-------|----------|--------|--------------|")

        for persona in results.personas:
            persona_games = [g for g in valid_games if g.persona_name == persona]
            if persona_games:
                wins = sum(1 for g in persona_games if g.winner == "persona")
                avg_vp = sum(g.vp_persona for g in persona_games) / len(persona_games)
                settle_rate = sum(1 for g in persona_games if g.ending_type == "settlement") / len(persona_games)
                display = PERSONA_DISPLAY_NAMES.get(persona, persona)
                lines.append(
                    f"| {display} | {len(persona_games)} | {wins / len(persona_games) * 100:.1f}% | {avg_vp:.1f} | {settle_rate * 100:.1f}% |"
                )

        lines.extend(["", "## Per-Scenario Results", ""])
        lines.append("| Scenario | Games | Persona Win Rate | Avg Turns | MD Rate |")
        lines.append("|----------|-------|------------------|-----------|---------|")

        for scenario in results.scenarios:
            scenario_games = [g for g in valid_games if g.scenario_id == scenario]
            if scenario_games:
                wins = sum(1 for g in scenario_games if g.winner == "persona")
                avg_t = sum(g.turns_played for g in scenario_games) / len(scenario_games)
                md_rate = sum(1 for g in scenario_games if g.ending_type == "mutual_destruction") / len(scenario_games)
                lines.append(
                    f"| {scenario} | {len(scenario_games)} | {wins / len(scenario_games) * 100:.1f}% | {avg_t:.1f} | {md_rate * 100:.1f}% |"
                )

    # Errors
    error_games = [g for g in results.games if g.error is not None]
    if error_games:
        lines.extend(["", "## Errors", ""])
        for g in error_games[:10]:  # Show first 10 errors
            lines.append(f"- {g.scenario_id}/{g.persona_name}: {g.error}")
        if len(error_games) > 10:
            lines.append(f"- ... and {len(error_games) - 10} more errors")

    output_path.write_text("\n".join(lines))
    print(f"\nReport written to: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="LLM Opponent Playtesting")
    parser.add_argument("--games", type=int, default=10, help="Games per scenario/persona combo")
    parser.add_argument("--persona", type=str, help="Single persona to test (e.g., nixon, bismarck)")
    parser.add_argument("--all-personas", action="store_true", help="Test all personas (expensive!)")
    parser.add_argument("--scenarios", type=str, help="Comma-separated scenario IDs")
    parser.add_argument("--output", type=str, default="docs/LLM_PLAYTEST_REPORT.md", help="Output markdown file")
    parser.add_argument("--opponent", type=str, default="tit_for_tat", help="Deterministic opponent to test against")

    args = parser.parse_args()

    # Get scenarios
    repo = get_scenario_repository()
    if args.scenarios:
        scenarios = args.scenarios.split(",")
    else:
        scenarios = [s["id"] for s in repo.list_scenarios()]

    # Get personas
    if args.all_personas:
        personas = list(PERSONA_DISPLAY_NAMES.keys())
    elif args.persona:
        personas = [args.persona]
    else:
        # Default to a few representative personas
        personas = ["nixon", "bismarck", "kissinger"]

    print("LLM Playtest Configuration:")
    print(f"  Scenarios: {len(scenarios)}")
    print(f"  Personas: {len(personas)}")
    print(f"  Games per combo: {args.games}")
    print(f"  Total games: {len(scenarios) * len(personas) * args.games}")
    print(f"  Estimated API calls: ~{len(scenarios) * len(personas) * args.games * 20}")
    print()

    # Run playtests
    results = asyncio.run(
        run_playtest_batch(
            scenarios=scenarios,
            personas=personas,
            games_per_combo=args.games,
            deterministic_opponent=args.opponent,
        )
    )

    # Generate report
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    generate_markdown_report(results, output_path)

    # Also save raw JSON
    json_path = output_path.with_suffix(".json")
    json_path.write_text(json.dumps(results.to_dict(), indent=2))
    print(f"JSON data written to: {json_path}")


if __name__ == "__main__":
    main()
