"""Opponent implementations for Brinksmanship.

This module provides different opponent types that players can face:

1. Deterministic opponents - Rule-based strategies (Nash, TitForTat, etc.)
2. Historical personas - LLM-driven opponents embodying historical figures
3. Custom personas - User-defined or generated personas

All opponents implement the Opponent base class interface.
"""

from brinksmanship.opponents.base import (
    Opponent,
    OpponentType,
    SettlementProposal,
    SettlementResponse,
    get_opponent_by_type,
    list_opponent_types,
)
from brinksmanship.opponents.deterministic import (
    DeterministicOpponent,
    Erratic,
    GrimTrigger,
    NashCalculator,
    Opportunist,
    SecuritySeeker,
    TitForTat,
)
from brinksmanship.opponents.historical import (
    HistoricalPersona,
    PERSONA_DISPLAY_NAMES,
    PERSONA_PROMPTS,
)
from brinksmanship.opponents.persona_generator import (
    GeneratedPersona,
    PersonaDefinition,
    PersonaGenerationResult,
    PersonaGenerator,
    create_opponent_from_persona,
    generate_new_persona,
)

__all__ = [
    # Base classes and types
    "Opponent",
    "OpponentType",
    "SettlementProposal",
    "SettlementResponse",
    # Factory functions
    "get_opponent_by_type",
    "list_opponent_types",
    # Deterministic opponents
    "DeterministicOpponent",
    "NashCalculator",
    "SecuritySeeker",
    "Opportunist",
    "Erratic",
    "TitForTat",
    "GrimTrigger",
    # Historical personas
    "HistoricalPersona",
    "PERSONA_DISPLAY_NAMES",
    "PERSONA_PROMPTS",
    # Persona generation
    "PersonaDefinition",
    "PersonaGenerationResult",
    "PersonaGenerator",
    "GeneratedPersona",
    "create_opponent_from_persona",
    "generate_new_persona",
]
