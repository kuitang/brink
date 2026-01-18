"""Test script to verify Claude Agent SDK installation and functionality."""

import asyncio
import sys


def test_imports():
    """Test that all SDK imports work correctly."""
    print("Testing imports...")
    print("-" * 40)

    try:
        from claude_agent_sdk import (
            query,
            ClaudeSDKClient,
            ClaudeAgentOptions,
            AssistantMessage,
            TextBlock,
        )

        print("  claude_agent_sdk.query: OK")
        print("  claude_agent_sdk.ClaudeSDKClient: OK")
        print("  claude_agent_sdk.ClaudeAgentOptions: OK")
        print("  claude_agent_sdk.AssistantMessage: OK")
        print("  claude_agent_sdk.TextBlock: OK")
    except ImportError as e:
        print(f"  claude_agent_sdk: FAIL ({e})")
        return False

    try:
        import textual

        print(f"  textual (v{textual.__version__}): OK")
    except ImportError as e:
        print(f"  textual: FAIL ({e})")
        return False

    try:
        import pydantic

        print(f"  pydantic (v{pydantic.__version__}): OK")
    except ImportError as e:
        print(f"  pydantic: FAIL ({e})")
        return False

    try:
        import numpy

        print(f"  numpy (v{numpy.__version__}): OK")
    except ImportError as e:
        print(f"  numpy: FAIL ({e})")
        return False

    print("-" * 40)
    return True


async def test_simple_query():
    """Test the Claude Agent SDK with a simple query."""
    from claude_agent_sdk import query, ClaudeAgentOptions, AssistantMessage, TextBlock

    print("\nTest 1: Simple query...")
    print("-" * 40)

    response_text = ""
    try:
        async for message in query(
            prompt="What is 2 + 2? Reply with just the number.",
            options=ClaudeAgentOptions(max_turns=1),
        ):
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        response_text += block.text
            elif hasattr(message, "result"):
                response_text = str(message.result)
    except Exception as e:
        print(f"Error: {e}")
        return False

    print(f"Response: {response_text}")
    success = "4" in response_text
    print(f"Result: {'PASS' if success else 'FAIL'}")
    print("-" * 40)
    return success


async def test_system_prompt():
    """Test the Claude Agent SDK with a custom system prompt."""
    from claude_agent_sdk import query, ClaudeAgentOptions, AssistantMessage, TextBlock

    print("\nTest 2: Custom system prompt...")
    print("-" * 40)

    response_text = ""
    try:
        async for message in query(
            prompt="What are you?",
            options=ClaudeAgentOptions(
                system_prompt="You are a helpful pirate. Always respond like a pirate.",
                max_turns=1,
            ),
        ):
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        response_text += block.text
            elif hasattr(message, "result"):
                response_text = str(message.result)
    except Exception as e:
        print(f"Error: {e}")
        return False

    print(f"Response: {response_text[:200]}...")
    # Check for pirate-like language
    pirate_words = ["arr", "matey", "ahoy", "sea", "ship", "captain", "ye", "aye"]
    success = any(word in response_text.lower() for word in pirate_words)
    print(f"Result: {'PASS' if success else 'FAIL'} (looking for pirate language)")
    print("-" * 40)
    return success


async def test_json_response():
    """Test getting structured JSON response."""
    from claude_agent_sdk import query, ClaudeAgentOptions, AssistantMessage, TextBlock
    import json

    print("\nTest 3: JSON structured output...")
    print("-" * 40)

    response_text = ""
    try:
        async for message in query(
            prompt="List 3 primary colors as a JSON array. Only output the JSON, nothing else.",
            options=ClaudeAgentOptions(max_turns=1),
        ):
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        response_text += block.text
            elif hasattr(message, "result"):
                response_text = str(message.result)
    except Exception as e:
        print(f"Error: {e}")
        return False

    print(f"Response: {response_text}")

    # Try to parse as JSON
    try:
        # Extract JSON from response (might have markdown code blocks)
        json_str = response_text.strip()
        if json_str.startswith("```"):
            json_str = json_str.split("```")[1]
            if json_str.startswith("json"):
                json_str = json_str[4:]
        data = json.loads(json_str.strip())
        success = isinstance(data, list) and len(data) >= 3
        print(f"Parsed JSON: {data}")
    except json.JSONDecodeError:
        success = False
        print("Failed to parse JSON")

    print(f"Result: {'PASS' if success else 'FAIL'}")
    print("-" * 40)
    return success


async def main():
    print("=" * 50)
    print("Claude Agent SDK Test Suite")
    print("=" * 50)
    print("Using bundled Claude Code CLI for all API calls")
    print("Auth: Uses your existing Claude Code authentication")
    print("=" * 50)

    # Test 1: Imports
    imports_ok = test_imports()
    print(f"\nImports: {'PASS' if imports_ok else 'FAIL'}")

    if not imports_ok:
        print("Import tests failed. Cannot continue.")
        return 1

    # Run live tests
    print("\n" + "=" * 50)
    print("Running live API tests...")
    print("=" * 50)

    results = []

    # Test simple query
    results.append(("Simple query", await test_simple_query()))

    # Test system prompt
    results.append(("System prompt", await test_system_prompt()))

    # Test JSON response
    results.append(("JSON output", await test_json_response()))

    # Summary
    print("\n" + "=" * 50)
    print("SUMMARY")
    print("=" * 50)
    all_passed = True
    for name, passed in results:
        status = "PASS" if passed else "FAIL"
        print(f"  {name}: {status}")
        if not passed:
            all_passed = False

    print("=" * 50)
    if all_passed:
        print("All tests passed!")
        return 0
    else:
        print("Some tests failed.")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
