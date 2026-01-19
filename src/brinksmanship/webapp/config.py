"""Flask configuration."""

import os
from pathlib import Path


class Config:
    """Base configuration."""

    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-key-change-in-prod")

    # Database - instance folder is at project root
    PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
    INSTANCE_PATH = PROJECT_ROOT / "instance"
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", f"sqlite:///{INSTANCE_PATH}/brinksmanship.db"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Scenarios
    SCENARIOS_PATH = PROJECT_ROOT / "scenarios"
    SCENARIO_STORAGE = "file"  # 'file' or 'sqlite'

    # LLM
    LLM_TIMEOUT = 60  # seconds to wait for persona responses


class TestConfig(Config):
    """Testing configuration."""

    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False
