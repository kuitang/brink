"""Brinksmanship CLI module.

Provides a Textual-based terminal interface for playing Brinksmanship.

Usage:
    uv run brinksmanship

Or directly:
    python -m brinksmanship.cli.app
"""

from brinksmanship.cli.app import BrinksmanshipApp, main

__all__ = ["BrinksmanshipApp", "main"]
