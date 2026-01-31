"""LLM-based scenario generation for Brinksmanship.

This module implements the ScenarioGenerator class that uses Claude Agent SDK
to generate complete game scenarios. The generator follows the constructor pattern:
LLM outputs matrix_type + matrix_parameters, never raw payoffs.

See ENGINEERING_DESIGN.md Milestone 3.2 for design rationale.
See GAME_MANUAL.md Part II for game type specifications.
"""

import random
import uuid
from typing import Any

from brinksmanship.generation.schemas import (
    BranchTargets,
    OutcomeNarratives,
    Scenario,
    TurnDefinition,
)
from brinksmanship.llm import generate_json
from brinksmanship.models.matrices import (
    CONSTRUCTORS,
    MatrixParameters,
    MatrixType,
    build_matrix,
    get_default_params_for_type,
)
from brinksmanship.prompts import (
    SCENARIO_GENERATION_SYSTEM_PROMPT,
    format_scenario_generation_prompt,
    format_turn_generation_prompt,
)

# Game type recommendations by theme and act
# From ENGINEERING_DESIGN.md Milestone 3.2
GAME_TYPES_BY_THEME_AND_ACT: dict[str, dict[int, list[MatrixType]]] = {
    "crisis": {
        1: [MatrixType.INSPECTION_GAME, MatrixType.STAG_HUNT, MatrixType.PRISONERS_DILEMMA],
        2: [MatrixType.CHICKEN, MatrixType.SECURITY_DILEMMA],
        3: [MatrixType.CHICKEN, MatrixType.SECURITY_DILEMMA, MatrixType.DEADLOCK],
    },
    "rivals": {
        1: [MatrixType.INSPECTION_GAME, MatrixType.STAG_HUNT],
        2: [MatrixType.CHICKEN, MatrixType.PRISONERS_DILEMMA, MatrixType.DEADLOCK],
        3: [MatrixType.CHICKEN, MatrixType.DEADLOCK, MatrixType.SECURITY_DILEMMA],
    },
    "allies": {
        1: [MatrixType.HARMONY, MatrixType.PURE_COORDINATION, MatrixType.STAG_HUNT],
        2: [MatrixType.BATTLE_OF_SEXES, MatrixType.STAG_HUNT, MatrixType.LEADER],
        3: [MatrixType.VOLUNTEERS_DILEMMA, MatrixType.STAG_HUNT, MatrixType.BATTLE_OF_SEXES],
    },
    "espionage": {
        1: [MatrixType.INSPECTION_GAME, MatrixType.RECONNAISSANCE],
        2: [MatrixType.INSPECTION_GAME, MatrixType.MATCHING_PENNIES, MatrixType.PRISONERS_DILEMMA],
        3: [MatrixType.INSPECTION_GAME, MatrixType.CHICKEN, MatrixType.PRISONERS_DILEMMA],
    },
    "default": {
        1: [MatrixType.STAG_HUNT, MatrixType.PURE_COORDINATION, MatrixType.LEADER],
        2: [MatrixType.PRISONERS_DILEMMA, MatrixType.CHICKEN, MatrixType.BATTLE_OF_SEXES],
        3: [MatrixType.CHICKEN, MatrixType.SECURITY_DILEMMA, MatrixType.PRISONERS_DILEMMA],
    },
}

# Act scaling multipliers from GAME_MANUAL.md
ACT_SCALING: dict[int, float] = {
    1: 0.7,  # Act I (turns 1-4)
    2: 1.0,  # Act II (turns 5-8)
    3: 1.3,  # Act III (turns 9+)
}


def get_act_for_turn(turn: int) -> int:
    """Determine which act a turn belongs to.

    From GAME_MANUAL.md:
    - Act I: turns 1-4
    - Act II: turns 5-8
    - Act III: turns 9+
    """
    if turn <= 4:
        return 1
    elif turn <= 8:
        return 2
    else:
        return 3


def classify_theme(theme: str) -> str:
    """Classify user-provided theme into one of the known categories.

    Returns one of: crisis, rivals, allies, espionage, default
    """
    theme_lower = theme.lower()

    crisis_keywords = ["war", "nuclear", "confrontation", "crisis", "conflict", "standoff"]
    rivals_keywords = ["rival", "enemy", "competitor", "adversary", "opposition"]
    allies_keywords = ["ally", "alliance", "partner", "coalition", "friend", "cooperation"]
    espionage_keywords = ["spy", "intelligence", "secret", "espionage", "covert", "agent"]

    if any(kw in theme_lower for kw in crisis_keywords):
        return "crisis"
    elif any(kw in theme_lower for kw in rivals_keywords):
        return "rivals"
    elif any(kw in theme_lower for kw in allies_keywords):
        return "allies"
    elif any(kw in theme_lower for kw in espionage_keywords):
        return "espionage"
    else:
        return "default"


def get_available_types_for_turn(
    turn: int,
    theme: str,
    previous_types: list[MatrixType],
    risk_level: float = 5.0,
    cooperation_score: float = 5.0,
) -> list[MatrixType]:
    """Get available matrix types for a given turn, respecting constraints.

    Constraints:
    - Never repeat the immediately previous type
    - High risk (>=7): Favor Chicken or Stag Hunt
    - High cooperation (>=7): Favor trust-based games
    - Low cooperation (<=3): Favor confrontational games
    """
    act = get_act_for_turn(turn)
    theme_key = classify_theme(theme)

    # Get base types for this act and theme
    base_types = GAME_TYPES_BY_THEME_AND_ACT.get(theme_key, GAME_TYPES_BY_THEME_AND_ACT["default"])
    available = list(base_types.get(act, base_types[1]))

    # Add variety types based on state
    if risk_level >= 7:
        # High risk: favor Chicken (brinkmanship) or Stag Hunt (de-escalation)
        if MatrixType.CHICKEN not in available:
            available.append(MatrixType.CHICKEN)
        if MatrixType.STAG_HUNT not in available:
            available.append(MatrixType.STAG_HUNT)
    elif cooperation_score >= 7:
        # High cooperation: favor trust-based games
        if MatrixType.STAG_HUNT not in available:
            available.append(MatrixType.STAG_HUNT)
        if MatrixType.HARMONY not in available:
            available.append(MatrixType.HARMONY)
    elif cooperation_score <= 3:
        # Low cooperation: favor confrontational games
        if MatrixType.CHICKEN not in available:
            available.append(MatrixType.CHICKEN)
        if MatrixType.DEADLOCK not in available:
            available.append(MatrixType.DEADLOCK)

    # Remove immediately previous type to ensure variety
    if previous_types:
        last_type = previous_types[-1]
        available = [t for t in available if t != last_type]

    # If we filtered everything, fall back to all types except the last
    if not available:
        all_types = list(MatrixType)
        if previous_types:
            available = [t for t in all_types if t != previous_types[-1]]
        else:
            available = all_types

    return available


def scale_parameters_for_act(
    params: MatrixParameters,
    act: int,
) -> MatrixParameters:
    """Apply act-based scaling to matrix parameters.

    Act I (turns 1-4): Delta scaling x0.7 (lower stakes)
    Act II (turns 5-8): Delta scaling x1.0 (standard stakes)
    Act III (turns 9+): Delta scaling x1.3 (higher stakes)
    """
    scale_factor = ACT_SCALING.get(act, 1.0)
    new_scale = params.scale * scale_factor

    return MatrixParameters(
        scale=new_scale,
        position_weight=params.position_weight,
        resource_weight=params.resource_weight,
        risk_weight=params.risk_weight,
        temptation=params.temptation,
        reward=params.reward,
        punishment=params.punishment,
        sucker=params.sucker,
        swerve_payoff=params.swerve_payoff,
        crash_payoff=params.crash_payoff,
        coordination_bonus=params.coordination_bonus,
        miscoordination_penalty=params.miscoordination_penalty,
        preference_a=params.preference_a,
        preference_b=params.preference_b,
        stag_payoff=params.stag_payoff,
        hare_temptation=params.hare_temptation,
        hare_safe=params.hare_safe,
        stag_fail=params.stag_fail,
        volunteer_cost=params.volunteer_cost,
        free_ride_bonus=params.free_ride_bonus,
        disaster_penalty=params.disaster_penalty,
        inspection_cost=params.inspection_cost,
        cheat_gain=params.cheat_gain,
        caught_penalty=params.caught_penalty,
        loss_if_exploited=params.loss_if_exploited,
    )


def validate_and_build_matrix(
    matrix_type: MatrixType,
    params: MatrixParameters,
) -> bool:
    """Validate that parameters can build a valid matrix.

    Returns True if the matrix can be built, False otherwise.
    This is a validation step before storing in scenario.
    """
    constructor = CONSTRUCTORS.get(matrix_type)
    if constructor is None:
        return False

    constructor.validate_params(params)
    build_matrix(matrix_type, params)
    return True


def parse_matrix_type(type_str: str) -> MatrixType:
    """Parse a matrix type string to MatrixType enum.

    Handles both value format (e.g., "prisoners_dilemma") and
    name format (e.g., "PRISONERS_DILEMMA").
    """
    type_str = type_str.strip().upper()

    # Try by name first
    for mt in MatrixType:
        if mt.name == type_str or mt.value.upper() == type_str:
            return mt

    raise ValueError(f"Unknown matrix type: {type_str}")


def parse_matrix_parameters(
    matrix_type: MatrixType,
    params_dict: dict[str, Any],
) -> MatrixParameters:
    """Parse a dictionary of parameters into a MatrixParameters object.

    Uses default values for the given type, then overrides with provided values.
    """
    # Start with defaults for this type
    defaults = get_default_params_for_type(matrix_type)

    # Build kwargs with defaults, overriding with provided values
    kwargs: dict[str, Any] = {
        "scale": params_dict.get("scale", defaults.scale),
        "position_weight": params_dict.get("position_weight", defaults.position_weight),
        "resource_weight": params_dict.get("resource_weight", defaults.resource_weight),
        "risk_weight": params_dict.get("risk_weight", defaults.risk_weight),
        "temptation": params_dict.get("temptation", defaults.temptation),
        "reward": params_dict.get("reward", defaults.reward),
        "punishment": params_dict.get("punishment", defaults.punishment),
        "sucker": params_dict.get("sucker", defaults.sucker),
        "swerve_payoff": params_dict.get("swerve_payoff", defaults.swerve_payoff),
        "crash_payoff": params_dict.get("crash_payoff", defaults.crash_payoff),
        "coordination_bonus": params_dict.get("coordination_bonus", defaults.coordination_bonus),
        "miscoordination_penalty": params_dict.get("miscoordination_penalty", defaults.miscoordination_penalty),
        "preference_a": params_dict.get("preference_a", defaults.preference_a),
        "preference_b": params_dict.get("preference_b", defaults.preference_b),
        "stag_payoff": params_dict.get("stag_payoff", defaults.stag_payoff),
        "hare_temptation": params_dict.get("hare_temptation", defaults.hare_temptation),
        "hare_safe": params_dict.get("hare_safe", defaults.hare_safe),
        "stag_fail": params_dict.get("stag_fail", defaults.stag_fail),
        "volunteer_cost": params_dict.get("volunteer_cost", defaults.volunteer_cost),
        "free_ride_bonus": params_dict.get("free_ride_bonus", defaults.free_ride_bonus),
        "disaster_penalty": params_dict.get("disaster_penalty", defaults.disaster_penalty),
        "inspection_cost": params_dict.get("inspection_cost", defaults.inspection_cost),
        "cheat_gain": params_dict.get("cheat_gain", defaults.cheat_gain),
        "caught_penalty": params_dict.get("caught_penalty", defaults.caught_penalty),
        "loss_if_exploited": params_dict.get("loss_if_exploited", defaults.loss_if_exploited),
    }

    return MatrixParameters(**kwargs)


class ScenarioGenerator:
    """LLM-based scenario generator using Claude Agent SDK.

    The generator creates complete game scenarios with:
    - Narrative briefings for each turn
    - Matrix type selections appropriate for act and theme
    - Matrix parameters within valid ranges
    - Branching structure for outcome-dependent paths

    The generator follows the constructor pattern:
    - LLM outputs matrix_type + matrix_parameters only
    - Raw payoffs are never generated
    - All parameters are validated before storage
    """

    async def generate_scenario(
        self,
        theme: str,
        setting: str,
        time_period: str = "",
        player_a_role: str = "Player A",
        player_b_role: str = "Player B",
        additional_context: str = "",
        num_turns: int | None = None,
        previous_errors: list[str] | None = None,
    ) -> Scenario:
        """Generate a complete scenario using LLM.

        Args:
            theme: The thematic category (crisis, rivals, allies, espionage, or custom)
            setting: Description of the scenario setting
            time_period: Historical or fictional time period
            player_a_role: Description of Player A's role
            player_b_role: Description of Player B's role
            additional_context: Any additional context for generation
            num_turns: Target number of turns (12-16, randomized if not specified)
            previous_errors: List of validation errors from previous attempt to fix

        Returns:
            A validated Scenario object with all matrices constructable.
        """
        # Randomize turn count if not specified (12-16 range)
        num_turns = random.randint(12, 16) if num_turns is None else max(12, min(16, num_turns))

        # Add error feedback to additional context if provided
        error_context = additional_context
        if previous_errors:
            error_feedback = (
                "\n\nPREVIOUS ATTEMPT FAILED VALIDATION. Fix these issues:\n"
                + "\n".join(f"- {error}" for error in previous_errors)
                + "\n\nEnsure all branch targets exist, default_next points to valid turns, "
                "and matrix parameters are balanced."
            )
            error_context = additional_context + error_feedback

        # Format the generation prompt
        user_prompt = format_scenario_generation_prompt(
            theme=theme,
            setting=setting,
            time_period=time_period,
            player_a_role=player_a_role,
            player_b_role=player_b_role,
            additional_context=error_context,
            num_turns=num_turns,
        )

        # Call LLM to generate the scenario
        response = await generate_json(
            prompt=user_prompt,
            system_prompt=SCENARIO_GENERATION_SYSTEM_PROMPT,
        )

        # Parse and validate the response
        scenario = self._parse_scenario_response(response, theme, setting, num_turns)

        # Verify all matrices can be constructed
        scenario.construct_all_matrices()

        return scenario

    async def generate_turn(
        self,
        turn_number: int,
        theme: str,
        setting: str,
        previous_matrix_types: list[MatrixType],
        current_state: dict[str, Any] | None = None,
    ) -> TurnDefinition:
        """Generate a single turn definition.

        This method generates a turn with appropriate matrix type and parameters
        based on the current state and previous turns.

        Args:
            turn_number: The turn number (1-16)
            theme: The scenario theme
            setting: The scenario setting
            previous_matrix_types: List of matrix types used in previous turns
            current_state: Current game state dict with risk_level, cooperation_score, etc.

        Returns:
            A validated TurnDefinition with constructable matrix.
        """
        if current_state is None:
            current_state = {
                "risk_level": 2.0,
                "cooperation_score": 5.0,
                "stability": 5.0,
                "position_a": 5.0,
                "position_b": 5.0,
            }

        act = get_act_for_turn(turn_number)

        # Get available types for this turn
        available_types = get_available_types_for_turn(
            turn=turn_number,
            theme=theme,
            previous_types=previous_matrix_types,
            risk_level=current_state.get("risk_level", 5.0),
            cooperation_score=current_state.get("cooperation_score", 5.0),
        )

        # Format the turn generation prompt
        user_prompt = format_turn_generation_prompt(
            turn_number=turn_number,
            act_number=act,
            risk_level=current_state.get("risk_level", 5.0),
            cooperation_score=current_state.get("cooperation_score", 5.0),
            stability=current_state.get("stability", 5.0),
            position_a=current_state.get("position_a", 5.0),
            position_b=current_state.get("position_b", 5.0),
            previous_result="Game starting" if turn_number == 1 else "Turn in progress",
            previous_matrix_types=[t.value for t in previous_matrix_types],
            theme=theme,
            setting=setting,
        )

        # Call LLM to generate the turn
        response = await generate_json(
            prompt=user_prompt,
            system_prompt=SCENARIO_GENERATION_SYSTEM_PROMPT,
        )

        # Parse and validate the response
        turn_def = self._parse_turn_response(response, turn_number, act, available_types)

        return turn_def

    def _parse_scenario_response(
        self,
        response: dict[str, Any],
        theme: str,
        setting: str,
        num_turns: int,
    ) -> Scenario:
        """Parse LLM response into a validated Scenario object.

        Validates all matrix parameters and ensures they can build valid matrices.
        """
        # Generate scenario ID if not provided
        scenario_id = response.get("scenario_id") or f"scenario_{uuid.uuid4().hex[:8]}"

        # Parse title and setting
        title = response.get("title", f"Scenario: {theme}")

        # Parse turns
        turns_data = response.get("turns", [])
        turns: list[TurnDefinition] = []
        used_types: set[MatrixType] = set()

        for turn_data in turns_data:
            turn_def = self._parse_turn_data(turn_data)
            turns.append(turn_def)
            used_types.add(turn_def.matrix_type)

        # If we don't have enough turns, generate minimal ones
        while len(turns) < num_turns:
            turn_num = len(turns) + 1
            turn_def = self._create_fallback_turn(
                turn_num,
                theme,
                [t.matrix_type for t in turns],
            )
            turns.append(turn_def)
            used_types.add(turn_def.matrix_type)

        # Ensure we have at least 8 distinct matrix types
        # If not, replace some turns with different types
        turns = self._ensure_type_variety(turns, theme)

        # Parse branches
        branches_data = response.get("branches", {})
        branches: dict[str, TurnDefinition] = {}
        for branch_id, branch_data in branches_data.items():
            branch_def = self._parse_turn_data(branch_data)
            branches[branch_id] = branch_def

        return Scenario(
            scenario_id=scenario_id,
            title=title,
            setting=setting,
            max_turns=num_turns,
            turns=turns,
            branches=branches,
        )

    def _parse_turn_data(self, turn_data: dict[str, Any]) -> TurnDefinition:
        """Parse a single turn from LLM response data."""
        turn_num = int(turn_data.get("turn", 1))
        act = int(turn_data.get("act", get_act_for_turn(turn_num)))

        # Parse matrix type
        type_str = turn_data.get("matrix_type", "STAG_HUNT")
        matrix_type = parse_matrix_type(type_str)

        # Parse matrix parameters
        params_dict = turn_data.get("matrix_parameters", {})
        base_params = parse_matrix_parameters(matrix_type, params_dict)

        # Apply act scaling
        scaled_params = scale_parameters_for_act(base_params, act)

        # Validate the matrix can be built
        validate_and_build_matrix(matrix_type, scaled_params)

        # Parse outcome narratives
        narratives_data = turn_data.get("outcome_narratives", {})
        outcome_narratives = OutcomeNarratives(
            CC=narratives_data.get("CC", "Both sides chose cooperation."),
            CD=narratives_data.get("CD", "Player A cooperated, but Player B defected."),
            DC=narratives_data.get("DC", "Player A defected, while Player B cooperated."),
            DD=narratives_data.get("DD", "Both sides chose confrontation."),
        )

        # Parse branch targets
        branches_data = turn_data.get("branches", {})
        branch_targets = BranchTargets(
            CC=branches_data.get("CC"),
            CD=branches_data.get("CD"),
            DC=branches_data.get("DC"),
            DD=branches_data.get("DD"),
        )

        # Pass actions directly - Pydantic will validate against TurnAction schema
        actions_data = turn_data.get("actions", [])

        return TurnDefinition(
            turn=turn_num,
            act=act,
            narrative_briefing=turn_data.get("narrative_briefing", f"Turn {turn_num} situation briefing."),
            matrix_type=matrix_type,
            matrix_parameters=scaled_params,
            actions=actions_data,
            outcome_narratives=outcome_narratives,
            branches=branch_targets,
            default_next=turn_data.get("default_next"),
            settlement_available=turn_data.get("settlement_available", turn_num >= 5),
            settlement_failed_narrative=turn_data.get(
                "settlement_failed_narrative",
                "Negotiations collapsed. The crisis remains unresolved.",
            ),
        )

    def _parse_turn_response(
        self,
        response: dict[str, Any],
        expected_turn: int,
        expected_act: int,
        available_types: list[MatrixType],
    ) -> TurnDefinition:
        """Parse a turn generation response, ensuring constraints are met."""
        # Override turn/act if needed
        response["turn"] = expected_turn
        response["act"] = expected_act

        # Ensure matrix type is from available list
        type_str = response.get("matrix_type", "")
        selected_type: MatrixType | None = None

        if type_str:
            parsed_type = parse_matrix_type(type_str)
            if parsed_type in available_types:
                selected_type = parsed_type

        # Fall back to random available type if not valid
        if selected_type is None:
            selected_type = random.choice(available_types)
            response["matrix_type"] = selected_type.value

        return self._parse_turn_data(response)

    def _create_fallback_turn(
        self,
        turn_num: int,
        theme: str,
        previous_types: list[MatrixType],
    ) -> TurnDefinition:
        """Create a minimal valid turn when LLM response is incomplete."""
        act = get_act_for_turn(turn_num)

        # Select a valid type
        available = get_available_types_for_turn(
            turn=turn_num,
            theme=theme,
            previous_types=previous_types,
        )
        selected_type = random.choice(available)

        # Get default parameters and apply act scaling
        base_params = get_default_params_for_type(selected_type)
        scaled_params = scale_parameters_for_act(base_params, act)

        return TurnDefinition(
            turn=turn_num,
            act=act,
            narrative_briefing=f"Turn {turn_num}: The situation continues to develop.",
            matrix_type=selected_type,
            matrix_parameters=scaled_params,
            outcome_narratives=OutcomeNarratives(
                CC="Both sides chose cooperation, easing tensions.",
                CD="Your cooperation was met with defection.",
                DC="You pressed your advantage while they sought peace.",
                DD="Both sides stood firm, escalating the conflict.",
            ),
            branches=BranchTargets(),
            default_next=None,
            settlement_available=turn_num >= 5,
            settlement_failed_narrative="Negotiations failed. The standoff continues.",
        )

    def _ensure_type_variety(
        self,
        turns: list[TurnDefinition],
        theme: str,
    ) -> list[TurnDefinition]:
        """Ensure the scenario uses at least 8 distinct matrix types.

        Replaces some turns if needed to achieve variety.
        """
        used_types = {t.matrix_type for t in turns}

        # If we already have 8+ types, we're good
        min_required = min(8, len(turns) // 2 + 1)
        if len(used_types) >= min_required:
            return turns

        # Get all available types
        all_types = set(MatrixType)
        unused_types = list(all_types - used_types)

        # Find turns that share a type with another turn (duplicates)
        type_count: dict[MatrixType, list[int]] = {}
        for i, turn in enumerate(turns):
            if turn.matrix_type not in type_count:
                type_count[turn.matrix_type] = []
            type_count[turn.matrix_type].append(i)

        # Replace duplicate types with unused types
        modified_turns = list(turns)
        for _matrix_type, indices in type_count.items():
            if len(indices) > 1 and unused_types:
                # Keep the first occurrence, replace others
                for idx in indices[1:]:
                    if not unused_types:
                        break

                    new_type = unused_types.pop(0)
                    old_turn = modified_turns[idx]

                    # Create replacement turn with new type
                    base_params = get_default_params_for_type(new_type)
                    scaled_params = scale_parameters_for_act(base_params, old_turn.act)

                    modified_turns[idx] = TurnDefinition(
                        turn=old_turn.turn,
                        act=old_turn.act,
                        narrative_briefing=old_turn.narrative_briefing,
                        matrix_type=new_type,
                        matrix_parameters=scaled_params,
                        actions=old_turn.actions,
                        outcome_narratives=old_turn.outcome_narratives,
                        branches=old_turn.branches,
                        default_next=old_turn.default_next,
                        settlement_available=old_turn.settlement_available,
                        settlement_failed_narrative=old_turn.settlement_failed_narrative,
                    )

                    # Check if we have enough variety now
                    current_types = {t.matrix_type for t in modified_turns}
                    if len(current_types) >= min_required:
                        return modified_turns

        return modified_turns


# Convenience function for simple scenario generation
async def generate_scenario(
    theme: str,
    setting: str,
    **kwargs: Any,
) -> Scenario:
    """Generate a scenario with the given theme and setting.

    This is a convenience wrapper around ScenarioGenerator.generate_scenario.

    Args:
        theme: The thematic category (crisis, rivals, allies, espionage, or custom)
        setting: Description of the scenario setting
        **kwargs: Additional arguments passed to generate_scenario

    Returns:
        A validated Scenario object.
    """
    generator = ScenarioGenerator()
    return await generator.generate_scenario(theme=theme, setting=setting, **kwargs)
