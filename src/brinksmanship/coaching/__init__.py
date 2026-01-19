"""Coaching module for Brinksmanship post-game analysis.

This module provides tools for analyzing completed games and helping players
improve their strategic play.

Classes:
    PostGameCoach: Main class for analyzing completed games.
    CoachingReport: Structured report containing analysis results.
    CriticalDecision: Analysis of a specific decision point.
    BayesianInference: Opponent type inference engine.
    OpponentType: Enum of possible opponent strategy types.
    OpponentTypeDistribution: Probability distribution over opponent types.
    ObservedAction: A single observed opponent action with context.

Functions:
    format_turn_history: Format game history for analysis prompts.
"""

from brinksmanship.coaching.bayesian_inference import (
    BayesianInference,
    ObservedAction,
    OpponentType,
    OpponentTypeDistribution,
)
from brinksmanship.coaching.post_game import (
    CoachingReport,
    CriticalDecision,
    PostGameCoach,
    format_turn_history,
)

__all__ = [
    "BayesianInference",
    "CoachingReport",
    "CriticalDecision",
    "ObservedAction",
    "OpponentType",
    "OpponentTypeDistribution",
    "PostGameCoach",
    "format_turn_history",
]
