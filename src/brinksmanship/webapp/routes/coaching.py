"""Coaching routes - post-game analysis and feedback."""

import asyncio

from flask import Blueprint, flash, redirect, render_template, url_for
from flask_login import current_user, login_required

from ..models.game_record import GameRecord
from ..services.coaching_service import generate_coaching_report

bp = Blueprint("coaching", __name__, url_prefix="/game")


@bp.route("/<game_id>/coaching")
@login_required
def view(game_id: str):
    """Coaching analysis page.

    Shows loading indicator initially, then uses htmx to fetch the
    actual coaching report which may take 10-30 seconds to generate.
    """
    game_record = GameRecord.query.filter_by(game_id=game_id, user_id=current_user.id).first_or_404()

    if not game_record.is_finished:
        flash("Coaching analysis is only available for completed games.", "warning")
        return redirect(url_for("game.play", game_id=game_id))

    return render_template(
        "pages/coaching.html",
        game_id=game_id,
        game=game_record,
        state=game_record.state,
    )


@bp.route("/<game_id>/coaching/generate")
@login_required
def generate(game_id: str):
    """htmx endpoint that generates coaching report.

    This endpoint is called via htmx hx-get with hx-trigger="load"
    to fetch the coaching analysis asynchronously after page load.
    """
    game_record = GameRecord.query.filter_by(game_id=game_id, user_id=current_user.id).first_or_404()

    if not game_record.is_finished:
        return render_template(
            "components/coaching_error.html",
            error="Game not finished. Coaching requires a completed game.",
        )

    try:
        # Run async coaching generation in sync context
        report = asyncio.run(generate_coaching_report(game_record))

        return render_template(
            "components/coaching_report.html",
            report=report,
            game=game_record,
        )

    except Exception as e:
        return render_template(
            "components/coaching_error.html",
            error=f"Failed to generate coaching analysis: {str(e)}",
        )
