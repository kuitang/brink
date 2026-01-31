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


def check_claude_api_credentials():
    """Check if Claude API credentials are available and test the connection.

    The claude-agent-sdk spawns Claude Code CLI which uses OAuth authentication.
    Claude Code checks for credentials in this order:
    1. CLAUDE_CODE_OAUTH_TOKEN environment variable (for server/CI deployments)
    2. ~/.claude/.credentials.json file (from 'claude login' or 'claude setup-token')

    If neither is available, LLM-based opponents will fail. Deterministic opponents still work.

    Returns:
        bool: True if credentials are configured and working, False otherwise
    """
    from pathlib import Path

    # Check for OAuth token env var (server/CI deployment)
    oauth_token = os.environ.get("CLAUDE_CODE_OAUTH_TOKEN")
    credentials_path = Path.home() / ".claude" / ".credentials.json"

    if oauth_token:
        masked = oauth_token[:20] + "..." if len(oauth_token) > 20 else "***"
        logger.info(f"CLAUDE_CODE_OAUTH_TOKEN is set ({masked})")
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

    # Power-on test: verify Claude CLI actually works using subprocess
    # No exception handling - let it crash with full traceback if broken
    import subprocess

    logger.info("Testing Claude CLI with 'say hi' prompt...")
    result = subprocess.run(
        ["claude", "-p", "Say hello in one word", "--output-format", "text"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        logger.error(f"Claude CLI FAILED with exit code {result.returncode}")
        logger.error(f"stdout: {result.stdout}")
        logger.error(f"stderr: {result.stderr}")
        raise RuntimeError(f"Claude CLI failed: {result.stderr}")

    response = result.stdout.strip()[:50]
    logger.info(f"Claude CLI power-on test SUCCESS: '{response}...'")
    return True


def create_app(config_class=Config):
    """Create and configure the Flask application."""
    # Check API credentials at startup - FAIL HARD if not working
    has_claude = check_claude_api_credentials()
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
