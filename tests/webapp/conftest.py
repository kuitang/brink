"""Pytest fixtures for webapp tests."""

from unittest.mock import AsyncMock, patch

import pytest

from brinksmanship.webapp.config import TestConfig
from brinksmanship.webapp.extensions import db
from brinksmanship.webapp.models import User


@pytest.fixture
def app():
    """Create test application with mocked Claude check."""
    # Mock Claude check so webapp tests work without Claude CLI
    # The function is async, so use AsyncMock that returns True
    mock_check = AsyncMock(return_value=True)
    with patch("brinksmanship.webapp.app.check_claude_api_credentials", mock_check):
        from brinksmanship.webapp import create_app

        app = create_app(TestConfig)
        with app.app_context():
            db.create_all()
            yield app
            db.drop_all()


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()


@pytest.fixture
def runner(app):
    """Create test CLI runner."""
    return app.test_cli_runner()


@pytest.fixture
def user(app):
    """Create a test user and return user_id."""
    with app.app_context():
        user = User(username="testuser")
        user.set_password("testpassword123")
        db.session.add(user)
        db.session.commit()
        # Return just the ID to avoid DetachedInstanceError
        user_id = user.id
    return user_id


@pytest.fixture
def auth_client(client, user):
    """Create authenticated test client."""
    # user is now a user_id, login works the same
    client.post(
        "/auth/login",
        data={"username": "testuser", "password": "testpassword123"},
    )
    return client
