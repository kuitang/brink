"""Core game engine for Brinksmanship.

This module implements the GameEngine class, which manages the complete game loop
including the 8-phase turn structure, state updates, information tracking, and
ending condition checks.

Turn Sequence (from GAME_MANUAL.md Section 3.3):
1. BRIEFING - Present narrative, show state
2. DECISION - Collect simultaneous actions
3. RESOLUTION - Resolve via matrix or settlement
4. STATE UPDATE - Update Cooperation Score, Stability
5. CHECK DETERMINISTIC ENDINGS - Risk=10, Position=0, Resources=0
6. CHECK CRISIS TERMINATION - Turn >= 10, Risk > 7
7. CHECK NATURAL ENDING - Turn = Max_Turn
8. ADVANCE - Increment turn
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Literal, Optional

from brinksmanship.models.actions import (
    Action,
    ActionCategory,
    ActionMenu,
    ActionType,
    get_action_menu,
    validate_action_availability,
)
from brinksmanship.models.matrices import (
    MatrixParameters,
    MatrixType,
    PayoffMatrix,
    build_matrix,
    get_default_params_for_type,
)
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

if TYPE_CHECKING:
    from brinksmanship.storage import ScenarioRepository


class TurnPhase(Enum):
    """Current phase within a turn."""

    BRIEFING = "briefing"
    DECISION = "decision"
    RESOLUTION = "resolution"
    STATE_UPDATE = "state_update"
    CHECK_DETERMINISTIC = "check_deterministic"
    CHECK_CRISIS = "check_crisis"
    CHECK_NATURAL = "check_natural"
    ADVANCE = "advance"
    GAME_OVER = "game_over"


class EndingType(Enum):
    """Types of game endings."""

    # Deterministic endings
    MUTUAL_DESTRUCTION = "mutual_destruction"  # Risk = 10
    POSITION_COLLAPSE_A = "position_collapse_a"  # Player A position = 0
    POSITION_COLLAPSE_B = "position_collapse_b"  # Player B position = 0
    RESOURCE_EXHAUSTION_A = "resource_exhaustion_a"  # Player A resources = 0
    RESOURCE_EXHAUSTION_B = "resource_exhaustion_b"  # Player B resources = 0

    # Probabilistic endings
    CRISIS_TERMINATION = "crisis_termination"  # Turn >= 10, Risk > 7, random trigger
    NATURAL_ENDING = "natural_ending"  # Turn = Max_Turn

    # Negotiated ending
    SETTLEMENT = "settlement"  # Both players agreed to settlement


@dataclass
class GameEnding:
    """Result of a completed game.

    Attributes:
        ending_type: How the game ended
        vp_a: Victory points for player A (0-100)
        vp_b: Victory points for player B (0-100)
        turn: Turn on which game ended
        description: Human-readable description of ending

    Note:
        VP normally sum to 100, but mutual destruction is a special case
        where both players receive 20 VP (sum = 40) per GAME_MANUAL.md Section 4.5.
    """

    ending_type: EndingType
    vp_a: float
    vp_b: float
    turn: int
    description: str

    def __post_init__(self) -> None:
        """Validate VP constraints."""
        if not (0 <= self.vp_a <= 100 and 0 <= self.vp_b <= 100):
            raise ValueError(f"VP must be in [0, 100], got A={self.vp_a}, B={self.vp_b}")
        # Mutual destruction is a special case where VP don't sum to 100
        if self.ending_type != EndingType.MUTUAL_DESTRUCTION:
            if abs(self.vp_a + self.vp_b - 100) > 0.01:
                raise ValueError(f"VP must sum to 100, got {self.vp_a + self.vp_b}")


@dataclass
class TurnRecord:
    """Record of a single turn's events.

    Used for history tracking and coaching analysis.

    Attributes:
        turn: Turn number (1-indexed)
        phase: Phase when record was created
        action_a: Action taken by player A (None if not yet submitted)
        action_b: Action taken by player B (None if not yet submitted)
        outcome: Result of action resolution (None if not yet resolved)
        state_before: Game state at start of turn
        state_after: Game state after turn completion (None if not yet completed)
        narrative: Briefing or outcome narrative text
        matrix_type: Game type used this turn (None for special actions)
    """

    turn: int
    phase: TurnPhase
    action_a: Optional[Action] = None
    action_b: Optional[Action] = None
    outcome: Optional[ActionResult] = None
    state_before: Optional[GameState] = None
    state_after: Optional[GameState] = None
    narrative: str = ""
    matrix_type: Optional[MatrixType] = None


@dataclass
class TurnResult:
    """Result of submitting actions for a turn.

    Returned by submit_actions() to provide feedback on turn resolution.

    Attributes:
        success: Whether actions were successfully processed
        action_result: The ActionResult from resolution (None if failed)
        ending: GameEnding if game ended this turn (None if continuing)
        narrative: Outcome narrative text
        error: Error message if success=False
    """

    success: bool
    action_result: Optional[ActionResult] = None
    ending: Optional[GameEnding] = None
    narrative: str = ""
    error: Optional[str] = None


@dataclass
class TurnConfiguration:
    """Configuration for the current turn from the scenario.

    Attributes:
        turn: Turn number
        act: Act number (1, 2, or 3)
        narrative_briefing: Scenario narrative for this turn
        matrix_type: Game type to use for resolution
        matrix_params: Parameters for matrix construction
        action_menu_override: Optional override for available actions
        outcome_narratives: Narrative text for each outcome (CC, CD, DC, DD)
        branches: Next turn mappings based on outcome
        default_next: Default next turn if settlement fails or special action
        settlement_available: Whether settlement can be proposed
        settlement_failed_narrative: Narrative for failed settlement
    """

    turn: int
    act: int
    narrative_briefing: str
    matrix_type: MatrixType
    matrix_params: MatrixParameters
    action_menu_override: Optional[list[str]] = None
    outcome_narratives: Optional[dict[str, str]] = None
    branches: Optional[dict[str, str]] = None
    default_next: Optional[str] = None
    settlement_available: bool = True
    settlement_failed_narrative: str = "Negotiations failed. The crisis continues."


class GameEngine:
    """Core game engine managing the complete game loop.

    The GameEngine handles:
    - Scenario loading and turn configuration
    - 8-phase turn structure
    - State management and updates
    - Information tracking for both players
    - Ending condition checks
    - Turn history for coaching

    Attributes:
        scenario_id: ID of the loaded scenario
        state: Current game state
        phase: Current phase within the turn
        history: Complete turn history
        ending: Game ending (None if game is in progress)
    """

    def __init__(
        self,
        scenario_id: str,
        scenario_repo: ScenarioRepository,
        max_turns: Optional[int] = None,
        random_seed: Optional[int] = None,
    ) -> None:
        """Initialize the game engine with a scenario.

        Args:
            scenario_id: ID of scenario to load
            scenario_repo: Repository for loading scenarios
            max_turns: Override for maximum turns (default: random 12-16)
            random_seed: Seed for random number generation (for reproducibility)

        Raises:
            ValueError: If scenario not found or invalid
        """
        self.scenario_id = scenario_id
        self._scenario_repo = scenario_repo
        self._random = random.Random(random_seed)

        # Load scenario
        scenario = scenario_repo.get_scenario(scenario_id)
        if scenario is None:
            raise ValueError(f"Scenario not found: {scenario_id}")

        self._scenario = scenario
        self._turn_configs: dict[str, TurnConfiguration] = {}
        self._current_turn_key: str = ""

        # Parse scenario structure
        self._parse_scenario(scenario)

        # Initialize game state
        if max_turns is None:
            max_turns = self._random.randint(12, 16)
        self.state = self._create_initial_state(max_turns)

        # Track current phase
        self.phase = TurnPhase.BRIEFING

        # History and ending
        self.history: list[TurnRecord] = []
        self.ending: Optional[GameEnding] = None

        # Pending actions (collected during DECISION phase)
        self._pending_action_a: Optional[Action] = None
        self._pending_action_b: Optional[Action] = None

        # Record initial state
        self._record_turn_start()

    def _parse_scenario(self, scenario: dict) -> None:
        """Parse scenario JSON into turn configurations."""
        # Handle linear turn list or branching structure
        turns = scenario.get("turns", [])
        branches = scenario.get("branches", {})

        # Parse linear turns
        for i, turn_data in enumerate(turns):
            turn_num = turn_data.get("turn", i + 1)
            key = f"turn_{turn_num}"
            self._turn_configs[key] = self._parse_turn_config(turn_data)

            # Set first turn as current
            if i == 0:
                self._current_turn_key = key

        # Parse branch turns
        for branch_key, turn_data in branches.items():
            self._turn_configs[branch_key] = self._parse_turn_config(turn_data)

        # If no turns defined, create default configuration
        if not self._turn_configs:
            self._turn_configs["turn_1"] = self._create_default_turn_config(1)
            self._current_turn_key = "turn_1"

    def _parse_matrix_type(self, matrix_type_str: str, turn: int) -> MatrixType:
        """Parse matrix type string with alias support.

        Raises ValueError if the matrix type is unknown - no fallbacks.
        """
        # Normalize the string
        normalized = matrix_type_str.lower().replace("-", "_").replace(" ", "_")

        # Alias mapping for common variations (documented mappings only)
        aliases = {
            "inspection": "inspection_game",
            "inspect": "inspection_game",
            "recon": "reconnaissance",
            "pd": "prisoners_dilemma",
            "prisoner_dilemma": "prisoners_dilemma",
            "bos": "battle_of_sexes",
            "battle": "battle_of_sexes",
            "stag": "stag_hunt",
            "coord": "pure_coordination",
            "coordination": "pure_coordination",
            "trust": "stag_hunt",  # Trust game maps to Stag Hunt (similar structure)
            "trust_game": "stag_hunt",
            "security": "security_dilemma",
        }

        # Apply alias if exists
        if normalized in aliases:
            normalized = aliases[normalized]

        # Try direct enum lookup
        try:
            return MatrixType(normalized)
        except ValueError:
            pass

        # Try uppercase enum name
        try:
            return MatrixType[matrix_type_str.upper().replace("-", "_").replace(" ", "_")]
        except KeyError:
            pass

        # No fallbacks - fail with clear error
        valid_types = [t.value for t in MatrixType]
        raise ValueError(
            f"Unknown matrix type '{matrix_type_str}' at turn {turn}. "
            f"Valid types: {valid_types}. "
            f"Valid aliases: {list(aliases.keys())}"
        )

    def _parse_turn_config(self, turn_data: dict) -> TurnConfiguration:
        """Parse a single turn configuration from scenario data."""
        turn_num = turn_data.get("turn", 1)
        act = self._get_act_for_turn(turn_num)

        # Parse matrix type with alias mapping - no fallbacks, fail on invalid
        matrix_type_str = turn_data.get("matrix_type", "PRISONERS_DILEMMA")
        matrix_type = self._parse_matrix_type(matrix_type_str, turn_num)

        # Parse matrix parameters or use defaults
        params_data = turn_data.get("matrix_parameters", {})
        if params_data:
            matrix_params = MatrixParameters(**params_data)
        else:
            matrix_params = get_default_params_for_type(matrix_type)

        return TurnConfiguration(
            turn=turn_num,
            act=act,
            narrative_briefing=turn_data.get("narrative_briefing", ""),
            matrix_type=matrix_type,
            matrix_params=matrix_params,
            action_menu_override=turn_data.get("action_menu"),
            outcome_narratives=turn_data.get("outcome_narratives"),
            branches=turn_data.get("branches"),
            default_next=turn_data.get("default_next"),
            settlement_available=turn_data.get("settlement_available", True),
            settlement_failed_narrative=turn_data.get(
                "settlement_failed_narrative",
                "Negotiations failed. The crisis continues.",
            ),
        )

    def _create_default_turn_config(self, turn: int) -> TurnConfiguration:
        """Create a default turn configuration."""
        act = self._get_act_for_turn(turn)

        # Select appropriate matrix type based on act
        if act == 1:
            matrix_type = MatrixType.STAG_HUNT
        elif act == 2:
            matrix_type = MatrixType.PRISONERS_DILEMMA
        else:
            matrix_type = MatrixType.CHICKEN

        return TurnConfiguration(
            turn=turn,
            act=act,
            narrative_briefing=f"Turn {turn} - The situation develops...",
            matrix_type=matrix_type,
            matrix_params=get_default_params_for_type(matrix_type),
        )

    def _get_act_for_turn(self, turn: int) -> int:
        """Determine act number from turn number."""
        if turn <= 4:
            return 1
        elif turn <= 8:
            return 2
        else:
            return 3

    def _create_initial_state(self, max_turns: int) -> GameState:
        """Create the initial game state."""
        return GameState(
            player_a=PlayerState(
                position=5.0,
                resources=5.0,
                previous_type=None,
                information=InformationState(),
            ),
            player_b=PlayerState(
                position=5.0,
                resources=5.0,
                previous_type=None,
                information=InformationState(),
            ),
            cooperation_score=5.0,
            stability=5.0,
            risk_level=2.0,
            turn=1,
            max_turns=max_turns,
        )

    def _record_turn_start(self) -> None:
        """Record the start of a new turn in history."""
        config = self._get_current_config()
        record = TurnRecord(
            turn=self.state.turn,
            phase=self.phase,
            state_before=self.state.model_copy(deep=True),
            narrative=config.narrative_briefing,
            matrix_type=config.matrix_type,
        )
        self.history.append(record)

    def _get_current_config(self) -> TurnConfiguration:
        """Get the configuration for the current turn."""
        if self._current_turn_key and self._current_turn_key in self._turn_configs:
            return self._turn_configs[self._current_turn_key]

        # Fallback: look for turn by number
        turn_key = f"turn_{self.state.turn}"
        if turn_key in self._turn_configs:
            return self._turn_configs[turn_key]

        # Create default if not found
        config = self._create_default_turn_config(self.state.turn)
        self._turn_configs[turn_key] = config
        return config

    # =========================================================================
    # Public API
    # =========================================================================

    def get_current_state(self) -> GameState:
        """Get the current game state.

        Returns:
            Copy of current GameState
        """
        return self.state.model_copy(deep=True)

    def get_available_actions(self, player: Literal["A", "B"]) -> list[Action]:
        """Get available actions for a player.

        Args:
            player: "A" or "B"

        Returns:
            List of available actions
        """
        if player == "A":
            position = self.state.position_a
            resources = self.state.resources_a
        else:
            position = self.state.position_b
            resources = self.state.resources_b

        config = self._get_current_config()

        # Get base action menu
        menu = get_action_menu(
            risk_level=int(self.state.risk_level),
            turn=self.state.turn,
            stability=self.state.stability,
            player_position=position,
            player_resources=resources,
        )

        # Check if settlement is available per scenario
        if not config.settlement_available:
            # Remove settlement from special actions
            menu.special_actions = [
                a for a in menu.special_actions
                if a.category != ActionCategory.SETTLEMENT
            ]

        return menu.all_actions()

    def get_action_menu(self, player: Literal["A", "B"]) -> ActionMenu:
        """Get the complete action menu for a player.

        Args:
            player: "A" or "B"

        Returns:
            ActionMenu with standard and special actions
        """
        if player == "A":
            position = self.state.position_a
            resources = self.state.resources_a
        else:
            position = self.state.position_b
            resources = self.state.resources_b

        config = self._get_current_config()

        menu = get_action_menu(
            risk_level=int(self.state.risk_level),
            turn=self.state.turn,
            stability=self.state.stability,
            player_position=position,
            player_resources=resources,
        )

        # Check if settlement is available per scenario
        if not config.settlement_available:
            menu.special_actions = [
                a for a in menu.special_actions
                if a.category != ActionCategory.SETTLEMENT
            ]
            menu.can_propose_settlement = False

        return menu

    def get_briefing(self) -> str:
        """Get the narrative briefing for the current turn.

        Returns:
            Narrative text describing the current situation
        """
        config = self._get_current_config()
        return config.narrative_briefing

    def submit_actions(
        self,
        action_a: Action,
        action_b: Action,
    ) -> TurnResult:
        """Submit simultaneous actions for both players.

        This processes the complete turn sequence:
        1. Validate actions
        2. Resolve actions (matrix game or special)
        3. Update state
        4. Check endings
        5. Advance turn

        Args:
            action_a: Action for player A
            action_b: Action for player B

        Returns:
            TurnResult with outcome information
        """
        if self.is_game_over():
            return TurnResult(
                success=False,
                error="Game is already over",
            )

        # Phase 2: DECISION - Validate actions
        valid_a, error_a = validate_action_availability(
            action_a,
            self.state.turn,
            self.state.stability,
            self.state.resources_a,
        )
        if not valid_a:
            return TurnResult(success=False, error=f"Player A: {error_a}")

        valid_b, error_b = validate_action_availability(
            action_b,
            self.state.turn,
            self.state.stability,
            self.state.resources_b,
        )
        if not valid_b:
            return TurnResult(success=False, error=f"Player B: {error_b}")

        self._pending_action_a = action_a
        self._pending_action_b = action_b
        self.phase = TurnPhase.RESOLUTION

        # Phase 3: RESOLUTION
        action_result, narrative = self._resolve_actions(action_a, action_b)

        # Phase 4: STATE UPDATE
        self.phase = TurnPhase.STATE_UPDATE
        new_state = self._update_state(action_result)

        # Update history
        if self.history:
            self.history[-1].action_a = action_a
            self.history[-1].action_b = action_b
            self.history[-1].outcome = action_result
            self.history[-1].state_after = new_state.model_copy(deep=True)
            self.history[-1].narrative = narrative

        self.state = new_state

        # Phase 5: CHECK DETERMINISTIC ENDINGS
        self.phase = TurnPhase.CHECK_DETERMINISTIC
        ending = self._check_deterministic_endings()
        if ending:
            self.ending = ending
            self.phase = TurnPhase.GAME_OVER
            return TurnResult(
                success=True,
                action_result=action_result,
                ending=ending,
                narrative=narrative,
            )

        # Phase 6: CHECK CRISIS TERMINATION (Turn >= 10, Risk > 7)
        self.phase = TurnPhase.CHECK_CRISIS
        ending = self._check_crisis_termination()
        if ending:
            self.ending = ending
            self.phase = TurnPhase.GAME_OVER
            return TurnResult(
                success=True,
                action_result=action_result,
                ending=ending,
                narrative=narrative,
            )

        # Phase 7: CHECK NATURAL ENDING
        self.phase = TurnPhase.CHECK_NATURAL
        ending = self._check_natural_ending()
        if ending:
            self.ending = ending
            self.phase = TurnPhase.GAME_OVER
            return TurnResult(
                success=True,
                action_result=action_result,
                ending=ending,
                narrative=narrative,
            )

        # Phase 8: ADVANCE
        self.phase = TurnPhase.ADVANCE
        self._advance_turn(action_result)

        return TurnResult(
            success=True,
            action_result=action_result,
            narrative=narrative,
        )

    def get_history(self) -> list[TurnRecord]:
        """Get the complete turn history.

        Returns:
            List of TurnRecords for all completed turns
        """
        return list(self.history)

    def is_game_over(self) -> bool:
        """Check if the game has ended.

        Returns:
            True if game is over
        """
        return self.ending is not None

    def get_ending(self) -> Optional[GameEnding]:
        """Get the game ending if game is over.

        Returns:
            GameEnding if game is over, None otherwise
        """
        return self.ending

    def get_information_state(self, player: Literal["A", "B"]) -> InformationState:
        """Get a player's information state about their opponent.

        Args:
            player: "A" or "B"

        Returns:
            InformationState for that player
        """
        if player == "A":
            return self.state.player_a.information.model_copy(deep=True)
        else:
            return self.state.player_b.information.model_copy(deep=True)

    # =========================================================================
    # Resolution Logic
    # =========================================================================

    def _resolve_actions(
        self,
        action_a: Action,
        action_b: Action,
    ) -> tuple[ActionResult, str]:
        """Resolve submitted actions.

        Handles:
        - Standard matrix game resolution
        - Information games (Reconnaissance, Inspection)
        - Settlement proposals

        Returns:
            Tuple of (ActionResult, narrative_text)
        """
        config = self._get_current_config()

        # Check for special action categories
        if (action_a.category == ActionCategory.SETTLEMENT or
                action_b.category == ActionCategory.SETTLEMENT):
            return self._resolve_settlement(action_a, action_b)

        if (action_a.category == ActionCategory.RECONNAISSANCE or
                action_b.category == ActionCategory.RECONNAISSANCE):
            return self._resolve_reconnaissance(action_a, action_b)

        if (action_a.category == ActionCategory.INSPECTION or
                action_b.category == ActionCategory.INSPECTION):
            return self._resolve_inspection(action_a, action_b)

        # Standard matrix resolution
        return self._resolve_matrix(action_a, action_b, config)

    def _resolve_matrix(
        self,
        action_a: Action,
        action_b: Action,
        config: TurnConfiguration,
    ) -> tuple[ActionResult, str]:
        """Resolve actions via matrix game."""
        # Build the matrix
        matrix = build_matrix(config.matrix_type, config.matrix_params)

        # Map actions to matrix choices (0=cooperate/first, 1=defect/second)
        choice_a = 0 if action_a.action_type == ActionType.COOPERATIVE else 1
        choice_b = 0 if action_b.action_type == ActionType.COOPERATIVE else 1

        # Get outcome
        outcome = matrix.get_outcome(choice_a, choice_b)

        # Build outcome code
        code_a = "C" if action_a.action_type == ActionType.COOPERATIVE else "D"
        code_b = "C" if action_b.action_type == ActionType.COOPERATIVE else "D"
        outcome_code = f"{code_a}{code_b}"

        # Get narrative
        narrative = ""
        if config.outcome_narratives and outcome_code in config.outcome_narratives:
            narrative = config.outcome_narratives[outcome_code]
        else:
            narrative = self._generate_default_narrative(outcome_code, matrix)

        # Create action result
        deltas = outcome.deltas
        result = ActionResult(
            action_a=action_a.action_type,
            action_b=action_b.action_type,
            position_delta_a=deltas.pos_a,
            position_delta_b=deltas.pos_b,
            resource_cost_a=deltas.res_cost_a + action_a.resource_cost,
            resource_cost_b=deltas.res_cost_b + action_b.resource_cost,
            risk_delta=deltas.risk_delta,
            outcome_code=outcome_code,
            narrative=narrative,
        )

        return result, narrative

    def _resolve_reconnaissance(
        self,
        action_a: Action,
        action_b: Action,
    ) -> tuple[ActionResult, str]:
        """Resolve reconnaissance game.

        From GAME_MANUAL.md Section 3.6.1:
        - Probe + Vigilant = Detected (Risk+0.5, no info)
        - Probe + Project = Success (learn opponent Position)
        - Mask + Vigilant = Stalemate
        - Mask + Project = Exposed (opponent learns your Position)

        Both players choose Probe/Mask. Initiator pays 0.5 Resources.
        """
        # Determine who initiated (has RECONNAISSANCE action)
        initiator = "A" if action_a.category == ActionCategory.RECONNAISSANCE else "B"

        # Both players implicitly choose in the recon game
        # Map their strategic action types to recon choices
        # Cooperative -> Mask (defensive), Competitive -> Probe (aggressive)
        choice_a = "Probe" if action_a.action_type == ActionType.COMPETITIVE or action_a.category == ActionCategory.RECONNAISSANCE else "Mask"
        choice_b = "Probe" if action_b.action_type == ActionType.COMPETITIVE or action_b.category == ActionCategory.RECONNAISSANCE else "Mask"

        # For recon, if you initiated you're probing
        if initiator == "A":
            choice_a = "Probe"
            # Opponent chooses based on their action
            choice_b = "Vigilant" if action_b.action_type == ActionType.COOPERATIVE else "Project"
        else:
            choice_b = "Probe"
            choice_a = "Vigilant" if action_a.action_type == ActionType.COOPERATIVE else "Project"

        # Resolve
        risk_delta = 0.0
        narrative = ""

        if initiator == "A":
            if choice_a == "Probe" and choice_b == "Vigilant":
                # Detected
                risk_delta = 0.5
                narrative = "Your reconnaissance attempt was detected. Risk increases."
            elif choice_a == "Probe" and choice_b == "Project":
                # Success - A learns B's position
                self.state.player_a.information.update_position(
                    self.state.position_b, self.state.turn
                )
                narrative = f"Reconnaissance successful. You learned your opponent's position: {self.state.position_b:.1f}"
            elif choice_a == "Mask" and choice_b == "Vigilant":
                # Stalemate
                narrative = "Your cautious approach yielded no information."
            else:  # Mask + Project
                # Exposed - B learns A's position
                self.state.player_b.information.update_position(
                    self.state.position_a, self.state.turn
                )
                narrative = "Your position was exposed to your opponent."
        else:  # initiator == "B"
            if choice_b == "Probe" and choice_a == "Vigilant":
                risk_delta = 0.5
                narrative = "Opponent's reconnaissance was detected. Risk increases."
            elif choice_b == "Probe" and choice_a == "Project":
                self.state.player_b.information.update_position(
                    self.state.position_a, self.state.turn
                )
                narrative = "Opponent gained intelligence on your position."
            elif choice_b == "Mask" and choice_a == "Vigilant":
                narrative = "Stalemate in intelligence gathering."
            else:
                self.state.player_a.information.update_position(
                    self.state.position_b, self.state.turn
                )
                narrative = "Your counterintelligence revealed opponent's position."

        # Resource cost for initiator
        res_cost_a = 0.5 if initiator == "A" else 0.0
        res_cost_b = 0.5 if initiator == "B" else 0.0

        result = ActionResult(
            action_a=action_a.action_type,
            action_b=action_b.action_type,
            position_delta_a=0.0,
            position_delta_b=0.0,
            resource_cost_a=res_cost_a,
            resource_cost_b=res_cost_b,
            risk_delta=risk_delta,
            outcome_code="RECON",
            narrative=narrative,
        )

        return result, narrative

    def _resolve_inspection(
        self,
        action_a: Action,
        action_b: Action,
    ) -> tuple[ActionResult, str]:
        """Resolve inspection game.

        From GAME_MANUAL.md Section 3.6.2:
        - Inspect + Comply = Verified (learn opponent Resources)
        - Inspect + Cheat = Caught (learn Resources, opponent Risk+1, Position-0.5)
        - Trust + Comply = Nothing
        - Trust + Cheat = Exploited (opponent Position+0.5)
        """
        # Determine who initiated
        initiator = "A" if action_a.category == ActionCategory.INSPECTION else "B"

        # Initiator chooses Inspect, opponent chooses Comply/Cheat
        # Map opponent action: Cooperative -> Comply, Competitive -> Cheat
        if initiator == "A":
            opponent_choice = "Comply" if action_b.action_type == ActionType.COOPERATIVE else "Cheat"
        else:
            opponent_choice = "Comply" if action_a.action_type == ActionType.COOPERATIVE else "Cheat"

        # Resolve
        pos_delta_a = 0.0
        pos_delta_b = 0.0
        risk_delta = 0.0
        narrative = ""

        if initiator == "A":
            if opponent_choice == "Comply":
                # Verified - A learns B's resources
                self.state.player_a.information.update_resources(
                    self.state.resources_b, self.state.turn
                )
                narrative = f"Inspection verified. Opponent resources: {self.state.resources_b:.1f}"
            else:  # Cheat -> Caught
                self.state.player_a.information.update_resources(
                    self.state.resources_b, self.state.turn
                )
                pos_delta_b = -0.5
                risk_delta = 1.0
                narrative = f"Inspection caught opponent cheating! Their resources: {self.state.resources_b:.1f}. They lose position and risk increases."
        else:  # initiator == "B"
            if opponent_choice == "Comply":
                self.state.player_b.information.update_resources(
                    self.state.resources_a, self.state.turn
                )
                narrative = f"Opponent's inspection verified your compliance. Your resources revealed: {self.state.resources_a:.1f}"
            else:  # Cheat -> Caught
                self.state.player_b.information.update_resources(
                    self.state.resources_a, self.state.turn
                )
                pos_delta_a = -0.5
                risk_delta = 1.0
                narrative = "You were caught cheating during inspection! Position and risk affected."

        # Resource cost for initiator
        res_cost_a = 0.3 if initiator == "A" else 0.0
        res_cost_b = 0.3 if initiator == "B" else 0.0

        result = ActionResult(
            action_a=action_a.action_type,
            action_b=action_b.action_type,
            position_delta_a=pos_delta_a,
            position_delta_b=pos_delta_b,
            resource_cost_a=res_cost_a,
            resource_cost_b=res_cost_b,
            risk_delta=risk_delta,
            outcome_code="INSPECT",
            narrative=narrative,
        )

        return result, narrative

    def _resolve_settlement(
        self,
        action_a: Action,
        action_b: Action,
    ) -> tuple[ActionResult, str]:
        """Resolve settlement proposal.

        Settlement handling is simplified here - full negotiation protocol
        would be implemented in a separate settlement module.

        For now: if both propose settlement, game can end.
        If one proposes, it's treated as a cooperative action.
        """
        config = self._get_current_config()

        both_settle = (
            action_a.category == ActionCategory.SETTLEMENT and
            action_b.category == ActionCategory.SETTLEMENT
        )

        if both_settle:
            # Both want to settle - calculate fair split based on positions
            total_pos = self.state.position_a + self.state.position_b
            if total_pos > 0:
                vp_a = (self.state.position_a / total_pos) * 100
            else:
                vp_a = 50.0
            vp_b = 100.0 - vp_a

            # Apply cooperation bonus
            coop_bonus = (self.state.cooperation_score - 5) * 2
            vp_a = clamp(vp_a + coop_bonus, 5, 95)
            vp_b = 100.0 - vp_a

            # Create ending
            self.ending = GameEnding(
                ending_type=EndingType.SETTLEMENT,
                vp_a=vp_a,
                vp_b=vp_b,
                turn=self.state.turn,
                description=f"Settlement reached. Player A: {vp_a:.1f} VP, Player B: {vp_b:.1f} VP",
            )

            result = ActionResult(
                action_a=ActionType.COOPERATIVE,
                action_b=ActionType.COOPERATIVE,
                outcome_code="SETTLE",
                narrative="Both parties have agreed to a settlement.",
            )
            return result, "Settlement reached!"

        # One-sided settlement attempt - treated as cooperative action
        # Risk +1 for failed negotiation
        narrative = config.settlement_failed_narrative

        result = ActionResult(
            action_a=action_a.action_type,
            action_b=action_b.action_type,
            risk_delta=1.0,
            outcome_code="SETTLE_FAIL",
            narrative=narrative,
        )
        return result, narrative

    def _generate_default_narrative(
        self,
        outcome_code: str,
        matrix: PayoffMatrix,
    ) -> str:
        """Generate default outcome narrative."""
        narratives = {
            "CC": f"Both sides chose cooperation. {matrix.row_labels[0]} met {matrix.col_labels[0]}.",
            "CD": f"You cooperated while your opponent competed. {matrix.row_labels[0]} against {matrix.col_labels[1]}.",
            "DC": f"You competed while your opponent cooperated. {matrix.row_labels[1]} against {matrix.col_labels[0]}.",
            "DD": f"Both sides chose competition. {matrix.row_labels[1]} met {matrix.col_labels[1]}.",
        }
        return narratives.get(outcome_code, "The turn resolves.")

    # =========================================================================
    # State Update
    # =========================================================================

    def _update_state(self, result: ActionResult) -> GameState:
        """Apply action result to update game state.

        Uses the apply_action_result function from state.py which handles:
        - Position changes (scaled by act multiplier)
        - Resource costs
        - Risk level changes
        - Cooperation score update
        - Stability update
        - Previous action type tracking
        """
        return apply_action_result(self.state, result)

    # =========================================================================
    # Ending Checks
    # =========================================================================

    def _check_deterministic_endings(self) -> Optional[GameEnding]:
        """Check for deterministic game endings.

        From GAME_MANUAL.md Section 4.5:
        - Risk = 10: Mutual Destruction (both get 20 VP)
        - Position = 0: That player loses (10 VP, opponent 90 VP)
        - Resources = 0: That player loses (15 VP, opponent 85 VP)
        """
        # Risk = 10: Mutual Destruction
        if self.state.risk_level >= 10:
            return GameEnding(
                ending_type=EndingType.MUTUAL_DESTRUCTION,
                vp_a=20.0,
                vp_b=20.0,
                turn=self.state.turn,
                description="Risk reached critical level. Mutual destruction.",
            )

        # Position = 0: That player loses
        if self.state.position_a <= 0:
            return GameEnding(
                ending_type=EndingType.POSITION_COLLAPSE_A,
                vp_a=10.0,
                vp_b=90.0,
                turn=self.state.turn,
                description="Player A's position collapsed. Total defeat.",
            )

        if self.state.position_b <= 0:
            return GameEnding(
                ending_type=EndingType.POSITION_COLLAPSE_B,
                vp_a=90.0,
                vp_b=10.0,
                turn=self.state.turn,
                description="Player B's position collapsed. Total defeat.",
            )

        # Resources = 0: That player loses
        if self.state.resources_a <= 0:
            return GameEnding(
                ending_type=EndingType.RESOURCE_EXHAUSTION_A,
                vp_a=15.0,
                vp_b=85.0,
                turn=self.state.turn,
                description="Player A exhausted all resources. Defeat.",
            )

        if self.state.resources_b <= 0:
            return GameEnding(
                ending_type=EndingType.RESOURCE_EXHAUSTION_B,
                vp_a=85.0,
                vp_b=15.0,
                turn=self.state.turn,
                description="Player B exhausted all resources. Defeat.",
            )

        return None

    def _check_crisis_termination(self) -> Optional[GameEnding]:
        """Check for probabilistic crisis termination.

        From GAME_MANUAL.md Section 4.6:
        - Only checked for Turn >= 10 and Risk > 7
        - P(Termination) = (Risk - 7) * 0.08
        - Risk 8: 8%, Risk 9: 16%
        """
        if self.state.turn < 10:
            return None

        if self.state.risk_level <= 7:
            return None

        # Calculate termination probability
        p_termination = (self.state.risk_level - 7) * 0.08

        if self._random.random() < p_termination:
            # Crisis termination triggered - perform final resolution
            vp_a, vp_b = self._final_resolution()
            return GameEnding(
                ending_type=EndingType.CRISIS_TERMINATION,
                vp_a=vp_a,
                vp_b=vp_b,
                turn=self.state.turn,
                description=f"Crisis spiraled out of control at Risk {self.state.risk_level:.1f}.",
            )

        return None

    def _check_natural_ending(self) -> Optional[GameEnding]:
        """Check for natural game ending at max turns."""
        # Note: state.turn has already been incremented by apply_action_result
        # So we check if we've completed the max turn
        if self.state.turn > self.state.max_turns:
            vp_a, vp_b = self._final_resolution()
            return GameEnding(
                ending_type=EndingType.NATURAL_ENDING,
                vp_a=vp_a,
                vp_b=vp_b,
                turn=self.state.turn - 1,  # The turn we just completed
                description="The crisis reached its natural conclusion.",
            )

        return None

    def _final_resolution(self) -> tuple[float, float]:
        """Calculate final VP using variance formula.

        From GAME_MANUAL.md Section 4.3:
        1. Calculate expected values from position
        2. Calculate shared variance
        3. Apply symmetric noise
        4. Clamp and renormalize to sum to 100
        """
        # Expected values from position
        total_pos = self.state.position_a + self.state.position_b
        if total_pos == 0:
            ev_a = 50.0
        else:
            ev_a = (self.state.position_a / total_pos) * 100
        ev_b = 100.0 - ev_a

        # Calculate shared variance (use state's computed property)
        shared_sigma = self.state.shared_sigma

        # Apply symmetric noise
        noise = self._random.gauss(0, shared_sigma)
        vp_a_raw = ev_a + noise
        vp_b_raw = ev_b - noise  # Symmetric: both move together

        # Clamp both to [5, 95]
        vp_a_clamped = clamp(vp_a_raw, 5.0, 95.0)
        vp_b_clamped = clamp(vp_b_raw, 5.0, 95.0)

        # Renormalize to sum to 100
        total = vp_a_clamped + vp_b_clamped
        vp_a = (vp_a_clamped * 100.0) / total
        vp_b = (vp_b_clamped * 100.0) / total

        return vp_a, vp_b

    # =========================================================================
    # Turn Advancement
    # =========================================================================

    def _advance_turn(self, result: ActionResult) -> None:
        """Advance to the next turn.

        Updates:
        - Current turn key based on branching
        - Phase to BRIEFING
        - Records new turn start
        """
        config = self._get_current_config()

        # Determine next turn key based on outcome
        if config.branches and result.outcome_code in config.branches:
            self._current_turn_key = config.branches[result.outcome_code]
        elif config.default_next:
            self._current_turn_key = config.default_next
        else:
            # Default: increment turn number
            self._current_turn_key = f"turn_{self.state.turn}"

        # Reset phase
        self.phase = TurnPhase.BRIEFING
        self._pending_action_a = None
        self._pending_action_b = None

        # Record new turn start
        self._record_turn_start()


# =============================================================================
# Factory function for creating games
# =============================================================================


def create_game(
    scenario_id: str,
    scenario_repo: ScenarioRepository,
    max_turns: Optional[int] = None,
    random_seed: Optional[int] = None,
) -> GameEngine:
    """Create a new game with the specified scenario.

    Args:
        scenario_id: ID of scenario to use
        scenario_repo: Repository for loading scenarios
        max_turns: Override for maximum turns (default: random 12-16)
        random_seed: Seed for reproducibility

    Returns:
        Initialized GameEngine

    Raises:
        ValueError: If scenario not found
    """
    return GameEngine(
        scenario_id=scenario_id,
        scenario_repo=scenario_repo,
        max_turns=max_turns,
        random_seed=random_seed,
    )
