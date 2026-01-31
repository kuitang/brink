"""Game balance parameters for Brinksmanship.

This module is the SINGLE SOURCE OF TRUTH for all tunable game constants.
See GAME_MANUAL.md Appendix C for detailed documentation.

Parameter Categories:
- Surplus Creation: How cooperation creates value
- Exploitation: How defection captures value
- Risk: How actions affect crisis probability
- Settlement: Negotiation mechanics

Usage:
    from brinksmanship.parameters import SURPLUS_BASE, CAPTURE_RATE

Note: These parameters are NOT fixed constants. They should be tuned through
simulation to achieve balanced gameplay. Each parameter includes analysis
notes and tuning guidance.
"""

# =============================================================================
# SURPLUS CREATION PARAMETERS
# =============================================================================

SURPLUS_BASE = 2.0
"""VP created per mutual cooperation (CC outcome).

Current: 2.0

Analysis:
    With 14-turn max game and perfect cooperation:
    - No streak bonus: 14 x 2.0 = 28 VP total surplus
    - With streak bonus: ~45 VP total surplus (see SURPLUS_STREAK_BONUS)
    - This is significant vs 100 VP position baseline but not overwhelming

Tuning:
    - If settlement rate too LOW: increase (more surplus = more to negotiate over)
    - If exploitation too WEAK: increase (bigger pool = bigger captures)
    - If total value > 150 average: decrease (pie growing too fast)
    - Run: "surplus creation sweep" simulation varying 1.5 to 3.0

Related: SURPLUS_STREAK_BONUS
"""

SURPLUS_STREAK_BONUS = 0.1
"""Additional surplus multiplier per consecutive cooperation (streak level).

Current: 0.1 (10% bonus per consecutive CC)

Analysis:
    Creates compounding value for sustained cooperation.
    Surplus per CC at different streak levels:
    - Streak 0:  2.0 VP
    - Streak 5:  3.0 VP
    - Streak 10: 4.0 VP

    This rewards patience but creates "when to defect" tension.
    The longer you cooperate, the more valuable defection becomes.

Tuning:
    - If late-game too static: increase (more reward for holding out)
    - If early defection never happens: decrease (reduce late-game bonus)
    - Should interact with STREAK_PROTECTION_RATE if enabled (see below)
    - Run: "streak bonus sensitivity" simulation at 0.05, 0.1, 0.15

Related: SURPLUS_BASE, STREAK_PROTECTION_RATE (reserve)
"""


# =============================================================================
# EXPLOITATION PARAMETERS
# =============================================================================

CAPTURE_RATE = 0.4
"""Fraction of cooperation surplus captured on exploitation (CD/DC outcome).

Current: 0.4 (40% of pool)

Analysis:
    This is the TEMPTATION payoff in game theory terms.
    - Too high: exploitation always dominates (chicken dynamics return)
    - Too low: no reason to ever defect (boring cooperation fest)
    - 40% means you need 2-3 exploitations to drain the pool

    Capture values at different game states:
    - With ~20 surplus at turn 8: capture = 8 VP (significant but not dominant)
    - With ~45 surplus at turn 14: capture = 18 VP (very strong)

Tuning:
    - If "always cooperate" dominates: increase toward 0.5
    - If "always defect" dominates: decrease toward 0.3
    - If "late defection" dominates: add STREAK_PROTECTION (see reserve params)
    - Run: "exploitation timing analysis" simulation

Related: EXPLOIT_POSITION_GAIN, STREAK_PROTECTION_RATE (reserve)
"""

EXPLOIT_POSITION_GAIN = 0.7
"""Position shift on exploitation (exploiter gains, victim loses).

Current: 0.7

Analysis:
    Zero-sum position transfer (exploiter +0.7, victim -0.7).
    Affects final VP calculation: (position / total_position) x 100

    Starting positions are 5.0/5.0:
    - Single exploit: 5.7/4.3 = 57/43 split (14 VP difference)
    - Two exploits: 6.4/3.6 = 64/36 split (28 VP difference)

Tuning:
    - If exploitation feels weak: increase toward 1.0
    - If one defection is decisive: decrease toward 0.5
    - Position matters less if surplus is large (settlement dominates)

Related: CAPTURE_RATE
"""


# =============================================================================
# RISK PARAMETERS
# =============================================================================

CC_RISK_REDUCTION = 0.5
"""Risk level decrease on mutual cooperation (CC outcome).

Current: 0.5

Analysis:
    Cooperation de-escalates the situation.
    Starting risk is 2.0:
    - 4 consecutive CCs bring risk to 0 (completely safe)
    - Creates breathing room for negotiation

    Risk progression with sustained cooperation:
    - Turn 1: 2.0 -> 1.5
    - Turn 2: 1.5 -> 1.0
    - Turn 3: 1.0 -> 0.5
    - Turn 4: 0.5 -> 0.0

Tuning:
    - If crisis termination too frequent: increase (faster de-escalation)
    - If risk feels meaningless: decrease

Related: EXPLOIT_RISK_INCREASE, DD_RISK_INCREASE
"""

EXPLOIT_RISK_INCREASE = 0.8
"""Risk level increase on exploitation (CD/DC outcome).

Current: 0.8

Analysis:
    Exploitation is risky but not catastrophic.
    - From starting risk 2.0, need ~10 exploitations to hit risk=10
    - But mixed with DD outcomes, escalation is faster

    The asymmetric risk (0.8 vs 1.8 for DD) means:
    - Successful exploitation is "safer" than mutual defection
    - But repeated exploitation still escalates dangerously

Tuning:
    - If exploitation feels too safe: increase toward 1.2
    - If exploitation feels too punishing: decrease toward 0.5

Related: CC_RISK_REDUCTION, DD_RISK_INCREASE
"""

DD_RISK_INCREASE = 1.8
"""Risk level increase on mutual defection (DD outcome).

Current: 1.8

Analysis:
    Mutual defection is DANGEROUS - the stick in the game.
    - From starting risk 2.0, only 4-5 DDs to hit risk=10 (mutual destruction)
    - This makes DD the worst outcome for both players (Chicken logic)
    - Mutual destruction = 0 VP for BOTH players (total loss)

    Risk progression with sustained mutual defection:
    - Turn 1: 2.0 -> 3.8
    - Turn 2: 3.8 -> 5.6
    - Turn 3: 5.6 -> 7.4
    - Turn 4: 7.4 -> 9.2
    - Turn 5: 9.2 -> 10.0 = MUTUAL DESTRUCTION

Tuning:
    - TARGET: Mutual destruction rate should be 10-20% of games
    - If MD rate > 20%: decrease toward 1.5
    - If MD rate < 10%: increase toward 2.0
    - Current default (1.8) calibrated for ~15-18% MD rate
    - Remember: MD is 0,0 VP (worst outcome) - players should fear it

Related: DD_BURN_RATE, CC_RISK_REDUCTION
"""

DD_BURN_RATE = 0.2
"""Fraction of cooperation surplus destroyed on mutual defection (DD outcome).

Current: 0.2 (20% destroyed)

Analysis:
    Deadweight loss from conflict - value destroyed, not captured.
    Unlike exploitation (which transfers value), DD destroys it.

    Surplus destruction over multiple DDs:
    - After 1 DD: 80% remains
    - After 2 DDs: 64% remains
    - After 3 DDs: 51% remains (roughly half destroyed)
    - After 5 DDs: 33% remains

    Creates strong incentive to avoid DD even when not cooperating.
    A sequence of DDs rapidly erodes the value both players built.

Tuning:
    - If players don't fear DD enough: increase toward 0.3
    - If surplus disappears too fast: decrease toward 0.15

Related: DD_RISK_INCREASE
"""


# =============================================================================
# SETTLEMENT PARAMETERS
# =============================================================================

REJECTION_BASE_PENALTY = 1.5
"""Base risk penalty added per settlement rejection.

Current: 1.5

Analysis:
    Failed negotiations should be costly to prevent frivolous offers.
    - Old value (1.0) was too gentle - players could reject freely
    - At 1.5, a full rejection cycle (3 rejections) is very costly

    Cumulative risk from rejections (with REJECTION_ESCALATION=0.5):
    - 1st rejection: +1.5 risk
    - 2nd rejection: +2.25 risk
    - 3rd rejection: +3.0 risk
    - Total: +6.75 risk (can push stable situation into crisis)

Tuning:
    - If settlement attempts feel risk-free: increase toward 2.0
    - If players never attempt settlement: decrease toward 1.0
    - Run: "settlement negotiation" simulation tracking rejection patterns

Related: REJECTION_ESCALATION
"""

REJECTION_ESCALATION = 0.5
"""Multiplier for how much rejection penalty increases per subsequent rejection.

Current: 0.5 (50% increase per rejection)

Analysis:
    Escalating penalties create urgency to reach agreement.
    Penalty formula: base * (1.0 + escalation * (rejection_number - 1))

    With base=1.5 and escalation=0.5:
    - 1st rejection: 1.5 * 1.0 = 1.5 risk
    - 2nd rejection: 1.5 * 1.5 = 2.25 risk
    - 3rd rejection: 1.5 * 2.0 = 3.0 risk

    This pressure curve encourages:
    - Reasonable opening offers (to avoid rejection)
    - Quicker convergence in counter-offer exchanges
    - Avoiding the 3rd rejection (which ends negotiation AND adds 3.0 risk)

Tuning:
    - If players drag out negotiations: increase toward 0.75
    - If negotiations feel too pressured: decrease toward 0.25

Related: REJECTION_BASE_PENALTY
"""

SETTLEMENT_MIN_TURN = 5
"""Minimum turn number before settlement becomes available.

Current: 5 (settlement available from turn 5 onwards)

Analysis:
    Prevents premature settlement before meaningful game develops.
    - Turns 1-4 (Act I): Opening postures, early signaling
    - Turn 5+ (Act II): Settlement becomes available

    This ensures:
    - Players must engage with the core mechanics first
    - Some surplus has accumulated before negotiation
    - Position has had time to shift from starting values

Tuning:
    - If games feel too short: increase toward 6-7
    - If games drag without settlement option: decrease toward 4

Related: SETTLEMENT_MIN_STABILITY
"""

SETTLEMENT_MIN_STABILITY = 2.0
"""Minimum stability level required to propose settlement.

Current: 2.0 (settlement blocked if stability <= 2.0)

Analysis:
    Erratic behavior prevents negotiation - you can't negotiate with chaos.
    Stability starts at 5.0 and can range from 1.0 to 10.0.

    Getting blocked from settlement signals:
    - Too much action switching has occurred
    - Players need to establish predictable patterns first

    To regain settlement access:
    - Consistent action choices (both consistent = +1.5 stability)
    - Stability naturally decays toward neutral (x0.8 + 1.0 per turn)

Tuning:
    - If settlement always available: increase toward 3.0
    - If settlement too often blocked: decrease toward 1.5

Related: SETTLEMENT_MIN_TURN
"""


# =============================================================================
# RESERVE PARAMETERS (Commented out by default)
# =============================================================================
#
# These parameters are NOT active by default. Add them only if simulation
# reveals specific problems. See GAME_MANUAL.md Appendix C.5 for details.
#
# -----------------------------------------------------------------------------
# STREAK PROTECTION
# -----------------------------------------------------------------------------
# The problem: Without protection, late-game defection can be extremely
# profitable because the surplus pool is largest at the end.
#
# Example without protection:
#   Turn 14 defection: 40% of ~45 surplus = 18 VP from one action!
#
# Streak protection models "relationship capital" - the longer you cooperate,
# the harder it is to exploit the accumulated trust. Think of it as
# institutional resistance to betrayal.
#
# Formula:
#   effective_rate = CAPTURE_RATE * (1.0 - STREAK_PROTECTION_RATE * streak / MAX_PROTECTED_STREAK)
#
# Example with 50% protection enabled (STREAK_PROTECTION_RATE = 0.5):
#   Turn 3:  40% * 1.0 = 40% capture (no protection, streak too short)
#   Turn 10: 40% * 0.5 = 20% capture (50% protected by streak)
#   Turn 14: 40% * 0.5 = 20% capture (max protection reached)
#
# This makes mid-game the "sweet spot" for defection rather than late-game.
#
# Only enable if "Exploitation Timing Analysis" simulation shows turn 12+
# as optimal defection timing.

# STREAK_PROTECTION_RATE = 0.0  # Disabled by default. Enable at 0.5 if needed.
"""Fraction of capture protected by cooperation streak (0.0 = disabled).

Reserve parameter - only enable if late-defection dominates.

Values:
    - 0.0: No protection (default)
    - 0.5: 50% protection at max streak
    - 1.0: Full protection (exploitation impossible at max streak)
"""

# MAX_PROTECTED_STREAK = 10
"""Streak level at which maximum protection is reached.

Reserve parameter - only relevant if STREAK_PROTECTION_RATE > 0.

Analysis:
    With MAX_PROTECTED_STREAK=10:
    - Streak 5 = 50% of max protection
    - Streak 10+ = full protection effect
"""

# -----------------------------------------------------------------------------
# CAPTURE DECAY (Alternative to streak protection)
# -----------------------------------------------------------------------------
# Alternative mechanic: capture rate decays over game time regardless of streak.
# This is simpler but less thematically coherent than streak protection.
#
# Formula:
#   effective_rate = max(0.1, CAPTURE_RATE - CAPTURE_DECAY_PER_TURN * turn)
#
# Example at 0.02 decay:
#   Turn 1:  40%
#   Turn 5:  30%
#   Turn 10: 20%
#   Turn 15: 10% (floor)

# CAPTURE_DECAY_PER_TURN = 0.0  # Disabled by default
"""Capture rate reduction per turn (0.0 = disabled).

Reserve parameter - alternative to STREAK_PROTECTION_RATE.

Values:
    - 0.0: No decay (default)
    - 0.02: 2% reduction per turn (reaches floor by turn 15)
"""


# =============================================================================
# DERIVED CONSTANTS (Computed from parameters)
# =============================================================================

def calculate_surplus_for_streak(streak: int) -> float:
    """Calculate surplus generated for a given cooperation streak level.

    Args:
        streak: Number of consecutive CC outcomes (0 = first CC)

    Returns:
        VP created for this CC outcome

    Example:
        >>> calculate_surplus_for_streak(0)
        2.0
        >>> calculate_surplus_for_streak(5)
        3.0
    """
    return SURPLUS_BASE * (1.0 + SURPLUS_STREAK_BONUS * streak)


def calculate_max_theoretical_surplus(max_turns: int = 14) -> float:
    """Calculate maximum possible surplus with perfect cooperation.

    Args:
        max_turns: Maximum game length (default 14)

    Returns:
        Total VP that could be created with CC every turn

    Example:
        >>> calculate_max_theoretical_surplus(14)
        45.5
    """
    total = 0.0
    for streak in range(max_turns):
        total += calculate_surplus_for_streak(streak)
    return total


def calculate_rejection_penalty(rejection_number: int) -> float:
    """Calculate risk penalty for a specific rejection in sequence.

    Args:
        rejection_number: Which rejection this is (1, 2, or 3)

    Returns:
        Risk penalty to apply

    Example:
        >>> calculate_rejection_penalty(1)
        1.5
        >>> calculate_rejection_penalty(2)
        2.25
        >>> calculate_rejection_penalty(3)
        3.0
    """
    return REJECTION_BASE_PENALTY * (1.0 + REJECTION_ESCALATION * (rejection_number - 1))


def calculate_total_rejection_risk(num_rejections: int) -> float:
    """Calculate total risk accumulated from multiple rejections.

    Args:
        num_rejections: Number of rejections (1-3)

    Returns:
        Total risk penalty from all rejections

    Example:
        >>> calculate_total_rejection_risk(3)
        6.75
    """
    return sum(calculate_rejection_penalty(i) for i in range(1, num_rejections + 1))
