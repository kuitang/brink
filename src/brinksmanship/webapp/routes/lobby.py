"""Lobby routes - game list and new game creation."""

import uuid

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from ..extensions import db
from ..models.game_record import GameRecord
from ..services.game_service import get_game_service

bp = Blueprint("lobby", __name__)


@bp.route("/")
@login_required
def index():
    """Main lobby - show active and completed games."""
    active_games = (
        GameRecord.query.filter_by(user_id=current_user.id, is_finished=False)
        .order_by(GameRecord.updated_at.desc())
        .all()
    )

    finished_games = (
        GameRecord.query.filter_by(user_id=current_user.id, is_finished=True)
        .order_by(GameRecord.finished_at.desc())
        .limit(10)
        .all()
    )

    return render_template(
        "pages/lobby.html",
        active_games=active_games,
        finished_games=finished_games,
    )


@bp.route("/new", methods=["GET", "POST"])
@login_required
def new_game():
    """Create a new game."""
    game_service = get_game_service()

    if request.method == "POST":
        scenario_id = request.form.get("scenario_id", "")
        opponent_type = request.form.get("opponent_type", "")

        if not scenario_id or not opponent_type:
            flash("Please select a scenario and opponent.", "error")
            return redirect(url_for("lobby.new_game"))

        # Create game via service
        game_id = str(uuid.uuid4())[:8]
        state = game_service.create_game(scenario_id, opponent_type, current_user.id)

        # Persist game record
        game_record = GameRecord(
            game_id=game_id,
            user_id=current_user.id,
            scenario_id=scenario_id,
            opponent_type=opponent_type,
        )
        game_record.state = state
        db.session.add(game_record)
        db.session.commit()

        return redirect(url_for("game.play", game_id=game_id))

    # GET - show new game form
    scenarios = game_service.get_scenarios()
    opponent_types = game_service.get_opponent_types()

    return render_template(
        "pages/new_game.html",
        scenarios=scenarios,
        opponent_types=opponent_types,
    )
