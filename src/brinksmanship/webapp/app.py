"""Flask application factory."""

from flask import Flask

from .config import Config
from .extensions import db, login_manager


def create_app(config_class=Config):
    """Create and configure the Flask application."""
    app = Flask(
        __name__,
        template_folder="templates",
        static_folder="static",
    )
    app.config.from_object(config_class)

    # Ensure instance folder exists
    config_class.INSTANCE_PATH.mkdir(parents=True, exist_ok=True)

    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)

    # Register blueprints
    from .routes import auth, game, leaderboard, lobby, scenarios

    app.register_blueprint(auth.bp)
    app.register_blueprint(lobby.bp)
    app.register_blueprint(game.bp)
    app.register_blueprint(leaderboard.bp)
    app.register_blueprint(scenarios.bp)

    # Create database tables
    with app.app_context():
        db.create_all()

    return app


def main():
    """Entry point for `brinksmanship-web` command."""
    app = create_app()
    app.run(debug=True, port=5000)


if __name__ == "__main__":
    main()
