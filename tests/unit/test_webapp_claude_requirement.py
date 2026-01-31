"""Test that webapp requires working Claude CLI.

This test verifies the hard requirement: if Claude CLI doesn't work,
the webapp should crash on startup.
"""

import subprocess
from unittest.mock import MagicMock, patch

import pytest


def test_create_app_crashes_if_claude_fails():
    """create_app should raise RuntimeError if Claude CLI fails."""
    import sys

    # Remove cached webapp modules
    mods_to_remove = [k for k in sys.modules if k.startswith("brinksmanship.webapp")]
    for mod in mods_to_remove:
        del sys.modules[mod]

    # Mock subprocess.run to simulate Claude CLI failure
    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_result.stdout = ""
    mock_result.stderr = "authentication failed"

    with patch.dict("os.environ", {"CLAUDE_CODE_OAUTH_TOKEN": "fake-token"}):
        with patch("subprocess.run", return_value=mock_result):
            from brinksmanship.webapp.app import create_app

            with pytest.raises(RuntimeError, match="Claude CLI"):
                create_app()
