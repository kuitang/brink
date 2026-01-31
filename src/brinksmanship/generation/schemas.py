"""JSON schemas for Brinksmanship scenarios.

This module defines Pydantic models for scenario structure and validation.
Scenarios specify matrix_type + matrix_parameters only; raw payoffs are never stored.
Matrices are constructed at load time, guaranteeing type correctness.

See ENGINEERING_DESIGN.md Milestone 3.1 for design rationale.
See GAME_MANUAL.md Part II for game type specifications.
"""

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from brinksmanship.models.actions import ActionType
from brinksmanship.models.matrices import (
    CONSTRUCTORS,
    MatrixParameters,
    MatrixType,
    PayoffMatrix,
    build_matrix,
)

# Type alias for outcome codes
OutcomeCode = Literal["CC", "CD", "DC", "DD"]

# Valid theme options for scenarios
ThemeType = Literal["default", "cold-war", "renaissance", "byzantine", "corporate"]
VALID_THEMES: list[str] = ["default", "cold-war", "renaissance", "byzantine", "corporate"]


class OutcomeNarratives(BaseModel):
    """Narrative descriptions for each matrix outcome.

    Keys are outcome codes: CC, CD, DC, DD
    These describe what happens narratively for each possible combination
    of player actions.
    """

    model_config = ConfigDict(frozen=True)

    CC: str = Field(description="Both players cooperate")
    CD: str = Field(description="Player A cooperates, Player B defects")
    DC: str = Field(description="Player A defects, Player B cooperates")
    DD: str = Field(description="Both players defect")

    def get_narrative(self, outcome_code: OutcomeCode) -> str:
        """Get the narrative for a specific outcome code."""
        return getattr(self, outcome_code)


class BranchTargets(BaseModel):
    """Branch targets for each matrix outcome.

    Maps outcome codes to turn IDs in the scenario's branch dictionary.
    Optional fields allow for linear progression (no branching) on some outcomes.
    """

    model_config = ConfigDict(frozen=True)

    CC: str | None = Field(default=None, description="Target turn for mutual cooperation")
    CD: str | None = Field(default=None, description="Target turn for A cooperates, B defects")
    DC: str | None = Field(default=None, description="Target turn for A defects, B cooperates")
    DD: str | None = Field(default=None, description="Target turn for mutual defection")

    def get_branch(self, outcome_code: OutcomeCode) -> str | None:
        """Get the branch target for a specific outcome code."""
        return getattr(self, outcome_code)


class TurnAction(BaseModel):
    """A context-specific action available on a particular turn.

    Each turn in a scenario defines its own action menu with narrative descriptions
    that make sense in the context of that turn's situation. This replaces the
    generic action names like "De-escalate" with specific, meaningful choices
    like "Order naval blockade of Cuba".

    The action_id maps to a base action type (escalate, hold, etc.) which
    determines the game mechanics (cooperative vs competitive classification).
    The narrative_description provides the context-specific meaning.

    Example:
        TurnAction(
            action_id="escalate",
            narrative_description="Order naval blockade of Cuba",
            action_type="competitive"
        )
    """

    model_config = ConfigDict(frozen=True)

    action_id: str = Field(
        description="Base action identifier (e.g., 'escalate', 'hold', 'deescalate', "
        "'reconnaissance', 'inspection', 'settlement')"
    )
    narrative_description: str = Field(
        min_length=1,
        max_length=200,
        description="Context-specific description of this action for this turn"
    )
    action_type: ActionType = Field(
        description="Whether this action is cooperative or competitive"
    )
    resource_cost: float = Field(
        default=0.0,
        ge=0.0,
        le=10.0,
        description="Resource cost to take this action"
    )

    def to_matrix_choice(self) -> Literal["C", "D"]:
        """Map action type to matrix game choice."""
        if self.action_type == ActionType.COOPERATIVE:
            return "C"
        return "D"


class TurnDefinition(BaseModel):
    """Definition of a single turn in a scenario.

    Contains the matrix type, parameters, narratives, and branching structure.

    IMPORTANT: This model stores matrix_type + matrix_parameters only.
    Raw payoffs are NEVER stored. Matrices are constructed at load time
    by calling construct_matrix().
    """

    model_config = ConfigDict(extra="forbid")

    # Turn identification
    turn: int = Field(ge=1, le=16, description="Turn number (1-16)")
    act: int = Field(ge=1, le=3, description="Act number (1, 2, or 3)")

    # Narrative content
    narrative_briefing: str = Field(
        min_length=1,
        description="Situation briefing for players"
    )

    # Matrix specification (type + parameters, NOT raw payoffs)
    matrix_type: MatrixType = Field(
        description="Game theory matrix type for this turn"
    )
    matrix_parameters: MatrixParameters = Field(
        default_factory=MatrixParameters,
        description="Parameters for matrix construction",
    )

    # Action menu with context-specific descriptions
    # When provided, these replace the generic actions with narrative meanings
    # that make sense in the context of this turn's situation
    actions: list[TurnAction] = Field(
        default_factory=list,
        max_length=6,
        description="Available actions this turn with context-specific narrative descriptions. "
        "If empty, generic actions based on Risk Level will be used."
    )

    # Outcome narratives
    outcome_narratives: OutcomeNarratives = Field(
        description="Narrative descriptions for each outcome"
    )

    # Branching logic
    branches: BranchTargets = Field(
        default_factory=BranchTargets,
        description="Branch targets for each outcome (optional)",
    )
    default_next: str | None = Field(
        default=None,
        description="Default branch if settlement fails or no specific branch matches",
    )

    # Settlement configuration
    settlement_available: bool = Field(
        default=False,
        description="Whether settlement can be proposed this turn",
    )
    settlement_failed_narrative: str = Field(
        default="Negotiations collapsed. The crisis remains unresolved.",
        description="Narrative for failed settlement",
    )

    # Cached constructed matrix (not serialized, populated at load time)
    _cached_matrix: PayoffMatrix | None = None

    @model_validator(mode="after")
    def validate_act_matches_turn(self) -> "TurnDefinition":
        """Validate that act number is consistent with turn number.

        From GAME_MANUAL.md:
        - Act I: turns 1-4
        - Act II: turns 5-8
        - Act III: turns 9+
        """
        expected_act: int
        if self.turn <= 4:
            expected_act = 1
        elif self.turn <= 8:
            expected_act = 2
        else:
            expected_act = 3

        if self.act != expected_act:
            raise ValueError(
                f"Turn {self.turn} should be in Act {expected_act}, got Act {self.act}. "
                f"Act I: turns 1-4, Act II: turns 5-8, Act III: turns 9+"
            )
        return self

    @model_validator(mode="after")
    def validate_settlement_availability(self) -> "TurnDefinition":
        """Validate settlement configuration.

        From GAME_MANUAL.md Section 4.4:
        Settlement is available after Turn 4 unless Stability <= 2.
        For scenarios, we require turn >= 5 for settlement_available=True.
        """
        if self.settlement_available and self.turn < 5:
            raise ValueError(
                f"Settlement is not available until turn 5 (Act II). "
                f"Turn {self.turn} cannot have settlement_available=True"
            )
        return self

    @model_validator(mode="after")
    def validate_matrix_parameters(self) -> "TurnDefinition":
        """Validate that matrix parameters satisfy the game type's constraints.

        This calls the constructor's validation to ensure ordinal constraints
        are met before the scenario is accepted.
        """
        constructor = CONSTRUCTORS.get(self.matrix_type)
        if constructor is None:
            raise ValueError(f"Unknown matrix type: {self.matrix_type}")

        # Validate parameters against game-type-specific constraints
        constructor.validate_params(self.matrix_parameters)
        return self

    def construct_matrix(self) -> PayoffMatrix:
        """Construct the payoff matrix from type and parameters.

        This is called at load time to build the actual matrix.
        The matrix is guaranteed to satisfy the game type's ordinal
        constraints because the constructor enforces them.

        The result is cached for repeated access.

        Returns:
            PayoffMatrix: The constructed matrix ready for game use.

        Raises:
            ValueError: If parameters violate the game type's constraints.
        """
        if self._cached_matrix is None:
            self._cached_matrix = build_matrix(
                self.matrix_type, self.matrix_parameters
            )
        return self._cached_matrix

    def get_outcome_narrative(self, outcome_code: OutcomeCode) -> str:
        """Get the narrative for a specific outcome.

        Args:
            outcome_code: One of "CC", "CD", "DC", "DD"

        Returns:
            The narrative string for that outcome.
        """
        return self.outcome_narratives.get_narrative(outcome_code)

    def get_next_turn_id(self, outcome_code: OutcomeCode) -> str | None:
        """Get the next turn ID based on outcome.

        First checks specific branch conditions, then falls back to default_next.

        Args:
            outcome_code: One of "CC", "CD", "DC", "DD"

        Returns:
            The turn ID to proceed to, or None if continuing sequentially.
        """
        branch_target = self.branches.get_branch(outcome_code)
        if branch_target is not None:
            return branch_target
        return self.default_next

    def has_scenario_actions(self) -> bool:
        """Check if this turn defines scenario-specific actions.

        Returns:
            True if actions are defined with narrative descriptions.
        """
        return len(self.actions) > 0

    def get_scenario_actions(self) -> list[TurnAction]:
        """Get the scenario-specific actions for this turn.

        Returns:
            List of TurnAction objects with narrative descriptions.
        """
        return list(self.actions)


class Scenario(BaseModel):
    """Complete scenario definition.

    Contains all turns, branches, and metadata for a Brinksmanship scenario.

    IMPORTANT: Scenarios do NOT store raw payoffs - only matrix_type and
    matrix_parameters pairs. Matrices are constructed at load time via
    construct_all_matrices().
    """

    model_config = ConfigDict(extra="forbid")

    # Metadata
    scenario_id: str = Field(
        min_length=1,
        description="Unique identifier for the scenario"
    )
    title: str = Field(
        min_length=1,
        description="Human-readable title"
    )
    setting: str = Field(
        min_length=1,
        description="Theme/setting description"
    )
    theme: ThemeType = Field(
        default="default",
        description="Visual theme for the scenario UI"
    )

    # Game length (hidden from players during play)
    max_turns: int = Field(
        ge=12, le=16,
        description="Maximum turn count (hidden from players)"
    )

    # Main turn sequence
    turns: list[TurnDefinition] = Field(
        min_length=1,
        description="Initial turn sequence (before branching)"
    )

    # Branch definitions (keyed by branch ID)
    branches: dict[str, TurnDefinition] = Field(
        default_factory=dict,
        description="Branch targets by ID"
    )

    @model_validator(mode="after")
    def validate_turn_sequence(self) -> "Scenario":
        """Validate that main turn sequence is properly ordered."""
        for i, turn in enumerate(self.turns):
            expected_turn = i + 1
            if turn.turn != expected_turn:
                raise ValueError(
                    f"Turn sequence mismatch: expected turn {expected_turn} "
                    f"at index {i}, got turn {turn.turn}"
                )
        return self

    @model_validator(mode="after")
    def validate_branch_targets(self) -> "Scenario":
        """Validate that all branch targets point to valid turn IDs."""
        # Collect all valid turn IDs
        all_turn_ids: set[str] = set()

        # Main sequence turns are referenced as "turn_N"
        for turn in self.turns:
            all_turn_ids.add(f"turn_{turn.turn}")

        # Branch IDs are directly referenced
        for branch_id in self.branches:
            all_turn_ids.add(branch_id)

        # Validate all branch references
        errors: list[str] = []

        for turn in self.turns:
            self._validate_turn_branch_targets(
                turn, f"Turn {turn.turn}", all_turn_ids, errors
            )

        for branch_id, branch_turn in self.branches.items():
            self._validate_turn_branch_targets(
                branch_turn, f"Branch '{branch_id}'", all_turn_ids, errors
            )

        if errors:
            raise ValueError(
                "Invalid branch targets:\n  " + "\n  ".join(errors)
            )

        return self

    def _validate_turn_branch_targets(
        self,
        turn: TurnDefinition,
        turn_name: str,
        valid_ids: set[str],
        errors: list[str],
    ) -> None:
        """Validate branch targets for a single turn definition."""
        # Check specific branch targets
        for outcome in ["CC", "CD", "DC", "DD"]:
            target = turn.branches.get_branch(outcome)  # type: ignore[arg-type]
            if target is not None and target not in valid_ids:
                errors.append(
                    f"{turn_name} {outcome} branch target '{target}' not found. "
                    f"Valid targets: {sorted(valid_ids)}"
                )

        # Check default_next
        if turn.default_next is not None and turn.default_next not in valid_ids:
            errors.append(
                f"{turn_name} default_next '{turn.default_next}' not found. "
                f"Valid targets: {sorted(valid_ids)}"
            )

    @model_validator(mode="after")
    def validate_game_variety(self) -> "Scenario":
        """Validate that scenario uses diverse game types.

        From ENGINEERING_DESIGN.md: Generated scenarios use 8+ distinct matrix types.
        The minimum is scaled based on total turn count for shorter scenarios.
        """
        all_types = self.get_all_matrix_types()
        total_turns = len(self.turns) + len(self.branches)

        # Scale minimum types based on scenario size
        # Full scenarios (12+ turns) need 8 types
        # Smaller scenarios need proportionally fewer
        min_types = min(8, max(3, total_turns // 2))

        if len(all_types) < min_types:
            type_names = sorted(t.value for t in all_types)
            raise ValueError(
                f"Scenario should use at least {min_types} distinct game types "
                f"(has {total_turns} turn definitions), but only uses "
                f"{len(all_types)}: {type_names}"
            )
        return self

    def get_turn(self, turn_id: str | int) -> TurnDefinition | None:
        """Get a turn definition by ID or turn number.

        Args:
            turn_id: Either a branch ID string, "turn_N" format, or turn number

        Returns:
            The TurnDefinition or None if not found.
        """
        if isinstance(turn_id, int):
            # Look up by turn number in main sequence
            for turn in self.turns:
                if turn.turn == turn_id:
                    return turn
            return None
        elif turn_id.startswith("turn_"):
            # Parse "turn_N" format
            turn_num = int(turn_id.split("_")[1])
            return self.get_turn(turn_num)
        else:
            # Look up by branch ID
            return self.branches.get(turn_id)

    def get_all_turns(self) -> list[TurnDefinition]:
        """Get all turns including branches."""
        return self.turns + list(self.branches.values())

    def get_all_matrix_types(self) -> set[MatrixType]:
        """Get all unique matrix types used in the scenario."""
        return {turn.matrix_type for turn in self.get_all_turns()}

    def construct_all_matrices(self) -> dict[str, PayoffMatrix]:
        """Construct all matrices at load time.

        This should be called when loading a scenario to verify all
        matrix parameters are valid and pre-populate the matrix cache.

        Returns:
            Dictionary mapping turn identifiers to constructed matrices.
            Keys are "turn_N" for main sequence or branch IDs for branches.

        Raises:
            ValueError: If any turn's matrix parameters are invalid.
        """
        matrices: dict[str, PayoffMatrix] = {}

        for turn in self.turns:
            matrices[f"turn_{turn.turn}"] = turn.construct_matrix()

        for branch_id, branch_turn in self.branches.items():
            matrices[branch_id] = branch_turn.construct_matrix()

        return matrices

    def to_json(self) -> str:
        """Serialize scenario to JSON string."""
        return self.model_dump_json(indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> "Scenario":
        """Deserialize scenario from JSON string.

        This also validates all matrix parameters and constructs matrices
        to ensure the scenario is playable.

        Args:
            json_str: JSON string representation of scenario

        Returns:
            Validated Scenario object

        Raises:
            ValueError: If JSON is invalid or matrix parameters fail validation
            pydantic.ValidationError: If schema validation fails
        """
        scenario = cls.model_validate_json(json_str)
        # Verify all matrices can be constructed
        scenario.construct_all_matrices()
        return scenario

    def to_dict(self) -> dict:
        """Serialize scenario to dictionary."""
        return self.model_dump(mode="json")

    @classmethod
    def from_dict(cls, data: dict) -> "Scenario":
        """Deserialize scenario from dictionary.

        This also validates all matrix parameters and constructs matrices
        to ensure the scenario is playable.

        Args:
            data: Dictionary representation of scenario

        Returns:
            Validated Scenario object

        Raises:
            ValueError: If data is invalid or matrix parameters fail validation
            pydantic.ValidationError: If schema validation fails
        """
        scenario = cls.model_validate(data)
        # Verify all matrices can be constructed
        scenario.construct_all_matrices()
        return scenario


def load_scenario(scenario_path: str) -> Scenario:
    """Load and validate a scenario from a JSON file.

    Args:
        scenario_path: Path to the scenario JSON file

    Returns:
        Validated Scenario object with all matrices constructed

    Raises:
        FileNotFoundError: If the file doesn't exist
        ValueError: If validation fails
        pydantic.ValidationError: If schema validation fails
    """
    path = Path(scenario_path)
    with path.open() as f:
        data = json.load(f)

    scenario = Scenario.model_validate(data)

    # Construct all matrices to verify validity
    scenario.construct_all_matrices()

    return scenario


def save_scenario(scenario: Scenario, scenario_path: str) -> None:
    """Save a scenario to a JSON file.

    Args:
        scenario: Scenario object to save
        scenario_path: Path to write the JSON file
    """
    path = Path(scenario_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w") as f:
        json.dump(scenario.model_dump(mode="json"), f, indent=2)


# Alias for backward compatibility
ScenarioDefinition = Scenario
