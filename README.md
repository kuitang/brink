# Brinksmanship

A game-theoretic strategy simulation exploring nuclear brinkmanship, deterrence theory, and coordination games. Built with Python, htmx, and Claude AI.

## What is this?

Play through diplomatic crises using real game theory. Each turn presents a strategic dilemma—Prisoner's Dilemma, Chicken, Stag Hunt—where your outcome depends on both your choice and your opponent's. Manage risk, build (or destroy) trust, and decide when to negotiate.

The AI opponent uses Claude to roleplay distinct personas: a cautious diplomat, an aggressive hawk, or an unpredictable wild card. Post-game coaching explains what happened in game-theoretic terms.

**[Read the full game manual →](GAME_MANUAL.md)**

## Quick Start

```bash
# Install dependencies (requires uv)
uv sync

# Run the webapp
uv run python -m brinksmanship.webapp.app

# Run tests
uv run pytest
```

## Key Features

- **24 game types** from game theory literature (Prisoner's Dilemma, Chicken, Stag Hunt, etc.)
- **LLM-powered opponents** with distinct strategic personalities
- **Scenario generation** creates historically-themed crises
- **Post-game coaching** analyzes your decisions

## Project Structure

```
src/brinksmanship/
├── engine/       # Core game logic and resolution
├── models/       # Game state, actions, payoff matrices
├── generation/   # LLM scenario generation
├── opponents/    # AI opponent strategies
├── coaching/     # Post-game analysis
├── webapp/       # Flask + htmx web interface
└── testing/      # Playtesting framework
```

## License

MIT
