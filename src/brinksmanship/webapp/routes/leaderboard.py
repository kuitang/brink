"""Leaderboard routes."""

from flask import Blueprint, render_template
from flask_login import current_user

from ..services.leaderboard import get_available_leaderboards, get_leaderboard

bp = Blueprint("leaderboard", __name__, url_prefix="/leaderboard")


@bp.route("/")
def index():
    """List all available leaderboards."""
    leaderboards = get_available_leaderboards()
    return render_template("pages/leaderboards.html", leaderboards=leaderboards)


@bp.route("/<scenario_id>/<opponent_type>")
def view(scenario_id: str, opponent_type: str):
    """View a specific leaderboard."""
    entries = get_leaderboard(scenario_id, opponent_type)

    # Get scenario name from first entry or use ID
    scenario_name = scenario_id
    if entries:
        # Try to get scenario name from game service
        from ..services.game_service import get_game_service

        game_service = get_game_service()
        for scenario in game_service.get_scenarios():
            if scenario["id"] == scenario_id:
                scenario_name = scenario["name"]
                break

    current_user_id = current_user.id if current_user.is_authenticated else None

    return render_template(
        "pages/leaderboard.html",
        entries=entries,
        scenario_id=scenario_id,
        scenario_name=scenario_name,
        opponent_type=opponent_type,
        current_user_id=current_user_id,
    )
