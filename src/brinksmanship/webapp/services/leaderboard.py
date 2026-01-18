"""Leaderboard service."""

from datetime import datetime
from typing import Any

from sqlalchemy import func

from ..extensions import db
from ..models.game_record import GameRecord
from ..models.user import User


def get_leaderboard(
    scenario_id: str, opponent_type: str, limit: int = 50
) -> list[dict[str, Any]]:
    """Get ranked leaderboard for a scenario/opponent pair.

    Ranking: VP descending, then finished_at ascending (earlier wins ties).

    Args:
        scenario_id: Scenario identifier
        opponent_type: Opponent type identifier
        limit: Maximum number of entries to return

    Returns:
        List of {rank, user_id, username, vp, turns, ending_type, finished_at}
    """
    results = (
        db.session.query(
            GameRecord.id,
            GameRecord.user_id,
            User.username,
            GameRecord.final_vp_player,
            GameRecord.state_json,
            GameRecord.ending_type,
            GameRecord.finished_at,
        )
        .join(User, GameRecord.user_id == User.id)
        .filter(
            GameRecord.scenario_id == scenario_id,
            GameRecord.opponent_type == opponent_type,
            GameRecord.is_finished == True,
            GameRecord.final_vp_player.isnot(None),
        )
        .order_by(
            GameRecord.final_vp_player.desc(),
            GameRecord.finished_at.asc(),
        )
        .limit(limit)
        .all()
    )

    entries = []
    for rank, row in enumerate(results, start=1):
        # Extract turn count from state_json
        import json

        state = json.loads(row.state_json) if row.state_json else {}
        turns = state.get("turn", 0)

        entries.append(
            {
                "rank": rank,
                "user_id": row.user_id,
                "username": row.username,
                "vp": row.final_vp_player,
                "turns": turns,
                "ending_type": row.ending_type,
                "finished_at": row.finished_at,
            }
        )

    return entries


def get_available_leaderboards() -> list[dict[str, Any]]:
    """Get list of all scenario/opponent pairs that have games.

    Returns:
        List of {scenario_id, scenario_name, opponent_type, game_count}
    """
    import json

    results = (
        db.session.query(
            GameRecord.scenario_id,
            GameRecord.opponent_type,
            GameRecord.state_json,
            func.count(GameRecord.id).label("game_count"),
        )
        .filter(
            GameRecord.is_finished == True,
            GameRecord.final_vp_player.isnot(None),
        )
        .group_by(GameRecord.scenario_id, GameRecord.opponent_type)
        .order_by(func.count(GameRecord.id).desc())
        .all()
    )

    leaderboards = []
    for row in results:
        # Extract scenario name from first game's state
        state = json.loads(row.state_json) if row.state_json else {}
        scenario_name = state.get("scenario_name", row.scenario_id)

        leaderboards.append(
            {
                "scenario_id": row.scenario_id,
                "scenario_name": scenario_name,
                "opponent_type": row.opponent_type,
                "game_count": row.game_count,
            }
        )

    return leaderboards
