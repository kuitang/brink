"""Matrix definitions for Brinksmanship game theory structures.

This module implements the constructor pattern for game theory matrices.
Scenarios specify game type + parameters only; constructors guarantee valid
matrices by enforcing ordinal constraints. Nash equilibria are guaranteed
by the constraints themselves - no runtime computation needed.

See GAME_MANUAL.md Part II for game type specifications.
See ENGINEERING_DESIGN.md Milestone 1.2 for implementation details.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, field_validator, model_validator


class MatrixType(Enum):
    """All viable 2x2 game types.

    Categories from GAME_MANUAL.md:
    - Category A: Dominant Strategy Games (PD, Deadlock, Harmony)
    - Category B: Anti-Coordination Games (Chicken, Volunteers, War of Attrition)
    - Category C: Coordination Games (Pure Coord, Stag Hunt, BoS, Leader)
    - Category D: Zero-Sum/Info Games (Matching Pennies, Inspection, Recon)
    - Security Dilemma (same structure as PD)
    """

    # Category A: Dominant Strategy Games
    PRISONERS_DILEMMA = "prisoners_dilemma"
    DEADLOCK = "deadlock"
    HARMONY = "harmony"

    # Category B: Anti-Coordination Games
    CHICKEN = "chicken"
    VOLUNTEERS_DILEMMA = "volunteers_dilemma"
    WAR_OF_ATTRITION = "war_of_attrition"

    # Category C: Coordination Games
    PURE_COORDINATION = "pure_coordination"
    STAG_HUNT = "stag_hunt"
    BATTLE_OF_SEXES = "battle_of_sexes"
    LEADER = "leader"

    # Category D: Zero-Sum and Information Games
    MATCHING_PENNIES = "matching_pennies"
    INSPECTION_GAME = "inspection_game"
    RECONNAISSANCE = "reconnaissance"

    # Special variant (same structure as PD)
    SECURITY_DILEMMA = "security_dilemma"


@dataclass(frozen=True)
class StateDeltas:
    """State changes resulting from a matrix outcome.

    Represents changes to Position, Resources, and Risk for both players.
    These are applied after matrix resolution, scaled by act multiplier.

    Constraints from GAME_MANUAL.md Section 3.5:
    - Position: -1.5 to +1.5 per player per turn
    - Resource cost: 0 to 1.0 per player per turn
    - Risk: -1.0 to +2.0 shared per turn
    - Position changes are near-zero-sum: |pos_a + pos_b| <= 0.5
    """

    pos_a: float
    pos_b: float
    res_cost_a: float
    res_cost_b: float
    risk_delta: float

    def __post_init__(self) -> None:
        """Validate delta constraints."""
        if not -1.5 <= self.pos_a <= 1.5:
            raise ValueError(f"pos_a must be in [-1.5, 1.5], got {self.pos_a}")
        if not -1.5 <= self.pos_b <= 1.5:
            raise ValueError(f"pos_b must be in [-1.5, 1.5], got {self.pos_b}")
        if not 0.0 <= self.res_cost_a <= 1.0:
            raise ValueError(f"res_cost_a must be in [0, 1.0], got {self.res_cost_a}")
        if not 0.0 <= self.res_cost_b <= 1.0:
            raise ValueError(f"res_cost_b must be in [0, 1.0], got {self.res_cost_b}")
        if not -1.0 <= self.risk_delta <= 2.0:
            raise ValueError(f"risk_delta must be in [-1.0, 2.0], got {self.risk_delta}")
        if abs(self.pos_a + self.pos_b) > 0.5:
            raise ValueError(
                f"Position changes must be near-zero-sum: "
                f"|{self.pos_a} + {self.pos_b}| = {abs(self.pos_a + self.pos_b)} > 0.5"
            )


@dataclass(frozen=True)
class OutcomePayoffs:
    """Payoffs for a single outcome cell in the matrix.

    Contains both the raw payoff value and the associated state deltas.
    """

    payoff_a: float
    payoff_b: float
    deltas: StateDeltas


@dataclass(frozen=True)
class PayoffMatrix:
    """Complete payoff matrix for a 2x2 game.

    This is the output of constructors and is never serialized.
    Only (MatrixType, MatrixParameters) pairs persist in scenarios.

    Outcomes are indexed by (row_choice, col_choice):
    - cc: Both cooperate / Row A, Col A
    - cd: Row cooperates, Col defects / Row A, Col B
    - dc: Row defects, Col cooperates / Row B, Col A
    - dd: Both defect / Row B, Col B
    """

    matrix_type: MatrixType
    cc: OutcomePayoffs  # (Cooperate, Cooperate) or (A, A)
    cd: OutcomePayoffs  # (Cooperate, Defect) or (A, B)
    dc: OutcomePayoffs  # (Defect, Cooperate) or (B, A)
    dd: OutcomePayoffs  # (Defect, Defect) or (B, B)

    # Strategy labels for display
    row_labels: tuple[str, str] = ("Cooperate", "Defect")
    col_labels: tuple[str, str] = ("Cooperate", "Defect")

    def get_outcome(self, row_action: int, col_action: int) -> OutcomePayoffs:
        """Get outcome for given actions (0=first strategy, 1=second strategy)."""
        outcomes = [[self.cc, self.cd], [self.dc, self.dd]]
        return outcomes[row_action][col_action]


class MatrixParameters(BaseModel):
    """Parameters for constructing a payoff matrix.

    These parameters are stored in scenarios. The constructor uses them
    to build the actual PayoffMatrix at load time, guaranteeing validity.

    Global constraints:
    - scale > 0
    - position_weight + resource_weight + risk_weight == 1.0
    - All weights non-negative
    """

    model_config = ConfigDict(frozen=True)

    # Scale factor for all payoffs
    scale: float = 1.0

    # Weights for how payoffs translate to state deltas
    position_weight: float = 0.6
    resource_weight: float = 0.2
    risk_weight: float = 0.2

    # Game-specific parameters (used by different constructors)
    # PD-family parameters (T > R > P > S)
    temptation: float = 1.5  # T: defect against cooperator
    reward: float = 1.0  # R: mutual cooperation
    punishment: float = 0.3  # P: mutual defection
    sucker: float = 0.0  # S: cooperate against defector

    # Chicken-family parameters (T > R > S > P)
    # Uses temptation, reward, but with different S/P relationship
    swerve_payoff: float = 0.5  # S: swerve against hawk (better than crash)
    crash_payoff: float = -1.0  # P: mutual crash (worst)

    # Coordination game parameters
    coordination_bonus: float = 1.0  # Bonus for matching
    miscoordination_penalty: float = 0.0  # Penalty for not matching
    preference_a: float = 1.2  # Row player's preference for first equilibrium
    preference_b: float = 1.2  # Col player's preference for second equilibrium

    # Stag Hunt parameters (R > T > P > S)
    stag_payoff: float = 2.0  # R: mutual stag hunt
    hare_temptation: float = 1.5  # T: hunt hare while partner hunts stag
    hare_safe: float = 1.0  # P: mutual hare hunt
    stag_fail: float = 0.0  # S: hunt stag alone

    # Volunteer's Dilemma parameters (Free-ride > Work > Disaster)
    volunteer_cost: float = 0.3  # Cost of volunteering
    free_ride_bonus: float = 0.5  # Bonus for not volunteering when other does
    disaster_penalty: float = 1.0  # Penalty when nobody volunteers

    # Inspection/Recon parameters
    inspection_cost: float = 0.3  # Cost of inspecting
    cheat_gain: float = 0.5  # Gain from cheating successfully
    caught_penalty: float = 1.0  # Penalty for being caught cheating
    loss_if_exploited: float = 0.7  # Loss if trusting a cheater

    @field_validator("scale")
    @classmethod
    def validate_scale(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("scale must be positive")
        return v

    @field_validator(
        "position_weight",
        "resource_weight",
        "risk_weight",
    )
    @classmethod
    def validate_weights_non_negative(cls, v: float) -> float:
        if v < 0:
            raise ValueError("weights must be non-negative")
        return v

    @model_validator(mode="after")
    def validate_weights_sum(self) -> "MatrixParameters":
        total = self.position_weight + self.resource_weight + self.risk_weight
        if abs(total - 1.0) > 1e-6:
            raise ValueError(
                f"Weights must sum to 1.0, got {total} "
                f"({self.position_weight} + {self.resource_weight} + {self.risk_weight})"
            )
        return self


@runtime_checkable
class MatrixConstructor(Protocol):
    """Protocol for matrix constructors.

    Each game type has a constructor that enforces its ordinal constraints
    and builds a valid PayoffMatrix from parameters.
    """

    @staticmethod
    def build(params: MatrixParameters) -> PayoffMatrix:
        """Build a payoff matrix from parameters.

        The constructor guarantees the resulting matrix satisfies
        the game type's ordinal constraints.
        """
        ...

    @staticmethod
    def validate_params(params: MatrixParameters) -> None:
        """Validate that parameters satisfy game-specific constraints.

        Raises ValueError if constraints are violated.
        """
        ...


def _make_deltas(
    params: MatrixParameters,
    payoff_a: float,
    payoff_b: float,
    base_risk: float,
) -> StateDeltas:
    """Convert payoffs to state deltas using weights.

    Payoffs are normalized and distributed across position, resources, and risk
    according to the weights in params.
    """
    # Normalize payoffs by scale
    norm_a = payoff_a * params.scale
    norm_b = payoff_b * params.scale

    # Position changes based on relative payoff advantage
    # Near-zero-sum: one player's gain is roughly another's loss
    pos_diff = (norm_a - norm_b) * params.position_weight * 0.5
    pos_a = max(-1.5, min(1.5, pos_diff))
    pos_b = max(-1.5, min(1.5, -pos_diff))

    # Resource costs based on negative payoffs (costs)
    res_cost_a = max(0.0, min(1.0, -min(0, norm_a) * params.resource_weight))
    res_cost_b = max(0.0, min(1.0, -min(0, norm_b) * params.resource_weight))

    # Risk based on provided base risk, scaled by weight
    risk = max(-1.0, min(2.0, base_risk * params.risk_weight * 5))

    return StateDeltas(
        pos_a=pos_a,
        pos_b=pos_b,
        res_cost_a=res_cost_a,
        res_cost_b=res_cost_b,
        risk_delta=risk,
    )


class PrisonersDilemmaConstructor:
    """Constructor for Prisoner's Dilemma matrices.

    Ordinal constraint: T > R > P > S
    Where:
    - T (Temptation): Defect while other cooperates
    - R (Reward): Mutual cooperation
    - P (Punishment): Mutual defection
    - S (Sucker): Cooperate while other defects

    Guaranteed Nash Equilibrium: Unique (D, D)
    """

    @staticmethod
    def validate_params(params: MatrixParameters) -> None:
        """Validate T > R > P > S constraint."""
        t, r, p, s = params.temptation, params.reward, params.punishment, params.sucker
        if not (t > r > p > s):
            raise ValueError(f"Prisoner's Dilemma requires T > R > P > S, got T={t}, R={r}, P={p}, S={s}")

    @staticmethod
    def build(params: MatrixParameters) -> PayoffMatrix:
        """Build PD matrix with guaranteed (D,D) equilibrium."""
        PrisonersDilemmaConstructor.validate_params(params)

        t, r, p, s = params.temptation, params.reward, params.punishment, params.sucker

        return PayoffMatrix(
            matrix_type=MatrixType.PRISONERS_DILEMMA,
            cc=OutcomePayoffs(r, r, _make_deltas(params, r, r, -0.5)),  # Mutual coop
            cd=OutcomePayoffs(s, t, _make_deltas(params, s, t, 0.5)),  # Row exploited
            dc=OutcomePayoffs(t, s, _make_deltas(params, t, s, 0.5)),  # Col exploited
            dd=OutcomePayoffs(p, p, _make_deltas(params, p, p, 1.0)),  # Mutual defect
            row_labels=("Cooperate", "Defect"),
            col_labels=("Cooperate", "Defect"),
        )


class DeadlockConstructor:
    """Constructor for Deadlock matrices.

    Ordinal constraint: T > P > R > S
    Both players prefer mutual defection over mutual cooperation.
    No cooperative solution exists.

    Guaranteed Nash Equilibrium: Unique (D, D), Pareto optimal
    """

    @staticmethod
    def validate_params(params: MatrixParameters) -> None:
        """Validate T > P > R > S constraint."""
        t, r, p, s = params.temptation, params.reward, params.punishment, params.sucker
        if not (t > p > r > s):
            raise ValueError(f"Deadlock requires T > P > R > S, got T={t}, P={p}, R={r}, S={s}")

    @staticmethod
    def build(params: MatrixParameters) -> PayoffMatrix:
        """Build Deadlock matrix with guaranteed (D,D) equilibrium."""
        DeadlockConstructor.validate_params(params)

        t, r, p, s = params.temptation, params.reward, params.punishment, params.sucker

        return PayoffMatrix(
            matrix_type=MatrixType.DEADLOCK,
            cc=OutcomePayoffs(r, r, _make_deltas(params, r, r, 0.0)),
            cd=OutcomePayoffs(s, t, _make_deltas(params, s, t, 0.5)),
            dc=OutcomePayoffs(t, s, _make_deltas(params, t, s, 0.5)),
            dd=OutcomePayoffs(p, p, _make_deltas(params, p, p, 0.5)),  # Preferred outcome
            row_labels=("Cooperate", "Defect"),
            col_labels=("Cooperate", "Defect"),
        )


class HarmonyConstructor:
    """Constructor for Harmony matrices.

    Ordinal constraint: R > T > S > P
    Cooperation dominates for both players. No conflict.

    Guaranteed Nash Equilibrium: Unique (C, C)
    """

    @staticmethod
    def validate_params(params: MatrixParameters) -> None:
        """Validate R > T > S > P constraint."""
        t, r, p, s = params.temptation, params.reward, params.punishment, params.sucker
        if not (r > t > s > p):
            raise ValueError(f"Harmony requires R > T > S > P, got R={r}, T={t}, S={s}, P={p}")

    @staticmethod
    def build(params: MatrixParameters) -> PayoffMatrix:
        """Build Harmony matrix with guaranteed (C,C) equilibrium."""
        HarmonyConstructor.validate_params(params)

        t, r, p, s = params.temptation, params.reward, params.punishment, params.sucker

        return PayoffMatrix(
            matrix_type=MatrixType.HARMONY,
            cc=OutcomePayoffs(r, r, _make_deltas(params, r, r, -0.5)),  # Best for both
            cd=OutcomePayoffs(s, t, _make_deltas(params, s, t, 0.0)),
            dc=OutcomePayoffs(t, s, _make_deltas(params, t, s, 0.0)),
            dd=OutcomePayoffs(p, p, _make_deltas(params, p, p, 0.5)),  # Worst for both
            row_labels=("Cooperate", "Defect"),
            col_labels=("Cooperate", "Defect"),
        )


class ChickenConstructor:
    """Constructor for Chicken (Hawk-Dove) matrices.

    Ordinal constraint: T > R > S > P
    Where:
    - T: Win (be aggressive while other backs down)
    - R: Tie (both back down)
    - S: Lose (back down while other is aggressive)
    - P: Crash (both aggressive - worst outcome)

    Guaranteed Nash Equilibria: Two pure (C,D) and (D,C) plus mixed
    """

    @staticmethod
    def validate_params(params: MatrixParameters) -> None:
        """Validate T > R > S > P constraint for Chicken."""
        t = params.temptation
        r = params.reward
        s = params.swerve_payoff
        p = params.crash_payoff
        if not (t > r > s > p):
            raise ValueError(f"Chicken requires T > R > S > P, got T={t}, R={r}, S={s}, P={p}")

    @staticmethod
    def build(params: MatrixParameters) -> PayoffMatrix:
        """Build Chicken matrix with two pure equilibria."""
        ChickenConstructor.validate_params(params)

        t = params.temptation
        r = params.reward
        s = params.swerve_payoff
        p = params.crash_payoff

        return PayoffMatrix(
            matrix_type=MatrixType.CHICKEN,
            cc=OutcomePayoffs(r, r, _make_deltas(params, r, r, -0.5)),  # Both swerve
            cd=OutcomePayoffs(s, t, _make_deltas(params, s, t, 0.5)),  # Row swerves (equilibrium)
            dc=OutcomePayoffs(t, s, _make_deltas(params, t, s, 0.5)),  # Col swerves (equilibrium)
            dd=OutcomePayoffs(p, p, _make_deltas(params, p, p, 2.0)),  # Crash - worst
            row_labels=("Dove", "Hawk"),
            col_labels=("Dove", "Hawk"),
        )


class VolunteersDilemmaConstructor:
    """Constructor for Volunteer's Dilemma matrices.

    Ordinal constraint: F > W > D
    Where:
    - F (Free-ride): Don't volunteer when other does
    - W (Work): Volunteer (costly but prevents disaster)
    - D (Disaster): Nobody volunteers

    Guaranteed Nash Equilibria: Two pure (one volunteers) plus mixed
    """

    @staticmethod
    def validate_params(params: MatrixParameters) -> None:
        """Validate F > W > D constraint."""
        w = params.reward - params.volunteer_cost  # Work payoff
        f = params.reward + params.free_ride_bonus  # Free-ride payoff
        d = -params.disaster_penalty  # Disaster payoff
        if not (f > w > d):
            raise ValueError(f"Volunteer's Dilemma requires F > W > D, got F={f}, W={w}, D={d}")

    @staticmethod
    def build(params: MatrixParameters) -> PayoffMatrix:
        """Build Volunteer's Dilemma matrix."""
        VolunteersDilemmaConstructor.validate_params(params)

        base = params.reward
        cost = params.volunteer_cost
        bonus = params.free_ride_bonus
        disaster = params.disaster_penalty

        w = base - cost  # Work payoff
        f = base + bonus  # Free-ride payoff
        d = -disaster  # Disaster payoff

        return PayoffMatrix(
            matrix_type=MatrixType.VOLUNTEERS_DILEMMA,
            cc=OutcomePayoffs(w, w, _make_deltas(params, w, w, -0.5)),  # Both volunteer
            cd=OutcomePayoffs(w, f, _make_deltas(params, w, f, 0.0)),  # Row volunteers (eq)
            dc=OutcomePayoffs(f, w, _make_deltas(params, f, w, 0.0)),  # Col volunteers (eq)
            dd=OutcomePayoffs(d, d, _make_deltas(params, d, d, 1.5)),  # Disaster
            row_labels=("Volunteer", "Abstain"),
            col_labels=("Volunteer", "Abstain"),
        )


class WarOfAttritionConstructor:
    """Constructor for War of Attrition matrices (2x2 representation).

    Simplified to Continue/Quit decision.
    Ordinal constraint: Solo win > Mutual quit > Mutual continue (costly)

    Guaranteed Nash Equilibria: Two pure (one quits) plus mixed
    """

    @staticmethod
    def validate_params(params: MatrixParameters) -> None:
        """Validate war of attrition constraints."""
        # Win by outlasting: temptation
        # Mutual quit: reward (modest)
        # Mutual continue: punishment (costly)
        # Quit while other continues: sucker
        t, r, p, s = params.temptation, params.reward, params.punishment, params.sucker
        if not (t > r and r > p and t > s):
            raise ValueError(f"War of Attrition requires T > R > P and T > S, got T={t}, R={r}, P={p}, S={s}")

    @staticmethod
    def build(params: MatrixParameters) -> PayoffMatrix:
        """Build War of Attrition matrix."""
        WarOfAttritionConstructor.validate_params(params)

        t, r, p, s = params.temptation, params.reward, params.punishment, params.sucker

        return PayoffMatrix(
            matrix_type=MatrixType.WAR_OF_ATTRITION,
            cc=OutcomePayoffs(p, p, _make_deltas(params, p, p, 1.0)),  # Both continue (costly)
            cd=OutcomePayoffs(t, s, _make_deltas(params, t, s, 0.0)),  # Row wins (eq)
            dc=OutcomePayoffs(s, t, _make_deltas(params, s, t, 0.0)),  # Col wins (eq)
            dd=OutcomePayoffs(r, r, _make_deltas(params, r, r, -0.5)),  # Both quit
            row_labels=("Continue", "Quit"),
            col_labels=("Continue", "Quit"),
        )


class PureCoordinationConstructor:
    """Constructor for Pure Coordination matrices.

    Both players want to match, indifferent between which option.
    Ordinal constraint: Match > Mismatch (symmetric)

    Guaranteed Nash Equilibria: Two pure (A,A) and (B,B)
    """

    @staticmethod
    def validate_params(params: MatrixParameters) -> None:
        """Validate coordination constraint."""
        match = params.coordination_bonus
        mismatch = params.miscoordination_penalty
        if not (match > mismatch):
            raise ValueError(f"Pure Coordination requires Match > Mismatch, got Match={match}, Mismatch={mismatch}")

    @staticmethod
    def build(params: MatrixParameters) -> PayoffMatrix:
        """Build Pure Coordination matrix."""
        PureCoordinationConstructor.validate_params(params)

        match = params.coordination_bonus
        mismatch = params.miscoordination_penalty

        return PayoffMatrix(
            matrix_type=MatrixType.PURE_COORDINATION,
            cc=OutcomePayoffs(match, match, _make_deltas(params, match, match, -0.3)),  # (A,A) eq
            cd=OutcomePayoffs(mismatch, mismatch, _make_deltas(params, mismatch, mismatch, 0.3)),
            dc=OutcomePayoffs(mismatch, mismatch, _make_deltas(params, mismatch, mismatch, 0.3)),
            dd=OutcomePayoffs(match, match, _make_deltas(params, match, match, -0.3)),  # (B,B) eq
            row_labels=("A", "B"),
            col_labels=("A", "B"),
        )


class StagHuntConstructor:
    """Constructor for Stag Hunt (Assurance Game) matrices.

    Ordinal constraint: R > T > P > S
    Where:
    - R: Mutual stag hunt (payoff-dominant equilibrium)
    - T: Hunt hare while partner hunts stag
    - P: Mutual hare hunt (risk-dominant equilibrium)
    - S: Hunt stag alone (worst - stag escapes)

    Guaranteed Nash Equilibria: Two pure (Stag,Stag) and (Hare,Hare)
    """

    @staticmethod
    def validate_params(params: MatrixParameters) -> None:
        """Validate R > T > P > S constraint."""
        r = params.stag_payoff
        t = params.hare_temptation
        p = params.hare_safe
        s = params.stag_fail
        if not (r > t > p > s):
            raise ValueError(f"Stag Hunt requires R > T > P > S, got R={r}, T={t}, P={p}, S={s}")

    @staticmethod
    def build(params: MatrixParameters) -> PayoffMatrix:
        """Build Stag Hunt matrix with two pure equilibria."""
        StagHuntConstructor.validate_params(params)

        r = params.stag_payoff
        t = params.hare_temptation
        p = params.hare_safe
        s = params.stag_fail

        return PayoffMatrix(
            matrix_type=MatrixType.STAG_HUNT,
            cc=OutcomePayoffs(r, r, _make_deltas(params, r, r, -0.5)),  # Stag,Stag (payoff-dom eq)
            cd=OutcomePayoffs(s, t, _make_deltas(params, s, t, 0.3)),  # Row fails
            dc=OutcomePayoffs(t, s, _make_deltas(params, t, s, 0.3)),  # Col fails
            dd=OutcomePayoffs(p, p, _make_deltas(params, p, p, 0.0)),  # Hare,Hare (risk-dom eq)
            row_labels=("Stag", "Hare"),
            col_labels=("Stag", "Hare"),
        )


class BattleOfSexesConstructor:
    """Constructor for Battle of the Sexes matrices.

    Coordination with distributional conflict. Both prefer to coordinate,
    but each prefers a different coordination point.

    Ordinal constraint: Coord > Miscoord, with opposite preferences

    Guaranteed Nash Equilibria: Two pure plus mixed
    """

    @staticmethod
    def validate_params(params: MatrixParameters) -> None:
        """Validate BoS constraints."""
        coord = params.coordination_bonus
        miscoord = params.miscoordination_penalty
        pref_a = params.preference_a
        pref_b = params.preference_b
        if not (coord > miscoord):
            raise ValueError(f"BoS requires Coord > Miscoord, got Coord={coord}, Miscoord={miscoord}")
        if not (pref_a > 1.0 and pref_b > 1.0):
            raise ValueError(f"BoS requires preference multipliers > 1.0, got pref_a={pref_a}, pref_b={pref_b}")

    @staticmethod
    def build(params: MatrixParameters) -> PayoffMatrix:
        """Build Battle of the Sexes matrix."""
        BattleOfSexesConstructor.validate_params(params)

        coord = params.coordination_bonus
        miscoord = params.miscoordination_penalty
        pref_a = params.preference_a
        pref_b = params.preference_b

        # Row prefers (A,A), Col prefers (B,B)
        aa_row = coord * pref_a  # Row's preferred equilibrium
        aa_col = coord
        bb_row = coord
        bb_col = coord * pref_b  # Col's preferred equilibrium

        return PayoffMatrix(
            matrix_type=MatrixType.BATTLE_OF_SEXES,
            cc=OutcomePayoffs(aa_row, aa_col, _make_deltas(params, aa_row, aa_col, -0.3)),  # (A,A) eq
            cd=OutcomePayoffs(miscoord, miscoord, _make_deltas(params, miscoord, miscoord, 0.5)),
            dc=OutcomePayoffs(miscoord, miscoord, _make_deltas(params, miscoord, miscoord, 0.5)),
            dd=OutcomePayoffs(bb_row, bb_col, _make_deltas(params, bb_row, bb_col, -0.3)),  # (B,B) eq
            row_labels=("Opera", "Football"),
            col_labels=("Opera", "Football"),
        )


class LeaderConstructor:
    """Constructor for Leader (Asymmetric Coordination) matrices.

    One should lead, one should follow. If both lead or both follow, bad.

    Ordinal constraint: G > H > B > C
    Where:
    - G (Great): Lead while other follows
    - H (Happy): Follow while other leads
    - B (Bad): Both follow (stuck)
    - C (Clash): Both lead (conflict)

    Guaranteed Nash Equilibria: Two pure (one leads, one follows)
    """

    @staticmethod
    def validate_params(params: MatrixParameters) -> None:
        """Validate G > H > B > C constraint."""
        # Using existing params: temptation=G, reward=H, sucker=B, punishment=C
        g = params.temptation  # Lead success
        h = params.reward  # Follow success
        b = params.sucker  # Both follow (stuck)
        c = params.punishment  # Both lead (clash)
        if not (g > h > b > c):
            raise ValueError(f"Leader requires G > H > B > C, got G={g}, H={h}, B={b}, C={c}")

    @staticmethod
    def build(params: MatrixParameters) -> PayoffMatrix:
        """Build Leader matrix."""
        LeaderConstructor.validate_params(params)

        g = params.temptation  # Lead success
        h = params.reward  # Follow success
        b = params.sucker  # Both follow
        c = params.punishment  # Both lead

        return PayoffMatrix(
            matrix_type=MatrixType.LEADER,
            cc=OutcomePayoffs(b, b, _make_deltas(params, b, b, 0.3)),  # Both follow (stuck)
            cd=OutcomePayoffs(h, g, _make_deltas(params, h, g, -0.3)),  # Row follows (eq)
            dc=OutcomePayoffs(g, h, _make_deltas(params, g, h, -0.3)),  # Row leads (eq)
            dd=OutcomePayoffs(c, c, _make_deltas(params, c, c, 1.0)),  # Both lead (clash)
            row_labels=("Follow", "Lead"),
            col_labels=("Follow", "Lead"),
        )


class MatchingPenniesConstructor:
    """Constructor for Matching Pennies matrices.

    Zero-sum game. Row wants to match, Col wants to mismatch.
    Only mixed-strategy equilibrium exists (50-50).

    Ordinal constraint: Zero-sum with match/mismatch asymmetry
    """

    @staticmethod
    def validate_params(params: MatrixParameters) -> None:
        """Matching pennies has no specific parameter constraints."""
        pass  # Zero-sum structure is built in

    @staticmethod
    def build(params: MatrixParameters) -> PayoffMatrix:
        """Build Matching Pennies matrix."""
        MatchingPenniesConstructor.validate_params(params)

        win = params.scale
        lose = -params.scale

        return PayoffMatrix(
            matrix_type=MatrixType.MATCHING_PENNIES,
            cc=OutcomePayoffs(win, lose, _make_deltas(params, win, lose, 0.0)),  # Match (row wins)
            cd=OutcomePayoffs(lose, win, _make_deltas(params, lose, win, 0.0)),  # Mismatch (col wins)
            dc=OutcomePayoffs(lose, win, _make_deltas(params, lose, win, 0.0)),  # Mismatch (col wins)
            dd=OutcomePayoffs(win, lose, _make_deltas(params, win, lose, 0.0)),  # Match (row wins)
            row_labels=("Heads", "Tails"),
            col_labels=("Heads", "Tails"),
        )


class InspectionGameConstructor:
    """Constructor for Inspection Game matrices.

    Inspector vs potential cheater.

    Ordinal constraint: L > c, g > p
    Where:
    - L: Loss if trusting a cheater
    - c: Cost of inspection
    - g: Gain from successful cheating
    - p: Penalty for getting caught

    Guaranteed Nash Equilibrium: Unique mixed
    """

    @staticmethod
    def validate_params(params: MatrixParameters) -> None:
        """Validate inspection game constraints."""
        loss = params.loss_if_exploited
        cost = params.inspection_cost
        gain = params.cheat_gain
        penalty = params.caught_penalty
        if not (loss > cost):
            raise ValueError(f"Inspection Game requires Loss > Cost, got Loss={loss}, Cost={cost}")
        if not (gain > 0 and penalty > gain):
            raise ValueError(f"Inspection Game requires Penalty > Gain > 0, got Penalty={penalty}, Gain={gain}")

    @staticmethod
    def build(params: MatrixParameters) -> PayoffMatrix:
        """Build Inspection Game matrix."""
        InspectionGameConstructor.validate_params(params)

        cost = params.inspection_cost
        gain = params.cheat_gain
        penalty = params.caught_penalty
        loss = params.loss_if_exploited

        # Payoffs: (Inspector, Inspected)
        # Inspect + Comply: (-cost, 0)
        # Inspect + Cheat: (caught_bonus - cost, -penalty)
        # Trust + Comply: (0, 0)
        # Trust + Cheat: (-loss, +gain)

        caught_bonus = penalty * 0.5  # Partial recovery from catching

        return PayoffMatrix(
            matrix_type=MatrixType.INSPECTION_GAME,
            cc=OutcomePayoffs(-cost, 0, _make_deltas(params, -cost, 0, 0.0)),  # Inspect+Comply
            cd=OutcomePayoffs(  # Inspect+Cheat (caught)
                caught_bonus - cost,
                -penalty,
                _make_deltas(params, caught_bonus - cost, -penalty, 1.0),
            ),
            dc=OutcomePayoffs(0, 0, _make_deltas(params, 0, 0, 0.0)),  # Trust+Comply
            dd=OutcomePayoffs(-loss, gain, _make_deltas(params, -loss, gain, 0.5)),  # Trust+Cheat
            row_labels=("Inspect", "Trust"),
            col_labels=("Comply", "Cheat"),
        )


class ReconnaissanceConstructor:
    """Constructor for Reconnaissance Game matrices.

    Custom variant for information gathering. Zero-sum information game.

    Ordinal constraint: Zero-sum with mixed equilibrium (50-50)

    From GAME_MANUAL.md:
    - Probe + Vigilant = Detected (Risk+1, no info)
    - Probe + Project = Success (learn opponent Position)
    - Mask + Vigilant = Stalemate
    - Mask + Project = Exposed (receive disinformation)
    """

    @staticmethod
    def validate_params(params: MatrixParameters) -> None:
        """Reconnaissance has fixed structure."""
        pass  # Zero-sum structure is built in

    @staticmethod
    def build(params: MatrixParameters) -> PayoffMatrix:
        """Build Reconnaissance matrix."""
        ReconnaissanceConstructor.validate_params(params)

        scale = params.scale
        # Payoffs represent information value (Row is initiator)
        # Probe+Vigilant: Row detected, risk increases
        # Probe+Project: Row succeeds, learns info
        # Mask+Vigilant: Stalemate, nothing happens
        # Mask+Project: Row exposed, col gets info

        return PayoffMatrix(
            matrix_type=MatrixType.RECONNAISSANCE,
            cc=OutcomePayoffs(-scale, scale, StateDeltas(0.0, 0.0, 0.0, 0.0, 0.5)),  # Detected
            cd=OutcomePayoffs(scale, -scale, StateDeltas(0.0, 0.0, 0.0, 0.0, 0.0)),  # Success
            dc=OutcomePayoffs(0, 0, StateDeltas(0.0, 0.0, 0.0, 0.0, 0.0)),  # Stalemate
            dd=OutcomePayoffs(-scale, scale, StateDeltas(0.0, 0.0, 0.0, 0.0, 0.0)),  # Exposed
            row_labels=("Probe", "Mask"),
            col_labels=("Vigilant", "Project"),
        )


class SecurityDilemmaConstructor:
    """Constructor for Security Dilemma matrices.

    Same structure as Prisoner's Dilemma (T > R > P > S), but
    the interpretation matters - defensive arming appears offensive.

    Guaranteed Nash Equilibrium: Unique (Arm, Arm)
    """

    @staticmethod
    def validate_params(params: MatrixParameters) -> None:
        """Validate T > R > P > S constraint (same as PD)."""
        PrisonersDilemmaConstructor.validate_params(params)

    @staticmethod
    def build(params: MatrixParameters) -> PayoffMatrix:
        """Build Security Dilemma matrix."""
        SecurityDilemmaConstructor.validate_params(params)

        t, r, p, s = params.temptation, params.reward, params.punishment, params.sucker

        return PayoffMatrix(
            matrix_type=MatrixType.SECURITY_DILEMMA,
            cc=OutcomePayoffs(r, r, _make_deltas(params, r, r, -0.5)),  # Mutual disarm
            cd=OutcomePayoffs(s, t, _make_deltas(params, s, t, 0.5)),  # Row disarms (exploited)
            dc=OutcomePayoffs(t, s, _make_deltas(params, t, s, 0.5)),  # Col disarms (exploited)
            dd=OutcomePayoffs(p, p, _make_deltas(params, p, p, 1.0)),  # Mutual arm (equilibrium)
            row_labels=("Disarm", "Arm"),
            col_labels=("Disarm", "Arm"),
        )


# Registry of all constructors by matrix type
CONSTRUCTORS: dict[MatrixType, type[MatrixConstructor]] = {
    MatrixType.PRISONERS_DILEMMA: PrisonersDilemmaConstructor,
    MatrixType.DEADLOCK: DeadlockConstructor,
    MatrixType.HARMONY: HarmonyConstructor,
    MatrixType.CHICKEN: ChickenConstructor,
    MatrixType.VOLUNTEERS_DILEMMA: VolunteersDilemmaConstructor,
    MatrixType.WAR_OF_ATTRITION: WarOfAttritionConstructor,
    MatrixType.PURE_COORDINATION: PureCoordinationConstructor,
    MatrixType.STAG_HUNT: StagHuntConstructor,
    MatrixType.BATTLE_OF_SEXES: BattleOfSexesConstructor,
    MatrixType.LEADER: LeaderConstructor,
    MatrixType.MATCHING_PENNIES: MatchingPenniesConstructor,
    MatrixType.INSPECTION_GAME: InspectionGameConstructor,
    MatrixType.RECONNAISSANCE: ReconnaissanceConstructor,
    MatrixType.SECURITY_DILEMMA: SecurityDilemmaConstructor,
}


def build_matrix(matrix_type: MatrixType, params: MatrixParameters) -> PayoffMatrix:
    """Build a payoff matrix from type and parameters.

    This is the main entry point for matrix construction.
    Raises ValueError if parameters violate the game type's constraints.
    """
    constructor = CONSTRUCTORS.get(matrix_type)
    if constructor is None:
        raise ValueError(f"Unknown matrix type: {matrix_type}")
    return constructor.build(params)


def get_default_params_for_type(matrix_type: MatrixType) -> MatrixParameters:
    """Get default parameters that satisfy the ordinal constraints for a given type.

    Useful for testing and scenario generation.
    """
    defaults = {
        MatrixType.PRISONERS_DILEMMA: MatrixParameters(temptation=1.5, reward=1.0, punishment=0.3, sucker=0.0),
        MatrixType.DEADLOCK: MatrixParameters(temptation=1.5, punishment=1.0, reward=0.5, sucker=0.0),
        MatrixType.HARMONY: MatrixParameters(reward=1.5, temptation=1.0, sucker=0.5, punishment=0.0),
        MatrixType.CHICKEN: MatrixParameters(temptation=1.5, reward=1.0, swerve_payoff=0.5, crash_payoff=-1.0),
        MatrixType.VOLUNTEERS_DILEMMA: MatrixParameters(
            reward=1.0, volunteer_cost=0.3, free_ride_bonus=0.5, disaster_penalty=1.0
        ),
        MatrixType.WAR_OF_ATTRITION: MatrixParameters(temptation=1.5, reward=1.0, punishment=0.3, sucker=0.0),
        MatrixType.PURE_COORDINATION: MatrixParameters(coordination_bonus=1.0, miscoordination_penalty=0.0),
        MatrixType.STAG_HUNT: MatrixParameters(stag_payoff=2.0, hare_temptation=1.5, hare_safe=1.0, stag_fail=0.0),
        MatrixType.BATTLE_OF_SEXES: MatrixParameters(
            coordination_bonus=1.0, miscoordination_penalty=0.0, preference_a=1.5, preference_b=1.3
        ),
        MatrixType.LEADER: MatrixParameters(temptation=2.0, reward=1.5, sucker=0.5, punishment=0.0),
        MatrixType.MATCHING_PENNIES: MatrixParameters(scale=1.0),
        MatrixType.INSPECTION_GAME: MatrixParameters(
            inspection_cost=0.3, cheat_gain=0.5, caught_penalty=1.0, loss_if_exploited=0.7
        ),
        MatrixType.RECONNAISSANCE: MatrixParameters(scale=1.0),
        MatrixType.SECURITY_DILEMMA: MatrixParameters(temptation=1.5, reward=1.0, punishment=0.3, sucker=0.0),
    }
    return defaults.get(matrix_type, MatrixParameters())
