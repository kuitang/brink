"""Leaderboard service."""

from typing import Any

from sqlalchemy import func

from ..extensions import db
from ..models.game_record import GameRecord
from ..models.user import User


def get_leaderboard(scenario_id: str, opponent_type: str, limit: int = 50) -> list[dict[str, Any]]:
    """Get ranked leaderboard for a scenario/opponent pair.

    Ranking: VP descending, then finished_at ascending (earlier wins ties).
    """
    results = (
        db.session.query(
            GameRecord.id,
            GameRecord.user_id,
            User.username,
            GameRecord.final_vp_player,
            GameRecord.turn,
            GameRecord.ending_type,
            GameRecord.finished_at,
        )
        .join(User, GameRecord.user_id == User.id)
        .filter(
            GameRecord.scenario_id == scenario_id,
            GameRecord.opponent_type == opponent_type,
            GameRecord.is_finished,
            GameRecord.final_vp_player.isnot(None),
        )
        .order_by(
            GameRecord.final_vp_player.desc(),
            GameRecord.finished_at.asc(),
        )
        .limit(limit)
        .all()
    )

    return [
        {
            "rank": rank,
            "user_id": row.user_id,
            "username": row.username,
            "vp": row.final_vp_player,
            "turns": row.turn,
            "ending_type": row.ending_type,
            "finished_at": row.finished_at,
        }
        for rank, row in enumerate(results, start=1)
    ]


def get_available_leaderboards() -> list[dict[str, Any]]:
    """Get list of all scenario/opponent pairs that have games."""
    results = (
        db.session.query(
            GameRecord.scenario_id,
            GameRecord.scenario_name,
            GameRecord.opponent_type,
            func.count(GameRecord.id).label("game_count"),
        )
        .filter(
            GameRecord.is_finished,
            GameRecord.final_vp_player.isnot(None),
        )
        .group_by(GameRecord.scenario_id, GameRecord.scenario_name, GameRecord.opponent_type)
        .order_by(func.count(GameRecord.id).desc())
        .all()
    )

    return [
        {
            "scenario_id": row.scenario_id,
            "scenario_name": row.scenario_name or row.scenario_id,
            "opponent_type": row.opponent_type,
            "game_count": row.game_count,
        }
        for row in results
    ]
