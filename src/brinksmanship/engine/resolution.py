"""Resolution system for Brinksmanship game mechanics.

This module implements the core resolution mechanics for:
- Matrix game resolution (simultaneous actions)
- Reconnaissance game (Matching Pennies variant for position intelligence)
- Inspection game (resource intelligence)
- Settlement negotiation

See GAME_MANUAL.md Sections 3.5, 3.6, and 4.4 for authoritative rules.
See ENGINEERING_DESIGN.md Milestone 2.2 for implementation specifications.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field

from brinksmanship.models.actions import Action, ActionType, map_action_to_matrix_choice
from brinksmanship.models.matrices import (
    MatrixType,
    PayoffMatrix,
    StateDeltas,
)
from brinksmanship.models.state import (
    ActionResult,
    GameState,
    clamp,
)


# =============================================================================
# Matrix Choice Enum
# =============================================================================


class MatrixChoice(str, Enum):
    """Matrix game choice: Cooperate or Defect.

    Maps to the standard 2x2 game theory notation.
    Cooperative actions -> C, Competitive actions -> D
    """

    C = "C"  # Cooperate / First strategy
    D = "D"  # Defect / Second strategy

    @classmethod
    def from_action(cls, action: Action) -> MatrixChoice:
        """Convert an Action to a MatrixChoice.

        Cooperative actions map to C (Cooperate).
        Competitive actions map to D (Defect).
        """
        choice_str = map_action_to_matrix_choice(action)
        return cls(choice_str)


# =============================================================================
# Reconnaissance Game Types (GAME_MANUAL.md Section 3.6.1)
# =============================================================================


class ReconnaissanceChoice(str, Enum):
    """Player choices in the Reconnaissance game.

    Probe: Attempt to gather intelligence on opponent's position.
    Mask: Attempt to hide your own position/intentions.
    """

    PROBE = "probe"
    MASK = "mask"


class ReconnaissanceOpponentChoice(str, Enum):
    """Opponent choices in the Reconnaissance game.

    Vigilant: Active counterintelligence, watching for probes.
    Project: Projecting a false image/disinformation.
    """

    VIGILANT = "vigilant"
    PROJECT = "project"


@dataclass(frozen=True)
class ReconnaissanceResult:
    """Result of a Reconnaissance game resolution.

    Attributes:
        outcome: The outcome category (detected, success, stalemate, exposed)
        player_learns_position: True if player learns opponent's exact position
        opponent_learns_position: True if opponent learns player's exact position
        risk_delta: Change to shared risk level
        player_detected: True if opponent knows player attempted recon
        narrative: Description of what happened
    """

    outcome: Literal["detected", "success", "stalemate", "exposed"]
    player_learns_position: bool
    opponent_learns_position: bool
    risk_delta: float
    player_detected: bool
    narrative: str


# =============================================================================
# Inspection Game Types (GAME_MANUAL.md Section 3.6.2)
# =============================================================================


class InspectionChoice(str, Enum):
    """Player choices in the Inspection game.

    Inspect: Actively verify opponent's claims/resources.
    Trust: Accept opponent's claims without verification.
    """

    INSPECT = "inspect"
    TRUST = "trust"


class InspectionOpponentChoice(str, Enum):
    """Opponent choices in the Inspection game.

    Comply: Honestly reveal true resource state.
    Cheat: Attempt to hide or misrepresent resources.
    """

    COMPLY = "comply"
    CHEAT = "cheat"


@dataclass(frozen=True)
class InspectionResult:
    """Result of an Inspection game resolution.

    Attributes:
        outcome: The outcome category (verified, caught, nothing, exploited)
        player_learns_resources: True if player learns opponent's exact resources
        opponent_risk_penalty: Risk penalty applied to opponent (if caught cheating)
        opponent_position_delta: Position change for opponent (if caught/exploited)
        player_position_delta: Position change for player (if exploited)
        narrative: Description of what happened
    """

    outcome: Literal["verified", "caught", "nothing", "exploited"]
    player_learns_resources: bool
    opponent_risk_penalty: float
    opponent_position_delta: float
    player_position_delta: float
    narrative: str


# =============================================================================
# Settlement Types (GAME_MANUAL.md Section 4.4)
# =============================================================================


class SettlementProposal(BaseModel):
    """A settlement proposal with numeric offer and argument.

    From GAME_MANUAL.md Section 4.4.1:
    - Numeric Offer: VP split proposed
    - Argument Text: Free-form rationale (max 500 characters)
    """

    offered_vp: int = Field(..., ge=0, le=100, description="VP proposed for the proposer (0-100)")
    argument: str = Field(..., max_length=500, description="Free-text rationale for the offer")


class SettlementAction(str, Enum):
    """Possible responses to a settlement proposal."""

    ACCEPT = "accept"
    COUNTER = "counter"
    REJECT = "reject"


class SettlementResponse(BaseModel):
    """Response to a settlement proposal.

    From GAME_MANUAL.md Section 4.4.3:
    - Accept: Game ends at proposed VP split
    - Counter: Propose alternative VP split (one counteroffer allowed)
    - Reject: Game continues, Risk +1
    """

    action: SettlementAction
    counter_vp: int | None = Field(
        default=None, ge=0, le=100, description="Counterproposal VP (if countering)"
    )
    counter_argument: str | None = Field(
        default=None, max_length=500, description="Counter-argument (if countering)"
    )
    rejection_reason: str | None = Field(
        default=None, max_length=500, description="Explanation for rejection"
    )


@dataclass(frozen=True)
class SettlementConstraints:
    """Constraints on valid settlement offers for a player.

    From GAME_MANUAL.md Section 4.4.2:
    Position_Difference = Your_Position - Opponent_Position
    Cooperation_Bonus = (Cooperation_Score - 5) * 2
    Your_Suggested_VP = 50 + (Position_Difference * 5) + Cooperation_Bonus
    Your_Min_Offer = max(20, Your_Suggested_VP - 10)
    Your_Max_Offer = min(80, Your_Suggested_VP + 10)
    """

    min_vp: int
    max_vp: int
    suggested_vp: int


# =============================================================================
# Matrix Game Resolution
# =============================================================================


def resolve_matrix_game(
    state: GameState,
    action_a: Action,
    action_b: Action,
    matrix: PayoffMatrix,
) -> ActionResult:
    """Resolve a matrix game given both players' actions.

    This is the core resolution function for simultaneous actions.
    Both players' actions are mapped to matrix choices (C or D),
    then the appropriate outcome cell is looked up.

    Args:
        state: Current game state (for context, not modified)
        action_a: Player A's action
        action_b: Player B's action
        matrix: The PayoffMatrix for this turn

    Returns:
        ActionResult containing all state deltas and outcome information
    """
    # Map actions to matrix choices
    choice_a = MatrixChoice.from_action(action_a)
    choice_b = MatrixChoice.from_action(action_b)

    # Convert choices to row/col indices (C=0, D=1)
    row_idx = 0 if choice_a == MatrixChoice.C else 1
    col_idx = 0 if choice_b == MatrixChoice.C else 1

    # Look up outcome in matrix
    outcome = matrix.get_outcome(row_idx, col_idx)
    deltas = outcome.deltas

    # Build outcome code
    outcome_code = f"{choice_a.value}{choice_b.value}"

    # Calculate resource costs (from actions, not matrix)
    resource_cost_a = action_a.resource_cost
    resource_cost_b = action_b.resource_cost

    # Return result with deltas (act scaling applied later by apply_state_deltas)
    return ActionResult(
        action_a=action_a.action_type,
        action_b=action_b.action_type,
        position_delta_a=deltas.pos_a,
        position_delta_b=deltas.pos_b,
        resource_cost_a=resource_cost_a + deltas.res_cost_a,
        resource_cost_b=resource_cost_b + deltas.res_cost_b,
        risk_delta=deltas.risk_delta,
        cooperation_delta=_calculate_cooperation_delta(choice_a, choice_b),
        stability_delta=0.0,  # Calculated separately by update_stability
        outcome_code=outcome_code,
        narrative="",  # Narrative is provided by scenario
    )


def _calculate_cooperation_delta(choice_a: MatrixChoice, choice_b: MatrixChoice) -> float:
    """Calculate cooperation score change from outcome.

    From GAME_MANUAL.md Section 3.3:
    - CC (both cooperative): +1
    - DD (both competitive): -1
    - CD or DC (mixed): no change
    """
    if choice_a == MatrixChoice.C and choice_b == MatrixChoice.C:
        return 1.0
    elif choice_a == MatrixChoice.D and choice_b == MatrixChoice.D:
        return -1.0
    else:
        return 0.0


# =============================================================================
# Reconnaissance Game Resolution (GAME_MANUAL.md Section 3.6.1)
# =============================================================================


def resolve_reconnaissance(
    state: GameState,
    player_choice: ReconnaissanceChoice,
    opponent_choice: ReconnaissanceOpponentChoice,
) -> ReconnaissanceResult:
    """Resolve a Reconnaissance game (Matching Pennies variant).

    From GAME_MANUAL.md Section 3.6.1:

    | Player\\Opponent | Vigilant        | Project         |
    |------------------|-----------------|-----------------|
    | Probe            | Detected        | Success         |
    | Mask             | Stalemate       | Exposed         |

    Outcomes:
    - Detected (Probe + Vigilant): No info, opponent knows you tried, Risk +0.5
    - Success (Probe + Project): Learn opponent's exact Position
    - Stalemate (Mask + Vigilant): Nothing happens
    - Exposed (Mask + Project): Opponent learns YOUR exact Position

    Args:
        state: Current game state (for context)
        player_choice: The initiating player's choice
        opponent_choice: The opponent's choice

    Returns:
        ReconnaissanceResult with outcome details
    """
    if player_choice == ReconnaissanceChoice.PROBE:
        if opponent_choice == ReconnaissanceOpponentChoice.VIGILANT:
            # Detected: Player found nothing, opponent knows about attempt
            return ReconnaissanceResult(
                outcome="detected",
                player_learns_position=False,
                opponent_learns_position=False,
                risk_delta=0.5,
                player_detected=True,
                narrative="Your reconnaissance attempt was detected by vigilant counterintelligence. "
                "No intelligence gathered, and tensions have risen.",
            )
        else:  # PROJECT
            # Success: Player learns opponent's position
            return ReconnaissanceResult(
                outcome="success",
                player_learns_position=True,
                opponent_learns_position=False,
                risk_delta=0.0,
                player_detected=False,
                narrative="Your reconnaissance succeeded. You have learned your opponent's "
                "exact strategic position.",
            )
    else:  # MASK
        if opponent_choice == ReconnaissanceOpponentChoice.VIGILANT:
            # Stalemate: Nothing happens
            return ReconnaissanceResult(
                outcome="stalemate",
                player_learns_position=False,
                opponent_learns_position=False,
                risk_delta=0.0,
                player_detected=False,
                narrative="Both sides maintained operational security. "
                "No intelligence was exchanged.",
            )
        else:  # PROJECT
            # Exposed: Opponent learns player's position
            return ReconnaissanceResult(
                outcome="exposed",
                player_learns_position=False,
                opponent_learns_position=True,
                risk_delta=0.0,
                player_detected=False,
                narrative="While you were masking your activities, your opponent's projection "
                "operation revealed your true position to them.",
            )


# =============================================================================
# Inspection Game Resolution (GAME_MANUAL.md Section 3.6.2)
# =============================================================================


def resolve_inspection(
    state: GameState,
    player_choice: InspectionChoice,
    opponent_choice: InspectionOpponentChoice,
) -> InspectionResult:
    """Resolve an Inspection game.

    From GAME_MANUAL.md Section 3.6.2:

    | Player\\Opponent | Comply          | Cheat           |
    |------------------|-----------------|-----------------|
    | Inspect          | Verified        | Caught          |
    | Trust            | Nothing         | Exploited       |

    Outcomes:
    - Verified (Inspect + Comply): Learn opponent's exact Resources
    - Caught (Inspect + Cheat): Learn opponent's Resources, opponent Risk +1, Position -0.5
    - Nothing (Trust + Comply): No effect
    - Exploited (Trust + Cheat): Opponent Position +0.5

    Args:
        state: Current game state (for context)
        player_choice: The initiating player's choice
        opponent_choice: The opponent's choice

    Returns:
        InspectionResult with outcome details
    """
    if player_choice == InspectionChoice.INSPECT:
        if opponent_choice == InspectionOpponentChoice.COMPLY:
            # Verified: Player learns opponent's resources
            return InspectionResult(
                outcome="verified",
                player_learns_resources=True,
                opponent_risk_penalty=0.0,
                opponent_position_delta=0.0,
                player_position_delta=0.0,
                narrative="Your inspection was successful. Your opponent complied fully, "
                "and you have verified their exact resource levels.",
            )
        else:  # CHEAT
            # Caught: Player learns resources AND opponent is penalized
            return InspectionResult(
                outcome="caught",
                player_learns_resources=True,
                opponent_risk_penalty=1.0,
                opponent_position_delta=-0.5,
                player_position_delta=0.0,
                narrative="Your inspection caught your opponent attempting to deceive you! "
                "You have learned their true resources, and their credibility is damaged.",
            )
    else:  # TRUST
        if opponent_choice == InspectionOpponentChoice.COMPLY:
            # Nothing: No effect
            return InspectionResult(
                outcome="nothing",
                player_learns_resources=False,
                opponent_risk_penalty=0.0,
                opponent_position_delta=0.0,
                player_position_delta=0.0,
                narrative="You chose to trust your opponent's representations. "
                "They were honest, but you have no verified intelligence.",
            )
        else:  # CHEAT
            # Exploited: Opponent gains advantage
            return InspectionResult(
                outcome="exploited",
                player_learns_resources=False,
                opponent_risk_penalty=0.0,
                opponent_position_delta=0.5,
                player_position_delta=0.0,
                narrative="Your trust was misplaced. Your opponent successfully misrepresented "
                "their position and has gained a strategic advantage.",
            )


# =============================================================================
# Settlement Constraints (GAME_MANUAL.md Section 4.4.2)
# =============================================================================


def calculate_settlement_constraints(
    state: GameState,
    proposer: Literal["A", "B"],
) -> SettlementConstraints:
    """Calculate valid VP range for a settlement proposal.

    From GAME_MANUAL.md Section 4.4.2:
    Position_Difference = Your_Position - Opponent_Position
    Cooperation_Bonus = (Cooperation_Score - 5) * 2
    Your_Suggested_VP = 50 + (Position_Difference * 5) + Cooperation_Bonus
    Your_Min_Offer = max(20, Your_Suggested_VP - 10)
    Your_Max_Offer = min(80, Your_Suggested_VP + 10)

    Args:
        state: Current game state
        proposer: Which player is proposing ("A" or "B")

    Returns:
        SettlementConstraints with min, max, and suggested VP values
    """
    if proposer == "A":
        your_position = state.position_a
        opponent_position = state.position_b
    else:
        your_position = state.position_b
        opponent_position = state.position_a

    position_difference = your_position - opponent_position
    cooperation_bonus = (state.cooperation_score - 5) * 2

    suggested_vp = int(50 + (position_difference * 5) + cooperation_bonus)

    # Clamp suggested to valid range
    suggested_vp = max(20, min(80, suggested_vp))

    min_vp = max(20, suggested_vp - 10)
    max_vp = min(80, suggested_vp + 10)

    return SettlementConstraints(
        min_vp=min_vp,
        max_vp=max_vp,
        suggested_vp=suggested_vp,
    )


def validate_settlement_proposal(
    proposal: SettlementProposal,
    state: GameState,
    proposer: Literal["A", "B"],
) -> tuple[bool, str | None]:
    """Validate a settlement proposal against constraints.

    Args:
        proposal: The settlement proposal to validate
        state: Current game state
        proposer: Which player is proposing

    Returns:
        Tuple of (is_valid, error_message). Error is None if valid.
    """
    constraints = calculate_settlement_constraints(state, proposer)

    if proposal.offered_vp < constraints.min_vp:
        return False, f"Offer too low. Minimum: {constraints.min_vp} VP"

    if proposal.offered_vp > constraints.max_vp:
        return False, f"Offer too high. Maximum: {constraints.max_vp} VP"

    if not proposal.argument.strip():
        return False, "Settlement proposal must include an argument"

    return True, None


# =============================================================================
# State Delta Application
# =============================================================================


def get_act_multiplier(turn: int) -> float:
    """Get the act multiplier for state deltas based on turn number.

    From GAME_MANUAL.md Section 3.5:
    - Act I (turns 1-4): 0.7
    - Act II (turns 5-8): 1.0
    - Act III (turns 9+): 1.3

    Args:
        turn: Current turn number

    Returns:
        Act multiplier for scaling deltas
    """
    if turn <= 4:
        return 0.7
    elif turn <= 8:
        return 1.0
    else:
        return 1.3


def apply_state_deltas(
    state: GameState,
    deltas: StateDeltas,
    act_multiplier: float | None = None,
) -> GameState:
    """Apply state deltas to produce a new game state.

    Deltas are scaled by the act multiplier before application.
    This function creates a new GameState - it does not modify the input.

    Note: This function only applies position, resource, and risk deltas.
    Cooperation score and stability updates should be handled separately
    using update_cooperation_score and update_stability from state.py.

    Args:
        state: Current game state
        deltas: StateDeltas to apply
        act_multiplier: Optional override for act multiplier. If None,
            calculated from state.turn.

    Returns:
        New GameState with deltas applied
    """
    if act_multiplier is None:
        act_multiplier = get_act_multiplier(state.turn)

    # Calculate new values with act scaling
    new_position_a = clamp(
        state.position_a + (deltas.pos_a * act_multiplier),
        0.0,
        10.0,
    )
    new_position_b = clamp(
        state.position_b + (deltas.pos_b * act_multiplier),
        0.0,
        10.0,
    )
    new_resources_a = clamp(
        state.resources_a - deltas.res_cost_a,  # Resource costs are NOT scaled
        0.0,
        10.0,
    )
    new_resources_b = clamp(
        state.resources_b - deltas.res_cost_b,  # Resource costs are NOT scaled
        0.0,
        10.0,
    )
    new_risk = clamp(
        state.risk_level + (deltas.risk_delta * act_multiplier),
        0.0,
        10.0,
    )

    # Create new state with updated values
    # Note: We use model_copy to preserve other fields like information state
    new_player_a = state.player_a.model_copy(
        update={"position": new_position_a, "resources": new_resources_a}
    )
    new_player_b = state.player_b.model_copy(
        update={"position": new_position_b, "resources": new_resources_b}
    )

    return state.model_copy(
        update={
            "player_a": new_player_a,
            "player_b": new_player_b,
            "risk_level": new_risk,
        }
    )


def apply_action_result_deltas(
    state: GameState,
    result: ActionResult,
) -> GameState:
    """Apply ActionResult deltas to a game state.

    This is a convenience function that converts ActionResult deltas
    to a StateDeltas object and applies them.

    Args:
        state: Current game state
        result: ActionResult containing deltas

    Returns:
        New GameState with deltas applied
    """
    deltas = StateDeltas(
        pos_a=result.position_delta_a,
        pos_b=result.position_delta_b,
        res_cost_a=result.resource_cost_a,
        res_cost_b=result.resource_cost_b,
        risk_delta=result.risk_delta,
    )
    return apply_state_deltas(state, deltas)


# =============================================================================
# Helper Functions for Game Engine Integration
# =============================================================================


def resolve_simultaneous_actions(
    state: GameState,
    action_a: Action,
    action_b: Action,
    matrix: PayoffMatrix,
    outcome_narrative: str = "",
) -> tuple[GameState, ActionResult]:
    """Full resolution of simultaneous actions including state update.

    This is the high-level function for resolving a regular matrix game turn.
    It resolves the matrix game and applies all state changes.

    Args:
        state: Current game state
        action_a: Player A's action
        action_b: Player B's action
        matrix: The PayoffMatrix for this turn
        outcome_narrative: Optional narrative to include in result

    Returns:
        Tuple of (new_state, action_result)
    """
    # Resolve the matrix game
    result = resolve_matrix_game(state, action_a, action_b, matrix)

    # Add narrative if provided
    if outcome_narrative:
        result = ActionResult(
            action_a=result.action_a,
            action_b=result.action_b,
            position_delta_a=result.position_delta_a,
            position_delta_b=result.position_delta_b,
            resource_cost_a=result.resource_cost_a,
            resource_cost_b=result.resource_cost_b,
            risk_delta=result.risk_delta,
            cooperation_delta=result.cooperation_delta,
            stability_delta=result.stability_delta,
            outcome_code=result.outcome_code,
            narrative=outcome_narrative,
        )

    # Apply state changes using the existing apply_action_result from state.py
    # This handles act scaling, cooperation, stability, and turn increment
    from brinksmanship.models.state import apply_action_result

    new_state = apply_action_result(state, result)

    return new_state, result


def resolve_reconnaissance_turn(
    state: GameState,
    player: Literal["A", "B"],
    player_choice: ReconnaissanceChoice,
    opponent_choice: ReconnaissanceOpponentChoice,
) -> tuple[GameState, ReconnaissanceResult]:
    """Resolve a full reconnaissance turn including state updates.

    This handles the reconnaissance game resolution and applies all
    state changes including:
    - Information state updates (if position learned)
    - Risk changes (if detected)
    - Resource cost (0.5 for initiator)

    Args:
        state: Current game state
        player: Which player initiated ("A" or "B")
        player_choice: The initiating player's choice
        opponent_choice: The opponent's choice

    Returns:
        Tuple of (new_state, recon_result)
    """
    result = resolve_reconnaissance(state, player_choice, opponent_choice)

    # Start with a copy of the state
    new_player_a = state.player_a.model_copy(deep=True)
    new_player_b = state.player_b.model_copy(deep=True)
    new_risk = state.risk_level

    # Apply resource cost to initiator
    if player == "A":
        new_player_a.resources = clamp(new_player_a.resources - 0.5, 0.0, 10.0)
    else:
        new_player_b.resources = clamp(new_player_b.resources - 0.5, 0.0, 10.0)

    # Apply risk change
    new_risk = clamp(new_risk + result.risk_delta, 0.0, 10.0)

    # Update information states
    if result.player_learns_position:
        # Player learns opponent's position
        if player == "A":
            opponent_position = state.position_b
            new_player_a.information.update_position(opponent_position, state.turn)
        else:
            opponent_position = state.position_a
            new_player_b.information.update_position(opponent_position, state.turn)

    if result.opponent_learns_position:
        # Opponent learns player's position
        if player == "A":
            player_position = state.position_a
            new_player_b.information.update_position(player_position, state.turn)
        else:
            player_position = state.position_b
            new_player_a.information.update_position(player_position, state.turn)

    # Create new state
    new_state = state.model_copy(
        update={
            "player_a": new_player_a,
            "player_b": new_player_b,
            "risk_level": new_risk,
            "turn": state.turn + 1,
        }
    )

    return new_state, result


def resolve_inspection_turn(
    state: GameState,
    player: Literal["A", "B"],
    player_choice: InspectionChoice,
    opponent_choice: InspectionOpponentChoice,
) -> tuple[GameState, InspectionResult]:
    """Resolve a full inspection turn including state updates.

    This handles the inspection game resolution and applies all
    state changes including:
    - Information state updates (if resources learned)
    - Risk changes (if caught)
    - Position changes (if caught or exploited)
    - Resource cost (0.3 for initiator)

    Args:
        state: Current game state
        player: Which player initiated ("A" or "B")
        player_choice: The initiating player's choice
        opponent_choice: The opponent's choice

    Returns:
        Tuple of (new_state, inspection_result)
    """
    result = resolve_inspection(state, player_choice, opponent_choice)

    # Start with a copy of the state
    new_player_a = state.player_a.model_copy(deep=True)
    new_player_b = state.player_b.model_copy(deep=True)
    new_risk = state.risk_level

    # Apply resource cost to initiator
    if player == "A":
        new_player_a.resources = clamp(new_player_a.resources - 0.3, 0.0, 10.0)
    else:
        new_player_b.resources = clamp(new_player_b.resources - 0.3, 0.0, 10.0)

    # Apply risk penalty to opponent (if caught)
    if player == "A":
        new_risk = clamp(new_risk + result.opponent_risk_penalty, 0.0, 10.0)
    else:
        new_risk = clamp(new_risk + result.opponent_risk_penalty, 0.0, 10.0)

    # Apply position changes
    if player == "A":
        # Opponent is B
        new_player_b.position = clamp(
            new_player_b.position + result.opponent_position_delta, 0.0, 10.0
        )
        new_player_a.position = clamp(
            new_player_a.position + result.player_position_delta, 0.0, 10.0
        )
    else:
        # Opponent is A
        new_player_a.position = clamp(
            new_player_a.position + result.opponent_position_delta, 0.0, 10.0
        )
        new_player_b.position = clamp(
            new_player_b.position + result.player_position_delta, 0.0, 10.0
        )

    # Update information states
    if result.player_learns_resources:
        if player == "A":
            opponent_resources = state.resources_b
            new_player_a.information.update_resources(opponent_resources, state.turn)
        else:
            opponent_resources = state.resources_a
            new_player_b.information.update_resources(opponent_resources, state.turn)

    # Create new state
    new_state = state.model_copy(
        update={
            "player_a": new_player_a,
            "player_b": new_player_b,
            "risk_level": new_risk,
            "turn": state.turn + 1,
        }
    )

    return new_state, result


def handle_failed_settlement(state: GameState) -> GameState:
    """Apply state changes for a failed settlement attempt.

    From GAME_MANUAL.md Section 4.4.4:
    - Risk +1
    - Turn is consumed
    - Matrix game is NOT played

    Args:
        state: Current game state

    Returns:
        New game state with risk increased and turn advanced
    """
    new_risk = clamp(state.risk_level + 1.0, 0.0, 10.0)

    return state.model_copy(
        update={
            "risk_level": new_risk,
            "turn": state.turn + 1,
        }
    )


def determine_settlement_roles(
    state: GameState,
) -> tuple[Literal["A", "B"], Literal["A", "B"]]:
    """Determine proposer and recipient roles when both propose settlement.

    From GAME_MANUAL.md Section 4.4.3:
    When both players propose settlement simultaneously:
    - Player with higher Position becomes "Proposer"
    - Player with lower Position becomes "Recipient"
    - Ties: randomly assign roles (we use A as default tiebreaker)

    Args:
        state: Current game state

    Returns:
        Tuple of (proposer, recipient) where each is "A" or "B"
    """
    if state.position_a > state.position_b:
        return ("A", "B")
    elif state.position_b > state.position_a:
        return ("B", "A")
    else:
        # Tie - deterministically use A as proposer for reproducibility
        # In actual gameplay, this could be randomized
        return ("A", "B")
