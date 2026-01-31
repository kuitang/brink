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

from brinksmanship.models.actions import Action, ActionType
from brinksmanship.models.state import GameState
from brinksmanship.opponents.base import (
    Opponent,
    SettlementProposal,
    SettlementResponse,
)

if TYPE_CHECKING:
    from brinksmanship.models.state import ActionResult


class DeterministicOpponent(Opponent):
    """Base class for deterministic opponents.

    Strategic actions and settlement evaluation are purely deterministic
    (testable, reproducible). No LLM calls required.
    """

    # Subclasses can override these for settlement evaluation
    # Generous thresholds to encourage settlement (target >= 70%)
    settlement_threshold: ClassVar[float] = -15.0  # Accept if offer within 15 VP of fair
    counter_threshold: ClassVar[float] = -25.0  # Counter if within 25 VP
    counter_adjustment: ClassVar[float] = 0.0  # Counter at fair value

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
        if self._is_player_a:
            return state.position_a
        return state.position_b

    def _get_opponent_position(self, state: GameState) -> float:
        """Get the human player's position from state."""
        if self._is_player_a:
            return state.position_b
        return state.position_a

    def _get_my_resources(self, state: GameState) -> float:
        """Get this opponent's resources from state."""
        if self._is_player_a:
            return state.resources_a
        return state.resources_b

    def _get_opponent_previous_type(self, state: GameState) -> ActionType | None:
        """Get the human player's previous action type."""
        if self._is_player_a:
            return state.previous_type_b
        return state.previous_type_a

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

    async def choose_action(self, state: GameState, available_actions: list[Action]) -> Action:
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
        """Evaluate a settlement proposal using simple deterministic rules.

        Accept if offer is within threshold of fair value.
        """
        my_vp = 100 - proposal.offered_vp
        fair_vp = self.get_position_fair_vp(state, self._is_player_a or False)
        vp_diff = my_vp - fair_vp

        if vp_diff >= self.settlement_threshold:
            return SettlementResponse(action="accept")

        if not is_final_offer and vp_diff >= self.counter_threshold:
            counter_vp = max(20, min(80, int(fair_vp + self.counter_adjustment)))
            return SettlementResponse(
                action="counter",
                counter_vp=counter_vp,
                counter_argument="Consider this fair counter-offer.",
            )

        return SettlementResponse(
            action="reject",
            rejection_reason="This offer is unacceptable.",
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

    Settlement: Accepts fair offers (within 5 VP of position-fair value)
    """

    # Nash: accepts fair offers, values rationality
    settlement_threshold: ClassVar[float] = -5.0  # Accept if within 5 VP of fair
    counter_threshold: ClassVar[float] = -15.0  # Counter if within 15 VP
    counter_adjustment: ClassVar[float] = 0.0  # Counter at fair value

    def __init__(self) -> None:
        """Initialize NashCalculator opponent."""
        super().__init__(name="Nash Calculator")

    async def choose_action(self, state: GameState, available_actions: list[Action]) -> Action:
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

        # Risk-aware Nash: at high risk, survival probability matters
        # Start de-escalating at risk 6, always de-escalate at risk 8+
        if state.risk_level >= 8:
            coop_actions = self._get_cooperative_actions(available_actions)
            if coop_actions:
                return random.choice(coop_actions)
        elif state.risk_level >= 6:
            # Elevated risk: 60% chance to de-escalate
            if random.random() < 0.6:
                return self._select_random_from_type(available_actions, ActionType.COOPERATIVE)

        # Standard Nash reasoning: defection is typically dominant or risk-dominant
        # Position advantage reinforces this
        if my_position >= opponent_position:
            # Ahead or even: press advantage with competitive action
            return self._select_random_from_type(available_actions, ActionType.COMPETITIVE)
        else:
            # Behind: still defect (Nash), but less aggressively
            # 60% competitive, 40% cooperative (hedge)
            if random.random() < 0.6:
                return self._select_random_from_type(available_actions, ActionType.COMPETITIVE)
            else:
                return self._select_random_from_type(available_actions, ActionType.COOPERATIVE)

    async def propose_settlement(self, state: GameState) -> SettlementProposal | None:
        """Propose settlement when position advantage is clear or risk is high."""
        if state.turn <= 4 or state.stability <= 2:
            return None

        my_position = self._get_my_position(state)
        opponent_position = self._get_opponent_position(state)

        clearly_ahead = my_position > opponent_position + 1.0 and state.risk_level >= 3
        high_risk = state.risk_level >= 5

        if not (clearly_ahead or high_risk):
            return None

        fair_vp = self.get_position_fair_vp(state, self._is_player_a or False)
        return SettlementProposal(
            offered_vp=fair_vp,
            argument=(
                "The current position advantage suggests this is a fair division. "
                "Continued play introduces variance that benefits neither party. "
                "A rational settlement now locks in expected value."
            ),
        )


class SecuritySeeker(DeterministicOpponent):
    """Spiral model actor - escalates only when threatened.

    Based on Jervis's Spiral Model: conflict arises from mutual fear and
    misperception. Prefers de-escalation and cooperation unless directly
    threatened.

    Strategic pattern:
    - Default to cooperative actions
    - Escalate only in response to opponent's competitive actions
    - De-escalate when opponent cooperates

    Settlement: Strongly prefers settlement, accepts unfavorable offers for peace
    """

    # Security seeker: values stability, accepts even unfavorable offers
    settlement_threshold: ClassVar[float] = -15.0  # Accept up to 15 VP below fair
    counter_threshold: ClassVar[float] = -25.0  # Counter even bad offers
    counter_adjustment: ClassVar[float] = -5.0  # Counter below fair (concedes)

    def __init__(self) -> None:
        """Initialize SecuritySeeker opponent."""
        super().__init__(name="Security Seeker")

    async def choose_action(self, state: GameState, available_actions: list[Action]) -> Action:
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
            return self._select_random_from_type(available_actions, ActionType.COOPERATIVE)

        # Respond to opponent's last action
        if opponent_prev == ActionType.COMPETITIVE:
            # Defensive escalation - but not always
            # 60% respond competitively, 40% try to break the spiral
            if random.random() < 0.6:
                return self._select_random_from_type(available_actions, ActionType.COMPETITIVE)
            else:
                return self._select_random_from_type(available_actions, ActionType.COOPERATIVE)
        else:
            # Opponent cooperated or first turn: cooperate
            return self._select_random_from_type(available_actions, ActionType.COOPERATIVE)

    async def propose_settlement(self, state: GameState) -> SettlementProposal | None:
        """Propose settlement proactively to ensure stability."""
        if state.turn <= 4 or state.stability <= 2:
            return None

        if state.risk_level < 3 and state.turn < 7:
            return None

        fair_vp = self.get_position_fair_vp(state, self._is_player_a or False)
        offer_vp = max(20, fair_vp - 5)  # Willing to accept slightly less for peace
        return SettlementProposal(
            offered_vp=offer_vp,
            argument=(
                "The escalating risk threatens us both. Neither side benefits "
                "from mutual destruction. I propose a fair settlement that "
                "acknowledges our positions while ending this dangerous spiral."
            ),
        )


class Opportunist(DeterministicOpponent):
    """Deterrence model actor - probes for weakness, exploits when possible.

    Based on Jervis's Deterrence Model: some actors genuinely seek expansion.
    Weakness invites predation.

    Strategic pattern:
    - Defect when opponent appears weak (low position or resources)
    - Defect when ahead in position
    - Cooperate tactically to set up exploitation

    Settlement: Only accepts if offer is clearly advantageous
    """

    # Opportunist: demanding, only accepts advantageous offers
    settlement_threshold: ClassVar[float] = 5.0  # Only accept if 5+ VP above fair
    counter_threshold: ClassVar[float] = -5.0  # Counter if close to fair
    counter_adjustment: ClassVar[float] = 10.0  # Counter well above fair (demands)

    def __init__(self) -> None:
        """Initialize Opportunist opponent."""
        super().__init__(name="Opportunist")

    async def choose_action(self, state: GameState, available_actions: list[Action]) -> Action:
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

        # Risk-aware: even opportunists fear mutual destruction
        if state.risk_level >= 7:
            # Very high risk: survival mode
            return self._select_random_from_type(available_actions, ActionType.COOPERATIVE)
        elif state.risk_level >= 5:
            # Elevated risk: 40% chance to de-escalate
            if random.random() < 0.4:
                return self._select_random_from_type(available_actions, ActionType.COOPERATIVE)

        # Check if we're ahead
        position_advantage = my_position - opponent_position

        if position_advantage >= 1.0:
            # Clearly ahead: press the advantage
            return self._select_random_from_type(available_actions, ActionType.COMPETITIVE)
        elif position_advantage <= -1.5:
            # Significantly behind: tactical cooperation to regroup
            if random.random() < 0.6:
                return self._select_random_from_type(available_actions, ActionType.COOPERATIVE)
            else:
                return self._select_random_from_type(available_actions, ActionType.COMPETITIVE)
        else:
            # Roughly even: probe for weakness
            # 60% competitive, 40% cooperative (feel out opponent)
            if random.random() < 0.6:
                return self._select_random_from_type(available_actions, ActionType.COMPETITIVE)
            else:
                return self._select_random_from_type(available_actions, ActionType.COOPERATIVE)

    async def propose_settlement(self, state: GameState) -> SettlementProposal | None:
        """Propose settlement when dominant, or at high risk to preserve gains."""
        if state.turn <= 4 or state.stability <= 2:
            return None

        my_position = self._get_my_position(state)
        opponent_position = self._get_opponent_position(state)

        significantly_ahead = my_position > opponent_position + 2.0
        high_risk_advantage = state.risk_level >= 6 and my_position >= opponent_position

        if not (significantly_ahead or high_risk_advantage):
            return None

        fair_vp = self.get_position_fair_vp(state, self._is_player_a or False)
        offer_vp = min(80, fair_vp + 5)  # Demand more than fair
        return SettlementProposal(
            offered_vp=offer_vp,
            argument=(
                "Your position has deteriorated significantly. This offer "
                "reflects the reality on the ground. Accept now or face "
                "further losses. The terms will only get worse from here."
            ),
        )


class Erratic(DeterministicOpponent):
    """Unpredictable actor - randomly mixes strategies.

    Represents an opponent whose behavior cannot be modeled or predicted.
    Useful for testing robustness of strategies.

    Strategic pattern:
    - ~40% cooperative, 60% competitive bias
    - No consistent response to opponent actions
    - Random settlement behavior

    Settlement: Random acceptance (50% at fair, random threshold)
    """

    def __init__(self) -> None:
        """Initialize Erratic opponent."""
        super().__init__(name="Erratic")

    async def choose_action(self, state: GameState, available_actions: list[Action]) -> Action:
        """Choose action randomly with competitive bias.

        ~40% cooperative, 60% competitive - but erratic actors also
        have survival instincts at extreme risk.

        Args:
            state: Current game state
            available_actions: List of valid actions to choose from

        Returns:
            The chosen action
        """
        # Survival instinct at very high risk
        if state.risk_level >= 8:
            # 70% chance to cooperate at extreme risk
            if random.random() < 0.7:
                return self._select_random_from_type(available_actions, ActionType.COOPERATIVE)

        # Normal erratic behavior: 40% cooperative, 60% competitive
        if random.random() < 0.4:
            return self._select_random_from_type(available_actions, ActionType.COOPERATIVE)
        else:
            return self._select_random_from_type(available_actions, ActionType.COMPETITIVE)

    async def evaluate_settlement(
        self,
        proposal: SettlementProposal,
        state: GameState,
        is_final_offer: bool,
    ) -> SettlementResponse:
        """Evaluate settlement randomly (erratic behavior).

        ~40% accept, ~30% counter, ~30% reject regardless of fairness.
        """
        roll = random.random()
        if roll < 0.4:
            # 40% chance to accept
            return SettlementResponse(action="accept")
        elif roll < 0.7 and not is_final_offer:
            # 30% chance to counter with random VP
            counter_vp = random.randint(30, 70)
            return SettlementResponse(
                action="counter",
                counter_vp=counter_vp,
                counter_argument="Let's try this instead. Or not. Whatever.",
            )
        else:
            # 30% chance to reject
            return SettlementResponse(
                action="reject",
                rejection_reason="I don't like it. Don't ask me why.",
            )

    async def propose_settlement(self, state: GameState) -> SettlementProposal | None:
        """Randomly propose settlement (20% chance each turn)."""
        if state.turn <= 4 or state.stability <= 2:
            return None

        if random.random() >= 0.2:
            return None

        fair_vp = self.get_position_fair_vp(state, self._is_player_a or False)
        deviation = random.randint(-15, 15)
        offer_vp = max(20, min(80, fair_vp + deviation))
        return SettlementProposal(
            offered_vp=offer_vp,
            argument=(
                "Let's end this now. I'm tired of the back and forth. "
                "Take it or leave it - who knows what I'll do next."
            ),
        )


class TitForTat(DeterministicOpponent):
    """Reciprocator - Axelrod's famous strategy.

    From Axelrod's tournaments: cooperate on first move, then mirror
    opponent's last action.

    Key properties:
    - Nice: never defects first
    - Retaliatory: responds to defection with defection
    - Forgiving: returns to cooperation if opponent does
    - Clear: behavior is predictable and easy to understand

    Settlement: Accepts fair offers, more generous when cooperation is high
    """

    # TitForTat: fair-minded, accepts fair offers
    settlement_threshold: ClassVar[float] = -5.0  # Accept within 5 VP of fair
    counter_threshold: ClassVar[float] = -15.0  # Counter if within 15 VP
    counter_adjustment: ClassVar[float] = 0.0  # Counter at fair value

    def __init__(self) -> None:
        """Initialize TitForTat opponent."""
        super().__init__(name="Tit for Tat")

    async def choose_action(self, state: GameState, available_actions: list[Action]) -> Action:
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
            return self._select_random_from_type(available_actions, ActionType.COOPERATIVE)

        # Mirror opponent's last action
        if opponent_prev == ActionType.COOPERATIVE:
            return self._select_random_from_type(available_actions, ActionType.COOPERATIVE)
        else:
            return self._select_random_from_type(available_actions, ActionType.COMPETITIVE)

    async def evaluate_settlement(
        self,
        proposal: SettlementProposal,
        state: GameState,
        is_final_offer: bool,
    ) -> SettlementResponse:
        """Evaluate settlement with cooperation-aware thresholds.

        TitForTat becomes more generous when cooperation has been high.
        """
        # Adjust threshold based on cooperation score
        coop_bonus = max(0, (state.cooperation_score - 5) * 2)  # +2 per point above 5
        adjusted_threshold = self.settlement_threshold - coop_bonus

        my_vp = 100 - proposal.offered_vp
        fair_vp = self.get_position_fair_vp(state, self._is_player_a if self._is_player_a is not None else False)
        vp_diff = my_vp - fair_vp

        # Risk and turn bonuses from parent
        risk_bonus = max(0, (state.risk_level - 4) * 2)
        turn_bonus = max(0, (state.turn - 6) * 1)
        effective_threshold = adjusted_threshold - risk_bonus - turn_bonus

        if vp_diff >= effective_threshold:
            return SettlementResponse(action="accept")
        elif not is_final_offer and vp_diff >= self.counter_threshold - risk_bonus:
            counter_vp = max(20, min(80, int(fair_vp + self.counter_adjustment)))
            return SettlementResponse(
                action="counter",
                counter_vp=counter_vp,
                counter_argument="We've cooperated well. Let's find a fair middle ground.",
            )
        else:
            return SettlementResponse(
                action="reject",
                rejection_reason="This doesn't reflect our mutual cooperation.",
            )

    async def propose_settlement(self, state: GameState) -> SettlementProposal | None:
        """Propose settlement when cooperation has been established."""
        if state.turn <= 4 or state.stability <= 2:
            return None

        good_cooperation = state.cooperation_score >= 5 and state.risk_level >= 2
        late_game = state.turn >= 8

        if not (good_cooperation or late_game):
            return None

        fair_vp = self.get_position_fair_vp(state, self._is_player_a or False)
        return SettlementProposal(
            offered_vp=fair_vp,
            argument=(
                "We've shown we can work together. This fair settlement "
                "reflects our mutual cooperation and positions. Let's "
                "formalize what we've built rather than risk destroying it."
            ),
        )


class GrimTrigger(DeterministicOpponent):
    """Punisher - cooperates until betrayed, then defects forever.

    A harsh strategy that enforces cooperation through the threat of
    permanent retaliation. Once triggered, never forgives.

    Strategic pattern:
    - Cooperate as long as opponent has never defected
    - After any defection: defect forever
    - No forgiveness, no second chances

    Settlement: Very generous when trust intact, never accepts after betrayal
    """

    # GrimTrigger: generous to trustworthy partners, harsh to betrayers
    settlement_threshold: ClassVar[float] = -10.0  # Accept up to 10 VP below fair
    counter_threshold: ClassVar[float] = -20.0  # Counter even unfavorable offers
    counter_adjustment: ClassVar[float] = 0.0  # Counter at fair value

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
        opponent_action = result.action_b if self._is_player_a else result.action_a

        # Check for betrayal
        if opponent_action == ActionType.COMPETITIVE:
            self._triggered = True

    async def choose_action(self, state: GameState, available_actions: list[Action]) -> Action:
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
            # Betrayed, but self-preservation overrides at extreme risk
            if state.risk_level >= 8:
                # Survival instinct: 70% de-escalate at extreme risk
                if random.random() < 0.7:
                    return self._select_random_from_type(available_actions, ActionType.COOPERATIVE)
            # Otherwise, defect (punishment mode)
            return self._select_random_from_type(available_actions, ActionType.COMPETITIVE)
        else:
            # Trust not broken: cooperate
            return self._select_random_from_type(available_actions, ActionType.COOPERATIVE)

    async def evaluate_settlement(
        self,
        proposal: SettlementProposal,
        state: GameState,
        is_final_offer: bool,
    ) -> SettlementResponse:
        """Evaluate settlement - harsh after betrayal, but self-preserving at extreme risk."""
        if not self._triggered:
            return await super().evaluate_settlement(proposal, state, is_final_offer)

        # Self-preservation: accept fair offers at extreme risk
        if state.risk_level >= 7:
            my_vp = 100 - proposal.offered_vp
            fair_vp = self.get_position_fair_vp(state, self._is_player_a or False)
            if my_vp >= fair_vp - 5:
                return SettlementResponse(action="accept")

        return SettlementResponse(
            action="reject",
            rejection_reason=("You betrayed my trust. There will be no negotiation. No settlement. Only consequences."),
        )

    async def propose_settlement(self, state: GameState) -> SettlementProposal | None:
        """Propose settlement only if trust is intact."""
        if state.turn <= 4 or state.stability <= 2 or self._triggered:
            return None

        good_cooperation = state.cooperation_score >= 5
        trust_held_long = state.turn >= 8

        if not (good_cooperation or trust_held_long):
            return None

        fair_vp = self.get_position_fair_vp(state, self._is_player_a or False)
        return SettlementProposal(
            offered_vp=fair_vp,
            argument=(
                "Our cooperation has been exemplary. I propose we seal "
                "this partnership with a fair settlement. Trust maintained "
                "is trust rewarded. But know this - betrayal would change "
                "everything."
            ),
        )


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
