"""Test that webapp requires working Claude CLI."""

from unittest.mock import patch

import pytest


class TestClaudeRequirement:
    """Tests that webapp fails to start without working Claude."""

    def test_webapp_crashes_if_claude_cli_missing(self):
        """Webapp should crash if claude command is not found."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError("claude not found")

            from brinksmanship.webapp.app import check_claude_api_credentials

            with pytest.raises(FileNotFoundError):
                check_claude_api_credentials()

    def test_webapp_crashes_if_claude_cli_fails(self):
        """Webapp should crash if claude command returns non-zero."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 1
            mock_run.return_value.stdout = ""
            mock_run.return_value.stderr = "authentication failed"

            from brinksmanship.webapp.app import check_claude_api_credentials

            with pytest.raises(RuntimeError, match="Claude CLI failed"):
                check_claude_api_credentials()

    def test_webapp_crashes_if_no_credentials(self):
        """Webapp should crash if no OAuth token and no credentials file."""
        import os
        from pathlib import Path

        with patch.dict(os.environ, {}, clear=True):
            with patch.object(Path, "exists", return_value=False):
                from brinksmanship.webapp.app import check_claude_api_credentials

                # Should return False (no credentials), which causes create_app to crash
                result = check_claude_api_credentials()
                assert result is False

    def test_create_app_crashes_without_claude(self):
        """create_app should raise RuntimeError if Claude check fails."""
        with patch("brinksmanship.webapp.app.check_claude_api_credentials", return_value=False):
            from brinksmanship.webapp.app import create_app

            with pytest.raises(RuntimeError, match="Claude CLI is not working"):
                create_app()
