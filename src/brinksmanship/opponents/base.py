"""Base opponent interface for Brinksmanship.

This module defines the abstract base class for all opponent types,
along with settlement-related dataclasses and factory functions.

See ENGINEERING_DESIGN.md Milestone 4.1 for specification.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

from brinksmanship.models.actions import Action
from brinksmanship.models.state import GameState

if TYPE_CHECKING:
    from brinksmanship.models.state import ActionResult


@dataclass
class SettlementProposal:
    """A settlement proposal with numeric offer and argument.

    Attributes:
        offered_vp: VP proposed for the proposer (0-100)
        argument: Free-text rationale (max 500 chars)
    """

    offered_vp: int
    argument: str = ""

    def __post_init__(self) -> None:
        """Validate proposal constraints."""
        if not 0 <= self.offered_vp <= 100:
            raise ValueError(f"offered_vp must be 0-100, got {self.offered_vp}")
        if len(self.argument) > 500:
            self.argument = self.argument[:500]


@dataclass
class SettlementResponse:
    """Response to a settlement proposal.

    Attributes:
        action: The response action - accept, counter, or reject
        counter_vp: VP for counter-proposal (if countering)
        counter_argument: Argument for counter-proposal (if countering)
        rejection_reason: Reason for rejection (if rejecting)
    """

    action: Literal["accept", "counter", "reject"]
    counter_vp: int | None = None
    counter_argument: str | None = None
    rejection_reason: str | None = None

    def __post_init__(self) -> None:
        """Validate response constraints."""
        if self.action == "counter":
            if self.counter_vp is None:
                raise ValueError("counter_vp required when action is 'counter'")
            if not 0 <= self.counter_vp <= 100:
                raise ValueError(f"counter_vp must be 0-100, got {self.counter_vp}")


class Opponent(ABC):
    """Abstract base class for all opponent types.

    All opponents implement the same interface, supporting both
    strategic actions and settlement negotiations.

    Subclasses:
        - Deterministic opponents (NashCalculator, TitForTat, etc.)
        - Historical personas (Bismarck, Nixon, etc.)
        - Custom generated personas
    """

    def __init__(self, name: str = "Opponent"):
        """Initialize opponent.

        Args:
            name: Display name for the opponent
        """
        self.name = name
        self._history: list[tuple[Action, Action, "ActionResult"]] = []

    @abstractmethod
    def choose_action(
        self, state: GameState, available_actions: list[Action]
    ) -> Action:
        """Choose strategic action for this turn.

        Args:
            state: Current game state
            available_actions: List of valid actions to choose from

        Returns:
            The chosen action
        """
        pass

    def receive_result(self, result: "ActionResult") -> None:
        """Process the result of a turn for learning/adaptation.

        Default implementation stores history. Subclasses can override
        to implement learning behavior.

        Args:
            result: The outcome of the turn
        """
        # Default: just record history (subclasses may do more)
        pass

    @abstractmethod
    def evaluate_settlement(
        self,
        proposal: SettlementProposal,
        state: GameState,
        is_final_offer: bool,
    ) -> SettlementResponse:
        """Evaluate a settlement proposal and respond.

        NOTE: Even deterministic opponents use LLM for this method,
        as the argument text requires language understanding.

        Args:
            proposal: The settlement proposal to evaluate
            state: Current game state
            is_final_offer: Whether this is the final offer (no counter allowed)

        Returns:
            Response to the proposal
        """
        pass

    @abstractmethod
    def propose_settlement(self, state: GameState) -> SettlementProposal | None:
        """Optionally propose settlement.

        Args:
            state: Current game state

        Returns:
            Settlement proposal, or None if not proposing
        """
        pass

    def get_position_fair_vp(self, state: GameState, is_player_a: bool) -> int:
        """Calculate fair VP based on position difference.

        Uses formula from GAME_MANUAL.md Section 4.4.2:
            Position_Difference = Your_Position - Opponent_Position
            Cooperation_Bonus = (Cooperation_Score - 5) * 2
            Your_Suggested_VP = 50 + (Position_Difference * 5) + Cooperation_Bonus

        Args:
            state: Current game state
            is_player_a: Whether this opponent is player A

        Returns:
            Fair VP for this opponent based on position
        """
        if is_player_a:
            my_position = state.position_a
            their_position = state.position_b
        else:
            my_position = state.position_b
            their_position = state.position_a

        position_diff = my_position - their_position
        coop_bonus = (state.cooperation_score - 5) * 2
        suggested_vp = 50 + (position_diff * 5) + coop_bonus

        return int(max(20, min(80, suggested_vp)))


# Type alias for opponent types
OpponentType = Literal[
    # Deterministic opponents
    "nash_calculator",
    "security_seeker",
    "opportunist",
    "erratic",
    "tit_for_tat",
    "grim_trigger",
    # Historical personas
    "bismarck",
    "richelieu",
    "metternich",
    "pericles",
    "nixon",
    "kissinger",
    "khrushchev",
    "tito",
    "kekkonen",
    "lee_kuan_yew",
    "gates",
    "jobs",
    "icahn",
    "zuckerberg",
    "buffett",
    "theodora",
    "wu_zetian",
    "cixi",
    "livia",
    # Custom
    "custom",
]


def get_opponent_by_type(opponent_type: OpponentType | str) -> Opponent:
    """Create opponent by type name.

    Factory function that returns the appropriate opponent instance
    based on the type name.

    Args:
        opponent_type: Type of opponent to create

    Returns:
        Opponent instance

    Raises:
        ValueError: If opponent type is unknown
    """
    # Import here to avoid circular imports
    from brinksmanship.opponents.deterministic import (
        Erratic,
        GrimTrigger,
        NashCalculator,
        Opportunist,
        SecuritySeeker,
        TitForTat,
    )
    from brinksmanship.opponents.historical import HistoricalPersona

    # Normalize type name
    type_name = opponent_type.lower().replace("-", "_").replace(" ", "_")

    # Deterministic opponents
    deterministic_map: dict[str, type[Opponent]] = {
        "nash_calculator": NashCalculator,
        "nash": NashCalculator,
        "security_seeker": SecuritySeeker,
        "opportunist": Opportunist,
        "erratic": Erratic,
        "tit_for_tat": TitForTat,
        "titfortat": TitForTat,
        "grim_trigger": GrimTrigger,
        "grimtrigger": GrimTrigger,
    }

    if type_name in deterministic_map:
        return deterministic_map[type_name]()

    # Historical personas
    historical_personas = [
        "bismarck",
        "richelieu",
        "metternich",
        "pericles",
        "nixon",
        "kissinger",
        "khrushchev",
        "tito",
        "kekkonen",
        "lee_kuan_yew",
        "gates",
        "jobs",
        "icahn",
        "zuckerberg",
        "buffett",
        "theodora",
        "wu_zetian",
        "cixi",
        "livia",
    ]

    if type_name in historical_personas:
        return HistoricalPersona(persona_name=type_name)

    raise ValueError(
        f"Unknown opponent type: {opponent_type}. "
        f"Valid deterministic types: {list(deterministic_map.keys())}. "
        f"Valid personas: {historical_personas}"
    )


def list_opponent_types() -> dict[str, list[str]]:
    """List all available opponent types by category.

    Returns:
        Dictionary with categories as keys and list of types as values
    """
    return {
        "deterministic": [
            "nash_calculator",
            "security_seeker",
            "opportunist",
            "erratic",
            "tit_for_tat",
            "grim_trigger",
        ],
        "historical_political": [
            "bismarck",
            "richelieu",
            "metternich",
            "pericles",
        ],
        "historical_cold_war": [
            "nixon",
            "kissinger",
            "khrushchev",
            "tito",
            "kekkonen",
            "lee_kuan_yew",
        ],
        "historical_corporate": [
            "gates",
            "jobs",
            "icahn",
            "zuckerberg",
            "buffett",
        ],
        "historical_palace": [
            "theodora",
            "wu_zetian",
            "cixi",
            "livia",
        ],
    }
