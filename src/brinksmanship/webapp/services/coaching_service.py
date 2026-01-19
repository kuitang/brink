"""Coaching service - wrapper around PostGameCoach for webapp use.

Converts webapp GameRecord state to the format expected by PostGameCoach,
which analyzes completed games and provides structured coaching feedback.
"""

from brinksmanship.coaching import CoachingReport, PostGameCoach
from brinksmanship.engine.game_engine import EndingType, GameEnding, TurnRecord, TurnPhase
from brinksmanship.models.actions import Action, ActionType
from brinksmanship.models.state import GameState

from ..models.game_record import GameRecord


def _action_type_from_symbol(symbol: str) -> ActionType:
    """Convert C/D symbol to ActionType."""
    return ActionType.COOPERATIVE if symbol == "C" else ActionType.COMPETITIVE


def _ending_type_from_string(ending_str: str) -> EndingType:
    """Convert ending type string to EndingType enum."""
    mapping = {
        "mutual_destruction": EndingType.MUTUAL_DESTRUCTION,
        "position_collapse_a": EndingType.POSITION_COLLAPSE_A,
        "position_collapse_b": EndingType.POSITION_COLLAPSE_B,
        "player_eliminated": EndingType.POSITION_COLLAPSE_A,
        "opponent_eliminated": EndingType.POSITION_COLLAPSE_B,
        "resource_exhaustion_a": EndingType.RESOURCE_EXHAUSTION_A,
        "resource_exhaustion_b": EndingType.RESOURCE_EXHAUSTION_B,
        "crisis_termination": EndingType.CRISIS_TERMINATION,
        "natural_ending": EndingType.NATURAL_ENDING,
        "settlement": EndingType.SETTLEMENT,
    }
    return mapping.get(ending_str, EndingType.NATURAL_ENDING)


def _build_turn_records(state: dict) -> list[TurnRecord]:
    """Build TurnRecord list from webapp state history.

    The webapp stores history as:
    [{"turn": 1, "player": "C", "opponent": "D"}, ...]

    We reconstruct TurnRecord objects with minimal Action stubs
    since the coach primarily needs action types.
    """
    history = state.get("history", [])
    records = []

    for entry in history:
        turn_num = entry.get("turn", len(records) + 1)
        player_symbol = entry.get("player", "C")
        opponent_symbol = entry.get("opponent", "C")

        # Create stub actions with just the type information
        player_action = Action(
            name="Cooperate" if player_symbol == "C" else "Defect",
            action_type=_action_type_from_symbol(player_symbol),
            resource_cost=0,
            description="",
        )
        opponent_action = Action(
            name="Cooperate" if opponent_symbol == "C" else "Defect",
            action_type=_action_type_from_symbol(opponent_symbol),
            resource_cost=0,
            description="",
        )

        # Create minimal state_before for Bayesian inference
        # We don't have full state history, so use approximate values
        state_before = GameState(
            turn=turn_num,
            max_turns=state.get("max_turns", 14),
            position_a=state.get("position_player", 5.0),
            position_b=state.get("position_opponent", 5.0),
            resources_a=state.get("resources_player", 10.0),
            resources_b=state.get("resources_opponent", 10.0),
            risk_level=state.get("risk_level", 0.0),
            cooperation_score=float(state.get("cooperation_score", 50)),
            stability=float(state.get("stability", 50)),
        )

        record = TurnRecord(
            turn=turn_num,
            phase=TurnPhase.GAME_OVER,
            action_a=player_action,
            action_b=opponent_action,
            state_before=state_before,
        )
        records.append(record)

    return records


def _build_game_ending(game_record: GameRecord) -> GameEnding:
    """Build GameEnding from GameRecord."""
    ending_type = _ending_type_from_string(game_record.ending_type or "natural_ending")
    state = game_record.state

    return GameEnding(
        ending_type=ending_type,
        vp_a=float(game_record.final_vp_player or 50),
        vp_b=float(game_record.final_vp_opponent or 50),
        turn=state.get("turn", 1),
        description=state.get("ending_description", "Game concluded."),
    )


def _build_final_state(state: dict) -> GameState:
    """Build GameState from webapp state dict."""
    return GameState(
        turn=state.get("turn", 1),
        max_turns=state.get("max_turns", 14),
        position_a=state.get("position_player", 5.0),
        position_b=state.get("position_opponent", 5.0),
        resources_a=state.get("resources_player", 10.0),
        resources_b=state.get("resources_opponent", 10.0),
        risk_level=state.get("risk_level", 0.0),
        cooperation_score=float(state.get("cooperation_score", 50)),
        stability=float(state.get("stability", 50)),
    )


async def generate_coaching_report(game_record: GameRecord) -> CoachingReport:
    """Generate coaching analysis for a completed game.

    Converts GameRecord's persisted state into the TurnRecord format
    expected by PostGameCoach.analyze_game().

    Args:
        game_record: Completed game record from database.

    Returns:
        CoachingReport with full LLM analysis and Bayesian inference.

    Raises:
        ValueError: If game is not finished.
    """
    if not game_record.is_finished:
        raise ValueError("Cannot generate coaching for unfinished game")

    state = game_record.state

    # Build the data structures expected by PostGameCoach
    history = _build_turn_records(state)
    ending = _build_game_ending(game_record)
    final_state = _build_final_state(state)

    # Get player role and opponent info
    scenario_name = state.get("scenario_name", "Unknown Scenario")
    opponent_type = state.get("opponent_type", game_record.opponent_type)
    player_role = f"Player in {scenario_name}"

    # Create coach and analyze
    coach = PostGameCoach()
    report = await coach.analyze_game(
        history=history,
        ending=ending,
        final_state=final_state,
        player_role=player_role,
        opponent_type=opponent_type,
        player_is_a=True,
    )

    return report
