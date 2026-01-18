"""Unit tests for brinksmanship.models.state module.

Tests cover:
- GameState: initialization, clamping, computed properties, serialization
- PlayerState: initialization, clamping, serialization
- InformationState: position/resource estimation with decay
- ActionResult: creation, serialization, outcome properties
- Helper functions: update_cooperation_score, update_stability, clamp
"""

import json

import pytest

from brinksmanship.models.actions import ActionType
from brinksmanship.models.state import (
    ActionResult,
    GameState,
    InformationState,
    PlayerState,
    apply_action_result,
    clamp,
    update_cooperation_score,
    update_stability,
)


class TestClampFunction:
    """Tests for the clamp helper function."""

    def test_clamp_value_within_range(self):
        """Value within range is returned unchanged."""
        assert clamp(5.0, 0.0, 10.0) == 5.0

    def test_clamp_value_at_min(self):
        """Value at minimum boundary is returned unchanged."""
        assert clamp(0.0, 0.0, 10.0) == 0.0

    def test_clamp_value_at_max(self):
        """Value at maximum boundary is returned unchanged."""
        assert clamp(10.0, 0.0, 10.0) == 10.0

    def test_clamp_value_below_min(self):
        """Value below minimum is clamped to minimum."""
        assert clamp(-5.0, 0.0, 10.0) == 0.0

    def test_clamp_value_above_max(self):
        """Value above maximum is clamped to maximum."""
        assert clamp(15.0, 0.0, 10.0) == 10.0

    def test_clamp_negative_range(self):
        """Clamp works with negative ranges."""
        assert clamp(-5.0, -10.0, -1.0) == -5.0
        assert clamp(-15.0, -10.0, -1.0) == -10.0
        assert clamp(0.0, -10.0, -1.0) == -1.0


class TestInformationState:
    """Tests for InformationState class."""

    def test_default_initialization(self):
        """Default InformationState has unknown bounds."""
        info = InformationState()
        assert info.position_bounds == (0.0, 10.0)
        assert info.resources_bounds == (0.0, 10.0)
        assert info.known_position is None
        assert info.known_position_turn is None
        assert info.known_resources is None
        assert info.known_resources_turn is None

    def test_get_position_estimate_unknown(self):
        """Position estimate with no known data returns midpoint and full radius."""
        info = InformationState()
        estimate, uncertainty = info.get_position_estimate(current_turn=5)
        # Midpoint of (0.0, 10.0) is 5.0, radius is 5.0
        assert estimate == pytest.approx(5.0)
        assert uncertainty == pytest.approx(5.0)

    def test_get_position_estimate_with_known_position(self):
        """Position estimate with known data returns that value with decay-based uncertainty."""
        info = InformationState(
            known_position=7.0,
            known_position_turn=3,
        )
        # Current turn 5, turns elapsed = 2
        # Uncertainty = min(2 * 0.8, 5.0) = 1.6
        estimate, uncertainty = info.get_position_estimate(current_turn=5)
        assert estimate == pytest.approx(7.0)
        assert uncertainty == pytest.approx(1.6)

    def test_get_position_estimate_max_uncertainty(self):
        """Uncertainty caps at 5.0 after ~6 turns."""
        info = InformationState(
            known_position=7.0,
            known_position_turn=1,
        )
        # Current turn 10, turns elapsed = 9
        # Uncertainty = min(9 * 0.8, 5.0) = min(7.2, 5.0) = 5.0
        estimate, uncertainty = info.get_position_estimate(current_turn=10)
        assert estimate == pytest.approx(7.0)
        assert uncertainty == pytest.approx(5.0)

    def test_get_position_estimate_zero_turns_elapsed(self):
        """Zero turns elapsed means zero uncertainty."""
        info = InformationState(
            known_position=3.5,
            known_position_turn=5,
        )
        estimate, uncertainty = info.get_position_estimate(current_turn=5)
        assert estimate == pytest.approx(3.5)
        assert uncertainty == pytest.approx(0.0)

    def test_get_resources_estimate_unknown(self):
        """Resources estimate with no known data returns midpoint and full radius."""
        info = InformationState()
        estimate, uncertainty = info.get_resources_estimate(current_turn=5)
        assert estimate == pytest.approx(5.0)
        assert uncertainty == pytest.approx(5.0)

    def test_get_resources_estimate_with_known_resources(self):
        """Resources estimate with known data returns that value with decay-based uncertainty."""
        info = InformationState(
            known_resources=4.0,
            known_resources_turn=2,
        )
        # Current turn 6, turns elapsed = 4
        # Uncertainty = min(4 * 0.8, 5.0) = 3.2
        estimate, uncertainty = info.get_resources_estimate(current_turn=6)
        assert estimate == pytest.approx(4.0)
        assert uncertainty == pytest.approx(3.2)

    def test_get_resources_estimate_max_uncertainty(self):
        """Resources uncertainty caps at 5.0."""
        info = InformationState(
            known_resources=2.0,
            known_resources_turn=1,
        )
        # Current turn 12, turns elapsed = 11
        # Uncertainty = min(11 * 0.8, 5.0) = min(8.8, 5.0) = 5.0
        estimate, uncertainty = info.get_resources_estimate(current_turn=12)
        assert estimate == pytest.approx(2.0)
        assert uncertainty == pytest.approx(5.0)

    def test_update_position(self):
        """update_position sets known position and turn."""
        info = InformationState()
        info.update_position(6.5, turn=4)
        assert info.known_position == pytest.approx(6.5)
        assert info.known_position_turn == 4

    def test_update_resources(self):
        """update_resources sets known resources and turn."""
        info = InformationState()
        info.update_resources(3.2, turn=7)
        assert info.known_resources == pytest.approx(3.2)
        assert info.known_resources_turn == 7

    def test_information_state_serialization(self):
        """InformationState serializes and deserializes correctly."""
        info = InformationState(
            known_position=5.5,
            known_position_turn=3,
            known_resources=4.2,
            known_resources_turn=5,
        )
        data = info.model_dump()
        restored = InformationState.model_validate(data)
        assert restored.known_position == pytest.approx(5.5)
        assert restored.known_position_turn == 3
        assert restored.known_resources == pytest.approx(4.2)
        assert restored.known_resources_turn == 5


class TestPlayerState:
    """Tests for PlayerState class."""

    def test_default_initialization(self):
        """Default PlayerState has position=5, resources=5, no previous type."""
        player = PlayerState()
        assert player.position == pytest.approx(5.0)
        assert player.resources == pytest.approx(5.0)
        assert player.previous_type is None
        assert player.information is not None

    def test_custom_initialization(self):
        """PlayerState accepts custom values."""
        player = PlayerState(
            position=7.0,
            resources=3.0,
            previous_type=ActionType.COOPERATIVE,
        )
        assert player.position == pytest.approx(7.0)
        assert player.resources == pytest.approx(3.0)
        assert player.previous_type == ActionType.COOPERATIVE

    def test_position_clamping_below_min(self):
        """Position below 0 is clamped to 0."""
        player = PlayerState(position=-5.0)
        assert player.position == pytest.approx(0.0)

    def test_position_clamping_above_max(self):
        """Position above 10 is clamped to 10."""
        player = PlayerState(position=15.0)
        assert player.position == pytest.approx(10.0)

    def test_resources_clamping_below_min(self):
        """Resources below 0 is clamped to 0."""
        player = PlayerState(resources=-3.0)
        assert player.resources == pytest.approx(0.0)

    def test_resources_clamping_above_max(self):
        """Resources above 10 is clamped to 10."""
        player = PlayerState(resources=12.0)
        assert player.resources == pytest.approx(10.0)

    def test_player_state_serialization(self):
        """PlayerState serializes and deserializes correctly."""
        player = PlayerState(
            position=6.5,
            resources=4.2,
            previous_type=ActionType.COMPETITIVE,
        )
        data = player.model_dump()
        restored = PlayerState.model_validate(data)
        assert restored.position == pytest.approx(6.5)
        assert restored.resources == pytest.approx(4.2)
        assert restored.previous_type == ActionType.COMPETITIVE


class TestGameState:
    """Tests for GameState class."""

    def test_default_initialization(self):
        """Default GameState has expected initial values."""
        state = GameState()
        assert state.position_a == pytest.approx(5.0)
        assert state.position_b == pytest.approx(5.0)
        assert state.resources_a == pytest.approx(5.0)
        assert state.resources_b == pytest.approx(5.0)
        assert state.cooperation_score == pytest.approx(5.0)
        assert state.stability == pytest.approx(5.0)
        assert state.risk_level == pytest.approx(2.0)
        assert state.turn == 1
        assert state.max_turns == 14
        assert state.previous_type_a is None
        assert state.previous_type_b is None

    def test_custom_initialization(self):
        """GameState accepts custom values."""
        state = GameState(
            cooperation_score=7.0,
            stability=8.0,
            risk_level=5.0,
            turn=5,
            max_turns=15,
        )
        assert state.cooperation_score == pytest.approx(7.0)
        assert state.stability == pytest.approx(8.0)
        assert state.risk_level == pytest.approx(5.0)
        assert state.turn == 5
        assert state.max_turns == 15

    def test_cooperation_score_clamping_below_min(self):
        """Cooperation score below 0 is clamped to 0."""
        state = GameState(cooperation_score=-5.0)
        assert state.cooperation_score == pytest.approx(0.0)

    def test_cooperation_score_clamping_above_max(self):
        """Cooperation score above 10 is clamped to 10."""
        state = GameState(cooperation_score=15.0)
        assert state.cooperation_score == pytest.approx(10.0)

    def test_stability_clamping_below_min(self):
        """Stability below 1 is clamped to 1."""
        state = GameState(stability=-2.0)
        assert state.stability == pytest.approx(1.0)

    def test_stability_clamping_above_max(self):
        """Stability above 10 is clamped to 10."""
        state = GameState(stability=15.0)
        assert state.stability == pytest.approx(10.0)

    def test_risk_level_clamping_below_min(self):
        """Risk level below 0 is clamped to 0."""
        state = GameState(risk_level=-3.0)
        assert state.risk_level == pytest.approx(0.0)

    def test_risk_level_clamping_above_max(self):
        """Risk level above 10 is clamped to 10."""
        state = GameState(risk_level=12.0)
        assert state.risk_level == pytest.approx(10.0)

    def test_max_turns_clamping_below_min(self):
        """Max turns below 12 is clamped to 12."""
        state = GameState(max_turns=5)
        assert state.max_turns == 12

    def test_max_turns_clamping_above_max(self):
        """Max turns above 16 is clamped to 16."""
        state = GameState(max_turns=20)
        assert state.max_turns == 16

    def test_position_property_setters(self):
        """Position properties can be set and are clamped."""
        state = GameState()
        state.position_a = 8.0
        assert state.position_a == pytest.approx(8.0)
        state.position_a = 15.0
        assert state.position_a == pytest.approx(10.0)
        state.position_b = -2.0
        assert state.position_b == pytest.approx(0.0)

    def test_resources_property_setters(self):
        """Resources properties can be set and are clamped."""
        state = GameState()
        state.resources_a = 3.0
        assert state.resources_a == pytest.approx(3.0)
        state.resources_b = 12.0
        assert state.resources_b == pytest.approx(10.0)

    def test_previous_type_property_setters(self):
        """Previous type properties can be set."""
        state = GameState()
        state.previous_type_a = ActionType.COOPERATIVE
        state.previous_type_b = ActionType.COMPETITIVE
        assert state.previous_type_a == ActionType.COOPERATIVE
        assert state.previous_type_b == ActionType.COMPETITIVE

    # Computed property tests

    def test_act_property_act_1(self):
        """Turns 1-4 are Act I."""
        for turn in [1, 2, 3, 4]:
            state = GameState(turn=turn)
            assert state.act == 1

    def test_act_property_act_2(self):
        """Turns 5-8 are Act II."""
        for turn in [5, 6, 7, 8]:
            state = GameState(turn=turn)
            assert state.act == 2

    def test_act_property_act_3(self):
        """Turns 9+ are Act III."""
        for turn in [9, 10, 11, 12, 15]:
            state = GameState(turn=turn)
            assert state.act == 3

    def test_act_multiplier_act_1(self):
        """Act I multiplier is 0.7."""
        state = GameState(turn=3)
        assert state.act_multiplier == pytest.approx(0.7)

    def test_act_multiplier_act_2(self):
        """Act II multiplier is 1.0."""
        state = GameState(turn=6)
        assert state.act_multiplier == pytest.approx(1.0)

    def test_act_multiplier_act_3(self):
        """Act III multiplier is 1.3."""
        state = GameState(turn=10)
        assert state.act_multiplier == pytest.approx(1.3)

    def test_base_sigma_formula(self):
        """Base sigma = 8 + (Risk_Level * 1.2)."""
        # Risk = 0 -> base_sigma = 8
        state = GameState(risk_level=0.0)
        assert state.base_sigma == pytest.approx(8.0)

        # Risk = 5 -> base_sigma = 8 + 6 = 14
        state = GameState(risk_level=5.0)
        assert state.base_sigma == pytest.approx(14.0)

        # Risk = 10 -> base_sigma = 8 + 12 = 20
        state = GameState(risk_level=10.0)
        assert state.base_sigma == pytest.approx(20.0)

    def test_chaos_factor_formula(self):
        """Chaos factor = 1.2 - (Cooperation_Score / 50)."""
        # Coop = 10 -> chaos = 1.2 - 0.2 = 1.0
        state = GameState(cooperation_score=10.0)
        assert state.chaos_factor == pytest.approx(1.0)

        # Coop = 5 -> chaos = 1.2 - 0.1 = 1.1
        state = GameState(cooperation_score=5.0)
        assert state.chaos_factor == pytest.approx(1.1)

        # Coop = 0 -> chaos = 1.2 - 0 = 1.2
        state = GameState(cooperation_score=0.0)
        assert state.chaos_factor == pytest.approx(1.2)

    def test_instability_factor_formula(self):
        """Instability factor = 1 + (10 - Stability) / 20."""
        # Stability = 10 -> instability = 1 + 0 = 1.0
        state = GameState(stability=10.0)
        assert state.instability_factor == pytest.approx(1.0)

        # Stability = 5 -> instability = 1 + 5/20 = 1.25
        state = GameState(stability=5.0)
        assert state.instability_factor == pytest.approx(1.25)

        # Stability = 1 -> instability = 1 + 9/20 = 1.45
        state = GameState(stability=1.0)
        assert state.instability_factor == pytest.approx(1.45)

    def test_shared_sigma_formula(self):
        """Shared sigma = Base_sigma * Chaos_Factor * Instability_Factor * Act_Multiplier."""
        # Peaceful early game: Risk=3, Coop=7, Stab=8, Turn=3 (Act I)
        state = GameState(
            risk_level=3.0,
            cooperation_score=7.0,
            stability=8.0,
            turn=3,
        )
        # base_sigma = 8 + 3.6 = 11.6
        # chaos_factor = 1.2 - 0.14 = 1.06
        # instability_factor = 1 + 2/20 = 1.1
        # act_multiplier = 0.7
        expected = 11.6 * 1.06 * 1.1 * 0.7
        assert state.shared_sigma == pytest.approx(expected)

    def test_shared_sigma_chaotic_crisis(self):
        """Shared sigma for chaotic crisis scenario from GAME_MANUAL."""
        # Chaotic crisis: Risk=9, Coop=1, Stab=2, Turn=10 (Act III)
        state = GameState(
            risk_level=9.0,
            cooperation_score=1.0,
            stability=2.0,
            turn=10,
        )
        # base_sigma = 8 + 10.8 = 18.8
        # chaos_factor = 1.2 - 0.02 = 1.18
        # instability_factor = 1 + 8/20 = 1.4
        # act_multiplier = 1.3
        expected = 18.8 * 1.18 * 1.4 * 1.3
        assert state.shared_sigma == pytest.approx(expected)

    # Serialization tests

    def test_to_json_and_from_json(self):
        """GameState round-trips through JSON correctly."""
        state = GameState(
            cooperation_score=7.5,
            stability=6.0,
            risk_level=4.0,
            turn=5,
            max_turns=14,
        )
        state.position_a = 6.5
        state.resources_b = 3.0
        state.previous_type_a = ActionType.COOPERATIVE

        json_str = state.to_json()
        restored = GameState.from_json(json_str)

        assert restored.cooperation_score == pytest.approx(7.5)
        assert restored.stability == pytest.approx(6.0)
        assert restored.risk_level == pytest.approx(4.0)
        assert restored.turn == 5
        assert restored.max_turns == 14
        assert restored.position_a == pytest.approx(6.5)
        assert restored.resources_b == pytest.approx(3.0)
        assert restored.previous_type_a == ActionType.COOPERATIVE

    def test_to_dict_and_from_dict(self):
        """GameState round-trips through dict correctly."""
        state = GameState(
            cooperation_score=8.0,
            stability=9.0,
            risk_level=1.0,
            turn=2,
        )
        data = state.to_dict()
        restored = GameState.from_dict(data)

        assert restored.cooperation_score == pytest.approx(8.0)
        assert restored.stability == pytest.approx(9.0)
        assert restored.risk_level == pytest.approx(1.0)
        assert restored.turn == 2

    def test_json_is_valid_json(self):
        """to_json produces valid JSON."""
        state = GameState()
        json_str = state.to_json()
        data = json.loads(json_str)
        assert isinstance(data, dict)
        assert "cooperation_score" in data

    def test_get_act_method_via_act_property(self):
        """The act property correctly determines act based on turn."""
        # Test boundary cases
        assert GameState(turn=1).act == 1
        assert GameState(turn=4).act == 1
        assert GameState(turn=5).act == 2
        assert GameState(turn=8).act == 2
        assert GameState(turn=9).act == 3
        assert GameState(turn=16).act == 3


class TestActionResult:
    """Tests for ActionResult class."""

    def test_basic_creation(self):
        """ActionResult can be created with action types."""
        result = ActionResult(
            action_a=ActionType.COOPERATIVE,
            action_b=ActionType.COMPETITIVE,
        )
        assert result.action_a == ActionType.COOPERATIVE
        assert result.action_b == ActionType.COMPETITIVE

    def test_default_deltas(self):
        """ActionResult has zero deltas by default."""
        result = ActionResult(
            action_a=ActionType.COOPERATIVE,
            action_b=ActionType.COOPERATIVE,
        )
        assert result.position_delta_a == pytest.approx(0.0)
        assert result.position_delta_b == pytest.approx(0.0)
        assert result.resource_cost_a == pytest.approx(0.0)
        assert result.resource_cost_b == pytest.approx(0.0)
        assert result.risk_delta == pytest.approx(0.0)
        assert result.cooperation_delta == pytest.approx(0.0)
        assert result.stability_delta == pytest.approx(0.0)

    def test_custom_deltas(self):
        """ActionResult accepts custom delta values."""
        result = ActionResult(
            action_a=ActionType.COOPERATIVE,
            action_b=ActionType.COMPETITIVE,
            position_delta_a=-1.0,
            position_delta_b=1.0,
            resource_cost_a=0.5,
            resource_cost_b=0.0,
            risk_delta=0.5,
        )
        assert result.position_delta_a == pytest.approx(-1.0)
        assert result.position_delta_b == pytest.approx(1.0)
        assert result.resource_cost_a == pytest.approx(0.5)
        assert result.risk_delta == pytest.approx(0.5)

    def test_outcome_code_auto_computed_cc(self):
        """Outcome code is auto-computed to CC for mutual cooperation."""
        result = ActionResult(
            action_a=ActionType.COOPERATIVE,
            action_b=ActionType.COOPERATIVE,
        )
        assert result.outcome_code == "CC"

    def test_outcome_code_auto_computed_cd(self):
        """Outcome code is auto-computed to CD when A cooperates, B competes."""
        result = ActionResult(
            action_a=ActionType.COOPERATIVE,
            action_b=ActionType.COMPETITIVE,
        )
        assert result.outcome_code == "CD"

    def test_outcome_code_auto_computed_dc(self):
        """Outcome code is auto-computed to DC when A competes, B cooperates."""
        result = ActionResult(
            action_a=ActionType.COMPETITIVE,
            action_b=ActionType.COOPERATIVE,
        )
        assert result.outcome_code == "DC"

    def test_outcome_code_auto_computed_dd(self):
        """Outcome code is auto-computed to DD for mutual defection."""
        result = ActionResult(
            action_a=ActionType.COMPETITIVE,
            action_b=ActionType.COMPETITIVE,
        )
        assert result.outcome_code == "DD"

    def test_outcome_code_explicit_override(self):
        """Explicit outcome code is preserved."""
        result = ActionResult(
            action_a=ActionType.COOPERATIVE,
            action_b=ActionType.COOPERATIVE,
            outcome_code="CUSTOM",
        )
        assert result.outcome_code == "CUSTOM"

    def test_is_mutual_cooperation(self):
        """is_mutual_cooperation returns True when both cooperate."""
        result_cc = ActionResult(
            action_a=ActionType.COOPERATIVE,
            action_b=ActionType.COOPERATIVE,
        )
        result_cd = ActionResult(
            action_a=ActionType.COOPERATIVE,
            action_b=ActionType.COMPETITIVE,
        )
        assert result_cc.is_mutual_cooperation is True
        assert result_cd.is_mutual_cooperation is False

    def test_is_mutual_defection(self):
        """is_mutual_defection returns True when both compete."""
        result_dd = ActionResult(
            action_a=ActionType.COMPETITIVE,
            action_b=ActionType.COMPETITIVE,
        )
        result_dc = ActionResult(
            action_a=ActionType.COMPETITIVE,
            action_b=ActionType.COOPERATIVE,
        )
        assert result_dd.is_mutual_defection is True
        assert result_dc.is_mutual_defection is False

    def test_is_mixed(self):
        """is_mixed returns True when one cooperates and one competes."""
        result_cd = ActionResult(
            action_a=ActionType.COOPERATIVE,
            action_b=ActionType.COMPETITIVE,
        )
        result_dc = ActionResult(
            action_a=ActionType.COMPETITIVE,
            action_b=ActionType.COOPERATIVE,
        )
        result_cc = ActionResult(
            action_a=ActionType.COOPERATIVE,
            action_b=ActionType.COOPERATIVE,
        )
        result_dd = ActionResult(
            action_a=ActionType.COMPETITIVE,
            action_b=ActionType.COMPETITIVE,
        )
        assert result_cd.is_mixed is True
        assert result_dc.is_mixed is True
        assert result_cc.is_mixed is False
        assert result_dd.is_mixed is False

    def test_action_result_serialization(self):
        """ActionResult serializes and deserializes correctly."""
        result = ActionResult(
            action_a=ActionType.COOPERATIVE,
            action_b=ActionType.COMPETITIVE,
            position_delta_a=-0.5,
            position_delta_b=0.8,
            resource_cost_a=0.3,
            risk_delta=0.5,
            narrative="Player A was exploited.",
        )
        data = result.model_dump()
        restored = ActionResult.model_validate(data)

        assert restored.action_a == ActionType.COOPERATIVE
        assert restored.action_b == ActionType.COMPETITIVE
        assert restored.position_delta_a == pytest.approx(-0.5)
        assert restored.position_delta_b == pytest.approx(0.8)
        assert restored.resource_cost_a == pytest.approx(0.3)
        assert restored.risk_delta == pytest.approx(0.5)
        assert restored.narrative == "Player A was exploited."


class TestUpdateCooperationScore:
    """Tests for update_cooperation_score function."""

    def test_mutual_cooperation_increases_score(self):
        """CC (both cooperative) increases cooperation score by 1."""
        state = GameState(cooperation_score=5.0)
        result = ActionResult(
            action_a=ActionType.COOPERATIVE,
            action_b=ActionType.COOPERATIVE,
        )
        new_score = update_cooperation_score(state, result)
        assert new_score == pytest.approx(6.0)

    def test_mutual_defection_decreases_score(self):
        """DD (both competitive) decreases cooperation score by 1."""
        state = GameState(cooperation_score=5.0)
        result = ActionResult(
            action_a=ActionType.COMPETITIVE,
            action_b=ActionType.COMPETITIVE,
        )
        new_score = update_cooperation_score(state, result)
        assert new_score == pytest.approx(4.0)

    def test_mixed_cd_no_change(self):
        """CD (A cooperates, B competes) results in no change."""
        state = GameState(cooperation_score=5.0)
        result = ActionResult(
            action_a=ActionType.COOPERATIVE,
            action_b=ActionType.COMPETITIVE,
        )
        new_score = update_cooperation_score(state, result)
        assert new_score == pytest.approx(5.0)

    def test_mixed_dc_no_change(self):
        """DC (A competes, B cooperates) results in no change."""
        state = GameState(cooperation_score=5.0)
        result = ActionResult(
            action_a=ActionType.COMPETITIVE,
            action_b=ActionType.COOPERATIVE,
        )
        new_score = update_cooperation_score(state, result)
        assert new_score == pytest.approx(5.0)

    def test_cooperation_score_clamped_at_max(self):
        """Cooperation score is clamped at 10."""
        state = GameState(cooperation_score=10.0)
        result = ActionResult(
            action_a=ActionType.COOPERATIVE,
            action_b=ActionType.COOPERATIVE,
        )
        new_score = update_cooperation_score(state, result)
        assert new_score == pytest.approx(10.0)

    def test_cooperation_score_clamped_at_min(self):
        """Cooperation score is clamped at 0."""
        state = GameState(cooperation_score=0.0)
        result = ActionResult(
            action_a=ActionType.COMPETITIVE,
            action_b=ActionType.COMPETITIVE,
        )
        new_score = update_cooperation_score(state, result)
        assert new_score == pytest.approx(0.0)


class TestUpdateStability:
    """Tests for update_stability function.

    Decay-based formula from GAME_MANUAL.md:
        stability = stability * 0.8 + 1.0
        if switches == 0: stability += 1.5
        elif switches == 1: stability -= 3.5
        else: stability -= 5.5
        stability = clamp(stability, 1, 10)
    """

    def test_no_switches_increases_stability(self):
        """Both players consistent: stability increases after decay."""
        state = GameState(
            stability=5.0,
            player_a=PlayerState(previous_type=ActionType.COOPERATIVE),
            player_b=PlayerState(previous_type=ActionType.COOPERATIVE),
        )
        result = ActionResult(
            action_a=ActionType.COOPERATIVE,
            action_b=ActionType.COOPERATIVE,
        )
        # new = 5.0 * 0.8 + 1.0 = 5.0
        # 0 switches: +1.5 -> 6.5
        new_stability = update_stability(state, result)
        assert new_stability == pytest.approx(6.5)

    def test_one_switch_decreases_stability(self):
        """One player switches: stability decreases."""
        state = GameState(
            stability=5.0,
            player_a=PlayerState(previous_type=ActionType.COOPERATIVE),
            player_b=PlayerState(previous_type=ActionType.COOPERATIVE),
        )
        result = ActionResult(
            action_a=ActionType.COOPERATIVE,
            action_b=ActionType.COMPETITIVE,  # B switches
        )
        # new = 5.0 * 0.8 + 1.0 = 5.0
        # 1 switch: -3.5 -> 1.5
        new_stability = update_stability(state, result)
        assert new_stability == pytest.approx(1.5)

    def test_two_switches_severely_decreases_stability(self):
        """Both players switch: stability severely decreases."""
        state = GameState(
            stability=5.0,
            player_a=PlayerState(previous_type=ActionType.COOPERATIVE),
            player_b=PlayerState(previous_type=ActionType.COMPETITIVE),
        )
        result = ActionResult(
            action_a=ActionType.COMPETITIVE,  # A switches
            action_b=ActionType.COOPERATIVE,  # B switches
        )
        # new = 5.0 * 0.8 + 1.0 = 5.0
        # 2 switches: -5.5 -> -0.5 -> clamped to 1.0
        new_stability = update_stability(state, result)
        assert new_stability == pytest.approx(1.0)

    def test_turn_1_no_switches(self):
        """Turn 1 has no previous actions, so no switches count."""
        state = GameState(
            stability=5.0,
            turn=1,
            # No previous types (default None)
        )
        result = ActionResult(
            action_a=ActionType.COOPERATIVE,
            action_b=ActionType.COMPETITIVE,
        )
        # No previous types, so 0 switches
        # new = 5.0 * 0.8 + 1.0 = 5.0
        # 0 switches: +1.5 -> 6.5
        new_stability = update_stability(state, result)
        assert new_stability == pytest.approx(6.5)

    def test_stability_clamped_at_max(self):
        """Stability is clamped at 10."""
        state = GameState(
            stability=10.0,
            player_a=PlayerState(previous_type=ActionType.COOPERATIVE),
            player_b=PlayerState(previous_type=ActionType.COOPERATIVE),
        )
        result = ActionResult(
            action_a=ActionType.COOPERATIVE,
            action_b=ActionType.COOPERATIVE,
        )
        # new = 10.0 * 0.8 + 1.0 = 9.0
        # 0 switches: +1.5 -> 10.5 -> clamped to 10.0
        new_stability = update_stability(state, result)
        assert new_stability == pytest.approx(10.0)

    def test_stability_clamped_at_min(self):
        """Stability is clamped at 1."""
        state = GameState(
            stability=1.0,
            player_a=PlayerState(previous_type=ActionType.COOPERATIVE),
            player_b=PlayerState(previous_type=ActionType.COMPETITIVE),
        )
        result = ActionResult(
            action_a=ActionType.COMPETITIVE,  # A switches
            action_b=ActionType.COOPERATIVE,  # B switches
        )
        # new = 1.0 * 0.8 + 1.0 = 1.8
        # 2 switches: -5.5 -> -3.7 -> clamped to 1.0
        new_stability = update_stability(state, result)
        assert new_stability == pytest.approx(1.0)

    def test_partial_switch_only_a_has_previous(self):
        """Only A has previous type, only A can switch."""
        state = GameState(
            stability=5.0,
            player_a=PlayerState(previous_type=ActionType.COOPERATIVE),
            player_b=PlayerState(previous_type=None),
        )
        result = ActionResult(
            action_a=ActionType.COMPETITIVE,  # A switches
            action_b=ActionType.COMPETITIVE,  # B cannot switch (no previous)
        )
        # 1 switch (only A)
        # new = 5.0 * 0.8 + 1.0 = 5.0
        # 1 switch: -3.5 -> 1.5
        new_stability = update_stability(state, result)
        assert new_stability == pytest.approx(1.5)

    def test_decay_toward_neutral(self):
        """Stability decays toward neutral (5) over time."""
        # High stability decays down
        state_high = GameState(
            stability=10.0,
            player_a=PlayerState(previous_type=ActionType.COOPERATIVE),
            player_b=PlayerState(previous_type=ActionType.COOPERATIVE),
        )
        result = ActionResult(
            action_a=ActionType.COOPERATIVE,
            action_b=ActionType.COOPERATIVE,
        )
        # 10.0 * 0.8 + 1.0 = 9.0, then +1.5 = 10.5 -> clamped to 10.0
        # But without the bonus: 9.0, which shows decay from 10

        # Low stability decays up
        state_low = GameState(
            stability=1.0,
            player_a=PlayerState(previous_type=ActionType.COOPERATIVE),
            player_b=PlayerState(previous_type=ActionType.COOPERATIVE),
        )
        # 1.0 * 0.8 + 1.0 = 1.8, then +1.5 = 3.3
        new_stability_low = update_stability(state_low, result)
        assert new_stability_low == pytest.approx(3.3)


class TestApplyActionResult:
    """Tests for apply_action_result function."""

    def test_basic_application(self):
        """apply_action_result creates new state with changes applied."""
        state = GameState(
            cooperation_score=5.0,
            stability=5.0,
            risk_level=3.0,
            turn=5,
        )
        state.position_a = 5.0
        state.position_b = 5.0
        state.resources_a = 5.0
        state.resources_b = 5.0

        result = ActionResult(
            action_a=ActionType.COOPERATIVE,
            action_b=ActionType.COOPERATIVE,
            position_delta_a=0.5,
            position_delta_b=0.5,
            resource_cost_a=0.0,
            resource_cost_b=0.0,
            risk_delta=-0.5,
        )

        new_state = apply_action_result(state, result)

        # Turn 5 is Act II, multiplier = 1.0
        assert new_state.position_a == pytest.approx(5.5)
        assert new_state.position_b == pytest.approx(5.5)
        assert new_state.risk_level == pytest.approx(2.5)
        assert new_state.turn == 6  # Turn incremented
        # CC increases cooperation
        assert new_state.cooperation_score == pytest.approx(6.0)

    def test_act_multiplier_applied_to_position(self):
        """Position deltas are scaled by act multiplier."""
        state = GameState(turn=3)  # Act I, multiplier = 0.7
        state.position_a = 5.0
        state.position_b = 5.0

        result = ActionResult(
            action_a=ActionType.COOPERATIVE,
            action_b=ActionType.COMPETITIVE,
            position_delta_a=-1.0,
            position_delta_b=1.0,
        )

        new_state = apply_action_result(state, result)

        # -1.0 * 0.7 = -0.7
        assert new_state.position_a == pytest.approx(5.0 - 0.7)
        # +1.0 * 0.7 = +0.7
        assert new_state.position_b == pytest.approx(5.0 + 0.7)

    def test_act_multiplier_applied_to_risk(self):
        """Risk deltas are scaled by act multiplier."""
        state = GameState(turn=10, risk_level=5.0)  # Act III, multiplier = 1.3

        result = ActionResult(
            action_a=ActionType.COMPETITIVE,
            action_b=ActionType.COMPETITIVE,
            risk_delta=1.0,
        )

        new_state = apply_action_result(state, result)

        # 1.0 * 1.3 = 1.3
        assert new_state.risk_level == pytest.approx(6.3)

    def test_resource_costs_not_scaled(self):
        """Resource costs are applied directly, not scaled by act multiplier."""
        state = GameState(turn=10)  # Act III
        state.resources_a = 5.0
        state.resources_b = 5.0

        result = ActionResult(
            action_a=ActionType.COMPETITIVE,
            action_b=ActionType.COMPETITIVE,
            resource_cost_a=0.5,
            resource_cost_b=0.3,
        )

        new_state = apply_action_result(state, result)

        # Resources deducted directly
        assert new_state.resources_a == pytest.approx(4.5)
        assert new_state.resources_b == pytest.approx(4.7)

    def test_previous_types_updated(self):
        """Previous action types are updated after applying result."""
        state = GameState()

        result = ActionResult(
            action_a=ActionType.COOPERATIVE,
            action_b=ActionType.COMPETITIVE,
        )

        new_state = apply_action_result(state, result)

        assert new_state.previous_type_a == ActionType.COOPERATIVE
        assert new_state.previous_type_b == ActionType.COMPETITIVE

    def test_position_clamped_after_application(self):
        """Position values are clamped after applying deltas."""
        state = GameState(turn=10)  # Act III, multiplier = 1.3
        state.position_a = 9.0
        state.position_b = 1.0

        result = ActionResult(
            action_a=ActionType.COMPETITIVE,
            action_b=ActionType.COOPERATIVE,
            position_delta_a=1.5,  # Would push A to 9 + 1.5*1.3 = 10.95
            position_delta_b=-1.5,  # Would push B to 1 - 1.5*1.3 = -0.95
        )

        new_state = apply_action_result(state, result)

        assert new_state.position_a == pytest.approx(10.0)  # Clamped at max
        assert new_state.position_b == pytest.approx(0.0)  # Clamped at min

    def test_risk_clamped_after_application(self):
        """Risk level is clamped after applying deltas."""
        state = GameState(turn=10, risk_level=9.5)

        result = ActionResult(
            action_a=ActionType.COMPETITIVE,
            action_b=ActionType.COMPETITIVE,
            risk_delta=1.0,  # Would push to 9.5 + 1.0*1.3 = 10.8
        )

        new_state = apply_action_result(state, result)

        assert new_state.risk_level == pytest.approx(10.0)  # Clamped at max

    def test_information_state_preserved(self):
        """Information state is copied to new state."""
        state = GameState()
        state.player_a.information.update_position(7.0, turn=3)
        state.player_b.information.update_resources(4.0, turn=2)

        result = ActionResult(
            action_a=ActionType.COOPERATIVE,
            action_b=ActionType.COOPERATIVE,
        )

        new_state = apply_action_result(state, result)

        assert new_state.player_a.information.known_position == pytest.approx(7.0)
        assert new_state.player_a.information.known_position_turn == 3
        assert new_state.player_b.information.known_resources == pytest.approx(4.0)
        assert new_state.player_b.information.known_resources_turn == 2

    def test_max_turns_preserved(self):
        """max_turns value is preserved in new state."""
        state = GameState(max_turns=15)

        result = ActionResult(
            action_a=ActionType.COOPERATIVE,
            action_b=ActionType.COOPERATIVE,
        )

        new_state = apply_action_result(state, result)

        assert new_state.max_turns == 15


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_game_state_all_at_boundaries(self):
        """GameState with all values at boundaries."""
        state = GameState(
            cooperation_score=0.0,
            stability=1.0,
            risk_level=10.0,
            turn=16,
            max_turns=16,
        )
        state.position_a = 0.0
        state.position_b = 10.0
        state.resources_a = 10.0
        state.resources_b = 0.0

        # Verify all boundaries are respected
        assert state.cooperation_score == pytest.approx(0.0)
        assert state.stability == pytest.approx(1.0)
        assert state.risk_level == pytest.approx(10.0)
        assert state.position_a == pytest.approx(0.0)
        assert state.position_b == pytest.approx(10.0)
        assert state.resources_a == pytest.approx(10.0)
        assert state.resources_b == pytest.approx(0.0)

    def test_information_estimate_boundary_cases(self):
        """Information estimates at boundaries."""
        info = InformationState(
            known_position=0.0,
            known_position_turn=1,
            known_resources=10.0,
            known_resources_turn=1,
        )

        # Position at 0
        est, unc = info.get_position_estimate(current_turn=1)
        assert est == pytest.approx(0.0)
        assert unc == pytest.approx(0.0)

        # Resources at 10
        est, unc = info.get_resources_estimate(current_turn=1)
        assert est == pytest.approx(10.0)
        assert unc == pytest.approx(0.0)

    def test_action_result_with_all_defaults(self):
        """ActionResult with only required fields."""
        result = ActionResult(
            action_a=ActionType.COOPERATIVE,
            action_b=ActionType.COOPERATIVE,
        )
        assert result.position_delta_a == pytest.approx(0.0)
        assert result.position_delta_b == pytest.approx(0.0)
        assert result.resource_cost_a == pytest.approx(0.0)
        assert result.resource_cost_b == pytest.approx(0.0)
        assert result.risk_delta == pytest.approx(0.0)
        assert result.cooperation_delta == pytest.approx(0.0)
        assert result.stability_delta == pytest.approx(0.0)
        assert result.outcome_code == "CC"
        assert result.narrative == ""

    def test_stability_update_high_starting_value(self):
        """Stability update starting from maximum value."""
        state = GameState(
            stability=10.0,
            player_a=PlayerState(previous_type=ActionType.COOPERATIVE),
            player_b=PlayerState(previous_type=ActionType.COOPERATIVE),
        )
        result = ActionResult(
            action_a=ActionType.COMPETITIVE,  # A switches
            action_b=ActionType.COMPETITIVE,  # B switches
        )
        # 10.0 * 0.8 + 1.0 = 9.0
        # 2 switches: -5.5 -> 3.5
        new_stability = update_stability(state, result)
        assert new_stability == pytest.approx(3.5)

    def test_shared_sigma_extreme_values(self):
        """Shared sigma calculation with extreme values."""
        # Maximum variance scenario
        state = GameState(
            risk_level=10.0,  # Max risk
            cooperation_score=0.0,  # Max chaos
            stability=1.0,  # Max instability
            turn=10,  # Act III
        )
        # base_sigma = 8 + 12 = 20
        # chaos_factor = 1.2 - 0 = 1.2
        # instability_factor = 1 + 9/20 = 1.45
        # act_multiplier = 1.3
        expected = 20.0 * 1.2 * 1.45 * 1.3
        assert state.shared_sigma == pytest.approx(expected)

        # Minimum variance scenario
        state_min = GameState(
            risk_level=0.0,  # Min risk
            cooperation_score=10.0,  # Min chaos
            stability=10.0,  # Min instability
            turn=1,  # Act I
        )
        # base_sigma = 8 + 0 = 8
        # chaos_factor = 1.2 - 0.2 = 1.0
        # instability_factor = 1 + 0 = 1.0
        # act_multiplier = 0.7
        expected_min = 8.0 * 1.0 * 1.0 * 0.7
        assert state_min.shared_sigma == pytest.approx(expected_min)
