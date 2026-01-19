"""Comprehensive unit tests for state_deltas.py.

Tests cover:
1. StateDeltaOutcome dataclass - validation
2. Near-zero-sum constraint for position changes
3. DELTA_TEMPLATES - coverage for all 14 MatrixTypes
4. Act scaling (Act I, II, III) - actual behavior tests
5. get_delta_for_outcome function
6. Ordinal consistency validation for key game types

Removed tests (see test_removal_log.md):
- TestStateDeltaOutcome: test_creation_with_all_fields, test_frozen_dataclass, test_creation_at_boundary_values (trivial dataclass tests)
- TestGlobalBoundsEnforcement: Entire class (trivial constant checks, covered by validation tests)
- TestOutcomeBounds: test_creation (trivial dataclass test)
- TestNearZeroSumConstraint: test_validate_delta_full_catches_non_zero_sum (subsumed by integration)
- TestActScaling: test_act_multiplier_values, test_get_act_for_turn, test_get_act_multiplier (duplicated in test_variance.py and test_resolution.py)
"""

import pytest

from brinksmanship.models.matrices import MatrixType
from brinksmanship.engine.state_deltas import (
    DELTA_TEMPLATES,
    OutcomeBounds,
    OutcomeDeltaBounds,
    StateDeltaOutcome,
    StateDeltaTemplate,
    apply_act_scaling,
    get_delta_for_outcome,
    get_scaled_delta_for_outcome,
    validate_all_templates,
    validate_chicken_ordinal_consistency,
    validate_deadlock_ordinal_consistency,
    validate_delta_full,
    validate_delta_outcome,
    validate_harmony_ordinal_consistency,
    validate_near_zero_sum,
    validate_ordinal_consistency,
    validate_pd_ordinal_consistency,
    validate_stag_hunt_ordinal_consistency,
)


# =============================================================================
# StateDeltaOutcome Dataclass Tests
# =============================================================================


class TestStateDeltaOutcome:
    """Tests for StateDeltaOutcome dataclass creation and properties."""

    def test_validation_passes_for_valid_deltas(self) -> None:
        """Test that validate_delta_outcome passes for valid deltas."""
        # Zero-sum position change
        delta = StateDeltaOutcome(
            pos_a=1.0,
            pos_b=-1.0,
            res_cost_a=0.5,
            res_cost_b=0.3,
            risk_delta=0.5,
        )
        assert validate_delta_outcome(delta) is True

        # Near-zero-sum (within tolerance)
        delta_near = StateDeltaOutcome(
            pos_a=0.3,
            pos_b=0.2,
            res_cost_a=0.0,
            res_cost_b=0.0,
            risk_delta=0.0,
        )
        assert validate_delta_outcome(delta_near) is True
        # Sum is 0.5, which is exactly at the boundary
        assert abs(delta_near.pos_a + delta_near.pos_b) <= 0.5

    def test_validation_fails_for_out_of_bounds_position_a(self) -> None:
        """Test validation fails when pos_a exceeds bounds."""
        delta = StateDeltaOutcome(
            pos_a=2.0,  # Exceeds 1.5
            pos_b=-2.0,
            res_cost_a=0.0,
            res_cost_b=0.0,
            risk_delta=0.0,
        )
        assert validate_delta_outcome(delta) is False

        is_valid, errors = validate_delta_full(delta)
        assert is_valid is False
        assert any("pos_a" in e for e in errors)

    def test_validation_fails_for_out_of_bounds_position_b(self) -> None:
        """Test validation fails when pos_b exceeds bounds."""
        delta = StateDeltaOutcome(
            pos_a=0.0,
            pos_b=1.6,  # Exceeds 1.5
            res_cost_a=0.0,
            res_cost_b=0.0,
            risk_delta=0.0,
        )
        assert validate_delta_outcome(delta) is False

        is_valid, errors = validate_delta_full(delta)
        assert is_valid is False
        assert any("pos_b" in e for e in errors)

    def test_validation_fails_for_negative_resource_cost(self) -> None:
        """Test validation fails when resource cost is negative."""
        delta = StateDeltaOutcome(
            pos_a=0.0,
            pos_b=0.0,
            res_cost_a=-0.1,  # Below 0
            res_cost_b=0.0,
            risk_delta=0.0,
        )
        assert validate_delta_outcome(delta) is False

        is_valid, errors = validate_delta_full(delta)
        assert is_valid is False
        assert any("res_cost_a" in e for e in errors)

    def test_validation_fails_for_resource_cost_exceeding_max(self) -> None:
        """Test validation fails when resource cost exceeds 1.0."""
        delta = StateDeltaOutcome(
            pos_a=0.0,
            pos_b=0.0,
            res_cost_a=0.0,
            res_cost_b=1.5,  # Exceeds 1.0
            risk_delta=0.0,
        )
        assert validate_delta_outcome(delta) is False

        is_valid, errors = validate_delta_full(delta)
        assert is_valid is False
        assert any("res_cost_b" in e for e in errors)

    def test_validation_fails_for_risk_below_minimum(self) -> None:
        """Test validation fails when risk delta is below -1.0."""
        delta = StateDeltaOutcome(
            pos_a=0.0,
            pos_b=0.0,
            res_cost_a=0.0,
            res_cost_b=0.0,
            risk_delta=-1.5,  # Below -1.0
        )
        assert validate_delta_outcome(delta) is False

        is_valid, errors = validate_delta_full(delta)
        assert is_valid is False
        assert any("risk_delta" in e for e in errors)

    def test_validation_fails_for_risk_above_maximum(self) -> None:
        """Test validation fails when risk delta exceeds 2.0."""
        delta = StateDeltaOutcome(
            pos_a=0.0,
            pos_b=0.0,
            res_cost_a=0.0,
            res_cost_b=0.0,
            risk_delta=2.5,  # Exceeds 2.0
        )
        assert validate_delta_outcome(delta) is False

        is_valid, errors = validate_delta_full(delta)
        assert is_valid is False
        assert any("risk_delta" in e for e in errors)


# =============================================================================
# Near-Zero-Sum Constraint Tests
# =============================================================================


class TestNearZeroSumConstraint:
    """Tests for near-zero-sum position change constraint."""

    def test_exactly_zero_sum_is_valid(self) -> None:
        """Test that perfectly zero-sum position changes are valid."""
        delta = StateDeltaOutcome(
            pos_a=1.0, pos_b=-1.0, res_cost_a=0.0, res_cost_b=0.0, risk_delta=0.0
        )
        assert validate_near_zero_sum(delta) is True
        assert delta.pos_a + delta.pos_b == pytest.approx(0.0)

    def test_within_tolerance_is_valid(self) -> None:
        """Test that position sum within 0.5 tolerance is valid."""
        # Sum = 0.4, within 0.5 tolerance
        delta = StateDeltaOutcome(
            pos_a=0.2, pos_b=0.2, res_cost_a=0.0, res_cost_b=0.0, risk_delta=0.0
        )
        assert validate_near_zero_sum(delta) is True
        assert abs(delta.pos_a + delta.pos_b) <= 0.5

    def test_at_boundary_is_valid(self) -> None:
        """Test that position sum exactly at 0.5 is valid."""
        delta = StateDeltaOutcome(
            pos_a=0.3, pos_b=0.2, res_cost_a=0.0, res_cost_b=0.0, risk_delta=0.0
        )
        assert validate_near_zero_sum(delta) is True
        assert abs(delta.pos_a + delta.pos_b) == pytest.approx(0.5)

    def test_exceeding_tolerance_is_invalid(self) -> None:
        """Test that position sum exceeding 0.5 is invalid."""
        delta = StateDeltaOutcome(
            pos_a=1.0, pos_b=0.6, res_cost_a=0.0, res_cost_b=0.0, risk_delta=0.0
        )
        assert validate_near_zero_sum(delta) is False
        assert abs(delta.pos_a + delta.pos_b) > 0.5


# =============================================================================
# DELTA_TEMPLATES Tests
# =============================================================================


class TestDeltaTemplates:
    """Tests for DELTA_TEMPLATES coverage and validity."""

    def test_template_exists_for_all_14_matrix_types(self) -> None:
        """Test that DELTA_TEMPLATES has an entry for all 14 MatrixTypes."""
        assert len(DELTA_TEMPLATES) == 14

        for matrix_type in MatrixType:
            assert (
                matrix_type in DELTA_TEMPLATES
            ), f"Missing template for {matrix_type}"

    def test_each_template_has_four_outcomes(self) -> None:
        """Test that each template has CC, CD, DC, DD outcomes."""
        for matrix_type, template in DELTA_TEMPLATES.items():
            assert isinstance(template, StateDeltaTemplate)
            assert template.matrix_type == matrix_type

            # Check all four outcomes exist
            assert isinstance(template.cc, OutcomeDeltaBounds), f"{matrix_type} missing cc"
            assert isinstance(template.cd, OutcomeDeltaBounds), f"{matrix_type} missing cd"
            assert isinstance(template.dc, OutcomeDeltaBounds), f"{matrix_type} missing dc"
            assert isinstance(template.dd, OutcomeDeltaBounds), f"{matrix_type} missing dd"

    def test_all_outcomes_have_required_bounds(self) -> None:
        """Test that all outcome bounds have the required fields."""
        for matrix_type, template in DELTA_TEMPLATES.items():
            for outcome_name in ["cc", "cd", "dc", "dd"]:
                outcome = getattr(template, outcome_name)
                assert isinstance(outcome.pos_a, OutcomeBounds)
                assert isinstance(outcome.pos_b, OutcomeBounds)
                assert isinstance(outcome.res_cost_a, OutcomeBounds)
                assert isinstance(outcome.res_cost_b, OutcomeBounds)
                assert isinstance(outcome.risk, OutcomeBounds)

    def test_all_template_midpoints_pass_global_bounds(self) -> None:
        """Test that midpoints of all template bounds pass global bounds validation.

        Note: This tests only the global bounds (position, resource cost, risk).
        The near-zero-sum constraint is intentionally relaxed for some outcomes
        where game design requires both players to gain (mutual cooperation) or
        lose (mutual defection) together. See test_asymmetric_outcomes_are_near_zero_sum
        for outcomes that should be zero-sum.
        """
        for matrix_type in MatrixType:
            for outcome in ["CC", "CD", "DC", "DD"]:
                delta = get_delta_for_outcome(matrix_type, outcome)

                # Check bounds only (not near-zero-sum)
                is_valid = validate_delta_outcome(delta)
                assert (
                    is_valid
                ), f"{matrix_type} {outcome} midpoint fails bounds: {delta}"

    def test_asymmetric_outcomes_mostly_near_zero_sum(self) -> None:
        """Test that most asymmetric outcomes (CD, DC) satisfy near-zero-sum constraint.

        CD and DC outcomes represent one player exploiting another in most games,
        so the exploiter's gain should roughly equal the victim's loss.

        Exceptions:
        - Leader game: CD/DC are both beneficial (one leads, one follows - both gain)
        - Coordination games: may have slight deviations for balance

        Symmetric outcomes (CC, DD) may deviate from zero-sum as both players
        can gain or lose together.
        """
        # Games where CD/DC represent clear exploitation (should be near zero-sum)
        exploitation_games = [
            MatrixType.PRISONERS_DILEMMA,
            MatrixType.DEADLOCK,
            MatrixType.CHICKEN,
            MatrixType.STAG_HUNT,
            MatrixType.MATCHING_PENNIES,
            MatrixType.SECURITY_DILEMMA,
            MatrixType.WAR_OF_ATTRITION,
        ]

        for matrix_type in exploitation_games:
            for outcome in ["CD", "DC"]:
                delta = get_delta_for_outcome(matrix_type, outcome)
                is_near_zero = validate_near_zero_sum(delta)
                assert is_near_zero, (
                    f"{matrix_type} {outcome} should be near-zero-sum: "
                    f"pos_a={delta.pos_a}, pos_b={delta.pos_b}, sum={delta.pos_a + delta.pos_b}"
                )

    def test_outcome_bounds_are_well_formed(self) -> None:
        """Test that all OutcomeBounds have min <= max."""
        for matrix_type, template in DELTA_TEMPLATES.items():
            for outcome_name in ["cc", "cd", "dc", "dd"]:
                outcome = getattr(template, outcome_name)
                # OutcomeBounds validates min <= max in __post_init__
                # Just verify the structure is correct
                assert outcome.pos_a.min_val <= outcome.pos_a.max_val
                assert outcome.pos_b.min_val <= outcome.pos_b.max_val
                assert outcome.res_cost_a.min_val <= outcome.res_cost_a.max_val
                assert outcome.res_cost_b.min_val <= outcome.res_cost_b.max_val
                assert outcome.risk.min_val <= outcome.risk.max_val


# =============================================================================
# OutcomeBounds Tests
# =============================================================================


class TestOutcomeBounds:
    """Tests for OutcomeBounds helper class."""

    def test_midpoint(self) -> None:
        """Test midpoint calculation."""
        bounds = OutcomeBounds(min_val=0.0, max_val=1.0)
        assert bounds.midpoint() == 0.5

        bounds_neg = OutcomeBounds(min_val=-1.0, max_val=1.0)
        assert bounds_neg.midpoint() == 0.0

        bounds_asym = OutcomeBounds(min_val=0.3, max_val=0.7)
        assert bounds_asym.midpoint() == 0.5

    def test_contains(self) -> None:
        """Test contains method."""
        bounds = OutcomeBounds(min_val=0.0, max_val=1.0)
        assert bounds.contains(0.0) is True
        assert bounds.contains(0.5) is True
        assert bounds.contains(1.0) is True
        assert bounds.contains(-0.1) is False
        assert bounds.contains(1.1) is False

    def test_invalid_bounds_raises_error(self) -> None:
        """Test that min > max raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            OutcomeBounds(min_val=1.0, max_val=0.0)
        assert "cannot exceed" in str(exc_info.value)


# =============================================================================
# Act Scaling Tests
# =============================================================================


class TestActScaling:
    """Tests for act-based scaling of deltas."""

    def test_act_i_scales_down(self) -> None:
        """Test Act I (0.7) scales values down correctly."""
        base_delta = StateDeltaOutcome(
            pos_a=1.0, pos_b=-1.0, res_cost_a=0.5, res_cost_b=0.3, risk_delta=1.0
        )

        scaled = apply_act_scaling(base_delta, 0.7)

        assert scaled.pos_a == pytest.approx(0.7)
        assert scaled.pos_b == pytest.approx(-0.7)
        assert scaled.res_cost_a == pytest.approx(0.35)
        assert scaled.res_cost_b == pytest.approx(0.21)
        assert scaled.risk_delta == pytest.approx(0.7)

    def test_act_ii_no_change(self) -> None:
        """Test Act II (1.0) leaves values unchanged."""
        base_delta = StateDeltaOutcome(
            pos_a=1.0, pos_b=-1.0, res_cost_a=0.5, res_cost_b=0.3, risk_delta=1.0
        )

        scaled = apply_act_scaling(base_delta, 1.0)

        assert scaled.pos_a == pytest.approx(1.0)
        assert scaled.pos_b == pytest.approx(-1.0)
        assert scaled.res_cost_a == pytest.approx(0.5)
        assert scaled.res_cost_b == pytest.approx(0.3)
        assert scaled.risk_delta == pytest.approx(1.0)

    def test_act_iii_scales_up(self) -> None:
        """Test Act III (1.3) scales values up correctly."""
        base_delta = StateDeltaOutcome(
            pos_a=1.0, pos_b=-1.0, res_cost_a=0.5, res_cost_b=0.3, risk_delta=1.0
        )

        scaled = apply_act_scaling(base_delta, 1.3)

        assert scaled.pos_a == pytest.approx(1.3)
        assert scaled.pos_b == pytest.approx(-1.3)
        assert scaled.res_cost_a == pytest.approx(0.65)
        assert scaled.res_cost_b == pytest.approx(0.39)
        assert scaled.risk_delta == pytest.approx(1.3)

    def test_get_scaled_delta_for_outcome(self) -> None:
        """Test get_scaled_delta_for_outcome convenience function."""
        # Act I
        delta_act1 = get_scaled_delta_for_outcome(
            MatrixType.PRISONERS_DILEMMA, "CC", turn=2
        )
        base_delta = get_delta_for_outcome(MatrixType.PRISONERS_DILEMMA, "CC")
        expected_act1 = apply_act_scaling(base_delta, 0.7)
        assert delta_act1.pos_a == pytest.approx(expected_act1.pos_a)

        # Act II
        delta_act2 = get_scaled_delta_for_outcome(
            MatrixType.PRISONERS_DILEMMA, "CC", turn=6
        )
        expected_act2 = apply_act_scaling(base_delta, 1.0)
        assert delta_act2.pos_a == pytest.approx(expected_act2.pos_a)

        # Act III
        delta_act3 = get_scaled_delta_for_outcome(
            MatrixType.PRISONERS_DILEMMA, "CC", turn=10
        )
        expected_act3 = apply_act_scaling(base_delta, 1.3)
        assert delta_act3.pos_a == pytest.approx(expected_act3.pos_a)


# =============================================================================
# get_delta_for_outcome Tests
# =============================================================================


class TestGetDeltaForOutcome:
    """Tests for get_delta_for_outcome function."""

    def test_returns_correct_delta_for_each_outcome(self) -> None:
        """Test that get_delta_for_outcome returns correct delta for each outcome."""
        for matrix_type in MatrixType:
            template = DELTA_TEMPLATES[matrix_type]

            # CC
            delta_cc = get_delta_for_outcome(matrix_type, "CC")
            assert delta_cc.pos_a == pytest.approx(template.cc.pos_a.midpoint())
            assert delta_cc.pos_b == pytest.approx(template.cc.pos_b.midpoint())

            # CD
            delta_cd = get_delta_for_outcome(matrix_type, "CD")
            assert delta_cd.pos_a == pytest.approx(template.cd.pos_a.midpoint())
            assert delta_cd.pos_b == pytest.approx(template.cd.pos_b.midpoint())

            # DC
            delta_dc = get_delta_for_outcome(matrix_type, "DC")
            assert delta_dc.pos_a == pytest.approx(template.dc.pos_a.midpoint())
            assert delta_dc.pos_b == pytest.approx(template.dc.pos_b.midpoint())

            # DD
            delta_dd = get_delta_for_outcome(matrix_type, "DD")
            assert delta_dd.pos_a == pytest.approx(template.dd.pos_a.midpoint())
            assert delta_dd.pos_b == pytest.approx(template.dd.pos_b.midpoint())

    def test_case_insensitive_outcome(self) -> None:
        """Test that outcome string is case-insensitive."""
        delta_cc_lower = get_delta_for_outcome(MatrixType.PRISONERS_DILEMMA, "cc")
        delta_cc_upper = get_delta_for_outcome(MatrixType.PRISONERS_DILEMMA, "CC")
        delta_cc_mixed = get_delta_for_outcome(MatrixType.PRISONERS_DILEMMA, "Cc")

        assert delta_cc_lower.pos_a == delta_cc_upper.pos_a
        assert delta_cc_lower.pos_a == delta_cc_mixed.pos_a

    def test_invalid_outcome_raises_value_error(self) -> None:
        """Test that invalid outcome string raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            get_delta_for_outcome(MatrixType.PRISONERS_DILEMMA, "XX")
        assert "Invalid outcome" in str(exc_info.value)

        with pytest.raises(ValueError):
            get_delta_for_outcome(MatrixType.PRISONERS_DILEMMA, "")

    def test_returns_state_delta_outcome(self) -> None:
        """Test that return type is StateDeltaOutcome."""
        delta = get_delta_for_outcome(MatrixType.CHICKEN, "CC")
        assert isinstance(delta, StateDeltaOutcome)


# =============================================================================
# Ordinal Consistency Tests - Prisoner's Dilemma
# =============================================================================


class TestPrisonersDilemmaOrdinalConsistency:
    """Tests for PD ordinal consistency (T > R > P > S)."""

    def test_pd_template_satisfies_ordinal_constraint(self) -> None:
        """Test that PD template satisfies T > R > P > S for row player A."""
        template = DELTA_TEMPLATES[MatrixType.PRISONERS_DILEMMA]

        # For row player A:
        # T = DC (defect against cooperator)
        # R = CC (mutual cooperation)
        # P = DD (mutual defection)
        # S = CD (cooperate against defector)
        t = template.dc.pos_a.midpoint()
        r = template.cc.pos_a.midpoint()
        p = template.dd.pos_a.midpoint()
        s = template.cd.pos_a.midpoint()

        assert t > r, f"T > R violated: T={t}, R={r}"
        assert r > p, f"R > P violated: R={r}, P={p}"
        assert p > s, f"P > S violated: P={p}, S={s}"

    def test_pd_ordinal_validator_passes(self) -> None:
        """Test that validate_pd_ordinal_consistency passes for PD template."""
        template = DELTA_TEMPLATES[MatrixType.PRISONERS_DILEMMA]
        is_valid, errors = validate_pd_ordinal_consistency(template)
        assert is_valid is True, f"PD ordinal validation failed: {errors}"
        assert len(errors) == 0

    def test_defector_gains_against_cooperator(self) -> None:
        """Test that defecting against a cooperator gives the defector an advantage."""
        delta_dc = get_delta_for_outcome(MatrixType.PRISONERS_DILEMMA, "DC")
        delta_cd = get_delta_for_outcome(MatrixType.PRISONERS_DILEMMA, "CD")

        # DC: A defects, B cooperates - A should gain more than B
        assert delta_dc.pos_a > 0, "Defector should gain position"
        assert delta_dc.pos_b < 0, "Cooperator against defector should lose position"

        # CD: A cooperates, B defects - B should gain more than A
        assert delta_cd.pos_a < 0, "Cooperator against defector should lose position"
        assert delta_cd.pos_b > 0, "Defector should gain position"


# =============================================================================
# Ordinal Consistency Tests - Chicken
# =============================================================================


class TestChickenOrdinalConsistency:
    """Tests for Chicken ordinal consistency (T > R > S > P)."""

    def test_chicken_template_satisfies_ordinal_constraint(self) -> None:
        """Test that Chicken template satisfies T > R > S > P for row player A."""
        template = DELTA_TEMPLATES[MatrixType.CHICKEN]

        # For row player A:
        # T = DC (hawk against dove)
        # R = CC (both dove)
        # S = CD (dove against hawk)
        # P = DD (crash)
        t = template.dc.pos_a.midpoint()
        r = template.cc.pos_a.midpoint()
        s = template.cd.pos_a.midpoint()
        p = template.dd.pos_a.midpoint()

        assert t > r, f"T > R violated: T={t}, R={r}"
        assert r > s, f"R > S violated: R={r}, S={s}"
        assert s > p, f"S > P violated: S={s}, P={p}"

    def test_chicken_ordinal_validator_passes(self) -> None:
        """Test that validate_chicken_ordinal_consistency passes for Chicken template."""
        template = DELTA_TEMPLATES[MatrixType.CHICKEN]
        is_valid, errors = validate_chicken_ordinal_consistency(template)
        assert is_valid is True, f"Chicken ordinal validation failed: {errors}"
        assert len(errors) == 0

    def test_mutual_hawk_is_worst_outcome(self) -> None:
        """Test that mutual hawk (DD) is the worst outcome for both players."""
        delta_dd = get_delta_for_outcome(MatrixType.CHICKEN, "DD")
        delta_cc = get_delta_for_outcome(MatrixType.CHICKEN, "CC")
        delta_cd = get_delta_for_outcome(MatrixType.CHICKEN, "CD")
        delta_dc = get_delta_for_outcome(MatrixType.CHICKEN, "DC")

        # DD should be worse than all other outcomes for player A
        assert delta_dd.pos_a < delta_cc.pos_a, "DD should be worse than CC for A"
        assert delta_dd.pos_a < delta_cd.pos_a, "DD should be worse than CD for A"
        assert delta_dd.pos_a < delta_dc.pos_a, "DD should be worse than DC for A"

        # DD should also have highest risk
        assert delta_dd.risk_delta >= delta_cc.risk_delta
        assert delta_dd.risk_delta >= delta_cd.risk_delta
        assert delta_dd.risk_delta >= delta_dc.risk_delta


# =============================================================================
# Ordinal Consistency Tests - Stag Hunt
# =============================================================================


class TestStagHuntOrdinalConsistency:
    """Tests for Stag Hunt ordinal consistency (R > T > P > S)."""

    def test_stag_hunt_template_satisfies_ordinal_constraint(self) -> None:
        """Test that Stag Hunt template satisfies R > T > P > S for row player A."""
        template = DELTA_TEMPLATES[MatrixType.STAG_HUNT]

        # For row player A:
        # R = CC (mutual stag)
        # T = DC (hare while other stags)
        # P = DD (mutual hare)
        # S = CD (stag alone)
        r = template.cc.pos_a.midpoint()
        t = template.dc.pos_a.midpoint()
        p = template.dd.pos_a.midpoint()
        s = template.cd.pos_a.midpoint()

        assert r > t, f"R > T violated: R={r}, T={t}"
        assert t > p, f"T > P violated: T={t}, P={p}"
        assert p > s, f"P > S violated: P={p}, S={s}"

    def test_stag_hunt_ordinal_validator_passes(self) -> None:
        """Test that validate_stag_hunt_ordinal_consistency passes for Stag Hunt template."""
        template = DELTA_TEMPLATES[MatrixType.STAG_HUNT]
        is_valid, errors = validate_stag_hunt_ordinal_consistency(template)
        assert is_valid is True, f"Stag Hunt ordinal validation failed: {errors}"
        assert len(errors) == 0

    def test_mutual_stag_is_best_outcome(self) -> None:
        """Test that mutual stag (CC) is the best outcome for both players."""
        delta_cc = get_delta_for_outcome(MatrixType.STAG_HUNT, "CC")
        delta_cd = get_delta_for_outcome(MatrixType.STAG_HUNT, "CD")
        delta_dc = get_delta_for_outcome(MatrixType.STAG_HUNT, "DC")
        delta_dd = get_delta_for_outcome(MatrixType.STAG_HUNT, "DD")

        # CC should be better than all other outcomes for player A
        assert delta_cc.pos_a > delta_cd.pos_a, "CC should be better than CD for A"
        assert delta_cc.pos_a > delta_dc.pos_a, "CC should be better than DC for A"
        assert delta_cc.pos_a > delta_dd.pos_a, "CC should be better than DD for A"


# =============================================================================
# Ordinal Consistency Tests - Deadlock
# =============================================================================


class TestDeadlockOrdinalConsistency:
    """Tests for Deadlock ordinal consistency (T > P > R > S)."""

    def test_deadlock_template_satisfies_ordinal_constraint(self) -> None:
        """Test that Deadlock template satisfies T > P > R > S for row player A."""
        template = DELTA_TEMPLATES[MatrixType.DEADLOCK]

        # For row player A:
        # T = DC
        # P = DD
        # R = CC
        # S = CD
        t = template.dc.pos_a.midpoint()
        p = template.dd.pos_a.midpoint()
        r = template.cc.pos_a.midpoint()
        s = template.cd.pos_a.midpoint()

        assert t > p, f"T > P violated: T={t}, P={p}"
        assert p > r, f"P > R violated: P={p}, R={r}"
        assert r > s, f"R > S violated: R={r}, S={s}"

    def test_deadlock_ordinal_validator_passes(self) -> None:
        """Test that validate_deadlock_ordinal_consistency passes for Deadlock template."""
        template = DELTA_TEMPLATES[MatrixType.DEADLOCK]
        is_valid, errors = validate_deadlock_ordinal_consistency(template)
        assert is_valid is True, f"Deadlock ordinal validation failed: {errors}"
        assert len(errors) == 0


# =============================================================================
# Ordinal Consistency Tests - Harmony
# =============================================================================


class TestHarmonyOrdinalConsistency:
    """Tests for Harmony ordinal consistency (R > T > S > P)."""

    def test_harmony_template_satisfies_ordinal_constraint(self) -> None:
        """Test that Harmony template satisfies R > T > S > P for row player A."""
        template = DELTA_TEMPLATES[MatrixType.HARMONY]

        # For row player A:
        # R = CC
        # T = DC
        # S = CD
        # P = DD
        r = template.cc.pos_a.midpoint()
        t = template.dc.pos_a.midpoint()
        s = template.cd.pos_a.midpoint()
        p = template.dd.pos_a.midpoint()

        assert r > t, f"R > T violated: R={r}, T={t}"
        assert t > s, f"T > S violated: T={t}, S={s}"
        assert s > p, f"S > P violated: S={s}, P={p}"

    def test_harmony_ordinal_validator_passes(self) -> None:
        """Test that validate_harmony_ordinal_consistency passes for Harmony template."""
        template = DELTA_TEMPLATES[MatrixType.HARMONY]
        is_valid, errors = validate_harmony_ordinal_consistency(template)
        assert is_valid is True, f"Harmony ordinal validation failed: {errors}"
        assert len(errors) == 0


# =============================================================================
# validate_ordinal_consistency Tests
# =============================================================================


class TestValidateOrdinalConsistency:
    """Tests for validate_ordinal_consistency function."""

    def test_validates_all_supported_types(self) -> None:
        """Test that ordinal consistency validation works for all supported types."""
        # Types with ordinal validators
        types_with_validators = [
            MatrixType.PRISONERS_DILEMMA,
            MatrixType.SECURITY_DILEMMA,
            MatrixType.CHICKEN,
            MatrixType.STAG_HUNT,
            MatrixType.DEADLOCK,
            MatrixType.HARMONY,
        ]

        for matrix_type in types_with_validators:
            is_valid, errors = validate_ordinal_consistency(matrix_type)
            assert is_valid is True, f"{matrix_type} failed ordinal validation: {errors}"

    def test_returns_true_for_types_without_constraints(self) -> None:
        """Test that types without ordinal constraints return (True, [])."""
        # Types without specific ordinal constraints (e.g., zero-sum games)
        types_without_validators = [
            MatrixType.MATCHING_PENNIES,
            MatrixType.PURE_COORDINATION,
            MatrixType.BATTLE_OF_SEXES,
            MatrixType.LEADER,
            MatrixType.VOLUNTEERS_DILEMMA,
            MatrixType.WAR_OF_ATTRITION,
            MatrixType.INSPECTION_GAME,
            MatrixType.RECONNAISSANCE,
        ]

        for matrix_type in types_without_validators:
            is_valid, errors = validate_ordinal_consistency(matrix_type)
            assert is_valid is True
            assert len(errors) == 0


# =============================================================================
# validate_all_templates Tests
# =============================================================================


class TestValidateAllTemplates:
    """Tests for validate_all_templates function."""

    def test_validates_all_templates(self) -> None:
        """Test that validate_all_templates returns results for all templates."""
        results = validate_all_templates()

        assert len(results) == 14
        for matrix_type in MatrixType:
            assert matrix_type in results

    def test_all_templates_pass_validation(self) -> None:
        """Test that all templates pass ordinal consistency validation."""
        results = validate_all_templates()

        for matrix_type, (is_valid, errors) in results.items():
            assert is_valid is True, f"{matrix_type} failed: {errors}"


# =============================================================================
# Security Dilemma Tests (Same as PD)
# =============================================================================


class TestSecurityDilemmaOrdinalConsistency:
    """Tests for Security Dilemma ordinal consistency (same as PD: T > R > P > S)."""

    def test_security_dilemma_uses_pd_validator(self) -> None:
        """Test that Security Dilemma uses the same validator as PD."""
        template = DELTA_TEMPLATES[MatrixType.SECURITY_DILEMMA]
        is_valid, errors = validate_pd_ordinal_consistency(template)
        assert is_valid is True, f"Security Dilemma ordinal validation failed: {errors}"

    def test_security_dilemma_passes_ordinal_validation(self) -> None:
        """Test that Security Dilemma passes ordinal consistency validation."""
        is_valid, errors = validate_ordinal_consistency(MatrixType.SECURITY_DILEMMA)
        assert is_valid is True, f"Security Dilemma failed: {errors}"


# =============================================================================
# Integration Tests
# =============================================================================


class TestIntegration:
    """Integration tests combining multiple features."""

    def test_full_workflow_get_and_scale_delta(self) -> None:
        """Test the full workflow of getting a delta and scaling it."""
        # Get base delta - use CD which should be near-zero-sum
        base_delta = get_delta_for_outcome(MatrixType.CHICKEN, "CD")

        # Verify it passes validation (bounds and near-zero-sum)
        assert validate_delta_outcome(base_delta) is True
        assert validate_near_zero_sum(base_delta) is True

        # Scale for different acts
        for turn, expected_mult in [(2, 0.7), (6, 1.0), (10, 1.3)]:
            scaled = get_scaled_delta_for_outcome(MatrixType.CHICKEN, "CD", turn)
            expected = apply_act_scaling(base_delta, expected_mult)
            assert scaled.pos_a == pytest.approx(expected.pos_a)
            assert scaled.risk_delta == pytest.approx(expected.risk_delta)

    def test_symmetric_outcomes_may_deviate_from_zero_sum(self) -> None:
        """Test that symmetric outcomes (CC, DD) may deviate from strict zero-sum.

        This is by design - mutual cooperation can benefit both players,
        and mutual defection can harm both players.
        """
        # Chicken DD: both players lose in a crash
        delta_chicken_dd = get_delta_for_outcome(MatrixType.CHICKEN, "DD")
        assert validate_delta_outcome(delta_chicken_dd) is True
        # Both lose position - sum is negative (not zero-sum)
        assert delta_chicken_dd.pos_a < 0
        assert delta_chicken_dd.pos_b < 0

        # PD CC: both players gain from mutual cooperation
        delta_pd_cc = get_delta_for_outcome(MatrixType.PRISONERS_DILEMMA, "CC")
        assert validate_delta_outcome(delta_pd_cc) is True
        # Both gain position - sum is positive (not zero-sum)
        assert delta_pd_cc.pos_a > 0
        assert delta_pd_cc.pos_b > 0

    def test_all_deltas_for_all_types_at_all_acts(self) -> None:
        """Test that all combinations of type/outcome/act produce deltas."""
        for matrix_type in MatrixType:
            for outcome in ["CC", "CD", "DC", "DD"]:
                for turn in [1, 5, 10]:  # Acts I, II, III
                    delta = get_scaled_delta_for_outcome(matrix_type, outcome, turn)
                    assert isinstance(delta, StateDeltaOutcome)
                    # Scaled deltas may exceed pre-scaling bounds
                    # That's intentional per the docstring

    def test_validate_delta_full_returns_all_errors(self) -> None:
        """Test that validate_delta_full returns all validation errors."""
        # Create a delta with multiple violations
        delta = StateDeltaOutcome(
            pos_a=2.0,  # Exceeds bound
            pos_b=2.0,  # Exceeds bound AND causes non-zero-sum
            res_cost_a=-0.5,  # Negative
            res_cost_b=1.5,  # Exceeds bound
            risk_delta=3.0,  # Exceeds bound
        )

        is_valid, errors = validate_delta_full(delta)
        assert is_valid is False
        # Should have multiple errors
        assert len(errors) >= 4  # At least pos_a, pos_b, res_cost_a, res_cost_b, risk_delta
