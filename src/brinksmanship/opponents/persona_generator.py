"""Persona generator for creating new historical personas.

This module provides the PersonaGenerator class for creating new opponent
personas from figure names, optionally using web search to ground personas
in documented historical behavior.

See ENGINEERING_DESIGN.md Milestone 4.4 for specification.
"""

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from brinksmanship.llm import agentic_query, generate_json
from brinksmanship.models.actions import Action, ActionType
from brinksmanship.models.state import GameState
from brinksmanship.opponents.base import (
    Opponent,
    SettlementProposal,
    SettlementResponse,
)
from brinksmanship.prompts import (
    GENERATED_PERSONA_ACTION_PROMPT,
    GENERATED_PERSONA_SETTLEMENT_PROMPT,
    HISTORICAL_PERSONA_SYSTEM_PROMPT,
    PERSONA_EVALUATION_PROMPT,
    PERSONA_GENERATION_PROMPT,
    PERSONA_RESEARCH_PROMPT,
    PERSONA_RESEARCH_SYSTEM_PROMPT,
    SETTLEMENT_EVALUATION_SYSTEM_PROMPT,
    format_settlement_evaluation_prompt,
)

if TYPE_CHECKING:
    from brinksmanship.models.state import ActionResult

logger = logging.getLogger(__name__)


@dataclass
class PersonaDefinition:
    """A complete persona definition for a historical figure.

    This dataclass contains all the information needed to create a
    playable HistoricalPersona from a generated persona.

    Attributes:
        figure_name: The name of the historical figure.
        worldview: Core beliefs about power, conflict, and strategy.
        strategic_patterns: List of typical strategic approaches.
        negotiation_style: How they negotiate and make deals.
        risk_profile: Risk tolerance and planning horizon.
        characteristic_quotes: Documented quotes about strategy.
        decision_triggers: Situations that cause distinctive reactions.
    """

    figure_name: str
    worldview: str
    strategic_patterns: list[str]
    negotiation_style: str
    risk_profile: dict[str, str]  # {"risk_tolerance": str, "planning_horizon": str}
    characteristic_quotes: list[str]
    decision_triggers: list[str]

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "figure_name": self.figure_name,
            "worldview": self.worldview,
            "strategic_patterns": self.strategic_patterns,
            "negotiation_style": self.negotiation_style,
            "risk_profile": self.risk_profile,
            "characteristic_quotes": self.characteristic_quotes,
            "decision_triggers": self.decision_triggers,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PersonaDefinition":
        """Create from dictionary."""
        return cls(
            figure_name=data["figure_name"],
            worldview=data["worldview"],
            strategic_patterns=data["strategic_patterns"],
            negotiation_style=data["negotiation_style"],
            risk_profile=data["risk_profile"],
            characteristic_quotes=data["characteristic_quotes"],
            decision_triggers=data["decision_triggers"],
        )


@dataclass
class PersonaGenerationResult:
    """Result of persona generation including evaluation metadata.

    Attributes:
        persona: The generated persona definition.
        web_search_used: Whether web search was used.
        web_search_added_value: Whether web search provided additional value.
        evaluation: Evaluation details comparing baseline vs researched.
        baseline_persona: The baseline persona (from training knowledge only).
        researched_persona: The researched persona (if web search was used).
    """

    persona: PersonaDefinition
    web_search_used: bool = False
    web_search_added_value: bool | None = None
    evaluation: dict | None = None
    baseline_persona: PersonaDefinition | None = None
    researched_persona: PersonaDefinition | None = None


class PersonaGenerator:
    """Generator for creating new historical personas.

    This class can create persona definitions from figure names,
    optionally using web search to research the figure's documented
    strategic behavior.

    Example:
        >>> generator = PersonaGenerator()
        >>> result = await generator.generate_persona(
        ...     "Napoleon Bonaparte",
        ...     use_web_search=True,
        ...     evaluate_quality=True
        ... )
        >>> print(result.persona.worldview)
    """

    def __init__(self) -> None:
        """Initialize the persona generator."""
        self._cache: dict[str, PersonaGenerationResult] = {}

    async def generate_persona(
        self,
        figure_name: str,
        use_web_search: bool = False,
        evaluate_quality: bool = True,
    ) -> PersonaGenerationResult:
        """Generate a persona definition from a figure name.

        Args:
            figure_name: The name of the historical figure.
            use_web_search: If True, research the figure using web search.
            evaluate_quality: If True and web search is used, compare
                baseline and researched versions to determine which is better.

        Returns:
            PersonaGenerationResult containing the generated persona and
            evaluation metadata.
        """
        # Check cache first
        cache_key = f"{figure_name}:{use_web_search}:{evaluate_quality}"
        if cache_key in self._cache:
            logger.info(f"Using cached persona for {figure_name}")
            return self._cache[cache_key]

        logger.info(f"Generating persona for {figure_name} (web_search={use_web_search})")

        # 1. Generate baseline persona from training knowledge
        baseline_persona = await self._generate_baseline_persona(figure_name)

        if not use_web_search:
            result = PersonaGenerationResult(
                persona=baseline_persona,
                web_search_used=False,
                baseline_persona=baseline_persona,
            )
            self._cache[cache_key] = result
            return result

        # 2. Research the figure using web search
        research_context = await self._research_figure(figure_name)

        # 3. Generate researched persona
        researched_persona = await self._generate_researched_persona(
            figure_name, research_context
        )

        if not evaluate_quality:
            result = PersonaGenerationResult(
                persona=researched_persona,
                web_search_used=True,
                baseline_persona=baseline_persona,
                researched_persona=researched_persona,
            )
            self._cache[cache_key] = result
            return result

        # 4. Evaluate which persona is better
        evaluation = await self._evaluate_personas(
            figure_name, baseline_persona, researched_persona
        )

        # Choose the recommended persona
        recommendation = evaluation.get("recommendation", "use_researched")
        web_search_added_value = evaluation.get("web_search_added_value", True)

        if recommendation == "use_baseline":
            chosen_persona = baseline_persona
            logger.info(
                f"Web search did not add significant value for {figure_name}. "
                f"Using baseline persona."
            )
        else:
            chosen_persona = researched_persona
            logger.info(
                f"Web search added value for {figure_name}: "
                f"{evaluation.get('new_specific_details', [])}"
            )

        result = PersonaGenerationResult(
            persona=chosen_persona,
            web_search_used=True,
            web_search_added_value=web_search_added_value,
            evaluation=evaluation,
            baseline_persona=baseline_persona,
            researched_persona=researched_persona,
        )
        self._cache[cache_key] = result
        return result

    async def _generate_baseline_persona(self, figure_name: str) -> PersonaDefinition:
        """Generate a persona using only LLM training knowledge.

        Args:
            figure_name: The name of the historical figure.

        Returns:
            PersonaDefinition generated from training knowledge.
        """
        prompt = PERSONA_GENERATION_PROMPT.format(
            figure_name=figure_name,
            research_context="",
        )

        response = await generate_json(
            prompt=prompt,
            system_prompt=HISTORICAL_PERSONA_SYSTEM_PROMPT,
        )

        return self._parse_persona_response(response)

    async def _research_figure(self, figure_name: str) -> str:
        """Research a figure using web search.

        Args:
            figure_name: The name of the historical figure.

        Returns:
            Research context text synthesized from web search results.
        """
        research_prompt = PERSONA_RESEARCH_PROMPT.format(figure_name=figure_name)

        research = await agentic_query(
            prompt=research_prompt,
            system_prompt=PERSONA_RESEARCH_SYSTEM_PROMPT,
            allowed_tools=["WebSearch", "WebFetch"],
            max_turns=5,
        )

        return research

    async def _generate_researched_persona(
        self, figure_name: str, research_context: str
    ) -> PersonaDefinition:
        """Generate a persona using research context.

        Args:
            figure_name: The name of the historical figure.
            research_context: Research context from web search.

        Returns:
            PersonaDefinition generated with research context.
        """
        prompt = PERSONA_GENERATION_PROMPT.format(
            figure_name=figure_name,
            research_context=f"\nRESEARCH CONTEXT:\n{research_context}\n",
        )

        response = await generate_json(
            prompt=prompt,
            system_prompt=HISTORICAL_PERSONA_SYSTEM_PROMPT,
        )

        return self._parse_persona_response(response)

    async def _evaluate_personas(
        self,
        figure_name: str,
        baseline_persona: PersonaDefinition,
        researched_persona: PersonaDefinition,
    ) -> dict:
        """Evaluate and compare baseline vs researched personas.

        Args:
            figure_name: The name of the historical figure.
            baseline_persona: Persona from training knowledge only.
            researched_persona: Persona with web search context.

        Returns:
            Evaluation dict with recommendation and details.
        """
        prompt = PERSONA_EVALUATION_PROMPT.format(
            figure_name=figure_name,
            baseline_persona=json.dumps(baseline_persona.to_dict(), indent=2),
            researched_persona=json.dumps(researched_persona.to_dict(), indent=2),
        )

        evaluation = await generate_json(
            prompt=prompt,
            system_prompt=HISTORICAL_PERSONA_SYSTEM_PROMPT,
        )

        return evaluation

    def _parse_persona_response(self, response: dict) -> PersonaDefinition:
        """Parse LLM response into a PersonaDefinition.

        Args:
            response: Parsed JSON response from LLM.

        Returns:
            PersonaDefinition extracted from response.
        """
        # Handle nested structure if present
        if "persona" in response:
            response = response["persona"]

        return PersonaDefinition(
            figure_name=response.get("figure_name", "Unknown"),
            worldview=response.get("worldview", ""),
            strategic_patterns=response.get("strategic_patterns", []),
            negotiation_style=response.get("negotiation_style", ""),
            risk_profile=response.get(
                "risk_profile",
                {"risk_tolerance": "calculated", "planning_horizon": "medium_term"},
            ),
            characteristic_quotes=response.get("characteristic_quotes", []),
            decision_triggers=response.get("decision_triggers", []),
        )

    def clear_cache(self) -> None:
        """Clear the persona cache."""
        self._cache.clear()

    def get_cached_personas(self) -> list[str]:
        """Get list of cached figure names.

        Returns:
            List of figure names that have been cached.
        """
        return [key.split(":")[0] for key in self._cache.keys()]


class GeneratedPersona(Opponent):
    """An opponent created from a generated PersonaDefinition.

    This class uses LLM with the generated persona prompt to make decisions.
    It's similar to HistoricalPersona but uses a dynamically generated
    persona definition rather than a pre-defined one.

    Attributes:
        persona_definition: The generated persona definition.
        is_player_a: Whether this opponent plays as Player A.
    """

    def __init__(
        self,
        persona_definition: PersonaDefinition,
        is_player_a: bool = False,
    ) -> None:
        """Initialize a generated persona opponent.

        Args:
            persona_definition: The persona definition to use.
            is_player_a: Whether this opponent plays as Player A.
        """
        super().__init__(name=persona_definition.figure_name)

        self.persona_definition = persona_definition
        self.is_player_a = is_player_a
        self._persona_prompt = _build_persona_prompt(persona_definition)

        # History tracking
        self.action_history: list[tuple[Action, GameState]] = []

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
        """Get estimate of opponent's position with uncertainty."""
        if self.is_player_a:
            info_state = state.player_a.information
        else:
            info_state = state.player_b.information

        return info_state.get_position_estimate(state.turn)

    def choose_action(
        self, state: GameState, available_actions: list[Action]
    ) -> Action:
        """Choose an action using LLM with generated persona prompt."""
        # Get state from this persona's perspective
        my_position, my_resources, my_last_type = self._get_my_state(state)
        _, _, opp_last_type = self._get_opponent_state(state)
        opp_position_est, opp_uncertainty = self._get_opponent_estimate(state)

        # Format action list
        action_list = self._format_action_list(available_actions)

        # Build prompt using centralized prompt from prompts.py
        prompt = GENERATED_PERSONA_ACTION_PROMPT.format(
            turn=state.turn,
            risk_level=f"{state.risk_level:.1f}",
            cooperation_score=f"{state.cooperation_score:.1f}",
            stability=f"{state.stability:.1f}",
            my_position=f"{my_position:.1f}",
            my_resources=f"{my_resources:.1f}",
            opp_position_est=f"{opp_position_est:.1f}",
            opp_uncertainty=f"{opp_uncertainty:.1f}",
            my_last_type=self._format_action_type(my_last_type),
            opp_last_type=self._format_action_type(opp_last_type),
            action_list=action_list,
            figure_name=self.persona_definition.figure_name,
        )

        system_prompt = f"""{HISTORICAL_PERSONA_SYSTEM_PROMPT}

{self._persona_prompt}
"""

        # Run async LLM call
        response = asyncio.run(
            generate_json(prompt=prompt, system_prompt=system_prompt)
        )

        # Find matching action
        selected_name = response.get("selected_action", "").strip()
        selected_action = None

        for action in available_actions:
            if action.name.lower() == selected_name.lower():
                selected_action = action
                break

        # Fallback: partial match
        if selected_action is None:
            for action in available_actions:
                if selected_name.lower() in action.name.lower():
                    selected_action = action
                    break

        # Final fallback
        if selected_action is None:
            selected_action = available_actions[0]
            logger.warning(
                f"{self.name} selected unknown action '{selected_name}', "
                f"falling back to {selected_action.name}"
            )

        self.action_history.append((selected_action, state))
        return selected_action

    def evaluate_settlement(
        self,
        proposal: SettlementProposal,
        state: GameState,
        is_final_offer: bool,
    ) -> SettlementResponse:
        """Evaluate a settlement proposal using LLM."""
        my_position, my_resources, _ = self._get_my_state(state)
        opp_position, _, _ = self._get_opponent_state(state)

        their_vp = proposal.offered_vp
        my_vp = 100 - their_vp

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
            persona_description=self._persona_prompt,
        )

        response = asyncio.run(
            generate_json(
                prompt=prompt,
                system_prompt=SETTLEMENT_EVALUATION_SYSTEM_PROMPT,
            )
        )

        action = response.get("action", "").upper()

        if action == "ACCEPT":
            return SettlementResponse(action="accept")
        elif action == "COUNTER" and not is_final_offer:
            counter_vp = response.get("counter_vp")
            counter_arg = response.get("counter_argument", "")

            fair_vp = self.get_position_fair_vp(state, self.is_player_a)
            min_vp = max(20, fair_vp - 10)
            max_vp = min(80, fair_vp + 10)

            if counter_vp is None:
                counter_vp = fair_vp
            else:
                counter_vp = max(min_vp, min(max_vp, int(counter_vp)))

            return SettlementResponse(
                action="counter",
                counter_vp=counter_vp,
                counter_argument=counter_arg[:500] if counter_arg else None,
            )
        else:
            reason = response.get("rejection_reason", "Terms unacceptable.")
            return SettlementResponse(
                action="reject",
                rejection_reason=reason,
            )

    def propose_settlement(self, state: GameState) -> SettlementProposal | None:
        """Decide whether to propose settlement."""
        if state.turn <= 4 or state.stability <= 2:
            return None

        my_position, my_resources, _ = self._get_my_state(state)
        opp_position_est, opp_uncertainty = self._get_opponent_estimate(state)

        fair_vp = self.get_position_fair_vp(state, self.is_player_a)
        min_vp = max(20, fair_vp - 10)
        max_vp = min(80, fair_vp + 10)

        # Build prompt using centralized prompt from prompts.py
        prompt = GENERATED_PERSONA_SETTLEMENT_PROMPT.format(
            figure_name=self.persona_definition.figure_name,
            persona_prompt=self._persona_prompt,
            turn=state.turn,
            my_position=f"{my_position:.1f}",
            my_resources=f"{my_resources:.1f}",
            opp_position_est=f"{opp_position_est:.1f}",
            opp_uncertainty=f"{opp_uncertainty:.1f}",
            risk_level=f"{state.risk_level:.1f}",
            cooperation_score=f"{state.cooperation_score:.1f}",
            min_vp=min_vp,
            max_vp=max_vp,
        )

        response = asyncio.run(
            generate_json(
                prompt=prompt,
                system_prompt=HISTORICAL_PERSONA_SYSTEM_PROMPT,
            )
        )

        if not response.get("propose", False):
            return None

        offered_vp = response.get("offered_vp")
        argument = response.get("argument", "")

        if offered_vp is None:
            offered_vp = fair_vp
        else:
            offered_vp = max(min_vp, min(max_vp, int(offered_vp)))

        return SettlementProposal(
            offered_vp=offered_vp,
            argument=argument[:500] if argument else "",
        )

    def _format_action_type(self, action_type: ActionType | None) -> str:
        """Format action type for display."""
        if action_type is None:
            return "None (first turn)"
        return action_type.value.capitalize()

    def _format_action_list(self, actions: list[Action]) -> str:
        """Format action list for prompt."""
        lines = []
        for i, action in enumerate(actions, 1):
            type_str = "COOPERATIVE" if action.action_type == ActionType.COOPERATIVE else "COMPETITIVE"
            cost_str = f" (costs {action.resource_cost} resources)" if action.resource_cost > 0 else ""
            lines.append(f"{i}. {action.name} [{type_str}]{cost_str}")
            if action.description:
                lines.append(f"   {action.description}")
        return "\n".join(lines)

    def __repr__(self) -> str:
        """String representation."""
        return f"GeneratedPersona('{self.persona_definition.figure_name}')"


def create_opponent_from_persona(
    persona_def: PersonaDefinition,
    is_player_a: bool = False,
) -> "GeneratedPersona":
    """Create a playable opponent from a generated definition.

    This function creates a GeneratedPersona instance that uses the
    persona definition for LLM-based decision making.

    Args:
        persona_def: The generated persona definition.
        is_player_a: Whether this opponent plays as Player A.

    Returns:
        A GeneratedPersona instance ready for gameplay.

    Example:
        >>> generator = PersonaGenerator()
        >>> result = await generator.generate_persona("Napoleon Bonaparte")
        >>> opponent = create_opponent_from_persona(result.persona)
        >>> action = opponent.choose_action(game_state, available_actions)
    """
    return GeneratedPersona(
        persona_definition=persona_def,
        is_player_a=is_player_a,
    )


def _build_persona_prompt(persona_def: PersonaDefinition) -> str:
    """Build a persona prompt string from a PersonaDefinition.

    Args:
        persona_def: The persona definition.

    Returns:
        Formatted persona prompt for LLM.
    """
    quotes_section = "\n".join(
        f'- "{quote}"' for quote in persona_def.characteristic_quotes
    )

    patterns_section = "\n".join(
        f"- {pattern}" for pattern in persona_def.strategic_patterns
    )

    triggers_section = "\n".join(
        f"- {trigger}" for trigger in persona_def.decision_triggers
    )

    return f"""You are {persona_def.figure_name}.

WORLDVIEW:
{persona_def.worldview}

STRATEGIC PATTERNS:
{patterns_section}

NEGOTIATION STYLE:
{persona_def.negotiation_style}

RISK PROFILE:
- Risk Tolerance: {persona_def.risk_profile.get('risk_tolerance', 'calculated')}
- Planning Horizon: {persona_def.risk_profile.get('planning_horizon', 'medium_term')}

CHARACTERISTIC QUOTES:
{quotes_section}

DECISION TRIGGERS (situations that cause distinctive reactions):
{triggers_section}
"""


async def generate_new_persona(
    figure_name: str,
    use_web_search: bool = False,
    is_player_a: bool = False,
) -> GeneratedPersona:
    """Convenience function to generate and create a new persona opponent.

    This function combines persona generation and opponent creation into
    a single call.

    Args:
        figure_name: The name of the historical figure.
        use_web_search: If True, research the figure using web search.
        is_player_a: Whether this opponent plays as Player A.

    Returns:
        A GeneratedPersona instance ready for gameplay.

    Example:
        >>> opponent = await generate_new_persona(
        ...     "Napoleon Bonaparte",
        ...     use_web_search=True
        ... )
        >>> action = opponent.choose_action(game_state, available_actions)
    """
    generator = PersonaGenerator()
    result = await generator.generate_persona(
        figure_name=figure_name,
        use_web_search=use_web_search,
        evaluate_quality=use_web_search,  # Only evaluate if using web search
    )
    return create_opponent_from_persona(result.persona, is_player_a=is_player_a)
