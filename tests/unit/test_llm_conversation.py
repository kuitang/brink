"""Unit tests for LLM conversation history in HistoricalPersona.

Tests verify that:
1. The same ClaudeSDKClient instance is reused across turns
2. Conversation history accumulates across calls
3. Conversation turn count is tracked correctly
"""

import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from brinksmanship.models.actions import Action, ActionType
from brinksmanship.models.state import GameState
from brinksmanship.opponents.historical import HistoricalPersona


def _has_claude_cli():
    """Check if Claude Code CLI credentials are available."""
    # Check for OAuth token env var (server/CI deployment)
    if os.environ.get("CLAUDE_CODE_OAUTH_TOKEN"):
        return True
    # Check for credentials file (local development)
    credentials_path = Path.home() / ".claude" / ".credentials.json"
    return credentials_path.exists()


HAS_CLAUDE_CLI = _has_claude_cli()


class TestPersonaClientReuse:
    """Tests for ClaudeSDKClient reuse across turns."""

    def test_client_is_none_initially(self):
        """Test that client is None before first LLM call."""
        persona = HistoricalPersona("nixon", is_player_a=True)
        assert persona._client is None
        assert persona._conversation_turn_count == 0

    def test_conversation_turn_count_starts_at_zero(self):
        """Test that conversation turn count starts at zero."""
        persona = HistoricalPersona("bismarck")
        assert persona._conversation_turn_count == 0

    @pytest.mark.asyncio
    async def test_get_client_creates_client_on_first_call(self):
        """Test that _get_client creates a client on first call."""
        persona = HistoricalPersona("nixon", is_player_a=True)

        with patch("brinksmanship.opponents.historical.ClaudeSDKClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client

            client = persona._get_client()

            assert client is mock_client
            assert persona._client is mock_client
            mock_client_class.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_client_returns_same_instance(self):
        """Test that _get_client returns the same client instance on subsequent calls."""
        persona = HistoricalPersona("nixon", is_player_a=True)

        with patch("brinksmanship.opponents.historical.ClaudeSDKClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client

            client1 = persona._get_client()
            client2 = persona._get_client()
            client3 = persona._get_client()

            assert client1 is client2 is client3
            # Should only create client once
            mock_client_class.assert_called_once()


class TestConversationHistory:
    """Tests for conversation history accumulation."""

    @pytest.mark.asyncio
    async def test_conversation_turn_count_increments(self):
        """Exercise the actual SDK query API without credentials or network."""
        from claude_agent_sdk import AssistantMessage, TextBlock

        persona = HistoricalPersona("nixon", is_player_a=True)

        async def mock_query(**kwargs):
            assert kwargs["options"].allowed_tools == ["Read"]
            yield AssistantMessage(
                content=[TextBlock(text='{"selected_action": "De-escalate", "reasoning": "test"}')],
                model="test",
            )

        with patch("claude_agent_sdk.query", mock_query):
            for expected in range(1, 4):
                result = await persona._query_llm("test prompt", {"type": "object"})
                assert result["selected_action"] == "De-escalate"
                assert persona._conversation_turn_count == expected

    @pytest.mark.asyncio
    async def test_history_summary_includes_conversation_turns(self):
        """Test that history summary includes conversation turn count."""
        persona = HistoricalPersona("nixon", is_player_a=True)

        # Initially zero
        summary = persona.get_history_summary()
        assert "conversation_turns" in summary
        assert summary["conversation_turns"] == 0

        # Simulate some conversation turns
        persona._conversation_turn_count = 5

        # Add some action history too
        mock_action = Action(name="Test", action_type=ActionType.COOPERATIVE)
        mock_state = MagicMock(spec=GameState)
        persona.action_history.append((mock_action, mock_state))

        summary = persona.get_history_summary()
        assert summary["conversation_turns"] == 5
        assert summary["turns_played"] == 1


class TestClientCleanup:
    """Tests for proper client cleanup."""

    @pytest.mark.asyncio
    async def test_cleanup_closes_client(self):
        """Test that cleanup properly closes the client."""
        persona = HistoricalPersona("nixon", is_player_a=True)

        mock_client = MagicMock()
        mock_client.__aexit__ = AsyncMock()
        persona._client = mock_client
        persona._conversation_turn_count = 5

        await persona.cleanup()

        mock_client.__aexit__.assert_called_once_with(None, None, None)
        assert persona._client is None

    @pytest.mark.asyncio
    async def test_cleanup_handles_no_client(self):
        """Test that cleanup handles case where client was never created."""
        persona = HistoricalPersona("nixon", is_player_a=True)

        # Should not raise
        await persona.cleanup()

        assert persona._client is None


class TestPersonaCreation:
    """Tests for persona creation and initialization."""

    def test_fresh_persona_per_game(self):
        """Test that creating a new persona gives fresh state."""
        persona1 = HistoricalPersona("nixon", is_player_a=True)
        persona1._conversation_turn_count = 10

        # Create new persona - should have fresh state
        persona2 = HistoricalPersona("nixon", is_player_a=True)

        assert persona2._conversation_turn_count == 0
        assert persona2._client is None
        assert persona2.action_history == []

    def test_persona_attributes_set_correctly(self):
        """Test that persona attributes are set correctly."""
        persona = HistoricalPersona(
            "khrushchev",
            is_player_a=False,
            role_name="Soviet Premier",
            role_description="Leader of the USSR during the Cuban Missile Crisis",
        )

        assert persona.persona_name == "khrushchev"
        assert persona.is_player_a is False
        assert persona.role_name == "Soviet Premier"
        assert "USSR" in persona.role_description
        assert persona._client is None
        assert persona._conversation_turn_count == 0
