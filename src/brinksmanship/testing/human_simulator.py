"""Human Simulator for Brinksmanship playtesting.

This module provides a simulated human player that makes realistic (sometimes
suboptimal) decisions based on a generated persona. Used for automated playtesting
to ensure the game is engaging for real human players.

See ENGINEERING_DESIGN.md Milestone 5.1 for specification.
"""

import random
from typing import Literal

from pydantic import BaseModel, Field

from brinksmanship.llm import generate_json
from brinksmanship.models import (
    Action,
    ActionType,
    GameState,
    get_action_menu,
)
from brinksmanship.opponents.base import (
    Opponent,
    SettlementProposal as BaseSettlementProposal,
    SettlementResponse as BaseSettlementResponse,
)
from brinksmanship.prompts import (
    HUMAN_ACTION_SELECTION_PROMPT,
    HUMAN_PERSONA_GENERATION_PROMPT,
    HUMAN_PERSONA_GENERATION_SYSTEM_PROMPT,
    HUMAN_SETTLEMENT_EVALUATION_PROMPT,
    HUMAN_SIMULATOR_SYSTEM_PROMPT,
    MISTAKE_CHECK_PROMPT,
    MISTAKE_CHECK_SYSTEM_PROMPT,
)


class HumanPersona(BaseModel):
    """A simulated human player persona.

    Personas capture the behavioral characteristics that influence how a
    simulated human makes decisions. They are generated fresh for each
    playtest session to ensure diversity.

    Attributes:
        risk_tolerance: Approach to risky situations
        sophistication: Strategic understanding level
        emotional_state: Current psychological state
        personality: General interaction style
        backstory: Brief background explaining the persona
        decision_style: How they approach choices
        triggers: Situations causing out-of-character behavior
    """

    risk_tolerance: Literal["risk_averse", "neutral", "risk_seeking"] = Field(
        description="How the player approaches risky situations"
    )
    sophistication: Literal["novice", "intermediate", "expert"] = Field(
        description="Strategic understanding level"
    )
    emotional_state: Literal["calm", "stressed", "desperate"] = Field(
        description="Current psychological state"
    )
    personality: Literal["cooperative", "competitive", "erratic"] = Field(
        description="General interaction style"
    )
    backstory: str = Field(
        description="Brief background explaining this persona's traits"
    )
    decision_style: str = Field(
        description="How they approach choices"
    )
    triggers: list[str] = Field(
        default_factory=list,
        description="Situations that cause out-of-character behavior"
    )

    def get_mistake_probability(self) -> float:
        """Calculate base mistake probability based on sophistication.

        Returns:
            Base probability of making a suboptimal choice (0.0 to 1.0)
        """
        base_rates = {
            "novice": 0.30,
            "intermediate": 0.15,
            "expert": 0.05,
        }
        return base_rates[self.sophistication]

    def get_emotional_modifier(self) -> float:
        """Get multiplier for mistake probability based on emotional state.

        Returns:
            Multiplier for mistake probability (1.0 to 2.0)
        """
        modifiers = {
            "calm": 1.0,
            "stressed": 1.5,
            "desperate": 2.0,
        }
        return modifiers[self.emotional_state]

    def get_risk_preference_bias(self) -> float:
        """Get bias toward risky vs safe actions.

        Returns:
            Bias value: negative favors safe, positive favors risky (-1.0 to 1.0)
        """
        biases = {
            "risk_averse": -0.3,
            "neutral": 0.0,
            "risk_seeking": 0.3,
        }
        return biases[self.risk_tolerance]

    def get_cooperation_bias(self) -> float:
        """Get bias toward cooperative vs competitive actions.

        Returns:
            Bias value: negative favors competitive, positive favors cooperative
        """
        biases = {
            "cooperative": 0.3,
            "competitive": -0.3,
            "erratic": 0.0,  # No consistent bias
        }
        return biases[self.personality]


class ActionSelection(BaseModel):
    """Result of the human simulator's action selection.

    Attributes:
        reasoning: The persona's thought process
        emotional_reaction: How they feel about the situation
        selected_action: Name of the chosen action
        confidence: How confident they are in the choice
    """

    reasoning: str
    emotional_reaction: str
    selected_action: str
    confidence: Literal["low", "medium", "high"]


class MistakeCheck(BaseModel):
    """Result of checking if a mistake should occur.

    Attributes:
        would_make_mistake: Whether to override the LLM's choice
        mistake_type: What kind of mistake to make
        explanation: Why this mistake would occur
    """

    would_make_mistake: bool
    mistake_type: Literal["impulsive", "overcautious", "vindictive", "overconfident"] | None
    explanation: str


class SettlementResponse(BaseModel):
    """Response to a settlement proposal.

    Attributes:
        reasoning: How the persona thinks about the offer
        emotional_response: How they feel about it
        decision: Accept, counter, or reject
        counter_vp: VP to counter with (if countering)
        counter_argument: Argument for counter (if countering)
        rejection_reason: Why rejected (if rejecting)
    """

    reasoning: str
    emotional_response: str
    decision: Literal["accept", "counter", "reject"]
    counter_vp: int | None = None
    counter_argument: str | None = None
    rejection_reason: str | None = None


class HumanSimulator(Opponent):
    """Simulates human player behavior for playtesting.

    The HumanSimulator generates diverse human personas and makes decisions
    that reflect realistic human play, including occasional mistakes and
    emotional reactions.

    Inherits from Opponent to provide a consistent interface for use in
    the game engine and playtesting framework.

    Example:
        >>> simulator = HumanSimulator(is_player_a=False)
        >>> persona = await simulator.generate_persona()
        >>> print(f"Playing as: {persona.backstory}")
        >>>
        >>> action = simulator.choose_action(
        ...     state=game_state,
        ...     available_actions=action_menu.all_actions(),
        ... )
        >>> print(f"Chose: {action.name}")
    """

    def __init__(
        self,
        persona: HumanPersona | None = None,
        is_player_a: bool = False,
    ):
        """Initialize the human simulator.

        Args:
            persona: Optional pre-defined persona. If None, generate_persona()
                    must be called before choose_action().
            is_player_a: Whether this simulator plays as Player A (default: False)
        """
        super().__init__(name="Human Simulator")
        self.persona = persona
        self.is_player_a = is_player_a
        self._turn_history: list[str] = []

    async def generate_persona(self) -> HumanPersona:
        """Generate a fresh human persona using LLM.

        Creates a new, randomly varied persona with coherent traits.
        The persona is stored in self.persona for subsequent action choices.

        Returns:
            The generated HumanPersona
        """
        result = await generate_json(
            prompt=HUMAN_PERSONA_GENERATION_PROMPT,
            system_prompt=HUMAN_PERSONA_GENERATION_SYSTEM_PROMPT,
        )

        self.persona = HumanPersona.model_validate(result)
        self._turn_history = []
        return self.persona

    def _format_opponent_intelligence(
        self, state: GameState, is_player_a: bool
    ) -> str:
        """Format opponent intelligence for the prompt.

        Args:
            state: Current game state
            is_player_a: Whether this simulator is player A

        Returns:
            Formatted string describing what we know about opponent
        """
        if is_player_a:
            info = state.player_a.information
            opponent_prev = state.previous_type_b
        else:
            info = state.player_b.information
            opponent_prev = state.previous_type_a

        pos_est, pos_unc = info.get_position_estimate(state.turn)
        res_est, res_unc = info.get_resources_estimate(state.turn)

        lines = []
        if info.known_position is not None:
            lines.append(
                f"- Position: Last known {info.known_position:.1f} "
                f"(turn {info.known_position_turn}), uncertainty +/-{pos_unc:.1f}"
            )
        else:
            lines.append(f"- Position: Unknown, estimate {pos_est:.1f} +/-{pos_unc:.1f}")

        if info.known_resources is not None:
            lines.append(
                f"- Resources: Last known {info.known_resources:.1f} "
                f"(turn {info.known_resources_turn}), uncertainty +/-{res_unc:.1f}"
            )
        else:
            lines.append(f"- Resources: Unknown, estimate {res_est:.1f} +/-{res_unc:.1f}")

        lines.append(f"- Last Action Type: {opponent_prev.value if opponent_prev else 'None'}")

        return "\n".join(lines)

    def _format_available_actions(self, actions: list[Action]) -> str:
        """Format available actions for the prompt.

        Args:
            actions: List of available actions

        Returns:
            Formatted string listing actions with their types and costs
        """
        lines = []
        for i, action in enumerate(actions, 1):
            type_label = "Cooperative" if action.action_type == ActionType.COOPERATIVE else "Competitive"
            cost_str = f" (costs {action.resource_cost} Resources)" if action.resource_cost > 0 else ""
            lines.append(f"{i}. {action.name} [{type_label}]{cost_str}")
            if action.description:
                lines.append(f"   {action.description}")
        return "\n".join(lines)

    def _format_history(self) -> str:
        """Format recent turn history.

        Returns:
            Formatted string of recent events
        """
        if not self._turn_history:
            return "No previous turns."
        return "\n".join(self._turn_history[-5:])  # Last 5 turns

    def _record_turn(self, action_a: ActionType, action_b: ActionType, turn: int) -> None:
        """Record a turn's outcome for history tracking.

        Args:
            action_a: Player A's action type
            action_b: Player B's action type
            turn: Turn number
        """
        a_code = "C" if action_a == ActionType.COOPERATIVE else "D"
        b_code = "C" if action_b == ActionType.COOPERATIVE else "D"
        self._turn_history.append(f"Turn {turn}: {a_code}{b_code}")

    async def choose_action(
        self,
        state: GameState,
        available_actions: list[Action],
    ) -> Action:
        """Choose an action based on human-like reasoning.

        Makes a decision as the simulated human persona, potentially including
        realistic mistakes based on sophistication and emotional state.

        This implements the Opponent interface.

        Args:
            state: Current game state
            available_actions: List of actions to choose from

        Returns:
            The selected Action

        Raises:
            ValueError: If no persona has been set
        """
        return await self._choose_action_async(state, available_actions)

    async def _choose_action_async(
        self,
        state: GameState,
        available_actions: list[Action],
        narrative: str = "",
    ) -> Action:
        """Async implementation of action selection.

        Args:
            state: Current game state
            available_actions: List of actions to choose from
            narrative: Optional narrative context for the decision

        Returns:
            The selected Action

        Raises:
            ValueError: If no persona has been set
        """
        if self.persona is None:
            raise ValueError("No persona set. Call generate_persona() first.")
        is_player_a = self.is_player_a

        # Get player state
        if is_player_a:
            player_position = state.position_a
            player_resources = state.resources_a
            previous_type = state.previous_type_a
            opponent_prev = state.previous_type_b
        else:
            player_position = state.position_b
            player_resources = state.resources_b
            previous_type = state.previous_type_b
            opponent_prev = state.previous_type_a

        # Format prompt
        prompt = HUMAN_ACTION_SELECTION_PROMPT.format(
            risk_tolerance=self.persona.risk_tolerance,
            sophistication=self.persona.sophistication,
            emotional_state=self.persona.emotional_state,
            personality=self.persona.personality,
            backstory=self.persona.backstory,
            decision_style=self.persona.decision_style,
            triggers=", ".join(self.persona.triggers),
            turn=state.turn,
            act=state.act,
            player_position=player_position,
            player_resources=player_resources,
            opponent_intelligence=self._format_opponent_intelligence(state, is_player_a),
            risk_level=state.risk_level,
            cooperation_score=state.cooperation_score,
            stability=state.stability,
            previous_type=previous_type.value if previous_type else "None (first turn)",
            opponent_previous_type=opponent_prev.value if opponent_prev else "None (first turn)",
            history=self._format_history(),
            narrative=narrative or "Standard turn progression.",
            available_actions=self._format_available_actions(available_actions),
        )

        # Get LLM's action selection
        result = await generate_json(
            prompt=prompt,
            system_prompt=HUMAN_SIMULATOR_SYSTEM_PROMPT,
        )

        selection = ActionSelection.model_validate(result)

        # Find the selected action
        selected_action = None
        for action in available_actions:
            if action.name.lower() == selection.selected_action.lower():
                selected_action = action
                break

        # If exact match failed, try fuzzy matching
        if selected_action is None:
            for action in available_actions:
                if selection.selected_action.lower() in action.name.lower():
                    selected_action = action
                    break

        # If still no match, check for mistakes and possibly override
        if selected_action is None:
            # LLM gave invalid action, apply mistake logic to pick something
            selected_action = await self._apply_mistake_fallback(
                state, available_actions, is_player_a
            )
        else:
            # Check if we should override with a "mistake"
            selected_action = await self._maybe_apply_mistake(
                state, available_actions, selected_action, is_player_a
            )

        return selected_action

    async def _maybe_apply_mistake(
        self,
        state: GameState,
        available_actions: list[Action],
        chosen_action: Action,
        is_player_a: bool,
    ) -> Action:
        """Potentially override the chosen action with a realistic mistake.

        Args:
            state: Current game state
            available_actions: All available actions
            chosen_action: The LLM's chosen action
            is_player_a: Whether this is player A

        Returns:
            Either the original action or a mistake action
        """
        # Calculate mistake probability
        base_prob = self.persona.get_mistake_probability()
        emotional_mod = self.persona.get_emotional_modifier()
        risk_mod = 1.3 if state.risk_level > 7 else 1.0

        final_prob = min(base_prob * emotional_mod * risk_mod, 0.7)  # Cap at 70%

        # Random check for mistake
        if random.random() > final_prob:
            return chosen_action  # No mistake

        # Get player position and opponent's last action
        if is_player_a:
            player_position = state.position_a
        else:
            player_position = state.position_b

        # Get opponent's previous action type
        opponent_previous_type = "unknown"
        if len(self._turn_history) >= 1:
            last = self._turn_history[-1]
            if "C" in last[1]:  # Second character is opponent's action
                opponent_previous_type = "cooperative"
            elif "D" in last[1]:
                opponent_previous_type = "competitive"

        # Format history for prompt
        history_str = ", ".join(self._turn_history[-3:]) if self._turn_history else "none"

        # Use LLM to determine mistake type
        mistake_prompt = MISTAKE_CHECK_PROMPT.format(
            risk_tolerance=self.persona.risk_tolerance,
            sophistication=self.persona.sophistication,
            emotional_state=self.persona.emotional_state,
            personality=self.persona.personality,
            triggers=", ".join(self.persona.triggers),
            turn=state.turn,
            risk_level=state.risk_level,
            player_position=player_position,
            opponent_previous_type=opponent_previous_type,
            history=history_str,
        )

        result = await generate_json(
            prompt=mistake_prompt,
            system_prompt=MISTAKE_CHECK_SYSTEM_PROMPT,
        )

        mistake = MistakeCheck.model_validate(result)

        if not mistake.would_make_mistake:
            return chosen_action

        # Apply the mistake
        return self._apply_mistake_type(
            mistake.mistake_type, available_actions, chosen_action
        )

    def _apply_mistake_type(
        self,
        mistake_type: str | None,
        available_actions: list[Action],
        current_choice: Action,
    ) -> Action:
        """Apply a specific type of mistake.

        Args:
            mistake_type: Type of mistake to make
            available_actions: All available actions
            current_choice: The original choice

        Returns:
            The mistake action
        """
        cooperative_actions = [
            a for a in available_actions if a.action_type == ActionType.COOPERATIVE
        ]
        competitive_actions = [
            a for a in available_actions if a.action_type == ActionType.COMPETITIVE
        ]

        if mistake_type == "impulsive":
            # Pick the most aggressive available action
            if competitive_actions:
                return random.choice(competitive_actions)

        elif mistake_type == "overcautious":
            # Pick the safest available action (cooperative, low cost)
            safe_actions = [
                a for a in cooperative_actions if a.resource_cost == 0
            ]
            if safe_actions:
                return random.choice(safe_actions)
            elif cooperative_actions:
                return random.choice(cooperative_actions)

        elif mistake_type == "vindictive":
            # Defect regardless of strategic merit
            if competitive_actions:
                return random.choice(competitive_actions)

        elif mistake_type == "overconfident":
            # Take a risky action even when it's not warranted
            risky_actions = [
                a for a in available_actions
                if a.action_type == ActionType.COMPETITIVE or a.resource_cost > 0
            ]
            if risky_actions:
                return random.choice(risky_actions)

        # Fallback: return original
        return current_choice

    async def _apply_mistake_fallback(
        self,
        state: GameState,
        available_actions: list[Action],
        is_player_a: bool,
    ) -> Action:
        """Select an action when the LLM gave an invalid response.

        Uses persona traits to guide selection.

        Args:
            state: Current game state
            available_actions: All available actions
            is_player_a: Whether this is player A

        Returns:
            A selected action based on persona traits
        """
        # Use persona biases to select
        coop_bias = self.persona.get_cooperation_bias()
        risk_bias = self.persona.get_risk_preference_bias()

        cooperative_actions = [
            a for a in available_actions if a.action_type == ActionType.COOPERATIVE
        ]
        competitive_actions = [
            a for a in available_actions if a.action_type == ActionType.COMPETITIVE
        ]

        # Decide cooperative vs competitive
        if self.persona.personality == "erratic":
            # Random choice
            use_coop = random.random() > 0.5
        else:
            # Bias toward personality preference
            use_coop = random.random() < (0.5 + coop_bias)

        if use_coop and cooperative_actions:
            return random.choice(cooperative_actions)
        elif competitive_actions:
            return random.choice(competitive_actions)
        else:
            return random.choice(available_actions)

    async def evaluate_settlement(
        self,
        proposal: BaseSettlementProposal,
        state: GameState,
        is_final_offer: bool,
    ) -> BaseSettlementResponse:
        """Evaluate a settlement proposal as this persona.

        Implements the Opponent interface.

        Args:
            proposal: The settlement proposal to evaluate
            state: Current game state
            is_final_offer: Whether this is a final offer (no counter possible)

        Returns:
            SettlementResponse with decision

        Raises:
            ValueError: If no persona has been set
        """
        return await self._evaluate_settlement_async(proposal, state, is_final_offer)

    async def _evaluate_settlement_async(
        self,
        proposal: BaseSettlementProposal,
        state: GameState,
        is_final_offer: bool,
    ) -> BaseSettlementResponse:
        """Async implementation of settlement evaluation.

        Args:
            proposal: The settlement proposal to evaluate
            state: Current game state
            is_final_offer: Whether this is a final offer (no counter possible)

        Returns:
            SettlementResponse with decision and reasoning

        Raises:
            ValueError: If no persona has been set
        """
        if self.persona is None:
            raise ValueError("No persona set. Call generate_persona() first.")

        # Calculate VP from proposal (proposal.offered_vp is what proposer wants)
        opponent_vp = proposal.offered_vp
        your_vp = 100 - opponent_vp
        argument = proposal.argument

        if self.is_player_a:
            player_position = state.position_a
            info = state.player_a.information
        else:
            player_position = state.position_b
            info = state.player_b.information

        # Estimate opponent position
        opp_est, opp_unc = info.get_position_estimate(state.turn)

        # Calculate "fair" VP based on positions
        total_pos = player_position + opp_est
        if total_pos > 0:
            fair_vp = int((player_position / total_pos) * 100)
        else:
            fair_vp = 50

        vp_difference = your_vp - fair_vp

        prompt = HUMAN_SETTLEMENT_EVALUATION_PROMPT.format(
            risk_tolerance=self.persona.risk_tolerance,
            sophistication=self.persona.sophistication,
            emotional_state=self.persona.emotional_state,
            personality=self.persona.personality,
            decision_style=self.persona.decision_style,
            your_vp=your_vp,
            argument=argument,
            is_final_offer="Yes" if is_final_offer else "No",
            turn=state.turn,
            player_position=player_position,
            opponent_position=f"{opp_est:.1f}",
            risk_level=state.risk_level,
            cooperation_score=state.cooperation_score,
            fair_vp=fair_vp,
            vp_difference=vp_difference,
        )

        result = await generate_json(
            prompt=prompt,
            system_prompt=HUMAN_SIMULATOR_SYSTEM_PROMPT,
        )

        internal_response = SettlementResponse.model_validate(result)

        # Convert to base class SettlementResponse
        return BaseSettlementResponse(
            action=internal_response.decision,
            counter_vp=internal_response.counter_vp,
            counter_argument=internal_response.counter_argument,
            rejection_reason=internal_response.rejection_reason,
        )

    async def propose_settlement(self, state: GameState) -> BaseSettlementProposal | None:
        """Decide whether to propose settlement and what offer to make.

        Implements the Opponent interface.

        Args:
            state: Current game state

        Returns:
            SettlementProposal if proposing, None otherwise
        """
        if self.persona is None:
            raise ValueError("No persona set. Call generate_persona() first.")

        # Only consider settlement after turn 4 and if stability > 2
        if state.turn <= 4 or state.stability <= 2:
            return None

        if self.is_player_a:
            player_position = state.position_a
            info = state.player_a.information
        else:
            player_position = state.position_b
            info = state.player_b.information

        # Get opponent estimate
        opp_est, _ = info.get_position_estimate(state.turn)

        # Calculate position-based VP
        total_pos = player_position + opp_est
        if total_pos > 0:
            base_vp = (player_position / total_pos) * 100
        else:
            base_vp = 50

        # Decide based on persona
        # Risk-averse players more likely to settle
        # Players who are ahead want to lock in gains
        # Desperate players may accept less

        position_advantage = player_position - opp_est
        settle_probability = 0.3  # Base 30% chance

        if self.persona.risk_tolerance == "risk_averse":
            settle_probability += 0.2
        elif self.persona.risk_tolerance == "risk_seeking":
            settle_probability -= 0.15

        if self.persona.emotional_state == "desperate":
            settle_probability += 0.3
        elif self.persona.emotional_state == "stressed":
            settle_probability += 0.1

        if position_advantage > 1:
            settle_probability += 0.2  # Want to lock in advantage
        elif position_advantage < -1:
            settle_probability -= 0.1  # Don't want to lock in disadvantage

        if state.risk_level > 7:
            settle_probability += 0.25  # High risk encourages settlement

        # Random decision
        if random.random() > settle_probability:
            return None

        # Calculate offer
        # Add personality-based adjustment
        if self.persona.personality == "cooperative":
            # Offer closer to fair
            adjustment = random.randint(-3, 3)
        elif self.persona.personality == "competitive":
            # Try to get more
            adjustment = random.randint(2, 8)
        else:  # erratic
            adjustment = random.randint(-5, 10)

        offered_vp = int(base_vp + adjustment)
        offered_vp = max(20, min(80, offered_vp))  # Clamp to valid range

        # Generate argument based on persona
        if self.persona.personality == "cooperative":
            argument = (
                f"We've both invested significantly in this crisis. "
                f"A {offered_vp}-{100-offered_vp} split reflects our relative positions "
                f"while avoiding the risks of continued brinkmanship."
            )
        elif self.persona.personality == "competitive":
            argument = (
                f"My position warrants a {offered_vp}-{100-offered_vp} split. "
                f"Continued resistance will only cost us both more. "
                f"Accept this reasonable offer while it's still on the table."
            )
        else:
            argument = (
                f"I propose {offered_vp}-{100-offered_vp}. "
                f"The current situation is unstable. Let's end this."
            )

        return BaseSettlementProposal(offered_vp=offered_vp, argument=argument)

    def update_emotional_state(
        self,
        result_for_player: str,
        position_change: float,
    ) -> None:
        """Update persona's emotional state based on game events.

        This simulates how humans react emotionally to outcomes.

        Args:
            result_for_player: "exploited", "exploiter", "mutual_coop", "mutual_defect"
            position_change: Change in player's position this turn
        """
        if self.persona is None:
            return

        # Negative outcomes increase stress
        if result_for_player == "exploited" or position_change < -0.5:
            if self.persona.emotional_state == "calm":
                # 40% chance to become stressed
                if random.random() < 0.4:
                    self.persona.emotional_state = "stressed"
            elif self.persona.emotional_state == "stressed":
                # 30% chance to become desperate
                if random.random() < 0.3:
                    self.persona.emotional_state = "desperate"

        # Positive outcomes can reduce stress
        elif result_for_player == "exploiter" or position_change > 0.5:
            if self.persona.emotional_state == "desperate":
                # 50% chance to improve to stressed
                if random.random() < 0.5:
                    self.persona.emotional_state = "stressed"
            elif self.persona.emotional_state == "stressed":
                # 30% chance to calm down
                if random.random() < 0.3:
                    self.persona.emotional_state = "calm"

        # Mutual cooperation tends to calm
        elif result_for_player == "mutual_coop":
            if self.persona.emotional_state != "calm" and random.random() < 0.25:
                if self.persona.emotional_state == "desperate":
                    self.persona.emotional_state = "stressed"
                else:
                    self.persona.emotional_state = "calm"
