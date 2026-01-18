"""Scenario management routes."""

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_required

from ..services.game_service import get_game_service

bp = Blueprint("scenarios", __name__, url_prefix="/scenarios")

# Built-in themes for scenario generation
GENERATION_THEMES = [
    {
        "id": "cold-war",
        "name": "Cold War",
        "description": "Superpower brinkmanship, proxy conflicts, arms control negotiations",
    },
    {
        "id": "corporate",
        "name": "Corporate Governance",
        "description": "Hostile takeovers, board conflicts, merger negotiations",
    },
    {
        "id": "ancient",
        "name": "Ancient History",
        "description": "Succession crises, alliance formation, territorial disputes",
    },
    {
        "id": "palace",
        "name": "Palace Intrigue",
        "description": "Court politics, succession, factional conflict",
    },
    {
        "id": "legal",
        "name": "Legal Strategy",
        "description": "Settlement negotiations, litigation tactics",
    },
]


@bp.route("/")
def index():
    """List all available scenarios."""
    game_service = get_game_service()
    scenarios = game_service.get_scenarios()

    return render_template("pages/scenarios.html", scenarios=scenarios)


@bp.route("/<scenario_id>")
def view(scenario_id: str):
    """View scenario details."""
    game_service = get_game_service()
    scenarios = game_service.get_scenarios()

    scenario = next((s for s in scenarios if s["id"] == scenario_id), None)
    if not scenario:
        flash("Scenario not found.", "error")
        return redirect(url_for("scenarios.index"))

    return render_template("pages/scenario_detail.html", scenario=scenario)


@bp.route("/generate", methods=["GET", "POST"])
@login_required
def generate():
    """Generate a new scenario."""
    if request.method == "POST":
        theme = request.form.get("theme", "")
        custom_prompt = request.form.get("custom_prompt", "").strip()

        if not theme and not custom_prompt:
            flash("Please select a theme or enter a custom prompt.", "error")
            return render_template(
                "pages/generate_scenario.html", themes=GENERATION_THEMES
            )

        # TODO: Integrate with scenario generator when available
        flash(
            "Scenario generation is not yet implemented. "
            "Scenarios will be generated using AI when the feature is complete.",
            "info",
        )
        return redirect(url_for("scenarios.index"))

    return render_template("pages/generate_scenario.html", themes=GENERATION_THEMES)
