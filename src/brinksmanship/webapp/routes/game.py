"""Game routes - main gameplay loop."""

from datetime import datetime

from flask import Blueprint, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from ..extensions import db
from ..models.game_record import GameRecord
from ..services.game_service import get_game_service

bp = Blueprint("game", __name__, url_prefix="/game")


@bp.route("/<game_id>")
@login_required
def play(game_id: str):
    """Main game page."""
    game_record = GameRecord.query.filter_by(
        game_id=game_id, user_id=current_user.id
    ).first_or_404()

    if game_record.is_finished:
        return redirect(url_for("game.game_over", game_id=game_id))

    game_service = get_game_service()
    state = game_record.state
    actions = game_service.get_available_actions(state)

    return render_template(
        "pages/game.html",
        game_id=game_id,
        state=state,
        actions=actions,
    )


@bp.route("/<game_id>/action", methods=["POST"])
@login_required
def submit_action(game_id: str):
    """Submit player action."""
    game_record = GameRecord.query.filter_by(
        game_id=game_id, user_id=current_user.id
    ).first_or_404()

    if game_record.is_finished:
        return redirect(url_for("game.game_over", game_id=game_id))

    action_id = request.form.get("action_id", "")
    game_service = get_game_service()

    # Process action
    state = game_record.state
    new_state = game_service.submit_action(state, action_id)

    # Update record
    game_record.state = new_state
    game_record.updated_at = datetime.utcnow()

    # Check for game over
    if new_state.get("is_finished"):
        game_record.is_finished = True
        game_record.ending_type = new_state.get("ending_type", "unknown")
        game_record.final_vp_player = new_state.get("vp_player")
        game_record.final_vp_opponent = new_state.get("vp_opponent")
        game_record.finished_at = datetime.utcnow()

    db.session.commit()

    # Handle htmx vs regular request
    if request.headers.get("HX-Request"):
        if game_record.is_finished:
            # Use HX-Redirect for htmx
            response = redirect(url_for("game.game_over", game_id=game_id))
            response.headers["HX-Redirect"] = url_for("game.game_over", game_id=game_id)
            return response
        actions = game_service.get_available_actions(new_state)
        return render_template(
            "components/game_board.html",
            game_id=game_id,
            state=new_state,
            actions=actions,
        )

    return redirect(url_for("game.play", game_id=game_id))


@bp.route("/<game_id>/over")
@login_required
def game_over(game_id: str):
    """Game over screen."""
    game_record = GameRecord.query.filter_by(
        game_id=game_id, user_id=current_user.id
    ).first_or_404()

    return render_template(
        "pages/game_over.html",
        game_id=game_id,
        game=game_record,
        state=game_record.state,
    )
