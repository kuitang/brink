#!/usr/bin/env python3
"""Comprehensive LLM Playtesting for Brinksmanship.

Runs 3x3 comparison per scenario:
1. Historical Figure A vs Historical Figure B (appropriate to scenario sides)
2. Smart Rational Player (Opus 4.5) vs Historical A
3. Smart Rational Player (Opus 4.5) vs Historical B

Total: ~500 games across all scenarios.

Usage:
    uv run python scripts/comprehensive_llm_playtest.py --total-games 500

    # Quick test with fewer games
    uv run python scripts/comprehensive_llm_playtest.py --total-games 30 --scenarios cuban_missile_crisis
"""

import argparse
import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from brinksmanship.engine.game_engine import EndingType, GameEngine
from brinksmanship.llm import generate_json
from brinksmanship.models.actions import Action, ActionType
from brinksmanship.models.state import GameState
from brinksmanship.opponents.base import (
    Opponent,
    SettlementProposal,
    SettlementResponse,
)
from brinksmanship.opponents.historical import HistoricalPersona
from brinksmanship.storage import get_scenario_repository


# =============================================================================
# SCENARIO TO PERSONA MAPPING
# =============================================================================
# Each scenario has two sides (A and B). We map appropriate historical figures.
# Player A is typically the "Western" or "protagonist" side.
# Player B is typically the "adversary" or "challenger" side.

SCENARIO_PERSONAS = {
    # Cold War scenarios
    "cuban_missile_crisis": {
        "historical_a": "nixon",      # US side - Nixon/Kennedy era
        "historical_b": "khrushchev", # Soviet side
        "role_a": "American President",
        "role_b": "Soviet Premier",
    },
    "berlin_blockade": {
        "historical_a": "nixon",      # Western powers
        "historical_b": "khrushchev", # Soviet Union
        "role_a": "Western Allied Commander",
        "role_b": "Soviet Leadership",
    },
    "taiwan_strait_crisis": {
        "historical_a": "kissinger",  # US/Taiwan side - Kissinger's diplomacy
        "historical_b": "khrushchev", # Communist bloc
        "role_a": "American Diplomat",
        "role_b": "Communist Leadership",
    },
    "cold_war_espionage": {
        "historical_a": "kissinger",  # Western intelligence
        "historical_b": "khrushchev", # Soviet intelligence
        "role_a": "Western Intelligence Chief",
        "role_b": "Soviet Spymaster",
    },
    "nato_burden_sharing": {
        "historical_a": "nixon",      # US position
        "historical_b": "bismarck",   # European realpolitik
        "role_a": "American President",
        "role_b": "European Alliance Leader",
    },
    # Corporate scenarios
    "silicon_valley_tech_wars": {
        "historical_a": "gates",      # Tech titan A
        "historical_b": "jobs",       # Tech titan B
        "role_a": "Tech Company CEO",
        "role_b": "Rival Tech CEO",
    },
    "opec_oil_politics": {
        "historical_a": "kissinger",  # Western oil interests
        "historical_b": "bismarck",   # OPEC realpolitik
        "role_a": "Western Energy Minister",
        "role_b": "OPEC Representative",
    },
    # European/Diplomatic scenarios
    "brexit_negotiations": {
        "historical_a": "bismarck",   # UK position - realpolitik
        "historical_b": "metternich", # EU position - balance of power
        "role_a": "British Negotiator",
        "role_b": "EU Chief Negotiator",
    },
    # Historical scenarios
    "byzantine_succession": {
        "historical_a": "theodora",   # Imperial faction A
        "historical_b": "livia",      # Rival faction
        "role_a": "Imperial Faction Leader",
        "role_b": "Challenger Faction",
    },
    "medici_banking_dynasty": {
        "historical_a": "richelieu",  # Banking house A
        "historical_b": "metternich", # Rival house
        "role_a": "Banking House Patriarch",
        "role_b": "Rival Banking House",
    },
}


# =============================================================================
# SMART RATIONAL PLAYER
# =============================================================================

SMART_RATIONAL_PLAYER_PROMPT = """You are a skilled strategic player in a negotiation/crisis game.

GAME MECHANICS YOU UNDERSTAND:
1. **Cooperation Creates Value**: When both players choose cooperative actions (CC),
   a shared "surplus pool" grows. This pool represents the value created through mutual trust.

2. **Defection Captures Value**: When one cooperates and one defects (CD/DC), the defector
   captures 40% of the surplus pool. This is tempting but reduces the shared value.

3. **Mutual Defection Destroys Value**: When both defect (DD), 20% of the surplus is
   burned AND risk level increases significantly. High risk leads to mutual destruction.

4. **Risk Management**: Risk starts at 2.0 and can rise to 10.0. At 10.0, both players
   get 0 VP (mutual destruction - the worst outcome). Cooperation reduces risk.

5. **Settlement**: After turn 4 (if stability > 2), players can negotiate settlement.
   Settlement locks in your captured surplus + position-based share. It ends the game.

STRATEGIC PRINCIPLES:
- Build cooperation early to grow the surplus pool
- Defect strategically when the pool is large and you can capture significant value
- Watch risk levels - if risk > 6, prioritize de-escalation
- Consider settlement when you have a positional advantage or risk is climbing
- Don't be predictable - adapt to your opponent's patterns

CURRENT STATE:
- Turn: {turn}
- Your Position: {my_position}
- Your Resources: {my_resources}
- Opponent Position (estimated): {opp_position_est} (uncertainty: {opp_uncertainty})
- Risk Level: {risk_level}
- Cooperation Score: {coop_score}
- Your Previous Action: {my_last_type}
- Opponent's Previous Action: {opp_last_type}

AVAILABLE ACTIONS:
{action_list}

Choose the action that best serves your strategic goals given the current state."""

SMART_RATIONAL_SYSTEM_PROMPT = """You are playing a strategic negotiation game as a rational, skilled player.
Make decisions based on game-theoretic reasoning, adapting to your opponent's patterns.
Respond with a JSON object containing your chosen action and brief reasoning."""

SMART_RATIONAL_ACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "selected_action": {
            "type": "string",
            "description": "The exact name of the action you choose"
        },
        "reasoning": {
            "type": "string",
            "description": "Brief strategic reasoning (1-2 sentences)"
        }
    },
    "required": ["selected_action", "reasoning"]
}


class SmartRationalPlayer(Opponent):
    """A smart rational player using Opus 4.5 with game principles knowledge.

    This represents a skilled human player who understands the game mechanics
    but doesn't have a specific historical persona.
    """

    def __init__(self, is_player_a: bool = True):
        super().__init__(name="Smart Rational Player")
        self._is_player_a = is_player_a

    def set_player_side(self, is_player_a: bool) -> None:
        """Set which side this player is on."""
        self._is_player_a = is_player_a

    def _get_my_state(self, state: GameState) -> tuple[float, float, ActionType | None]:
        """Get this player's position, resources, and previous action type."""
        if self._is_player_a:
            return state.position_a, state.resources_a, state.previous_type_a
        return state.position_b, state.resources_b, state.previous_type_b

    def _get_opponent_state(self, state: GameState) -> tuple[float, float, ActionType | None]:
        """Get opponent's position, resources, and previous action type."""
        if self._is_player_a:
            return state.position_b, state.resources_b, state.previous_type_b
        return state.position_a, state.resources_a, state.previous_type_a

    def _format_action_type(self, action_type: ActionType | None) -> str:
        """Format an action type for display."""
        if action_type is None:
            return "None (first turn)"
        return action_type.value.capitalize()

    def _format_action_list(self, actions: list[Action]) -> str:
        """Format a list of actions for the prompt."""
        lines = []
        for i, action in enumerate(actions, 1):
            type_str = "COOPERATIVE" if action.action_type == ActionType.COOPERATIVE else "COMPETITIVE"
            lines.append(f"{i}. {action.name} [{type_str}]")
            if action.description:
                lines.append(f"   {action.description}")
        return "\n".join(lines)

    async def choose_action(
        self, state: GameState, available_actions: list[Action]
    ) -> Action:
        """Choose an action using rational game-theoretic reasoning."""
        my_position, my_resources, my_last_type = self._get_my_state(state)
        _, _, opp_last_type = self._get_opponent_state(state)

        # Get opponent position estimate
        if self._is_player_a:
            info_state = state.player_a.information
        else:
            info_state = state.player_b.information
        opp_position_est, opp_uncertainty = info_state.get_position_estimate(state.turn)

        prompt = SMART_RATIONAL_PLAYER_PROMPT.format(
            turn=state.turn,
            my_position=f"{my_position:.1f}",
            my_resources=f"{my_resources:.1f}",
            opp_position_est=f"{opp_position_est:.1f}",
            opp_uncertainty=f"{opp_uncertainty:.1f}",
            risk_level=f"{state.risk_level:.1f}",
            coop_score=f"{state.cooperation_score:.1f}",
            my_last_type=self._format_action_type(my_last_type),
            opp_last_type=self._format_action_type(opp_last_type),
            action_list=self._format_action_list(available_actions),
        )

        response = await generate_json(
            prompt=prompt,
            system_prompt=SMART_RATIONAL_SYSTEM_PROMPT,
            schema=SMART_RATIONAL_ACTION_SCHEMA,
        )

        selected_name = response.get("selected_action", "").strip()

        # Find matching action
        for action in available_actions:
            if action.name.lower() == selected_name.lower():
                return action

        # Partial match fallback
        for action in available_actions:
            if selected_name.lower() in action.name.lower():
                return action

        # Final fallback: first cooperative action or first action
        for action in available_actions:
            if action.action_type == ActionType.COOPERATIVE:
                return action
        return available_actions[0]

    async def evaluate_settlement(
        self,
        proposal: SettlementProposal,
        state: GameState,
        is_final_offer: bool,
    ) -> SettlementResponse:
        """Evaluate settlement based on position and risk."""
        my_vp = 100 - proposal.offered_vp
        fair_vp = self.get_position_fair_vp(state, self._is_player_a)
        vp_diff = my_vp - fair_vp

        # Accept if offer is within 15 VP of fair, or if risk is high
        if vp_diff >= -15 or state.risk_level >= 7:
            return SettlementResponse(action="accept")

        # Counter if within 25 VP and not final offer
        if not is_final_offer and vp_diff >= -25:
            counter_vp = max(20, min(80, int(fair_vp)))
            return SettlementResponse(
                action="counter",
                counter_vp=counter_vp,
                counter_argument="Let's meet at a fair value based on our positions.",
            )

        return SettlementResponse(
            action="reject",
            rejection_reason="The offer doesn't reflect current positions fairly.",
        )

    async def propose_settlement(self, state: GameState) -> SettlementProposal | None:
        """Propose settlement if conditions favor it."""
        if state.turn <= 4 or state.stability <= 2:
            return None

        # Propose if we have advantage or risk is concerning
        fair_vp = self.get_position_fair_vp(state, self._is_player_a)
        my_position = state.position_a if self._is_player_a else state.position_b
        opp_position = state.position_b if self._is_player_a else state.position_a

        # Propose if we're ahead or risk > 5
        if my_position > opp_position or state.risk_level > 5:
            # Offer slightly generous to encourage acceptance
            offered_vp = max(25, min(75, int(100 - fair_vp + 5)))
            return SettlementProposal(
                offered_vp=offered_vp,
                argument="A settlement now preserves our mutual gains.",
            )

        return None


# =============================================================================
# GAME METRICS
# =============================================================================

@dataclass
class GameMetrics:
    """Metrics collected from a single game."""
    scenario_id: str
    player_a_name: str
    player_b_name: str
    winner: str
    ending_type: str
    turns_played: int
    vp_a: float
    vp_b: float
    settlement_reached: bool = False
    final_risk: float = 0.0
    final_cooperation: float = 0.0
    error: Optional[str] = None


@dataclass
class PlaytestResults:
    """Aggregated results from a playtest batch."""
    timestamp: str
    total_games: int
    scenarios: list[str]
    matchups: list[str]
    games: list[GameMetrics] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "total_games": self.total_games,
            "scenarios": self.scenarios,
            "matchups": self.matchups,
            "games": [
                {
                    "scenario_id": g.scenario_id,
                    "player_a_name": g.player_a_name,
                    "player_b_name": g.player_b_name,
                    "winner": g.winner,
                    "ending_type": g.ending_type,
                    "turns_played": g.turns_played,
                    "vp_a": g.vp_a,
                    "vp_b": g.vp_b,
                    "settlement_reached": g.settlement_reached,
                    "final_risk": g.final_risk,
                    "final_cooperation": g.final_cooperation,
                    "error": g.error,
                }
                for g in self.games
            ],
        }


# =============================================================================
# GAME RUNNER
# =============================================================================

async def run_single_game(
    scenario_id: str,
    player_a: Opponent,
    player_b: Opponent,
) -> GameMetrics:
    """Run a single game between two players."""
    repo = get_scenario_repository()
    engine = GameEngine(scenario_id, repo)

    if hasattr(player_a, 'set_player_side'):
        player_a.set_player_side(is_player_a=True)
    if hasattr(player_b, 'set_player_side'):
        player_b.set_player_side(is_player_a=False)

    settlement_reached = False

    try:
        while not engine.is_game_over():
            state = engine.get_current_state()

            # Check for settlement
            if state.turn > 4 and state.stability > 2:
                # Player A proposes
                if hasattr(player_a, 'propose_settlement'):
                    proposal_a = await player_a.propose_settlement(state)
                    if proposal_a:
                        if hasattr(player_b, 'evaluate_settlement'):
                            response = await player_b.evaluate_settlement(
                                proposal_a, state, is_final_offer=False
                            )
                            if response.action == "accept":
                                settlement_reached = True
                                vp_b = proposal_a.offered_vp
                                vp_a = 100 - vp_b
                                return GameMetrics(
                                    scenario_id=scenario_id,
                                    player_a_name=player_a.name,
                                    player_b_name=player_b.name,
                                    winner="A" if vp_a > vp_b else "B",
                                    ending_type="settlement",
                                    turns_played=state.turn,
                                    vp_a=vp_a,
                                    vp_b=vp_b,
                                    settlement_reached=True,
                                    final_risk=state.risk_level,
                                    final_cooperation=state.cooperation_score,
                                )

                # Player B proposes
                if hasattr(player_b, 'propose_settlement'):
                    proposal_b = await player_b.propose_settlement(state)
                    if proposal_b:
                        if hasattr(player_a, 'evaluate_settlement'):
                            response = await player_a.evaluate_settlement(
                                proposal_b, state, is_final_offer=False
                            )
                            if response.action == "accept":
                                settlement_reached = True
                                vp_a = proposal_b.offered_vp
                                vp_b = 100 - vp_a
                                return GameMetrics(
                                    scenario_id=scenario_id,
                                    player_a_name=player_a.name,
                                    player_b_name=player_b.name,
                                    winner="A" if vp_a > vp_b else "B",
                                    ending_type="settlement",
                                    turns_played=state.turn,
                                    vp_a=vp_a,
                                    vp_b=vp_b,
                                    settlement_reached=True,
                                    final_risk=state.risk_level,
                                    final_cooperation=state.cooperation_score,
                                )

            # Get actions
            actions_a = engine.get_available_actions("A")
            actions_b = engine.get_available_actions("B")

            action_a = await player_a.choose_action(state, actions_a)
            action_b = await player_b.choose_action(state, actions_b)

            result = engine.submit_actions(action_a, action_b)

            if hasattr(player_a, 'receive_result') and result.action_result:
                player_a.receive_result(result.action_result)
            if hasattr(player_b, 'receive_result') and result.action_result:
                player_b.receive_result(result.action_result)

            if result.ending:
                break

        final_state = engine.get_current_state()
        ending = engine.get_ending()

        if ending:
            vp_a = ending.vp_a
            vp_b = ending.vp_b
            ending_type = ending.ending_type.value
            if ending.ending_type == EndingType.MUTUAL_DESTRUCTION:
                winner = "mutual_destruction"
            elif vp_a > vp_b:
                winner = "A"
            elif vp_b > vp_a:
                winner = "B"
            else:
                winner = "tie"
        else:
            vp_a = vp_b = 50
            ending_type = "unknown"
            winner = "tie"

        return GameMetrics(
            scenario_id=scenario_id,
            player_a_name=player_a.name,
            player_b_name=player_b.name,
            winner=winner,
            ending_type=ending_type,
            turns_played=final_state.turn,
            vp_a=vp_a,
            vp_b=vp_b,
            settlement_reached=settlement_reached,
            final_risk=final_state.risk_level,
            final_cooperation=final_state.cooperation_score,
        )
    except Exception as e:
        return GameMetrics(
            scenario_id=scenario_id,
            player_a_name=player_a.name,
            player_b_name=player_b.name,
            winner="error",
            ending_type="error",
            turns_played=0,
            vp_a=0,
            vp_b=0,
            error=str(e),
        )


def create_historical_persona(persona_name: str, is_player_a: bool, role_name: str) -> HistoricalPersona:
    """Create a historical persona with proper side assignment."""
    return HistoricalPersona(
        persona_name=persona_name,
        is_player_a=is_player_a,
        role_name=role_name,
    )


async def run_playtest_batch(
    scenarios: list[str],
    games_per_matchup: int,
) -> PlaytestResults:
    """Run comprehensive playtest with 3x3 comparison per scenario."""
    results = PlaytestResults(
        timestamp=datetime.now().isoformat(),
        total_games=0,
        scenarios=scenarios,
        matchups=["historical_vs_historical", "smart_vs_historical_a", "smart_vs_historical_b"],
    )

    total_matchups = len(scenarios) * 3 * games_per_matchup
    completed = 0

    for scenario_id in scenarios:
        # Get scenario config
        config = SCENARIO_PERSONAS.get(scenario_id)
        if not config:
            print(f"Warning: No persona mapping for {scenario_id}, skipping")
            continue

        historical_a_name = config["historical_a"]
        historical_b_name = config["historical_b"]
        role_a = config.get("role_a", "Player A")
        role_b = config.get("role_b", "Player B")

        print(f"\n=== Scenario: {scenario_id} ===")
        print(f"  Historical A: {historical_a_name} ({role_a})")
        print(f"  Historical B: {historical_b_name} ({role_b})")

        # Matchup 1: Historical A vs Historical B
        print(f"\n  Matchup 1: {historical_a_name} vs {historical_b_name}")
        for game_num in range(games_per_matchup):
            player_a = create_historical_persona(historical_a_name, True, role_a)
            player_b = create_historical_persona(historical_b_name, False, role_b)

            metric = await run_single_game(scenario_id, player_a, player_b)
            results.games.append(metric)
            completed += 1

            if metric.error:
                print(f"    Game {game_num + 1}: ERROR - {metric.error}")
            else:
                print(f"    Game {game_num + 1}: {metric.winner} ({metric.ending_type}, {metric.turns_played} turns)")

        # Matchup 2: Smart Player (A) vs Historical B
        print(f"\n  Matchup 2: Smart Player vs {historical_b_name}")
        for game_num in range(games_per_matchup):
            player_a = SmartRationalPlayer(is_player_a=True)
            player_b = create_historical_persona(historical_b_name, False, role_b)

            metric = await run_single_game(scenario_id, player_a, player_b)
            results.games.append(metric)
            completed += 1

            if metric.error:
                print(f"    Game {game_num + 1}: ERROR - {metric.error}")
            else:
                print(f"    Game {game_num + 1}: {metric.winner} ({metric.ending_type}, {metric.turns_played} turns)")

        # Matchup 3: Historical A vs Smart Player (B)
        print(f"\n  Matchup 3: {historical_a_name} vs Smart Player")
        for game_num in range(games_per_matchup):
            player_a = create_historical_persona(historical_a_name, True, role_a)
            player_b = SmartRationalPlayer(is_player_a=False)

            metric = await run_single_game(scenario_id, player_a, player_b)
            results.games.append(metric)
            completed += 1

            if metric.error:
                print(f"    Game {game_num + 1}: ERROR - {metric.error}")
            else:
                print(f"    Game {game_num + 1}: {metric.winner} ({metric.ending_type}, {metric.turns_played} turns)")

    results.total_games = len(results.games)
    return results


def generate_markdown_report(results: PlaytestResults, output_path: Path) -> None:
    """Generate comprehensive markdown report."""
    lines = [
        "# Comprehensive LLM Playtest Report",
        "",
        f"**Generated:** {results.timestamp}",
        f"**Total Games:** {results.total_games}",
        f"**Scenarios:** {len(results.scenarios)}",
        "",
        "---",
        "",
        "## Overall Summary",
        "",
    ]

    valid_games = [g for g in results.games if g.error is None]
    if not valid_games:
        lines.append("No valid games completed.")
    else:
        # Overall stats
        settlements = sum(1 for g in valid_games if g.ending_type == "settlement")
        md = sum(1 for g in valid_games if g.ending_type == "mutual_destruction")
        a_wins = sum(1 for g in valid_games if g.winner == "A")
        b_wins = sum(1 for g in valid_games if g.winner == "B")

        avg_turns = sum(g.turns_played for g in valid_games) / len(valid_games)
        avg_risk = sum(g.final_risk for g in valid_games) / len(valid_games)

        lines.extend([
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

        # Per-matchup breakdown
        lines.extend([
            "## Results by Matchup Type",
            "",
        ])

        # Historical vs Historical
        hist_vs_hist = [g for g in valid_games
                       if "Smart Rational Player" not in g.player_a_name
                       and "Smart Rational Player" not in g.player_b_name]
        if hist_vs_hist:
            lines.append("### Historical vs Historical")
            lines.append("")
            _add_matchup_stats(lines, hist_vs_hist, "Historical A", "Historical B")

        # Smart vs Historical
        smart_vs_hist = [g for g in valid_games
                        if "Smart Rational Player" in g.player_a_name
                        or "Smart Rational Player" in g.player_b_name]
        if smart_vs_hist:
            lines.append("### Smart Player vs Historical")
            lines.append("")
            smart_wins = sum(1 for g in smart_vs_hist
                           if (g.winner == "A" and "Smart" in g.player_a_name)
                           or (g.winner == "B" and "Smart" in g.player_b_name))
            hist_wins = len(smart_vs_hist) - smart_wins - sum(1 for g in smart_vs_hist if g.winner in ["tie", "mutual_destruction"])
            settlements = sum(1 for g in smart_vs_hist if g.ending_type == "settlement")

            lines.extend([
                "| Metric | Value |",
                "|--------|-------|",
                f"| Games | {len(smart_vs_hist)} |",
                f"| Smart Player Win Rate | {smart_wins / len(smart_vs_hist) * 100:.1f}% |",
                f"| Historical Win Rate | {hist_wins / len(smart_vs_hist) * 100:.1f}% |",
                f"| Settlement Rate | {settlements / len(smart_vs_hist) * 100:.1f}% |",
                "",
            ])

        # Per-scenario breakdown
        lines.extend([
            "## Results by Scenario",
            "",
            "| Scenario | Games | Settlement % | MD % | Avg Turns |",
            "|----------|-------|--------------|------|-----------|",
        ])

        for scenario in results.scenarios:
            scenario_games = [g for g in valid_games if g.scenario_id == scenario]
            if scenario_games:
                settlements = sum(1 for g in scenario_games if g.ending_type == "settlement")
                md = sum(1 for g in scenario_games if g.ending_type == "mutual_destruction")
                avg_t = sum(g.turns_played for g in scenario_games) / len(scenario_games)
                lines.append(
                    f"| {scenario} | {len(scenario_games)} | "
                    f"{settlements / len(scenario_games) * 100:.0f}% | "
                    f"{md / len(scenario_games) * 100:.0f}% | "
                    f"{avg_t:.1f} |"
                )

        lines.append("")

        # Detailed matchup results table
        lines.extend([
            "## Detailed Matchup Results",
            "",
            "| Scenario | Matchup | Games | A Wins | B Wins | Settlement | MD |",
            "|----------|---------|-------|--------|--------|------------|-----|",
        ])

        for scenario in results.scenarios:
            config = SCENARIO_PERSONAS.get(scenario, {})
            hist_a = config.get("historical_a", "Unknown")
            hist_b = config.get("historical_b", "Unknown")

            for matchup_type, a_name, b_name in [
                ("hist_vs_hist", hist_a, hist_b),
                ("smart_vs_hist_b", "Smart", hist_b),
                ("hist_a_vs_smart", hist_a, "Smart"),
            ]:
                if matchup_type == "hist_vs_hist":
                    games = [g for g in valid_games
                            if g.scenario_id == scenario
                            and "Smart" not in g.player_a_name
                            and "Smart" not in g.player_b_name]
                    matchup_label = f"{hist_a} vs {hist_b}"
                elif matchup_type == "smart_vs_hist_b":
                    games = [g for g in valid_games
                            if g.scenario_id == scenario
                            and "Smart" in g.player_a_name]
                    matchup_label = f"Smart vs {hist_b}"
                else:
                    games = [g for g in valid_games
                            if g.scenario_id == scenario
                            and "Smart" in g.player_b_name]
                    matchup_label = f"{hist_a} vs Smart"

                if games:
                    a_wins = sum(1 for g in games if g.winner == "A")
                    b_wins = sum(1 for g in games if g.winner == "B")
                    settlements = sum(1 for g in games if g.ending_type == "settlement")
                    md = sum(1 for g in games if g.ending_type == "mutual_destruction")
                    lines.append(
                        f"| {scenario} | {matchup_label} | {len(games)} | "
                        f"{a_wins} | {b_wins} | {settlements} | {md} |"
                    )

    # Errors section
    error_games = [g for g in results.games if g.error is not None]
    if error_games:
        lines.extend([
            "",
            "## Errors",
            "",
        ])
        for g in error_games[:10]:
            lines.append(f"- {g.scenario_id}: {g.error}")
        if len(error_games) > 10:
            lines.append(f"- ... and {len(error_games) - 10} more errors")

    output_path.write_text("\n".join(lines))
    print(f"\nReport written to: {output_path}")


def _add_matchup_stats(lines: list[str], games: list[GameMetrics], a_label: str, b_label: str) -> None:
    """Add statistics for a matchup type."""
    a_wins = sum(1 for g in games if g.winner == "A")
    b_wins = sum(1 for g in games if g.winner == "B")
    settlements = sum(1 for g in games if g.ending_type == "settlement")
    md = sum(1 for g in games if g.ending_type == "mutual_destruction")

    lines.extend([
        "| Metric | Value |",
        "|--------|-------|",
        f"| Games | {len(games)} |",
        f"| {a_label} Win Rate | {a_wins / len(games) * 100:.1f}% |",
        f"| {b_label} Win Rate | {b_wins / len(games) * 100:.1f}% |",
        f"| Settlement Rate | {settlements / len(games) * 100:.1f}% |",
        f"| Mutual Destruction Rate | {md / len(games) * 100:.1f}% |",
        "",
    ])


def main():
    parser = argparse.ArgumentParser(description="Comprehensive LLM Playtesting")
    parser.add_argument("--total-games", type=int, default=500,
                        help="Total games to run across all scenarios")
    parser.add_argument("--scenarios", type=str,
                        help="Comma-separated scenario IDs (default: all)")
    parser.add_argument("--output", type=str, default="docs/COMPREHENSIVE_PLAYTEST_REPORT.md",
                        help="Output markdown file")

    args = parser.parse_args()

    # Get scenarios
    if args.scenarios:
        scenarios = [s.strip() for s in args.scenarios.split(",")]
    else:
        # Use all scenarios that have persona mappings
        scenarios = list(SCENARIO_PERSONAS.keys())

    # Calculate games per matchup
    # Each scenario has 3 matchups
    total_matchups = len(scenarios) * 3
    games_per_matchup = max(1, args.total_games // total_matchups)

    print(f"Comprehensive LLM Playtest Configuration:")
    print(f"  Scenarios: {len(scenarios)}")
    print(f"  Matchups per scenario: 3")
    print(f"  Games per matchup: {games_per_matchup}")
    print(f"  Total games: {len(scenarios) * 3 * games_per_matchup}")
    print(f"  Estimated API calls: ~{len(scenarios) * 3 * games_per_matchup * 20}")
    print()

    # Run playtests
    results = asyncio.run(run_playtest_batch(
        scenarios=scenarios,
        games_per_matchup=games_per_matchup,
    ))

    # Generate report
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    generate_markdown_report(results, output_path)

    # Save raw JSON
    json_path = output_path.with_suffix(".json")
    json_path.write_text(json.dumps(results.to_dict(), indent=2))
    print(f"JSON data written to: {json_path}")


if __name__ == "__main__":
    main()
