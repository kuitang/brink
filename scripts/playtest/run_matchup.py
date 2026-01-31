#!/usr/bin/env python3
"""Run a single matchup (multiple games between two players).

This is the atomic unit of work for the playtest system.
It runs N games between two specified players and writes results to a JSON file.

Usage:
    uv run python scripts/playtest/run_matchup.py \
        --scenario cuban_missile_crisis \
        --player-a historical:nixon \
        --player-b historical:khrushchev \
        --games 3 \
        --output work/cuban_missile_crisis__nixon_vs_khrushchev.json
"""

import argparse
import asyncio
import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from brinksmanship.engine.game_engine import EndingType, GameEngine
from brinksmanship.llm import generate_json
from brinksmanship.models.actions import Action, ActionType
from brinksmanship.models.state import GameState
from brinksmanship.opponents.base import Opponent, SettlementProposal, SettlementResponse
from brinksmanship.opponents.historical import HistoricalPersona
from brinksmanship.storage import get_scenario_repository

# =============================================================================
# SMART RATIONAL PLAYER
# =============================================================================

SMART_RATIONAL_PLAYER_PROMPT = """You are a skilled strategic player in a negotiation/crisis game.

GAME MECHANICS:
1. Cooperation (CC) creates shared value - a "surplus pool" grows
2. Defection (CD/DC) captures 40% of the pool - tempting but reduces shared value
3. Mutual Defection (DD) burns 20% of surplus AND raises risk
4. Risk at 10.0 = mutual destruction (0 VP for both - worst outcome)
5. Settlement after turn 4 locks in gains - good when ahead or risk is high

CURRENT STATE:
- Turn: {turn}, Risk: {risk_level}, Cooperation: {coop_score}
- Your Position: {my_position}, Resources: {my_resources}
- Opponent Position (est): {opp_position_est} (+/-{opp_uncertainty})
- Your Last Action: {my_last_type}, Opponent's Last: {opp_last_type}

ACTIONS:
{action_list}

Choose wisely based on game state and opponent patterns."""

SMART_RATIONAL_ACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "action": {"type": "string"},
        "reason": {"type": "string"},
    },
    "required": ["action"],
}


class SmartRationalPlayer(Opponent):
    """LLM-based player with game-theoretic understanding."""

    def __init__(self, is_player_a: bool = True):
        super().__init__(name="Smart Rational Player")
        self._is_player_a = is_player_a

    def set_player_side(self, is_player_a: bool) -> None:
        self._is_player_a = is_player_a

    def _get_player_state(self, state: GameState) -> tuple[float, float, ActionType | None]:
        """Get this player's position, resources, and previous action type."""
        if self._is_player_a:
            return state.position_a, state.resources_a, state.previous_type_a
        return state.position_b, state.resources_b, state.previous_type_b

    async def choose_action(self, state: GameState, available_actions: list[Action]) -> Action:
        my_pos, my_res, my_last = self._get_player_state(state)
        opp_last = state.previous_type_b if self._is_player_a else state.previous_type_a
        info = state.player_a.information if self._is_player_a else state.player_b.information
        opp_est, opp_unc = info.get_position_estimate(state.turn)

        action_list = "\n".join(
            f"- {a.name} [{'COOP' if a.action_type == ActionType.COOPERATIVE else 'COMP'}]: {a.description or ''}"
            for a in available_actions
        )

        prompt = SMART_RATIONAL_PLAYER_PROMPT.format(
            turn=state.turn,
            risk_level=f"{state.risk_level:.1f}",
            coop_score=f"{state.cooperation_score:.1f}",
            my_position=f"{my_pos:.1f}",
            my_resources=f"{my_res:.1f}",
            opp_position_est=f"{opp_est:.1f}",
            opp_uncertainty=f"{opp_unc:.1f}",
            my_last_type=my_last.value if my_last else "None",
            opp_last_type=opp_last.value if opp_last else "None",
            action_list=action_list,
        )

        response = await generate_json(
            prompt=prompt,
            system_prompt='You\'re playing a strategy game. Pick an action. Return JSON: {"action": "exact action name", "reason": "brief"}',
            schema=SMART_RATIONAL_ACTION_SCHEMA,
        )

        return self._find_matching_action(response.get("action", ""), available_actions)

    def _find_matching_action(self, selected: str, available_actions: list[Action]) -> Action:
        """Find the best matching action from available actions."""
        selected_lower = selected.strip().lower()

        # Exact match first
        for action in available_actions:
            if action.name.lower() == selected_lower:
                return action

        # Partial match
        for action in available_actions:
            if selected_lower in action.name.lower():
                return action

        # Fallback: first cooperative action or first action
        for action in available_actions:
            if action.action_type == ActionType.COOPERATIVE:
                return action
        return available_actions[0]

    async def evaluate_settlement(
        self, proposal: SettlementProposal, state: GameState, is_final_offer: bool
    ) -> SettlementResponse:
        my_vp = 100 - proposal.offered_vp
        fair_vp = self.get_position_fair_vp(state, self._is_player_a)

        if my_vp >= fair_vp - 15 or state.risk_level >= 7:
            return SettlementResponse(action="accept")
        if not is_final_offer and my_vp >= fair_vp - 25:
            return SettlementResponse(action="counter", counter_vp=max(20, min(80, int(fair_vp))))
        return SettlementResponse(action="reject")

    async def propose_settlement(self, state: GameState) -> SettlementProposal | None:
        if state.turn <= 4 or state.stability <= 2:
            return None

        fair_vp = self.get_position_fair_vp(state, self._is_player_a)
        my_pos = state.position_a if self._is_player_a else state.position_b
        opp_pos = state.position_b if self._is_player_a else state.position_a

        if my_pos > opp_pos or state.risk_level > 5:
            offered_vp = max(25, min(75, int(100 - fair_vp + 5)))
            return SettlementProposal(offered_vp=offered_vp, argument="Fair settlement")
        return None


# =============================================================================
# PLAYER FACTORY
# =============================================================================


def create_player(player_spec: str, is_player_a: bool) -> Opponent:
    """Create a player from a spec like 'historical:nixon' or 'smart'."""
    if player_spec == "smart":
        return SmartRationalPlayer(is_player_a=is_player_a)
    if player_spec.startswith("historical:"):
        persona_name = player_spec.split(":", 1)[1]
        return HistoricalPersona(persona_name=persona_name, is_player_a=is_player_a)
    raise ValueError(f"Unknown player spec: {player_spec}")


# =============================================================================
# GAME RUNNER
# =============================================================================


@dataclass
class GameResult:
    """Result of a single game."""

    scenario_id: str
    player_a: str
    player_b: str
    winner: str
    ending_type: str
    turns: int
    vp_a: float
    vp_b: float
    final_risk: float
    error: str | None = None


def _determine_winner(ending: EndingType | None, vp_a: float, vp_b: float) -> str:
    """Determine the winner string from ending type and VP scores."""
    if ending == EndingType.MUTUAL_DESTRUCTION:
        return "md"
    if vp_a > vp_b:
        return "A"
    if vp_b > vp_a:
        return "B"
    return "tie"


async def _try_settlement(
    proposer: Opponent,
    evaluator: Opponent,
    state: GameState,
    proposer_is_a: bool,
    scenario_id: str,
) -> GameResult | None:
    """Try to reach a settlement between proposer and evaluator."""
    if not hasattr(proposer, "propose_settlement") or not hasattr(evaluator, "evaluate_settlement"):
        return None

    proposal = await proposer.propose_settlement(state)
    if not proposal:
        return None

    response = await evaluator.evaluate_settlement(proposal, state, False)
    if response.action != "accept":
        return None

    if proposer_is_a:
        vp_b = proposal.offered_vp
        vp_a = 100 - vp_b
    else:
        vp_a = proposal.offered_vp
        vp_b = 100 - vp_a

    return GameResult(
        scenario_id=scenario_id,
        player_a=proposer.name if proposer_is_a else evaluator.name,
        player_b=evaluator.name if proposer_is_a else proposer.name,
        winner="A" if vp_a > vp_b else "B",
        ending_type="settlement",
        turns=state.turn,
        vp_a=vp_a,
        vp_b=vp_b,
        final_risk=state.risk_level,
    )


async def run_single_game(
    scenario_id: str,
    player_a: Opponent,
    player_b: Opponent,
) -> GameResult:
    """Run a single game between two players."""
    repo = get_scenario_repository()
    engine = GameEngine(scenario_id, repo)

    if hasattr(player_a, "set_player_side"):
        player_a.set_player_side(is_player_a=True)
    if hasattr(player_b, "set_player_side"):
        player_b.set_player_side(is_player_a=False)

    try:
        while not engine.is_game_over():
            state = engine.get_current_state()

            # Try settlement negotiations
            if state.turn > 4 and state.stability > 2:
                settlement = await _try_settlement(
                    player_a, player_b, state, proposer_is_a=True, scenario_id=scenario_id
                )
                if settlement:
                    return settlement
                settlement = await _try_settlement(
                    player_b, player_a, state, proposer_is_a=False, scenario_id=scenario_id
                )
                if settlement:
                    return settlement

            # Execute turn
            actions_a = engine.get_available_actions("A")
            actions_b = engine.get_available_actions("B")
            action_a = await player_a.choose_action(state, actions_a)
            action_b = await player_b.choose_action(state, actions_b)
            result = engine.submit_actions(action_a, action_b)

            if result.ending:
                break

        final_state = engine.get_current_state()
        ending = engine.get_ending()

        if ending:
            return GameResult(
                scenario_id=scenario_id,
                player_a=player_a.name,
                player_b=player_b.name,
                winner=_determine_winner(ending.ending_type, ending.vp_a, ending.vp_b),
                ending_type=ending.ending_type.value,
                turns=final_state.turn,
                vp_a=ending.vp_a,
                vp_b=ending.vp_b,
                final_risk=final_state.risk_level,
            )

        return GameResult(
            scenario_id=scenario_id,
            player_a=player_a.name,
            player_b=player_b.name,
            winner="tie",
            ending_type="unknown",
            turns=final_state.turn,
            vp_a=50,
            vp_b=50,
            final_risk=final_state.risk_level,
        )
    except Exception as e:
        return GameResult(
            scenario_id=scenario_id,
            player_a=player_a.name,
            player_b=player_b.name,
            winner="error",
            ending_type="error",
            turns=0,
            vp_a=0,
            vp_b=0,
            final_risk=0,
            error=str(e),
        )


async def run_matchup(
    scenario_id: str,
    player_a_spec: str,
    player_b_spec: str,
    num_games: int,
) -> list[dict]:
    """Run multiple games for a matchup."""
    results = []
    for i in range(num_games):
        player_a = create_player(player_a_spec, is_player_a=True)
        player_b = create_player(player_b_spec, is_player_a=False)
        result = await run_single_game(scenario_id, player_a, player_b)
        results.append(asdict(result))
        print(f"  Game {i + 1}/{num_games}: {result.winner} ({result.ending_type})")
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a single matchup")
    parser.add_argument("--scenario", required=True, help="Scenario ID")
    parser.add_argument("--player-a", required=True, help="Player A spec (e.g., historical:nixon or smart)")
    parser.add_argument("--player-b", required=True, help="Player B spec")
    parser.add_argument("--games", type=int, default=3, help="Number of games")
    parser.add_argument("--output", required=True, help="Output JSON file")
    args = parser.parse_args()

    print(f"Matchup: {args.scenario}")
    print(f"  {args.player_a} vs {args.player_b}")
    print(f"  {args.games} games")

    results = asyncio.run(
        run_matchup(
            scenario_id=args.scenario,
            player_a_spec=args.player_a,
            player_b_spec=args.player_b,
            num_games=args.games,
        )
    )

    output = {
        "scenario": args.scenario,
        "player_a": args.player_a,
        "player_b": args.player_b,
        "timestamp": datetime.now().isoformat(),
        "games": results,
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, indent=2))
    print(f"Results written to: {output_path}")


if __name__ == "__main__":
    main()
