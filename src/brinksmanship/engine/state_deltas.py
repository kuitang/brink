"""State Delta System for Brinksmanship game mechanics.

This module defines how matrix outcomes affect game state (Position, Resources, Risk).
Each matrix type has a delta template defining bounds for each outcome.

State deltas must satisfy global constraints and game-type-specific ordinal consistency.

See GAME_MANUAL.md Section 3.5 for authoritative specifications.
See ENGINEERING_DESIGN.md Milestone 2.5 for implementation details.
"""

from dataclasses import dataclass

from brinksmanship.models.matrices import MatrixParameters, MatrixType


@dataclass(frozen=True)
class StateDeltaOutcome:
    """State changes resulting from a single matrix outcome.

    Represents changes to Position, Resources, and Risk for both players
    after a turn's matrix resolution.

    Constraints from GAME_MANUAL.md Section 3.5:
    - Position: -1.5 to +1.5 per player per turn (pre-scaling)
    - Resource cost: 0 to 1.0 per player per turn (pre-scaling)
    - Risk: -1.0 to +2.0 shared per turn (pre-scaling)
    - Position changes are near-zero-sum: |pos_a + pos_b| <= 0.5
    """

    pos_a: float  # Position change for player A
    pos_b: float  # Position change for player B
    res_cost_a: float  # Resource cost for player A (always >= 0)
    res_cost_b: float  # Resource cost for player B (always >= 0)
    risk_delta: float  # Shared risk level change


@dataclass(frozen=True)
class OutcomeBounds:
    """Min/max bounds for a single value in a delta template."""

    min_val: float
    max_val: float

    def __post_init__(self) -> None:
        if self.min_val > self.max_val:
            raise ValueError(
                f"min_val ({self.min_val}) cannot exceed max_val ({self.max_val})"
            )

    def midpoint(self) -> float:
        """Return the midpoint of the bounds range."""
        return (self.min_val + self.max_val) / 2.0

    def contains(self, value: float) -> bool:
        """Check if a value falls within bounds (inclusive)."""
        return self.min_val <= value <= self.max_val


@dataclass(frozen=True)
class OutcomeDeltaBounds:
    """Bounds for all delta values of a single outcome."""

    pos_a: OutcomeBounds
    pos_b: OutcomeBounds
    res_cost_a: OutcomeBounds
    res_cost_b: OutcomeBounds
    risk: OutcomeBounds


@dataclass(frozen=True)
class StateDeltaTemplate:
    """Delta template for a matrix type.

    Defines the bounds for state deltas for each of the four possible outcomes
    (CC, CD, DC, DD). Used to validate scenario-specified deltas and to
    generate default deltas for testing.
    """

    matrix_type: MatrixType
    cc: OutcomeDeltaBounds  # Both cooperate / (A, A)
    cd: OutcomeDeltaBounds  # Row cooperates, Col defects / (A, B)
    dc: OutcomeDeltaBounds  # Row defects, Col cooperates / (B, A)
    dd: OutcomeDeltaBounds  # Both defect / (B, B)


# Global bounds constraints from GAME_MANUAL.md Section 3.5
GLOBAL_BOUNDS = {
    "position": (-1.5, 1.5),  # Per player, per turn (pre-scaling)
    "resource_cost": (0.0, 1.0),  # Per player, per turn (pre-scaling)
    "risk": (-1.0, 2.0),  # Shared, per turn (pre-scaling)
}

# Maximum allowed deviation from zero-sum for position changes
MAX_POSITION_SUM_DEVIATION = 0.5


def _bounds(min_val: float, max_val: float) -> OutcomeBounds:
    """Helper to create OutcomeBounds."""
    return OutcomeBounds(min_val=min_val, max_val=max_val)


def _outcome_bounds(
    pos_a: tuple[float, float],
    pos_b: tuple[float, float],
    res_a: tuple[float, float] = (0.0, 0.0),
    res_b: tuple[float, float] = (0.0, 0.0),
    risk: tuple[float, float] = (0.0, 0.0),
) -> OutcomeDeltaBounds:
    """Helper to create OutcomeDeltaBounds from tuples."""
    return OutcomeDeltaBounds(
        pos_a=_bounds(*pos_a),
        pos_b=_bounds(*pos_b),
        res_cost_a=_bounds(*res_a),
        res_cost_b=_bounds(*res_b),
        risk=_bounds(*risk),
    )


# =============================================================================
# Delta Templates for All 14 Matrix Types
# =============================================================================
#
# These templates define reasonable deltas that:
# 1. Stay within global bounds
# 2. Maintain near-zero-sum for position changes
# 3. Reflect the strategic logic of each game type
#
# Based on GAME_MANUAL.md Section 3.5 examples and game theory principles.

# Prisoner's Dilemma (T > R > P > S)
# - CC: Mutual cooperation - both gain moderately, risk decreases
# - CD/DC: Exploitation - exploiter gains, victim loses, risk increases
# - DD: Mutual defection - both lose slightly, high resource cost, high risk
PD_DELTA_TEMPLATE = StateDeltaTemplate(
    matrix_type=MatrixType.PRISONERS_DILEMMA,
    cc=_outcome_bounds(
        pos_a=(0.3, 0.7), pos_b=(0.3, 0.7), risk=(-1.0, 0.0)
    ),  # Mutual gain
    cd=_outcome_bounds(
        pos_a=(-1.2, -0.5), pos_b=(0.5, 1.2), risk=(0.0, 1.0)
    ),  # A exploited
    dc=_outcome_bounds(
        pos_a=(0.5, 1.2), pos_b=(-1.2, -0.5), risk=(0.0, 1.0)
    ),  # B exploited
    dd=_outcome_bounds(
        pos_a=(-0.7, 0.0),
        pos_b=(-0.7, 0.0),
        res_a=(0.3, 0.6),
        res_b=(0.3, 0.6),
        risk=(0.5, 1.5),
    ),  # Mutual harm
)

# Deadlock (T > P > R > S)
# Both prefer mutual defection - DD is actually stable and not harmful
DEADLOCK_DELTA_TEMPLATE = StateDeltaTemplate(
    matrix_type=MatrixType.DEADLOCK,
    cc=_outcome_bounds(
        pos_a=(0.1, 0.4), pos_b=(0.1, 0.4), risk=(-0.3, 0.3)
    ),  # Suboptimal
    cd=_outcome_bounds(
        pos_a=(-1.0, -0.4), pos_b=(0.4, 1.0), risk=(0.2, 0.8)
    ),  # A exploited
    dc=_outcome_bounds(
        pos_a=(0.4, 1.0), pos_b=(-1.0, -0.4), risk=(0.2, 0.8)
    ),  # B exploited
    dd=_outcome_bounds(
        pos_a=(0.2, 0.5), pos_b=(0.2, 0.5), risk=(-0.3, 0.3)
    ),  # Preferred by both
)

# Harmony (R > T > S > P)
# Cooperation dominates - CC is best for everyone
# For row player A: R=CC > T=DC > S=CD > P=DD
HARMONY_DELTA_TEMPLATE = StateDeltaTemplate(
    matrix_type=MatrixType.HARMONY,
    cc=_outcome_bounds(
        pos_a=(0.5, 1.0), pos_b=(0.5, 1.0), risk=(-1.0, -0.3)
    ),  # R: Best outcome (mutual coop)
    cd=_outcome_bounds(
        pos_a=(-0.1, 0.1), pos_b=(0.2, 0.5), risk=(-0.2, 0.3)
    ),  # S: Row cooperates, col defects (row is sucker but not too bad)
    dc=_outcome_bounds(
        pos_a=(0.2, 0.5), pos_b=(-0.1, 0.1), risk=(-0.2, 0.3)
    ),  # T: Row defects, col cooperates (row tempted but coop is better)
    dd=_outcome_bounds(
        pos_a=(-0.5, -0.2),
        pos_b=(-0.5, -0.2),
        res_a=(0.2, 0.5),
        res_b=(0.2, 0.5),
        risk=(0.3, 1.0),
    ),  # P: Worst (mutual defect)
)

# Chicken (T > R > S > P)
# - Dove-Dove: Both back down, modest gains, risk decreases
# - Hawk-Dove: Hawk wins, Dove loses but survives
# - Hawk-Hawk: CRASH - catastrophic for both, maximum risk
CHICKEN_DELTA_TEMPLATE = StateDeltaTemplate(
    matrix_type=MatrixType.CHICKEN,
    cc=_outcome_bounds(
        pos_a=(0.2, 0.5), pos_b=(0.2, 0.5), risk=(-0.7, -0.2)
    ),  # Both swerve
    cd=_outcome_bounds(
        pos_a=(-0.7, -0.3), pos_b=(0.7, 1.2), risk=(0.2, 0.7)
    ),  # Row swerves
    dc=_outcome_bounds(
        pos_a=(0.7, 1.2), pos_b=(-0.7, -0.3), risk=(0.2, 0.7)
    ),  # Col swerves
    dd=_outcome_bounds(
        pos_a=(-1.5, -1.0),
        pos_b=(-1.5, -1.0),
        res_a=(0.7, 1.0),
        res_b=(0.7, 1.0),
        risk=(1.5, 2.0),
    ),  # CRASH
)

# Volunteer's Dilemma (F > W > D)
# Someone must volunteer or everyone loses
VOLUNTEERS_DILEMMA_DELTA_TEMPLATE = StateDeltaTemplate(
    matrix_type=MatrixType.VOLUNTEERS_DILEMMA,
    cc=_outcome_bounds(
        pos_a=(0.1, 0.3),
        pos_b=(0.1, 0.3),
        res_a=(0.1, 0.3),
        res_b=(0.1, 0.3),
        risk=(-0.5, 0.0),
    ),  # Both volunteer (wasteful)
    cd=_outcome_bounds(
        pos_a=(-0.2, 0.0),
        pos_b=(0.3, 0.6),
        res_a=(0.2, 0.4),
        risk=(-0.5, 0.0),
    ),  # Row volunteers
    dc=_outcome_bounds(
        pos_a=(0.3, 0.6),
        pos_b=(-0.2, 0.0),
        res_b=(0.2, 0.4),
        risk=(-0.5, 0.0),
    ),  # Col volunteers
    dd=_outcome_bounds(
        pos_a=(-1.0, -0.5),
        pos_b=(-1.0, -0.5),
        res_a=(0.5, 0.8),
        res_b=(0.5, 0.8),
        risk=(0.8, 1.5),
    ),  # Disaster
)

# War of Attrition (Continue/Quit)
# Costly conflict - mutual continue is expensive
WAR_OF_ATTRITION_DELTA_TEMPLATE = StateDeltaTemplate(
    matrix_type=MatrixType.WAR_OF_ATTRITION,
    cc=_outcome_bounds(
        pos_a=(-0.3, 0.0),
        pos_b=(-0.3, 0.0),
        res_a=(0.4, 0.7),
        res_b=(0.4, 0.7),
        risk=(0.5, 1.2),
    ),  # Both continue (costly)
    cd=_outcome_bounds(
        pos_a=(0.7, 1.2), pos_b=(-0.8, -0.3), risk=(-0.3, 0.2)
    ),  # Row wins
    dc=_outcome_bounds(
        pos_a=(-0.8, -0.3), pos_b=(0.7, 1.2), risk=(-0.3, 0.2)
    ),  # Col wins
    dd=_outcome_bounds(
        pos_a=(0.1, 0.3), pos_b=(0.1, 0.3), risk=(-0.5, 0.0)
    ),  # Both quit
)

# Pure Coordination (Match > Mismatch)
# Matching is good, mismatching is bad, but symmetric
PURE_COORDINATION_DELTA_TEMPLATE = StateDeltaTemplate(
    matrix_type=MatrixType.PURE_COORDINATION,
    cc=_outcome_bounds(
        pos_a=(0.3, 0.6), pos_b=(0.3, 0.6), risk=(-0.5, -0.1)
    ),  # Match on A
    cd=_outcome_bounds(
        pos_a=(-0.3, 0.0), pos_b=(-0.3, 0.0), risk=(0.1, 0.5)
    ),  # Mismatch
    dc=_outcome_bounds(
        pos_a=(-0.3, 0.0), pos_b=(-0.3, 0.0), risk=(0.1, 0.5)
    ),  # Mismatch
    dd=_outcome_bounds(
        pos_a=(0.3, 0.6), pos_b=(0.3, 0.6), risk=(-0.5, -0.1)
    ),  # Match on B
)

# Stag Hunt (R > T > P > S)
# - Stag-Stag: Best payoff-dominant equilibrium
# - Hare-Hare: Safe risk-dominant equilibrium
# - Mixed: Stag hunter fails
STAG_HUNT_DELTA_TEMPLATE = StateDeltaTemplate(
    matrix_type=MatrixType.STAG_HUNT,
    cc=_outcome_bounds(
        pos_a=(0.6, 1.0), pos_b=(0.6, 1.0), risk=(-0.8, -0.3)
    ),  # Stag-Stag (best)
    cd=_outcome_bounds(
        pos_a=(-0.8, -0.3), pos_b=(0.2, 0.5), risk=(0.1, 0.5)
    ),  # Row fails
    dc=_outcome_bounds(
        pos_a=(0.2, 0.5), pos_b=(-0.8, -0.3), risk=(0.1, 0.5)
    ),  # Col fails
    dd=_outcome_bounds(
        pos_a=(0.1, 0.3), pos_b=(0.1, 0.3), risk=(-0.2, 0.2)
    ),  # Hare-Hare (safe)
)

# Battle of the Sexes (Coord > Miscoord with preference asymmetry)
BATTLE_OF_SEXES_DELTA_TEMPLATE = StateDeltaTemplate(
    matrix_type=MatrixType.BATTLE_OF_SEXES,
    cc=_outcome_bounds(
        pos_a=(0.5, 0.8), pos_b=(0.2, 0.4), risk=(-0.4, 0.0)
    ),  # Row's preferred
    cd=_outcome_bounds(
        pos_a=(-0.4, -0.1), pos_b=(-0.4, -0.1), risk=(0.2, 0.6)
    ),  # Mismatch
    dc=_outcome_bounds(
        pos_a=(-0.4, -0.1), pos_b=(-0.4, -0.1), risk=(0.2, 0.6)
    ),  # Mismatch
    dd=_outcome_bounds(
        pos_a=(0.2, 0.4), pos_b=(0.5, 0.8), risk=(-0.4, 0.0)
    ),  # Col's preferred
)

# Leader (G > H > B > C)
# One should lead, one should follow
LEADER_DELTA_TEMPLATE = StateDeltaTemplate(
    matrix_type=MatrixType.LEADER,
    cc=_outcome_bounds(
        pos_a=(-0.3, 0.0), pos_b=(-0.3, 0.0), risk=(0.1, 0.5)
    ),  # Both follow (stuck)
    cd=_outcome_bounds(
        pos_a=(0.2, 0.5), pos_b=(0.5, 0.9), risk=(-0.4, 0.0)
    ),  # Col leads
    dc=_outcome_bounds(
        pos_a=(0.5, 0.9), pos_b=(0.2, 0.5), risk=(-0.4, 0.0)
    ),  # Row leads
    dd=_outcome_bounds(
        pos_a=(-0.5, -0.2),
        pos_b=(-0.5, -0.2),
        res_a=(0.2, 0.5),
        res_b=(0.2, 0.5),
        risk=(0.5, 1.2),
    ),  # Both lead (clash)
)

# Matching Pennies (Zero-sum)
# One player's gain is exactly the other's loss
MATCHING_PENNIES_DELTA_TEMPLATE = StateDeltaTemplate(
    matrix_type=MatrixType.MATCHING_PENNIES,
    cc=_outcome_bounds(
        pos_a=(0.3, 0.7), pos_b=(-0.7, -0.3), risk=(-0.2, 0.2)
    ),  # Row wins
    cd=_outcome_bounds(
        pos_a=(-0.7, -0.3), pos_b=(0.3, 0.7), risk=(-0.2, 0.2)
    ),  # Col wins
    dc=_outcome_bounds(
        pos_a=(-0.7, -0.3), pos_b=(0.3, 0.7), risk=(-0.2, 0.2)
    ),  # Col wins
    dd=_outcome_bounds(
        pos_a=(0.3, 0.7), pos_b=(-0.7, -0.3), risk=(-0.2, 0.2)
    ),  # Row wins
)

# Inspection Game (Inspector vs potential cheater)
INSPECTION_GAME_DELTA_TEMPLATE = StateDeltaTemplate(
    matrix_type=MatrixType.INSPECTION_GAME,
    cc=_outcome_bounds(
        pos_a=(-0.1, 0.1), pos_b=(0.0, 0.2), res_a=(0.1, 0.3), risk=(-0.2, 0.1)
    ),  # Inspect+Comply
    cd=_outcome_bounds(
        pos_a=(0.3, 0.6), pos_b=(-0.8, -0.4), risk=(0.5, 1.2)
    ),  # Caught cheating
    dc=_outcome_bounds(
        pos_a=(-0.1, 0.1), pos_b=(0.0, 0.2), risk=(-0.2, 0.1)
    ),  # Trust+Comply
    dd=_outcome_bounds(
        pos_a=(-0.7, -0.3), pos_b=(0.4, 0.8), risk=(0.2, 0.7)
    ),  # Exploited
)

# Reconnaissance Game (Information zero-sum)
# Special handling per GAME_MANUAL.md Section 3.6.1
RECONNAISSANCE_DELTA_TEMPLATE = StateDeltaTemplate(
    matrix_type=MatrixType.RECONNAISSANCE,
    cc=_outcome_bounds(
        pos_a=(-0.2, 0.0), pos_b=(0.0, 0.2), risk=(0.3, 0.7)
    ),  # Detected
    cd=_outcome_bounds(
        pos_a=(0.0, 0.2), pos_b=(-0.2, 0.0), risk=(-0.1, 0.1)
    ),  # Success
    dc=_outcome_bounds(
        pos_a=(0.0, 0.0), pos_b=(0.0, 0.0), risk=(-0.1, 0.1)
    ),  # Stalemate
    dd=_outcome_bounds(
        pos_a=(-0.2, 0.0), pos_b=(0.0, 0.2), risk=(-0.1, 0.1)
    ),  # Exposed
)

# Security Dilemma (Same as PD but with defensive interpretation)
SECURITY_DILEMMA_DELTA_TEMPLATE = StateDeltaTemplate(
    matrix_type=MatrixType.SECURITY_DILEMMA,
    cc=_outcome_bounds(
        pos_a=(0.3, 0.7), pos_b=(0.3, 0.7), risk=(-1.0, -0.3)
    ),  # Mutual disarm
    cd=_outcome_bounds(
        pos_a=(-1.2, -0.5), pos_b=(0.5, 1.2), risk=(0.3, 1.0)
    ),  # A vulnerable
    dc=_outcome_bounds(
        pos_a=(0.5, 1.2), pos_b=(-1.2, -0.5), risk=(0.3, 1.0)
    ),  # B vulnerable
    dd=_outcome_bounds(
        pos_a=(-0.5, 0.0),
        pos_b=(-0.5, 0.0),
        res_a=(0.3, 0.6),
        res_b=(0.3, 0.6),
        risk=(0.3, 1.0),
    ),  # Arms race
)


# Registry of all delta templates by matrix type
DELTA_TEMPLATES: dict[MatrixType, StateDeltaTemplate] = {
    MatrixType.PRISONERS_DILEMMA: PD_DELTA_TEMPLATE,
    MatrixType.DEADLOCK: DEADLOCK_DELTA_TEMPLATE,
    MatrixType.HARMONY: HARMONY_DELTA_TEMPLATE,
    MatrixType.CHICKEN: CHICKEN_DELTA_TEMPLATE,
    MatrixType.VOLUNTEERS_DILEMMA: VOLUNTEERS_DILEMMA_DELTA_TEMPLATE,
    MatrixType.WAR_OF_ATTRITION: WAR_OF_ATTRITION_DELTA_TEMPLATE,
    MatrixType.PURE_COORDINATION: PURE_COORDINATION_DELTA_TEMPLATE,
    MatrixType.STAG_HUNT: STAG_HUNT_DELTA_TEMPLATE,
    MatrixType.BATTLE_OF_SEXES: BATTLE_OF_SEXES_DELTA_TEMPLATE,
    MatrixType.LEADER: LEADER_DELTA_TEMPLATE,
    MatrixType.MATCHING_PENNIES: MATCHING_PENNIES_DELTA_TEMPLATE,
    MatrixType.INSPECTION_GAME: INSPECTION_GAME_DELTA_TEMPLATE,
    MatrixType.RECONNAISSANCE: RECONNAISSANCE_DELTA_TEMPLATE,
    MatrixType.SECURITY_DILEMMA: SECURITY_DILEMMA_DELTA_TEMPLATE,
}


# =============================================================================
# Validation Functions
# =============================================================================


def validate_delta_outcome(delta: StateDeltaOutcome) -> bool:
    """Validate that a delta outcome satisfies global bounds.

    Returns True if valid, False otherwise.
    Does not raise exceptions.
    """
    pos_min, pos_max = GLOBAL_BOUNDS["position"]
    res_min, res_max = GLOBAL_BOUNDS["resource_cost"]
    risk_min, risk_max = GLOBAL_BOUNDS["risk"]

    # Check position bounds
    if not (pos_min <= delta.pos_a <= pos_max):
        return False
    if not (pos_min <= delta.pos_b <= pos_max):
        return False

    # Check resource cost bounds
    if not (res_min <= delta.res_cost_a <= res_max):
        return False
    if not (res_min <= delta.res_cost_b <= res_max):
        return False

    # Check risk bounds
    return risk_min <= delta.risk_delta <= risk_max


def validate_near_zero_sum(delta: StateDeltaOutcome) -> bool:
    """Validate that position changes are near-zero-sum.

    Per GAME_MANUAL.md Section 3.5:
    |delta_pos_a + delta_pos_b| <= 0.5

    Returns True if constraint is satisfied.
    """
    return abs(delta.pos_a + delta.pos_b) <= MAX_POSITION_SUM_DEVIATION


def validate_delta_full(delta: StateDeltaOutcome) -> tuple[bool, list[str]]:
    """Perform full validation of a delta outcome.

    Returns (is_valid, list_of_error_messages).
    """
    errors = []
    pos_min, pos_max = GLOBAL_BOUNDS["position"]
    res_min, res_max = GLOBAL_BOUNDS["resource_cost"]
    risk_min, risk_max = GLOBAL_BOUNDS["risk"]

    # Check position bounds
    if not (pos_min <= delta.pos_a <= pos_max):
        errors.append(f"pos_a={delta.pos_a} outside bounds [{pos_min}, {pos_max}]")
    if not (pos_min <= delta.pos_b <= pos_max):
        errors.append(f"pos_b={delta.pos_b} outside bounds [{pos_min}, {pos_max}]")

    # Check resource cost bounds
    if not (res_min <= delta.res_cost_a <= res_max):
        errors.append(
            f"res_cost_a={delta.res_cost_a} outside bounds [{res_min}, {res_max}]"
        )
    if not (res_min <= delta.res_cost_b <= res_max):
        errors.append(
            f"res_cost_b={delta.res_cost_b} outside bounds [{res_min}, {res_max}]"
        )

    # Check risk bounds
    if not (risk_min <= delta.risk_delta <= risk_max):
        errors.append(
            f"risk_delta={delta.risk_delta} outside bounds [{risk_min}, {risk_max}]"
        )

    # Check near-zero-sum
    position_sum = abs(delta.pos_a + delta.pos_b)
    if position_sum > MAX_POSITION_SUM_DEVIATION:
        errors.append(
            f"Position changes not near-zero-sum: "
            f"|{delta.pos_a} + {delta.pos_b}| = {position_sum} > {MAX_POSITION_SUM_DEVIATION}"
        )

    return len(errors) == 0, errors


# =============================================================================
# Act Scaling
# =============================================================================

# Act multipliers from GAME_MANUAL.md Section 3.5
ACT_MULTIPLIERS = {
    1: 0.7,  # Act I (turns 1-4): lower stakes
    2: 1.0,  # Act II (turns 5-8): standard stakes
    3: 1.3,  # Act III (turns 9+): high stakes
}


def get_act_for_turn(turn: int) -> int:
    """Determine which act a turn belongs to.

    From GAME_MANUAL.md Section 6.1:
    - Act I: Turns 1-4
    - Act II: Turns 5-8
    - Act III: Turns 9+
    """
    if turn <= 4:
        return 1
    elif turn <= 8:
        return 2
    else:
        return 3


def get_act_multiplier(turn: int) -> float:
    """Get the act multiplier for a given turn number."""
    act = get_act_for_turn(turn)
    return ACT_MULTIPLIERS[act]


def apply_act_scaling(
    delta: StateDeltaOutcome, act_multiplier: float
) -> StateDeltaOutcome:
    """Apply act scaling to a delta outcome.

    Scales position, resource cost, and risk changes by the act multiplier.
    The multiplier is based on the current turn's act:
    - Act I (turns 1-4): x0.7
    - Act II (turns 5-8): x1.0
    - Act III (turns 9+): x1.3

    Note: The scaled deltas may exceed global bounds. This is intentional
    as the bounds in templates are pre-scaling values. Final application
    to game state will clamp to valid ranges.
    """
    return StateDeltaOutcome(
        pos_a=delta.pos_a * act_multiplier,
        pos_b=delta.pos_b * act_multiplier,
        res_cost_a=delta.res_cost_a * act_multiplier,
        res_cost_b=delta.res_cost_b * act_multiplier,
        risk_delta=delta.risk_delta * act_multiplier,
    )


# =============================================================================
# Delta Generation
# =============================================================================


def get_delta_for_outcome(
    matrix_type: MatrixType,
    outcome: str,
    params: MatrixParameters | None = None,
) -> StateDeltaOutcome:
    """Get the default state delta for a matrix outcome.

    Uses the midpoint of the bounds in the delta template for the given
    matrix type and outcome.

    Args:
        matrix_type: The type of game matrix
        outcome: One of "CC", "CD", "DC", "DD"
        params: Optional matrix parameters (currently unused, reserved for
                future parameter-influenced deltas)

    Returns:
        StateDeltaOutcome with midpoint values from the template bounds

    Raises:
        ValueError: If matrix_type or outcome is invalid
    """
    template = DELTA_TEMPLATES.get(matrix_type)
    if template is None:
        raise ValueError(f"Unknown matrix type: {matrix_type}")

    outcome_upper = outcome.upper()
    if outcome_upper == "CC":
        bounds = template.cc
    elif outcome_upper == "CD":
        bounds = template.cd
    elif outcome_upper == "DC":
        bounds = template.dc
    elif outcome_upper == "DD":
        bounds = template.dd
    else:
        raise ValueError(f"Invalid outcome: {outcome}. Must be CC, CD, DC, or DD")

    return StateDeltaOutcome(
        pos_a=bounds.pos_a.midpoint(),
        pos_b=bounds.pos_b.midpoint(),
        res_cost_a=bounds.res_cost_a.midpoint(),
        res_cost_b=bounds.res_cost_b.midpoint(),
        risk_delta=bounds.risk.midpoint(),
    )


def get_scaled_delta_for_outcome(
    matrix_type: MatrixType,
    outcome: str,
    turn: int,
    params: MatrixParameters | None = None,
) -> StateDeltaOutcome:
    """Get a state delta with act scaling applied.

    Convenience function that combines get_delta_for_outcome with apply_act_scaling.

    Args:
        matrix_type: The type of game matrix
        outcome: One of "CC", "CD", "DC", "DD"
        turn: Current turn number (used to determine act)
        params: Optional matrix parameters

    Returns:
        StateDeltaOutcome with act scaling applied
    """
    base_delta = get_delta_for_outcome(matrix_type, outcome, params)
    multiplier = get_act_multiplier(turn)
    return apply_act_scaling(base_delta, multiplier)


# =============================================================================
# Ordinal Consistency Validation
# =============================================================================
#
# These functions validate that deltas maintain ordinal consistency with
# the game type's strategic structure. For example, in Prisoner's Dilemma:
# T > R > P > S means the defector's payoff against a cooperator (T) should
# be better than mutual cooperation (R), etc.


def _get_player_delta_value(
    delta: StateDeltaOutcome, player: str, metric: str = "position"
) -> float:
    """Get the relevant delta value for a player.

    For ordinal comparison, we typically use position change as the
    primary indicator of outcome quality.
    """
    if metric == "position":
        return delta.pos_a if player == "A" else delta.pos_b
    elif metric == "net":
        # Net value = position gain - resource cost
        if player == "A":
            return delta.pos_a - delta.res_cost_a
        else:
            return delta.pos_b - delta.res_cost_b
    else:
        raise ValueError(f"Unknown metric: {metric}")


def validate_pd_ordinal_consistency(template: StateDeltaTemplate) -> tuple[bool, list[str]]:
    """Validate Prisoner's Dilemma ordinal constraint: T > R > P > S.

    For row player A:
    - T = DC (defect against cooperator): pos_a from dc
    - R = CC (mutual cooperation): pos_a from cc
    - P = DD (mutual defection): pos_a from dd
    - S = CD (cooperate against defector): pos_a from cd

    Uses midpoint of bounds for comparison.
    """
    errors = []

    t = template.dc.pos_a.midpoint()  # Temptation (defect vs coop)
    r = template.cc.pos_a.midpoint()  # Reward (mutual coop)
    p = template.dd.pos_a.midpoint()  # Punishment (mutual defect)
    s = template.cd.pos_a.midpoint()  # Sucker (coop vs defect)

    if not (t > r):
        errors.append(f"T > R violated: T={t:.2f}, R={r:.2f}")
    if not (r > p):
        errors.append(f"R > P violated: R={r:.2f}, P={p:.2f}")
    if not (p > s):
        errors.append(f"P > S violated: P={p:.2f}, S={s:.2f}")

    return len(errors) == 0, errors


def validate_chicken_ordinal_consistency(template: StateDeltaTemplate) -> tuple[bool, list[str]]:
    """Validate Chicken ordinal constraint: T > R > S > P.

    For row player A:
    - T = DC (hawk vs dove): pos_a from dc
    - R = CC (both dove): pos_a from cc
    - S = CD (dove vs hawk): pos_a from cd
    - P = DD (crash): pos_a from dd
    """
    errors = []

    t = template.dc.pos_a.midpoint()
    r = template.cc.pos_a.midpoint()
    s = template.cd.pos_a.midpoint()
    p = template.dd.pos_a.midpoint()

    if not (t > r):
        errors.append(f"T > R violated: T={t:.2f}, R={r:.2f}")
    if not (r > s):
        errors.append(f"R > S violated: R={r:.2f}, S={s:.2f}")
    if not (s > p):
        errors.append(f"S > P violated: S={s:.2f}, P={p:.2f}")

    return len(errors) == 0, errors


def validate_stag_hunt_ordinal_consistency(template: StateDeltaTemplate) -> tuple[bool, list[str]]:
    """Validate Stag Hunt ordinal constraint: R > T > P > S.

    For row player A:
    - R = CC (mutual stag): pos_a from cc
    - T = DC (hare while other stags): pos_a from dc
    - P = DD (mutual hare): pos_a from dd
    - S = CD (stag alone): pos_a from cd
    """
    errors = []

    r = template.cc.pos_a.midpoint()
    t = template.dc.pos_a.midpoint()
    p = template.dd.pos_a.midpoint()
    s = template.cd.pos_a.midpoint()

    if not (r > t):
        errors.append(f"R > T violated: R={r:.2f}, T={t:.2f}")
    if not (t > p):
        errors.append(f"T > P violated: T={t:.2f}, P={p:.2f}")
    if not (p > s):
        errors.append(f"P > S violated: P={p:.2f}, S={s:.2f}")

    return len(errors) == 0, errors


def validate_deadlock_ordinal_consistency(template: StateDeltaTemplate) -> tuple[bool, list[str]]:
    """Validate Deadlock ordinal constraint: T > P > R > S.

    For row player A:
    - T = DC: pos_a from dc
    - P = DD: pos_a from dd
    - R = CC: pos_a from cc
    - S = CD: pos_a from cd
    """
    errors = []

    t = template.dc.pos_a.midpoint()
    p = template.dd.pos_a.midpoint()
    r = template.cc.pos_a.midpoint()
    s = template.cd.pos_a.midpoint()

    if not (t > p):
        errors.append(f"T > P violated: T={t:.2f}, P={p:.2f}")
    if not (p > r):
        errors.append(f"P > R violated: P={p:.2f}, R={r:.2f}")
    if not (r > s):
        errors.append(f"R > S violated: R={r:.2f}, S={s:.2f}")

    return len(errors) == 0, errors


def validate_harmony_ordinal_consistency(template: StateDeltaTemplate) -> tuple[bool, list[str]]:
    """Validate Harmony ordinal constraint: R > T > S > P.

    For row player A:
    - R = CC: pos_a from cc
    - T = DC: pos_a from dc
    - S = CD: pos_a from cd
    - P = DD: pos_a from dd
    """
    errors = []

    r = template.cc.pos_a.midpoint()
    t = template.dc.pos_a.midpoint()
    s = template.cd.pos_a.midpoint()
    p = template.dd.pos_a.midpoint()

    if not (r > t):
        errors.append(f"R > T violated: R={r:.2f}, T={t:.2f}")
    if not (t > s):
        errors.append(f"T > S violated: T={t:.2f}, S={s:.2f}")
    if not (s > p):
        errors.append(f"S > P violated: S={s:.2f}, P={p:.2f}")

    return len(errors) == 0, errors


# Ordinal validators by matrix type
ORDINAL_VALIDATORS = {
    MatrixType.PRISONERS_DILEMMA: validate_pd_ordinal_consistency,
    MatrixType.SECURITY_DILEMMA: validate_pd_ordinal_consistency,  # Same structure as PD
    MatrixType.CHICKEN: validate_chicken_ordinal_consistency,
    MatrixType.STAG_HUNT: validate_stag_hunt_ordinal_consistency,
    MatrixType.DEADLOCK: validate_deadlock_ordinal_consistency,
    MatrixType.HARMONY: validate_harmony_ordinal_consistency,
}


def validate_ordinal_consistency(
    matrix_type: MatrixType, template: StateDeltaTemplate | None = None
) -> tuple[bool, list[str]]:
    """Validate ordinal consistency for a matrix type's delta template.

    If no template is provided, uses the default template from DELTA_TEMPLATES.

    Returns (is_valid, list_of_error_messages).
    For matrix types without ordinal constraints (e.g., zero-sum games),
    returns (True, []).
    """
    if template is None:
        template = DELTA_TEMPLATES.get(matrix_type)
        if template is None:
            return False, [f"Unknown matrix type: {matrix_type}"]

    validator = ORDINAL_VALIDATORS.get(matrix_type)
    if validator is None:
        # No ordinal constraints for this type (e.g., Matching Pennies)
        return True, []

    return validator(template)


def validate_all_templates() -> dict[MatrixType, tuple[bool, list[str]]]:
    """Validate all delta templates for ordinal consistency.

    Returns a dict mapping each MatrixType to (is_valid, errors).
    Useful for testing and validation scripts.
    """
    results = {}
    for matrix_type, template in DELTA_TEMPLATES.items():
        results[matrix_type] = validate_ordinal_consistency(matrix_type, template)
    return results
