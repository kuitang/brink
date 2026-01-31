#!/bin/bash
# Local CI script - runs all automated tests
# Usage: ./scripts/ci.sh

set -e

echo "========================================"
echo "BRINKSMANSHIP CI"
echo "========================================"
echo ""

# Ensure dependencies
echo "→ Syncing dependencies..."
uv sync --extra dev --extra webapp --quiet

# Run all tests
echo ""
echo "→ Running all tests..."
uv run pytest -v --tb=short

# Run balance simulation
echo ""
echo "→ Running balance simulation..."
uv run python scripts/balance_simulation.py --games 50 --seed 42

echo ""
echo "========================================"
echo "CI PASSED"
echo "========================================"
