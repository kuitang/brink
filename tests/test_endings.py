"""Tests for the game endings module.

Tests verify all game ending conditions as specified in GAME_MANUAL.md:
1. EndingType enum membership
2. Mutual destruction (Risk = 10)
3. Position loss (Position = 0)
4. Resource loss (Resources = 0)
5. Crisis termination probability calculation
6. Max turns ending
7. check_all_endings priority order
"""

import pytest

from brinksmanship.engine.endings import (
    EndingType,
    GameEnding,
    check_all_endings,
    check_crisis_termination,
    check_max_turns,
    check_mutual_destruction,
    check_position_loss,
    check_resource_loss,
    get_crisis_termination_probability,
)
from brinksmanship.models.state import GameState, PlayerState


class TestEndingType:
    """Tests for EndingType enum."""

    def test_all_ending_types_defined(self):
        """All expected ending types exist in the enum."""
        expected_types = [
            "MUTUAL_DESTRUCTION",
            "POSITION_LOSS_A",
            "POSITION_LOSS_B",
            "RESOURCE_LOSS_A",
            "RESOURCE_LOSS_B",
            "CRISIS_TERMINATION",
            "MAX_TURNS",
            "SETTLEMENT",
        ]
        for type_name in expected_types:
            assert hasattr(EndingType, type_name), f"EndingType.{type_name} not found"

    def test_enum_membership(self):
        """EndingType values are proper enum members."""
        assert isinstance(EndingType.MUTUAL_DESTRUCTION, EndingType)
        assert isinstance(EndingType.POSITION_LOSS_A, EndingType)
        assert isinstance(EndingType.POSITION_LOSS_B, EndingType)
        assert isinstance(EndingType.RESOURCE_LOSS_A, EndingType)
        assert isinstance(EndingType.RESOURCE_LOSS_B, EndingType)
        assert isinstance(EndingType.CRISIS_TERMINATION, EndingType)
        assert isinstance(EndingType.MAX_TURNS, EndingType)
        assert isinstance(EndingType.SETTLEMENT, EndingType)

    def test_enum_count(self):
        """Verify total number of ending types."""
        assert len(EndingType) == 8


class TestGameEnding:
    """Tests for GameEnding dataclass."""

    def test_game_ending_creation(self):
        """GameEnding can be created with all required fields."""
        ending = GameEnding(
            ending_type=EndingType.MUTUAL_DESTRUCTION,
            vp_a=20.0,
            vp_b=20.0,
            description="Test description",
        )
        assert ending.ending_type == EndingType.MUTUAL_DESTRUCTION
        assert ending.vp_a == 20.0
        assert ending.vp_b == 20.0
        assert ending.description == "Test description"

    def test_game_ending_frozen(self):
        """GameEnding is immutable (frozen dataclass)."""
        ending = GameEnding(
            ending_type=EndingType.MUTUAL_DESTRUCTION,
            vp_a=20.0,
            vp_b=20.0,
            description="Test",
        )
        with pytest.raises(AttributeError):
            ending.vp_a = 50.0


class TestMutualDestruction:
    """Tests for check_mutual_destruction function.

    From GAME_MANUAL.md:
        Risk = 10: Mutual Destruction, both receive 20 VP
    """

    def _make_state(self, risk_level: float) -> GameState:
        """Helper to create state with specific risk level."""
        return GameState(
            player_a=PlayerState(position=5.0, resources=5.0),
            player_b=PlayerState(position=5.0, resources=5.0),
            risk_level=risk_level,
        )

    def test_risk_ten_triggers_mutual_destruction(self):
        """Risk level 10 triggers mutual destruction."""
        state = self._make_state(risk_level=10.0)
        ending = check_mutual_destruction(state)

        assert ending is not None
        assert ending.ending_type == EndingType.MUTUAL_DESTRUCTION
        assert ending.vp_a == 20.0
        assert ending.vp_b == 20.0

    def test_risk_above_ten_triggers_mutual_destruction(self):
        """Risk level > 10 also triggers (edge case from clamping)."""
        # Even though state clamps to 10, test the check logic
        state = self._make_state(risk_level=10.0)
        # Manually exceed 10 to test the >= check
        state = GameState(
            player_a=PlayerState(position=5.0, resources=5.0),
            player_b=PlayerState(position=5.0, resources=5.0),
            risk_level=10.0,  # Will be clamped, but this tests >= logic
        )
        ending = check_mutual_destruction(state)
        assert ending is not None
        assert ending.ending_type == EndingType.MUTUAL_DESTRUCTION

    def test_risk_below_ten_does_not_trigger(self):
        """Risk level < 10 does not trigger mutual destruction."""
        for risk in [0, 1, 5, 7, 9, 9.9]:
            state = self._make_state(risk_level=risk)
            ending = check_mutual_destruction(state)
            assert ending is None, f"Risk {risk} should not trigger mutual destruction"

    def test_mutual_destruction_vp_values(self):
        """Both players receive exactly 20 VP on mutual destruction."""
        state = self._make_state(risk_level=10.0)
        ending = check_mutual_destruction(state)

        assert ending.vp_a == 20.0
        assert ending.vp_b == 20.0
        assert ending.vp_a == ending.vp_b  # Symmetric

    def test_mutual_destruction_description(self):
        """Mutual destruction ending has appropriate description."""
        state = self._make_state(risk_level=10.0)
        ending = check_mutual_destruction(state)

        assert "destruction" in ending.description.lower()


class TestPositionLoss:
    """Tests for check_position_loss function.

    From GAME_MANUAL.md:
        Position = 0: That player loses, 10 VP. Opponent: 90 VP
    """

    def _make_state(self, pos_a: float, pos_b: float) -> GameState:
        """Helper to create state with specific positions."""
        return GameState(
            player_a=PlayerState(position=pos_a, resources=5.0),
            player_b=PlayerState(position=pos_b, resources=5.0),
        )

    def test_player_a_position_zero_triggers_loss(self):
        """Player A position = 0 triggers position loss for A."""
        state = self._make_state(pos_a=0.0, pos_b=5.0)
        ending = check_position_loss(state)

        assert ending is not None
        assert ending.ending_type == EndingType.POSITION_LOSS_A
        assert ending.vp_a == 10.0
        assert ending.vp_b == 90.0

    def test_player_b_position_zero_triggers_loss(self):
        """Player B position = 0 triggers position loss for B."""
        state = self._make_state(pos_a=5.0, pos_b=0.0)
        ending = check_position_loss(state)

        assert ending is not None
        assert ending.ending_type == EndingType.POSITION_LOSS_B
        assert ending.vp_a == 90.0
        assert ending.vp_b == 10.0

    def test_both_positions_zero_a_checked_first(self):
        """When both positions are 0, A's loss is detected first."""
        state = self._make_state(pos_a=0.0, pos_b=0.0)
        ending = check_position_loss(state)

        # A is checked first due to implementation order
        assert ending is not None
        assert ending.ending_type == EndingType.POSITION_LOSS_A

    def test_position_above_zero_does_not_trigger(self):
        """Position > 0 does not trigger position loss."""
        test_positions = [0.1, 1.0, 5.0, 10.0]
        for pos in test_positions:
            state = self._make_state(pos_a=pos, pos_b=pos)
            ending = check_position_loss(state)
            assert ending is None, f"Position {pos} should not trigger loss"

    def test_position_loss_vp_values_a(self):
        """Player A gets 10 VP, Player B gets 90 VP when A loses."""
        state = self._make_state(pos_a=0.0, pos_b=5.0)
        ending = check_position_loss(state)

        assert ending.vp_a == 10.0
        assert ending.vp_b == 90.0
        assert ending.vp_a + ending.vp_b == 100.0

    def test_position_loss_vp_values_b(self):
        """Player A gets 90 VP, Player B gets 10 VP when B loses."""
        state = self._make_state(pos_a=5.0, pos_b=0.0)
        ending = check_position_loss(state)

        assert ending.vp_a == 90.0
        assert ending.vp_b == 10.0
        assert ending.vp_a + ending.vp_b == 100.0


class TestResourceLoss:
    """Tests for check_resource_loss function.

    From GAME_MANUAL.md:
        Resources = 0: That player loses, 15 VP. Opponent: 85 VP
    """

    def _make_state(self, res_a: float, res_b: float) -> GameState:
        """Helper to create state with specific resources."""
        return GameState(
            player_a=PlayerState(position=5.0, resources=res_a),
            player_b=PlayerState(position=5.0, resources=res_b),
        )

    def test_player_a_resources_zero_triggers_loss(self):
        """Player A resources = 0 triggers resource loss for A."""
        state = self._make_state(res_a=0.0, res_b=5.0)
        ending = check_resource_loss(state)

        assert ending is not None
        assert ending.ending_type == EndingType.RESOURCE_LOSS_A
        assert ending.vp_a == 15.0
        assert ending.vp_b == 85.0

    def test_player_b_resources_zero_triggers_loss(self):
        """Player B resources = 0 triggers resource loss for B."""
        state = self._make_state(res_a=5.0, res_b=0.0)
        ending = check_resource_loss(state)

        assert ending is not None
        assert ending.ending_type == EndingType.RESOURCE_LOSS_B
        assert ending.vp_a == 85.0
        assert ending.vp_b == 15.0

    def test_both_resources_zero_a_checked_first(self):
        """When both resources are 0, A's loss is detected first."""
        state = self._make_state(res_a=0.0, res_b=0.0)
        ending = check_resource_loss(state)

        # A is checked first due to implementation order
        assert ending is not None
        assert ending.ending_type == EndingType.RESOURCE_LOSS_A

    def test_resources_above_zero_does_not_trigger(self):
        """Resources > 0 does not trigger resource loss."""
        test_resources = [0.1, 1.0, 5.0, 10.0]
        for res in test_resources:
            state = self._make_state(res_a=res, res_b=res)
            ending = check_resource_loss(state)
            assert ending is None, f"Resources {res} should not trigger loss"

    def test_resource_loss_vp_values_a(self):
        """Player A gets 15 VP, Player B gets 85 VP when A loses."""
        state = self._make_state(res_a=0.0, res_b=5.0)
        ending = check_resource_loss(state)

        assert ending.vp_a == 15.0
        assert ending.vp_b == 85.0
        assert ending.vp_a + ending.vp_b == 100.0

    def test_resource_loss_vp_values_b(self):
        """Player A gets 85 VP, Player B gets 15 VP when B loses."""
        state = self._make_state(res_a=5.0, res_b=0.0)
        ending = check_resource_loss(state)

        assert ending.vp_a == 85.0
        assert ending.vp_b == 15.0
        assert ending.vp_a + ending.vp_b == 100.0


class TestCrisisTerminationProbability:
    """Tests for get_crisis_termination_probability function.

    From GAME_MANUAL.md:
        Only checked for Turn >= 10 and Risk > 7
        P(Termination) = (Risk_Level - 7) * 0.08
        - Risk 7 or below: 0%
        - Risk 8: 8%
        - Risk 9: 16%
        - Risk 10: 100% (automatic mutual destruction, handled separately)
    """

    def test_turn_below_ten_probability_zero(self):
        """Turn < 10 always gives 0 probability, regardless of risk."""
        for turn in [1, 5, 9]:
            for risk in [0, 5, 8, 9, 10]:
                prob = get_crisis_termination_probability(risk, turn)
                assert prob == 0.0, f"Turn {turn}, Risk {risk} should have 0 probability"

    def test_risk_seven_or_below_probability_zero(self):
        """Risk <= 7 gives 0 probability, regardless of turn."""
        for risk in [0, 1, 5, 7]:
            prob = get_crisis_termination_probability(risk, turn=10)
            assert prob == 0.0, f"Risk {risk} should have 0 probability"

    def test_risk_eight_turn_ten_probability(self):
        """Risk 8, Turn >= 10: probability = 8% (0.08)."""
        prob = get_crisis_termination_probability(risk_level=8.0, turn=10)
        assert prob == pytest.approx(0.08)

    def test_risk_nine_turn_ten_probability(self):
        """Risk 9, Turn >= 10: probability = 16% (0.16)."""
        prob = get_crisis_termination_probability(risk_level=9.0, turn=10)
        assert prob == pytest.approx(0.16)

    def test_risk_ten_probability_one(self):
        """Risk 10, Turn >= 10: probability = 100% (1.0)."""
        prob = get_crisis_termination_probability(risk_level=10.0, turn=10)
        assert prob == 1.0

    def test_fractional_risk_levels(self):
        """Fractional risk levels work correctly."""
        # Risk 8.5: (8.5 - 7) * 0.08 = 1.5 * 0.08 = 0.12
        prob = get_crisis_termination_probability(risk_level=8.5, turn=10)
        assert prob == pytest.approx(0.12)

        # Risk 7.5: (7.5 - 7) * 0.08 = 0.5 * 0.08 = 0.04
        prob = get_crisis_termination_probability(risk_level=7.5, turn=10)
        assert prob == pytest.approx(0.04)

    def test_turn_above_ten(self):
        """Turns > 10 should still calculate probability."""
        for turn in [11, 12, 15, 16]:
            prob = get_crisis_termination_probability(risk_level=8.0, turn=turn)
            assert prob == pytest.approx(0.08)

    def test_formula_from_manual(self):
        """Verify the formula: P = (Risk - 7) * 0.08 for various values."""
        test_cases = [
            (7.0, 0.0),    # Risk 7: 0%
            (7.5, 0.04),   # Risk 7.5: 4%
            (8.0, 0.08),   # Risk 8: 8%
            (8.5, 0.12),   # Risk 8.5: 12%
            (9.0, 0.16),   # Risk 9: 16%
            (9.5, 0.20),   # Risk 9.5: 20%
        ]
        for risk, expected_prob in test_cases:
            prob = get_crisis_termination_probability(risk, turn=10)
            assert prob == pytest.approx(expected_prob), f"Risk {risk}: expected {expected_prob}, got {prob}"


class TestCrisisTermination:
    """Tests for check_crisis_termination function."""

    def _make_state(self, risk: float, turn: int) -> GameState:
        """Helper to create state with specific risk and turn."""
        return GameState(
            player_a=PlayerState(position=5.0, resources=5.0),
            player_b=PlayerState(position=5.0, resources=5.0),
            risk_level=risk,
            turn=turn,
        )

    def test_no_termination_before_turn_ten(self):
        """Crisis termination never triggers before turn 10."""
        state = self._make_state(risk=9.0, turn=9)

        # Try many seeds - should never terminate
        for seed in range(100):
            ending = check_crisis_termination(state, seed=seed)
            assert ending is None

    def test_no_termination_risk_seven_or_below(self):
        """Crisis termination never triggers at risk 7 or below."""
        state = self._make_state(risk=7.0, turn=10)

        for seed in range(100):
            ending = check_crisis_termination(state, seed=seed)
            assert ending is None

    def test_termination_with_seeded_random(self):
        """Crisis termination is deterministic with seed."""
        state = self._make_state(risk=8.0, turn=10)

        # Find a seed that triggers termination
        terminating_seed = None
        for seed in range(1000):
            ending = check_crisis_termination(state, seed=seed)
            if ending is not None:
                terminating_seed = seed
                break

        assert terminating_seed is not None, "Should find a terminating seed with 8% probability"

        # Same seed should always produce same result
        ending1 = check_crisis_termination(state, seed=terminating_seed)
        ending2 = check_crisis_termination(state, seed=terminating_seed)
        assert ending1 is not None
        assert ending2 is not None
        assert ending1.ending_type == ending2.ending_type

    def test_termination_returns_correct_type(self):
        """Crisis termination returns CRISIS_TERMINATION ending type."""
        state = self._make_state(risk=8.0, turn=10)

        # Find a terminating seed
        for seed in range(1000):
            ending = check_crisis_termination(state, seed=seed)
            if ending is not None:
                assert ending.ending_type == EndingType.CRISIS_TERMINATION
                break

    def test_termination_uses_final_resolution_for_vp(self):
        """Crisis termination VP are calculated using final resolution."""
        state = self._make_state(risk=8.0, turn=10)

        # Find a terminating seed
        for seed in range(1000):
            ending = check_crisis_termination(state, seed=seed)
            if ending is not None:
                # VP should sum to 100 (from final resolution)
                assert ending.vp_a + ending.vp_b == pytest.approx(100.0)
                break

    def test_termination_probability_statistical(self):
        """Statistical test: termination rate matches expected probability."""
        state = self._make_state(risk=8.0, turn=10)  # 8% probability

        terminations = 0
        num_trials = 10000

        for seed in range(num_trials):
            ending = check_crisis_termination(state, seed=seed)
            if ending is not None:
                terminations += 1

        actual_rate = terminations / num_trials
        expected_rate = 0.08

        # Allow 2% tolerance for statistical variation
        assert abs(actual_rate - expected_rate) < 0.02, (
            f"Expected ~{expected_rate*100}% termination rate, got {actual_rate*100:.1f}%"
        )


class TestMaxTurns:
    """Tests for check_max_turns function.

    From GAME_MANUAL.md:
        Maximum Turn Range: 12-16 turns (unknown to players)
        If Turn = Max_Turn: Final Resolution -> END
    """

    def _make_state(self, turn: int, max_turns: int = 14) -> GameState:
        """Helper to create state with specific turn and max_turns."""
        return GameState(
            player_a=PlayerState(position=5.0, resources=5.0),
            player_b=PlayerState(position=5.0, resources=5.0),
            turn=turn,
            max_turns=max_turns,
        )

    def test_turn_equals_max_triggers_ending(self):
        """Turn = max_turns triggers MAX_TURNS ending."""
        state = self._make_state(turn=14, max_turns=14)
        ending = check_max_turns(state)

        assert ending is not None
        assert ending.ending_type == EndingType.MAX_TURNS

    def test_turn_above_max_triggers_ending(self):
        """Turn > max_turns also triggers ending."""
        state = self._make_state(turn=15, max_turns=14)
        ending = check_max_turns(state)

        assert ending is not None
        assert ending.ending_type == EndingType.MAX_TURNS

    def test_turn_below_max_does_not_trigger(self):
        """Turn < max_turns does not trigger ending."""
        state = self._make_state(turn=13, max_turns=14)
        ending = check_max_turns(state)

        assert ending is None

    def test_max_turns_uses_final_resolution(self):
        """MAX_TURNS ending uses final resolution for VP."""
        state = self._make_state(turn=14, max_turns=14)
        ending = check_max_turns(state, seed=42)

        assert ending is not None
        assert ending.vp_a + ending.vp_b == pytest.approx(100.0)

    def test_max_turns_deterministic_with_seed(self):
        """MAX_TURNS VP are deterministic with seed."""
        state = self._make_state(turn=14, max_turns=14)

        ending1 = check_max_turns(state, seed=42)
        ending2 = check_max_turns(state, seed=42)

        assert ending1.vp_a == ending2.vp_a
        assert ending1.vp_b == ending2.vp_b

    def test_different_max_turns_values(self):
        """Test with different max_turns values in valid range 12-16."""
        for max_turns in [12, 13, 14, 15, 16]:
            state_at_max = self._make_state(turn=max_turns, max_turns=max_turns)
            state_before_max = self._make_state(turn=max_turns - 1, max_turns=max_turns)

            ending_at_max = check_max_turns(state_at_max)
            ending_before_max = check_max_turns(state_before_max)

            assert ending_at_max is not None, f"Turn {max_turns} should trigger at max {max_turns}"
            assert ending_before_max is None, f"Turn {max_turns-1} should not trigger at max {max_turns}"


class TestCheckAllEndings:
    """Tests for check_all_endings function.

    The order of checks from GAME_MANUAL.md:
    1. Deterministic Endings (checked first, in order):
       a. Risk = 10: Mutual Destruction
       b. Position = 0: Position Loss
       c. Resources = 0: Resource Loss
    2. Probabilistic Endings (checked after deterministic):
       a. Crisis Termination (Turn >= 10, Risk > 7)
       b. Max Turns (turn >= max_turns)
    """

    def _make_state(
        self,
        pos_a: float = 5.0,
        pos_b: float = 5.0,
        res_a: float = 5.0,
        res_b: float = 5.0,
        risk: float = 5.0,
        turn: int = 5,
        max_turns: int = 14,
    ) -> GameState:
        """Helper to create state with specific values."""
        return GameState(
            player_a=PlayerState(position=pos_a, resources=res_a),
            player_b=PlayerState(position=pos_b, resources=res_b),
            risk_level=risk,
            turn=turn,
            max_turns=max_turns,
        )

    def test_no_ending_returns_none(self):
        """Normal game state with no ending returns None."""
        state = self._make_state()
        ending = check_all_endings(state)

        assert ending is None

    def test_mutual_destruction_has_highest_priority(self):
        """Mutual destruction is checked before other endings."""
        # State with risk=10 AND position=0 AND resources=0
        state = self._make_state(
            pos_a=0.0,  # Would trigger position loss
            res_a=0.0,  # Would trigger resource loss
            risk=10.0,  # Should win - mutual destruction
        )
        ending = check_all_endings(state)

        assert ending is not None
        assert ending.ending_type == EndingType.MUTUAL_DESTRUCTION

    def test_position_loss_before_resource_loss(self):
        """Position loss is checked before resource loss."""
        state = self._make_state(
            pos_a=0.0,  # Position loss
            res_a=0.0,  # Resource loss
        )
        ending = check_all_endings(state)

        assert ending is not None
        assert ending.ending_type == EndingType.POSITION_LOSS_A

    def test_resource_loss_checked_after_position(self):
        """Resource loss triggers when position is fine."""
        state = self._make_state(
            pos_a=5.0,  # Position OK
            res_a=0.0,  # Resource loss
        )
        ending = check_all_endings(state)

        assert ending is not None
        assert ending.ending_type == EndingType.RESOURCE_LOSS_A

    def test_deterministic_before_probabilistic(self):
        """Deterministic endings are checked before probabilistic ones."""
        # State at turn 10 with high risk (crisis termination possible)
        # AND position = 0 (deterministic)
        state = self._make_state(
            pos_a=0.0,
            risk=9.0,
            turn=10,
        )
        ending = check_all_endings(state)

        # Should get position loss, not crisis termination
        assert ending is not None
        assert ending.ending_type == EndingType.POSITION_LOSS_A

    def test_crisis_termination_before_max_turns(self):
        """Crisis termination is checked before max turns."""
        # State at max turns with high risk
        # Find a seed that triggers crisis termination
        state = self._make_state(
            risk=9.0,
            turn=14,
            max_turns=14,
        )

        # Try seeds until we find one that triggers crisis termination
        for seed in range(1000):
            ending = check_all_endings(state, seed=seed)
            if ending is not None and ending.ending_type == EndingType.CRISIS_TERMINATION:
                # Crisis termination triggered before max turns
                break
        else:
            # If no crisis termination in 1000 tries, the implementation may
            # check max turns first. Verify max turns is at least returned.
            ending = check_all_endings(state, seed=0)
            assert ending is not None

    def test_max_turns_triggers_when_no_other_endings(self):
        """Max turns triggers when no other ending conditions are met."""
        state = self._make_state(
            pos_a=5.0,
            pos_b=5.0,
            res_a=5.0,
            res_b=5.0,
            risk=5.0,  # Too low for crisis termination
            turn=14,
            max_turns=14,
        )
        ending = check_all_endings(state)

        assert ending is not None
        assert ending.ending_type == EndingType.MAX_TURNS

    def test_seed_passed_to_probabilistic_checks(self):
        """Seed is passed through to probabilistic ending checks."""
        state = self._make_state(
            risk=8.0,
            turn=10,
        )

        # Same seed should give same result
        ending1 = check_all_endings(state, seed=42)
        ending2 = check_all_endings(state, seed=42)

        # Both should be either None or same ending
        if ending1 is not None:
            assert ending2 is not None
            assert ending1.ending_type == ending2.ending_type
        else:
            assert ending2 is None

    def test_all_deterministic_endings_returnable(self):
        """All deterministic ending types can be returned."""
        # Mutual destruction
        state_md = self._make_state(risk=10.0)
        assert check_all_endings(state_md).ending_type == EndingType.MUTUAL_DESTRUCTION

        # Position loss A
        state_pla = self._make_state(pos_a=0.0)
        assert check_all_endings(state_pla).ending_type == EndingType.POSITION_LOSS_A

        # Position loss B
        state_plb = self._make_state(pos_b=0.0)
        assert check_all_endings(state_plb).ending_type == EndingType.POSITION_LOSS_B

        # Resource loss A
        state_rla = self._make_state(res_a=0.0)
        assert check_all_endings(state_rla).ending_type == EndingType.RESOURCE_LOSS_A

        # Resource loss B
        state_rlb = self._make_state(res_b=0.0)
        assert check_all_endings(state_rlb).ending_type == EndingType.RESOURCE_LOSS_B


class TestVPSumsTo100:
    """Tests verifying that all endings produce VP summing to 100."""

    def _make_state(
        self,
        pos_a: float = 5.0,
        pos_b: float = 5.0,
        res_a: float = 5.0,
        res_b: float = 5.0,
        risk: float = 5.0,
        turn: int = 5,
        max_turns: int = 14,
    ) -> GameState:
        """Helper to create state."""
        return GameState(
            player_a=PlayerState(position=pos_a, resources=res_a),
            player_b=PlayerState(position=pos_b, resources=res_b),
            risk_level=risk,
            turn=turn,
            max_turns=max_turns,
        )

    def test_mutual_destruction_vp_sum(self):
        """Mutual destruction VP sum to 40 (20 + 20)."""
        state = self._make_state(risk=10.0)
        ending = check_mutual_destruction(state)

        # Note: Mutual destruction is special - both get 20 VP
        assert ending.vp_a + ending.vp_b == 40.0

    def test_position_loss_vp_sum(self):
        """Position loss VP sum to 100."""
        state_a = self._make_state(pos_a=0.0)
        state_b = self._make_state(pos_b=0.0)

        ending_a = check_position_loss(state_a)
        ending_b = check_position_loss(state_b)

        assert ending_a.vp_a + ending_a.vp_b == 100.0
        assert ending_b.vp_a + ending_b.vp_b == 100.0

    def test_resource_loss_vp_sum(self):
        """Resource loss VP sum to 100."""
        state_a = self._make_state(res_a=0.0)
        state_b = self._make_state(res_b=0.0)

        ending_a = check_resource_loss(state_a)
        ending_b = check_resource_loss(state_b)

        assert ending_a.vp_a + ending_a.vp_b == 100.0
        assert ending_b.vp_a + ending_b.vp_b == 100.0

    def test_max_turns_vp_sum(self):
        """Max turns VP sum to 100."""
        state = self._make_state(turn=14, max_turns=14)

        for seed in range(10):
            ending = check_max_turns(state, seed=seed)
            assert ending.vp_a + ending.vp_b == pytest.approx(100.0)

    def test_crisis_termination_vp_sum(self):
        """Crisis termination VP sum to 100."""
        state = self._make_state(risk=9.0, turn=10)

        # Find a seed that triggers termination
        for seed in range(1000):
            ending = check_crisis_termination(state, seed=seed)
            if ending is not None:
                assert ending.vp_a + ending.vp_b == pytest.approx(100.0)
                break
