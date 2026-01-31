"""State Delta System for Brinksmanship game mechanics.

This module defines how matrix outcomes affect game state (Position, Resources, Risk).
Each matrix type has a delta template defining bounds for each outcome.

State deltas must satisfy global constraints and game-type-specific ordinal consistency.

See GAME_MANUAL.md Section 3.5 for authoritative specifications.
See ENGINEERING_DESIGN.md Milestone 2.5 for implementation details.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING

from brinksmanship.models.matrices import MatrixParameters, MatrixType
from brinksmanship.parameters import (
    CAPTURE_RATE,
    CC_RISK_REDUCTION,
    DD_BURN_RATE,
    DD_RISK_INCREASE,
    EXPLOIT_POSITION_GAIN,
    EXPLOIT_RISK_INCREASE,
    SURPLUS_BASE,
    SURPLUS_STREAK_BONUS,
)

if TYPE_CHECKING:
    from brinksmanship.models.state import GameState


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

    ENFORCES STRICT ZERO-SUM: Position changes must sum to zero for all outcomes.
    """

    matrix_type: MatrixType
    cc: OutcomeDeltaBounds  # Both cooperate / (A, A)
    cd: OutcomeDeltaBounds  # Row cooperates, Col defects / (A, B)
    dc: OutcomeDeltaBounds  # Row defects, Col cooperates / (B, A)
    dd: OutcomeDeltaBounds  # Both defect / (B, B)

    def __post_init__(self) -> None:
        """Validate that all outcomes are strictly zero-sum for position."""
        for outcome_name, bounds in [
            ("CC", self.cc),
            ("CD", self.cd),
            ("DC", self.dc),
            ("DD", self.dd),
        ]:
            pos_a_mid = bounds.pos_a.midpoint()
            pos_b_mid = bounds.pos_b.midpoint()
            pos_sum = pos_a_mid + pos_b_mid
            if abs(pos_sum) > 0.01:  # Allow tiny floating point errors
                raise ValueError(
                    f"{self.matrix_type.value} {outcome_name} violates zero-sum: "
                    f"pos_a={pos_a_mid:.2f} + pos_b={pos_b_mid:.2f} = {pos_sum:.2f}"
                )


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
# STRICTLY ZERO-SUM POSITION: Only exploitation changes position.
# - CC: Mutual cooperation - NO position change, risk decreases (incentive to cooperate)
# - CD/DC: Exploitation - exploiter gains what victim loses (zero-sum)
# - DD: Mutual defection - NO position change, risk spikes (standoff)
#
# The strategic logic:
# - Cooperate = safe from escalation but vulnerable to exploitation
# - Defect = safe from exploitation but increases mutual risk
# - The temptation payoff comes from exploiting a cooperator
# - The punishment for mutual defection is RISK, not position loss
#
# Ordinal (for position): T=0.7 > R=0 > P=0 > S=-0.7
# This means T > R but R = P (not strictly valid PD for position alone)
# However, when considering RISK, the ordinal makes sense:
# - CC: pos=0, risk=-0.5 (good)
# - DD: pos=0, risk=+2.0 (bad)
# So R > P when you factor in risk consequences.
PD_DELTA_TEMPLATE = StateDeltaTemplate(
    matrix_type=MatrixType.PRISONERS_DILEMMA,
    cc=_outcome_bounds(
        pos_a=(0.0, 0.0), pos_b=(0.0, 0.0), risk=(-0.6, -0.4)
    ),  # R: No position change, risk -0.5 (cooperation reduces danger)
    cd=_outcome_bounds(
        pos_a=(-0.8, -0.6), pos_b=(0.6, 0.8), risk=(0.6, 1.0)
    ),  # ZERO-SUM: A=-0.7, B=+0.7, risk +0.8 (exploitation punished by risk)
    dc=_outcome_bounds(
        pos_a=(0.6, 0.8), pos_b=(-0.8, -0.6), risk=(0.6, 1.0)
    ),  # ZERO-SUM: A=+0.7, B=-0.7, risk +0.8 (exploitation punished by risk)
    dd=_outcome_bounds(
        pos_a=(0.0, 0.0),
        pos_b=(0.0, 0.0),
        risk=(1.8, 2.2),
    ),  # P: No position change, risk +2.0 (standoff - very dangerous)
)

# Deadlock (T > P > R > S)
# Both prefer mutual defection - DD is stable and preferred
# STRICTLY ZERO-SUM: Risk differentiates outcomes
DEADLOCK_DELTA_TEMPLATE = StateDeltaTemplate(
    matrix_type=MatrixType.DEADLOCK,
    cc=_outcome_bounds(
        pos_a=(0.0, 0.0), pos_b=(0.0, 0.0), risk=(0.2, 0.5)
    ),  # Neither wants this - risk increases
    cd=_outcome_bounds(
        pos_a=(-0.8, -0.6), pos_b=(0.6, 0.8), risk=(0.3, 0.7)
    ),  # ZERO-SUM: A=-0.7, B=+0.7
    dc=_outcome_bounds(
        pos_a=(0.6, 0.8), pos_b=(-0.8, -0.6), risk=(0.3, 0.7)
    ),  # ZERO-SUM: A=+0.7, B=-0.7
    dd=_outcome_bounds(
        pos_a=(0.0, 0.0), pos_b=(0.0, 0.0), risk=(-0.5, -0.2)
    ),  # Preferred by both - risk decreases
)

# Harmony (R > T > S > P)
# Cooperation dominates - CC is best for everyone
# STRICTLY ZERO-SUM: Risk differentiates outcomes
# For row player A: R=CC > T=DC > S=CD > P=DD
HARMONY_DELTA_TEMPLATE = StateDeltaTemplate(
    matrix_type=MatrixType.HARMONY,
    cc=_outcome_bounds(
        pos_a=(0.0, 0.0), pos_b=(0.0, 0.0), risk=(-0.8, -0.5)
    ),  # R: Best outcome - big risk decrease
    cd=_outcome_bounds(
        pos_a=(-0.4, -0.2), pos_b=(0.2, 0.4), risk=(-0.2, 0.2)
    ),  # S: ZERO-SUM A=-0.3, B=+0.3
    dc=_outcome_bounds(
        pos_a=(0.2, 0.4), pos_b=(-0.4, -0.2), risk=(-0.2, 0.2)
    ),  # T: ZERO-SUM A=+0.3, B=-0.3
    dd=_outcome_bounds(
        pos_a=(0.0, 0.0), pos_b=(0.0, 0.0), risk=(0.8, 1.2)
    ),  # P: Worst - big risk increase
)

# Chicken (T > R > S > P)
# STRICTLY ZERO-SUM POSITION: Only exploitation changes position.
# - Dove-Dove: Both back down, NO position change, risk decreases significantly
# - Hawk-Dove: Hawk wins, Dove loses (zero-sum position change)
# - Hawk-Hawk: CRASH - NO position change but MASSIVE risk spike
#
# The strategic logic:
# - Swerving is "safe" but vulnerable to hawks
# - Going straight risks catastrophic crash if opponent doesn't swerve
# - The incentive to swerve comes from RISK consequences, not position
CHICKEN_DELTA_TEMPLATE = StateDeltaTemplate(
    matrix_type=MatrixType.CHICKEN,
    cc=_outcome_bounds(
        pos_a=(0.0, 0.0), pos_b=(0.0, 0.0), risk=(-0.8, -0.3)
    ),  # Both swerve: No position change, risk decreases
    cd=_outcome_bounds(
        pos_a=(-0.6, -0.4), pos_b=(0.4, 0.6), risk=(0.3, 0.8)
    ),  # Row swerves: ZERO-SUM A=-0.5, B=+0.5
    dc=_outcome_bounds(
        pos_a=(0.4, 0.6), pos_b=(-0.6, -0.4), risk=(0.3, 0.8)
    ),  # Col swerves: ZERO-SUM A=+0.5, B=-0.5
    dd=_outcome_bounds(
        pos_a=(0.0, 0.0),
        pos_b=(0.0, 0.0),
        risk=(1.8, 2.2),
    ),  # CRASH: No position change, risk +2.0 (catastrophic)
)

# Volunteer's Dilemma (F > W > D)
# Someone must volunteer or everyone loses
# STRICTLY ZERO-SUM: Free-rider gains what volunteer loses
VOLUNTEERS_DILEMMA_DELTA_TEMPLATE = StateDeltaTemplate(
    matrix_type=MatrixType.VOLUNTEERS_DILEMMA,
    cc=_outcome_bounds(
        pos_a=(0.0, 0.0), pos_b=(0.0, 0.0), risk=(-0.5, -0.2)
    ),  # Both volunteer - wasteful but safe
    cd=_outcome_bounds(
        pos_a=(-0.5, -0.3), pos_b=(0.3, 0.5), risk=(-0.4, -0.1)
    ),  # ZERO-SUM: A volunteers (-0.4), B free-rides (+0.4)
    dc=_outcome_bounds(
        pos_a=(0.3, 0.5), pos_b=(-0.5, -0.3), risk=(-0.4, -0.1)
    ),  # ZERO-SUM: B volunteers (-0.4), A free-rides (+0.4)
    dd=_outcome_bounds(
        pos_a=(0.0, 0.0), pos_b=(0.0, 0.0), risk=(1.3, 1.7)
    ),  # Disaster - nobody volunteers, risk spikes
)

# War of Attrition (Continue/Quit)
# Costly conflict - mutual continue is expensive
# STRICTLY ZERO-SUM: Winner gains what loser loses
WAR_OF_ATTRITION_DELTA_TEMPLATE = StateDeltaTemplate(
    matrix_type=MatrixType.WAR_OF_ATTRITION,
    cc=_outcome_bounds(
        pos_a=(0.0, 0.0), pos_b=(0.0, 0.0), risk=(0.8, 1.2)
    ),  # Both continue - costly, risk increases
    cd=_outcome_bounds(
        pos_a=(0.6, 0.8), pos_b=(-0.8, -0.6), risk=(-0.3, 0.0)
    ),  # ZERO-SUM: A wins (+0.7), B loses (-0.7)
    dc=_outcome_bounds(
        pos_a=(-0.8, -0.6), pos_b=(0.6, 0.8), risk=(-0.3, 0.0)
    ),  # ZERO-SUM: B wins (+0.7), A loses (-0.7)
    dd=_outcome_bounds(
        pos_a=(0.0, 0.0), pos_b=(0.0, 0.0), risk=(-0.5, -0.2)
    ),  # Both quit - status quo, slight risk decrease
)

# Pure Coordination (Match > Mismatch)
# Matching is good, mismatching is bad, but symmetric
# STRICTLY ZERO-SUM: No position changes - only risk matters
PURE_COORDINATION_DELTA_TEMPLATE = StateDeltaTemplate(
    matrix_type=MatrixType.PURE_COORDINATION,
    cc=_outcome_bounds(
        pos_a=(0.0, 0.0), pos_b=(0.0, 0.0), risk=(-0.5, -0.2)
    ),  # Match on A - risk decreases
    cd=_outcome_bounds(
        pos_a=(0.0, 0.0), pos_b=(0.0, 0.0), risk=(0.3, 0.6)
    ),  # Mismatch - risk increases
    dc=_outcome_bounds(
        pos_a=(0.0, 0.0), pos_b=(0.0, 0.0), risk=(0.3, 0.6)
    ),  # Mismatch - risk increases
    dd=_outcome_bounds(
        pos_a=(0.0, 0.0), pos_b=(0.0, 0.0), risk=(-0.5, -0.2)
    ),  # Match on B - risk decreases
)

# Stag Hunt (R > T > P > S)
# - Stag-Stag: Best payoff-dominant equilibrium
# - Hare-Hare: Safe risk-dominant equilibrium
# - Mixed: Stag hunter fails
# STRICTLY ZERO-SUM: Opportunist gains at failed cooperator's expense
STAG_HUNT_DELTA_TEMPLATE = StateDeltaTemplate(
    matrix_type=MatrixType.STAG_HUNT,
    cc=_outcome_bounds(
        pos_a=(0.0, 0.0), pos_b=(0.0, 0.0), risk=(-0.8, -0.5)
    ),  # Stag-Stag: best - big risk decrease
    cd=_outcome_bounds(
        pos_a=(-0.6, -0.4), pos_b=(0.4, 0.6), risk=(0.2, 0.5)
    ),  # ZERO-SUM: A fails (-0.5), B opportunist (+0.5)
    dc=_outcome_bounds(
        pos_a=(0.4, 0.6), pos_b=(-0.6, -0.4), risk=(0.2, 0.5)
    ),  # ZERO-SUM: B fails (-0.5), A opportunist (+0.5)
    dd=_outcome_bounds(
        pos_a=(0.0, 0.0), pos_b=(0.0, 0.0), risk=(-0.1, 0.1)
    ),  # Hare-Hare: safe but boring, neutral risk
)

# Battle of the Sexes (Coord > Miscoord with preference asymmetry)
# STRICTLY ZERO-SUM: Coordination point favors one player over the other
BATTLE_OF_SEXES_DELTA_TEMPLATE = StateDeltaTemplate(
    matrix_type=MatrixType.BATTLE_OF_SEXES,
    cc=_outcome_bounds(
        pos_a=(0.2, 0.4), pos_b=(-0.4, -0.2), risk=(-0.4, -0.1)
    ),  # ZERO-SUM: Row's preferred (+0.3/-0.3), risk decreases
    cd=_outcome_bounds(
        pos_a=(0.0, 0.0), pos_b=(0.0, 0.0), risk=(0.3, 0.6)
    ),  # Mismatch - no position change, risk increases
    dc=_outcome_bounds(
        pos_a=(0.0, 0.0), pos_b=(0.0, 0.0), risk=(0.3, 0.6)
    ),  # Mismatch - no position change, risk increases
    dd=_outcome_bounds(
        pos_a=(-0.4, -0.2), pos_b=(0.2, 0.4), risk=(-0.4, -0.1)
    ),  # ZERO-SUM: Col's preferred (-0.3/+0.3), risk decreases
)

# Leader (G > H > B > C)
# One should lead, one should follow
# STRICTLY ZERO-SUM: Leader gains slight advantage over follower
LEADER_DELTA_TEMPLATE = StateDeltaTemplate(
    matrix_type=MatrixType.LEADER,
    cc=_outcome_bounds(
        pos_a=(0.0, 0.0), pos_b=(0.0, 0.0), risk=(0.3, 0.6)
    ),  # Both follow (stuck) - risk increases
    cd=_outcome_bounds(
        pos_a=(-0.2, 0.0), pos_b=(0.0, 0.2), risk=(-0.4, -0.1)
    ),  # ZERO-SUM: Col leads (+0.1), A follows (-0.1)
    dc=_outcome_bounds(
        pos_a=(0.0, 0.2), pos_b=(-0.2, 0.0), risk=(-0.4, -0.1)
    ),  # ZERO-SUM: Row leads (+0.1), B follows (-0.1)
    dd=_outcome_bounds(
        pos_a=(0.0, 0.0), pos_b=(0.0, 0.0), risk=(0.8, 1.2)
    ),  # Both lead (clash) - big risk spike
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
# STRICTLY ZERO-SUM: Cheater gains/loses what Inspector loses/gains
INSPECTION_GAME_DELTA_TEMPLATE = StateDeltaTemplate(
    matrix_type=MatrixType.INSPECTION_GAME,
    cc=_outcome_bounds(
        pos_a=(-0.1, 0.1), pos_b=(-0.1, 0.1), risk=(-0.2, 0.1)
    ),  # Inspect+Comply: slight cost to inspector, neutral
    cd=_outcome_bounds(
        pos_a=(0.4, 0.6), pos_b=(-0.6, -0.4), risk=(0.5, 0.8)
    ),  # ZERO-SUM: Caught cheating - inspector gains (+0.5), cheater loses (-0.5)
    dc=_outcome_bounds(
        pos_a=(0.0, 0.0), pos_b=(0.0, 0.0), risk=(-0.3, 0.0)
    ),  # Trust+Comply: status quo, slight risk decrease
    dd=_outcome_bounds(
        pos_a=(-0.6, -0.4), pos_b=(0.4, 0.6), risk=(0.3, 0.6)
    ),  # ZERO-SUM: Exploited - inspector loses (-0.5), cheater gains (+0.5)
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

# Security Dilemma (Same structure as PD with defensive interpretation)
# STRICTLY ZERO-SUM POSITION: Same as PD template
# - CC (mutual disarm): No position change, risk decreases
# - CD/DC (arms race): exploiter gains what victim loses
# - DD (arms race): No position change, risk spikes (dangerous standoff)
SECURITY_DILEMMA_DELTA_TEMPLATE = StateDeltaTemplate(
    matrix_type=MatrixType.SECURITY_DILEMMA,
    cc=_outcome_bounds(
        pos_a=(0.0, 0.0), pos_b=(0.0, 0.0), risk=(-0.6, -0.4)
    ),  # R: Mutual disarm, no position change, risk -0.5
    cd=_outcome_bounds(
        pos_a=(-0.8, -0.6), pos_b=(0.6, 0.8), risk=(0.6, 1.0)
    ),  # ZERO-SUM: A=-0.7, B=+0.7, risk +0.8
    dc=_outcome_bounds(
        pos_a=(0.6, 0.8), pos_b=(-0.8, -0.6), risk=(0.6, 1.0)
    ),  # ZERO-SUM: A=+0.7, B=-0.7, risk +0.8
    dd=_outcome_bounds(
        pos_a=(0.0, 0.0),
        pos_b=(0.0, 0.0),
        risk=(1.8, 2.2),
    ),  # P: Arms race standoff, no position change, risk +2.0
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
    """Validate Prisoner's Dilemma ordinal constraint: T > R >= P > S.

    With strictly zero-sum positions, CC and DD both have pos=0.
    The constraint becomes T > R >= P > S where R = P = 0.
    The R vs P distinction comes from RISK, not position:
    - R (CC): risk decreases
    - P (DD): risk increases dramatically

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
    if not (r >= p):  # Changed from > to >= since R=P=0 in zero-sum model
        errors.append(f"R >= P violated: R={r:.2f}, P={p:.2f}")
    if not (p > s):
        errors.append(f"P > S violated: P={p:.2f}, S={s:.2f}")

    return len(errors) == 0, errors


def validate_chicken_ordinal_consistency(template: StateDeltaTemplate) -> tuple[bool, list[str]]:
    """Validate Chicken ordinal constraint: T > R >= S > P.

    With strictly zero-sum positions, CC and DD both have pos=0.
    The constraint becomes T > R >= S > P where R = P = 0.
    The key distinction is:
    - R (CC): both swerve, risk decreases (good)
    - P (DD): crash, risk spikes (catastrophic)

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
    if not (r >= s):  # Changed from > to >= for zero-sum model
        errors.append(f"R >= S violated: R={r:.2f}, S={s:.2f}")
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


# =============================================================================
# Surplus Mechanics
# =============================================================================


def apply_surplus_effects(state: "GameState", outcome: str) -> "GameState":
    """Apply surplus mechanics based on outcome.

    Implements the Joint Investment model from GAME_MANUAL.md Section 3.4.
    This function modifies the state in place and returns it.

    Args:
        state: Current game state (modified in place)
        outcome: One of "CC", "CD", "DC", "DD"

    Returns:
        The modified game state

    Raises:
        ValueError: If outcome is not one of CC, CD, DC, DD

    Outcome effects:
        CC (Mutual Cooperation):
            - Creates new surplus scaled by cooperation streak
            - Increments cooperation streak
            - Reduces risk

        CD (A Cooperates, B Defects):
            - B captures portion of accumulated surplus
            - Position shifts toward B
            - Streak resets, risk increases

        DC (A Defects, B Cooperates):
            - A captures portion of accumulated surplus
            - Position shifts toward A
            - Streak resets, risk increases

        DD (Mutual Defection):
            - Surplus is partially destroyed (deadweight loss)
            - No position change
            - Streak resets, risk spikes
    """
    outcome_upper = outcome.upper()

    if outcome_upper == "CC":
        # Create new surplus - scales with cooperation streak
        new_surplus = SURPLUS_BASE * (1.0 + SURPLUS_STREAK_BONUS * state.cooperation_streak)
        state.cooperation_surplus = state.cooperation_surplus + new_surplus
        state.cooperation_streak = state.cooperation_streak + 1

        # Risk decreases (situation safer)
        new_risk = state.risk_level - CC_RISK_REDUCTION
        state.risk_level = max(0.0, new_risk)

    elif outcome_upper == "CD":
        # B captures portion of surplus
        captured = state.cooperation_surplus * CAPTURE_RATE
        state.surplus_captured_b = state.surplus_captured_b + captured
        state.cooperation_surplus = state.cooperation_surplus - captured

        # Position shift toward B
        state.position_b = min(10.0, state.player_b.position + EXPLOIT_POSITION_GAIN)
        state.position_a = max(0.0, state.player_a.position - EXPLOIT_POSITION_GAIN)

        # Reset streak, increase risk
        state.cooperation_streak = 0
        state.risk_level = min(10.0, state.risk_level + EXPLOIT_RISK_INCREASE)

    elif outcome_upper == "DC":
        # A captures portion of surplus
        captured = state.cooperation_surplus * CAPTURE_RATE
        state.surplus_captured_a = state.surplus_captured_a + captured
        state.cooperation_surplus = state.cooperation_surplus - captured

        # Position shift toward A
        state.position_a = min(10.0, state.player_a.position + EXPLOIT_POSITION_GAIN)
        state.position_b = max(0.0, state.player_b.position - EXPLOIT_POSITION_GAIN)

        # Reset streak, increase risk
        state.cooperation_streak = 0
        state.risk_level = min(10.0, state.risk_level + EXPLOIT_RISK_INCREASE)

    elif outcome_upper == "DD":
        # Surplus is partially destroyed (deadweight loss)
        state.cooperation_surplus = state.cooperation_surplus * (1.0 - DD_BURN_RATE)

        # No position change

        # Reset streak, spike risk
        state.cooperation_streak = 0
        state.risk_level = min(10.0, state.risk_level + DD_RISK_INCREASE)

    else:
        raise ValueError(f"Invalid outcome: {outcome}. Must be CC, CD, DC, or DD")

    return state
