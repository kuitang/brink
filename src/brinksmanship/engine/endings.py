"""Game ending conditions for Brinksmanship.

This module implements all game ending conditions as specified in GAME_MANUAL.md.

Ending Types:
- MUTUAL_DESTRUCTION: Risk = 10, both get 0 VP (worst possible outcome)
- POSITION_LOSS_A/B: Position = 0, loser gets 10 VP, winner gets 90 VP + captured surplus
- RESOURCE_LOSS_A/B: Resources = 0, loser gets 15 VP, winner gets 85 VP + captured surplus
- CRISIS_TERMINATION: Probabilistic ending when Risk > 7 and Turn >= 10
- MAX_TURNS: Natural ending when turn reaches max_turns
- SETTLEMENT: Negotiated ending (handled separately by settlement system)

Deterministic Endings (checked in order):
1. Risk = 10 -> Mutual Destruction (0 VP for both, all surplus lost)
2. Position = 0 -> Position Loss
3. Resources = 0 -> Resource Loss

Probabilistic Endings (checked after deterministic):
1. Crisis Termination (Turn >= 10, Risk > 7)
2. Max Turns (turn >= max_turns)

Crisis Termination Formula (from GAME_MANUAL.md):
    P(Termination) = (Risk_Level - 7) * 0.08
    - Risk 8: 8%
    - Risk 9: 16%
    - Risk 10: 100% (handled by deterministic check)
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from enum import Enum, auto

from brinksmanship.engine.variance import final_resolution
from brinksmanship.models.state import GameState


class EndingType(Enum):
    """Types of game endings."""

    # Deterministic endings
    MUTUAL_DESTRUCTION = auto()  # Risk = 10
    POSITION_LOSS_A = auto()     # Player A Position = 0
    POSITION_LOSS_B = auto()     # Player B Position = 0
    RESOURCE_LOSS_A = auto()     # Player A Resources = 0
    RESOURCE_LOSS_B = auto()     # Player B Resources = 0

    # Probabilistic endings
    CRISIS_TERMINATION = auto()  # Random termination when Risk > 7, Turn >= 10
    MAX_TURNS = auto()           # Natural ending at max_turns

    # Negotiated ending
    SETTLEMENT = auto()          # Players agreed on settlement


@dataclass(frozen=True)
class GameEnding:
    """Result of a game ending.

    Attributes:
        ending_type: The type of ending that occurred
        vp_a: Victory points for player A
        vp_b: Victory points for player B
        description: Human-readable description of the ending
    """
    ending_type: EndingType
    vp_a: float
    vp_b: float
    description: str


def check_mutual_destruction(state: GameState) -> GameEnding | None:
    """Check if Risk = 10 (Mutual Destruction).

    From GAME_MANUAL.md Section 4.5:
        Risk = 10: Mutual Destruction
        - Both players receive **0 VP** (worst possible outcome)
        - All surplus is lost
        - Game ends immediately

    Args:
        state: Current game state

    Returns:
        GameEnding if Risk = 10, None otherwise
    """
    if state.risk_level >= 10.0:
        return GameEnding(
            ending_type=EndingType.MUTUAL_DESTRUCTION,
            vp_a=0.0,
            vp_b=0.0,
            description="The crisis has spiraled out of control. Mutual destruction ensues. Both players receive 0 VP - all value is lost.",
        )
    return None


def check_position_loss(state: GameState) -> GameEnding | None:
    """Check if either player's Position = 0.

    From GAME_MANUAL.md Section 4.5:
        Position = 0: Eliminated player receives 10 VP
        Surviving player receives 90 VP + all their captured surplus
        Remaining cooperation surplus is lost

    Args:
        state: Current game state

    Returns:
        GameEnding if either position is 0, None otherwise
    """
    if state.position_a <= 0.0:
        # Player A eliminated, Player B wins
        # Winner gets 90 VP + their captured surplus
        vp_b = 90.0 + state.surplus_captured_b
        return GameEnding(
            ending_type=EndingType.POSITION_LOSS_A,
            vp_a=10.0,
            vp_b=vp_b,
            description=f"Player A's position has collapsed. Player A receives 10 VP, Player B receives {vp_b:.1f} VP (90 + {state.surplus_captured_b:.1f} captured surplus).",
        )
    if state.position_b <= 0.0:
        # Player B eliminated, Player A wins
        # Winner gets 90 VP + their captured surplus
        vp_a = 90.0 + state.surplus_captured_a
        return GameEnding(
            ending_type=EndingType.POSITION_LOSS_B,
            vp_a=vp_a,
            vp_b=10.0,
            description=f"Player B's position has collapsed. Player A receives {vp_a:.1f} VP (90 + {state.surplus_captured_a:.1f} captured surplus), Player B receives 10 VP.",
        )
    return None


def check_resource_loss(state: GameState) -> GameEnding | None:
    """Check if either player's Resources = 0.

    From GAME_MANUAL.md:
        Resources = 0: That player loses, 15 VP. Opponent: 85 VP + captured surplus
        Remaining cooperation surplus is lost

    Args:
        state: Current game state

    Returns:
        GameEnding if either resources is 0, None otherwise
    """
    if state.resources_a <= 0.0:
        # Player A loses, Player B wins
        vp_b = 85.0 + state.surplus_captured_b
        return GameEnding(
            ending_type=EndingType.RESOURCE_LOSS_A,
            vp_a=15.0,
            vp_b=vp_b,
            description=f"Player A has exhausted all resources. Player A receives 15 VP, Player B receives {vp_b:.1f} VP (85 + {state.surplus_captured_b:.1f} captured surplus).",
        )
    if state.resources_b <= 0.0:
        # Player B loses, Player A wins
        vp_a = 85.0 + state.surplus_captured_a
        return GameEnding(
            ending_type=EndingType.RESOURCE_LOSS_B,
            vp_a=vp_a,
            vp_b=15.0,
            description=f"Player B has exhausted all resources. Player A receives {vp_a:.1f} VP (85 + {state.surplus_captured_a:.1f} captured surplus), Player B receives 15 VP.",
        )
    return None


def get_crisis_termination_probability(risk_level: float, turn: int) -> float:
    """Calculate the probability of crisis termination.

    From GAME_MANUAL.md:
        Only checked for Turn >= 10 and Risk > 7
        P(Termination) = (Risk_Level - 7) * 0.08
        - Risk 7 or below: 0%
        - Risk 8: 8%
        - Risk 9: 16%
        - Risk 10: 100% (automatic mutual destruction)

    Args:
        risk_level: Current risk level (0-10)
        turn: Current turn number

    Returns:
        Probability of crisis termination (0.0 to 1.0)
    """
    # Crisis termination only applies from turn 10 onwards
    if turn < 10:
        return 0.0

    # No probability for risk 7 or below
    if risk_level <= 7.0:
        return 0.0

    # Risk 10 is handled by mutual destruction check, but for completeness
    if risk_level >= 10.0:
        return 1.0

    # Formula: (Risk - 7) * 0.08
    return (risk_level - 7.0) * 0.08


def check_crisis_termination(
    state: GameState,
    seed: int | None = None
) -> GameEnding | None:
    """Check for probabilistic crisis termination.

    From GAME_MANUAL.md:
        Starting Turn 10, at the END of each turn:
        if Risk_Level > 7:
            P(Crisis_Termination) = (Risk_Level - 7) * 0.08
            if random() < P(Crisis_Termination):
                trigger Final_Resolution

    Args:
        state: Current game state
        seed: Optional random seed for deterministic testing

    Returns:
        GameEnding if crisis terminates, None otherwise
    """
    probability = get_crisis_termination_probability(state.risk_level, state.turn)

    if probability <= 0.0:
        return None

    # Use seeded random if provided for testing
    if seed is not None:
        rng = random.Random(seed)
        roll = rng.random()
    else:
        roll = random.random()

    if roll < probability:
        # Crisis termination uses final resolution VP calculation
        vp_a, vp_b = final_resolution(state, seed)
        return GameEnding(
            ending_type=EndingType.CRISIS_TERMINATION,
            vp_a=vp_a,
            vp_b=vp_b,
            description=f"The crisis has terminated unexpectedly at Risk Level {state.risk_level:.1f}. Final resolution determines outcome.",
        )

    return None


def check_max_turns(state: GameState, seed: int | None = None) -> GameEnding | None:
    """Check if game has reached maximum turns.

    From GAME_MANUAL.md:
        Maximum Turn Range: 12-16 turns (unknown to players)
        If Turn = Max_Turn: Final Resolution -> END

    Args:
        state: Current game state
        seed: Optional random seed for deterministic final resolution

    Returns:
        GameEnding if max turns reached, None otherwise
    """
    if state.turn >= state.max_turns:
        vp_a, vp_b = final_resolution(state, seed)
        return GameEnding(
            ending_type=EndingType.MAX_TURNS,
            vp_a=vp_a,
            vp_b=vp_b,
            description=f"The game has reached its natural conclusion after {state.turn} turns. Final resolution determines outcome.",
        )
    return None


def check_all_endings(
    state: GameState,
    seed: int | None = None
) -> GameEnding | None:
    """Check all ending conditions in the correct order.

    The order of checks is important per GAME_MANUAL.md:

    1. Deterministic Endings (checked first, in order):
       a. Risk = 10: Mutual Destruction
       b. Position = 0: Position Loss
       c. Resources = 0: Resource Loss

    2. Probabilistic Endings (checked after deterministic):
       a. Crisis Termination (Turn >= 10, Risk > 7)
       b. Max Turns (turn >= max_turns)

    Note: Settlement is handled separately by the settlement system,
    not through this function.

    Args:
        state: Current game state
        seed: Optional random seed for deterministic testing

    Returns:
        GameEnding if any ending condition is met, None otherwise
    """
    # 1. Deterministic endings (checked in order of severity)

    # 1a. Mutual Destruction (Risk = 10)
    ending = check_mutual_destruction(state)
    if ending is not None:
        return ending

    # 1b. Position Loss
    ending = check_position_loss(state)
    if ending is not None:
        return ending

    # 1c. Resource Loss
    ending = check_resource_loss(state)
    if ending is not None:
        return ending

    # 2. Probabilistic endings

    # 2a. Crisis Termination (probabilistic)
    ending = check_crisis_termination(state, seed)
    if ending is not None:
        return ending

    # 2b. Max Turns (natural ending)
    ending = check_max_turns(state, seed)
    if ending is not None:
        return ending

    # No ending condition met
    return None
