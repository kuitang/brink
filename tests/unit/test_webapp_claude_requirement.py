"""Test that webapp requires working Claude CLI."""

from unittest.mock import patch

import pytest


class TestClaudeRequirement:
    """Tests that webapp fails to start without working Claude."""

    def test_create_app_crashes_without_claude(self):
        """create_app should raise RuntimeError if Claude check fails."""
        with patch("brinksmanship.webapp.app.check_claude_api_credentials", return_value=False):
            # Need fresh import after patching
            import importlib

            import brinksmanship.webapp.app as app_module

            importlib.reload(app_module)

            with pytest.raises(RuntimeError, match="Claude CLI is not working"):
                app_module.create_app()

    def test_create_app_succeeds_with_claude(self):
        """create_app should succeed if Claude check passes."""
        with patch("brinksmanship.webapp.app.check_claude_api_credentials", return_value=True):
            import importlib

            import brinksmanship.webapp.app as app_module

            importlib.reload(app_module)

            # Should not raise
            app = app_module.create_app()
            assert app is not None
            assert app.config["CLAUDE_API_AVAILABLE"] is True
