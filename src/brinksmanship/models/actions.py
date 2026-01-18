"""Action definitions for Brinksmanship.

This module defines all game actions, their classifications (Cooperative vs Competitive),
and the action menus available at different Risk Levels. See GAME_MANUAL.md Section 3.2
for the authoritative action classification.
"""

from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


class ActionType(str, Enum):
    """Classification of actions as Cooperative or Competitive.

    This classification determines:
    - How the action maps to matrix choices (C or D)
    - How Cooperation Score is updated
    - How Stability is affected by switching types

    Inherits from str for proper JSON serialization.
    """

    COOPERATIVE = "cooperative"
    COMPETITIVE = "competitive"


class ActionCategory(Enum):
    """Special categories for actions that bypass normal matrix resolution."""

    STANDARD = "standard"  # Normal matrix game action
    SETTLEMENT = "settlement"  # Bypasses matrix, special negotiation
    RECONNAISSANCE = "reconnaissance"  # Information game for Position
    INSPECTION = "inspection"  # Information game for Resources
    COSTLY_SIGNALING = "costly_signaling"  # Voluntary disclosure, no turn cost


class Action(BaseModel):
    """A game action that a player can take.

    Actions are classified as either Cooperative or Competitive, which determines
    how they map to matrix game choices (C or D respectively).

    Attributes:
        name: The action name displayed to players
        action_type: Whether the action is COOPERATIVE or COMPETITIVE
        resource_cost: Resources consumed when taking this action (default 0)
        description: Human-readable description of the action
        category: Special action category (default STANDARD)
    """

    name: str = Field(..., min_length=1)
    action_type: ActionType
    resource_cost: float = Field(default=0.0, ge=0.0)
    description: str = Field(default="")
    category: ActionCategory = Field(default=ActionCategory.STANDARD)

    @field_validator("resource_cost")
    @classmethod
    def validate_resource_cost(cls, v: float) -> float:
        """Ensure resource cost is non-negative and reasonable."""
        if v < 0:
            raise ValueError("Resource cost cannot be negative")
        if v > 10.0:
            raise ValueError("Resource cost cannot exceed 10.0 (max resources)")
        return v

    def to_matrix_choice(self) -> Literal["C", "D"]:
        """Map action type to matrix game choice.

        Cooperative actions map to C (Cooperate).
        Competitive actions map to D (Defect).
        """
        if self.action_type == ActionType.COOPERATIVE:
            return "C"
        return "D"

    def is_special(self) -> bool:
        """Check if this action requires special handling (non-standard resolution)."""
        return self.category != ActionCategory.STANDARD

    def replaces_turn(self) -> bool:
        """Check if this action replaces the regular matrix game for the turn."""
        return self.category in (
            ActionCategory.SETTLEMENT,
            ActionCategory.RECONNAISSANCE,
            ActionCategory.INSPECTION,
        )


# =============================================================================
# Standard Actions (from GAME_MANUAL.md Section 3.2)
# =============================================================================

# Cooperative Actions
DEESCALATE = Action(
    name="De-escalate",
    action_type=ActionType.COOPERATIVE,
    description="Reduce tensions through measured withdrawal or conciliatory gestures.",
)

HOLD_MAINTAIN = Action(
    name="Hold / Maintain",
    action_type=ActionType.COOPERATIVE,
    description="Maintain current position without escalation or de-escalation.",
)

PROPOSE_SETTLEMENT = Action(
    name="Propose Settlement",
    action_type=ActionType.COOPERATIVE,
    category=ActionCategory.SETTLEMENT,
    description="Offer to negotiate a mutually acceptable end to the crisis. "
    "Available after Turn 4 unless Stability <= 2.",
)

BACK_CHANNEL = Action(
    name="Back Channel",
    action_type=ActionType.COOPERATIVE,
    description="Initiate informal, deniable communication to explore options.",
)

CONCEDE = Action(
    name="Concede",
    action_type=ActionType.COOPERATIVE,
    resource_cost=0.0,
    description="Accept a disadvantageous position to reduce overall risk.",
)

WITHDRAW = Action(
    name="Withdraw",
    action_type=ActionType.COOPERATIVE,
    description="Pull back from contested position or claim.",
)

# Competitive Actions
ESCALATE = Action(
    name="Escalate",
    action_type=ActionType.COMPETITIVE,
    description="Increase pressure and commitment to current position.",
)

AGGRESSIVE_PRESSURE = Action(
    name="Aggressive Pressure",
    action_type=ActionType.COMPETITIVE,
    description="Apply direct pressure through threats or demonstrations.",
)

ISSUE_ULTIMATUM = Action(
    name="Issue Ultimatum",
    action_type=ActionType.COMPETITIVE,
    description="Demand specific concessions with implicit or explicit deadline.",
)

SHOW_OF_FORCE = Action(
    name="Show of Force",
    action_type=ActionType.COMPETITIVE,
    description="Demonstrate capability and resolve through visible action.",
)

DEMAND = Action(
    name="Demand",
    action_type=ActionType.COMPETITIVE,
    description="Make explicit demands for opponent concessions.",
)

ADVANCE = Action(
    name="Advance",
    action_type=ActionType.COMPETITIVE,
    description="Push forward into contested space or escalate commitment.",
)


# =============================================================================
# Special Actions (from GAME_MANUAL.md Section 3.6)
# =============================================================================

RECONNAISSANCE = Action(
    name="Initiate Reconnaissance",
    action_type=ActionType.COOPERATIVE,  # Classified as cooperative (information seeking)
    resource_cost=0.5,
    category=ActionCategory.RECONNAISSANCE,
    description="Attempt to learn opponent's exact Position. "
    "Costs 0.5 Resources. Replaces regular matrix game for this turn.",
)

INSPECTION = Action(
    name="Initiate Inspection",
    action_type=ActionType.COOPERATIVE,  # Classified as cooperative (verification seeking)
    resource_cost=0.3,
    category=ActionCategory.INSPECTION,
    description="Attempt to learn opponent's exact Resources. "
    "Costs 0.3 Resources. Replaces regular matrix game for this turn.",
)


def create_costly_signaling_action(position: float) -> Action:
    """Create a Costly Signaling action with cost based on player's Position.

    From GAME_MANUAL.md Section 3.6.3:
    - Position >= 7 (Strong): 0.3 Resources
    - Position 4-6 (Medium): 0.7 Resources
    - Position <= 3 (Weak): 1.2 Resources

    Args:
        position: The player's current Position value (0-10)

    Returns:
        Action with appropriate resource cost for costly signaling
    """
    if position >= 7:
        cost = 0.3
        cost_description = "0.3 (strong position)"
    elif position >= 4:
        cost = 0.7
        cost_description = "0.7 (medium position)"
    else:
        cost = 1.2
        cost_description = "1.2 (weak position)"

    return Action(
        name="Signal Strength",
        action_type=ActionType.COOPERATIVE,  # Revealing information is cooperative
        resource_cost=cost,
        category=ActionCategory.COSTLY_SIGNALING,
        description=f"Credibly reveal your position strength to opponent. "
        f"Costs {cost_description} Resources. Does NOT replace your regular action.",
    )


# =============================================================================
# Action Menus by Risk Level
# =============================================================================

# Collections for building menus
ALL_COOPERATIVE_ACTIONS: list[Action] = [
    DEESCALATE,
    HOLD_MAINTAIN,
    BACK_CHANNEL,
    CONCEDE,
    WITHDRAW,
]

ALL_COMPETITIVE_ACTIONS: list[Action] = [
    ESCALATE,
    AGGRESSIVE_PRESSURE,
    ISSUE_ULTIMATUM,
    SHOW_OF_FORCE,
    DEMAND,
    ADVANCE,
]


class ActionMenu(BaseModel):
    """Available actions for a given game state.

    The action menu varies based on Risk Level tier:
    - Low Risk (1-3): More cooperative options
    - Medium Risk (4-6): Balanced options
    - High Risk (7-9): More confrontational options

    Attributes:
        standard_actions: Regular actions available this turn
        special_actions: Special actions (settlement, recon, etc.)
        risk_level: Current Risk Level
        turn: Current turn number
        can_propose_settlement: Whether settlement is available
    """

    standard_actions: list[Action]
    special_actions: list[Action]
    risk_level: int
    turn: int
    can_propose_settlement: bool

    def all_actions(self) -> list[Action]:
        """Return all available actions (standard + special)."""
        return self.standard_actions + self.special_actions

    def cooperative_actions(self) -> list[Action]:
        """Return only cooperative actions."""
        return [a for a in self.all_actions() if a.action_type == ActionType.COOPERATIVE]

    def competitive_actions(self) -> list[Action]:
        """Return only competitive actions."""
        return [a for a in self.all_actions() if a.action_type == ActionType.COMPETITIVE]


def get_risk_tier(risk_level: int) -> Literal["low", "medium", "high"]:
    """Determine risk tier from risk level.

    Args:
        risk_level: Current Risk Level (0-10)

    Returns:
        Risk tier classification
    """
    if risk_level <= 3:
        return "low"
    elif risk_level <= 6:
        return "medium"
    else:
        return "high"


def can_propose_settlement(turn: int, stability: float) -> bool:
    """Check if settlement proposal is available.

    From GAME_MANUAL.md Section 4.4:
    - Available after Turn 4
    - NOT available if Stability <= 2

    Args:
        turn: Current turn number
        stability: Current Stability value

    Returns:
        True if settlement can be proposed
    """
    return turn > 4 and stability > 2


def get_action_menu(
    risk_level: int,
    turn: int,
    stability: float,
    player_position: float,
    player_resources: float,
) -> ActionMenu:
    """Get available actions based on current game state.

    The menu composition follows these principles from ENGINEERING_DESIGN.md:
    - Low Risk (1-3): More cooperative options (4 coop, 2 competitive)
    - Medium Risk (4-6): Balanced options (3 coop, 3 competitive)
    - High Risk (7-9): More confrontational options (2 coop, 4 competitive)

    Args:
        risk_level: Current Risk Level (0-10)
        turn: Current turn number
        stability: Current Stability value
        player_position: Player's Position (for costly signaling cost)
        player_resources: Player's Resources (for affordability check)

    Returns:
        ActionMenu with available actions
    """
    tier = get_risk_tier(risk_level)
    settlement_available = can_propose_settlement(turn, stability)

    # Build standard action menu based on risk tier
    if tier == "low":
        # More cooperative: 4 cooperative, 2 competitive
        standard_actions = [
            DEESCALATE,
            HOLD_MAINTAIN,
            BACK_CHANNEL,
            WITHDRAW,
            ESCALATE,
            AGGRESSIVE_PRESSURE,
        ]
    elif tier == "medium":
        # Balanced: 3 cooperative, 3 competitive
        standard_actions = [
            DEESCALATE,
            HOLD_MAINTAIN,
            BACK_CHANNEL,
            ESCALATE,
            AGGRESSIVE_PRESSURE,
            SHOW_OF_FORCE,
        ]
    else:  # high
        # More confrontational: 2 cooperative, 4 competitive
        standard_actions = [
            HOLD_MAINTAIN,
            CONCEDE,
            ESCALATE,
            AGGRESSIVE_PRESSURE,
            ISSUE_ULTIMATUM,
            SHOW_OF_FORCE,
        ]

    # Build special actions list
    special_actions: list[Action] = []

    # Settlement (if available)
    if settlement_available:
        special_actions.append(PROPOSE_SETTLEMENT)

    # Reconnaissance (always available if affordable)
    if player_resources >= RECONNAISSANCE.resource_cost:
        special_actions.append(RECONNAISSANCE)

    # Inspection (always available if affordable)
    if player_resources >= INSPECTION.resource_cost:
        special_actions.append(INSPECTION)

    # Costly Signaling (cost depends on position)
    signaling = create_costly_signaling_action(player_position)
    if player_resources >= signaling.resource_cost:
        special_actions.append(signaling)

    return ActionMenu(
        standard_actions=standard_actions,
        special_actions=special_actions,
        risk_level=risk_level,
        turn=turn,
        can_propose_settlement=settlement_available,
    )


# =============================================================================
# Action Validation and Classification Helpers
# =============================================================================


def classify_action(action: Action) -> ActionType:
    """Return the classification of an action.

    This is a simple accessor for action.action_type, provided for
    API consistency.
    """
    return action.action_type


def validate_action_affordability(action: Action, player_resources: float) -> bool:
    """Check if player can afford the action's resource cost.

    Args:
        action: The action to validate
        player_resources: Player's current Resources

    Returns:
        True if player has sufficient resources
    """
    return player_resources >= action.resource_cost


def validate_action_availability(
    action: Action,
    turn: int,
    stability: float,
    player_resources: float,
) -> tuple[bool, Optional[str]]:
    """Validate whether an action can be taken given game state.

    Args:
        action: The action to validate
        turn: Current turn number
        stability: Current Stability value
        player_resources: Player's current Resources

    Returns:
        Tuple of (is_valid, error_message). error_message is None if valid.
    """
    # Check resource affordability
    if not validate_action_affordability(action, player_resources):
        return False, f"Insufficient resources. Need {action.resource_cost}, have {player_resources}"

    # Check settlement availability
    if action.category == ActionCategory.SETTLEMENT:
        if not can_propose_settlement(turn, stability):
            if turn <= 4:
                return False, "Settlement not available until after Turn 4"
            else:
                return False, f"Settlement not available when Stability <= 2 (current: {stability})"

    return True, None


def get_action_by_name(name: str) -> Optional[Action]:
    """Look up a standard action by name (case-insensitive).

    Args:
        name: Action name to look up

    Returns:
        Action if found, None otherwise
    """
    name_lower = name.lower().strip()

    all_standard = ALL_COOPERATIVE_ACTIONS + ALL_COMPETITIVE_ACTIONS + [
        PROPOSE_SETTLEMENT,
        RECONNAISSANCE,
        INSPECTION,
    ]

    for action in all_standard:
        if action.name.lower() == name_lower:
            return action

    return None


def map_action_to_matrix_choice(action: Action) -> Literal["C", "D"]:
    """Map an action to its corresponding matrix choice.

    Cooperative actions -> C (Cooperate)
    Competitive actions -> D (Defect)

    This is the core mapping used in matrix resolution.

    Args:
        action: The action to map

    Returns:
        "C" for Cooperative, "D" for Competitive
    """
    return action.to_matrix_choice()


# =============================================================================
# Action Summary for Display
# =============================================================================


def format_action_for_display(action: Action, index: int) -> str:
    """Format an action for CLI display.

    Args:
        action: The action to format
        index: Display index (for selection)

    Returns:
        Formatted string for display
    """
    type_label = "Cooperative" if action.action_type == ActionType.COOPERATIVE else "Competitive"
    cost_str = f" (costs {action.resource_cost} Resources)" if action.resource_cost > 0 else ""
    special_str = ""

    if action.category == ActionCategory.SETTLEMENT:
        special_str = " [SETTLEMENT - replaces action]"
    elif action.category == ActionCategory.RECONNAISSANCE:
        special_str = " [INFO GAME - replaces turn]"
    elif action.category == ActionCategory.INSPECTION:
        special_str = " [INFO GAME - replaces turn]"
    elif action.category == ActionCategory.COSTLY_SIGNALING:
        special_str = " [SIGNAL - no turn cost]"

    return f"[{index}] {action.name} ({type_label}){cost_str}{special_str}"
