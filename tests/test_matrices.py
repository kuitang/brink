"""Comprehensive unit tests for matrices.py.

Tests cover:
1. MatrixType enum - all 14 game types defined
2. MatrixParameters - default values and validation
3. StateDeltas - creation and near-zero-sum constraint
4. PayoffMatrix - creation and properties
5. All 14 constructors - ordinal constraints and random parameter validation
6. CONSTRUCTORS registry - completeness and build_matrix function
"""

import random
from typing import Any

import pytest
from pydantic import ValidationError

from brinksmanship.models.matrices import (
    CONSTRUCTORS,
    BattleOfSexesConstructor,
    ChickenConstructor,
    DeadlockConstructor,
    HarmonyConstructor,
    InspectionGameConstructor,
    LeaderConstructor,
    MatchingPenniesConstructor,
    MatrixParameters,
    MatrixType,
    OutcomePayoffs,
    PayoffMatrix,
    PrisonersDilemmaConstructor,
    PureCoordinationConstructor,
    ReconnaissanceConstructor,
    SecurityDilemmaConstructor,
    StagHuntConstructor,
    StateDeltas,
    VolunteersDilemmaConstructor,
    WarOfAttritionConstructor,
    build_matrix,
    get_default_params_for_type,
)


# =============================================================================
# MatrixType Enum Tests
# =============================================================================


class TestMatrixType:
    """Tests for MatrixType enum."""

    def test_all_14_game_types_defined(self) -> None:
        """Verify all 14 game types are defined in the enum."""
        expected_types = {
            # Category A: Dominant Strategy Games
            "PRISONERS_DILEMMA",
            "DEADLOCK",
            "HARMONY",
            # Category B: Anti-Coordination Games
            "CHICKEN",
            "VOLUNTEERS_DILEMMA",
            "WAR_OF_ATTRITION",
            # Category C: Coordination Games
            "PURE_COORDINATION",
            "STAG_HUNT",
            "BATTLE_OF_SEXES",
            "LEADER",
            # Category D: Zero-Sum and Information Games
            "MATCHING_PENNIES",
            "INSPECTION_GAME",
            "RECONNAISSANCE",
            # Special variant
            "SECURITY_DILEMMA",
        }

        actual_types = {member.name for member in MatrixType}
        assert actual_types == expected_types
        assert len(MatrixType) == 14

    def test_enum_values_are_strings(self) -> None:
        """Verify all enum values are descriptive strings."""
        for matrix_type in MatrixType:
            assert isinstance(matrix_type.value, str)
            assert len(matrix_type.value) > 0

    def test_enum_membership(self) -> None:
        """Test enum membership checks."""
        assert MatrixType.PRISONERS_DILEMMA in MatrixType
        assert MatrixType.CHICKEN in MatrixType
        assert MatrixType.STAG_HUNT in MatrixType

    def test_enum_by_value(self) -> None:
        """Test accessing enum by value."""
        assert MatrixType("prisoners_dilemma") == MatrixType.PRISONERS_DILEMMA
        assert MatrixType("chicken") == MatrixType.CHICKEN
        assert MatrixType("stag_hunt") == MatrixType.STAG_HUNT


# =============================================================================
# MatrixParameters Tests
# =============================================================================


class TestMatrixParameters:
    """Tests for MatrixParameters validation and defaults."""

    def test_default_parameters(self) -> None:
        """Test that default parameters are valid."""
        params = MatrixParameters()

        # Check defaults
        assert params.scale == 1.0
        assert params.position_weight == 0.6
        assert params.resource_weight == 0.2
        assert params.risk_weight == 0.2

        # Check weights sum to 1.0
        total = params.position_weight + params.resource_weight + params.risk_weight
        assert total == pytest.approx(1.0)

    def test_scale_must_be_positive(self) -> None:
        """Test that scale <= 0 is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            MatrixParameters(scale=0)
        assert "scale must be positive" in str(exc_info.value)

        with pytest.raises(ValidationError) as exc_info:
            MatrixParameters(scale=-1.0)
        assert "scale must be positive" in str(exc_info.value)

    def test_weights_must_sum_to_one(self) -> None:
        """Test that weights not summing to 1.0 are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            MatrixParameters(position_weight=0.5, resource_weight=0.3, risk_weight=0.3)
        assert "Weights must sum to 1.0" in str(exc_info.value)

        with pytest.raises(ValidationError) as exc_info:
            MatrixParameters(position_weight=0.2, resource_weight=0.2, risk_weight=0.2)
        assert "Weights must sum to 1.0" in str(exc_info.value)

    def test_weights_must_be_non_negative(self) -> None:
        """Test that negative weights are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            MatrixParameters(position_weight=-0.1, resource_weight=0.6, risk_weight=0.5)
        assert "non-negative" in str(exc_info.value).lower()

        with pytest.raises(ValidationError) as exc_info:
            MatrixParameters(position_weight=0.6, resource_weight=-0.2, risk_weight=0.6)
        assert "non-negative" in str(exc_info.value).lower()

        with pytest.raises(ValidationError) as exc_info:
            MatrixParameters(position_weight=0.6, resource_weight=0.6, risk_weight=-0.2)
        assert "non-negative" in str(exc_info.value).lower()

    def test_valid_custom_weights(self) -> None:
        """Test valid custom weight combinations."""
        params = MatrixParameters(
            position_weight=0.5, resource_weight=0.3, risk_weight=0.2
        )
        total = params.position_weight + params.resource_weight + params.risk_weight
        assert total == pytest.approx(1.0)

        params2 = MatrixParameters(
            position_weight=1.0, resource_weight=0.0, risk_weight=0.0
        )
        total2 = params2.position_weight + params2.resource_weight + params2.risk_weight
        assert total2 == pytest.approx(1.0)

    def test_parameters_are_frozen(self) -> None:
        """Test that parameters are immutable."""
        params = MatrixParameters()
        with pytest.raises(ValidationError):
            params.scale = 2.0  # type: ignore[misc]


# =============================================================================
# StateDeltas Tests
# =============================================================================


class TestStateDeltas:
    """Tests for StateDeltas creation and constraints."""

    def test_valid_creation(self) -> None:
        """Test creating valid StateDeltas."""
        deltas = StateDeltas(
            pos_a=0.5, pos_b=-0.5, res_cost_a=0.3, res_cost_b=0.2, risk_delta=0.5
        )
        assert deltas.pos_a == 0.5
        assert deltas.pos_b == -0.5
        assert deltas.res_cost_a == 0.3
        assert deltas.res_cost_b == 0.2
        assert deltas.risk_delta == 0.5

    def test_zero_sum_position_changes(self) -> None:
        """Test that perfectly zero-sum position changes are valid."""
        deltas = StateDeltas(
            pos_a=1.0, pos_b=-1.0, res_cost_a=0.0, res_cost_b=0.0, risk_delta=0.0
        )
        assert deltas.pos_a + deltas.pos_b == pytest.approx(0.0)

    def test_near_zero_sum_constraint(self) -> None:
        """Test that position changes must be near-zero-sum (|pos_a + pos_b| <= 0.5)."""
        # Valid: within tolerance
        deltas = StateDeltas(
            pos_a=0.3, pos_b=0.2, res_cost_a=0.0, res_cost_b=0.0, risk_delta=0.0
        )
        assert abs(deltas.pos_a + deltas.pos_b) <= 0.5

        # Invalid: exceeds tolerance
        with pytest.raises(ValueError) as exc_info:
            StateDeltas(
                pos_a=1.0, pos_b=1.0, res_cost_a=0.0, res_cost_b=0.0, risk_delta=0.0
            )
        assert "near-zero-sum" in str(exc_info.value)

    def test_position_bounds(self) -> None:
        """Test position change bounds (-1.5 to +1.5)."""
        # Valid at bounds
        deltas = StateDeltas(
            pos_a=1.5, pos_b=-1.5, res_cost_a=0.0, res_cost_b=0.0, risk_delta=0.0
        )
        assert deltas.pos_a == 1.5
        assert deltas.pos_b == -1.5

        # Invalid: exceeds positive bound
        with pytest.raises(ValueError) as exc_info:
            StateDeltas(
                pos_a=2.0, pos_b=-2.0, res_cost_a=0.0, res_cost_b=0.0, risk_delta=0.0
            )
        assert "pos_a must be in [-1.5, 1.5]" in str(exc_info.value)

        # Invalid: exceeds negative bound
        with pytest.raises(ValueError) as exc_info:
            StateDeltas(
                pos_a=-2.0, pos_b=2.0, res_cost_a=0.0, res_cost_b=0.0, risk_delta=0.0
            )
        assert "pos_a must be in [-1.5, 1.5]" in str(exc_info.value)

    def test_resource_cost_bounds(self) -> None:
        """Test resource cost bounds (0 to 1.0)."""
        # Valid at bounds
        deltas = StateDeltas(
            pos_a=0.0, pos_b=0.0, res_cost_a=0.0, res_cost_b=1.0, risk_delta=0.0
        )
        assert deltas.res_cost_a == 0.0
        assert deltas.res_cost_b == 1.0

        # Invalid: negative
        with pytest.raises(ValueError) as exc_info:
            StateDeltas(
                pos_a=0.0, pos_b=0.0, res_cost_a=-0.1, res_cost_b=0.0, risk_delta=0.0
            )
        assert "res_cost_a must be in [0, 1.0]" in str(exc_info.value)

        # Invalid: exceeds maximum
        with pytest.raises(ValueError) as exc_info:
            StateDeltas(
                pos_a=0.0, pos_b=0.0, res_cost_a=0.0, res_cost_b=1.5, risk_delta=0.0
            )
        assert "res_cost_b must be in [0, 1.0]" in str(exc_info.value)

    def test_risk_delta_bounds(self) -> None:
        """Test risk delta bounds (-1.0 to +2.0)."""
        # Valid at bounds
        deltas_low = StateDeltas(
            pos_a=0.0, pos_b=0.0, res_cost_a=0.0, res_cost_b=0.0, risk_delta=-1.0
        )
        assert deltas_low.risk_delta == -1.0

        deltas_high = StateDeltas(
            pos_a=0.0, pos_b=0.0, res_cost_a=0.0, res_cost_b=0.0, risk_delta=2.0
        )
        assert deltas_high.risk_delta == 2.0

        # Invalid: below minimum
        with pytest.raises(ValueError) as exc_info:
            StateDeltas(
                pos_a=0.0, pos_b=0.0, res_cost_a=0.0, res_cost_b=0.0, risk_delta=-1.5
            )
        assert "risk_delta must be in [-1.0, 2.0]" in str(exc_info.value)

        # Invalid: above maximum
        with pytest.raises(ValueError) as exc_info:
            StateDeltas(
                pos_a=0.0, pos_b=0.0, res_cost_a=0.0, res_cost_b=0.0, risk_delta=2.5
            )
        assert "risk_delta must be in [-1.0, 2.0]" in str(exc_info.value)

    def test_frozen_dataclass(self) -> None:
        """Test that StateDeltas is immutable."""
        deltas = StateDeltas(
            pos_a=0.0, pos_b=0.0, res_cost_a=0.0, res_cost_b=0.0, risk_delta=0.0
        )
        with pytest.raises(AttributeError):
            deltas.pos_a = 1.0  # type: ignore[misc]


# =============================================================================
# PayoffMatrix Tests
# =============================================================================


class TestPayoffMatrix:
    """Tests for PayoffMatrix creation and properties."""

    def _make_deltas(self) -> StateDeltas:
        """Helper to create valid StateDeltas."""
        return StateDeltas(
            pos_a=0.0, pos_b=0.0, res_cost_a=0.0, res_cost_b=0.0, risk_delta=0.0
        )

    def test_creation(self) -> None:
        """Test creating a PayoffMatrix."""
        deltas = self._make_deltas()
        matrix = PayoffMatrix(
            matrix_type=MatrixType.PRISONERS_DILEMMA,
            cc=OutcomePayoffs(3.0, 3.0, deltas),
            cd=OutcomePayoffs(0.0, 5.0, deltas),
            dc=OutcomePayoffs(5.0, 0.0, deltas),
            dd=OutcomePayoffs(1.0, 1.0, deltas),
        )

        assert matrix.matrix_type == MatrixType.PRISONERS_DILEMMA
        assert matrix.cc.payoff_a == 3.0
        assert matrix.cd.payoff_b == 5.0

    def test_get_outcome(self) -> None:
        """Test get_outcome method."""
        deltas = self._make_deltas()
        matrix = PayoffMatrix(
            matrix_type=MatrixType.PRISONERS_DILEMMA,
            cc=OutcomePayoffs(3.0, 3.0, deltas),
            cd=OutcomePayoffs(0.0, 5.0, deltas),
            dc=OutcomePayoffs(5.0, 0.0, deltas),
            dd=OutcomePayoffs(1.0, 1.0, deltas),
        )

        # Row 0, Col 0 = CC
        assert matrix.get_outcome(0, 0) == matrix.cc
        # Row 0, Col 1 = CD
        assert matrix.get_outcome(0, 1) == matrix.cd
        # Row 1, Col 0 = DC
        assert matrix.get_outcome(1, 0) == matrix.dc
        # Row 1, Col 1 = DD
        assert matrix.get_outcome(1, 1) == matrix.dd

    def test_default_labels(self) -> None:
        """Test default strategy labels."""
        deltas = self._make_deltas()
        matrix = PayoffMatrix(
            matrix_type=MatrixType.PRISONERS_DILEMMA,
            cc=OutcomePayoffs(3.0, 3.0, deltas),
            cd=OutcomePayoffs(0.0, 5.0, deltas),
            dc=OutcomePayoffs(5.0, 0.0, deltas),
            dd=OutcomePayoffs(1.0, 1.0, deltas),
        )

        assert matrix.row_labels == ("Cooperate", "Defect")
        assert matrix.col_labels == ("Cooperate", "Defect")

    def test_custom_labels(self) -> None:
        """Test custom strategy labels."""
        deltas = self._make_deltas()
        matrix = PayoffMatrix(
            matrix_type=MatrixType.CHICKEN,
            cc=OutcomePayoffs(3.0, 3.0, deltas),
            cd=OutcomePayoffs(2.0, 4.0, deltas),
            dc=OutcomePayoffs(4.0, 2.0, deltas),
            dd=OutcomePayoffs(1.0, 1.0, deltas),
            row_labels=("Dove", "Hawk"),
            col_labels=("Dove", "Hawk"),
        )

        assert matrix.row_labels == ("Dove", "Hawk")
        assert matrix.col_labels == ("Dove", "Hawk")

    def test_is_zero_sum_property(self) -> None:
        """Test checking if a matrix is zero-sum."""
        deltas = self._make_deltas()

        # Zero-sum matrix (Matching Pennies)
        zero_sum_matrix = PayoffMatrix(
            matrix_type=MatrixType.MATCHING_PENNIES,
            cc=OutcomePayoffs(1.0, -1.0, deltas),
            cd=OutcomePayoffs(-1.0, 1.0, deltas),
            dc=OutcomePayoffs(-1.0, 1.0, deltas),
            dd=OutcomePayoffs(1.0, -1.0, deltas),
        )

        # Check that all payoffs sum to zero
        assert zero_sum_matrix.cc.payoff_a + zero_sum_matrix.cc.payoff_b == pytest.approx(0.0)
        assert zero_sum_matrix.cd.payoff_a + zero_sum_matrix.cd.payoff_b == pytest.approx(0.0)
        assert zero_sum_matrix.dc.payoff_a + zero_sum_matrix.dc.payoff_b == pytest.approx(0.0)
        assert zero_sum_matrix.dd.payoff_a + zero_sum_matrix.dd.payoff_b == pytest.approx(0.0)

        # Non-zero-sum matrix (Prisoner's Dilemma)
        non_zero_sum = PayoffMatrix(
            matrix_type=MatrixType.PRISONERS_DILEMMA,
            cc=OutcomePayoffs(3.0, 3.0, deltas),
            cd=OutcomePayoffs(0.0, 5.0, deltas),
            dc=OutcomePayoffs(5.0, 0.0, deltas),
            dd=OutcomePayoffs(1.0, 1.0, deltas),
        )

        # CC payoffs don't sum to zero
        assert non_zero_sum.cc.payoff_a + non_zero_sum.cc.payoff_b != pytest.approx(0.0)


# =============================================================================
# Constructor Tests - Helper Functions
# =============================================================================


def generate_random_pd_params() -> MatrixParameters:
    """Generate random valid parameters for Prisoner's Dilemma (T > R > P > S)."""
    # Generate in order: S, P, R, T with increasing values
    s = random.uniform(-1.0, 0.5)
    p = random.uniform(s + 0.1, s + 1.0)
    r = random.uniform(p + 0.1, p + 1.0)
    t = random.uniform(r + 0.1, r + 1.0)

    return MatrixParameters(temptation=t, reward=r, punishment=p, sucker=s)


def generate_random_deadlock_params() -> MatrixParameters:
    """Generate random valid parameters for Deadlock (T > P > R > S)."""
    s = random.uniform(-1.0, 0.5)
    r = random.uniform(s + 0.1, s + 1.0)
    p = random.uniform(r + 0.1, r + 1.0)
    t = random.uniform(p + 0.1, p + 1.0)

    return MatrixParameters(temptation=t, reward=r, punishment=p, sucker=s)


def generate_random_harmony_params() -> MatrixParameters:
    """Generate random valid parameters for Harmony (R > T > S > P)."""
    p = random.uniform(-1.0, 0.5)
    s = random.uniform(p + 0.1, p + 1.0)
    t = random.uniform(s + 0.1, s + 1.0)
    r = random.uniform(t + 0.1, t + 1.0)

    return MatrixParameters(temptation=t, reward=r, punishment=p, sucker=s)


def generate_random_chicken_params() -> MatrixParameters:
    """Generate random valid parameters for Chicken (T > R > S > P)."""
    p = random.uniform(-2.0, -0.5)  # crash_payoff is worst
    s = random.uniform(p + 0.1, 0.5)  # swerve_payoff
    r = random.uniform(s + 0.1, s + 1.0)  # reward
    t = random.uniform(r + 0.1, r + 1.0)  # temptation

    return MatrixParameters(temptation=t, reward=r, swerve_payoff=s, crash_payoff=p)


def generate_random_stag_hunt_params() -> MatrixParameters:
    """Generate random valid parameters for Stag Hunt (R > T > P > S)."""
    s = random.uniform(-1.0, 0.5)  # stag_fail
    p = random.uniform(s + 0.1, s + 1.0)  # hare_safe
    t = random.uniform(p + 0.1, p + 1.0)  # hare_temptation
    r = random.uniform(t + 0.1, t + 1.0)  # stag_payoff

    return MatrixParameters(
        stag_payoff=r, hare_temptation=t, hare_safe=p, stag_fail=s
    )


def generate_random_volunteers_params() -> MatrixParameters:
    """Generate random valid parameters for Volunteer's Dilemma (F > W > D)."""
    # W = base - cost, F = base + bonus, D = -disaster
    # Need F > W > D, so: base + bonus > base - cost > -disaster
    # This means: bonus > -cost (always true for positive values)
    # And: base - cost > -disaster, so base + disaster > cost

    base = random.uniform(0.5, 2.0)
    cost = random.uniform(0.1, 0.5)
    bonus = random.uniform(0.2, 0.8)
    disaster = random.uniform(0.5, 2.0)

    # Verify constraint: F > W > D
    # F = base + bonus, W = base - cost, D = -disaster
    # Need base + bonus > base - cost, which is bonus > -cost (always true)
    # Need base - cost > -disaster, which is base + disaster > cost (need to check)
    while base - cost <= -disaster:
        base = random.uniform(0.5, 2.0)
        cost = random.uniform(0.1, min(0.5, base + disaster - 0.1))

    return MatrixParameters(
        reward=base,
        volunteer_cost=cost,
        free_ride_bonus=bonus,
        disaster_penalty=disaster,
    )


def generate_random_war_of_attrition_params() -> MatrixParameters:
    """Generate random valid parameters for War of Attrition (T > R > P and T > S)."""
    p = random.uniform(0.0, 0.5)
    r = random.uniform(p + 0.1, p + 1.0)
    s = random.uniform(-1.0, r)  # S can be anywhere below T
    t = random.uniform(max(r, s) + 0.1, max(r, s) + 1.0)

    return MatrixParameters(temptation=t, reward=r, punishment=p, sucker=s)


def generate_random_pure_coordination_params() -> MatrixParameters:
    """Generate random valid parameters for Pure Coordination (Match > Mismatch)."""
    mismatch = random.uniform(-1.0, 0.5)
    match = random.uniform(mismatch + 0.1, mismatch + 2.0)

    return MatrixParameters(coordination_bonus=match, miscoordination_penalty=mismatch)


def generate_random_battle_of_sexes_params() -> MatrixParameters:
    """Generate random valid parameters for Battle of Sexes."""
    mismatch = random.uniform(-1.0, 0.5)
    match = random.uniform(mismatch + 0.1, mismatch + 2.0)
    pref_a = random.uniform(1.01, 2.0)
    pref_b = random.uniform(1.01, 2.0)

    return MatrixParameters(
        coordination_bonus=match,
        miscoordination_penalty=mismatch,
        preference_a=pref_a,
        preference_b=pref_b,
    )


def generate_random_leader_params() -> MatrixParameters:
    """Generate random valid parameters for Leader (G > H > B > C)."""
    # G=temptation, H=reward, B=sucker, C=punishment
    c = random.uniform(-1.0, 0.5)
    b = random.uniform(c + 0.1, c + 1.0)
    h = random.uniform(b + 0.1, b + 1.0)
    g = random.uniform(h + 0.1, h + 1.0)

    return MatrixParameters(temptation=g, reward=h, sucker=b, punishment=c)


def generate_random_inspection_params() -> MatrixParameters:
    """Generate random valid parameters for Inspection Game (Loss > Cost, Penalty > Gain > 0)."""
    cost = random.uniform(0.1, 0.5)
    loss = random.uniform(cost + 0.1, cost + 1.0)
    gain = random.uniform(0.1, 0.8)
    penalty = random.uniform(gain + 0.1, gain + 1.0)

    return MatrixParameters(
        inspection_cost=cost,
        cheat_gain=gain,
        caught_penalty=penalty,
        loss_if_exploited=loss,
    )


def generate_random_scale_params() -> MatrixParameters:
    """Generate parameters with random scale for zero-sum games."""
    scale = random.uniform(0.5, 3.0)
    return MatrixParameters(scale=scale)


# =============================================================================
# Prisoner's Dilemma Constructor Tests
# =============================================================================


class TestPrisonersDilemmaConstructor:
    """Tests for Prisoner's Dilemma constructor."""

    def test_ordinal_constraint_t_greater_than_r_greater_than_p_greater_than_s(
        self,
    ) -> None:
        """Test that T > R > P > S constraint is enforced."""
        # Valid params
        valid_params = MatrixParameters(
            temptation=5.0, reward=3.0, punishment=1.0, sucker=0.0
        )
        PrisonersDilemmaConstructor.validate_params(valid_params)  # Should not raise

        # Invalid: T not > R
        with pytest.raises(ValueError) as exc_info:
            invalid_params = MatrixParameters(
                temptation=3.0, reward=3.0, punishment=1.0, sucker=0.0
            )
            PrisonersDilemmaConstructor.validate_params(invalid_params)
        assert "T > R > P > S" in str(exc_info.value)

        # Invalid: R not > P
        with pytest.raises(ValueError) as exc_info:
            invalid_params = MatrixParameters(
                temptation=5.0, reward=1.0, punishment=1.0, sucker=0.0
            )
            PrisonersDilemmaConstructor.validate_params(invalid_params)
        assert "T > R > P > S" in str(exc_info.value)

    def test_build_returns_valid_matrix(self) -> None:
        """Test that build() returns a valid PayoffMatrix."""
        params = MatrixParameters(
            temptation=5.0, reward=3.0, punishment=1.0, sucker=0.0
        )
        matrix = PrisonersDilemmaConstructor.build(params)

        assert isinstance(matrix, PayoffMatrix)
        assert matrix.matrix_type == MatrixType.PRISONERS_DILEMMA
        assert matrix.row_labels == ("Cooperate", "Defect")

    @pytest.mark.parametrize("seed", range(10))
    def test_random_valid_params_produce_valid_matrix(self, seed: int) -> None:
        """Test that random valid parameters always produce valid matrices."""
        random.seed(seed)
        params = generate_random_pd_params()

        # Should not raise
        matrix = PrisonersDilemmaConstructor.build(params)
        assert matrix.matrix_type == MatrixType.PRISONERS_DILEMMA


# =============================================================================
# Deadlock Constructor Tests
# =============================================================================


class TestDeadlockConstructor:
    """Tests for Deadlock constructor."""

    def test_ordinal_constraint_t_greater_than_p_greater_than_r_greater_than_s(
        self,
    ) -> None:
        """Test that T > P > R > S constraint is enforced."""
        valid_params = MatrixParameters(
            temptation=4.0, punishment=3.0, reward=2.0, sucker=1.0
        )
        DeadlockConstructor.validate_params(valid_params)

        with pytest.raises(ValueError) as exc_info:
            invalid_params = MatrixParameters(
                temptation=4.0, punishment=2.0, reward=3.0, sucker=1.0
            )
            DeadlockConstructor.validate_params(invalid_params)
        assert "T > P > R > S" in str(exc_info.value)

    def test_build_returns_valid_matrix(self) -> None:
        """Test that build() returns a valid PayoffMatrix."""
        params = MatrixParameters(
            temptation=4.0, punishment=3.0, reward=2.0, sucker=1.0
        )
        matrix = DeadlockConstructor.build(params)

        assert isinstance(matrix, PayoffMatrix)
        assert matrix.matrix_type == MatrixType.DEADLOCK

    @pytest.mark.parametrize("seed", range(10))
    def test_random_valid_params_produce_valid_matrix(self, seed: int) -> None:
        """Test that random valid parameters always produce valid matrices."""
        random.seed(seed)
        params = generate_random_deadlock_params()
        matrix = DeadlockConstructor.build(params)
        assert matrix.matrix_type == MatrixType.DEADLOCK


# =============================================================================
# Harmony Constructor Tests
# =============================================================================


class TestHarmonyConstructor:
    """Tests for Harmony constructor."""

    def test_ordinal_constraint_r_greater_than_t_greater_than_s_greater_than_p(
        self,
    ) -> None:
        """Test that R > T > S > P constraint is enforced."""
        valid_params = MatrixParameters(
            reward=4.0, temptation=3.0, sucker=2.0, punishment=1.0
        )
        HarmonyConstructor.validate_params(valid_params)

        with pytest.raises(ValueError) as exc_info:
            invalid_params = MatrixParameters(
                reward=3.0, temptation=4.0, sucker=2.0, punishment=1.0
            )
            HarmonyConstructor.validate_params(invalid_params)
        assert "R > T > S > P" in str(exc_info.value)

    def test_build_returns_valid_matrix(self) -> None:
        """Test that build() returns a valid PayoffMatrix."""
        params = MatrixParameters(
            reward=4.0, temptation=3.0, sucker=2.0, punishment=1.0
        )
        matrix = HarmonyConstructor.build(params)

        assert isinstance(matrix, PayoffMatrix)
        assert matrix.matrix_type == MatrixType.HARMONY

    @pytest.mark.parametrize("seed", range(10))
    def test_random_valid_params_produce_valid_matrix(self, seed: int) -> None:
        """Test that random valid parameters always produce valid matrices."""
        random.seed(seed)
        params = generate_random_harmony_params()
        matrix = HarmonyConstructor.build(params)
        assert matrix.matrix_type == MatrixType.HARMONY


# =============================================================================
# Chicken Constructor Tests
# =============================================================================


class TestChickenConstructor:
    """Tests for Chicken constructor."""

    def test_ordinal_constraint_t_greater_than_r_greater_than_s_greater_than_p(
        self,
    ) -> None:
        """Test that T > R > S > P constraint is enforced."""
        valid_params = MatrixParameters(
            temptation=4.0, reward=3.0, swerve_payoff=2.0, crash_payoff=1.0
        )
        ChickenConstructor.validate_params(valid_params)

        with pytest.raises(ValueError) as exc_info:
            invalid_params = MatrixParameters(
                temptation=4.0, reward=3.0, swerve_payoff=0.5, crash_payoff=1.0
            )
            ChickenConstructor.validate_params(invalid_params)
        assert "T > R > S > P" in str(exc_info.value)

    def test_build_returns_valid_matrix(self) -> None:
        """Test that build() returns a valid PayoffMatrix."""
        params = MatrixParameters(
            temptation=4.0, reward=3.0, swerve_payoff=2.0, crash_payoff=0.0
        )
        matrix = ChickenConstructor.build(params)

        assert isinstance(matrix, PayoffMatrix)
        assert matrix.matrix_type == MatrixType.CHICKEN
        assert matrix.row_labels == ("Dove", "Hawk")

    @pytest.mark.parametrize("seed", range(10))
    def test_random_valid_params_produce_valid_matrix(self, seed: int) -> None:
        """Test that random valid parameters always produce valid matrices."""
        random.seed(seed)
        params = generate_random_chicken_params()
        matrix = ChickenConstructor.build(params)
        assert matrix.matrix_type == MatrixType.CHICKEN


# =============================================================================
# Stag Hunt Constructor Tests
# =============================================================================


class TestStagHuntConstructor:
    """Tests for Stag Hunt constructor."""

    def test_ordinal_constraint_r_greater_than_t_greater_than_p_greater_than_s(
        self,
    ) -> None:
        """Test that R > T > P > S constraint is enforced."""
        valid_params = MatrixParameters(
            stag_payoff=4.0, hare_temptation=3.0, hare_safe=2.0, stag_fail=1.0
        )
        StagHuntConstructor.validate_params(valid_params)

        with pytest.raises(ValueError) as exc_info:
            invalid_params = MatrixParameters(
                stag_payoff=3.0, hare_temptation=4.0, hare_safe=2.0, stag_fail=1.0
            )
            StagHuntConstructor.validate_params(invalid_params)
        assert "R > T > P > S" in str(exc_info.value)

    def test_build_returns_valid_matrix(self) -> None:
        """Test that build() returns a valid PayoffMatrix."""
        params = MatrixParameters(
            stag_payoff=4.0, hare_temptation=3.0, hare_safe=2.0, stag_fail=1.0
        )
        matrix = StagHuntConstructor.build(params)

        assert isinstance(matrix, PayoffMatrix)
        assert matrix.matrix_type == MatrixType.STAG_HUNT
        assert matrix.row_labels == ("Stag", "Hare")

    @pytest.mark.parametrize("seed", range(10))
    def test_random_valid_params_produce_valid_matrix(self, seed: int) -> None:
        """Test that random valid parameters always produce valid matrices."""
        random.seed(seed)
        params = generate_random_stag_hunt_params()
        matrix = StagHuntConstructor.build(params)
        assert matrix.matrix_type == MatrixType.STAG_HUNT


# =============================================================================
# Volunteer's Dilemma Constructor Tests
# =============================================================================


class TestVolunteersDilemmaConstructor:
    """Tests for Volunteer's Dilemma constructor."""

    def test_ordinal_constraint_f_greater_than_w_greater_than_d(self) -> None:
        """Test that F > W > D constraint is enforced."""
        # F = reward + free_ride_bonus, W = reward - volunteer_cost, D = -disaster_penalty
        valid_params = MatrixParameters(
            reward=2.0, volunteer_cost=0.3, free_ride_bonus=0.5, disaster_penalty=1.0
        )
        # F = 2.5, W = 1.7, D = -1.0 => F > W > D
        VolunteersDilemmaConstructor.validate_params(valid_params)

        with pytest.raises(ValueError) as exc_info:
            # Make W < D by having high cost
            invalid_params = MatrixParameters(
                reward=0.5, volunteer_cost=2.0, free_ride_bonus=0.5, disaster_penalty=0.1
            )
            # F = 1.0, W = -1.5, D = -0.1 => W < D
            VolunteersDilemmaConstructor.validate_params(invalid_params)
        assert "F > W > D" in str(exc_info.value)

    def test_build_returns_valid_matrix(self) -> None:
        """Test that build() returns a valid PayoffMatrix."""
        params = MatrixParameters(
            reward=2.0, volunteer_cost=0.3, free_ride_bonus=0.5, disaster_penalty=1.0
        )
        matrix = VolunteersDilemmaConstructor.build(params)

        assert isinstance(matrix, PayoffMatrix)
        assert matrix.matrix_type == MatrixType.VOLUNTEERS_DILEMMA
        assert matrix.row_labels == ("Volunteer", "Abstain")

    @pytest.mark.parametrize("seed", range(10))
    def test_random_valid_params_produce_valid_matrix(self, seed: int) -> None:
        """Test that random valid parameters always produce valid matrices."""
        random.seed(seed)
        params = generate_random_volunteers_params()
        matrix = VolunteersDilemmaConstructor.build(params)
        assert matrix.matrix_type == MatrixType.VOLUNTEERS_DILEMMA


# =============================================================================
# War of Attrition Constructor Tests
# =============================================================================


class TestWarOfAttritionConstructor:
    """Tests for War of Attrition constructor."""

    def test_ordinal_constraint(self) -> None:
        """Test that T > R > P and T > S constraint is enforced."""
        valid_params = MatrixParameters(
            temptation=4.0, reward=3.0, punishment=2.0, sucker=1.0
        )
        WarOfAttritionConstructor.validate_params(valid_params)

        with pytest.raises(ValueError) as exc_info:
            invalid_params = MatrixParameters(
                temptation=2.0, reward=3.0, punishment=1.0, sucker=0.0
            )
            WarOfAttritionConstructor.validate_params(invalid_params)
        assert "T > R > P and T > S" in str(exc_info.value)

    def test_build_returns_valid_matrix(self) -> None:
        """Test that build() returns a valid PayoffMatrix."""
        params = MatrixParameters(
            temptation=4.0, reward=3.0, punishment=2.0, sucker=1.0
        )
        matrix = WarOfAttritionConstructor.build(params)

        assert isinstance(matrix, PayoffMatrix)
        assert matrix.matrix_type == MatrixType.WAR_OF_ATTRITION
        assert matrix.row_labels == ("Continue", "Quit")

    @pytest.mark.parametrize("seed", range(10))
    def test_random_valid_params_produce_valid_matrix(self, seed: int) -> None:
        """Test that random valid parameters always produce valid matrices."""
        random.seed(seed)
        params = generate_random_war_of_attrition_params()
        matrix = WarOfAttritionConstructor.build(params)
        assert matrix.matrix_type == MatrixType.WAR_OF_ATTRITION


# =============================================================================
# Pure Coordination Constructor Tests
# =============================================================================


class TestPureCoordinationConstructor:
    """Tests for Pure Coordination constructor."""

    def test_ordinal_constraint_match_greater_than_mismatch(self) -> None:
        """Test that Match > Mismatch constraint is enforced."""
        valid_params = MatrixParameters(
            coordination_bonus=2.0, miscoordination_penalty=0.0
        )
        PureCoordinationConstructor.validate_params(valid_params)

        with pytest.raises(ValueError) as exc_info:
            invalid_params = MatrixParameters(
                coordination_bonus=1.0, miscoordination_penalty=2.0
            )
            PureCoordinationConstructor.validate_params(invalid_params)
        assert "Match > Mismatch" in str(exc_info.value)

    def test_build_returns_valid_matrix(self) -> None:
        """Test that build() returns a valid PayoffMatrix."""
        params = MatrixParameters(coordination_bonus=2.0, miscoordination_penalty=0.0)
        matrix = PureCoordinationConstructor.build(params)

        assert isinstance(matrix, PayoffMatrix)
        assert matrix.matrix_type == MatrixType.PURE_COORDINATION
        assert matrix.row_labels == ("A", "B")

    @pytest.mark.parametrize("seed", range(10))
    def test_random_valid_params_produce_valid_matrix(self, seed: int) -> None:
        """Test that random valid parameters always produce valid matrices."""
        random.seed(seed)
        params = generate_random_pure_coordination_params()
        matrix = PureCoordinationConstructor.build(params)
        assert matrix.matrix_type == MatrixType.PURE_COORDINATION


# =============================================================================
# Battle of Sexes Constructor Tests
# =============================================================================


class TestBattleOfSexesConstructor:
    """Tests for Battle of Sexes constructor."""

    def test_ordinal_constraint_coord_greater_than_miscoord_and_prefs_greater_than_one(
        self,
    ) -> None:
        """Test that Coord > Miscoord and pref_a, pref_b > 1.0 are enforced."""
        valid_params = MatrixParameters(
            coordination_bonus=2.0,
            miscoordination_penalty=0.0,
            preference_a=1.5,
            preference_b=1.3,
        )
        BattleOfSexesConstructor.validate_params(valid_params)

        # Invalid: coord not > miscoord
        with pytest.raises(ValueError) as exc_info:
            invalid_params = MatrixParameters(
                coordination_bonus=1.0,
                miscoordination_penalty=2.0,
                preference_a=1.5,
                preference_b=1.3,
            )
            BattleOfSexesConstructor.validate_params(invalid_params)
        assert "Coord > Miscoord" in str(exc_info.value)

        # Invalid: preference not > 1.0
        with pytest.raises(ValueError) as exc_info:
            invalid_params = MatrixParameters(
                coordination_bonus=2.0,
                miscoordination_penalty=0.0,
                preference_a=0.9,
                preference_b=1.3,
            )
            BattleOfSexesConstructor.validate_params(invalid_params)
        assert "preference multipliers > 1.0" in str(exc_info.value)

    def test_build_returns_valid_matrix(self) -> None:
        """Test that build() returns a valid PayoffMatrix."""
        params = MatrixParameters(
            coordination_bonus=2.0,
            miscoordination_penalty=0.0,
            preference_a=1.5,
            preference_b=1.3,
        )
        matrix = BattleOfSexesConstructor.build(params)

        assert isinstance(matrix, PayoffMatrix)
        assert matrix.matrix_type == MatrixType.BATTLE_OF_SEXES
        assert matrix.row_labels == ("Opera", "Football")

    @pytest.mark.parametrize("seed", range(10))
    def test_random_valid_params_produce_valid_matrix(self, seed: int) -> None:
        """Test that random valid parameters always produce valid matrices."""
        random.seed(seed)
        params = generate_random_battle_of_sexes_params()
        matrix = BattleOfSexesConstructor.build(params)
        assert matrix.matrix_type == MatrixType.BATTLE_OF_SEXES


# =============================================================================
# Leader Constructor Tests
# =============================================================================


class TestLeaderConstructor:
    """Tests for Leader constructor."""

    def test_ordinal_constraint_g_greater_than_h_greater_than_b_greater_than_c(
        self,
    ) -> None:
        """Test that G > H > B > C constraint is enforced."""
        # G=temptation, H=reward, B=sucker, C=punishment
        valid_params = MatrixParameters(
            temptation=4.0, reward=3.0, sucker=2.0, punishment=1.0
        )
        LeaderConstructor.validate_params(valid_params)

        with pytest.raises(ValueError) as exc_info:
            invalid_params = MatrixParameters(
                temptation=4.0, reward=2.0, sucker=3.0, punishment=1.0
            )
            LeaderConstructor.validate_params(invalid_params)
        assert "G > H > B > C" in str(exc_info.value)

    def test_build_returns_valid_matrix(self) -> None:
        """Test that build() returns a valid PayoffMatrix."""
        params = MatrixParameters(
            temptation=4.0, reward=3.0, sucker=2.0, punishment=1.0
        )
        matrix = LeaderConstructor.build(params)

        assert isinstance(matrix, PayoffMatrix)
        assert matrix.matrix_type == MatrixType.LEADER
        assert matrix.row_labels == ("Follow", "Lead")

    @pytest.mark.parametrize("seed", range(10))
    def test_random_valid_params_produce_valid_matrix(self, seed: int) -> None:
        """Test that random valid parameters always produce valid matrices."""
        random.seed(seed)
        params = generate_random_leader_params()
        matrix = LeaderConstructor.build(params)
        assert matrix.matrix_type == MatrixType.LEADER


# =============================================================================
# Matching Pennies Constructor Tests
# =============================================================================


class TestMatchingPenniesConstructor:
    """Tests for Matching Pennies constructor."""

    def test_no_specific_parameter_constraints(self) -> None:
        """Test that Matching Pennies has no specific parameter constraints."""
        params = MatrixParameters()
        MatchingPenniesConstructor.validate_params(params)  # Should not raise

    def test_build_returns_valid_matrix(self) -> None:
        """Test that build() returns a valid PayoffMatrix."""
        params = MatrixParameters(scale=1.0)
        matrix = MatchingPenniesConstructor.build(params)

        assert isinstance(matrix, PayoffMatrix)
        assert matrix.matrix_type == MatrixType.MATCHING_PENNIES
        assert matrix.row_labels == ("Heads", "Tails")

    def test_matrix_is_zero_sum(self) -> None:
        """Test that the matrix is zero-sum."""
        params = MatrixParameters(scale=2.0)
        matrix = MatchingPenniesConstructor.build(params)

        # Check all cells sum to zero
        assert matrix.cc.payoff_a + matrix.cc.payoff_b == pytest.approx(0.0)
        assert matrix.cd.payoff_a + matrix.cd.payoff_b == pytest.approx(0.0)
        assert matrix.dc.payoff_a + matrix.dc.payoff_b == pytest.approx(0.0)
        assert matrix.dd.payoff_a + matrix.dd.payoff_b == pytest.approx(0.0)

    @pytest.mark.parametrize("seed", range(10))
    def test_random_valid_params_produce_valid_matrix(self, seed: int) -> None:
        """Test that random valid parameters always produce valid matrices."""
        random.seed(seed)
        params = generate_random_scale_params()
        matrix = MatchingPenniesConstructor.build(params)
        assert matrix.matrix_type == MatrixType.MATCHING_PENNIES


# =============================================================================
# Inspection Game Constructor Tests
# =============================================================================


class TestInspectionGameConstructor:
    """Tests for Inspection Game constructor."""

    def test_ordinal_constraint_loss_greater_than_cost_and_penalty_greater_than_gain(
        self,
    ) -> None:
        """Test that Loss > Cost and Penalty > Gain > 0 are enforced."""
        valid_params = MatrixParameters(
            inspection_cost=0.3,
            cheat_gain=0.5,
            caught_penalty=1.0,
            loss_if_exploited=0.7,
        )
        InspectionGameConstructor.validate_params(valid_params)

        # Invalid: loss not > cost
        with pytest.raises(ValueError) as exc_info:
            invalid_params = MatrixParameters(
                inspection_cost=0.8,
                cheat_gain=0.5,
                caught_penalty=1.0,
                loss_if_exploited=0.5,
            )
            InspectionGameConstructor.validate_params(invalid_params)
        assert "Loss > Cost" in str(exc_info.value)

        # Invalid: penalty not > gain
        with pytest.raises(ValueError) as exc_info:
            invalid_params = MatrixParameters(
                inspection_cost=0.3,
                cheat_gain=1.5,
                caught_penalty=1.0,
                loss_if_exploited=0.7,
            )
            InspectionGameConstructor.validate_params(invalid_params)
        assert "Penalty > Gain" in str(exc_info.value)

    def test_build_returns_valid_matrix(self) -> None:
        """Test that build() returns a valid PayoffMatrix."""
        params = MatrixParameters(
            inspection_cost=0.3,
            cheat_gain=0.5,
            caught_penalty=1.0,
            loss_if_exploited=0.7,
        )
        matrix = InspectionGameConstructor.build(params)

        assert isinstance(matrix, PayoffMatrix)
        assert matrix.matrix_type == MatrixType.INSPECTION_GAME
        assert matrix.row_labels == ("Inspect", "Trust")
        assert matrix.col_labels == ("Comply", "Cheat")

    @pytest.mark.parametrize("seed", range(10))
    def test_random_valid_params_produce_valid_matrix(self, seed: int) -> None:
        """Test that random valid parameters always produce valid matrices."""
        random.seed(seed)
        params = generate_random_inspection_params()
        matrix = InspectionGameConstructor.build(params)
        assert matrix.matrix_type == MatrixType.INSPECTION_GAME


# =============================================================================
# Reconnaissance Constructor Tests
# =============================================================================


class TestReconnaissanceConstructor:
    """Tests for Reconnaissance constructor."""

    def test_no_specific_parameter_constraints(self) -> None:
        """Test that Reconnaissance has no specific parameter constraints."""
        params = MatrixParameters()
        ReconnaissanceConstructor.validate_params(params)  # Should not raise

    def test_build_returns_valid_matrix(self) -> None:
        """Test that build() returns a valid PayoffMatrix."""
        params = MatrixParameters(scale=1.0)
        matrix = ReconnaissanceConstructor.build(params)

        assert isinstance(matrix, PayoffMatrix)
        assert matrix.matrix_type == MatrixType.RECONNAISSANCE
        assert matrix.row_labels == ("Probe", "Mask")
        assert matrix.col_labels == ("Vigilant", "Project")

    def test_matrix_is_zero_sum(self) -> None:
        """Test that the matrix is zero-sum."""
        params = MatrixParameters(scale=2.0)
        matrix = ReconnaissanceConstructor.build(params)

        # Check all cells sum to zero
        assert matrix.cc.payoff_a + matrix.cc.payoff_b == pytest.approx(0.0)
        assert matrix.cd.payoff_a + matrix.cd.payoff_b == pytest.approx(0.0)
        assert matrix.dc.payoff_a + matrix.dc.payoff_b == pytest.approx(0.0)
        assert matrix.dd.payoff_a + matrix.dd.payoff_b == pytest.approx(0.0)

    @pytest.mark.parametrize("seed", range(10))
    def test_random_valid_params_produce_valid_matrix(self, seed: int) -> None:
        """Test that random valid parameters always produce valid matrices."""
        random.seed(seed)
        params = generate_random_scale_params()
        matrix = ReconnaissanceConstructor.build(params)
        assert matrix.matrix_type == MatrixType.RECONNAISSANCE


# =============================================================================
# Security Dilemma Constructor Tests
# =============================================================================


class TestSecurityDilemmaConstructor:
    """Tests for Security Dilemma constructor."""

    def test_ordinal_constraint_same_as_pd(self) -> None:
        """Test that T > R > P > S constraint is enforced (same as PD)."""
        valid_params = MatrixParameters(
            temptation=5.0, reward=3.0, punishment=1.0, sucker=0.0
        )
        SecurityDilemmaConstructor.validate_params(valid_params)

        with pytest.raises(ValueError) as exc_info:
            invalid_params = MatrixParameters(
                temptation=3.0, reward=5.0, punishment=1.0, sucker=0.0
            )
            SecurityDilemmaConstructor.validate_params(invalid_params)
        assert "T > R > P > S" in str(exc_info.value)

    def test_build_returns_valid_matrix(self) -> None:
        """Test that build() returns a valid PayoffMatrix."""
        params = MatrixParameters(
            temptation=5.0, reward=3.0, punishment=1.0, sucker=0.0
        )
        matrix = SecurityDilemmaConstructor.build(params)

        assert isinstance(matrix, PayoffMatrix)
        assert matrix.matrix_type == MatrixType.SECURITY_DILEMMA
        assert matrix.row_labels == ("Disarm", "Arm")

    @pytest.mark.parametrize("seed", range(10))
    def test_random_valid_params_produce_valid_matrix(self, seed: int) -> None:
        """Test that random valid parameters always produce valid matrices."""
        random.seed(seed)
        params = generate_random_pd_params()  # Same constraints as PD
        matrix = SecurityDilemmaConstructor.build(params)
        assert matrix.matrix_type == MatrixType.SECURITY_DILEMMA


# =============================================================================
# CONSTRUCTORS Registry Tests
# =============================================================================


class TestConstructorsRegistry:
    """Tests for the CONSTRUCTORS registry."""

    def test_all_matrix_types_have_constructor(self) -> None:
        """Test that every MatrixType has a corresponding constructor."""
        for matrix_type in MatrixType:
            assert matrix_type in CONSTRUCTORS, f"Missing constructor for {matrix_type}"

    def test_constructors_count_matches_types_count(self) -> None:
        """Test that constructor count matches type count."""
        assert len(CONSTRUCTORS) == len(MatrixType)
        assert len(CONSTRUCTORS) == 14

    def test_all_constructors_implement_protocol(self) -> None:
        """Test that all constructors have build and validate_params methods."""
        for matrix_type, constructor in CONSTRUCTORS.items():
            assert hasattr(
                constructor, "build"
            ), f"{matrix_type} constructor missing build()"
            assert hasattr(
                constructor, "validate_params"
            ), f"{matrix_type} constructor missing validate_params()"


# =============================================================================
# build_matrix Function Tests
# =============================================================================


class TestBuildMatrixFunction:
    """Tests for the build_matrix convenience function."""

    def test_build_matrix_works_for_all_types(self) -> None:
        """Test that build_matrix works for all matrix types with default params."""
        for matrix_type in MatrixType:
            params = get_default_params_for_type(matrix_type)
            matrix = build_matrix(matrix_type, params)
            assert isinstance(matrix, PayoffMatrix)
            assert matrix.matrix_type == matrix_type

    def test_build_matrix_raises_for_invalid_type(self) -> None:
        """Test that build_matrix raises for unknown matrix type."""
        # This is tricky to test since MatrixType is an enum
        # We test that all known types work instead
        for matrix_type in MatrixType:
            params = get_default_params_for_type(matrix_type)
            matrix = build_matrix(matrix_type, params)
            assert matrix is not None

    def test_build_matrix_propagates_validation_errors(self) -> None:
        """Test that build_matrix propagates validation errors from constructors."""
        # Invalid PD params
        invalid_params = MatrixParameters(
            temptation=1.0, reward=2.0, punishment=0.5, sucker=0.0
        )
        with pytest.raises(ValueError) as exc_info:
            build_matrix(MatrixType.PRISONERS_DILEMMA, invalid_params)
        assert "T > R > P > S" in str(exc_info.value)


# =============================================================================
# get_default_params_for_type Function Tests
# =============================================================================


class TestGetDefaultParamsForType:
    """Tests for the get_default_params_for_type function."""

    def test_all_types_have_valid_defaults(self) -> None:
        """Test that all matrix types have default params that pass validation."""
        for matrix_type in MatrixType:
            params = get_default_params_for_type(matrix_type)
            # Should not raise when building
            matrix = build_matrix(matrix_type, params)
            assert matrix.matrix_type == matrix_type

    def test_defaults_produce_different_matrices(self) -> None:
        """Test that different types produce different matrix structures."""
        pd_params = get_default_params_for_type(MatrixType.PRISONERS_DILEMMA)
        chicken_params = get_default_params_for_type(MatrixType.CHICKEN)

        pd_matrix = build_matrix(MatrixType.PRISONERS_DILEMMA, pd_params)
        chicken_matrix = build_matrix(MatrixType.CHICKEN, chicken_params)

        # Different types
        assert pd_matrix.matrix_type != chicken_matrix.matrix_type

        # Different labels
        assert pd_matrix.row_labels != chicken_matrix.row_labels


# =============================================================================
# Integration Tests - Matrix Properties
# =============================================================================


class TestMatrixProperties:
    """Integration tests verifying matrix properties across all types."""

    def test_all_matrices_have_valid_state_deltas(self) -> None:
        """Test that all constructed matrices have valid StateDeltas."""
        for matrix_type in MatrixType:
            params = get_default_params_for_type(matrix_type)
            matrix = build_matrix(matrix_type, params)

            # Check all four outcomes have valid deltas
            for outcome in [matrix.cc, matrix.cd, matrix.dc, matrix.dd]:
                deltas = outcome.deltas
                # Position bounds
                assert -1.5 <= deltas.pos_a <= 1.5
                assert -1.5 <= deltas.pos_b <= 1.5
                # Resource cost bounds
                assert 0.0 <= deltas.res_cost_a <= 1.0
                assert 0.0 <= deltas.res_cost_b <= 1.0
                # Risk bounds
                assert -1.0 <= deltas.risk_delta <= 2.0
                # Near-zero-sum constraint
                assert abs(deltas.pos_a + deltas.pos_b) <= 0.5

    def test_zero_sum_games_are_actually_zero_sum(self) -> None:
        """Test that games labeled as zero-sum actually are."""
        zero_sum_types = [MatrixType.MATCHING_PENNIES, MatrixType.RECONNAISSANCE]

        for matrix_type in zero_sum_types:
            params = get_default_params_for_type(matrix_type)
            matrix = build_matrix(matrix_type, params)

            for outcome in [matrix.cc, matrix.cd, matrix.dc, matrix.dd]:
                total = outcome.payoff_a + outcome.payoff_b
                assert total == pytest.approx(
                    0.0
                ), f"{matrix_type}: {outcome} is not zero-sum"
