"""Unit tests for brinksmanship.models.state module.

Tests cover:
- GameState: initialization, clamping, computed properties, serialization
- PlayerState: initialization, clamping, serialization
- InformationState: position/resource estimation with decay
- ActionResult: creation, serialization, outcome properties
- Helper functions: update_cooperation_score, update_stability, clamp

REMOVED TESTS (see test_removal_log.md for rationale):
- TestClampFunction: All 6 tests removed (trivial utility function)
- TestInformationState: test_default_initialization, test_get_resources_estimate_*,
  test_update_position, test_update_resources, test_get_position_estimate_zero_turns_elapsed
- TestPlayerState: test_default_initialization, test_custom_initialization, consolidated 4 clamping tests to 1
- TestGameState: Removed trivial default/accessor tests, consolidated clamping tests,
  consolidated act property/multiplier tests, removed test_shared_sigma_chaotic_crisis,
  test_to_dict_and_from_dict, test_json_is_valid_json, test_get_act_method_via_act_property
- TestActionResult: Removed test_basic_creation, test_default_deltas, test_custom_deltas,
  consolidated outcome_code tests, removed is_mutual_cooperation/defection/is_mixed
- TestUpdateCooperationScore: Consolidated mixed tests, removed clamping tests
- TestUpdateStability: Removed redundant clamping and edge case tests
- TestApplyActionResult: Removed act_multiplier_applied_to_risk, removed clamping tests
- TestEdgeCases: Kept only test_shared_sigma_extreme_values
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


class TestInformationState:
    """Tests for InformationState class."""

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

    def test_position_and_resources_clamping(self):
        """Position and resources are clamped to valid ranges."""
        # Position below 0 is clamped to 0
        player = PlayerState(position=-5.0)
        assert player.position == pytest.approx(0.0)

        # Position above 10 is clamped to 10
        player = PlayerState(position=15.0)
        assert player.position == pytest.approx(10.0)

        # Resources below 0 is clamped to 0
        player = PlayerState(resources=-3.0)
        assert player.resources == pytest.approx(0.0)

        # Resources above 10 is clamped to 10
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

    def test_state_clamping(self):
        """All state variables are clamped to valid ranges."""
        # Cooperation score
        assert GameState(cooperation_score=-5.0).cooperation_score == pytest.approx(0.0)
        assert GameState(cooperation_score=15.0).cooperation_score == pytest.approx(10.0)

        # Stability (min is 1, not 0)
        assert GameState(stability=-2.0).stability == pytest.approx(1.0)
        assert GameState(stability=15.0).stability == pytest.approx(10.0)

        # Risk level
        assert GameState(risk_level=-3.0).risk_level == pytest.approx(0.0)
        assert GameState(risk_level=12.0).risk_level == pytest.approx(10.0)

        # Max turns
        assert GameState(max_turns=5).max_turns == 12
        assert GameState(max_turns=20).max_turns == 16

    def test_act_property_and_multiplier(self):
        """Act property and multiplier correctly determined by turn."""
        # Act I: turns 1-4, multiplier 0.7
        state = GameState(turn=3)
        assert state.act == 1
        assert state.act_multiplier == pytest.approx(0.7)

        # Act II: turns 5-8, multiplier 1.0
        state = GameState(turn=6)
        assert state.act == 2
        assert state.act_multiplier == pytest.approx(1.0)

        # Act III: turns 9+, multiplier 1.3
        state = GameState(turn=10)
        assert state.act == 3
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

    def test_surplus_fields_serialize(self):
        """Verify surplus fields initialize, modify, and serialize correctly."""
        state = GameState(
            cooperation_surplus=10.5,
            surplus_captured_a=3.0,
            surplus_captured_b=2.0,
            cooperation_streak=5,
        )

        # Test computed properties
        assert state.total_surplus_captured == pytest.approx(5.0)
        assert state.surplus_remaining == pytest.approx(10.5)

        # Round-trip serialization via dict
        data = state.to_dict()
        restored = GameState.from_dict(data)

        assert restored.cooperation_surplus == pytest.approx(10.5)
        assert restored.surplus_captured_a == pytest.approx(3.0)
        assert restored.surplus_captured_b == pytest.approx(2.0)
        assert restored.cooperation_streak == 5
        assert restored.total_surplus_captured == pytest.approx(5.0)

        # Round-trip serialization via JSON
        json_str = state.to_json()
        restored_json = GameState.from_json(json_str)

        assert restored_json.cooperation_surplus == pytest.approx(10.5)
        assert restored_json.surplus_captured_a == pytest.approx(3.0)
        assert restored_json.surplus_captured_b == pytest.approx(2.0)
        assert restored_json.cooperation_streak == 5


class TestActionResult:
    """Tests for ActionResult class."""

    def test_outcome_code_auto_computed(self):
        """Outcome code is auto-computed based on action types."""
        # CC
        result = ActionResult(
            action_a=ActionType.COOPERATIVE,
            action_b=ActionType.COOPERATIVE,
        )
        assert result.outcome_code == "CC"

        # CD
        result = ActionResult(
            action_a=ActionType.COOPERATIVE,
            action_b=ActionType.COMPETITIVE,
        )
        assert result.outcome_code == "CD"

        # DC
        result = ActionResult(
            action_a=ActionType.COMPETITIVE,
            action_b=ActionType.COOPERATIVE,
        )
        assert result.outcome_code == "DC"

        # DD
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

    def test_mixed_outcomes_no_change(self):
        """CD and DC (mixed outcomes) result in no change."""
        state = GameState(cooperation_score=5.0)

        # CD
        result = ActionResult(
            action_a=ActionType.COOPERATIVE,
            action_b=ActionType.COMPETITIVE,
        )
        assert update_cooperation_score(state, result) == pytest.approx(5.0)

        # DC
        result = ActionResult(
            action_a=ActionType.COMPETITIVE,
            action_b=ActionType.COOPERATIVE,
        )
        assert update_cooperation_score(state, result) == pytest.approx(5.0)


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

    def test_decay_toward_neutral(self):
        """Stability decays toward neutral (5) over time."""
        # Low stability decays up
        state_low = GameState(
            stability=1.0,
            player_a=PlayerState(previous_type=ActionType.COOPERATIVE),
            player_b=PlayerState(previous_type=ActionType.COOPERATIVE),
        )
        result = ActionResult(
            action_a=ActionType.COOPERATIVE,
            action_b=ActionType.COOPERATIVE,
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

    def test_surplus_fields_preserved(self):
        """Surplus fields are preserved when applying action result."""
        state = GameState(
            cooperation_surplus=8.5,
            surplus_captured_a=2.0,
            surplus_captured_b=1.5,
            cooperation_streak=3,
        )

        result = ActionResult(
            action_a=ActionType.COOPERATIVE,
            action_b=ActionType.COOPERATIVE,
        )

        new_state = apply_action_result(state, result)

        assert new_state.cooperation_surplus == pytest.approx(8.5)
        assert new_state.surplus_captured_a == pytest.approx(2.0)
        assert new_state.surplus_captured_b == pytest.approx(1.5)
        assert new_state.cooperation_streak == 3


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

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
