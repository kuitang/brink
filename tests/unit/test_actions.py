"""Comprehensive tests for brinksmanship.models.actions module.

Tests cover:
- ActionType and ActionCategory enums
- Action dataclass and its methods
- Standard actions (cooperative and competitive)
- Special actions (settlement, reconnaissance, inspection, costly signaling)
- ActionMenu and get_action_menu
- Helper functions (classify, validate, map to matrix choice)

REMOVED TESTS (see test_removal_log.md for rationale):
- TestActionType: test_cooperative_value, test_competitive_value, test_action_type_is_string_enum,
  test_action_type_string_comparison (keep only test_action_type_has_only_two_members)
- TestActionCategory: test_all_category_values, test_standard_is_default_category
- TestAction: Consolidated trivial creation tests, consolidated validation tests, removed redundant serialization
- TestCooperativeActions: Removed all individual property tests (test_deescalate_properties etc.),
  kept only schema validation tests
- TestCompetitiveActions: Removed all individual property tests
- TestProposeSettlement: Kept only test_propose_settlement_properties
- TestReconnaissance: Kept only resource cost test
- TestInspection: Kept only resource cost test
- TestCostlySignaling: Consolidated to key tests
- TestActionMenu: Removed test_action_menu_creation, test_action_menu_competitive_actions
- TestGetRiskTier: Kept one consolidated test
- TestGetActionMenu: Consolidated menu composition tests, kept settlement/recon affordability
- TestClassifyAction, TestMapActionToMatrixChoice: Removed entirely
- TestValidateActionAffordability: Kept 2 tests
- TestValidateActionAvailability: Consolidated
- TestCanProposeSettlement: Consolidated to 2 tests
- TestGetActionByName: Removed whitespace test, find_special_actions, empty_string
- TestFormatActionForDisplay: Consolidated to 3 tests
- TestEdgeCases: Removed extreme_positions and risk_tier_boundaries
"""

import pytest
from pydantic import ValidationError

from brinksmanship.models.actions import (
    ALL_COMPETITIVE_ACTIONS,
    # Action Collections
    ALL_COOPERATIVE_ACTIONS,
    DEESCALATE,
    ESCALATE,
    HOLD_MAINTAIN,
    INSPECTION,
    PROPOSE_SETTLEMENT,
    # Special Actions
    RECONNAISSANCE,
    Action,
    ActionCategory,
    # ActionMenu
    ActionMenu,
    # Enums
    ActionType,
    can_propose_settlement,
    create_costly_signaling_action,
    format_action_for_display,
    get_action_by_name,
    get_action_menu,
    get_risk_tier,
    # Helper functions
    validate_action_affordability,
    validate_action_availability,
)

# =============================================================================
# ActionType Enum Tests
# =============================================================================


class TestActionType:
    """Tests for ActionType enum."""

    def test_action_type_has_only_two_members(self):
        """Test ActionType has exactly two members."""
        members = list(ActionType)
        assert len(members) == 2
        assert ActionType.COOPERATIVE in members
        assert ActionType.COMPETITIVE in members


# =============================================================================
# ActionCategory Enum Tests
# =============================================================================


class TestActionCategory:
    """Tests for ActionCategory enum."""

    def test_action_category_has_five_members(self):
        """Test ActionCategory has exactly five members."""
        members = list(ActionCategory)
        assert len(members) == 5


# =============================================================================
# Action Dataclass Tests
# =============================================================================


class TestAction:
    """Tests for Action Pydantic model."""

    def test_action_creation_and_defaults(self):
        """Test creating an Action with all fields and defaults."""
        # Full creation
        action = Action(
            name="Test Action",
            action_type=ActionType.COOPERATIVE,
            resource_cost=0.5,
            description="A test action description",
            category=ActionCategory.RECONNAISSANCE,
        )
        assert action.name == "Test Action"
        assert action.action_type == ActionType.COOPERATIVE
        assert action.resource_cost == 0.5
        assert action.category == ActionCategory.RECONNAISSANCE

        # Default values
        action_min = Action(
            name="Minimal Action",
            action_type=ActionType.COMPETITIVE,
        )
        assert action_min.resource_cost == 0.0
        assert action_min.category == ActionCategory.STANDARD

    def test_action_validation(self):
        """Test validation constraints on Action."""
        # Name required and non-empty
        with pytest.raises(ValidationError):
            Action(action_type=ActionType.COOPERATIVE)
        with pytest.raises(ValidationError):
            Action(name="", action_type=ActionType.COOPERATIVE)

        # Resource cost bounds
        with pytest.raises(ValidationError):
            Action(name="Test", action_type=ActionType.COOPERATIVE, resource_cost=-0.1)
        with pytest.raises(ValidationError):
            Action(name="Test", action_type=ActionType.COOPERATIVE, resource_cost=10.1)

    def test_action_to_matrix_choice(self):
        """Test actions map to correct matrix choices."""
        coop = Action(name="Test", action_type=ActionType.COOPERATIVE)
        assert coop.to_matrix_choice() == "C"

        comp = Action(name="Test", action_type=ActionType.COMPETITIVE)
        assert comp.to_matrix_choice() == "D"

    def test_action_is_special_and_replaces_turn(self):
        """Test is_special and replaces_turn methods."""
        # Standard is not special
        standard = Action(name="Test", action_type=ActionType.COOPERATIVE)
        assert standard.is_special() is False
        assert standard.replaces_turn() is False

        # Non-standard categories are special
        for category in [
            ActionCategory.SETTLEMENT,
            ActionCategory.RECONNAISSANCE,
            ActionCategory.INSPECTION,
            ActionCategory.COSTLY_SIGNALING,
        ]:
            action = Action(
                name="Test",
                action_type=ActionType.COOPERATIVE,
                category=category,
            )
            assert action.is_special() is True

        # Turn-replacing categories
        for category in [
            ActionCategory.SETTLEMENT,
            ActionCategory.RECONNAISSANCE,
            ActionCategory.INSPECTION,
        ]:
            action = Action(
                name="Test",
                action_type=ActionType.COOPERATIVE,
                category=category,
            )
            assert action.replaces_turn() is True

        # Costly signaling does not replace turn
        signaling = Action(
            name="Test",
            action_type=ActionType.COOPERATIVE,
            category=ActionCategory.COSTLY_SIGNALING,
        )
        assert signaling.replaces_turn() is False


# =============================================================================
# Standard Action Tests - Cooperative
# =============================================================================


class TestCooperativeActions:
    """Tests for standard cooperative actions."""

    def test_all_cooperative_actions_schema(self):
        """Test ALL_COOPERATIVE_ACTIONS has correct schema."""
        assert len(ALL_COOPERATIVE_ACTIONS) == 5
        for action in ALL_COOPERATIVE_ACTIONS:
            assert action.action_type == ActionType.COOPERATIVE
            assert action.to_matrix_choice() == "C"


# =============================================================================
# Standard Action Tests - Competitive
# =============================================================================


class TestCompetitiveActions:
    """Tests for standard competitive actions."""

    def test_all_competitive_actions_schema(self):
        """Test ALL_COMPETITIVE_ACTIONS has correct schema."""
        assert len(ALL_COMPETITIVE_ACTIONS) == 6
        for action in ALL_COMPETITIVE_ACTIONS:
            assert action.action_type == ActionType.COMPETITIVE
            assert action.to_matrix_choice() == "D"


# =============================================================================
# Special Action Tests
# =============================================================================


class TestProposeSettlement:
    """Tests for PROPOSE_SETTLEMENT special action."""

    def test_propose_settlement_properties(self):
        """Test PROPOSE_SETTLEMENT has correct properties."""
        assert PROPOSE_SETTLEMENT.name == "Propose Settlement"
        assert PROPOSE_SETTLEMENT.action_type == ActionType.COOPERATIVE
        assert PROPOSE_SETTLEMENT.resource_cost == 0.0
        assert PROPOSE_SETTLEMENT.category == ActionCategory.SETTLEMENT
        assert PROPOSE_SETTLEMENT.is_special() is True
        assert PROPOSE_SETTLEMENT.replaces_turn() is True
        assert PROPOSE_SETTLEMENT.to_matrix_choice() == "C"


class TestReconnaissance:
    """Tests for RECONNAISSANCE special action."""

    def test_reconnaissance_resource_cost(self):
        """Test RECONNAISSANCE costs 0.5 resources as per GAME_MANUAL.md."""
        assert RECONNAISSANCE.resource_cost == 0.5
        assert RECONNAISSANCE.category == ActionCategory.RECONNAISSANCE
        assert RECONNAISSANCE.replaces_turn() is True


class TestInspection:
    """Tests for INSPECTION special action."""

    def test_inspection_resource_cost(self):
        """Test INSPECTION costs 0.3 resources as per GAME_MANUAL.md."""
        assert INSPECTION.resource_cost == 0.3
        assert INSPECTION.category == ActionCategory.INSPECTION
        assert INSPECTION.replaces_turn() is True


class TestCostlySignaling:
    """Tests for create_costly_signaling_action function."""

    def test_position_based_costs(self):
        """Test costly signaling costs based on position thresholds."""
        # Strong position (>=7) costs 0.3
        assert create_costly_signaling_action(7.0).resource_cost == 0.3
        assert create_costly_signaling_action(10.0).resource_cost == 0.3

        # Medium position (4-6) costs 0.7
        assert create_costly_signaling_action(4.0).resource_cost == 0.7
        assert create_costly_signaling_action(6.0).resource_cost == 0.7

        # Weak position (<=3) costs 1.2
        assert create_costly_signaling_action(3.0).resource_cost == 1.2
        assert create_costly_signaling_action(0.0).resource_cost == 1.2

    def test_costly_signaling_category_and_turn(self):
        """Test costly signaling has correct category and does not replace turn."""
        action = create_costly_signaling_action(5.0)
        assert action.name == "Signal Strength"
        assert action.action_type == ActionType.COOPERATIVE
        assert action.category == ActionCategory.COSTLY_SIGNALING
        assert action.replaces_turn() is False
        assert action.is_special() is True

    def test_costly_signaling_boundaries(self):
        """Test boundary conditions at position 7 and 4."""
        # At exactly 7, should be strong (0.3)
        assert create_costly_signaling_action(7.0).resource_cost == 0.3
        assert create_costly_signaling_action(6.999).resource_cost == 0.7

        # At exactly 4, should be medium (0.7)
        assert create_costly_signaling_action(4.0).resource_cost == 0.7
        assert create_costly_signaling_action(3.999).resource_cost == 1.2


# =============================================================================
# ActionMenu Tests
# =============================================================================


class TestActionMenu:
    """Tests for ActionMenu model."""

    def test_action_menu_all_actions(self):
        """Test all_actions method combines standard and special."""
        menu = ActionMenu(
            standard_actions=[DEESCALATE, ESCALATE],
            special_actions=[RECONNAISSANCE, INSPECTION],
            risk_level=5,
            turn=3,
            can_propose_settlement=False,
        )
        all_actions = menu.all_actions()
        assert len(all_actions) == 4
        assert DEESCALATE in all_actions
        assert RECONNAISSANCE in all_actions

    def test_action_menu_cooperative_actions(self):
        """Test cooperative_actions filters correctly."""
        menu = ActionMenu(
            standard_actions=[DEESCALATE, ESCALATE, HOLD_MAINTAIN],
            special_actions=[RECONNAISSANCE],
            risk_level=5,
            turn=3,
            can_propose_settlement=False,
        )
        coop_actions = menu.cooperative_actions()
        # DEESCALATE, HOLD_MAINTAIN, RECONNAISSANCE are cooperative
        assert len(coop_actions) == 3
        for action in coop_actions:
            assert action.action_type == ActionType.COOPERATIVE


class TestGetRiskTier:
    """Tests for get_risk_tier function."""

    def test_risk_tiers(self):
        """Test risk level to tier mapping."""
        # Low: 0-3
        assert get_risk_tier(0) == "low"
        assert get_risk_tier(3) == "low"

        # Medium: 4-6
        assert get_risk_tier(4) == "medium"
        assert get_risk_tier(6) == "medium"

        # High: 7+
        assert get_risk_tier(7) == "high"
        assert get_risk_tier(10) == "high"


class TestGetActionMenu:
    """Tests for get_action_menu function."""

    def test_menu_composition_by_risk(self):
        """Test menu composition varies by risk level."""
        # Low risk: 4 coop, 2 competitive
        low_menu = get_action_menu(
            risk_level=2,
            turn=3,
            stability=5.0,
            player_position=5.0,
            player_resources=5.0,
        )
        coop_low = [a for a in low_menu.standard_actions if a.action_type == ActionType.COOPERATIVE]
        comp_low = [a for a in low_menu.standard_actions if a.action_type == ActionType.COMPETITIVE]
        assert len(coop_low) == 4
        assert len(comp_low) == 2

        # High risk: 2 coop, 4 competitive
        high_menu = get_action_menu(
            risk_level=8,
            turn=3,
            stability=5.0,
            player_position=5.0,
            player_resources=5.0,
        )
        coop_high = [a for a in high_menu.standard_actions if a.action_type == ActionType.COOPERATIVE]
        comp_high = [a for a in high_menu.standard_actions if a.action_type == ActionType.COMPETITIVE]
        assert len(coop_high) == 2
        assert len(comp_high) == 4

    def test_settlement_availability(self):
        """Test settlement availability conditions."""
        # Available after turn 4 with stability > 2
        menu = get_action_menu(
            risk_level=5,
            turn=5,
            stability=5.0,
            player_position=5.0,
            player_resources=5.0,
        )
        assert menu.can_propose_settlement is True

        # Not available on turn 4 or earlier
        menu = get_action_menu(
            risk_level=5,
            turn=4,
            stability=5.0,
            player_position=5.0,
            player_resources=5.0,
        )
        assert menu.can_propose_settlement is False

        # Not available with low stability
        menu = get_action_menu(
            risk_level=5,
            turn=6,
            stability=2.0,
            player_position=5.0,
            player_resources=5.0,
        )
        assert menu.can_propose_settlement is False

    def test_recon_affordability(self):
        """Test reconnaissance is included/excluded based on resources."""
        # Included when affordable
        menu = get_action_menu(
            risk_level=5,
            turn=3,
            stability=5.0,
            player_position=5.0,
            player_resources=1.0,
        )
        recon = [a for a in menu.special_actions if a.category == ActionCategory.RECONNAISSANCE]
        assert len(recon) == 1

        # Excluded when not affordable
        menu = get_action_menu(
            risk_level=5,
            turn=3,
            stability=5.0,
            player_position=5.0,
            player_resources=0.4,
        )
        recon = [a for a in menu.special_actions if a.category == ActionCategory.RECONNAISSANCE]
        assert len(recon) == 0


# =============================================================================
# Helper Function Tests
# =============================================================================


class TestValidateActionAffordability:
    """Tests for validate_action_affordability helper function."""

    def test_free_action_always_affordable(self):
        """Test zero-cost actions are always affordable."""
        assert validate_action_affordability(DEESCALATE, 0.0) is True

    def test_action_affordability_with_cost(self):
        """Test affordability checks for costly actions."""
        assert validate_action_affordability(RECONNAISSANCE, 0.5) is True
        assert validate_action_affordability(RECONNAISSANCE, 0.4) is False


class TestValidateActionAvailability:
    """Tests for validate_action_availability helper function."""

    def test_standard_and_special_availability(self):
        """Test action availability conditions."""
        # Standard action always available
        is_valid, error = validate_action_availability(
            DEESCALATE,
            turn=1,
            stability=5.0,
            player_resources=0.0,
        )
        assert is_valid is True

        # Action unavailable due to resources
        is_valid, error = validate_action_availability(
            RECONNAISSANCE,
            turn=5,
            stability=5.0,
            player_resources=0.3,
        )
        assert is_valid is False
        assert "Insufficient resources" in error

        # Settlement unavailable before turn 5
        is_valid, error = validate_action_availability(
            PROPOSE_SETTLEMENT,
            turn=4,
            stability=5.0,
            player_resources=5.0,
        )
        assert is_valid is False

        # Settlement available with proper conditions
        is_valid, error = validate_action_availability(
            PROPOSE_SETTLEMENT,
            turn=5,
            stability=3.0,
            player_resources=5.0,
        )
        assert is_valid is True


class TestCanProposeSettlement:
    """Tests for can_propose_settlement helper function."""

    def test_settlement_conditions(self):
        """Test settlement availability conditions."""
        # Available after turn 4 with stability > 2
        assert can_propose_settlement(turn=5, stability=3.0) is True

        # Not available before/at turn 4 or with low stability
        assert can_propose_settlement(turn=4, stability=5.0) is False
        assert can_propose_settlement(turn=6, stability=2.0) is False


class TestGetActionByName:
    """Tests for get_action_by_name helper function."""

    def test_find_action_exact_and_case_insensitive(self):
        """Test finding actions by name."""
        action = get_action_by_name("De-escalate")
        assert action is not None
        assert action.name == "De-escalate"

        action = get_action_by_name("de-escalate")
        assert action is not None

    def test_find_all_standard_actions(self):
        """Test finding all standard actions by name."""
        action_names = [
            "De-escalate",
            "Hold / Maintain",
            "Back Channel",
            "Concede",
            "Withdraw",
            "Escalate",
            "Aggressive Pressure",
            "Issue Ultimatum",
            "Show of Force",
            "Demand",
            "Advance",
        ]
        for name in action_names:
            assert get_action_by_name(name) is not None, f"Could not find action: {name}"

    def test_action_not_found(self):
        """Test None returned for non-existent action."""
        assert get_action_by_name("Nonexistent Action") is None


class TestFormatActionForDisplay:
    """Tests for format_action_for_display helper function."""

    def test_format_standard_action(self):
        """Test formatting a standard action."""
        result = format_action_for_display(DEESCALATE, 1)
        assert "[1]" in result
        assert "De-escalate" in result
        assert "Cooperative" in result

    def test_format_action_with_resource_cost(self):
        """Test formatting an action with resource cost."""
        result = format_action_for_display(RECONNAISSANCE, 3)
        assert "[3]" in result
        assert "costs 0.5 Resources" in result
        assert "INFO GAME" in result

    def test_format_costly_signaling_action(self):
        """Test formatting costly signaling action."""
        signaling = create_costly_signaling_action(5.0)
        result = format_action_for_display(signaling, 1)
        assert "SIGNAL" in result
        assert "no turn cost" in result


# =============================================================================
# Edge Case and Integration Tests
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and integration scenarios."""

    def test_all_actions_have_descriptions(self):
        """Test all standard actions have non-empty descriptions."""
        all_actions = (
            ALL_COOPERATIVE_ACTIONS
            + ALL_COMPETITIVE_ACTIONS
            + [
                PROPOSE_SETTLEMENT,
                RECONNAISSANCE,
                INSPECTION,
            ]
        )
        for action in all_actions:
            assert action.description != "", f"{action.name} has no description"

    def test_action_collections_are_distinct(self):
        """Test cooperative and competitive collections don't overlap."""
        coop_set = {a.name for a in ALL_COOPERATIVE_ACTIONS}
        comp_set = {a.name for a in ALL_COMPETITIVE_ACTIONS}
        assert coop_set.isdisjoint(comp_set)

    def test_action_menu_with_max_resources(self):
        """Test action menu when player has maximum resources."""
        menu = get_action_menu(
            risk_level=5,
            turn=6,
            stability=5.0,
            player_position=5.0,
            player_resources=10.0,
        )
        # All special actions should be available
        categories = {a.category for a in menu.special_actions}
        assert ActionCategory.SETTLEMENT in categories
        assert ActionCategory.RECONNAISSANCE in categories
        assert ActionCategory.INSPECTION in categories
        assert ActionCategory.COSTLY_SIGNALING in categories
