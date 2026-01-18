# Brinksmanship

A game-theoretic strategy simulation exploring nuclear brinkmanship, deterrence theory, and coordination games. Powered by Claude AI.

## Overview

Brinksmanship is an interactive strategy game where players navigate complex diplomatic and strategic scenarios using principles from game theory, including:

- **Coordination games** (Schelling's focal points)
- **Deterrence theory** (credible threats, commitment devices)
- **Repeated games** (reputation, trust-building)
- **Information asymmetry** (signaling, screening)

## Installation

```bash
# Using uv (recommended)
uv sync

# Or using pip
pip install -e .
```

## Development

```bash
uv sync --extra dev
```

## Usage

```bash
# Run the game
uv run brinksmanship

# Run tests
uv run pytest

# Run the SDK test suite
uv run python test_claude_sdk.py
```

## Architecture

The game uses the Claude Agent SDK for all LLM interactions:

- **No API key required** if you have Claude Code authenticated (Max plan, etc.)
- Shells out to the bundled Claude Code CLI
- Full access to Claude's reasoning capabilities

## Project Structure

```
brinksmanship/
├── src/brinksmanship/
│   ├── models/       # Game state, actions, matrices
│   ├── engine/       # Core game logic
│   ├── generation/   # Scenario generation via LLM
│   ├── opponents/    # AI opponents (deterministic + LLM personas)
│   ├── testing/      # Automated playtesting
│   ├── coaching/     # Post-game analysis
│   ├── cli/          # Textual CLI interface
│   ├── llm.py        # LLM utilities
│   └── prompts.py    # All LLM prompts
├── scenarios/        # Generated scenario files
├── tests/            # Test suite
└── scripts/          # Utility scripts
```

## License

MIT
