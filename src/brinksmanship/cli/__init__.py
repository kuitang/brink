"""Brinksmanship CLI module.

Provides a simple terminal interface for playing Brinksmanship.

Usage:
    uv run brinksmanship

Or directly:
    python -m brinksmanship.cli.app
"""

from brinksmanship.cli.app import BrinksmanshipCLI, main

__all__ = ["BrinksmanshipCLI", "main"]
