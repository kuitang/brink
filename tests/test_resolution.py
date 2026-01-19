"""Comprehensive unit tests for resolution.py.

Tests cover:
1. Reconnaissance game - all four outcome combinations
2. Inspection game - all four outcome combinations
3. Settlement constraints - min/max/suggested VP calculation
4. Matrix game resolution - outcome lookup and state deltas
5. Settlement proposal/response - validation and structure
6. Act multiplier scaling
7. Full turn resolution functions

Removed tests (see test_removal_log.md):
- TestMatrixChoice: Basic enum tests (trivial, covered by usage)
- TestReconnaissanceChoices: Enum value tests (trivial)
- TestInspectionChoices: Enum value tests (trivial)
- TestSettlementResponse.test_settlement_action_enum: Enum value test (trivial)
- TestReconnaissanceGame.test_reconnaissance_result_is_frozen: Frozen check (low value)
- TestInspectionGame.test_inspection_result_is_frozen: Frozen check (low value)
"""

import pytest
from pydantic import ValidationError

from brinksmanship.engine.resolution import (
    MatrixChoice,
    ReconnaissanceChoice,
    ReconnaissanceOpponentChoice,
    ReconnaissanceResult,
    InspectionChoice,
    InspectionOpponentChoice,
    InspectionResult,
    SettlementProposal,
    SettlementAction,
    SettlementResponse,
    SettlementConstraints,
    resolve_matrix_game,
    resolve_reconnaissance,
    resolve_inspection,
    calculate_settlement_constraints,
    validate_settlement_proposal,
    get_act_multiplier,
    apply_state_deltas,
    apply_action_result_deltas,
    resolve_simultaneous_actions,
    resolve_reconnaissance_turn,
    resolve_inspection_turn,
    handle_failed_settlement,
    determine_settlement_roles,
    _calculate_cooperation_delta,
)
from brinksmanship.models.actions import Action, ActionType
from brinksmanship.models.matrices import (
    MatrixType,
    MatrixParameters,
    PayoffMatrix,
    StateDeltas,
    OutcomePayoffs,
    build_matrix,
    get_default_params_for_type,
)
from brinksmanship.models.state import GameState, PlayerState


# =============================================================================
# Reconnaissance Game Tests (GAME_MANUAL.md Section 3.6.1)
# =============================================================================


class TestReconnaissanceGame:
    """Tests for the Reconnaissance game resolution."""

    @pytest.fixture
    def game_state(self) -> GameState:
        """Create a standard game state for testing."""
        return GameState(
            player_a=PlayerState(position=5.0, resources=5.0),
            player_b=PlayerState(position=5.0, resources=5.0),
            cooperation_score=5.0,
            stability=5.0,
            risk_level=2.0,
            turn=3,
        )

    def test_probe_plus_vigilant_equals_detected(self, game_state: GameState) -> None:
        """Probe + Vigilant = Detected (Risk +0.5, no info)."""
        result = resolve_reconnaissance(
            game_state,
            player_choice=ReconnaissanceChoice.PROBE,
            opponent_choice=ReconnaissanceOpponentChoice.VIGILANT,
        )

        assert result.outcome == "detected"
        assert result.player_learns_position is False
        assert result.opponent_learns_position is False
        assert result.risk_delta == 0.5
        assert result.player_detected is True
        assert len(result.narrative) > 0

    def test_probe_plus_project_equals_success(self, game_state: GameState) -> None:
        """Probe + Project = Success (learn opponent position)."""
        result = resolve_reconnaissance(
            game_state,
            player_choice=ReconnaissanceChoice.PROBE,
            opponent_choice=ReconnaissanceOpponentChoice.PROJECT,
        )

        assert result.outcome == "success"
        assert result.player_learns_position is True
        assert result.opponent_learns_position is False
        assert result.risk_delta == 0.0
        assert result.player_detected is False
        assert len(result.narrative) > 0

    def test_mask_plus_vigilant_equals_stalemate(self, game_state: GameState) -> None:
        """Mask + Vigilant = Stalemate (no change)."""
        result = resolve_reconnaissance(
            game_state,
            player_choice=ReconnaissanceChoice.MASK,
            opponent_choice=ReconnaissanceOpponentChoice.VIGILANT,
        )

        assert result.outcome == "stalemate"
        assert result.player_learns_position is False
        assert result.opponent_learns_position is False
        assert result.risk_delta == 0.0
        assert result.player_detected is False
        assert len(result.narrative) > 0

    def test_mask_plus_project_equals_exposed(self, game_state: GameState) -> None:
        """Mask + Project = Exposed (opponent learns your position)."""
        result = resolve_reconnaissance(
            game_state,
            player_choice=ReconnaissanceChoice.MASK,
            opponent_choice=ReconnaissanceOpponentChoice.PROJECT,
        )

        assert result.outcome == "exposed"
        assert result.player_learns_position is False
        assert result.opponent_learns_position is True
        assert result.risk_delta == 0.0
        assert result.player_detected is False
        assert len(result.narrative) > 0


# =============================================================================
# Inspection Game Tests (GAME_MANUAL.md Section 3.6.2)
# =============================================================================


class TestInspectionGame:
    """Tests for the Inspection game resolution."""

    @pytest.fixture
    def game_state(self) -> GameState:
        """Create a standard game state for testing."""
        return GameState(
            player_a=PlayerState(position=5.0, resources=5.0),
            player_b=PlayerState(position=5.0, resources=5.0),
            cooperation_score=5.0,
            stability=5.0,
            risk_level=2.0,
            turn=3,
        )

    def test_inspect_plus_comply_equals_verified(self, game_state: GameState) -> None:
        """Inspect + Comply = Verified (learn resources)."""
        result = resolve_inspection(
            game_state,
            player_choice=InspectionChoice.INSPECT,
            opponent_choice=InspectionOpponentChoice.COMPLY,
        )

        assert result.outcome == "verified"
        assert result.player_learns_resources is True
        assert result.opponent_risk_penalty == 0.0
        assert result.opponent_position_delta == 0.0
        assert result.player_position_delta == 0.0
        assert len(result.narrative) > 0

    def test_inspect_plus_cheat_equals_caught(self, game_state: GameState) -> None:
        """Inspect + Cheat = Caught (learn resources, opponent penalized)."""
        result = resolve_inspection(
            game_state,
            player_choice=InspectionChoice.INSPECT,
            opponent_choice=InspectionOpponentChoice.CHEAT,
        )

        assert result.outcome == "caught"
        assert result.player_learns_resources is True
        assert result.opponent_risk_penalty == 1.0
        assert result.opponent_position_delta == -0.5
        assert result.player_position_delta == 0.0
        assert len(result.narrative) > 0

    def test_trust_plus_comply_equals_nothing(self, game_state: GameState) -> None:
        """Trust + Comply = Nothing."""
        result = resolve_inspection(
            game_state,
            player_choice=InspectionChoice.TRUST,
            opponent_choice=InspectionOpponentChoice.COMPLY,
        )

        assert result.outcome == "nothing"
        assert result.player_learns_resources is False
        assert result.opponent_risk_penalty == 0.0
        assert result.opponent_position_delta == 0.0
        assert result.player_position_delta == 0.0
        assert len(result.narrative) > 0

    def test_trust_plus_cheat_equals_exploited(self, game_state: GameState) -> None:
        """Trust + Cheat = Exploited (opponent gains)."""
        result = resolve_inspection(
            game_state,
            player_choice=InspectionChoice.TRUST,
            opponent_choice=InspectionOpponentChoice.CHEAT,
        )

        assert result.outcome == "exploited"
        assert result.player_learns_resources is False
        assert result.opponent_risk_penalty == 0.0
        assert result.opponent_position_delta == 0.5
        assert result.player_position_delta == 0.0
        assert len(result.narrative) > 0


# =============================================================================
# Settlement Constraints Tests (GAME_MANUAL.md Section 4.4)
# =============================================================================


class TestSettlementConstraints:
    """Tests for settlement constraint calculations."""

    def test_calculate_correct_suggested_vp_equal_positions(self) -> None:
        """Test suggested VP calculation when positions are equal."""
        state = GameState(
            player_a=PlayerState(position=5.0, resources=5.0),
            player_b=PlayerState(position=5.0, resources=5.0),
            cooperation_score=5.0,  # Cooperation bonus = (5-5)*2 = 0
        )

        constraints = calculate_settlement_constraints(state, "A")

        # Position_Difference = 5 - 5 = 0
        # Cooperation_Bonus = (5 - 5) * 2 = 0
        # Suggested_VP = 50 + (0 * 5) + 0 = 50
        assert constraints.suggested_vp == 50
        assert constraints.min_vp == max(20, 50 - 10)  # 40
        assert constraints.max_vp == min(80, 50 + 10)  # 60

    def test_position_difference_affects_suggested_vp_positive(self) -> None:
        """Test that higher position increases suggested VP."""
        state = GameState(
            player_a=PlayerState(position=7.0, resources=5.0),
            player_b=PlayerState(position=5.0, resources=5.0),
            cooperation_score=5.0,
        )

        constraints = calculate_settlement_constraints(state, "A")

        # Position_Difference = 7 - 5 = 2
        # Cooperation_Bonus = (5 - 5) * 2 = 0
        # Suggested_VP = 50 + (2 * 5) + 0 = 60
        assert constraints.suggested_vp == 60
        assert constraints.min_vp == max(20, 60 - 10)  # 50
        assert constraints.max_vp == min(80, 60 + 10)  # 70

    def test_position_difference_affects_suggested_vp_negative(self) -> None:
        """Test that lower position decreases suggested VP."""
        state = GameState(
            player_a=PlayerState(position=3.0, resources=5.0),
            player_b=PlayerState(position=5.0, resources=5.0),
            cooperation_score=5.0,
        )

        constraints = calculate_settlement_constraints(state, "A")

        # Position_Difference = 3 - 5 = -2
        # Cooperation_Bonus = (5 - 5) * 2 = 0
        # Suggested_VP = 50 + (-2 * 5) + 0 = 40
        assert constraints.suggested_vp == 40
        assert constraints.min_vp == max(20, 40 - 10)  # 30
        assert constraints.max_vp == min(80, 40 + 10)  # 50

    def test_cooperation_bonus_applied(self) -> None:
        """Test that cooperation score affects suggested VP."""
        state = GameState(
            player_a=PlayerState(position=5.0, resources=5.0),
            player_b=PlayerState(position=5.0, resources=5.0),
            cooperation_score=8.0,  # Cooperation bonus = (8-5)*2 = 6
        )

        constraints = calculate_settlement_constraints(state, "A")

        # Position_Difference = 5 - 5 = 0
        # Cooperation_Bonus = (8 - 5) * 2 = 6
        # Suggested_VP = 50 + (0 * 5) + 6 = 56
        assert constraints.suggested_vp == 56
        assert constraints.min_vp == max(20, 56 - 10)  # 46
        assert constraints.max_vp == min(80, 56 + 10)  # 66

    def test_cooperation_penalty_applied(self) -> None:
        """Test that low cooperation score reduces suggested VP."""
        state = GameState(
            player_a=PlayerState(position=5.0, resources=5.0),
            player_b=PlayerState(position=5.0, resources=5.0),
            cooperation_score=2.0,  # Cooperation bonus = (2-5)*2 = -6
        )

        constraints = calculate_settlement_constraints(state, "A")

        # Position_Difference = 5 - 5 = 0
        # Cooperation_Bonus = (2 - 5) * 2 = -6
        # Suggested_VP = 50 + (0 * 5) + (-6) = 44
        assert constraints.suggested_vp == 44
        assert constraints.min_vp == max(20, 44 - 10)  # 34
        assert constraints.max_vp == min(80, 44 + 10)  # 54

    def test_suggested_vp_clamped_to_valid_range(self) -> None:
        """Test that suggested VP is clamped to [20, 80]."""
        # Very high position difference
        state_high = GameState(
            player_a=PlayerState(position=10.0, resources=5.0),
            player_b=PlayerState(position=0.0, resources=5.0),
            cooperation_score=10.0,
        )

        constraints_high = calculate_settlement_constraints(state_high, "A")

        # Position_Difference = 10 - 0 = 10
        # Cooperation_Bonus = (10 - 5) * 2 = 10
        # Suggested_VP = 50 + (10 * 5) + 10 = 110 -> clamped to 80
        assert constraints_high.suggested_vp == 80
        assert constraints_high.max_vp == 80

        # Very low position difference
        state_low = GameState(
            player_a=PlayerState(position=0.0, resources=5.0),
            player_b=PlayerState(position=10.0, resources=5.0),
            cooperation_score=0.0,
        )

        constraints_low = calculate_settlement_constraints(state_low, "A")

        # Position_Difference = 0 - 10 = -10
        # Cooperation_Bonus = (0 - 5) * 2 = -10
        # Suggested_VP = 50 + (-10 * 5) + (-10) = -10 -> clamped to 20
        assert constraints_low.suggested_vp == 20
        assert constraints_low.min_vp == 20

    def test_player_b_perspective(self) -> None:
        """Test constraints from player B's perspective."""
        state = GameState(
            player_a=PlayerState(position=7.0, resources=5.0),
            player_b=PlayerState(position=5.0, resources=5.0),
            cooperation_score=5.0,
        )

        constraints = calculate_settlement_constraints(state, "B")

        # Position_Difference (for B) = 5 - 7 = -2
        # Cooperation_Bonus = (5 - 5) * 2 = 0
        # Suggested_VP = 50 + (-2 * 5) + 0 = 40
        assert constraints.suggested_vp == 40
        assert constraints.min_vp == 30
        assert constraints.max_vp == 50


class TestSettlementProposal:
    """Tests for SettlementProposal validation."""

    def test_valid_proposal_structure(self) -> None:
        """Test creating a valid settlement proposal."""
        proposal = SettlementProposal(
            offered_vp=55, argument="A fair split based on our current positions."
        )
        assert proposal.offered_vp == 55
        assert proposal.argument == "A fair split based on our current positions."

    def test_proposal_vp_range_validation(self) -> None:
        """Test that VP must be in [0, 100]."""
        with pytest.raises(ValidationError):
            SettlementProposal(offered_vp=-1, argument="Invalid")

        with pytest.raises(ValidationError):
            SettlementProposal(offered_vp=101, argument="Invalid")

    def test_proposal_argument_max_length(self) -> None:
        """Test that argument is limited to 500 characters."""
        long_arg = "x" * 501
        with pytest.raises(ValidationError):
            SettlementProposal(offered_vp=50, argument=long_arg)

        # 500 characters should be valid
        valid_arg = "x" * 500
        proposal = SettlementProposal(offered_vp=50, argument=valid_arg)
        assert len(proposal.argument) == 500

    def test_validate_settlement_proposal_valid(self) -> None:
        """Test validating a proposal within constraints."""
        state = GameState(
            player_a=PlayerState(position=5.0, resources=5.0),
            player_b=PlayerState(position=5.0, resources=5.0),
            cooperation_score=5.0,
        )
        proposal = SettlementProposal(
            offered_vp=50, argument="Equal split for equal positions."
        )

        is_valid, error = validate_settlement_proposal(proposal, state, "A")
        assert is_valid is True
        assert error is None

    def test_validate_settlement_proposal_too_low(self) -> None:
        """Test rejecting a proposal below minimum."""
        state = GameState(
            player_a=PlayerState(position=5.0, resources=5.0),
            player_b=PlayerState(position=5.0, resources=5.0),
            cooperation_score=5.0,
        )
        # Min for equal positions = 40
        proposal = SettlementProposal(offered_vp=30, argument="Low ball offer.")

        is_valid, error = validate_settlement_proposal(proposal, state, "A")
        assert is_valid is False
        assert error is not None
        assert "too low" in error.lower()

    def test_validate_settlement_proposal_too_high(self) -> None:
        """Test rejecting a proposal above maximum."""
        state = GameState(
            player_a=PlayerState(position=5.0, resources=5.0),
            player_b=PlayerState(position=5.0, resources=5.0),
            cooperation_score=5.0,
        )
        # Max for equal positions = 60
        proposal = SettlementProposal(offered_vp=70, argument="Greedy offer.")

        is_valid, error = validate_settlement_proposal(proposal, state, "A")
        assert is_valid is False
        assert error is not None
        assert "too high" in error.lower()

    def test_validate_settlement_proposal_empty_argument(self) -> None:
        """Test rejecting a proposal with empty argument."""
        state = GameState(
            player_a=PlayerState(position=5.0, resources=5.0),
            player_b=PlayerState(position=5.0, resources=5.0),
            cooperation_score=5.0,
        )
        proposal = SettlementProposal(offered_vp=50, argument="   ")

        is_valid, error = validate_settlement_proposal(proposal, state, "A")
        assert is_valid is False
        assert error is not None
        assert "argument" in error.lower()


class TestSettlementResponse:
    """Tests for SettlementResponse validation."""

    def test_accept_response(self) -> None:
        """Test creating an accept response."""
        response = SettlementResponse(action=SettlementAction.ACCEPT)
        assert response.action == SettlementAction.ACCEPT
        assert response.counter_vp is None

    def test_counter_response(self) -> None:
        """Test creating a counter response."""
        response = SettlementResponse(
            action=SettlementAction.COUNTER,
            counter_vp=45,
            counter_argument="I think this is more fair.",
        )
        assert response.action == SettlementAction.COUNTER
        assert response.counter_vp == 45
        assert response.counter_argument == "I think this is more fair."

    def test_reject_response(self) -> None:
        """Test creating a reject response."""
        response = SettlementResponse(
            action=SettlementAction.REJECT,
            rejection_reason="Your offer is unacceptable.",
        )
        assert response.action == SettlementAction.REJECT
        assert response.rejection_reason == "Your offer is unacceptable."


# =============================================================================
# Matrix Game Resolution Tests
# =============================================================================


class TestMatrixGameResolution:
    """Tests for matrix game resolution."""

    @pytest.fixture
    def game_state(self) -> GameState:
        """Create a standard game state for testing."""
        return GameState(
            player_a=PlayerState(position=5.0, resources=5.0),
            player_b=PlayerState(position=5.0, resources=5.0),
            cooperation_score=5.0,
            stability=5.0,
            risk_level=2.0,
            turn=5,
        )

    @pytest.fixture
    def prisoners_dilemma_matrix(self) -> PayoffMatrix:
        """Create a Prisoner's Dilemma matrix for testing."""
        params = get_default_params_for_type(MatrixType.PRISONERS_DILEMMA)
        return build_matrix(MatrixType.PRISONERS_DILEMMA, params)

    def test_correct_outcome_lookup_cc(
        self, game_state: GameState, prisoners_dilemma_matrix: PayoffMatrix
    ) -> None:
        """Test CC outcome lookup."""
        action_a = Action(name="Cooperate", action_type=ActionType.COOPERATIVE)
        action_b = Action(name="Cooperate", action_type=ActionType.COOPERATIVE)

        result = resolve_matrix_game(
            game_state, action_a, action_b, prisoners_dilemma_matrix
        )

        assert result.outcome_code == "CC"
        assert result.action_a == ActionType.COOPERATIVE
        assert result.action_b == ActionType.COOPERATIVE

    def test_correct_outcome_lookup_cd(
        self, game_state: GameState, prisoners_dilemma_matrix: PayoffMatrix
    ) -> None:
        """Test CD outcome lookup."""
        action_a = Action(name="Cooperate", action_type=ActionType.COOPERATIVE)
        action_b = Action(name="Defect", action_type=ActionType.COMPETITIVE)

        result = resolve_matrix_game(
            game_state, action_a, action_b, prisoners_dilemma_matrix
        )

        assert result.outcome_code == "CD"
        assert result.action_a == ActionType.COOPERATIVE
        assert result.action_b == ActionType.COMPETITIVE

    def test_correct_outcome_lookup_dc(
        self, game_state: GameState, prisoners_dilemma_matrix: PayoffMatrix
    ) -> None:
        """Test DC outcome lookup."""
        action_a = Action(name="Defect", action_type=ActionType.COMPETITIVE)
        action_b = Action(name="Cooperate", action_type=ActionType.COOPERATIVE)

        result = resolve_matrix_game(
            game_state, action_a, action_b, prisoners_dilemma_matrix
        )

        assert result.outcome_code == "DC"
        assert result.action_a == ActionType.COMPETITIVE
        assert result.action_b == ActionType.COOPERATIVE

    def test_correct_outcome_lookup_dd(
        self, game_state: GameState, prisoners_dilemma_matrix: PayoffMatrix
    ) -> None:
        """Test DD outcome lookup."""
        action_a = Action(name="Defect", action_type=ActionType.COMPETITIVE)
        action_b = Action(name="Defect", action_type=ActionType.COMPETITIVE)

        result = resolve_matrix_game(
            game_state, action_a, action_b, prisoners_dilemma_matrix
        )

        assert result.outcome_code == "DD"
        assert result.action_a == ActionType.COMPETITIVE
        assert result.action_b == ActionType.COMPETITIVE

    def test_state_deltas_applied(
        self, game_state: GameState, prisoners_dilemma_matrix: PayoffMatrix
    ) -> None:
        """Test that state deltas are included in result."""
        action_a = Action(name="Cooperate", action_type=ActionType.COOPERATIVE)
        action_b = Action(name="Cooperate", action_type=ActionType.COOPERATIVE)

        result = resolve_matrix_game(
            game_state, action_a, action_b, prisoners_dilemma_matrix
        )

        # Result should contain deltas from the CC outcome
        # We just verify they are present and have reasonable values
        assert hasattr(result, "position_delta_a")
        assert hasattr(result, "position_delta_b")
        assert hasattr(result, "risk_delta")

    def test_resource_cost_from_action(
        self, game_state: GameState, prisoners_dilemma_matrix: PayoffMatrix
    ) -> None:
        """Test that action resource costs are included."""
        action_a = Action(
            name="Expensive", action_type=ActionType.COOPERATIVE, resource_cost=0.5
        )
        action_b = Action(
            name="Free", action_type=ActionType.COOPERATIVE, resource_cost=0.0
        )

        result = resolve_matrix_game(
            game_state, action_a, action_b, prisoners_dilemma_matrix
        )

        # Resource cost should include action cost plus any matrix delta
        assert result.resource_cost_a >= 0.5
        assert result.resource_cost_b >= 0.0


class TestCooperationDelta:
    """Tests for cooperation delta calculation."""

    def test_cc_increases_cooperation(self) -> None:
        """CC (both cooperative) should give +1 cooperation."""
        delta = _calculate_cooperation_delta(MatrixChoice.C, MatrixChoice.C)
        assert delta == 1.0

    def test_dd_decreases_cooperation(self) -> None:
        """DD (both competitive) should give -1 cooperation."""
        delta = _calculate_cooperation_delta(MatrixChoice.D, MatrixChoice.D)
        assert delta == -1.0

    def test_cd_no_change(self) -> None:
        """CD (mixed) should give 0 cooperation change."""
        delta = _calculate_cooperation_delta(MatrixChoice.C, MatrixChoice.D)
        assert delta == 0.0

    def test_dc_no_change(self) -> None:
        """DC (mixed) should give 0 cooperation change."""
        delta = _calculate_cooperation_delta(MatrixChoice.D, MatrixChoice.C)
        assert delta == 0.0


# =============================================================================
# Act Multiplier Tests
# =============================================================================


class TestActMultiplier:
    """Tests for act multiplier calculation."""

    def test_act_i_turns_1_to_4(self) -> None:
        """Act I (turns 1-4) should have multiplier 0.7."""
        assert get_act_multiplier(1) == 0.7
        assert get_act_multiplier(2) == 0.7
        assert get_act_multiplier(3) == 0.7
        assert get_act_multiplier(4) == 0.7

    def test_act_ii_turns_5_to_8(self) -> None:
        """Act II (turns 5-8) should have multiplier 1.0."""
        assert get_act_multiplier(5) == 1.0
        assert get_act_multiplier(6) == 1.0
        assert get_act_multiplier(7) == 1.0
        assert get_act_multiplier(8) == 1.0

    def test_act_iii_turns_9_plus(self) -> None:
        """Act III (turns 9+) should have multiplier 1.3."""
        assert get_act_multiplier(9) == 1.3
        assert get_act_multiplier(10) == 1.3
        assert get_act_multiplier(15) == 1.3
        assert get_act_multiplier(100) == 1.3


# =============================================================================
# State Delta Application Tests
# =============================================================================


class TestApplyStateDeltas:
    """Tests for applying state deltas to game state."""

    @pytest.fixture
    def base_state(self) -> GameState:
        """Create a base state for testing."""
        return GameState(
            player_a=PlayerState(position=5.0, resources=5.0),
            player_b=PlayerState(position=5.0, resources=5.0),
            cooperation_score=5.0,
            stability=5.0,
            risk_level=2.0,
            turn=5,  # Act II, multiplier 1.0
        )

    def test_position_changes_scaled_by_multiplier(self, base_state: GameState) -> None:
        """Test that position changes are scaled by act multiplier."""
        deltas = StateDeltas(
            pos_a=1.0, pos_b=-1.0, res_cost_a=0.0, res_cost_b=0.0, risk_delta=0.0
        )

        # Act II (turn 5), multiplier 1.0
        new_state = apply_state_deltas(base_state, deltas)
        assert new_state.position_a == 6.0  # 5.0 + 1.0 * 1.0
        assert new_state.position_b == 4.0  # 5.0 + (-1.0) * 1.0

    def test_resource_costs_not_scaled(self, base_state: GameState) -> None:
        """Test that resource costs are NOT scaled by act multiplier."""
        deltas = StateDeltas(
            pos_a=0.0, pos_b=0.0, res_cost_a=0.5, res_cost_b=0.3, risk_delta=0.0
        )

        new_state = apply_state_deltas(base_state, deltas)
        assert new_state.resources_a == 4.5  # 5.0 - 0.5 (not scaled)
        assert new_state.resources_b == 4.7  # 5.0 - 0.3 (not scaled)

    def test_risk_changes_scaled_by_multiplier(self, base_state: GameState) -> None:
        """Test that risk changes are scaled by act multiplier."""
        deltas = StateDeltas(
            pos_a=0.0, pos_b=0.0, res_cost_a=0.0, res_cost_b=0.0, risk_delta=1.0
        )

        new_state = apply_state_deltas(base_state, deltas)
        assert new_state.risk_level == 3.0  # 2.0 + 1.0 * 1.0

    def test_values_clamped_to_bounds(self, base_state: GameState) -> None:
        """Test that values are clamped to valid ranges."""
        # Try to push position above 10
        high_deltas = StateDeltas(
            pos_a=1.5, pos_b=-1.5, res_cost_a=0.0, res_cost_b=0.0, risk_delta=0.0
        )
        # Start from position 9
        base_state.player_a.position = 9.0
        new_state = apply_state_deltas(base_state, high_deltas, act_multiplier=1.3)
        assert new_state.position_a == 10.0  # Clamped at max

    def test_explicit_act_multiplier_override(self, base_state: GameState) -> None:
        """Test that explicit act_multiplier overrides calculation."""
        deltas = StateDeltas(
            pos_a=1.0, pos_b=-1.0, res_cost_a=0.0, res_cost_b=0.0, risk_delta=0.0
        )

        # Turn 5 would normally be multiplier 1.0, but override to 0.5
        new_state = apply_state_deltas(base_state, deltas, act_multiplier=0.5)
        assert new_state.position_a == 5.5  # 5.0 + 1.0 * 0.5
        assert new_state.position_b == 4.5  # 5.0 + (-1.0) * 0.5


# =============================================================================
# Full Turn Resolution Tests
# =============================================================================


class TestResolveSimultaneousActions:
    """Tests for full simultaneous action resolution."""

    @pytest.fixture
    def game_state(self) -> GameState:
        """Create a standard game state for testing."""
        return GameState(
            player_a=PlayerState(position=5.0, resources=5.0),
            player_b=PlayerState(position=5.0, resources=5.0),
            cooperation_score=5.0,
            stability=5.0,
            risk_level=2.0,
            turn=5,
        )

    def test_returns_new_state_and_result(self, game_state: GameState) -> None:
        """Test that function returns both new state and result."""
        action_a = Action(name="Cooperate", action_type=ActionType.COOPERATIVE)
        action_b = Action(name="Cooperate", action_type=ActionType.COOPERATIVE)
        matrix = build_matrix(
            MatrixType.PRISONERS_DILEMMA,
            get_default_params_for_type(MatrixType.PRISONERS_DILEMMA),
        )

        new_state, result = resolve_simultaneous_actions(
            game_state, action_a, action_b, matrix
        )

        assert isinstance(new_state, GameState)
        assert hasattr(result, "outcome_code")

    def test_turn_incremented(self, game_state: GameState) -> None:
        """Test that turn is incremented after resolution."""
        action_a = Action(name="Cooperate", action_type=ActionType.COOPERATIVE)
        action_b = Action(name="Cooperate", action_type=ActionType.COOPERATIVE)
        matrix = build_matrix(
            MatrixType.PRISONERS_DILEMMA,
            get_default_params_for_type(MatrixType.PRISONERS_DILEMMA),
        )

        new_state, _ = resolve_simultaneous_actions(
            game_state, action_a, action_b, matrix
        )

        assert new_state.turn == game_state.turn + 1

    def test_narrative_added_to_result(self, game_state: GameState) -> None:
        """Test that outcome narrative is added to result."""
        action_a = Action(name="Cooperate", action_type=ActionType.COOPERATIVE)
        action_b = Action(name="Cooperate", action_type=ActionType.COOPERATIVE)
        matrix = build_matrix(
            MatrixType.PRISONERS_DILEMMA,
            get_default_params_for_type(MatrixType.PRISONERS_DILEMMA),
        )

        _, result = resolve_simultaneous_actions(
            game_state, action_a, action_b, matrix, outcome_narrative="Test narrative"
        )

        assert result.narrative == "Test narrative"


class TestResolveReconnaissanceTurn:
    """Tests for full reconnaissance turn resolution."""

    @pytest.fixture
    def game_state(self) -> GameState:
        """Create a standard game state for testing."""
        return GameState(
            player_a=PlayerState(position=5.0, resources=5.0),
            player_b=PlayerState(position=6.0, resources=5.0),
            cooperation_score=5.0,
            stability=5.0,
            risk_level=2.0,
            turn=5,
        )

    def test_initiator_pays_resource_cost(self, game_state: GameState) -> None:
        """Test that initiator pays 0.5 resources."""
        new_state, _ = resolve_reconnaissance_turn(
            game_state,
            player="A",
            player_choice=ReconnaissanceChoice.PROBE,
            opponent_choice=ReconnaissanceOpponentChoice.VIGILANT,
        )

        assert new_state.resources_a == pytest.approx(4.5)  # 5.0 - 0.5
        assert new_state.resources_b == pytest.approx(5.0)  # Unchanged

    def test_player_b_as_initiator(self, game_state: GameState) -> None:
        """Test that player B can be the initiator."""
        new_state, _ = resolve_reconnaissance_turn(
            game_state,
            player="B",
            player_choice=ReconnaissanceChoice.PROBE,
            opponent_choice=ReconnaissanceOpponentChoice.PROJECT,
        )

        assert new_state.resources_a == pytest.approx(5.0)  # Unchanged
        assert new_state.resources_b == pytest.approx(4.5)  # 5.0 - 0.5

    def test_success_updates_information_state(self, game_state: GameState) -> None:
        """Test that successful recon updates information state."""
        new_state, result = resolve_reconnaissance_turn(
            game_state,
            player="A",
            player_choice=ReconnaissanceChoice.PROBE,
            opponent_choice=ReconnaissanceOpponentChoice.PROJECT,
        )

        assert result.outcome == "success"
        # Player A should have learned player B's position
        assert new_state.player_a.information.known_position == 6.0
        assert new_state.player_a.information.known_position_turn == 5

    def test_turn_incremented(self, game_state: GameState) -> None:
        """Test that turn is incremented."""
        new_state, _ = resolve_reconnaissance_turn(
            game_state,
            player="A",
            player_choice=ReconnaissanceChoice.MASK,
            opponent_choice=ReconnaissanceOpponentChoice.VIGILANT,
        )

        assert new_state.turn == game_state.turn + 1


class TestResolveInspectionTurn:
    """Tests for full inspection turn resolution."""

    @pytest.fixture
    def game_state(self) -> GameState:
        """Create a standard game state for testing."""
        return GameState(
            player_a=PlayerState(position=5.0, resources=5.0),
            player_b=PlayerState(position=5.0, resources=7.0),
            cooperation_score=5.0,
            stability=5.0,
            risk_level=2.0,
            turn=5,
        )

    def test_initiator_pays_resource_cost(self, game_state: GameState) -> None:
        """Test that initiator pays 0.3 resources."""
        new_state, _ = resolve_inspection_turn(
            game_state,
            player="A",
            player_choice=InspectionChoice.INSPECT,
            opponent_choice=InspectionOpponentChoice.COMPLY,
        )

        assert new_state.resources_a == pytest.approx(4.7)  # 5.0 - 0.3

    def test_caught_cheating_applies_penalties(self, game_state: GameState) -> None:
        """Test that caught cheating applies risk and position penalties."""
        new_state, result = resolve_inspection_turn(
            game_state,
            player="A",
            player_choice=InspectionChoice.INSPECT,
            opponent_choice=InspectionOpponentChoice.CHEAT,
        )

        assert result.outcome == "caught"
        assert new_state.risk_level == pytest.approx(3.0)  # 2.0 + 1.0
        assert new_state.position_b == pytest.approx(4.5)  # 5.0 - 0.5

    def test_verified_updates_information_state(self, game_state: GameState) -> None:
        """Test that verified inspection updates information state."""
        new_state, result = resolve_inspection_turn(
            game_state,
            player="A",
            player_choice=InspectionChoice.INSPECT,
            opponent_choice=InspectionOpponentChoice.COMPLY,
        )

        assert result.outcome == "verified"
        assert new_state.player_a.information.known_resources == 7.0
        assert new_state.player_a.information.known_resources_turn == 5


# =============================================================================
# Failed Settlement and Settlement Roles Tests
# =============================================================================


class TestHandleFailedSettlement:
    """Tests for handling failed settlement attempts."""

    def test_risk_increases_by_one(self) -> None:
        """Test that risk increases by 1 on failed settlement."""
        state = GameState(
            player_a=PlayerState(position=5.0, resources=5.0),
            player_b=PlayerState(position=5.0, resources=5.0),
            risk_level=3.0,
            turn=5,
        )

        new_state = handle_failed_settlement(state)

        assert new_state.risk_level == 4.0

    def test_turn_incremented(self) -> None:
        """Test that turn is incremented on failed settlement."""
        state = GameState(
            player_a=PlayerState(position=5.0, resources=5.0),
            player_b=PlayerState(position=5.0, resources=5.0),
            risk_level=3.0,
            turn=5,
        )

        new_state = handle_failed_settlement(state)

        assert new_state.turn == 6

    def test_risk_clamped_to_max(self) -> None:
        """Test that risk is clamped to 10 maximum."""
        state = GameState(
            player_a=PlayerState(position=5.0, resources=5.0),
            player_b=PlayerState(position=5.0, resources=5.0),
            risk_level=9.5,
            turn=5,
        )

        new_state = handle_failed_settlement(state)

        assert new_state.risk_level == 10.0


class TestDetermineSettlementRoles:
    """Tests for determining proposer/recipient roles."""

    def test_higher_position_is_proposer(self) -> None:
        """Test that player with higher position becomes proposer."""
        state = GameState(
            player_a=PlayerState(position=7.0, resources=5.0),
            player_b=PlayerState(position=5.0, resources=5.0),
        )

        proposer, recipient = determine_settlement_roles(state)

        assert proposer == "A"
        assert recipient == "B"

    def test_lower_position_player_b_is_proposer(self) -> None:
        """Test that player B with higher position becomes proposer."""
        state = GameState(
            player_a=PlayerState(position=4.0, resources=5.0),
            player_b=PlayerState(position=6.0, resources=5.0),
        )

        proposer, recipient = determine_settlement_roles(state)

        assert proposer == "B"
        assert recipient == "A"

    def test_tie_defaults_to_a_as_proposer(self) -> None:
        """Test that ties default to A as proposer."""
        state = GameState(
            player_a=PlayerState(position=5.0, resources=5.0),
            player_b=PlayerState(position=5.0, resources=5.0),
        )

        proposer, recipient = determine_settlement_roles(state)

        assert proposer == "A"
        assert recipient == "B"


# =============================================================================
# Integration Tests
# =============================================================================


class TestResolutionIntegration:
    """Integration tests for the resolution system."""

    def test_full_game_turn_flow(self) -> None:
        """Test a complete game turn through the resolution system."""
        # Initial state
        state = GameState(
            player_a=PlayerState(position=5.0, resources=5.0),
            player_b=PlayerState(position=5.0, resources=5.0),
            cooperation_score=5.0,
            stability=5.0,
            risk_level=2.0,
            turn=1,
        )

        # Create actions
        action_a = Action(name="De-escalate", action_type=ActionType.COOPERATIVE)
        action_b = Action(name="De-escalate", action_type=ActionType.COOPERATIVE)

        # Create matrix
        matrix = build_matrix(
            MatrixType.PRISONERS_DILEMMA,
            get_default_params_for_type(MatrixType.PRISONERS_DILEMMA),
        )

        # Resolve
        new_state, result = resolve_simultaneous_actions(
            state, action_a, action_b, matrix
        )

        # Verify outcome
        assert result.outcome_code == "CC"
        assert new_state.turn == 2
        # Cooperation should increase for CC outcome
        assert new_state.cooperation_score >= state.cooperation_score

    def test_all_recon_outcomes_produce_valid_results(self) -> None:
        """Test all reconnaissance outcomes produce valid results."""
        state = GameState()

        player_choices = [ReconnaissanceChoice.PROBE, ReconnaissanceChoice.MASK]
        opponent_choices = [
            ReconnaissanceOpponentChoice.VIGILANT,
            ReconnaissanceOpponentChoice.PROJECT,
        ]

        for pc in player_choices:
            for oc in opponent_choices:
                result = resolve_reconnaissance(state, pc, oc)
                assert result.outcome in ["detected", "success", "stalemate", "exposed"]
                assert isinstance(result.player_learns_position, bool)
                assert isinstance(result.opponent_learns_position, bool)
                assert isinstance(result.risk_delta, float)
                assert len(result.narrative) > 0

    def test_all_inspection_outcomes_produce_valid_results(self) -> None:
        """Test all inspection outcomes produce valid results."""
        state = GameState()

        player_choices = [InspectionChoice.INSPECT, InspectionChoice.TRUST]
        opponent_choices = [
            InspectionOpponentChoice.COMPLY,
            InspectionOpponentChoice.CHEAT,
        ]

        for pc in player_choices:
            for oc in opponent_choices:
                result = resolve_inspection(state, pc, oc)
                assert result.outcome in ["verified", "caught", "nothing", "exploited"]
                assert isinstance(result.player_learns_resources, bool)
                assert isinstance(result.opponent_risk_penalty, float)
                assert len(result.narrative) > 0
