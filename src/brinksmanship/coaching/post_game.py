"""Post-game coaching analysis for Brinksmanship.

This module provides the PostGameCoach class that analyzes completed games
and provides structured feedback to help players improve their strategic play.

The coach uses LLM analysis to:
- Assess overall game performance
- Identify critical decision points
- Analyze opponent patterns
- Extract strategic lessons
- Provide actionable recommendations
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from brinksmanship.coaching.bayesian_inference import (
    BayesianInference,
    ObservedAction,
    OpponentType,
    OpponentTypeDistribution,
)
from brinksmanship.engine.game_engine import EndingType, GameEnding, TurnRecord
from brinksmanship.llm import generate_text
from brinksmanship.models.actions import ActionType
from brinksmanship.models.matrices import MatrixType
from brinksmanship.models.state import GameState
from brinksmanship.prompts import COACHING_SYSTEM_PROMPT, format_coaching_prompt


@dataclass
class CriticalDecision:
    """Analysis of a critical decision point in the game.

    Attributes:
        turn: Turn number where the decision occurred.
        player_action: The action the player took.
        opponent_action: The action the opponent took.
        analysis: Explanation of why this decision was significant.
        alternative: What the player could have done differently.
    """

    turn: int
    player_action: str
    opponent_action: str
    analysis: str
    alternative: str


@dataclass
class CoachingReport:
    """Complete post-game coaching analysis.

    Attributes:
        overall_assessment: High-level summary of game performance.
        critical_decisions: List of key decision points analyzed.
        opponent_analysis: Analysis of the opponent's strategy and patterns.
        strategic_lessons: Game theory concepts and lessons from the game.
        recommendations: Actionable improvement suggestions.
        bayesian_inference_trace: Mathematical trace of opponent type inference.
        inferred_opponent_type: Most likely opponent type from Bayesian analysis.
        inferred_type_probability: Probability of the inferred opponent type.
        raw_analysis: Full LLM response for reference.
    """

    overall_assessment: str
    critical_decisions: list[CriticalDecision]
    opponent_analysis: str
    strategic_lessons: str
    recommendations: list[str]
    bayesian_inference_trace: str
    inferred_opponent_type: OpponentType
    inferred_type_probability: float
    raw_analysis: str = field(repr=False)


def _get_act_for_turn(turn: int) -> int:
    """Determine act number from turn number."""
    if turn <= 4:
        return 1
    elif turn <= 8:
        return 2
    else:
        return 3


def format_turn_history(history: list[TurnRecord]) -> str:
    """Format turn history into a readable string for the LLM prompt.

    Creates a structured representation of each turn including:
    - Turn number and act
    - Actions taken by both players
    - Outcome code
    - Game state after resolution

    Args:
        history: List of TurnRecord objects from a completed game.

    Returns:
        Formatted string representation of the game history.
    """
    lines = []

    for record in history:
        act = _get_act_for_turn(record.turn)
        act_names = {1: "Act I", 2: "Act II", 3: "Act III"}

        # Turn header
        lines.append(f"Turn {record.turn} ({act_names[act]}):")

        # Actions
        if record.action_a is not None:
            action_type_a = "Cooperative" if record.action_a.action_type == ActionType.COOPERATIVE else "Competitive"
            lines.append(f"  Player A: {record.action_a.name} ({action_type_a})")
        else:
            lines.append("  Player A: No action recorded")

        if record.action_b is not None:
            action_type_b = "Cooperative" if record.action_b.action_type == ActionType.COOPERATIVE else "Competitive"
            lines.append(f"  Player B: {record.action_b.name} ({action_type_b})")
        else:
            lines.append("  Player B: No action recorded")

        # Outcome
        if record.outcome is not None:
            outcome_desc = _get_outcome_description(record.outcome.outcome_code)
            lines.append(f"  Outcome: {record.outcome.outcome_code} - {outcome_desc}")
        else:
            lines.append("  Outcome: Not resolved")

        # State after turn
        if record.state_after is not None:
            state = record.state_after
            lines.append(
                f"  State: Position A={state.position_a:.1f}, B={state.position_b:.1f}, "
                f"Risk={state.risk_level:.1f}, Coop={state.cooperation_score:.1f}, "
                f"Stability={state.stability:.1f}"
            )

        # Matrix type if available
        if record.matrix_type is not None:
            lines.append(f"  Game Type: {_format_matrix_type(record.matrix_type)}")

        # Narrative snippet if available
        if record.narrative:
            # Truncate long narratives
            narrative = record.narrative[:150] + "..." if len(record.narrative) > 150 else record.narrative
            lines.append(f"  Narrative: {narrative}")

        lines.append("")  # Blank line between turns

    return "\n".join(lines)


def _get_outcome_description(outcome_code: str) -> str:
    """Get a human-readable description of an outcome code."""
    descriptions = {
        "CC": "Mutual cooperation",
        "CD": "Player A cooperated, B competed - A loses position",
        "DC": "Player A competed, B cooperated - B loses position",
        "DD": "Mutual competition",
        "RECON": "Reconnaissance game",
        "INSPECT": "Inspection game",
        "SETTLE": "Settlement reached",
        "SETTLE_FAIL": "Settlement failed",
    }
    return descriptions.get(outcome_code, "Unknown outcome")


def _format_matrix_type(matrix_type: MatrixType) -> str:
    """Format a MatrixType enum into a readable string."""
    name_mapping = {
        MatrixType.PRISONERS_DILEMMA: "Prisoner's Dilemma",
        MatrixType.DEADLOCK: "Deadlock",
        MatrixType.HARMONY: "Harmony",
        MatrixType.CHICKEN: "Chicken",
        MatrixType.VOLUNTEERS_DILEMMA: "Volunteer's Dilemma",
        MatrixType.WAR_OF_ATTRITION: "War of Attrition",
        MatrixType.PURE_COORDINATION: "Pure Coordination",
        MatrixType.STAG_HUNT: "Stag Hunt",
        MatrixType.BATTLE_OF_SEXES: "Battle of the Sexes",
        MatrixType.LEADER: "Leader",
        MatrixType.MATCHING_PENNIES: "Matching Pennies",
        MatrixType.INSPECTION_GAME: "Inspection Game",
        MatrixType.RECONNAISSANCE: "Reconnaissance",
        MatrixType.SECURITY_DILEMMA: "Security Dilemma",
    }
    return name_mapping.get(matrix_type, matrix_type.value)


def _format_ending_type(ending_type: EndingType) -> str:
    """Format an EndingType enum into a readable string."""
    name_mapping = {
        EndingType.MUTUAL_DESTRUCTION: "Mutual Destruction (Risk reached 10)",
        EndingType.POSITION_COLLAPSE_A: "Player A Position Collapse",
        EndingType.POSITION_COLLAPSE_B: "Player B Position Collapse",
        EndingType.RESOURCE_EXHAUSTION_A: "Player A Resource Exhaustion",
        EndingType.RESOURCE_EXHAUSTION_B: "Player B Resource Exhaustion",
        EndingType.CRISIS_TERMINATION: "Crisis Termination (probabilistic ending)",
        EndingType.NATURAL_ENDING: "Natural Ending (max turns reached)",
        EndingType.SETTLEMENT: "Negotiated Settlement",
    }
    return name_mapping.get(ending_type, ending_type.value)


class PostGameCoach:
    """Provides post-game coaching analysis for completed Brinksmanship games.

    The coach analyzes completed games and provides structured feedback including:
    - Overall assessment of performance
    - Critical decision point analysis
    - Opponent pattern recognition
    - Strategic lessons and game theory concepts
    - Actionable recommendations for improvement
    - Mathematically correct Bayesian inference trace

    Example:
        >>> coach = PostGameCoach()
        >>> report = await coach.analyze_game(
        ...     history=game_engine.get_history(),
        ...     ending=game_engine.get_ending(),
        ...     final_state=game_engine.get_current_state(),
        ...     player_role="Player A",
        ...     opponent_type="AI - Tit-for-Tat"
        ... )
        >>> print(report.overall_assessment)
        >>> print(report.bayesian_inference_trace)  # Mathematical trace
    """

    def __init__(self) -> None:
        """Initialize the PostGameCoach."""
        # No state needed - each analysis is independent
        pass

    def run_bayesian_inference(
        self,
        history: list[TurnRecord],
        player_is_a: bool = True,
    ) -> tuple[BayesianInference, OpponentType, float]:
        """Run Bayesian inference over game history to infer opponent type.

        This performs mathematically correct Bayesian updating based on
        the opponent's observed actions and the game context.

        Args:
            history: Complete turn history from the game.
            player_is_a: True if analyzing from Player A's perspective,
                False for Player B's perspective.

        Returns:
            Tuple of (inference_engine, most_likely_type, probability)
        """
        inference = BayesianInference()
        was_betrayed = False
        previous_player_action: ActionType | None = None

        for record in history:
            if record.action_a is None or record.action_b is None:
                continue
            if record.state_before is None:
                continue

            # Get actions from appropriate perspective
            if player_is_a:
                opponent_action = record.action_b.action_type
                player_action = record.action_a.action_type
                # Position difference from player's perspective (estimated)
                pos_diff = record.state_before.position_a - record.state_before.position_b
            else:
                opponent_action = record.action_a.action_type
                player_action = record.action_b.action_type
                pos_diff = record.state_before.position_b - record.state_before.position_a

            # Create observation
            observation = ObservedAction(
                turn=record.turn,
                opponent_action=opponent_action,
                player_previous_action=previous_player_action,
                position_difference=pos_diff,
                was_betrayed_before=was_betrayed,
            )

            # Update inference
            inference.update(observation)

            # Track state for next iteration
            previous_player_action = player_action

            # Check if player was betrayed (opponent defected while player cooperated)
            if player_action == ActionType.COOPERATIVE and opponent_action == ActionType.COMPETITIVE:
                was_betrayed = True

        most_likely_type, probability = inference.get_most_likely_type()
        return inference, most_likely_type, probability

    async def analyze_game(
        self,
        history: list[TurnRecord],
        ending: GameEnding,
        final_state: GameState,
        player_role: str,
        opponent_type: str,
        player_is_a: bool = True,
    ) -> CoachingReport:
        """Analyze a completed game and generate coaching feedback.

        Args:
            history: Complete turn history from the game.
            ending: The game ending information (VP distribution, ending type).
            final_state: The final game state.
            player_role: Description of the player's role (e.g., "Player A",
                "Soviet Premier", etc.).
            opponent_type: Description of the opponent (e.g., "Human",
                "AI - Bismarck", "Random").
            player_is_a: True if analyzing from Player A's perspective.

        Returns:
            CoachingReport with structured analysis and recommendations.
        """
        # Run Bayesian inference to get mathematically correct type inference
        inference, inferred_type, type_probability = self.run_bayesian_inference(
            history, player_is_a
        )
        inference_trace = inference.format_inference_trace()

        # Format the turn history for the prompt
        turn_history = format_turn_history(history)

        # Build the prompt (include Bayesian inference summary for LLM context)
        bayesian_summary = (
            f"Bayesian analysis inferred opponent type: {inferred_type.value} "
            f"(probability: {type_probability:.1%})"
        )

        prompt = format_coaching_prompt(
            turns_played=ending.turn,
            player_vp=int(ending.vp_a) if player_is_a else int(ending.vp_b),
            opponent_vp=int(ending.vp_b) if player_is_a else int(ending.vp_a),
            ending_type=_format_ending_type(ending.ending_type),
            final_risk=final_state.risk_level,
            final_cooperation=final_state.cooperation_score,
            turn_history=turn_history,
            player_role=player_role,
            opponent_type=opponent_type,
            bayesian_summary=bayesian_summary,
        )

        # Generate the analysis
        raw_analysis = await generate_text(
            prompt=prompt,
            system_prompt=COACHING_SYSTEM_PROMPT,
        )

        # Parse the response into structured format
        report = self._parse_analysis(
            raw_analysis,
            history,
            inference_trace,
            inferred_type,
            type_probability,
        )

        return report

    def _parse_analysis(
        self,
        raw_analysis: str,
        history: list[TurnRecord],
        inference_trace: str,
        inferred_type: OpponentType,
        type_probability: float,
    ) -> CoachingReport:
        """Parse the LLM response into a structured CoachingReport.

        The LLM is prompted to use specific headers, which we use to extract
        the different sections. If parsing fails for any section, we provide
        sensible defaults.

        Args:
            raw_analysis: The raw text response from the LLM.
            history: The turn history (used for extracting critical decisions).
            inference_trace: The Bayesian inference trace from mathematical analysis.
            inferred_type: The most likely opponent type from Bayesian inference.
            type_probability: Probability of the inferred opponent type.

        Returns:
            Structured CoachingReport.
        """
        # Extract sections using headers from the prompt template
        overall_assessment = self._extract_section(
            raw_analysis,
            ["OVERALL ASSESSMENT", "1. OVERALL ASSESSMENT", "## OVERALL ASSESSMENT"],
            ["CRITICAL DECISIONS", "2. CRITICAL DECISIONS", "## CRITICAL DECISIONS"],
        )

        critical_decisions_text = self._extract_section(
            raw_analysis,
            ["CRITICAL DECISIONS", "2. CRITICAL DECISIONS", "## CRITICAL DECISIONS"],
            ["OPPONENT ANALYSIS", "3. OPPONENT ANALYSIS", "## OPPONENT ANALYSIS"],
        )

        opponent_analysis = self._extract_section(
            raw_analysis,
            ["OPPONENT ANALYSIS", "3. OPPONENT ANALYSIS", "## OPPONENT ANALYSIS"],
            ["STRATEGIC LESSONS", "4. STRATEGIC LESSONS", "## STRATEGIC LESSONS"],
        )

        strategic_lessons = self._extract_section(
            raw_analysis,
            ["STRATEGIC LESSONS", "4. STRATEGIC LESSONS", "## STRATEGIC LESSONS"],
            ["SPECIFIC RECOMMENDATIONS", "5. SPECIFIC RECOMMENDATIONS", "## SPECIFIC RECOMMENDATIONS"],
        )

        recommendations_text = self._extract_section(
            raw_analysis,
            ["SPECIFIC RECOMMENDATIONS", "5. SPECIFIC RECOMMENDATIONS", "## SPECIFIC RECOMMENDATIONS"],
            [],  # No end marker, goes to end of text
        )

        # Parse critical decisions into structured format
        critical_decisions = self._parse_critical_decisions(critical_decisions_text, history)

        # Parse recommendations into list
        recommendations = self._parse_recommendations(recommendations_text)

        # Provide defaults for empty sections
        if not overall_assessment.strip():
            overall_assessment = "Analysis could not be extracted from the LLM response."

        if not opponent_analysis.strip():
            opponent_analysis = "Opponent analysis could not be extracted."

        if not strategic_lessons.strip():
            strategic_lessons = "Strategic lessons could not be extracted."

        if not recommendations:
            recommendations = ["Review the raw analysis for detailed recommendations."]

        return CoachingReport(
            overall_assessment=overall_assessment.strip(),
            critical_decisions=critical_decisions,
            opponent_analysis=opponent_analysis.strip(),
            strategic_lessons=strategic_lessons.strip(),
            recommendations=recommendations,
            bayesian_inference_trace=inference_trace,
            inferred_opponent_type=inferred_type,
            inferred_type_probability=type_probability,
            raw_analysis=raw_analysis,
        )

    def _extract_section(
        self,
        text: str,
        start_markers: list[str],
        end_markers: list[str],
    ) -> str:
        """Extract a section of text between markers.

        Args:
            text: The full text to search.
            start_markers: Possible section header variations.
            end_markers: Possible next section header variations.

        Returns:
            Extracted section text, or empty string if not found.
        """
        # Find the start position
        start_pos = -1
        for marker in start_markers:
            pos = text.find(marker)
            if pos != -1:
                # Move past the header line
                newline_pos = text.find("\n", pos)
                if newline_pos != -1:
                    start_pos = newline_pos + 1
                else:
                    start_pos = pos + len(marker)
                break

        if start_pos == -1:
            return ""

        # Find the end position
        end_pos = len(text)
        for marker in end_markers:
            pos = text.find(marker, start_pos)
            if pos != -1 and pos < end_pos:
                end_pos = pos

        return text[start_pos:end_pos].strip()

    def _parse_critical_decisions(
        self,
        text: str,
        history: list[TurnRecord],
    ) -> list[CriticalDecision]:
        """Parse critical decisions from the LLM text.

        Attempts to extract structured information about key decision points.
        Falls back to creating placeholder entries if parsing fails.

        Args:
            text: The critical decisions section text.
            history: Game history for reference.

        Returns:
            List of CriticalDecision objects.
        """
        decisions = []

        # Look for turn references in the text
        # Pattern: "Turn X" or "turn X"
        turn_pattern = re.compile(r"[Tt]urn\s+(\d+)", re.IGNORECASE)
        matches = turn_pattern.finditer(text)

        seen_turns: set[int] = set()
        for match in matches:
            turn_num = int(match.group(1))
            if turn_num in seen_turns:
                continue
            seen_turns.add(turn_num)

            # Find the corresponding history record
            record = None
            for r in history:
                if r.turn == turn_num:
                    record = r
                    break

            if record is None:
                continue

            # Extract player and opponent actions
            player_action = record.action_a.name if record.action_a else "Unknown"
            opponent_action = record.action_b.name if record.action_b else "Unknown"

            # Try to extract analysis around this turn mention
            # Get some context around the match
            start = max(0, match.start() - 50)
            end = min(len(text), match.end() + 500)
            context = text[start:end]

            # Create decision entry
            decisions.append(
                CriticalDecision(
                    turn=turn_num,
                    player_action=player_action,
                    opponent_action=opponent_action,
                    analysis=context.strip(),
                    alternative="See analysis for alternatives discussed.",
                )
            )

            # Limit to 3 critical decisions
            if len(decisions) >= 3:
                break

        # If we couldn't parse any, create a placeholder
        if not decisions and text.strip():
            decisions.append(
                CriticalDecision(
                    turn=0,
                    player_action="See raw analysis",
                    opponent_action="See raw analysis",
                    analysis=text[:500] + "..." if len(text) > 500 else text,
                    alternative="See raw analysis for detailed alternatives.",
                )
            )

        return decisions

    def _parse_recommendations(self, text: str) -> list[str]:
        """Parse recommendations from the LLM text into a list.

        Looks for numbered lists, bullet points, or line-separated items.

        Args:
            text: The recommendations section text.

        Returns:
            List of recommendation strings.
        """
        recommendations = []

        # Split by common list patterns
        # Try numbered lists first (1. 2. 3. or 1) 2) 3))
        numbered_pattern = re.compile(r"^\s*\d+[.)]\s*", re.MULTILINE)
        parts = numbered_pattern.split(text)

        # Filter out empty parts and clean up
        for part in parts:
            cleaned = part.strip()
            if cleaned and len(cleaned) > 10:  # Skip very short fragments
                # Remove leading bullet points or dashes
                cleaned = re.sub(r"^[-*]\s*", "", cleaned)
                # Limit length
                if len(cleaned) > 500:
                    cleaned = cleaned[:500] + "..."
                recommendations.append(cleaned)

        # If no numbered items found, try bullet points
        if not recommendations:
            bullet_pattern = re.compile(r"^\s*[-*]\s*", re.MULTILINE)
            parts = bullet_pattern.split(text)
            for part in parts:
                cleaned = part.strip()
                if cleaned and len(cleaned) > 10:
                    if len(cleaned) > 500:
                        cleaned = cleaned[:500] + "..."
                    recommendations.append(cleaned)

        # If still nothing, split by newlines
        if not recommendations:
            for line in text.split("\n"):
                cleaned = line.strip()
                if cleaned and len(cleaned) > 20:
                    if len(cleaned) > 500:
                        cleaned = cleaned[:500] + "..."
                    recommendations.append(cleaned)

        # Limit to 5 recommendations
        return recommendations[:5]
