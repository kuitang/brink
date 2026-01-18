"""LLM utilities using Claude Agent SDK.

This module provides helper functions for interacting with Claude via the
Agent SDK. All LLM calls in this project should use these utilities.

The Agent SDK shells out to Claude Code CLI, which means:
- Authentication uses your existing Claude Code auth (Max plan, API key, etc.)
- No separate API key configuration needed
- Full access to Claude's capabilities
"""

from collections.abc import AsyncIterator
from typing import Any

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    TextBlock,
    query,
)


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

    Args:
        prompt: The user prompt to send to Claude.
        system_prompt: Optional system prompt to set context.
        schema: Optional JSON schema for validation.

    Returns:
        The parsed JSON response as a dictionary.

    Raises:
        ValueError: If the response cannot be parsed as JSON.

    Example:
        >>> data = await generate_json(
        ...     prompt="Generate a game scenario with title and description.",
        ...     system_prompt="Output valid JSON only, no markdown."
        ... )
        >>> print(data["title"])
    """
    import json

    # Build options
    options_kwargs: dict[str, Any] = {"max_turns": 1}
    if system_prompt is not None:
        options_kwargs["system_prompt"] = system_prompt
    if schema is not None:
        options_kwargs["output_format"] = {"type": "json_schema", "schema": schema}

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

    # Clean up response (remove markdown code blocks if present)
    text = response_text.strip()
    if text.startswith("```"):
        # Extract content between code fences
        lines = text.split("\n")
        # Skip first line (```json or ```) and last line (```)
        if lines[-1].strip() == "```":
            lines = lines[1:-1]
        else:
            lines = lines[1:]
        text = "\n".join(lines)

    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
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
