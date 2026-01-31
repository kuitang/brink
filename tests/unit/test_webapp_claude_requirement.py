"""Test that webapp requires working Claude CLI."""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestClaudeRequirement:
    """Tests that webapp fails to start without working Claude."""

    def test_webapp_crashes_if_claude_cli_missing(self):
        """Webapp should crash if claude command is not found."""
        # Need to patch subprocess.run inside the app module
        with patch("brinksmanship.webapp.app.subprocess") as mock_subprocess:
            mock_subprocess.run.side_effect = FileNotFoundError("claude not found")

            # Need to reimport to get fresh function
            import importlib

            import brinksmanship.webapp.app as app_module

            importlib.reload(app_module)

            # Mock credentials exist so it tries to run claude
            with patch.dict(os.environ, {"CLAUDE_CODE_OAUTH_TOKEN": "test-token"}):
                with pytest.raises(FileNotFoundError):
                    app_module.check_claude_api_credentials()

    def test_webapp_crashes_if_claude_cli_fails(self):
        """Webapp should crash if claude command returns non-zero."""
        with patch("brinksmanship.webapp.app.subprocess") as mock_subprocess:
            mock_result = MagicMock()
            mock_result.returncode = 1
            mock_result.stdout = ""
            mock_result.stderr = "authentication failed"
            mock_subprocess.run.return_value = mock_result

            import importlib

            import brinksmanship.webapp.app as app_module

            importlib.reload(app_module)

            with patch.dict(os.environ, {"CLAUDE_CODE_OAUTH_TOKEN": "test-token"}):
                with pytest.raises(RuntimeError, match="Claude CLI failed"):
                    app_module.check_claude_api_credentials()

    def test_webapp_returns_false_if_no_credentials(self):
        """Webapp returns False if no OAuth token and no credentials file."""
        # Clear environment and mock credentials file doesn't exist
        env_without_token = {k: v for k, v in os.environ.items() if k != "CLAUDE_CODE_OAUTH_TOKEN"}
        with patch.dict(os.environ, env_without_token, clear=True):
            with patch.object(Path, "exists", return_value=False):
                import importlib

                import brinksmanship.webapp.app as app_module

                importlib.reload(app_module)

                result = app_module.check_claude_api_credentials()
                assert result is False

    def test_create_app_crashes_without_claude(self):
        """create_app should raise RuntimeError if Claude check fails."""
        with patch("brinksmanship.webapp.app.check_claude_api_credentials", return_value=False):
            import importlib

            import brinksmanship.webapp.app as app_module

            importlib.reload(app_module)

            with pytest.raises(RuntimeError, match="Claude CLI is not working"):
                app_module.create_app()
