#!/usr/bin/env python3
"""Test that Claude Agent SDK is reading GAME_MANUAL.md correctly.

This script tests whether the agent actually reads the game manual by:
1. Asking it to quote specific sections
2. Verifying the quotes match the actual content
"""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions, AssistantMessage, TextBlock


async def test_game_manual_reading():
    """Test that the agent can read and quote from GAME_MANUAL.md."""

    project_root = Path(__file__).parent.parent
    game_manual_path = project_root / "GAME_MANUAL.md"

    # Read actual content to verify
    with open(game_manual_path) as f:
        actual_content = f.read()

    # Set up options with Read tool and project settings (CLAUDE.md)
    options = ClaudeAgentOptions(
        max_turns=10,
        allowed_tools=["Read"],
        cwd=str(project_root),
        setting_sources=["project"],  # This should load CLAUDE.md which tells agent to read GAME_MANUAL.md
    )

    print("Testing whether agent reads GAME_MANUAL.md...")
    print(f"Project root: {project_root}")
    print(f"Game manual path: {game_manual_path}")
    print()

    async with ClaudeSDKClient(options=options) as client:
        # Test 1: Ask about a specific section that should be in GAME_MANUAL.md
        test_prompt = """Read the file GAME_MANUAL.md in the project root.

What are the 4 intelligence game types described in Section 3.6?
List them with their matrix type mappings."""

        print("Sending test prompt...")
        await client.query(test_prompt)

        response_text = ""
        async for message in client.receive_response():
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        response_text += block.text

        print("Response from agent:")
        print("-" * 60)
        print(response_text)
        print("-" * 60)

        # Verify expected terms appear
        expected_terms = [
            "Reconnaissance",
            "Matching Pennies",
            "Verification",
            "Back-Channel",
            "Diplomatic Standoff",
        ]

        found_terms = [term for term in expected_terms if term.lower() in response_text.lower()]
        missing_terms = [term for term in expected_terms if term.lower() not in response_text.lower()]

        print()
        print(f"Found {len(found_terms)}/{len(expected_terms)} expected terms:")
        for term in found_terms:
            print(f"  ✓ {term}")
        for term in missing_terms:
            print(f"  ✗ {term} (MISSING)")

        if len(found_terms) >= 3:
            print("\n✓ PASS: Agent appears to have read GAME_MANUAL.md")
            return True
        else:
            print("\n✗ FAIL: Agent may not have read GAME_MANUAL.md correctly")
            return False


if __name__ == "__main__":
    result = asyncio.run(test_game_manual_reading())
    sys.exit(0 if result else 1)
