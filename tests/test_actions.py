"""Comprehensive tests for brinksmanship.models.actions module.

Tests cover:
- ActionType and ActionCategory enums
- Action dataclass and its methods
- Standard actions (cooperative and competitive)
- Special actions (settlement, reconnaissance, inspection, costly signaling)
- ActionMenu and get_action_menu
- Helper functions (classify, validate, map to matrix choice)
"""

import pytest
from pydantic import ValidationError

from brinksmanship.models.actions import (
    # Enums
    ActionType,
    ActionCategory,
    # Dataclass
    Action,
    # Standard Actions - Cooperative
    DEESCALATE,
    HOLD_MAINTAIN,
    PROPOSE_SETTLEMENT,
    BACK_CHANNEL,
    CONCEDE,
    WITHDRAW,
    # Standard Actions - Competitive
    ESCALATE,
    AGGRESSIVE_PRESSURE,
    ISSUE_ULTIMATUM,
    SHOW_OF_FORCE,
    DEMAND,
    ADVANCE,
    # Special Actions
    RECONNAISSANCE,
    INSPECTION,
    create_costly_signaling_action,
    # Action Collections
    ALL_COOPERATIVE_ACTIONS,
    ALL_COMPETITIVE_ACTIONS,
    # ActionMenu
    ActionMenu,
    get_action_menu,
    get_risk_tier,
    # Helper functions
    classify_action,
    map_action_to_matrix_choice,
    validate_action_affordability,
    validate_action_availability,
    can_propose_settlement,
    get_action_by_name,
    format_action_for_display,
)


# =============================================================================
# ActionType Enum Tests
# =============================================================================


class TestActionType:
    """Tests for ActionType enum."""

    def test_cooperative_value(self):
        """Test COOPERATIVE enum has correct string value."""
        assert ActionType.COOPERATIVE.value == "cooperative"

    def test_competitive_value(self):
        """Test COMPETITIVE enum has correct string value."""
        assert ActionType.COMPETITIVE.value == "competitive"

    def test_action_type_is_string_enum(self):
        """Test ActionType inherits from str for JSON serialization."""
        assert isinstance(ActionType.COOPERATIVE, str)
        assert isinstance(ActionType.COMPETITIVE, str)

    def test_action_type_string_comparison(self):
        """Test ActionType can be compared as strings."""
        assert ActionType.COOPERATIVE == "cooperative"
        assert ActionType.COMPETITIVE == "competitive"

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

    def test_all_category_values(self):
        """Test all ActionCategory values exist with correct strings."""
        assert ActionCategory.STANDARD.value == "standard"
        assert ActionCategory.SETTLEMENT.value == "settlement"
        assert ActionCategory.RECONNAISSANCE.value == "reconnaissance"
        assert ActionCategory.INSPECTION.value == "inspection"
        assert ActionCategory.COSTLY_SIGNALING.value == "costly_signaling"

    def test_action_category_has_five_members(self):
        """Test ActionCategory has exactly five members."""
        members = list(ActionCategory)
        assert len(members) == 5

    def test_standard_is_default_category(self):
        """Test that STANDARD is meant to be the default (first in list)."""
        # This tests intent - STANDARD should be the normal case
        assert ActionCategory.STANDARD.value == "standard"


# =============================================================================
# Action Dataclass Tests
# =============================================================================


class TestAction:
    """Tests for Action Pydantic model."""

    def test_action_creation_with_all_fields(self):
        """Test creating an Action with all fields specified."""
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
        assert action.description == "A test action description"
        assert action.category == ActionCategory.RECONNAISSANCE

    def test_action_creation_with_defaults(self):
        """Test creating an Action with default values."""
        action = Action(
            name="Minimal Action",
            action_type=ActionType.COMPETITIVE,
        )
        assert action.name == "Minimal Action"
        assert action.action_type == ActionType.COMPETITIVE
        assert action.resource_cost == 0.0  # default
        assert action.description == ""  # default
        assert action.category == ActionCategory.STANDARD  # default

    def test_action_requires_name(self):
        """Test that name is required."""
        with pytest.raises(ValidationError):
            Action(action_type=ActionType.COOPERATIVE)

    def test_action_requires_action_type(self):
        """Test that action_type is required."""
        with pytest.raises(ValidationError):
            Action(name="Test")

    def test_action_name_cannot_be_empty(self):
        """Test that name must have at least 1 character."""
        with pytest.raises(ValidationError):
            Action(name="", action_type=ActionType.COOPERATIVE)

    def test_action_resource_cost_cannot_be_negative(self):
        """Test that resource_cost cannot be negative."""
        with pytest.raises(ValidationError):
            Action(name="Test", action_type=ActionType.COOPERATIVE, resource_cost=-0.1)

    def test_action_resource_cost_cannot_exceed_max(self):
        """Test that resource_cost cannot exceed 10.0."""
        with pytest.raises(ValidationError):
            Action(name="Test", action_type=ActionType.COOPERATIVE, resource_cost=10.1)

    def test_action_resource_cost_at_boundary(self):
        """Test resource_cost at boundary values."""
        # Zero is allowed
        action_zero = Action(name="Test", action_type=ActionType.COOPERATIVE, resource_cost=0.0)
        assert action_zero.resource_cost == 0.0

        # Max (10.0) is allowed
        action_max = Action(name="Test", action_type=ActionType.COOPERATIVE, resource_cost=10.0)
        assert action_max.resource_cost == 10.0

    def test_action_serialization_to_dict(self):
        """Test Action serializes to dictionary correctly."""
        action = Action(
            name="Test",
            action_type=ActionType.COOPERATIVE,
            resource_cost=0.5,
            description="Desc",
            category=ActionCategory.STANDARD,
        )
        data = action.model_dump()
        assert data["name"] == "Test"
        assert data["action_type"] == ActionType.COOPERATIVE
        assert data["resource_cost"] == 0.5
        assert data["description"] == "Desc"
        assert data["category"] == ActionCategory.STANDARD

    def test_action_serialization_to_json(self):
        """Test Action serializes to JSON correctly."""
        action = Action(
            name="Test",
            action_type=ActionType.COOPERATIVE,
        )
        json_str = action.model_dump_json()
        assert "Test" in json_str
        assert "cooperative" in json_str

    def test_action_to_matrix_choice_cooperative(self):
        """Test cooperative actions map to C."""
        action = Action(name="Test", action_type=ActionType.COOPERATIVE)
        assert action.to_matrix_choice() == "C"

    def test_action_to_matrix_choice_competitive(self):
        """Test competitive actions map to D."""
        action = Action(name="Test", action_type=ActionType.COMPETITIVE)
        assert action.to_matrix_choice() == "D"

    def test_action_is_special_for_standard(self):
        """Test is_special returns False for STANDARD category."""
        action = Action(name="Test", action_type=ActionType.COOPERATIVE)
        assert action.is_special() is False

    def test_action_is_special_for_non_standard(self):
        """Test is_special returns True for non-STANDARD categories."""
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
            assert action.is_special() is True, f"Failed for {category}"

    def test_action_replaces_turn_for_special_categories(self):
        """Test replaces_turn returns True for turn-replacing categories."""
        # These replace the turn
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
            assert action.replaces_turn() is True, f"Failed for {category}"

    def test_action_replaces_turn_for_non_replacing(self):
        """Test replaces_turn returns False for non-turn-replacing categories."""
        for category in [ActionCategory.STANDARD, ActionCategory.COSTLY_SIGNALING]:
            action = Action(
                name="Test",
                action_type=ActionType.COOPERATIVE,
                category=category,
            )
            assert action.replaces_turn() is False, f"Failed for {category}"


# =============================================================================
# Standard Action Tests - Cooperative
# =============================================================================


class TestCooperativeActions:
    """Tests for standard cooperative actions."""

    def test_deescalate_properties(self):
        """Test DEESCALATE action properties."""
        assert DEESCALATE.name == "De-escalate"
        assert DEESCALATE.action_type == ActionType.COOPERATIVE
        assert DEESCALATE.resource_cost == 0.0
        assert DEESCALATE.category == ActionCategory.STANDARD

    def test_hold_maintain_properties(self):
        """Test HOLD_MAINTAIN action properties."""
        assert HOLD_MAINTAIN.name == "Hold / Maintain"
        assert HOLD_MAINTAIN.action_type == ActionType.COOPERATIVE
        assert HOLD_MAINTAIN.resource_cost == 0.0
        assert HOLD_MAINTAIN.category == ActionCategory.STANDARD

    def test_back_channel_properties(self):
        """Test BACK_CHANNEL action properties."""
        assert BACK_CHANNEL.name == "Back Channel"
        assert BACK_CHANNEL.action_type == ActionType.COOPERATIVE
        assert BACK_CHANNEL.resource_cost == 0.0
        assert BACK_CHANNEL.category == ActionCategory.STANDARD

    def test_concede_properties(self):
        """Test CONCEDE action properties."""
        assert CONCEDE.name == "Concede"
        assert CONCEDE.action_type == ActionType.COOPERATIVE
        assert CONCEDE.resource_cost == 0.0
        assert CONCEDE.category == ActionCategory.STANDARD

    def test_withdraw_properties(self):
        """Test WITHDRAW action properties."""
        assert WITHDRAW.name == "Withdraw"
        assert WITHDRAW.action_type == ActionType.COOPERATIVE
        assert WITHDRAW.resource_cost == 0.0
        assert WITHDRAW.category == ActionCategory.STANDARD

    def test_all_cooperative_actions_list(self):
        """Test ALL_COOPERATIVE_ACTIONS contains expected actions."""
        assert DEESCALATE in ALL_COOPERATIVE_ACTIONS
        assert HOLD_MAINTAIN in ALL_COOPERATIVE_ACTIONS
        assert BACK_CHANNEL in ALL_COOPERATIVE_ACTIONS
        assert CONCEDE in ALL_COOPERATIVE_ACTIONS
        assert WITHDRAW in ALL_COOPERATIVE_ACTIONS
        assert len(ALL_COOPERATIVE_ACTIONS) == 5

    def test_all_cooperative_actions_are_cooperative_type(self):
        """Test all actions in ALL_COOPERATIVE_ACTIONS have COOPERATIVE type."""
        for action in ALL_COOPERATIVE_ACTIONS:
            assert action.action_type == ActionType.COOPERATIVE, f"{action.name} is not COOPERATIVE"

    def test_all_cooperative_actions_map_to_c(self):
        """Test all cooperative actions map to matrix choice C."""
        for action in ALL_COOPERATIVE_ACTIONS:
            assert action.to_matrix_choice() == "C", f"{action.name} does not map to C"


# =============================================================================
# Standard Action Tests - Competitive
# =============================================================================


class TestCompetitiveActions:
    """Tests for standard competitive actions."""

    def test_escalate_properties(self):
        """Test ESCALATE action properties."""
        assert ESCALATE.name == "Escalate"
        assert ESCALATE.action_type == ActionType.COMPETITIVE
        assert ESCALATE.resource_cost == 0.0
        assert ESCALATE.category == ActionCategory.STANDARD

    def test_aggressive_pressure_properties(self):
        """Test AGGRESSIVE_PRESSURE action properties."""
        assert AGGRESSIVE_PRESSURE.name == "Aggressive Pressure"
        assert AGGRESSIVE_PRESSURE.action_type == ActionType.COMPETITIVE
        assert AGGRESSIVE_PRESSURE.resource_cost == 0.0
        assert AGGRESSIVE_PRESSURE.category == ActionCategory.STANDARD

    def test_issue_ultimatum_properties(self):
        """Test ISSUE_ULTIMATUM action properties."""
        assert ISSUE_ULTIMATUM.name == "Issue Ultimatum"
        assert ISSUE_ULTIMATUM.action_type == ActionType.COMPETITIVE
        assert ISSUE_ULTIMATUM.resource_cost == 0.0
        assert ISSUE_ULTIMATUM.category == ActionCategory.STANDARD

    def test_show_of_force_properties(self):
        """Test SHOW_OF_FORCE action properties."""
        assert SHOW_OF_FORCE.name == "Show of Force"
        assert SHOW_OF_FORCE.action_type == ActionType.COMPETITIVE
        assert SHOW_OF_FORCE.resource_cost == 0.0
        assert SHOW_OF_FORCE.category == ActionCategory.STANDARD

    def test_demand_properties(self):
        """Test DEMAND action properties."""
        assert DEMAND.name == "Demand"
        assert DEMAND.action_type == ActionType.COMPETITIVE
        assert DEMAND.resource_cost == 0.0
        assert DEMAND.category == ActionCategory.STANDARD

    def test_advance_properties(self):
        """Test ADVANCE action properties."""
        assert ADVANCE.name == "Advance"
        assert ADVANCE.action_type == ActionType.COMPETITIVE
        assert ADVANCE.resource_cost == 0.0
        assert ADVANCE.category == ActionCategory.STANDARD

    def test_all_competitive_actions_list(self):
        """Test ALL_COMPETITIVE_ACTIONS contains expected actions."""
        assert ESCALATE in ALL_COMPETITIVE_ACTIONS
        assert AGGRESSIVE_PRESSURE in ALL_COMPETITIVE_ACTIONS
        assert ISSUE_ULTIMATUM in ALL_COMPETITIVE_ACTIONS
        assert SHOW_OF_FORCE in ALL_COMPETITIVE_ACTIONS
        assert DEMAND in ALL_COMPETITIVE_ACTIONS
        assert ADVANCE in ALL_COMPETITIVE_ACTIONS
        assert len(ALL_COMPETITIVE_ACTIONS) == 6

    def test_all_competitive_actions_are_competitive_type(self):
        """Test all actions in ALL_COMPETITIVE_ACTIONS have COMPETITIVE type."""
        for action in ALL_COMPETITIVE_ACTIONS:
            assert action.action_type == ActionType.COMPETITIVE, f"{action.name} is not COMPETITIVE"

    def test_all_competitive_actions_map_to_d(self):
        """Test all competitive actions map to matrix choice D."""
        for action in ALL_COMPETITIVE_ACTIONS:
            assert action.to_matrix_choice() == "D", f"{action.name} does not map to D"


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

    def test_propose_settlement_is_special(self):
        """Test PROPOSE_SETTLEMENT is marked as special."""
        assert PROPOSE_SETTLEMENT.is_special() is True

    def test_propose_settlement_replaces_turn(self):
        """Test PROPOSE_SETTLEMENT replaces the turn."""
        assert PROPOSE_SETTLEMENT.replaces_turn() is True

    def test_propose_settlement_maps_to_c(self):
        """Test PROPOSE_SETTLEMENT maps to C (cooperative)."""
        assert PROPOSE_SETTLEMENT.to_matrix_choice() == "C"


class TestReconnaissance:
    """Tests for RECONNAISSANCE special action."""

    def test_reconnaissance_resource_cost(self):
        """Test RECONNAISSANCE costs 0.5 resources as per GAME_MANUAL.md."""
        assert RECONNAISSANCE.resource_cost == 0.5

    def test_reconnaissance_properties(self):
        """Test RECONNAISSANCE has correct properties."""
        assert RECONNAISSANCE.name == "Initiate Reconnaissance"
        assert RECONNAISSANCE.action_type == ActionType.COOPERATIVE
        assert RECONNAISSANCE.category == ActionCategory.RECONNAISSANCE

    def test_reconnaissance_is_special(self):
        """Test RECONNAISSANCE is marked as special."""
        assert RECONNAISSANCE.is_special() is True

    def test_reconnaissance_replaces_turn(self):
        """Test RECONNAISSANCE replaces the turn."""
        assert RECONNAISSANCE.replaces_turn() is True


class TestInspection:
    """Tests for INSPECTION special action."""

    def test_inspection_resource_cost(self):
        """Test INSPECTION costs 0.3 resources as per GAME_MANUAL.md."""
        assert INSPECTION.resource_cost == 0.3

    def test_inspection_properties(self):
        """Test INSPECTION has correct properties."""
        assert INSPECTION.name == "Initiate Inspection"
        assert INSPECTION.action_type == ActionType.COOPERATIVE
        assert INSPECTION.category == ActionCategory.INSPECTION

    def test_inspection_is_special(self):
        """Test INSPECTION is marked as special."""
        assert INSPECTION.is_special() is True

    def test_inspection_replaces_turn(self):
        """Test INSPECTION replaces the turn."""
        assert INSPECTION.replaces_turn() is True


class TestCostlySignaling:
    """Tests for create_costly_signaling_action function."""

    def test_strong_position_cost(self):
        """Test position >= 7 costs 0.3 resources."""
        for position in [7.0, 8.0, 9.0, 10.0]:
            action = create_costly_signaling_action(position)
            assert action.resource_cost == 0.3, f"Failed for position {position}"

    def test_medium_position_cost(self):
        """Test position 4-6 costs 0.7 resources."""
        for position in [4.0, 5.0, 6.0, 6.9]:
            action = create_costly_signaling_action(position)
            assert action.resource_cost == 0.7, f"Failed for position {position}"

    def test_weak_position_cost(self):
        """Test position <= 3 costs 1.2 resources."""
        for position in [0.0, 1.0, 2.0, 3.0, 3.9]:
            action = create_costly_signaling_action(position)
            assert action.resource_cost == 1.2, f"Failed for position {position}"

    def test_costly_signaling_action_name(self):
        """Test costly signaling action has correct name."""
        action = create_costly_signaling_action(5.0)
        assert action.name == "Signal Strength"

    def test_costly_signaling_is_cooperative(self):
        """Test costly signaling is classified as cooperative."""
        action = create_costly_signaling_action(5.0)
        assert action.action_type == ActionType.COOPERATIVE

    def test_costly_signaling_category(self):
        """Test costly signaling has COSTLY_SIGNALING category."""
        action = create_costly_signaling_action(5.0)
        assert action.category == ActionCategory.COSTLY_SIGNALING

    def test_costly_signaling_does_not_replace_turn(self):
        """Test costly signaling does NOT replace the regular turn."""
        action = create_costly_signaling_action(5.0)
        assert action.replaces_turn() is False

    def test_costly_signaling_is_special(self):
        """Test costly signaling is marked as special."""
        action = create_costly_signaling_action(5.0)
        assert action.is_special() is True

    def test_costly_signaling_boundary_at_7(self):
        """Test boundary condition at position 7."""
        # At exactly 7, should be strong (0.3)
        action_at_7 = create_costly_signaling_action(7.0)
        assert action_at_7.resource_cost == 0.3

        # Just below 7, should be medium (0.7)
        action_below_7 = create_costly_signaling_action(6.999)
        assert action_below_7.resource_cost == 0.7

    def test_costly_signaling_boundary_at_4(self):
        """Test boundary condition at position 4."""
        # At exactly 4, should be medium (0.7)
        action_at_4 = create_costly_signaling_action(4.0)
        assert action_at_4.resource_cost == 0.7

        # Just below 4, should be weak (1.2)
        action_below_4 = create_costly_signaling_action(3.999)
        assert action_below_4.resource_cost == 1.2


# =============================================================================
# ActionMenu Tests
# =============================================================================


class TestActionMenu:
    """Tests for ActionMenu model."""

    def test_action_menu_creation(self):
        """Test creating an ActionMenu with all fields."""
        menu = ActionMenu(
            standard_actions=[DEESCALATE, ESCALATE],
            special_actions=[RECONNAISSANCE],
            risk_level=5,
            turn=3,
            can_propose_settlement=False,
        )
        assert len(menu.standard_actions) == 2
        assert len(menu.special_actions) == 1
        assert menu.risk_level == 5
        assert menu.turn == 3
        assert menu.can_propose_settlement is False

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
        assert ESCALATE in all_actions
        assert RECONNAISSANCE in all_actions
        assert INSPECTION in all_actions

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

    def test_action_menu_competitive_actions(self):
        """Test competitive_actions filters correctly."""
        menu = ActionMenu(
            standard_actions=[DEESCALATE, ESCALATE, AGGRESSIVE_PRESSURE],
            special_actions=[RECONNAISSANCE],
            risk_level=5,
            turn=3,
            can_propose_settlement=False,
        )
        comp_actions = menu.competitive_actions()
        # ESCALATE, AGGRESSIVE_PRESSURE are competitive
        assert len(comp_actions) == 2
        for action in comp_actions:
            assert action.action_type == ActionType.COMPETITIVE


class TestGetRiskTier:
    """Tests for get_risk_tier function."""

    def test_low_risk_tier(self):
        """Test risk levels 0-3 return 'low'."""
        for level in [0, 1, 2, 3]:
            assert get_risk_tier(level) == "low", f"Failed for level {level}"

    def test_medium_risk_tier(self):
        """Test risk levels 4-6 return 'medium'."""
        for level in [4, 5, 6]:
            assert get_risk_tier(level) == "medium", f"Failed for level {level}"

    def test_high_risk_tier(self):
        """Test risk levels 7+ return 'high'."""
        for level in [7, 8, 9, 10]:
            assert get_risk_tier(level) == "high", f"Failed for level {level}"


class TestGetActionMenu:
    """Tests for get_action_menu function."""

    def test_low_risk_menu_composition(self):
        """Test low risk menu has more cooperative options (4 coop, 2 competitive)."""
        menu = get_action_menu(
            risk_level=2,
            turn=3,
            stability=5.0,
            player_position=5.0,
            player_resources=5.0,
        )
        # Check standard actions only (special actions vary by affordability)
        coop_standard = [a for a in menu.standard_actions if a.action_type == ActionType.COOPERATIVE]
        comp_standard = [a for a in menu.standard_actions if a.action_type == ActionType.COMPETITIVE]
        assert len(coop_standard) == 4
        assert len(comp_standard) == 2

    def test_medium_risk_menu_composition(self):
        """Test medium risk menu has balanced options (3 coop, 3 competitive)."""
        menu = get_action_menu(
            risk_level=5,
            turn=3,
            stability=5.0,
            player_position=5.0,
            player_resources=5.0,
        )
        coop_standard = [a for a in menu.standard_actions if a.action_type == ActionType.COOPERATIVE]
        comp_standard = [a for a in menu.standard_actions if a.action_type == ActionType.COMPETITIVE]
        assert len(coop_standard) == 3
        assert len(comp_standard) == 3

    def test_high_risk_menu_composition(self):
        """Test high risk menu has more confrontational options (2 coop, 4 competitive)."""
        menu = get_action_menu(
            risk_level=8,
            turn=3,
            stability=5.0,
            player_position=5.0,
            player_resources=5.0,
        )
        coop_standard = [a for a in menu.standard_actions if a.action_type == ActionType.COOPERATIVE]
        comp_standard = [a for a in menu.standard_actions if a.action_type == ActionType.COMPETITIVE]
        assert len(coop_standard) == 2
        assert len(comp_standard) == 4

    def test_menu_includes_settlement_after_turn_4_with_sufficient_stability(self):
        """Test settlement is available after turn 4 with stability > 2."""
        menu = get_action_menu(
            risk_level=5,
            turn=5,
            stability=5.0,
            player_position=5.0,
            player_resources=5.0,
        )
        assert menu.can_propose_settlement is True
        settlement_actions = [a for a in menu.special_actions if a.category == ActionCategory.SETTLEMENT]
        assert len(settlement_actions) == 1

    def test_menu_excludes_settlement_before_turn_5(self):
        """Test settlement is NOT available on turn 4 or earlier."""
        for turn in [1, 2, 3, 4]:
            menu = get_action_menu(
                risk_level=5,
                turn=turn,
                stability=5.0,
                player_position=5.0,
                player_resources=5.0,
            )
            assert menu.can_propose_settlement is False, f"Failed for turn {turn}"

    def test_menu_excludes_settlement_with_low_stability(self):
        """Test settlement is NOT available when stability <= 2."""
        for stability in [0.0, 1.0, 2.0]:
            menu = get_action_menu(
                risk_level=5,
                turn=6,
                stability=stability,
                player_position=5.0,
                player_resources=5.0,
            )
            assert menu.can_propose_settlement is False, f"Failed for stability {stability}"

    def test_menu_includes_recon_when_affordable(self):
        """Test reconnaissance is included when player has enough resources."""
        menu = get_action_menu(
            risk_level=5,
            turn=3,
            stability=5.0,
            player_position=5.0,
            player_resources=1.0,  # More than 0.5
        )
        recon_actions = [a for a in menu.special_actions if a.category == ActionCategory.RECONNAISSANCE]
        assert len(recon_actions) == 1

    def test_menu_excludes_recon_when_not_affordable(self):
        """Test reconnaissance is excluded when player lacks resources."""
        menu = get_action_menu(
            risk_level=5,
            turn=3,
            stability=5.0,
            player_position=5.0,
            player_resources=0.4,  # Less than 0.5
        )
        recon_actions = [a for a in menu.special_actions if a.category == ActionCategory.RECONNAISSANCE]
        assert len(recon_actions) == 0

    def test_menu_includes_inspection_when_affordable(self):
        """Test inspection is included when player has enough resources."""
        menu = get_action_menu(
            risk_level=5,
            turn=3,
            stability=5.0,
            player_position=5.0,
            player_resources=0.5,  # More than 0.3
        )
        inspection_actions = [a for a in menu.special_actions if a.category == ActionCategory.INSPECTION]
        assert len(inspection_actions) == 1

    def test_menu_excludes_inspection_when_not_affordable(self):
        """Test inspection is excluded when player lacks resources."""
        menu = get_action_menu(
            risk_level=5,
            turn=3,
            stability=5.0,
            player_position=5.0,
            player_resources=0.2,  # Less than 0.3
        )
        inspection_actions = [a for a in menu.special_actions if a.category == ActionCategory.INSPECTION]
        assert len(inspection_actions) == 0

    def test_menu_includes_costly_signaling_when_affordable(self):
        """Test costly signaling is included when player has enough resources."""
        # Strong position (>=7) costs 0.3
        menu = get_action_menu(
            risk_level=5,
            turn=3,
            stability=5.0,
            player_position=8.0,  # Strong
            player_resources=0.5,  # More than 0.3
        )
        signaling_actions = [a for a in menu.special_actions if a.category == ActionCategory.COSTLY_SIGNALING]
        assert len(signaling_actions) == 1

    def test_menu_excludes_costly_signaling_when_not_affordable(self):
        """Test costly signaling is excluded when player lacks resources."""
        # Weak position (<=3) costs 1.2
        menu = get_action_menu(
            risk_level=5,
            turn=3,
            stability=5.0,
            player_position=2.0,  # Weak, costs 1.2
            player_resources=1.0,  # Less than 1.2
        )
        signaling_actions = [a for a in menu.special_actions if a.category == ActionCategory.COSTLY_SIGNALING]
        assert len(signaling_actions) == 0


# =============================================================================
# Helper Function Tests
# =============================================================================


class TestClassifyAction:
    """Tests for classify_action helper function."""

    def test_classify_cooperative_action(self):
        """Test classify_action returns COOPERATIVE for cooperative actions."""
        assert classify_action(DEESCALATE) == ActionType.COOPERATIVE
        assert classify_action(HOLD_MAINTAIN) == ActionType.COOPERATIVE
        assert classify_action(PROPOSE_SETTLEMENT) == ActionType.COOPERATIVE

    def test_classify_competitive_action(self):
        """Test classify_action returns COMPETITIVE for competitive actions."""
        assert classify_action(ESCALATE) == ActionType.COMPETITIVE
        assert classify_action(AGGRESSIVE_PRESSURE) == ActionType.COMPETITIVE
        assert classify_action(DEMAND) == ActionType.COMPETITIVE


class TestMapActionToMatrixChoice:
    """Tests for map_action_to_matrix_choice helper function."""

    def test_cooperative_maps_to_c(self):
        """Test cooperative actions map to 'C'."""
        assert map_action_to_matrix_choice(DEESCALATE) == "C"
        assert map_action_to_matrix_choice(HOLD_MAINTAIN) == "C"
        assert map_action_to_matrix_choice(BACK_CHANNEL) == "C"
        assert map_action_to_matrix_choice(PROPOSE_SETTLEMENT) == "C"
        assert map_action_to_matrix_choice(RECONNAISSANCE) == "C"

    def test_competitive_maps_to_d(self):
        """Test competitive actions map to 'D'."""
        assert map_action_to_matrix_choice(ESCALATE) == "D"
        assert map_action_to_matrix_choice(AGGRESSIVE_PRESSURE) == "D"
        assert map_action_to_matrix_choice(ISSUE_ULTIMATUM) == "D"
        assert map_action_to_matrix_choice(SHOW_OF_FORCE) == "D"
        assert map_action_to_matrix_choice(DEMAND) == "D"


class TestValidateActionAffordability:
    """Tests for validate_action_affordability helper function."""

    def test_free_action_always_affordable(self):
        """Test zero-cost actions are always affordable."""
        assert validate_action_affordability(DEESCALATE, 0.0) is True
        assert validate_action_affordability(ESCALATE, 0.0) is True

    def test_action_affordable_with_exact_resources(self):
        """Test action is affordable when resources exactly match cost."""
        assert validate_action_affordability(RECONNAISSANCE, 0.5) is True
        assert validate_action_affordability(INSPECTION, 0.3) is True

    def test_action_affordable_with_excess_resources(self):
        """Test action is affordable when resources exceed cost."""
        assert validate_action_affordability(RECONNAISSANCE, 5.0) is True
        assert validate_action_affordability(INSPECTION, 1.0) is True

    def test_action_not_affordable_with_insufficient_resources(self):
        """Test action is not affordable when resources are insufficient."""
        assert validate_action_affordability(RECONNAISSANCE, 0.4) is False
        assert validate_action_affordability(INSPECTION, 0.2) is False

    def test_costly_signaling_affordability(self):
        """Test costly signaling affordability at various positions."""
        weak_signal = create_costly_signaling_action(2.0)  # Costs 1.2
        assert validate_action_affordability(weak_signal, 1.2) is True
        assert validate_action_affordability(weak_signal, 1.0) is False

        strong_signal = create_costly_signaling_action(8.0)  # Costs 0.3
        assert validate_action_affordability(strong_signal, 0.3) is True
        assert validate_action_affordability(strong_signal, 0.2) is False


class TestValidateActionAvailability:
    """Tests for validate_action_availability helper function."""

    def test_standard_action_always_available(self):
        """Test standard zero-cost actions are always available."""
        is_valid, error = validate_action_availability(
            DEESCALATE,
            turn=1,
            stability=5.0,
            player_resources=0.0,
        )
        assert is_valid is True
        assert error is None

    def test_action_unavailable_due_to_resources(self):
        """Test action unavailable when resources insufficient."""
        is_valid, error = validate_action_availability(
            RECONNAISSANCE,
            turn=5,
            stability=5.0,
            player_resources=0.3,  # Less than 0.5
        )
        assert is_valid is False
        assert "Insufficient resources" in error

    def test_settlement_unavailable_before_turn_5(self):
        """Test settlement unavailable before turn 5."""
        is_valid, error = validate_action_availability(
            PROPOSE_SETTLEMENT,
            turn=4,
            stability=5.0,
            player_resources=5.0,
        )
        assert is_valid is False
        assert "Turn 4" in error

    def test_settlement_unavailable_with_low_stability(self):
        """Test settlement unavailable when stability <= 2."""
        is_valid, error = validate_action_availability(
            PROPOSE_SETTLEMENT,
            turn=6,
            stability=2.0,  # Exactly 2, which is <= 2
            player_resources=5.0,
        )
        assert is_valid is False
        assert "Stability" in error

    def test_settlement_available_with_proper_conditions(self):
        """Test settlement available after turn 4 with stability > 2."""
        is_valid, error = validate_action_availability(
            PROPOSE_SETTLEMENT,
            turn=5,
            stability=3.0,
            player_resources=5.0,
        )
        assert is_valid is True
        assert error is None


class TestCanProposeSettlement:
    """Tests for can_propose_settlement helper function."""

    def test_settlement_available_after_turn_4_with_stability(self):
        """Test settlement available after turn 4 with stability > 2."""
        assert can_propose_settlement(turn=5, stability=3.0) is True
        assert can_propose_settlement(turn=6, stability=5.0) is True
        assert can_propose_settlement(turn=10, stability=10.0) is True

    def test_settlement_not_available_on_turn_4(self):
        """Test settlement NOT available on turn 4 exactly."""
        assert can_propose_settlement(turn=4, stability=5.0) is False

    def test_settlement_not_available_before_turn_4(self):
        """Test settlement NOT available before turn 4."""
        for turn in [1, 2, 3]:
            assert can_propose_settlement(turn=turn, stability=5.0) is False

    def test_settlement_not_available_with_stability_2(self):
        """Test settlement NOT available when stability is exactly 2."""
        assert can_propose_settlement(turn=6, stability=2.0) is False

    def test_settlement_not_available_with_low_stability(self):
        """Test settlement NOT available when stability <= 2."""
        for stability in [0.0, 1.0, 1.5, 2.0]:
            assert can_propose_settlement(turn=6, stability=stability) is False

    def test_settlement_available_at_boundary(self):
        """Test settlement available at boundary conditions."""
        # Turn 5 (first available), stability just above 2
        assert can_propose_settlement(turn=5, stability=2.1) is True


class TestGetActionByName:
    """Tests for get_action_by_name helper function."""

    def test_find_action_exact_match(self):
        """Test finding action with exact name match."""
        action = get_action_by_name("De-escalate")
        assert action is not None
        assert action.name == "De-escalate"

    def test_find_action_case_insensitive(self):
        """Test finding action is case-insensitive."""
        action = get_action_by_name("de-escalate")
        assert action is not None
        assert action.name == "De-escalate"

        action = get_action_by_name("DE-ESCALATE")
        assert action is not None
        assert action.name == "De-escalate"

    def test_find_action_with_whitespace(self):
        """Test finding action handles whitespace."""
        action = get_action_by_name("  De-escalate  ")
        assert action is not None
        assert action.name == "De-escalate"

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
            action = get_action_by_name(name)
            assert action is not None, f"Could not find action: {name}"

    def test_find_special_actions(self):
        """Test finding special actions by name."""
        assert get_action_by_name("Propose Settlement") is not None
        assert get_action_by_name("Initiate Reconnaissance") is not None
        assert get_action_by_name("Initiate Inspection") is not None

    def test_action_not_found(self):
        """Test None returned for non-existent action."""
        action = get_action_by_name("Nonexistent Action")
        assert action is None

    def test_action_not_found_empty_string(self):
        """Test None returned for empty string."""
        action = get_action_by_name("")
        assert action is None


class TestFormatActionForDisplay:
    """Tests for format_action_for_display helper function."""

    def test_format_standard_cooperative_action(self):
        """Test formatting a standard cooperative action."""
        result = format_action_for_display(DEESCALATE, 1)
        assert "[1]" in result
        assert "De-escalate" in result
        assert "Cooperative" in result
        assert "costs" not in result  # No resource cost

    def test_format_standard_competitive_action(self):
        """Test formatting a standard competitive action."""
        result = format_action_for_display(ESCALATE, 2)
        assert "[2]" in result
        assert "Escalate" in result
        assert "Competitive" in result

    def test_format_action_with_resource_cost(self):
        """Test formatting an action with resource cost."""
        result = format_action_for_display(RECONNAISSANCE, 3)
        assert "[3]" in result
        assert "Initiate Reconnaissance" in result
        assert "costs 0.5 Resources" in result
        assert "INFO GAME" in result

    def test_format_settlement_action(self):
        """Test formatting settlement action."""
        result = format_action_for_display(PROPOSE_SETTLEMENT, 1)
        assert "SETTLEMENT" in result

    def test_format_reconnaissance_action(self):
        """Test formatting reconnaissance action."""
        result = format_action_for_display(RECONNAISSANCE, 1)
        assert "INFO GAME" in result
        assert "replaces turn" in result

    def test_format_inspection_action(self):
        """Test formatting inspection action."""
        result = format_action_for_display(INSPECTION, 1)
        assert "INFO GAME" in result
        assert "replaces turn" in result

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
        all_actions = ALL_COOPERATIVE_ACTIONS + ALL_COMPETITIVE_ACTIONS + [
            PROPOSE_SETTLEMENT,
            RECONNAISSANCE,
            INSPECTION,
        ]
        for action in all_actions:
            assert action.description != "", f"{action.name} has no description"

    def test_action_collections_are_distinct(self):
        """Test cooperative and competitive collections don't overlap."""
        coop_set = set(a.name for a in ALL_COOPERATIVE_ACTIONS)
        comp_set = set(a.name for a in ALL_COMPETITIVE_ACTIONS)
        assert coop_set.isdisjoint(comp_set)

    def test_costly_signaling_at_extreme_positions(self):
        """Test costly signaling at extreme position values."""
        # At position 0
        action_zero = create_costly_signaling_action(0.0)
        assert action_zero.resource_cost == 1.2

        # At position 10
        action_ten = create_costly_signaling_action(10.0)
        assert action_ten.resource_cost == 0.3

    def test_action_menu_with_no_resources(self):
        """Test action menu when player has no resources."""
        menu = get_action_menu(
            risk_level=5,
            turn=6,
            stability=5.0,
            player_position=5.0,
            player_resources=0.0,
        )
        # Should only have standard actions (no special actions require 0 cost)
        # And settlement if available (no cost)
        for action in menu.special_actions:
            if action.category != ActionCategory.SETTLEMENT:
                assert action.resource_cost == 0.0

    def test_action_menu_with_maximum_resources(self):
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

    def test_risk_tier_boundaries(self):
        """Test risk tier classification at exact boundaries."""
        # Boundary at 3/4
        assert get_risk_tier(3) == "low"
        assert get_risk_tier(4) == "medium"

        # Boundary at 6/7
        assert get_risk_tier(6) == "medium"
        assert get_risk_tier(7) == "high"
