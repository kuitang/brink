"""Variance and Final Resolution calculations for Brinksmanship.

This module implements the symmetric variance system and final VP resolution
as specified in GAME_MANUAL.md Section 4.

Key design principles:
1. Variance is a property of the SITUATION, not the individual
2. When either player acts unpredictably, BOTH face increased uncertainty
3. Symmetric noise application with renormalization ensures VP sum to 100

Formulas from GAME_MANUAL.md:
- Base_sigma = 8 + (Risk_Level * 1.2)           # Range: 8-20
- Chaos_Factor = 1.2 - (Cooperation_Score / 50)  # Range: 1.0-1.2
- Instability_Factor = 1 + (10 - Stability) / 20 # Range: 1.0-1.45
- Act_Multiplier: {1: 0.7, 2: 1.0, 3: 1.3}
- Shared_sigma = Base_sigma * Chaos_Factor * Instability_Factor * Act_Multiplier

Expected variance scenarios (from GAME_MANUAL.md Section 7.4):
- Peaceful early: ~10 sigma
- Neutral mid: ~19 sigma
- Tense late: ~27 sigma
- Chaotic crisis: ~37 sigma
"""

from __future__ import annotations

import random
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from brinksmanship.models.state import GameState


def clamp(value: float, min_val: float, max_val: float) -> float:
    """Clamp a value to the specified range.

    Args:
        value: The value to clamp
        min_val: Minimum allowed value
        max_val: Maximum allowed value

    Returns:
        Value clamped to [min_val, max_val]
    """
    return max(min_val, min(max_val, value))


def calculate_base_sigma(risk_level: float) -> float:
    """Calculate base sigma from risk level.

    Formula from GAME_MANUAL.md Section 4.2:
        Base_sigma = 8 + (Risk_Level * 1.2)

    Args:
        risk_level: Current risk level (0-10)

    Returns:
        Base sigma value (8-20)

    Examples:
        >>> calculate_base_sigma(0)
        8.0
        >>> calculate_base_sigma(5)
        14.0
        >>> calculate_base_sigma(10)
        20.0
    """
    return 8.0 + (risk_level * 1.2)


def calculate_chaos_factor(cooperation_score: float) -> float:
    """Calculate chaos factor from cooperation score.

    Formula from GAME_MANUAL.md Section 4.2:
        Chaos_Factor = 1.2 - (Cooperation_Score / 50)

    Higher cooperation = lower chaos (more predictable outcomes).

    Args:
        cooperation_score: Current cooperation score (0-10)

    Returns:
        Chaos factor (1.0-1.2)

    Examples:
        >>> calculate_chaos_factor(10)  # Strong cooperation
        1.0
        >>> calculate_chaos_factor(5)   # Neutral
        1.1
        >>> calculate_chaos_factor(0)   # Hostile
        1.2
    """
    return 1.2 - (cooperation_score / 50.0)


def calculate_instability_factor(stability: float) -> float:
    """Calculate instability factor from stability.

    Formula from GAME_MANUAL.md Section 4.2:
        Instability_Factor = 1 + (10 - Stability) / 20

    Higher stability = lower instability factor (more predictable outcomes).

    Args:
        stability: Current stability (1-10)

    Returns:
        Instability factor (1.0-1.45)

    Examples:
        >>> calculate_instability_factor(10)  # Very consistent
        1.0
        >>> calculate_instability_factor(5)   # Moderate
        1.25
        >>> calculate_instability_factor(1)   # Just switched
        1.45
    """
    return 1.0 + (10.0 - stability) / 20.0


def get_act_multiplier(turn: int) -> float:
    """Get the act multiplier for a given turn number.

    From GAME_MANUAL.md Section 4.2:
        - Act I (turns 1-4): 0.7
        - Act II (turns 5-8): 1.0
        - Act III (turns 9+): 1.3

    Args:
        turn: Current turn number (1-based)

    Returns:
        Act multiplier (0.7, 1.0, or 1.3)

    Examples:
        >>> get_act_multiplier(1)
        0.7
        >>> get_act_multiplier(4)
        0.7
        >>> get_act_multiplier(5)
        1.0
        >>> get_act_multiplier(8)
        1.0
        >>> get_act_multiplier(9)
        1.3
        >>> get_act_multiplier(15)
        1.3
    """
    if turn <= 4:
        return 0.7
    elif turn <= 8:
        return 1.0
    else:
        return 1.3


def calculate_shared_sigma(state: GameState) -> float:
    """Calculate the shared variance (sigma) for the current game state.

    Formula from GAME_MANUAL.md Section 4.2:
        Shared_sigma = Base_sigma * Chaos_Factor * Instability_Factor * Act_Multiplier

    This represents the standard deviation of the noise applied to final VP.
    The variance is "shared" because it affects both players equally (symmetric).

    Args:
        state: Current game state

    Returns:
        Shared sigma value (expected range ~10-40)

    Expected values from GAME_MANUAL.md Section 7.4:
        - Peaceful early (risk=3, coop=7, stab=8, act=I): ~10
        - Neutral mid (risk=5, coop=5, stab=5, act=II): ~19
        - Tense late (risk=7, coop=3, stab=6, act=III): ~27
        - Chaotic crisis (risk=9, coop=1, stab=2, act=III): ~37
    """
    base_sigma = calculate_base_sigma(state.risk_level)
    chaos_factor = calculate_chaos_factor(state.cooperation_score)
    instability_factor = calculate_instability_factor(state.stability)
    act_multiplier = get_act_multiplier(state.turn)

    return base_sigma * chaos_factor * instability_factor * act_multiplier


def final_resolution(
    state: GameState,
    seed: int | None = None
) -> tuple[float, float]:
    """Calculate final Victory Points for both players.

    This implements the Final Resolution algorithm from GAME_MANUAL.md Section 6.3.
    The algorithm:
    1. Calculate expected VP from position ratio
    2. Apply symmetric noise (same noise value affects both players)
    3. Clamp to [5, 95]
    4. Add captured surplus to final VP

    The symmetric noise ensures that variance is a property of the situation,
    not punishing one player for shared chaos.

    Note: Total VP can exceed 100 if surplus was created and captured!
    Remaining cooperation_surplus (unsettled) is LOST.

    Args:
        state: Final game state at resolution
        seed: Optional random seed for reproducibility (for testing)

    Returns:
        Tuple of (vp_a, vp_b). Total can exceed 100 due to captured surplus.

    Example from GAME_MANUAL.md:
        >>> state = GameState(position_a=6, position_b=4, risk_level=5,
        ...                   cooperation_score=5, stability=5, turn=9,
        ...                   surplus_captured_a=10.0, surplus_captured_b=5.0)
        >>> vp_a, vp_b = final_resolution(state, seed=42)
        >>> # Base ~60/40 + captured surplus = ~70/45
    """
    if seed is not None:
        random.seed(seed)

    # Calculate expected values from position ratio
    total_pos = state.position_a + state.position_b

    if total_pos == 0:
        # Edge case: both positions are 0
        ev_a = 50.0
    else:
        ev_a = (state.position_a / total_pos) * 100.0

    ev_b = 100.0 - ev_a

    # Calculate shared variance
    shared_sigma = calculate_shared_sigma(state)

    # Apply shared noise (symmetric: same noise affects both players)
    noise = random.gauss(0, shared_sigma)

    vp_a_raw = ev_a + noise
    vp_b_raw = ev_b - noise  # Symmetric: both move together

    # Clamp both to [5, 95]
    vp_a_clamped = clamp(vp_a_raw, 5.0, 95.0)
    vp_b_clamped = clamp(vp_b_raw, 5.0, 95.0)

    # Add captured surplus (can exceed 100 total!)
    # Per GAME_MANUAL.md Section 6.3: vp = clamp(vp_raw, 5, 95) + surplus_captured
    vp_a = vp_a_clamped + state.surplus_captured_a
    vp_b = vp_b_clamped + state.surplus_captured_b

    return vp_a, vp_b


def calculate_expected_vp(state: GameState) -> tuple[float, float]:
    """Calculate expected VP without noise (for display/analysis).

    This gives the "fair" VP split based purely on position ratio,
    before variance is applied.

    Args:
        state: Current game state

    Returns:
        Tuple of (expected_vp_a, expected_vp_b) summing to 100
    """
    total_pos = state.position_a + state.position_b

    if total_pos == 0:
        return 50.0, 50.0

    ev_a = (state.position_a / total_pos) * 100.0
    ev_b = 100.0 - ev_a

    return ev_a, ev_b
