# Brinksmanship

A game-theoretic strategy simulation exploring nuclear brinkmanship, deterrence theory, and coordination games. Built with Python, htmx, and Claude AI.

## What is this?

Play through diplomatic crises using real game theory. Each turn presents a strategic dilemma—Prisoner's Dilemma, Chicken, Stag Hunt—where your outcome depends on both your choice and your opponent's. Manage risk, build (or destroy) trust, and decide when to negotiate.

AI opponents use Claude to roleplay distinct personas: cautious diplomats, aggressive hawks, or unpredictable wildcards. Post-game coaching explains what happened in game-theoretic terms.

**[Read the full game manual →](GAME_MANUAL.md)**

## Quick Start

```bash
# Install uv if you don't have it
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone and install
git clone https://github.com/kuitang/brink.git
cd brink
uv sync --extra webapp

# Generate the manual
uv run python scripts/generate_manual.py

# Run the webapp
uv run brinksmanship-web

# Open http://localhost:5000
```

## Development

```bash
# Install dev dependencies
uv sync --all-extras

# Run the local CI script (same checks as GitHub Actions)
bash scripts/ci.sh

# Run tests only
uv run pytest

# Run linting only
uv run ruff check .
```

## Key Features

- **14 game types** from game theory literature (Prisoner's Dilemma, Chicken, Stag Hunt, Deadlock, and more)
- **10 scenarios** with historically-themed crises (Cold War, Renaissance, modern geopolitics)
- **LLM-powered opponents** with distinct strategic personalities
- **Post-game coaching** analyzes your decisions in game-theoretic terms
- **Cooperation surplus** mechanic rewards sustained mutual cooperation

## License

AGPL-3.0 - See [LICENSE](LICENSE) for details.
