"""Brinksmanship game models.

This module exports the core data structures for the game.
"""

from .actions import (
    # Standard actions
    ADVANCE,
    AGGRESSIVE_PRESSURE,
    ALL_COMPETITIVE_ACTIONS,
    ALL_COOPERATIVE_ACTIONS,
    BACK_CHANNEL,
    CONCEDE,
    DEESCALATE,
    DEMAND,
    ESCALATE,
    HOLD_MAINTAIN,
    INSPECTION,
    ISSUE_ULTIMATUM,
    PROPOSE_SETTLEMENT,
    RECONNAISSANCE,
    SHOW_OF_FORCE,
    WITHDRAW,
    Action,
    ActionCategory,
    ActionMenu,
    ActionType,
    can_propose_settlement,
    classify_action,
    create_costly_signaling_action,
    format_action_for_display,
    get_action_by_name,
    get_action_menu,
    get_risk_tier,
    map_action_to_matrix_choice,
    validate_action_affordability,
    validate_action_availability,
)
from .state import (
    ActionResult,
    GameState,
    InformationState,
    PlayerState,
    apply_action_result,
    clamp,
    update_cooperation_score,
    update_stability,
)

__all__ = [
    # Enums
    "ActionType",
    "ActionCategory",
    # Action Models
    "Action",
    "ActionMenu",
    # State Models
    "GameState",
    "PlayerState",
    "InformationState",
    "ActionResult",
    # Action Functions
    "can_propose_settlement",
    "classify_action",
    "create_costly_signaling_action",
    "format_action_for_display",
    "get_action_by_name",
    "get_action_menu",
    "get_risk_tier",
    "map_action_to_matrix_choice",
    "validate_action_affordability",
    "validate_action_availability",
    # State Functions
    "apply_action_result",
    "clamp",
    "update_cooperation_score",
    "update_stability",
    # Standard cooperative actions
    "DEESCALATE",
    "HOLD_MAINTAIN",
    "BACK_CHANNEL",
    "CONCEDE",
    "WITHDRAW",
    # Standard competitive actions
    "ESCALATE",
    "AGGRESSIVE_PRESSURE",
    "ISSUE_ULTIMATUM",
    "SHOW_OF_FORCE",
    "DEMAND",
    "ADVANCE",
    # Special actions
    "PROPOSE_SETTLEMENT",
    "RECONNAISSANCE",
    "INSPECTION",
    # Action collections
    "ALL_COOPERATIVE_ACTIONS",
    "ALL_COMPETITIVE_ACTIONS",
]
