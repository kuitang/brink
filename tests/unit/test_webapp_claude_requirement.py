"""Test that webapp requires working Claude CLI.

This test verifies the hard requirement: if Claude CLI doesn't work,
the webapp should crash on startup.
"""

import sys
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def cleanup_webapp_modules():
    """Clean up webapp modules before and after test."""
    # Save current state
    saved_modules = {k: v for k, v in sys.modules.items() if k.startswith("brinksmanship.webapp")}

    # Remove modules before test
    for mod in saved_modules:
        del sys.modules[mod]

    yield

    # Restore modules after test (important for other tests)
    for mod in list(sys.modules.keys()):
        if mod.startswith("brinksmanship.webapp"):
            del sys.modules[mod]
    sys.modules.update(saved_modules)


def test_create_app_crashes_if_claude_fails():
    """create_app should raise RuntimeError if Claude CLI fails."""
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
