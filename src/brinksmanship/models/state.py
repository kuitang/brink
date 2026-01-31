"""Game state models for Brinksmanship.

This module defines the core state dataclasses used throughout the game engine.
All numeric fields are clamped to valid ranges on assignment.

Key formulas from GAME_MANUAL.md:
- Base_sigma = 8 + (Risk_Level * 1.2)
- Chaos_Factor = 1.2 - (Cooperation_Score / 50)
- Instability_Factor = 1 + (10 - Stability) / 20
- Act_Multiplier: Act I (turns 1-4) = 0.7, Act II (5-8) = 1.0, Act III (9+) = 1.3
"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator, model_validator

from brinksmanship.models.actions import ActionType


def clamp(value: float, min_val: float, max_val: float) -> float:
    """Clamp a value to the specified range."""
    return max(min_val, min(max_val, value))


class InformationState(BaseModel):
    """What one player knows about the other.

    Information is acquired through strategic games, not passive observation.
    Information decays over time as opponent state changes.

    Attributes:
        position_bounds: Hard bounds on opponent position, always [0.0, 10.0]
        resources_bounds: Hard bounds on opponent resources, always [0.0, 10.0]
        known_position: Last known position from successful reconnaissance
        known_position_turn: Turn when position was last learned
        known_resources: Last known resources from successful inspection
        known_resources_turn: Turn when resources were last learned
    """

    position_bounds: tuple[float, float] = Field(default=(0.0, 10.0))
    resources_bounds: tuple[float, float] = Field(default=(0.0, 10.0))
    known_position: float | None = Field(default=None)
    known_position_turn: int | None = Field(default=None)
    known_resources: float | None = Field(default=None)
    known_resources_turn: int | None = Field(default=None)

    def get_position_estimate(self, current_turn: int) -> tuple[float, float]:
        """Get position estimate with uncertainty radius.

        Returns:
            Tuple of (estimate, uncertainty_radius).

        Information decay formula from GAME_MANUAL.md:
            uncertainty = min(turns_since_known * 0.8, 5.0)
        """
        if self.known_position is not None and self.known_position_turn is not None:
            turns_elapsed = current_turn - self.known_position_turn
            uncertainty = min(turns_elapsed * 0.8, 5.0)
            return self.known_position, uncertainty
        else:
            midpoint = sum(self.position_bounds) / 2
            radius = (self.position_bounds[1] - self.position_bounds[0]) / 2
            return midpoint, radius

    def get_resources_estimate(self, current_turn: int) -> tuple[float, float]:
        """Get resources estimate with uncertainty radius.

        Returns:
            Tuple of (estimate, uncertainty_radius).
        """
        if self.known_resources is not None and self.known_resources_turn is not None:
            turns_elapsed = current_turn - self.known_resources_turn
            uncertainty = min(turns_elapsed * 0.8, 5.0)
            return self.known_resources, uncertainty
        else:
            midpoint = sum(self.resources_bounds) / 2
            radius = (self.resources_bounds[1] - self.resources_bounds[0]) / 2
            return midpoint, radius

    def update_position(self, position: float, turn: int) -> None:
        """Update known position from successful reconnaissance."""
        self.known_position = position
        self.known_position_turn = turn

    def update_resources(self, resources: float, turn: int) -> None:
        """Update known resources from successful inspection."""
        self.known_resources = resources
        self.known_resources_turn = turn


class PlayerState(BaseModel):
    """Per-player state in the game.

    Attributes:
        position: Player's relative power/advantage (0-10, starts at 5)
        resources: Player's reserves - political capital, treasury (0-10, starts at 5)
        previous_type: Player's last action classification (None on turn 1)
        information: What this player knows about their opponent
    """

    position: float = Field(default=5.0, ge=0.0, le=10.0)
    resources: float = Field(default=5.0, ge=0.0, le=10.0)
    previous_type: ActionType | None = Field(default=None)
    information: InformationState = Field(default_factory=InformationState)

    @field_validator("position", "resources", mode="before")
    @classmethod
    def clamp_to_range(cls, v: float) -> float:
        """Clamp numeric fields to valid range [0, 10]."""
        return clamp(float(v), 0.0, 10.0)


class GameState(BaseModel):
    """Complete game state.

    Contains all state variables tracked during a game of Brinksmanship.

    Shared state variables:
        cooperation_score: Overall relationship trajectory (0-10, starts at 5)
        stability: Predictability of both players' behavior (1-10, starts at 5)
        risk_level: Position on escalation ladder (0-10, starts at 2)
        turn: Current turn number (starts at 1)
        max_turns: Maximum number of turns (12-16, hidden from players)

    Per-player state:
        player_a: State for player A
        player_b: State for player B
    """

    # Per-player state
    player_a: PlayerState = Field(default_factory=PlayerState)
    player_b: PlayerState = Field(default_factory=PlayerState)

    # Shared state
    cooperation_score: float = Field(default=5.0, ge=0.0, le=10.0)
    stability: float = Field(default=5.0, ge=1.0, le=10.0)
    risk_level: float = Field(default=2.0, ge=0.0, le=10.0)
    turn: int = Field(default=1, ge=1)
    max_turns: int = Field(default=14, ge=12, le=16)

    # Surplus mechanics (Joint Investment model)
    cooperation_surplus: float = Field(default=0.0, ge=0.0)  # Shared pool created by CC
    surplus_captured_a: float = Field(default=0.0, ge=0.0)  # VP locked by player A
    surplus_captured_b: float = Field(default=0.0, ge=0.0)  # VP locked by player B
    cooperation_streak: int = Field(default=0, ge=0)  # Consecutive CC outcomes

    @field_validator("cooperation_score", mode="before")
    @classmethod
    def clamp_cooperation(cls, v: float) -> float:
        """Clamp cooperation score to [0, 10]."""
        return clamp(float(v), 0.0, 10.0)

    @field_validator("stability", mode="before")
    @classmethod
    def clamp_stability(cls, v: float) -> float:
        """Clamp stability to [1, 10]."""
        return clamp(float(v), 1.0, 10.0)

    @field_validator("risk_level", mode="before")
    @classmethod
    def clamp_risk(cls, v: float) -> float:
        """Clamp risk level to [0, 10]."""
        return clamp(float(v), 0.0, 10.0)

    @field_validator("max_turns", mode="before")
    @classmethod
    def clamp_max_turns(cls, v: int) -> int:
        """Clamp max turns to [12, 16]."""
        return max(12, min(16, int(v)))

    # Convenience properties for backward compatibility
    @property
    def position_a(self) -> float:
        """Player A's position."""
        return self.player_a.position

    @position_a.setter
    def position_a(self, value: float) -> None:
        self.player_a.position = clamp(float(value), 0.0, 10.0)

    @property
    def position_b(self) -> float:
        """Player B's position."""
        return self.player_b.position

    @position_b.setter
    def position_b(self, value: float) -> None:
        self.player_b.position = clamp(float(value), 0.0, 10.0)

    @property
    def resources_a(self) -> float:
        """Player A's resources."""
        return self.player_a.resources

    @resources_a.setter
    def resources_a(self, value: float) -> None:
        self.player_a.resources = clamp(float(value), 0.0, 10.0)

    @property
    def resources_b(self) -> float:
        """Player B's resources."""
        return self.player_b.resources

    @resources_b.setter
    def resources_b(self, value: float) -> None:
        self.player_b.resources = clamp(float(value), 0.0, 10.0)

    @property
    def previous_type_a(self) -> ActionType | None:
        """Player A's previous action type."""
        return self.player_a.previous_type

    @previous_type_a.setter
    def previous_type_a(self, value: ActionType | None) -> None:
        self.player_a.previous_type = value

    @property
    def previous_type_b(self) -> ActionType | None:
        """Player B's previous action type."""
        return self.player_b.previous_type

    @previous_type_b.setter
    def previous_type_b(self, value: ActionType | None) -> None:
        self.player_b.previous_type = value

    # Computed properties for variance calculation
    @property
    def act(self) -> int:
        """Current act based on turn number.

        Act I: turns 1-4
        Act II: turns 5-8
        Act III: turns 9+
        """
        if self.turn <= 4:
            return 1
        elif self.turn <= 8:
            return 2
        else:
            return 3

    @property
    def act_multiplier(self) -> float:
        """Act multiplier for state deltas and variance.

        From GAME_MANUAL.md:
        - Act I (turns 1-4): 0.7
        - Act II (turns 5-8): 1.0
        - Act III (turns 9+): 1.3
        """
        multipliers = {1: 0.7, 2: 1.0, 3: 1.3}
        return multipliers[self.act]

    @property
    def base_sigma(self) -> float:
        """Base sigma from risk level.

        Formula from GAME_MANUAL.md:
            Base_sigma = 8 + (Risk_Level * 1.2)

        Range: 8 (risk=0) to 20 (risk=10)
        """
        return 8.0 + (self.risk_level * 1.2)

    @property
    def chaos_factor(self) -> float:
        """Chaos factor from cooperation score.

        Formula from GAME_MANUAL.md:
            Chaos_Factor = 1.2 - (Cooperation_Score / 50)

        Range: 1.0 (coop=10) to 1.2 (coop=0)
        """
        return 1.2 - (self.cooperation_score / 50.0)

    @property
    def instability_factor(self) -> float:
        """Instability factor from stability.

        Formula from GAME_MANUAL.md:
            Instability_Factor = 1 + (10 - Stability) / 20

        Range: 1.0 (stability=10) to 1.45 (stability=1)
        """
        return 1.0 + (10.0 - self.stability) / 20.0

    @property
    def shared_sigma(self) -> float:
        """Shared variance (sigma) for final resolution.

        Formula from GAME_MANUAL.md:
            Shared_sigma = Base_sigma * Chaos_Factor * Instability_Factor * Act_Multiplier

        Expected range: ~10 (peaceful early) to ~37 (chaotic crisis)
        """
        return self.base_sigma * self.chaos_factor * self.instability_factor * self.act_multiplier

    # Surplus convenience properties
    @property
    def total_surplus_captured(self) -> float:
        """Total surplus captured by both players."""
        return self.surplus_captured_a + self.surplus_captured_b

    @property
    def surplus_remaining(self) -> float:
        """Surplus still in the shared pool (not yet captured or distributed)."""
        return self.cooperation_surplus

    # Serialization methods
    def to_json(self) -> str:
        """Serialize state to JSON string."""
        return self.model_dump_json(indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> GameState:
        """Deserialize state from JSON string."""
        return cls.model_validate_json(json_str)

    def to_dict(self) -> dict:
        """Serialize state to dictionary."""
        return self.model_dump()

    @classmethod
    def from_dict(cls, data: dict) -> GameState:
        """Deserialize state from dictionary."""
        return cls.model_validate(data)


class ActionResult(BaseModel):
    """Result of resolving a turn's actions.

    Captures all changes that occurred during a turn resolution.

    Attributes:
        action_a: The action type player A took
        action_b: The action type player B took
        position_delta_a: Change to player A's position
        position_delta_b: Change to player B's position
        resource_cost_a: Resources expended by player A
        resource_cost_b: Resources expended by player B
        risk_delta: Change to shared risk level
        cooperation_delta: Change to shared cooperation score
        stability_delta: Change to shared stability
        outcome_code: The outcome code (e.g., "CC", "CD", "DC", "DD")
        narrative: Narrative description of the outcome
    """

    action_a: ActionType
    action_b: ActionType
    position_delta_a: float = Field(default=0.0)
    position_delta_b: float = Field(default=0.0)
    resource_cost_a: float = Field(default=0.0, ge=0.0)
    resource_cost_b: float = Field(default=0.0, ge=0.0)
    risk_delta: float = Field(default=0.0)
    cooperation_delta: float = Field(default=0.0)
    stability_delta: float = Field(default=0.0)
    outcome_code: str = Field(default="")
    narrative: str = Field(default="")

    @model_validator(mode="after")
    def compute_outcome_code(self) -> ActionResult:
        """Compute outcome code from action types if not provided."""
        if not self.outcome_code:
            a_code = "C" if self.action_a == ActionType.COOPERATIVE else "D"
            b_code = "C" if self.action_b == ActionType.COOPERATIVE else "D"
            self.outcome_code = f"{a_code}{b_code}"
        return self

    @property
    def is_mutual_cooperation(self) -> bool:
        """Both players cooperated."""
        return self.action_a == ActionType.COOPERATIVE and self.action_b == ActionType.COOPERATIVE

    @property
    def is_mutual_defection(self) -> bool:
        """Both players competed/defected."""
        return self.action_a == ActionType.COMPETITIVE and self.action_b == ActionType.COMPETITIVE

    @property
    def is_mixed(self) -> bool:
        """One player cooperated, one competed."""
        return not self.is_mutual_cooperation and not self.is_mutual_defection


def update_cooperation_score(state: GameState, result: ActionResult) -> float:
    """Calculate new cooperation score after a turn.

    From GAME_MANUAL.md:
        CC (both cooperative): +1
        DD (both competitive): -1
        CD or DC (mixed): no change

    Args:
        state: Current game state
        result: Result of the turn's actions

    Returns:
        New cooperation score (clamped to [0, 10])
    """
    if result.is_mutual_cooperation:
        delta = 1.0
    elif result.is_mutual_defection:
        delta = -1.0
    else:
        delta = 0.0

    return clamp(state.cooperation_score + delta, 0.0, 10.0)


def update_stability(state: GameState, result: ActionResult) -> float:
    """Calculate new stability after a turn.

    From GAME_MANUAL.md (decay-based formula):
        # Decay toward neutral (5)
        stability = stability * 0.8 + 1.0

        # Apply consistency bonus or switch penalty
        if switches == 0:
            stability += 1.5
        elif switches == 1:
            stability -= 3.5
        else:  # switches == 2
            stability -= 5.5

        stability = clamp(stability, 1, 10)

    Args:
        state: Current game state
        result: Result of the turn's actions

    Returns:
        New stability (clamped to [1, 10])
    """
    # Count switches
    switches = 0
    if state.previous_type_a is not None and result.action_a != state.previous_type_a:
        switches += 1
    if state.previous_type_b is not None and result.action_b != state.previous_type_b:
        switches += 1

    # Turn 1 has no previous actions, so no switches possible
    # But stability update still applies the decay formula

    # Decay toward neutral (5)
    new_stability = state.stability * 0.8 + 1.0

    # Apply consistency bonus or switch penalty
    if switches == 0:
        new_stability += 1.5
    elif switches == 1:
        new_stability -= 3.5
    else:  # switches == 2
        new_stability -= 5.5

    return clamp(new_stability, 1.0, 10.0)


def apply_action_result(state: GameState, result: ActionResult) -> GameState:
    """Apply an action result to produce a new game state.

    This function creates a new GameState with all the changes from the
    action result applied, including:
    - Position changes (scaled by act multiplier)
    - Resource costs
    - Risk level changes (scaled by act multiplier)
    - Cooperation score update
    - Stability update
    - Previous action type update
    - Turn increment

    Args:
        state: Current game state
        result: Result to apply

    Returns:
        New game state with all changes applied
    """
    act_mult = state.act_multiplier

    # Calculate new values
    new_position_a = clamp(state.position_a + (result.position_delta_a * act_mult), 0.0, 10.0)
    new_position_b = clamp(state.position_b + (result.position_delta_b * act_mult), 0.0, 10.0)
    new_resources_a = clamp(state.resources_a - result.resource_cost_a, 0.0, 10.0)
    new_resources_b = clamp(state.resources_b - result.resource_cost_b, 0.0, 10.0)
    new_risk = clamp(state.risk_level + (result.risk_delta * act_mult), 0.0, 10.0)

    # Calculate cooperation and stability updates
    new_cooperation = update_cooperation_score(state, result)
    new_stability = update_stability(state, result)

    # Create new state
    return GameState(
        player_a=PlayerState(
            position=new_position_a,
            resources=new_resources_a,
            previous_type=result.action_a,
            information=state.player_a.information.model_copy(deep=True),
        ),
        player_b=PlayerState(
            position=new_position_b,
            resources=new_resources_b,
            previous_type=result.action_b,
            information=state.player_b.information.model_copy(deep=True),
        ),
        cooperation_score=new_cooperation,
        stability=new_stability,
        risk_level=new_risk,
        turn=state.turn + 1,
        max_turns=state.max_turns,
        # Preserve surplus fields (actual mechanics implemented in T04)
        cooperation_surplus=state.cooperation_surplus,
        surplus_captured_a=state.surplus_captured_a,
        surplus_captured_b=state.surplus_captured_b,
        cooperation_streak=state.cooperation_streak,
    )
