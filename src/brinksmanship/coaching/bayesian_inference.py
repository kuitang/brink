"""Bayesian inference for opponent type analysis.

This module implements Bayesian updating to infer opponent strategy types
based on observed behavior during gameplay.

Opponent Types (from GAME_MANUAL.md and Axelrod's research):
- TitForTat: Cooperates first, then mirrors opponent's previous action
- GrimTrigger: Cooperates until betrayed, then defects forever
- Opportunist: Defects when ahead, cooperates when behind
- AlwaysCooperate: Always plays cooperative actions
- AlwaysDefect: Always plays competitive actions
- Random: Plays randomly (50-50)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Literal

from brinksmanship.models.actions import ActionType


class OpponentType(Enum):
    """Possible opponent strategy types."""

    TIT_FOR_TAT = "tit_for_tat"
    GRIM_TRIGGER = "grim_trigger"
    OPPORTUNIST = "opportunist"
    ALWAYS_COOPERATE = "always_cooperate"
    ALWAYS_DEFECT = "always_defect"
    RANDOM = "random"


@dataclass
class OpponentTypeDistribution:
    """Probability distribution over opponent types.

    Attributes:
        tit_for_tat: P(TitForTat)
        grim_trigger: P(GrimTrigger)
        opportunist: P(Opportunist)
        always_cooperate: P(AlwaysCooperate)
        always_defect: P(AlwaysDefect)
        random: P(Random)
    """

    tit_for_tat: float = field(default=1 / 6)
    grim_trigger: float = field(default=1 / 6)
    opportunist: float = field(default=1 / 6)
    always_cooperate: float = field(default=1 / 6)
    always_defect: float = field(default=1 / 6)
    random: float = field(default=1 / 6)

    def __post_init__(self) -> None:
        """Normalize probabilities to sum to 1."""
        self._normalize()

    def _normalize(self) -> None:
        """Ensure probabilities sum to 1."""
        total = (
            self.tit_for_tat
            + self.grim_trigger
            + self.opportunist
            + self.always_cooperate
            + self.always_defect
            + self.random
        )
        if total > 0:
            self.tit_for_tat /= total
            self.grim_trigger /= total
            self.opportunist /= total
            self.always_cooperate /= total
            self.always_defect /= total
            self.random /= total

    def get_probability(self, opponent_type: OpponentType) -> float:
        """Get probability for a specific opponent type."""
        mapping = {
            OpponentType.TIT_FOR_TAT: self.tit_for_tat,
            OpponentType.GRIM_TRIGGER: self.grim_trigger,
            OpponentType.OPPORTUNIST: self.opportunist,
            OpponentType.ALWAYS_COOPERATE: self.always_cooperate,
            OpponentType.ALWAYS_DEFECT: self.always_defect,
            OpponentType.RANDOM: self.random,
        }
        return mapping[opponent_type]

    def to_dict(self) -> dict[str, float]:
        """Convert to dictionary."""
        return {
            "tit_for_tat": self.tit_for_tat,
            "grim_trigger": self.grim_trigger,
            "opportunist": self.opportunist,
            "always_cooperate": self.always_cooperate,
            "always_defect": self.always_defect,
            "random": self.random,
        }


@dataclass
class ObservedAction:
    """A single observed action from the opponent.

    Attributes:
        turn: Turn number when action was observed
        opponent_action: The opponent's action type
        player_previous_action: Player's action on the previous turn (None for turn 1)
        position_difference: Player position - opponent position (estimated)
        was_betrayed_before: Whether opponent had been betrayed before this turn
    """

    turn: int
    opponent_action: ActionType
    player_previous_action: ActionType | None = None
    position_difference: float = 0.0
    was_betrayed_before: bool = False


class BayesianInference:
    """Bayesian inference engine for opponent type analysis.

    This class tracks opponent behavior and uses Bayesian updating to
    maintain probability estimates over different opponent strategy types.

    The inference is based on observing what action the opponent takes
    given the game context, and computing how likely each strategy type
    would be to produce that observation.
    """

    # Likelihood parameters: P(action | type, context)
    # These represent how likely each type is to take a specific action
    # given the context (previous actions, position, etc.)

    # Smoothing factor to avoid zero probabilities
    EPSILON = 0.01

    def __init__(
        self,
        prior: OpponentTypeDistribution | None = None,
    ) -> None:
        """Initialize the inference engine.

        Args:
            prior: Initial prior distribution. If None, uses uniform prior.
        """
        if prior is None:
            self.distribution = OpponentTypeDistribution()
        else:
            self.distribution = prior

        # Track observation history for trace output
        self._observations: list[ObservedAction] = []
        self._update_trace: list[dict] = []

    def update(self, observation: ObservedAction) -> None:
        """Update beliefs based on a new observation.

        Uses Bayes' rule:
            P(type | action) = P(action | type) * P(type) / P(action)

        Args:
            observation: The observed opponent action and context
        """
        self._observations.append(observation)

        # Compute likelihoods: P(action | type, context)
        likelihoods = self._compute_likelihoods(observation)

        # Get current priors
        priors = {
            OpponentType.TIT_FOR_TAT: self.distribution.tit_for_tat,
            OpponentType.GRIM_TRIGGER: self.distribution.grim_trigger,
            OpponentType.OPPORTUNIST: self.distribution.opportunist,
            OpponentType.ALWAYS_COOPERATE: self.distribution.always_cooperate,
            OpponentType.ALWAYS_DEFECT: self.distribution.always_defect,
            OpponentType.RANDOM: self.distribution.random,
        }

        # Compute unnormalized posteriors: P(type) * P(action | type)
        posteriors = {}
        for opp_type in OpponentType:
            posteriors[opp_type] = priors[opp_type] * likelihoods[opp_type]

        # Normalize
        total = sum(posteriors.values())
        if total > 0:
            for opp_type in OpponentType:
                posteriors[opp_type] /= total

        # Store trace information
        self._update_trace.append(
            {
                "turn": observation.turn,
                "opponent_action": observation.opponent_action.value,
                "likelihoods": {t.value: l for t, l in likelihoods.items()},
                "posteriors": {t.value: p for t, p in posteriors.items()},
            }
        )

        # Update distribution
        self.distribution = OpponentTypeDistribution(
            tit_for_tat=posteriors[OpponentType.TIT_FOR_TAT],
            grim_trigger=posteriors[OpponentType.GRIM_TRIGGER],
            opportunist=posteriors[OpponentType.OPPORTUNIST],
            always_cooperate=posteriors[OpponentType.ALWAYS_COOPERATE],
            always_defect=posteriors[OpponentType.ALWAYS_DEFECT],
            random=posteriors[OpponentType.RANDOM],
        )

    def _compute_likelihoods(
        self,
        observation: ObservedAction,
    ) -> dict[OpponentType, float]:
        """Compute P(action | type, context) for each opponent type.

        This is the core of the inference model. For each type, we estimate
        how likely they would be to take the observed action given the context.

        Returns:
            Dictionary mapping opponent types to likelihood values.
        """
        action = observation.opponent_action
        prev_action = observation.player_previous_action
        pos_diff = observation.position_difference
        was_betrayed = observation.was_betrayed_before
        turn = observation.turn

        is_cooperative = action == ActionType.COOPERATIVE
        is_competitive = action == ActionType.COMPETITIVE

        likelihoods = {}

        # TitForTat: Cooperate first, then mirror opponent's previous action
        if turn == 1 or prev_action is None:
            # First turn: TitForTat cooperates
            likelihoods[OpponentType.TIT_FOR_TAT] = (
                0.95 if is_cooperative else self.EPSILON
            )
        else:
            # Mirror previous action
            if prev_action == ActionType.COOPERATIVE:
                likelihoods[OpponentType.TIT_FOR_TAT] = (
                    0.95 if is_cooperative else self.EPSILON
                )
            else:
                likelihoods[OpponentType.TIT_FOR_TAT] = (
                    0.95 if is_competitive else self.EPSILON
                )

        # GrimTrigger: Cooperate until betrayed, then defect forever
        if was_betrayed:
            # After betrayal: always defect
            likelihoods[OpponentType.GRIM_TRIGGER] = (
                0.98 if is_competitive else self.EPSILON
            )
        else:
            # Before betrayal: always cooperate
            likelihoods[OpponentType.GRIM_TRIGGER] = (
                0.95 if is_cooperative else self.EPSILON
            )

        # Opportunist: Defect when ahead, cooperate when behind
        if pos_diff < -0.5:
            # Opponent is ahead (positive for them, negative for player)
            likelihoods[OpponentType.OPPORTUNIST] = (
                0.85 if is_competitive else 0.15
            )
        elif pos_diff > 0.5:
            # Opponent is behind
            likelihoods[OpponentType.OPPORTUNIST] = (
                0.85 if is_cooperative else 0.15
            )
        else:
            # Roughly equal
            likelihoods[OpponentType.OPPORTUNIST] = 0.5

        # AlwaysCooperate: Always cooperate
        likelihoods[OpponentType.ALWAYS_COOPERATE] = (
            0.98 if is_cooperative else self.EPSILON
        )

        # AlwaysDefect: Always defect
        likelihoods[OpponentType.ALWAYS_DEFECT] = (
            0.98 if is_competitive else self.EPSILON
        )

        # Random: 50-50
        likelihoods[OpponentType.RANDOM] = 0.5

        return likelihoods

    def get_most_likely_type(self) -> tuple[OpponentType, float]:
        """Get the most likely opponent type and its probability.

        Returns:
            Tuple of (most_likely_type, probability)
        """
        probs = {
            OpponentType.TIT_FOR_TAT: self.distribution.tit_for_tat,
            OpponentType.GRIM_TRIGGER: self.distribution.grim_trigger,
            OpponentType.OPPORTUNIST: self.distribution.opportunist,
            OpponentType.ALWAYS_COOPERATE: self.distribution.always_cooperate,
            OpponentType.ALWAYS_DEFECT: self.distribution.always_defect,
            OpponentType.RANDOM: self.distribution.random,
        }

        best_type = max(probs, key=lambda t: probs[t])
        return best_type, probs[best_type]

    def get_distribution(self) -> OpponentTypeDistribution:
        """Get the current probability distribution."""
        return self.distribution

    def format_inference_trace(self) -> str:
        """Format the inference trace for display.

        Returns:
            Human-readable string showing the inference history.
        """
        if not self._update_trace:
            return "No observations recorded."

        lines = ["Bayesian Inference Trace", "=" * 40]

        for update in self._update_trace:
            lines.append(f"\nTurn {update['turn']}:")
            lines.append(f"  Opponent action: {update['opponent_action']}")
            lines.append("  Likelihoods:")
            for type_name, likelihood in update["likelihoods"].items():
                lines.append(f"    {type_name}: {likelihood:.3f}")
            lines.append("  Posteriors:")
            for type_name, posterior in update["posteriors"].items():
                lines.append(f"    {type_name}: {posterior:.3f}")

        # Final summary
        best_type, prob = self.get_most_likely_type()
        lines.append("\n" + "=" * 40)
        lines.append(f"Most likely type: {best_type.value} ({prob:.1%})")

        return "\n".join(lines)

    def reset(self, prior: OpponentTypeDistribution | None = None) -> None:
        """Reset the inference engine to initial state.

        Args:
            prior: New prior distribution. If None, uses uniform prior.
        """
        if prior is None:
            self.distribution = OpponentTypeDistribution()
        else:
            self.distribution = prior
        self._observations = []
        self._update_trace = []
