"""Deterministic opponent implementations for Brinksmanship.

This module implements rule-based opponents with deterministic strategic actions
but LLM-based settlement evaluation. Each opponent type embodies a specific
game-theoretic or strategic archetype.

See ENGINEERING_DESIGN.md Milestone 4.2 for specifications.
See GAME_MANUAL.md for game mechanics.
"""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, ClassVar

from brinksmanship.llm import generate_json
from brinksmanship.models.actions import Action, ActionType
from brinksmanship.models.state import GameState
from brinksmanship.opponents.base import (
    Opponent,
    SettlementProposal,
    SettlementResponse,
)
from brinksmanship.prompts import (
    SETTLEMENT_EVALUATION_PROMPT,
    SETTLEMENT_EVALUATION_SCHEMA,
    SETTLEMENT_EVALUATION_SYSTEM_PROMPT,
)

if TYPE_CHECKING:
    from brinksmanship.models.state import ActionResult


class DeterministicOpponent(Opponent):
    """Base class for deterministic opponents.

    Strategic actions are purely deterministic (testable, reproducible).
    Settlement evaluation uses LLM with persona-specific prompts.
    """

    # Subclasses should override these
    settlement_persona: ClassVar[str] = "A rational game theorist"
    default_settlement_threshold: ClassVar[float] = 0.0  # VP difference threshold

    def __init__(self, name: str = "Opponent"):
        """Initialize the deterministic opponent.

        Args:
            name: Display name for the opponent
        """
        super().__init__(name=name)
        self._is_player_a: bool | None = None
        self._betrayed: bool = False  # Track if opponent has defected (for GrimTrigger)
        self._first_turn: bool = True

    def set_player_side(self, is_player_a: bool) -> None:
        """Set which side this opponent is playing.

        Args:
            is_player_a: True if this opponent is player A, False if player B
        """
        self._is_player_a = is_player_a

    def _get_my_position(self, state: GameState) -> float:
        """Get this opponent's position from state."""
        if self._is_player_a is None:
            # Default to player B if not set
            return state.position_b
        return state.position_a if self._is_player_a else state.position_b

    def _get_opponent_position(self, state: GameState) -> float:
        """Get the human player's position from state."""
        if self._is_player_a is None:
            return state.position_a
        return state.position_b if self._is_player_a else state.position_a

    def _get_my_resources(self, state: GameState) -> float:
        """Get this opponent's resources from state."""
        if self._is_player_a is None:
            return state.resources_b
        return state.resources_a if self._is_player_a else state.resources_b

    def _get_opponent_previous_type(self, state: GameState) -> ActionType | None:
        """Get the human player's previous action type."""
        if self._is_player_a is None:
            return state.previous_type_a
        return state.previous_type_b if self._is_player_a else state.previous_type_a

    def _get_cooperative_actions(self, available_actions: list[Action]) -> list[Action]:
        """Filter to cooperative actions only."""
        return [a for a in available_actions if a.action_type == ActionType.COOPERATIVE]

    def _get_competitive_actions(self, available_actions: list[Action]) -> list[Action]:
        """Filter to competitive actions only."""
        return [a for a in available_actions if a.action_type == ActionType.COMPETITIVE]

    def _select_random_from_type(
        self,
        available_actions: list[Action],
        action_type: ActionType,
    ) -> Action:
        """Select a random action of the specified type.

        Falls back to any available action if no actions of desired type exist.
        """
        typed_actions = [a for a in available_actions if a.action_type == action_type]
        if typed_actions:
            return random.choice(typed_actions)
        # Fallback to any action
        return random.choice(available_actions)

    async def choose_action(
        self, state: GameState, available_actions: list[Action]
    ) -> Action:
        """Choose action - must be overridden by subclasses.

        This is async for interface consistency, even though deterministic
        opponents don't need async (they don't call LLMs for action selection).
        """
        raise NotImplementedError("Subclasses must implement choose_action")

    async def evaluate_settlement(
        self,
        proposal: SettlementProposal,
        state: GameState,
        is_final_offer: bool,
    ) -> SettlementResponse:
        """Evaluate a settlement proposal using LLM with persona prompt.

        Even deterministic opponents use LLM for settlement evaluation
        because the argument text requires language understanding.

        Args:
            proposal: The settlement proposal to evaluate
            state: Current game state
            is_final_offer: Whether this is a final offer (no counter allowed)

        Returns:
            Response to the proposal
        """
        my_position = self._get_my_position(state)
        opponent_position = self._get_opponent_position(state)
        my_resources = self._get_my_resources(state)
        my_vp = 100 - proposal.offered_vp

        # Format the evaluation prompt
        prompt = SETTLEMENT_EVALUATION_PROMPT.format(
            turn_number=state.turn,
            risk_level=state.risk_level,
            cooperation_score=state.cooperation_score,
            your_position=my_position,
            opponent_position=opponent_position,
            your_resources=my_resources,
            offered_vp=proposal.offered_vp,
            your_vp=my_vp,
            argument=proposal.argument,
            is_final_offer="Yes" if is_final_offer else "No",
            persona_description=self.settlement_persona,
        )

        # Call LLM with structured output
        response = await generate_json(
            prompt=prompt,
            system_prompt=SETTLEMENT_EVALUATION_SYSTEM_PROMPT,
            schema=SETTLEMENT_EVALUATION_SCHEMA,
        )

        # Parse response
        action = response.get("action", "REJECT").upper()

        if action == "ACCEPT":
            return SettlementResponse(action="accept")
        elif action == "COUNTER" and not is_final_offer:
            counter_vp = response.get("counter_vp")
            counter_arg = response.get("counter_argument", "")
            if counter_vp is not None:
                # Ensure counter_vp is valid
                counter_vp = max(20, min(80, counter_vp))
                return SettlementResponse(
                    action="counter",
                    counter_vp=counter_vp,
                    counter_argument=counter_arg[:500] if counter_arg else None,
                )
        # Default to reject
        return SettlementResponse(
            action="reject",
            rejection_reason=response.get("rejection_reason", "Offer rejected."),
        )

    async def propose_settlement(self, state: GameState) -> SettlementProposal | None:
        """Optionally propose settlement based on strategy.

        Default implementation proposes settlement when in a favorable position
        and risk is elevated. Subclasses may override.

        This is async for interface consistency, even though deterministic
        opponents don't need async for this decision.

        Args:
            state: Current game state

        Returns:
            Settlement proposal, or None if not proposing
        """
        # Check if settlement is available
        if state.turn <= 4 or state.stability <= 2:
            return None

        # Default: don't propose unless overridden
        return None


class NashCalculator(DeterministicOpponent):
    """Pure game theorist - plays Nash equilibrium strategy.

    For most games in Brinksmanship, this means:
    - In Prisoner's Dilemma-like situations: defect (dominant strategy)
    - In Chicken: mixed strategy, but favor holding firm when ahead
    - In Stag Hunt: risk-dominant choice (defect/hare) unless cooperation is high

    Settlement: Accepts if offer >= position-fair value
    """

    settlement_persona: ClassVar[str] = """A pure game theorist who evaluates
    offers based on expected value calculations. Accepts fair offers but
    recognizes that continued play has variance costs. Values predictability
    and rational outcomes over emotional considerations."""

    def __init__(self) -> None:
        """Initialize NashCalculator opponent."""
        super().__init__(name="Nash Calculator")

    async def choose_action(
        self, state: GameState, available_actions: list[Action]
    ) -> Action:
        """Choose action based on Nash equilibrium reasoning.

        In most 2x2 games encountered:
        - If defection is dominant (PD, Security Dilemma): defect
        - If position is strong: maintain pressure
        - If risk is very high (>=8): consider de-escalation for self-preservation

        Args:
            state: Current game state
            available_actions: List of valid actions to choose from

        Returns:
            The chosen action
        """
        my_position = self._get_my_position(state)
        opponent_position = self._get_opponent_position(state)

        # Risk-aware Nash: at very high risk, survival matters more
        if state.risk_level >= 8:
            # Mutual destruction is worst outcome - consider de-escalation
            coop_actions = self._get_cooperative_actions(available_actions)
            if coop_actions:
                return random.choice(coop_actions)

        # Standard Nash reasoning: defection is typically dominant or risk-dominant
        # Position advantage reinforces this
        if my_position >= opponent_position:
            # Ahead or even: press advantage with competitive action
            return self._select_random_from_type(
                available_actions, ActionType.COMPETITIVE
            )
        else:
            # Behind: still defect (Nash), but less aggressively
            # 70% competitive, 30% cooperative (hedge)
            if random.random() < 0.7:
                return self._select_random_from_type(
                    available_actions, ActionType.COMPETITIVE
                )
            else:
                return self._select_random_from_type(
                    available_actions, ActionType.COOPERATIVE
                )

    async def propose_settlement(self, state: GameState) -> SettlementProposal | None:
        """Propose settlement when position advantage is clear.

        Nash reasoning: lock in gains when ahead.
        """
        if state.turn <= 4 or state.stability <= 2:
            return None

        my_position = self._get_my_position(state)
        opponent_position = self._get_opponent_position(state)

        # Propose when clearly ahead and risk is non-trivial
        if my_position > opponent_position + 1.0 and state.risk_level >= 4:
            fair_vp = self.get_position_fair_vp(
                state, self._is_player_a if self._is_player_a is not None else False
            )
            return SettlementProposal(
                offered_vp=fair_vp,
                argument=(
                    "The current position advantage suggests this is a fair division. "
                    "Continued play introduces variance that benefits neither party. "
                    "A rational settlement now locks in expected value."
                ),
            )
        return None


class SecuritySeeker(DeterministicOpponent):
    """Spiral model actor - escalates only when threatened.

    Based on Jervis's Spiral Model: conflict arises from mutual fear and
    misperception. Prefers de-escalation and cooperation unless directly
    threatened.

    Strategic pattern:
    - Default to cooperative actions
    - Escalate only in response to opponent's competitive actions
    - De-escalate when opponent cooperates

    Settlement: Prefers settlement, accepts generous offers
    """

    settlement_persona: ClassVar[str] = """A security-focused actor who prefers
    stability over gains. Worries about spiral dynamics and mutual destruction.
    Willing to accept slightly unfavorable terms to achieve peace. Becomes
    defensive when threatened but doesn't initiate aggression."""

    def __init__(self) -> None:
        """Initialize SecuritySeeker opponent."""
        super().__init__(name="Security Seeker")

    async def choose_action(
        self, state: GameState, available_actions: list[Action]
    ) -> Action:
        """Choose action based on spiral model reasoning.

        - Default: cooperative
        - If opponent defected last turn: escalate defensively
        - If risk is high: prioritize de-escalation

        Args:
            state: Current game state
            available_actions: List of valid actions to choose from

        Returns:
            The chosen action
        """
        opponent_prev = self._get_opponent_previous_type(state)

        # High risk: always try to de-escalate
        if state.risk_level >= 7:
            return self._select_random_from_type(
                available_actions, ActionType.COOPERATIVE
            )

        # Respond to opponent's last action
        if opponent_prev == ActionType.COMPETITIVE:
            # Defensive escalation - but not always
            # 60% respond competitively, 40% try to break the spiral
            if random.random() < 0.6:
                return self._select_random_from_type(
                    available_actions, ActionType.COMPETITIVE
                )
            else:
                return self._select_random_from_type(
                    available_actions, ActionType.COOPERATIVE
                )
        else:
            # Opponent cooperated or first turn: cooperate
            return self._select_random_from_type(
                available_actions, ActionType.COOPERATIVE
            )

    async def propose_settlement(self, state: GameState) -> SettlementProposal | None:
        """Propose settlement when risk is elevated.

        Security seekers value stability - propose when dangerous.
        """
        if state.turn <= 4 or state.stability <= 2:
            return None

        # Propose when risk is concerning
        if state.risk_level >= 5:
            fair_vp = self.get_position_fair_vp(
                state, self._is_player_a if self._is_player_a is not None else False
            )
            # Willing to accept slightly less for peace
            offer_vp = max(20, fair_vp - 5)
            return SettlementProposal(
                offered_vp=offer_vp,
                argument=(
                    "The escalating risk threatens us both. Neither side benefits "
                    "from mutual destruction. I propose a fair settlement that "
                    "acknowledges our positions while ending this dangerous spiral."
                ),
            )
        return None


class Opportunist(DeterministicOpponent):
    """Deterrence model actor - probes for weakness, exploits when possible.

    Based on Jervis's Deterrence Model: some actors genuinely seek expansion.
    Weakness invites predation.

    Strategic pattern:
    - Defect when opponent appears weak (low position or resources)
    - Defect when ahead in position
    - Cooperate tactically to set up exploitation

    Settlement: Rejects unless dominant, exploits weak arguments
    """

    settlement_persona: ClassVar[str] = """A calculating opportunist who sees
    negotiation as another arena for advantage. Rejects offers that don't
    reflect dominance. Looks for weakness in arguments to exploit. Only
    accepts settlements that lock in clear victories."""

    def __init__(self) -> None:
        """Initialize Opportunist opponent."""
        super().__init__(name="Opportunist")

    async def choose_action(
        self, state: GameState, available_actions: list[Action]
    ) -> Action:
        """Choose action based on deterrence model reasoning.

        - Probe for weakness: defect when ahead or opponent seems weak
        - If opponent shows strength: tactical cooperation

        Args:
            state: Current game state
            available_actions: List of valid actions to choose from

        Returns:
            The chosen action
        """
        my_position = self._get_my_position(state)
        opponent_position = self._get_opponent_position(state)

        # Check if we're ahead
        position_advantage = my_position - opponent_position

        if position_advantage >= 1.0:
            # Clearly ahead: press the advantage
            return self._select_random_from_type(
                available_actions, ActionType.COMPETITIVE
            )
        elif position_advantage <= -1.5:
            # Significantly behind: tactical cooperation to regroup
            if random.random() < 0.6:
                return self._select_random_from_type(
                    available_actions, ActionType.COOPERATIVE
                )
            else:
                return self._select_random_from_type(
                    available_actions, ActionType.COMPETITIVE
                )
        else:
            # Roughly even: probe for weakness
            # 70% competitive, 30% cooperative (feel out opponent)
            if random.random() < 0.7:
                return self._select_random_from_type(
                    available_actions, ActionType.COMPETITIVE
                )
            else:
                return self._select_random_from_type(
                    available_actions, ActionType.COOPERATIVE
                )

    async def propose_settlement(self, state: GameState) -> SettlementProposal | None:
        """Propose settlement only when clearly dominant.

        Opportunists only settle to lock in clear victories.
        """
        if state.turn <= 4 or state.stability <= 2:
            return None

        my_position = self._get_my_position(state)
        opponent_position = self._get_opponent_position(state)

        # Only propose when significantly ahead
        if my_position > opponent_position + 2.0:
            fair_vp = self.get_position_fair_vp(
                state, self._is_player_a if self._is_player_a is not None else False
            )
            # Demand more than fair due to dominance
            offer_vp = min(80, fair_vp + 5)
            return SettlementProposal(
                offered_vp=offer_vp,
                argument=(
                    "Your position has deteriorated significantly. This offer "
                    "reflects the reality on the ground. Accept now or face "
                    "further losses. The terms will only get worse from here."
                ),
            )
        return None


class Erratic(DeterministicOpponent):
    """Unpredictable actor - randomly mixes strategies.

    Represents an opponent whose behavior cannot be modeled or predicted.
    Useful for testing robustness of strategies.

    Strategic pattern:
    - ~40% cooperative, 60% competitive bias
    - No consistent response to opponent actions
    - Random settlement behavior

    Settlement: Unpredictable acceptance
    """

    settlement_persona: ClassVar[str] = """An unpredictable actor whose
    decision-making defies rational analysis. May accept or reject based on
    factors that seem arbitrary. Sometimes generous, sometimes demanding.
    Decisions feel impulsive rather than calculated."""

    def __init__(self) -> None:
        """Initialize Erratic opponent."""
        super().__init__(name="Erratic")

    async def choose_action(
        self, state: GameState, available_actions: list[Action]
    ) -> Action:
        """Choose action randomly with competitive bias.

        ~40% cooperative, 60% competitive - no strategy, pure chaos.

        Args:
            state: Current game state
            available_actions: List of valid actions to choose from

        Returns:
            The chosen action
        """
        # 40% cooperative, 60% competitive
        if random.random() < 0.4:
            return self._select_random_from_type(
                available_actions, ActionType.COOPERATIVE
            )
        else:
            return self._select_random_from_type(
                available_actions, ActionType.COMPETITIVE
            )

    async def propose_settlement(self, state: GameState) -> SettlementProposal | None:
        """Randomly propose settlement.

        Erratic behavior includes random settlement proposals.
        """
        if state.turn <= 4 or state.stability <= 2:
            return None

        # 20% chance to propose each turn
        if random.random() < 0.2:
            fair_vp = self.get_position_fair_vp(
                state, self._is_player_a if self._is_player_a is not None else False
            )
            # Random deviation from fair
            deviation = random.randint(-15, 15)
            offer_vp = max(20, min(80, fair_vp + deviation))
            return SettlementProposal(
                offered_vp=offer_vp,
                argument=(
                    "Let's end this now. I'm tired of the back and forth. "
                    "Take it or leave it - who knows what I'll do next."
                ),
            )
        return None


class TitForTat(DeterministicOpponent):
    """Reciprocator - Axelrod's famous strategy.

    From Axelrod's tournaments: cooperate on first move, then mirror
    opponent's last action.

    Key properties:
    - Nice: never defects first
    - Retaliatory: responds to defection with defection
    - Forgiving: returns to cooperation if opponent does
    - Clear: behavior is predictable and easy to understand

    Settlement: Accepts fair offers from cooperative opponents
    """

    settlement_persona: ClassVar[str] = """A fair-minded reciprocator who
    values cooperation but won't be exploited. Willing to settle with
    opponents who have shown good faith. Suspicious of offers from those
    who have defected. Values reciprocity and fairness in negotiations."""

    def __init__(self) -> None:
        """Initialize TitForTat opponent."""
        super().__init__(name="Tit for Tat")

    async def choose_action(
        self, state: GameState, available_actions: list[Action]
    ) -> Action:
        """Choose action using Tit-for-Tat strategy.

        - First turn: cooperate
        - Subsequent turns: mirror opponent's last action type

        Args:
            state: Current game state
            available_actions: List of valid actions to choose from

        Returns:
            The chosen action
        """
        opponent_prev = self._get_opponent_previous_type(state)

        # First turn or opponent hasn't acted: cooperate
        if opponent_prev is None:
            return self._select_random_from_type(
                available_actions, ActionType.COOPERATIVE
            )

        # Mirror opponent's last action
        if opponent_prev == ActionType.COOPERATIVE:
            return self._select_random_from_type(
                available_actions, ActionType.COOPERATIVE
            )
        else:
            return self._select_random_from_type(
                available_actions, ActionType.COMPETITIVE
            )

    async def propose_settlement(self, state: GameState) -> SettlementProposal | None:
        """Propose settlement when cooperation has been established.

        Tit-for-Tat values mutual cooperation - propose when it's working.
        """
        if state.turn <= 4 or state.stability <= 2:
            return None

        # Propose when cooperation is high and risk is moderate
        if state.cooperation_score >= 6 and state.risk_level >= 3:
            fair_vp = self.get_position_fair_vp(
                state, self._is_player_a if self._is_player_a is not None else False
            )
            return SettlementProposal(
                offered_vp=fair_vp,
                argument=(
                    "We've shown we can work together. This fair settlement "
                    "reflects our mutual cooperation and positions. Let's "
                    "formalize what we've built rather than risk destroying it."
                ),
            )
        return None


class GrimTrigger(DeterministicOpponent):
    """Punisher - cooperates until betrayed, then defects forever.

    A harsh strategy that enforces cooperation through the threat of
    permanent retaliation. Once triggered, never forgives.

    Strategic pattern:
    - Cooperate as long as opponent has never defected
    - After any defection: defect forever
    - No forgiveness, no second chances

    Settlement: Never accepts after betrayal
    """

    settlement_persona: ClassVar[str] = """A stern actor who values trust
    above all. Willing to cooperate and settle fairly with trustworthy
    opponents. Once betrayed, will never forgive - views any settlement
    offer after betrayal as an attempt at manipulation. Holds grudges
    permanently."""

    def __init__(self) -> None:
        """Initialize GrimTrigger opponent."""
        super().__init__(name="Grim Trigger")
        self._triggered: bool = False

    def receive_result(self, result: ActionResult) -> None:
        """Check if opponent defected and trigger punishment mode.

        Args:
            result: The outcome of the turn
        """
        # Determine which action was opponent's
        if self._is_player_a:
            opponent_action = result.action_b
        else:
            opponent_action = result.action_a

        # Check for betrayal
        if opponent_action == ActionType.COMPETITIVE:
            self._triggered = True

    async def choose_action(
        self, state: GameState, available_actions: list[Action]
    ) -> Action:
        """Choose action using Grim Trigger strategy.

        - If never triggered: cooperate
        - If triggered: defect forever

        Args:
            state: Current game state
            available_actions: List of valid actions to choose from

        Returns:
            The chosen action
        """
        # Check opponent's previous action to update trigger state
        opponent_prev = self._get_opponent_previous_type(state)
        if opponent_prev == ActionType.COMPETITIVE:
            self._triggered = True

        if self._triggered:
            # Betrayed: defect forever
            return self._select_random_from_type(
                available_actions, ActionType.COMPETITIVE
            )
        else:
            # Trust not broken: cooperate
            return self._select_random_from_type(
                available_actions, ActionType.COOPERATIVE
            )

    async def evaluate_settlement(
        self,
        proposal: SettlementProposal,
        state: GameState,
        is_final_offer: bool,
    ) -> SettlementResponse:
        """Evaluate settlement - auto-reject if triggered.

        After betrayal, GrimTrigger never accepts settlement.
        """
        if self._triggered:
            return SettlementResponse(
                action="reject",
                rejection_reason=(
                    "You betrayed my trust. There will be no negotiation. "
                    "No settlement. Only consequences."
                ),
            )
        # If not triggered, use normal LLM evaluation
        return await super().evaluate_settlement(proposal, state, is_final_offer)

    async def propose_settlement(self, state: GameState) -> SettlementProposal | None:
        """Propose settlement only if trust is intact.

        GrimTrigger proposes when cooperation is working well.
        """
        if state.turn <= 4 or state.stability <= 2:
            return None

        # Never propose after trigger
        if self._triggered:
            return None

        # Propose when cooperation is high
        if state.cooperation_score >= 7:
            fair_vp = self.get_position_fair_vp(
                state, self._is_player_a if self._is_player_a is not None else False
            )
            return SettlementProposal(
                offered_vp=fair_vp,
                argument=(
                    "Our cooperation has been exemplary. I propose we seal "
                    "this partnership with a fair settlement. Trust maintained "
                    "is trust rewarded. But know this - betrayal would change "
                    "everything."
                ),
            )
        return None


# Export all opponent classes
__all__ = [
    "DeterministicOpponent",
    "NashCalculator",
    "SecuritySeeker",
    "Opportunist",
    "Erratic",
    "TitForTat",
    "GrimTrigger",
]
