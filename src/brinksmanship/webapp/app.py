"""Flask application factory."""

import logging
import os

from flask import Flask, request

from .config import Config
from .extensions import db, login_manager

logger = logging.getLogger(__name__)

# Available themes
THEMES = ["default", "cold-war", "renaissance", "byzantine", "corporate"]


def seed_db():
    """Seed database with default test user if it doesn't exist.

    Also ensures all models are imported so their tables are created.
    """
    from .models.game_record import GameRecord, SettlementAttempt, TurnHistory  # noqa: F401
    from .models.user import User

    # Create default test user
    if not User.query.filter_by(username="test1234").first():
        user = User(username="test1234")
        user.set_password("test1234")
        db.session.add(user)
        db.session.commit()


async def check_claude_api_credentials():
    """Check if Claude API credentials are available and test the connection.

    The claude-agent-sdk spawns Claude Code CLI which uses OAuth authentication.
    Claude Code checks for credentials in this order:
    1. CLAUDE_CODE_OAUTH_TOKEN environment variable (for server/CI deployments)
    2. ~/.claude/.credentials.json file (from 'claude login' or 'claude setup-token')

    If neither is available, LLM-based opponents will fail. Deterministic opponents still work.

    Returns:
        bool: True if credentials are configured and working, False otherwise
    """
    import traceback
    from pathlib import Path

    from brinksmanship.llm import generate_text

    logger.info("=== Claude Agent SDK Power-On Self-Test ===")

    # Check for OAuth token env var (server/CI deployment)
    oauth_token = os.environ.get("CLAUDE_CODE_OAUTH_TOKEN")
    credentials_path = Path.home() / ".claude" / ".credentials.json"

    if oauth_token:
        masked = oauth_token[:20] + "..." if len(oauth_token) > 20 else "***"
        logger.info(f"CLAUDE_CODE_OAUTH_TOKEN is set: {masked}")
        logger.info(f"Token length: {len(oauth_token)} chars")
    elif credentials_path.exists():
        logger.info(f"Claude credentials file found at {credentials_path}")
    else:
        logger.warning(
            "Claude Code OAuth credentials not found! "
            "LLM-based opponents (historical personas, custom) will not work. "
            "Deterministic opponents (tit_for_tat, nash_calculator, etc.) will still work. "
            "For local dev: run 'claude login' or 'claude setup-token'. "
            "For Fly.io: set CLAUDE_CODE_OAUTH_TOKEN secret."
        )
        return False

    # Power-on test: use Claude Agent SDK to verify connection
    # The SDK spawns Claude Code CLI, so this fully exercises both layers
    logger.info("Calling Claude Agent SDK generate_text()...")
    logger.info("Prompt: 'Say hello in one word'")
    logger.info("max_turns: 1")

    try:
        response = await generate_text(prompt="Say hello in one word", max_turns=1)
        response_preview = response.strip()[:50]
        logger.info("Claude Agent SDK power-on test SUCCESS!")
        logger.info(f"Response: '{response_preview}'")
        logger.info("=== Power-On Self-Test PASSED ===")
        return True
    except Exception as e:
        logger.error("=== Power-On Self-Test FAILED ===")
        logger.error(f"Exception type: {type(e).__name__}")
        logger.error(f"Exception message: {e}")
        logger.error(f"Full traceback:\n{traceback.format_exc()}")
        raise


def create_app(config_class=Config):
    """Create and configure the Flask application."""
    import asyncio

    # Check API credentials at startup - FAIL HARD if not working
    # Use asyncio.run() since check_claude_api_credentials is async (uses SDK)
    has_claude = asyncio.run(check_claude_api_credentials())
    if not has_claude:
        raise RuntimeError(
            "Claude CLI is not working! Cannot start webapp without LLM support. "
            "Check Claude Code installation and CLAUDE_CODE_OAUTH_TOKEN secret."
        )

    app = Flask(
        __name__,
        template_folder="templates",
        static_folder="static",
    )
    app.config.from_object(config_class)

    # Claude is confirmed working
    app.config["CLAUDE_API_AVAILABLE"] = True

    # Ensure instance folder exists
    config_class.INSTANCE_PATH.mkdir(parents=True, exist_ok=True)

    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)

    # Register blueprints
    from .routes import auth, coaching, game, leaderboard, lobby, manual, scenarios

    app.register_blueprint(auth.bp)
    app.register_blueprint(lobby.bp)
    app.register_blueprint(game.bp)
    app.register_blueprint(coaching.bp)
    app.register_blueprint(leaderboard.bp)
    app.register_blueprint(manual.bp)
    app.register_blueprint(scenarios.bp)

    # Context processor to inject theme into all templates
    @app.context_processor
    def inject_theme():
        """Inject theme variable into all templates.

        Theme can be set via:
        1. Query parameter: ?theme=cold-war
        2. Cookie: theme=cold-war
        3. Default: 'default'
        """
        theme = request.args.get("theme")
        if not theme:
            theme = request.cookies.get("theme", "default")
        if theme not in THEMES:
            theme = "default"
        return {"theme": theme, "available_themes": THEMES}

    # Create database tables and seed
    with app.app_context():
        db.create_all()
        seed_db()

    return app


def main():
    """Entry point for `brinksmanship-web` command."""
    app = create_app()
    app.run(debug=True, host="0.0.0.0", port=5000)


if __name__ == "__main__":
    main()
