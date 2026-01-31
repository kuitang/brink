"""LLM utilities using Claude Agent SDK.

This module provides helper functions for interacting with Claude via the
Agent SDK. All LLM calls in this project should use these utilities.

The Agent SDK shells out to Claude Code CLI, which means:
- Authentication uses your existing Claude Code auth (Max plan, API key, etc.)
- No separate API key configuration needed
- Full access to Claude's capabilities
"""

import logging
import re
from collections.abc import AsyncIterator
from typing import Any

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    TextBlock,
    query,
)

logger = logging.getLogger(__name__)


async def generate_text(
    prompt: str,
    system_prompt: str | None = None,
    max_turns: int = 1,
) -> str:
    """Generate text from Claude.

    Args:
        prompt: The user prompt to send to Claude.
        system_prompt: Optional system prompt to set context.
        max_turns: Maximum number of turns (default 1 for single response).

    Returns:
        The generated text response.

    Example:
        >>> response = await generate_text(
        ...     prompt="What is game theory?",
        ...     system_prompt="You are a game theory expert. Be concise."
        ... )
        >>> print(response)
    """
    options = ClaudeAgentOptions(max_turns=max_turns)
    if system_prompt is not None:
        options = ClaudeAgentOptions(
            system_prompt=system_prompt,
            max_turns=max_turns,
        )

    response_text = ""
    async for message in query(prompt=prompt, options=options):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    response_text += block.text
        elif isinstance(message, ResultMessage):
            if message.result:
                response_text = str(message.result)

    return response_text


async def generate_json(
    prompt: str,
    system_prompt: str | None = None,
    schema: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Generate structured JSON from Claude.

    When a schema is provided, uses Claude Agent SDK's structured output feature
    which guarantees valid JSON matching the schema. Without a schema, parses
    the text response as JSON.

    Args:
        prompt: The user prompt to send to Claude.
        system_prompt: Optional system prompt to set context.
        schema: Optional JSON schema for validation. When provided, uses
            structured outputs for guaranteed valid JSON.

    Returns:
        The parsed JSON response as a dictionary.

    Raises:
        ValueError: If the response cannot be parsed as JSON.

    Example:
        >>> data = await generate_json(
        ...     prompt="Generate a game scenario with title and description.",
        ...     system_prompt="Output valid JSON only, no markdown.",
        ...     schema={"type": "object", "properties": {"title": {"type": "string"}}}
        ... )
        >>> print(data["title"])
    """
    import json

    logger.debug(f"generate_json: prompt={len(prompt)} chars, schema={schema is not None}")

    # Build options
    # When using structured output (schema provided), Claude uses a StructuredOutput tool
    # Per docs, use higher max_turns (examples use 250) to allow agent to complete
    # The structured_output field will be populated in ResultMessage when done
    # Enable Read tool so LLM can read GAME_MANUAL.md for authoritative game rules
    options_kwargs: dict[str, Any] = {
        "max_turns": 10 if schema is not None else 3,  # 3 turns allows reading GAME_MANUAL then generating
        "allowed_tools": ["Read"],  # Enable file reading for GAME_MANUAL.md
    }
    if system_prompt is not None:
        options_kwargs["system_prompt"] = system_prompt
    if schema is not None:
        options_kwargs["output_format"] = {"type": "json_schema", "schema": schema}

    options = ClaudeAgentOptions(**options_kwargs)

    response_text = ""
    structured_output = None

    async for message in query(prompt=prompt, options=options):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    response_text += block.text
        elif isinstance(message, ResultMessage):
            # Structured output is populated in ResultMessage when schema is provided
            if hasattr(message, 'structured_output') and message.structured_output:
                structured_output = message.structured_output

            elif message.result:
                response_text = str(message.result)

    # If we got structured output, use it (guaranteed valid when schema provided)
    if structured_output is not None:
        logger.debug(f"Received structured_output: {list(structured_output.keys())}")
        return structured_output

    # No structured_output - fall back to text parsing
    if schema is not None:
        logger.warning("Schema provided but structured_output not returned - falling back to text parsing")

    text = response_text.strip()

    # Try to extract JSON from markdown code blocks anywhere in the response

    # Pattern 1: Find ```json ... ``` block
    json_block_match = re.search(r'```json\s*\n(.*?)\n```', text, re.DOTALL)
    if json_block_match:
        text = json_block_match.group(1).strip()
    else:
        # Pattern 2: Find ``` ... ``` block (generic code block)
        code_block_match = re.search(r'```\s*\n(.*?)\n```', text, re.DOTALL)
        if code_block_match:
            text = code_block_match.group(1).strip()
        else:
            # Pattern 3: Find JSON object directly (starts with { and ends with })
            json_obj_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', text, re.DOTALL)
            if json_obj_match:
                text = json_obj_match.group(0).strip()
            # Otherwise, keep text as-is and let json.loads fail with clear error

    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON: {e}\nRaw response: {response_text[:500]}")
        raise ValueError(f"Failed to parse JSON response: {e}\nResponse: {text}") from e


async def stream_text(
    prompt: str,
    system_prompt: str | None = None,
    max_turns: int = 1,
) -> AsyncIterator[str]:
    """Stream text from Claude token by token.

    Args:
        prompt: The user prompt to send to Claude.
        system_prompt: Optional system prompt to set context.
        max_turns: Maximum number of turns.

    Yields:
        Text chunks as they arrive.

    Example:
        >>> async for chunk in stream_text("Tell me a story"):
        ...     print(chunk, end="", flush=True)
    """
    options_kwargs: dict[str, Any] = {"max_turns": max_turns}
    if system_prompt is not None:
        options_kwargs["system_prompt"] = system_prompt

    options = ClaudeAgentOptions(**options_kwargs)

    async for message in query(prompt=prompt, options=options):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    yield block.text


async def agentic_query(
    prompt: str,
    system_prompt: str | None = None,
    allowed_tools: list[str] | None = None,
    max_turns: int = 10,
    cwd: str | None = None,
) -> str:
    """Run an agentic query with tool access.

    This enables the agent to autonomously use tools like Bash, Read, Write,
    WebSearch, etc. to complete tasks that require deterministic execution.

    Args:
        prompt: The task description for the agent.
        system_prompt: Optional system prompt to set context.
        allowed_tools: List of tools the agent can use.
            Common tools: "Read", "Write", "Edit", "Bash", "Glob", "Grep",
                         "WebSearch", "WebFetch", "Task"
        max_turns: Maximum number of agentic turns (default 10).
        cwd: Working directory for the agent (default: current directory).

    Returns:
        The final result text from the agent.

    Example:
        >>> result = await agentic_query(
        ...     prompt="Research Otto von Bismarck's negotiation style",
        ...     system_prompt="Extract strategic patterns for game AI.",
        ...     allowed_tools=["WebSearch", "WebFetch"],
        ... )

        >>> result = await agentic_query(
        ...     prompt="Run validation: python scripts/quick_validate.py test.json",
        ...     allowed_tools=["Bash", "Read"],
        ... )
    """
    options_kwargs: dict[str, Any] = {"max_turns": max_turns}
    if system_prompt is not None:
        options_kwargs["system_prompt"] = system_prompt
    if allowed_tools is not None:
        options_kwargs["allowed_tools"] = allowed_tools
    if cwd is not None:
        options_kwargs["cwd"] = cwd

    options = ClaudeAgentOptions(**options_kwargs)

    response_text = ""
    async for message in query(prompt=prompt, options=options):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    response_text += block.text
        elif isinstance(message, ResultMessage):
            if message.result:
                response_text = str(message.result)

    return response_text


async def generate_and_fix_json(
    initial_prompt: str,
    output_path: str,
    validation_fn: callable,
    system_prompt: str | None = None,
    max_iterations: int = 5,
    cwd: str | None = None,
) -> dict[str, Any]:
    """Generate JSON to a file and iteratively fix validation errors.

    Uses ClaudeSDKClient for conversation continuity. The agent:
    1. Generates JSON and writes to output_path
    2. External validation_fn is called
    3. If errors, agent uses Edit tool to fix them
    4. Repeat until valid or max_iterations reached

    Per Claude Agent SDK docs, we use ClaudeSDKClient for continuous
    conversation so the agent maintains context about what it generated.

    Args:
        initial_prompt: The generation prompt
        output_path: Absolute path to write the JSON file
        validation_fn: Callable that takes the file path and returns
            (is_valid: bool, errors: list[str])
        system_prompt: Optional system prompt
        max_iterations: Maximum fix iterations
        cwd: Working directory for file operations

    Returns:
        The final valid JSON as a dictionary

    Raises:
        ValueError: If validation fails after max_iterations
    """
    import json
    from pathlib import Path
    from claude_agent_sdk import ClaudeSDKClient

    # Ensure absolute path
    output_path = str(Path(output_path).resolve())
    cwd = cwd or str(Path(output_path).parent)

    logger.info(f"generate_and_fix_json: output={output_path}, max_iter={max_iterations}")

    options_kwargs: dict[str, Any] = {
        "max_turns": 50,  # Allow multiple tool uses per iteration
        "allowed_tools": ["Read", "Write", "Edit"],
        "permission_mode": "acceptEdits",
        "cwd": cwd,
        "setting_sources": ["project"],  # Load CLAUDE.md for GAME_MANUAL.md reference
    }
    if system_prompt is not None:
        options_kwargs["system_prompt"] = system_prompt

    options = ClaudeAgentOptions(**options_kwargs)

    async with ClaudeSDKClient(options=options) as client:
        # Initial generation - tell agent to write to specific file
        generation_prompt = f"""{initial_prompt}

IMPORTANT: Write the complete JSON output to this exact file path:
{output_path}

Use the Write tool to create the file with the full JSON content."""

        await client.query(generation_prompt)

        # Process response (agent will use Write tool)
        async for message in client.receive_response():
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        logger.debug(f"Agent: {block.text[:200]}...")

        # Iteration loop for fixes
        for iteration in range(max_iterations):
            # Validate externally
            is_valid, errors = validation_fn(output_path)

            if is_valid:
                logger.info(f"Validation passed after {iteration} fix iterations")
                # Read and return the valid JSON
                with open(output_path) as f:
                    return json.load(f)

            if iteration >= max_iterations - 1:
                break

            # Send error feedback for fixing
            error_list = "\n".join(f"- {e}" for e in errors[:10])  # Limit to 10 errors
            fix_prompt = f"""The JSON file at {output_path} has validation errors:

{error_list}

Please read the file using the Read tool, then use the Edit tool to fix these issues.
Make surgical edits to fix only the specific problems identified above.
Do NOT regenerate the entire file - edit the existing content."""

            logger.info(f"Fix iteration {iteration + 1}: {len(errors)} errors")

            await client.query(fix_prompt)

            # Process fix response
            async for message in client.receive_response():
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            logger.debug(f"Agent fix: {block.text[:200]}...")

    # Final validation
    is_valid, errors = validation_fn(output_path)
    if is_valid:
        with open(output_path) as f:
            return json.load(f)

    raise ValueError(f"Validation failed after {max_iterations} iterations: {errors}")


class LLMClient:
    """Client for LLM interactions with consistent configuration.

    This class provides a convenient way to make multiple LLM calls with
    shared configuration (like system prompts).

    Example:
        >>> client = LLMClient(
        ...     system_prompt="You are a game designer specializing in game theory."
        ... )
        >>> response = await client.generate("Design a payoff matrix")
        >>> scenario = await client.generate_json("Create a scenario as JSON")
    """

    def __init__(
        self,
        system_prompt: str | None = None,
        max_turns: int = 1,
        allowed_tools: list[str] | None = None,
    ):
        """Initialize the LLM client.

        Args:
            system_prompt: Default system prompt for all calls.
            max_turns: Default max turns for all calls.
            allowed_tools: Default tools for agentic queries.
        """
        self.system_prompt = system_prompt
        self.max_turns = max_turns
        self.allowed_tools = allowed_tools

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        max_turns: int | None = None,
    ) -> str:
        """Generate text response.

        Args:
            prompt: The user prompt.
            system_prompt: Override the default system prompt.
            max_turns: Override the default max turns.

        Returns:
            Generated text.
        """
        return await generate_text(
            prompt=prompt,
            system_prompt=system_prompt or self.system_prompt,
            max_turns=max_turns or self.max_turns,
        )

    async def generate_json(
        self,
        prompt: str,
        system_prompt: str | None = None,
        schema: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Generate structured JSON response.

        Args:
            prompt: The user prompt.
            system_prompt: Override the default system prompt.
            schema: JSON schema for validation.

        Returns:
            Parsed JSON as dictionary.
        """
        return await generate_json(
            prompt=prompt,
            system_prompt=system_prompt or self.system_prompt,
            schema=schema,
        )

    async def stream(
        self,
        prompt: str,
        system_prompt: str | None = None,
        max_turns: int | None = None,
    ) -> AsyncIterator[str]:
        """Stream text response.

        Args:
            prompt: The user prompt.
            system_prompt: Override the default system prompt.
            max_turns: Override the default max turns.

        Yields:
            Text chunks.
        """
        async for chunk in stream_text(
            prompt=prompt,
            system_prompt=system_prompt or self.system_prompt,
            max_turns=max_turns or self.max_turns,
        ):
            yield chunk

    async def agentic(
        self,
        prompt: str,
        system_prompt: str | None = None,
        allowed_tools: list[str] | None = None,
        max_turns: int | None = None,
        cwd: str | None = None,
    ) -> str:
        """Run an agentic query with tool access.

        Args:
            prompt: The task description.
            system_prompt: Override the default system prompt.
            allowed_tools: Override the default allowed tools.
            max_turns: Override the default max turns (default 10 for agentic).
            cwd: Working directory for the agent.

        Returns:
            The final result text from the agent.
        """
        return await agentic_query(
            prompt=prompt,
            system_prompt=system_prompt or self.system_prompt,
            allowed_tools=allowed_tools or self.allowed_tools,
            max_turns=max_turns or 10,  # Higher default for agentic
            cwd=cwd,
        )
