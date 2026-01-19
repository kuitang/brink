"""Historical persona opponent implementation for Brinksmanship.

This module implements the HistoricalPersona class that uses LLM with persona-specific
prompts to make strategic decisions. Each persona embodies a historical figure's
documented strategic patterns and decision-making style.

See GAME_MANUAL.md for authoritative game mechanics.
See prompts.py for persona definitions (PERSONA_BISMARCK, PERSONA_NIXON, etc.).
"""

import asyncio
from typing import Any

from brinksmanship.llm import generate_json, generate_text
from brinksmanship.models.actions import Action, ActionType
from brinksmanship.models.state import ActionResult, GameState
from brinksmanship.opponents.base import (
    Opponent,
    SettlementProposal,
    SettlementResponse,
)
from brinksmanship.prompts import (
    HISTORICAL_PERSONA_SYSTEM_PROMPT,
    PERSONA_ACTION_SELECTION_PROMPT,
    PERSONA_BISMARCK,
    PERSONA_KHRUSHCHEV,
    PERSONA_NIXON,
    PERSONA_SETTLEMENT_PROPOSAL_PROMPT,
    SETTLEMENT_EVALUATION_PROMPT,
    SETTLEMENT_EVALUATION_SYSTEM_PROMPT,
    format_settlement_evaluation_prompt,
)


# Mapping from persona name to prompt constant name in prompts.py
PERSONA_PROMPTS: dict[str, str] = {
    "bismarck": "PERSONA_BISMARCK",
    "richelieu": "PERSONA_RICHELIEU",
    "metternich": "PERSONA_METTERNICH",
    "pericles": "PERSONA_PERICLES",
    "nixon": "PERSONA_NIXON",
    "kissinger": "PERSONA_KISSINGER",
    "khrushchev": "PERSONA_KHRUSHCHEV",
    "tito": "PERSONA_TITO",
    "kekkonen": "PERSONA_KEKKONEN",
    "lee_kuan_yew": "PERSONA_LEE_KUAN_YEW",
    "gates": "PERSONA_GATES",
    "jobs": "PERSONA_JOBS",
    "icahn": "PERSONA_ICAHN",
    "zuckerberg": "PERSONA_ZUCKERBERG",
    "buffett": "PERSONA_BUFFETT",
    "theodora": "PERSONA_THEODORA",
    "wu_zetian": "PERSONA_WU_ZETIAN",
    "cixi": "PERSONA_CIXI",
    "livia": "PERSONA_LIVIA",
}

# Display names for historical figures
PERSONA_DISPLAY_NAMES: dict[str, str] = {
    "bismarck": "Otto von Bismarck",
    "richelieu": "Cardinal Richelieu",
    "metternich": "Klemens von Metternich",
    "pericles": "Pericles of Athens",
    "nixon": "Richard Nixon",
    "kissinger": "Henry Kissinger",
    "khrushchev": "Nikita Khrushchev",
    "tito": "Josip Broz Tito",
    "kekkonen": "Urho Kekkonen",
    "lee_kuan_yew": "Lee Kuan Yew",
    "gates": "Bill Gates",
    "jobs": "Steve Jobs",
    "icahn": "Carl Icahn",
    "zuckerberg": "Mark Zuckerberg",
    "buffett": "Warren Buffett",
    "theodora": "Empress Theodora",
    "wu_zetian": "Empress Wu Zetian",
    "cixi": "Empress Dowager Cixi",
    "livia": "Livia Drusilla",
}


def _get_persona_description(persona_name: str) -> str:
    """Get the persona description from prompts.py.

    This dynamically imports the persona constant from the prompts module.

    Args:
        persona_name: The lowercase persona key (e.g., 'bismarck')

    Returns:
        The persona description string

    Raises:
        ValueError: If persona is not found
    """
    import brinksmanship.prompts as prompts_module

    prompt_name = PERSONA_PROMPTS.get(persona_name.lower())
    if not prompt_name:
        raise ValueError(
            f"Unknown persona: {persona_name}. "
            f"Valid personas: {list(PERSONA_PROMPTS.keys())}"
        )

    # Get the persona constant from the prompts module
    persona_desc = getattr(prompts_module, prompt_name, None)
    if persona_desc is None:
        # Fallback: return a generic description based on the name
        display_name = PERSONA_DISPLAY_NAMES.get(
            persona_name.lower(), persona_name.title()
        )
        return f"""You are {display_name}.

Embody this historical figure's documented strategic patterns and worldview.
Make decisions consistent with their known negotiation style, risk tolerance,
and approach to conflict resolution."""

    return persona_desc


def _format_action_type(action_type: ActionType | None) -> str:
    """Format an action type for display."""
    if action_type is None:
        return "None (first turn)"
    return action_type.value.capitalize()


def _format_action_list(actions: list[Action]) -> str:
    """Format a list of actions for the prompt."""
    lines = []
    for i, action in enumerate(actions, 1):
        type_str = "COOPERATIVE" if action.action_type == ActionType.COOPERATIVE else "COMPETITIVE"
        cost_str = f" (costs {action.resource_cost} resources)" if action.resource_cost > 0 else ""
        lines.append(f"{i}. {action.name} [{type_str}]{cost_str}")
        if action.description:
            lines.append(f"   {action.description}")
    return "\n".join(lines)


class HistoricalPersona(Opponent):
    """An opponent that embodies a historical figure's strategic patterns.

    Uses LLM with persona-specific prompts to make decisions. The persona
    influences action selection, settlement evaluation, and negotiation style.

    Attributes:
        persona_name: The lowercase key for the persona (e.g., 'bismarck')
        persona_description: The full persona description from prompts.py
        display_name: Human-readable name for display
        action_history: History of actions taken for adaptation
        is_player_a: Whether this opponent is playing as Player A
    """

    def __init__(
        self,
        persona_name: str,
        is_player_a: bool = False,
    ):
        """Initialize a historical persona opponent.

        Args:
            persona_name: The persona key (e.g., 'bismarck', 'nixon')
            is_player_a: Whether this opponent plays as Player A (default False)

        Raises:
            ValueError: If persona_name is not recognized
        """
        # Normalize persona name
        normalized_name = persona_name.lower().replace("-", "_").replace(" ", "_")

        if normalized_name not in PERSONA_PROMPTS:
            raise ValueError(
                f"Unknown persona: {persona_name}. "
                f"Valid personas: {list(PERSONA_PROMPTS.keys())}"
            )

        display_name = PERSONA_DISPLAY_NAMES.get(normalized_name, persona_name.title())
        super().__init__(name=display_name)

        self.persona_name = normalized_name
        self.persona_description = _get_persona_description(normalized_name)
        self.display_name = display_name
        self.is_player_a = is_player_a

        # History tracking for adaptation
        self.action_history: list[tuple[Action, GameState]] = []
        self.settlement_history: list[tuple[SettlementProposal, SettlementResponse, GameState]] = []

    def _get_my_state(self, state: GameState) -> tuple[float, float, ActionType | None]:
        """Get this persona's position, resources, and previous action type."""
        if self.is_player_a:
            return state.position_a, state.resources_a, state.previous_type_a
        return state.position_b, state.resources_b, state.previous_type_b

    def _get_opponent_state(self, state: GameState) -> tuple[float, float, ActionType | None]:
        """Get opponent's position, resources, and previous action type."""
        if self.is_player_a:
            return state.position_b, state.resources_b, state.previous_type_b
        return state.position_a, state.resources_a, state.previous_type_a

    def _get_opponent_estimate(self, state: GameState) -> tuple[float, float]:
        """Get estimate of opponent's position with uncertainty.

        Returns:
            Tuple of (estimated_position, uncertainty_radius)
        """
        if self.is_player_a:
            info_state = state.player_a.information
        else:
            info_state = state.player_b.information

        return info_state.get_position_estimate(state.turn)

    def choose_action(
        self, state: GameState, available_actions: list[Action]
    ) -> Action:
        """Choose an action using LLM with persona prompt.

        This method is synchronous but uses asyncio.run() internally to
        call the async LLM functions.

        Args:
            state: Current game state
            available_actions: List of valid actions to choose from

        Returns:
            The chosen action from available_actions
        """
        # Get state from this persona's perspective
        my_position, my_resources, my_last_type = self._get_my_state(state)
        _, _, opp_last_type = self._get_opponent_state(state)
        opp_position_est, opp_uncertainty = self._get_opponent_estimate(state)

        # Format the action selection prompt
        prompt = PERSONA_ACTION_SELECTION_PROMPT.format(
            persona_name=self.display_name,
            persona_description=self.persona_description,
            turn=state.turn,
            my_position=f"{my_position:.1f}",
            my_resources=f"{my_resources:.1f}",
            opp_position_est=f"{opp_position_est:.1f}",
            opp_uncertainty=f"{opp_uncertainty:.1f}",
            risk_level=f"{state.risk_level:.1f}",
            coop_score=f"{state.cooperation_score:.1f}",
            my_last_type=_format_action_type(my_last_type),
            opp_last_type=_format_action_type(opp_last_type),
            action_list=_format_action_list(available_actions),
        )

        # Call LLM (sync wrapper around async)
        response = asyncio.run(
            generate_json(
                prompt=prompt,
                system_prompt=HISTORICAL_PERSONA_SYSTEM_PROMPT,
            )
        )

        # Parse response and find matching action
        selected_name = response.get("selected_action", "").strip()
        reasoning = response.get("reasoning", "")

        # Find the matching action (case-insensitive)
        selected_action = None
        for action in available_actions:
            if action.name.lower() == selected_name.lower():
                selected_action = action
                break

        # Fallback: if no exact match, try partial match
        if selected_action is None:
            for action in available_actions:
                if selected_name.lower() in action.name.lower():
                    selected_action = action
                    break

        # Final fallback: choose first action
        if selected_action is None:
            selected_action = available_actions[0]

        # Record in history
        self.action_history.append((selected_action, state))

        return selected_action

    def evaluate_settlement(
        self,
        proposal: SettlementProposal,
        state: GameState,
        is_final_offer: bool,
    ) -> SettlementResponse:
        """Evaluate a settlement proposal using LLM with persona prompt.

        Uses Opus for quality evaluation of settlement arguments.

        Args:
            proposal: The settlement proposal to evaluate
            state: Current game state
            is_final_offer: Whether this is a final offer (no counter allowed)

        Returns:
            SettlementResponse indicating accept, counter, or reject
        """
        # Get state from this persona's perspective
        my_position, my_resources, _ = self._get_my_state(state)
        opp_position, _, _ = self._get_opponent_state(state)

        # Calculate what VP this persona would get
        their_vp = proposal.offered_vp
        my_vp = 100 - their_vp

        # Format evaluation prompt
        prompt = format_settlement_evaluation_prompt(
            turn_number=state.turn,
            risk_level=state.risk_level,
            cooperation_score=state.cooperation_score,
            your_position=my_position,
            opponent_position=opp_position,
            your_resources=my_resources,
            offered_vp=their_vp,
            your_vp=my_vp,
            argument=proposal.argument,
            is_final_offer=is_final_offer,
            persona_description=self.persona_description,
        )

        # Call LLM for evaluation
        response = asyncio.run(
            generate_json(
                prompt=prompt,
                system_prompt=SETTLEMENT_EVALUATION_SYSTEM_PROMPT,
            )
        )

        # Parse response
        action = response.get("action", "").upper()

        if action == "ACCEPT":
            result = SettlementResponse(action="accept")
        elif action == "COUNTER" and not is_final_offer:
            counter_vp = response.get("counter_vp")
            counter_arg = response.get("counter_argument", "")

            # Validate counter VP is in valid range
            fair_vp = self.get_position_fair_vp(state, self.is_player_a)
            min_vp = max(20, fair_vp - 10)
            max_vp = min(80, fair_vp + 10)

            if counter_vp is None:
                counter_vp = fair_vp
            else:
                counter_vp = max(min_vp, min(max_vp, int(counter_vp)))

            result = SettlementResponse(
                action="counter",
                counter_vp=counter_vp,
                counter_argument=counter_arg[:500] if counter_arg else None,
            )
        else:
            # Reject (or counter on final offer becomes reject)
            reason = response.get("rejection_reason", "Terms unacceptable.")
            result = SettlementResponse(
                action="reject",
                rejection_reason=reason,
            )

        # Record in history
        self.settlement_history.append((proposal, result, state))

        return result

    def propose_settlement(self, state: GameState) -> SettlementProposal | None:
        """Decide whether to propose settlement using LLM with persona prompt.

        Args:
            state: Current game state

        Returns:
            SettlementProposal if proposing, None otherwise
        """
        # Check if settlement is even available
        if state.turn <= 4 or state.stability <= 2:
            return None

        # Get state from this persona's perspective
        my_position, my_resources, _ = self._get_my_state(state)
        opp_position_est, opp_uncertainty = self._get_opponent_estimate(state)

        # Calculate valid VP range
        fair_vp = self.get_position_fair_vp(state, self.is_player_a)
        min_vp = max(20, fair_vp - 10)
        max_vp = min(80, fair_vp + 10)

        # Format settlement proposal prompt
        prompt = PERSONA_SETTLEMENT_PROPOSAL_PROMPT.format(
            persona_name=self.display_name,
            persona_description=self.persona_description,
            turn=state.turn,
            my_position=f"{my_position:.1f}",
            my_resources=f"{my_resources:.1f}",
            opp_position_est=f"{opp_position_est:.1f}",
            opp_uncertainty=f"{opp_uncertainty:.1f}",
            risk_level=f"{state.risk_level:.1f}",
            coop_score=f"{state.cooperation_score:.1f}",
            stability=f"{state.stability:.1f}",
            min_vp=min_vp,
            max_vp=max_vp,
        )

        # Call LLM
        response = asyncio.run(
            generate_json(
                prompt=prompt,
                system_prompt=HISTORICAL_PERSONA_SYSTEM_PROMPT,
            )
        )

        # Parse response
        should_propose = response.get("propose", False)

        if not should_propose:
            return None

        # Get VP offer and argument
        offered_vp = response.get("offered_vp")
        argument = response.get("argument", "")

        # Validate and clamp VP
        if offered_vp is None:
            offered_vp = fair_vp
        else:
            offered_vp = max(min_vp, min(max_vp, int(offered_vp)))

        return SettlementProposal(
            offered_vp=offered_vp,
            argument=argument[:500] if argument else "",
        )

    def receive_result(self, result: ActionResult) -> None:
        """Process the result of a turn for learning/adaptation.

        This implementation could be extended to track opponent patterns
        and adapt strategy over time.

        Args:
            result: The outcome of the turn
        """
        # Base implementation just records history (handled via _history in parent)
        # Could be extended for more sophisticated adaptation
        pass

    def get_history_summary(self) -> dict[str, Any]:
        """Get a summary of this persona's action history.

        Returns:
            Dictionary with history statistics
        """
        if not self.action_history:
            return {"turns_played": 0}

        cooperative_count = sum(
            1 for action, _ in self.action_history
            if action.action_type == ActionType.COOPERATIVE
        )
        competitive_count = len(self.action_history) - cooperative_count

        return {
            "turns_played": len(self.action_history),
            "cooperative_actions": cooperative_count,
            "competitive_actions": competitive_count,
            "cooperation_rate": cooperative_count / len(self.action_history),
            "settlements_evaluated": len(self.settlement_history),
        }

    def __repr__(self) -> str:
        """String representation of this persona."""
        return f"HistoricalPersona('{self.persona_name}', is_player_a={self.is_player_a})"
