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
    game_record = GameRecord.query.filter_by(game_id=game_id, user_id=current_user.id).first_or_404()

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
    game_record = GameRecord.query.filter_by(game_id=game_id, user_id=current_user.id).first_or_404()

    if game_record.is_finished:
        return redirect(url_for("game.game_over", game_id=game_id))

    action_id = request.form.get("action_id", "")
    game_service = get_game_service()

    # Process action
    state = game_record.state
    new_state = game_service.submit_action(state, action_id)

    # Record turn in history with full trace data
    game_record.add_turn(
        turn=new_state["new_turn_number"],
        player=new_state["new_turn_player"],
        opponent=new_state["new_turn_opponent"],
        player_action_name=new_state.get("new_turn_player_action_name"),
        opponent_action_name=new_state.get("new_turn_opponent_action_name"),
        outcome_code=new_state.get("new_turn_outcome_code"),
        narrative=new_state.get("new_turn_narrative"),
        state_after=new_state.get("new_turn_state_after"),
    )

    # Update record
    game_record.update_from_state(new_state)
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
    """Game over screen with multi-criteria scorecard."""
    game_record = GameRecord.query.filter_by(game_id=game_id, user_id=current_user.id).first_or_404()

    # Calculate scorecard metrics
    scorecard = _compute_scorecard(game_record)

    return render_template(
        "pages/game_over.html",
        game_id=game_id,
        game=game_record,
        state=game_record.state,
        scorecard=scorecard,
    )


def _compute_scorecard(game_record: GameRecord) -> dict:
    """Compute multi-criteria scorecard metrics for game end display.

    Based on GAME_MANUAL.md section 4.4 Multi-Criteria Scorecard.
    """
    vp_player = game_record.final_vp_player or 0
    vp_opponent = game_record.final_vp_opponent or 0
    total_vp = vp_player + vp_opponent

    # Personal Success
    vp_share_player = (vp_player / total_vp * 100) if total_vp > 0 else 50.0
    vp_share_opponent = (vp_opponent / total_vp * 100) if total_vp > 0 else 50.0

    # Joint Success
    baseline_vp = 100  # Zero-sum baseline
    value_vs_baseline = total_vp - baseline_vp

    # Pareto efficiency: ratio of actual total to theoretical maximum
    # Theoretical max depends on game length and perfect cooperation
    # Simplified: use 150 as max achievable (100 base + 50 max surplus)
    theoretical_max = 150
    pareto_efficiency = min(100.0, (total_vp / theoretical_max) * 100)

    # Settlement info
    settlement_reached = game_record.ending_type == "settlement"
    surplus_distributed = 0.0
    settlement_initiator = None

    if settlement_reached:
        # Calculate surplus distributed (total captured surplus)
        surplus_distributed = game_record.surplus_captured_player + game_record.surplus_captured_opponent
        # Find who initiated settlement
        first_attempt = game_record.settlement_attempts.first()
        if first_attempt:
            settlement_initiator = first_attempt.proposer

    # Strategic Profile
    history = list(game_record.turns.all())

    # Calculate max cooperation streak
    max_streak = 0
    current_streak = 0
    for turn in history:
        if turn.outcome_code == "CC":
            current_streak += 1
            max_streak = max(max_streak, current_streak)
        else:
            current_streak = 0

    # Also check game record's stored streak if higher
    if game_record.cooperation_streak > max_streak:
        max_streak = game_record.cooperation_streak

    # Count times exploited (CD for player, DC for opponent)
    times_player_exploited = sum(1 for t in history if t.outcome_code == "CD")
    times_opponent_exploited = sum(1 for t in history if t.outcome_code == "DC")

    return {
        # Personal Success
        "vp_player": vp_player,
        "vp_opponent": vp_opponent,
        "vp_share_player": round(vp_share_player, 1),
        "vp_share_opponent": round(vp_share_opponent, 1),
        # Joint Success
        "total_vp": total_vp,
        "value_vs_baseline": value_vs_baseline,
        "pareto_efficiency": round(pareto_efficiency, 1),
        # Settlement Info
        "settlement_reached": settlement_reached,
        "surplus_distributed": round(surplus_distributed, 1),
        "surplus_remaining": round(game_record.cooperation_surplus, 1),
        "settlement_initiator": settlement_initiator,
        # Strategic Profile
        "max_streak": max_streak,
        "times_player_exploited": times_player_exploited,
        "times_opponent_exploited": times_opponent_exploited,
    }


@bp.route("/<game_id>/trace")
@login_required
def get_trace(game_id: str):
    """Get full game trace as JSON."""
    from flask import jsonify

    game_record = GameRecord.query.filter_by(game_id=game_id, user_id=current_user.id).first_or_404()

    return jsonify(game_record.get_trace())


# Settlement routes


@bp.route("/<game_id>/settlement")
@login_required
def settlement_panel(game_id: str):
    """Get settlement panel HTML."""
    game_record = GameRecord.query.filter_by(game_id=game_id, user_id=current_user.id).first_or_404()

    if game_record.is_finished:
        return "", 204  # No content if game is over

    game_service = get_game_service()
    state = game_record.state

    can_settle = game_service.can_propose_settlement(state)
    suggested_vp = game_service.get_suggested_settlement_vp(state) if can_settle else 50

    # Check if opponent wants to propose
    opponent_proposal = game_service.check_opponent_settlement(state) if can_settle else None

    return render_template(
        "components/settlement_panel.html",
        game_id=game_id,
        state=state,
        can_settle=can_settle,
        suggested_vp=suggested_vp,
        opponent_proposal=opponent_proposal,
    )


@bp.route("/<game_id>/settlement/propose", methods=["POST"])
@login_required
def propose_settlement(game_id: str):
    """Player proposes settlement."""
    game_record = GameRecord.query.filter_by(game_id=game_id, user_id=current_user.id).first_or_404()

    if game_record.is_finished:
        return redirect(url_for("game.game_over", game_id=game_id))

    game_service = get_game_service()
    state = game_record.state

    if not game_service.can_propose_settlement(state):
        return render_template(
            "components/settlement_response.html",
            game_id=game_id,
            error="Settlement not available (requires Turn > 4 and Stability > 2)",
        )

    # Get proposal from form
    try:
        offered_vp = int(request.form.get("offered_vp", 50))
    except ValueError:
        offered_vp = 50

    argument = request.form.get("argument", "")[:500]

    # Clamp VP to valid range
    offered_vp = max(20, min(80, offered_vp))

    # Evaluate with opponent
    response = game_service.evaluate_settlement(state, offered_vp, argument)

    # Record the settlement attempt
    game_record.add_settlement_attempt(
        turn=state.get("turn", 1),
        proposer="player",
        offered_vp=offered_vp,
        argument=argument,
        response_action=response["action"],
        counter_vp=response.get("counter_vp"),
        counter_argument=response.get("counter_argument"),
        rejection_reason=response.get("rejection_reason"),
    )
    db.session.commit()

    if response["action"] == "accept":
        # Settlement accepted - end game
        player_vp = offered_vp
        new_state = game_service.finalize_settlement(state, player_vp)

        game_record.update_from_state(new_state)
        game_record.is_finished = True
        game_record.final_vp_player = player_vp
        game_record.final_vp_opponent = 100 - player_vp
        game_record.finished_at = datetime.utcnow()
        db.session.commit()

        # Return redirect via htmx
        response_html = render_template(
            "components/settlement_response.html",
            game_id=game_id,
            accepted=True,
            player_vp=player_vp,
        )
        resp = response_html
        return resp, 200, {"HX-Redirect": url_for("game.game_over", game_id=game_id)}

    return render_template(
        "components/settlement_response.html",
        game_id=game_id,
        response=response,
        offered_vp=offered_vp,
    )


@bp.route("/<game_id>/settlement/respond", methods=["POST"])
@login_required
def respond_to_settlement(game_id: str):
    """Player responds to opponent's settlement proposal."""
    game_record = GameRecord.query.filter_by(game_id=game_id, user_id=current_user.id).first_or_404()

    if game_record.is_finished:
        return redirect(url_for("game.game_over", game_id=game_id))

    game_service = get_game_service()
    state = game_record.state

    action = request.form.get("action", "reject")
    opponent_vp = int(request.form.get("opponent_vp", 50))
    opponent_argument = request.form.get("opponent_argument", "")

    if action == "accept":
        # Player accepts opponent's offer
        player_vp = 100 - opponent_vp

        # Record settlement attempt
        game_record.add_settlement_attempt(
            turn=state.get("turn", 1),
            proposer="opponent",
            offered_vp=opponent_vp,
            argument=opponent_argument,
            response_action="accept",
        )

        new_state = game_service.finalize_settlement(state, player_vp)
        game_record.update_from_state(new_state)
        game_record.is_finished = True
        game_record.final_vp_player = player_vp
        game_record.final_vp_opponent = opponent_vp
        game_record.finished_at = datetime.utcnow()
        db.session.commit()

        return "", 200, {"HX-Redirect": url_for("game.game_over", game_id=game_id)}

    elif action == "counter":
        # Player counters
        try:
            counter_vp = int(request.form.get("counter_vp", 50))
        except ValueError:
            counter_vp = 50

        counter_argument = request.form.get("counter_argument", "")[:500]

        # Record opponent's proposal and player's counter
        game_record.add_settlement_attempt(
            turn=state.get("turn", 1),
            proposer="opponent",
            offered_vp=opponent_vp,
            argument=opponent_argument,
            response_action="counter",
            counter_vp=counter_vp,
            counter_argument=counter_argument,
        )
        db.session.commit()

        # Evaluate counter with opponent (as final offer)
        response = game_service.evaluate_settlement(state, counter_vp, counter_argument)

        if response["action"] == "accept":
            player_vp = counter_vp
            new_state = game_service.finalize_settlement(state, player_vp)
            game_record.update_from_state(new_state)
            game_record.is_finished = True
            game_record.final_vp_player = player_vp
            game_record.final_vp_opponent = 100 - player_vp
            game_record.finished_at = datetime.utcnow()
            db.session.commit()

            return "", 200, {"HX-Redirect": url_for("game.game_over", game_id=game_id)}

        return render_template(
            "components/settlement_response.html",
            game_id=game_id,
            response=response,
            offered_vp=counter_vp,
            is_counter_response=True,
        )

    else:
        # Player rejects
        game_record.add_settlement_attempt(
            turn=state.get("turn", 1),
            proposer="opponent",
            offered_vp=opponent_vp,
            argument=opponent_argument,
            response_action="reject",
        )
        db.session.commit()

        return render_template(
            "components/settlement_response.html",
            game_id=game_id,
            rejected=True,
        )
