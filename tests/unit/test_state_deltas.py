"""Comprehensive unit tests for state_deltas.py.

Tests cover:
1. StateDeltaOutcome dataclass - validation
2. Strict zero-sum constraint for position changes
3. DELTA_TEMPLATES - coverage for all 14 MatrixTypes
4. Act scaling (Act I, II, III) - actual behavior tests
5. get_delta_for_outcome function

NOTE: Ordinal consistency tests (T > R > P > S, etc.) were removed because
they conflict with the strict zero-sum position constraint. In a zero-sum game,
symmetric outcomes (CC, DD) must have pos_a = pos_b = 0, which violates ordinal
rankings like R > P (cooperation better than defection for symmetric cases).

See test_removal_log.md for details on removed tests.
"""

import pytest

from brinksmanship.engine.state_deltas import (
    DELTA_TEMPLATES,
    OutcomeBounds,
    OutcomeDeltaBounds,
    StateDeltaOutcome,
    StateDeltaTemplate,
    apply_act_scaling,
    apply_surplus_effects,
    get_delta_for_outcome,
    get_scaled_delta_for_outcome,
    validate_delta_full,
    validate_delta_outcome,
    validate_near_zero_sum,
)
from brinksmanship.models.matrices import MatrixType
from brinksmanship.models.state import GameState
from brinksmanship.parameters import (
    CAPTURE_RATE,
    CC_RISK_REDUCTION,
    DD_BURN_RATE,
    DD_RISK_INCREASE,
    EXPLOIT_POSITION_GAIN,
    SURPLUS_BASE,
    SURPLUS_STREAK_BONUS,
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

        # Exactly zero-sum symmetric
        delta_sym = StateDeltaOutcome(
            pos_a=0.0,
            pos_b=0.0,
            res_cost_a=0.0,
            res_cost_b=0.0,
            risk_delta=0.0,
        )
        assert validate_delta_outcome(delta_sym) is True

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
# Strict Zero-Sum Constraint Tests
# =============================================================================


class TestStrictZeroSumConstraint:
    """Tests for strict zero-sum position change constraint."""

    def test_exactly_zero_sum_is_valid(self) -> None:
        """Test that perfectly zero-sum position changes are valid."""
        delta = StateDeltaOutcome(pos_a=1.0, pos_b=-1.0, res_cost_a=0.0, res_cost_b=0.0, risk_delta=0.0)
        assert validate_near_zero_sum(delta) is True
        assert delta.pos_a + delta.pos_b == pytest.approx(0.0)

    def test_symmetric_zero_is_valid(self) -> None:
        """Test that symmetric zero (both 0) is valid."""
        delta = StateDeltaOutcome(pos_a=0.0, pos_b=0.0, res_cost_a=0.0, res_cost_b=0.0, risk_delta=0.0)
        assert validate_near_zero_sum(delta) is True

    def test_all_templates_are_strictly_zero_sum(self) -> None:
        """Test that all templates have strictly zero-sum position changes.

        This is the key constraint: pos_a + pos_b = 0 for all outcomes.
        """
        for matrix_type in MatrixType:
            for outcome in ["CC", "CD", "DC", "DD"]:
                delta = get_delta_for_outcome(matrix_type, outcome)
                pos_sum = delta.pos_a + delta.pos_b
                assert abs(pos_sum) < 0.01, (
                    f"{matrix_type} {outcome} violates zero-sum: "
                    f"pos_a={delta.pos_a}, pos_b={delta.pos_b}, sum={pos_sum}"
                )


# =============================================================================
# DELTA_TEMPLATES Tests
# =============================================================================


class TestDeltaTemplates:
    """Tests for DELTA_TEMPLATES coverage and validity."""

    def test_template_exists_for_all_14_matrix_types(self) -> None:
        """Test that DELTA_TEMPLATES has an entry for all 14 MatrixTypes."""
        assert len(DELTA_TEMPLATES) == 14

        for matrix_type in MatrixType:
            assert matrix_type in DELTA_TEMPLATES, f"Missing template for {matrix_type}"

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
        for _matrix_type, template in DELTA_TEMPLATES.items():
            for outcome_name in ["cc", "cd", "dc", "dd"]:
                outcome = getattr(template, outcome_name)
                assert isinstance(outcome.pos_a, OutcomeBounds)
                assert isinstance(outcome.pos_b, OutcomeBounds)
                assert isinstance(outcome.res_cost_a, OutcomeBounds)
                assert isinstance(outcome.res_cost_b, OutcomeBounds)
                assert isinstance(outcome.risk, OutcomeBounds)

    def test_all_template_midpoints_pass_global_bounds(self) -> None:
        """Test that midpoints of all template bounds pass global bounds validation."""
        for matrix_type in MatrixType:
            for outcome in ["CC", "CD", "DC", "DD"]:
                delta = get_delta_for_outcome(matrix_type, outcome)

                # Check bounds
                is_valid = validate_delta_outcome(delta)
                assert is_valid, f"{matrix_type} {outcome} midpoint fails bounds: {delta}"

    def test_asymmetric_outcomes_are_zero_sum(self) -> None:
        """Test that asymmetric outcomes (CD, DC) are zero-sum.

        In asymmetric outcomes, one player gains what the other loses.
        """
        for matrix_type in MatrixType:
            for outcome in ["CD", "DC"]:
                delta = get_delta_for_outcome(matrix_type, outcome)
                pos_sum = delta.pos_a + delta.pos_b
                assert abs(pos_sum) < 0.01, (
                    f"{matrix_type} {outcome} not zero-sum: pos_a={delta.pos_a}, pos_b={delta.pos_b}, sum={pos_sum}"
                )

    def test_outcome_bounds_are_well_formed(self) -> None:
        """Test that all OutcomeBounds have min <= max."""
        for _matrix_type, template in DELTA_TEMPLATES.items():
            for outcome_name in ["cc", "cd", "dc", "dd"]:
                outcome = getattr(template, outcome_name)
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
        base_delta = StateDeltaOutcome(pos_a=1.0, pos_b=-1.0, res_cost_a=0.5, res_cost_b=0.3, risk_delta=1.0)

        scaled = apply_act_scaling(base_delta, 0.7)

        assert scaled.pos_a == pytest.approx(0.7)
        assert scaled.pos_b == pytest.approx(-0.7)
        assert scaled.res_cost_a == pytest.approx(0.35)
        assert scaled.res_cost_b == pytest.approx(0.21)
        assert scaled.risk_delta == pytest.approx(0.7)

    def test_act_ii_no_change(self) -> None:
        """Test Act II (1.0) leaves values unchanged."""
        base_delta = StateDeltaOutcome(pos_a=1.0, pos_b=-1.0, res_cost_a=0.5, res_cost_b=0.3, risk_delta=1.0)

        scaled = apply_act_scaling(base_delta, 1.0)

        assert scaled.pos_a == pytest.approx(1.0)
        assert scaled.pos_b == pytest.approx(-1.0)
        assert scaled.res_cost_a == pytest.approx(0.5)
        assert scaled.res_cost_b == pytest.approx(0.3)
        assert scaled.risk_delta == pytest.approx(1.0)

    def test_act_iii_scales_up(self) -> None:
        """Test Act III (1.3) scales values up correctly."""
        base_delta = StateDeltaOutcome(pos_a=1.0, pos_b=-1.0, res_cost_a=0.5, res_cost_b=0.3, risk_delta=1.0)

        scaled = apply_act_scaling(base_delta, 1.3)

        assert scaled.pos_a == pytest.approx(1.3)
        assert scaled.pos_b == pytest.approx(-1.3)
        assert scaled.res_cost_a == pytest.approx(0.65)
        assert scaled.res_cost_b == pytest.approx(0.39)
        assert scaled.risk_delta == pytest.approx(1.3)

    def test_get_scaled_delta_for_outcome(self) -> None:
        """Test get_scaled_delta_for_outcome convenience function."""
        # Act I
        delta_act1 = get_scaled_delta_for_outcome(MatrixType.PRISONERS_DILEMMA, "CC", turn=2)
        base_delta = get_delta_for_outcome(MatrixType.PRISONERS_DILEMMA, "CC")
        expected_act1 = apply_act_scaling(base_delta, 0.7)
        assert delta_act1.pos_a == pytest.approx(expected_act1.pos_a)

        # Act II
        delta_act2 = get_scaled_delta_for_outcome(MatrixType.PRISONERS_DILEMMA, "CC", turn=6)
        expected_act2 = apply_act_scaling(base_delta, 1.0)
        assert delta_act2.pos_a == pytest.approx(expected_act2.pos_a)

        # Act III
        delta_act3 = get_scaled_delta_for_outcome(MatrixType.PRISONERS_DILEMMA, "CC", turn=10)
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
# Integration Tests
# =============================================================================


class TestIntegration:
    """Integration tests combining multiple features."""

    def test_full_workflow_get_and_scale_delta(self) -> None:
        """Test the full workflow of getting a delta and scaling it."""
        # Get base delta - use CD which should be zero-sum
        base_delta = get_delta_for_outcome(MatrixType.CHICKEN, "CD")

        # Verify it passes validation (bounds and zero-sum)
        assert validate_delta_outcome(base_delta) is True
        assert validate_near_zero_sum(base_delta) is True

        # Scale for different acts
        for turn, expected_mult in [(2, 0.7), (6, 1.0), (10, 1.3)]:
            scaled = get_scaled_delta_for_outcome(MatrixType.CHICKEN, "CD", turn)
            expected = apply_act_scaling(base_delta, expected_mult)
            assert scaled.pos_a == pytest.approx(expected.pos_a)
            assert scaled.risk_delta == pytest.approx(expected.risk_delta)

    def test_all_deltas_for_all_types_at_all_acts(self) -> None:
        """Test that all combinations of type/outcome/act produce deltas."""
        for matrix_type in MatrixType:
            for outcome in ["CC", "CD", "DC", "DD"]:
                for turn in [1, 5, 10]:  # Acts I, II, III
                    delta = get_scaled_delta_for_outcome(matrix_type, outcome, turn)
                    assert isinstance(delta, StateDeltaOutcome)

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
        assert len(errors) >= 4


# =============================================================================
# Surplus Mechanics Tests
# =============================================================================


class TestSurplusMechanics:
    """Tests for apply_surplus_effects function (Joint Investment model)."""

    def test_surplus_flow_cooperation_then_defection(self) -> None:
        """Test: 3 CCs build surplus, then one defection captures it.

        This end-to-end test verifies the complete surplus flow:
        1. Consecutive CC outcomes build surplus with streak bonus
        2. CD outcome captures a portion of the accumulated surplus
        3. Streak resets on defection
        """
        state = GameState()

        # Initial state checks
        assert state.cooperation_surplus == 0.0
        assert state.cooperation_streak == 0
        assert state.surplus_captured_a == 0.0
        assert state.surplus_captured_b == 0.0

        # 3 CC outcomes build surplus
        for _i in range(3):
            state = apply_surplus_effects(state, "CC")

        # Verify surplus built with streak bonus
        # Streak 0: 2.0 * (1 + 0.1 * 0) = 2.0
        # Streak 1: 2.0 * (1 + 0.1 * 1) = 2.2
        # Streak 2: 2.0 * (1 + 0.1 * 2) = 2.4
        expected_surplus = (
            SURPLUS_BASE * (1.0 + SURPLUS_STREAK_BONUS * 0)
            + SURPLUS_BASE * (1.0 + SURPLUS_STREAK_BONUS * 1)
            + SURPLUS_BASE * (1.0 + SURPLUS_STREAK_BONUS * 2)
        )
        assert state.cooperation_surplus == pytest.approx(expected_surplus, rel=0.01)
        assert state.cooperation_streak == 3

        # Risk should have decreased by 3 * CC_RISK_REDUCTION from initial 2.0
        expected_risk = max(0.0, 2.0 - 3 * CC_RISK_REDUCTION)
        assert state.risk_level == pytest.approx(expected_risk, rel=0.01)

        # Store surplus before defection
        surplus_before_defection = state.cooperation_surplus

        # One defection (CD - B captures)
        state = apply_surplus_effects(state, "CD")

        # Verify capture
        expected_captured = surplus_before_defection * CAPTURE_RATE
        assert state.surplus_captured_b == pytest.approx(expected_captured, rel=0.01)
        assert state.cooperation_surplus == pytest.approx(surplus_before_defection - expected_captured, rel=0.01)
        assert state.cooperation_streak == 0

        # Position should have shifted
        assert state.position_b == pytest.approx(5.0 + EXPLOIT_POSITION_GAIN, rel=0.01)
        assert state.position_a == pytest.approx(5.0 - EXPLOIT_POSITION_GAIN, rel=0.01)

    def test_dd_burns_surplus(self) -> None:
        """Test that DD outcome burns a fraction of surplus.

        DD destroys value (deadweight loss) rather than transferring it.
        """
        state = GameState()

        # Build some surplus first
        state = apply_surplus_effects(state, "CC")
        state = apply_surplus_effects(state, "CC")
        surplus_before = state.cooperation_surplus

        # DD burns surplus
        state = apply_surplus_effects(state, "DD")

        # Verify burn
        expected_surplus = surplus_before * (1.0 - DD_BURN_RATE)
        assert state.cooperation_surplus == pytest.approx(expected_surplus, rel=0.01)

        # Verify streak reset and risk spike
        assert state.cooperation_streak == 0
        # Risk after 2 CC: 2.0 - 2*0.5 = 1.0
        # Risk after DD: 1.0 + DD_RISK_INCREASE
        expected_risk = min(10.0, (2.0 - 2 * CC_RISK_REDUCTION) + DD_RISK_INCREASE)
        assert state.risk_level == pytest.approx(expected_risk, rel=0.01)

        # Verify no surplus was captured (it was destroyed)
        assert state.surplus_captured_a == 0.0
        assert state.surplus_captured_b == 0.0

    def test_dc_mirrors_cd(self) -> None:
        """Test that DC is mirror of CD (A captures instead of B)."""
        state = GameState()

        # Build some surplus
        state = apply_surplus_effects(state, "CC")
        state = apply_surplus_effects(state, "CC")
        surplus_before = state.cooperation_surplus

        # DC - A defects, B cooperates
        state = apply_surplus_effects(state, "DC")

        # A should capture surplus (mirror of CD)
        expected_captured = surplus_before * CAPTURE_RATE
        assert state.surplus_captured_a == pytest.approx(expected_captured, rel=0.01)
        assert state.surplus_captured_b == 0.0

        # Position should shift toward A
        assert state.position_a == pytest.approx(5.0 + EXPLOIT_POSITION_GAIN, rel=0.01)
        assert state.position_b == pytest.approx(5.0 - EXPLOIT_POSITION_GAIN, rel=0.01)

    def test_invalid_outcome_raises_error(self) -> None:
        """Test that invalid outcome raises ValueError."""
        state = GameState()

        with pytest.raises(ValueError) as exc_info:
            apply_surplus_effects(state, "XX")
        assert "Invalid outcome" in str(exc_info.value)

    def test_outcome_is_case_insensitive(self) -> None:
        """Test that outcome string is case-insensitive."""
        state1 = GameState()
        state2 = GameState()

        apply_surplus_effects(state1, "cc")
        apply_surplus_effects(state2, "CC")

        assert state1.cooperation_surplus == state2.cooperation_surplus
        assert state1.cooperation_streak == state2.cooperation_streak
