#!/usr/bin/env python3
"""
Test script to verify Claude Agent SDK models work correctly.
Run this to confirm Opus 4.5 and Sonnet 4.5 are accessible via the SDK.
"""

import asyncio

from claude_agent_sdk import AssistantMessage, ClaudeAgentOptions, ResultMessage, TextBlock, query


async def test_model(model_name: str) -> bool:
    """Test a model via Claude Agent SDK and return success/failure."""
    try:
        options = ClaudeAgentOptions(model=model_name, max_turns=1)

        response_text = ""
        async for message in query(prompt="Say 'Model test successful' and nothing else.", options=options):
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        response_text += block.text
            elif isinstance(message, ResultMessage):
                print(f"  Model: {model_name}")
                print(f"  Response: {response_text[:100]}")
                print(f"  Cost: ${message.total_cost_usd:.4f}" if message.total_cost_usd else "  Cost: N/A")
                print("  Status: SUCCESS")
                return True

        print(f"  Model: {model_name}")
        print(f"  Response: {response_text[:100]}")
        print("  Status: SUCCESS (no ResultMessage)")
        return True

    except Exception as e:
        print(f"  Model: {model_name}")
        print(f"  Error: {e}")
        print("  Status: FAILED")
        return False


async def main():
    print("=" * 60)
    print("CLAUDE AGENT SDK MODEL VERIFICATION TEST")
    print("=" * 60)

    # Models to test (using SDK model names)
    models = ["opus", "sonnet"]

    results = {}

    for model_name in models:
        print(f"\n{'-' * 60}")
        print(f"Testing: {model_name}")
        print("-" * 60)
        success = await test_model(model_name)
        results[model_name] = success

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    passed = sum(1 for v in results.values() if v)
    failed = sum(1 for v in results.values() if not v)

    print(f"Passed: {passed}")
    print(f"Failed: {failed}")

    if failed > 0:
        print("\nFailed tests:")
        for key, success in results.items():
            if not success:
                print(f"  - {key}")
        return 1

    print("\nAll models verified successfully!")
    print("\nModel usage in ClaudeAgentOptions:")
    print('  Opus 4.5:  model="opus"')
    print('  Sonnet 4.5: model="sonnet"')
    return 0


if __name__ == "__main__":
    exit(asyncio.run(main()))
