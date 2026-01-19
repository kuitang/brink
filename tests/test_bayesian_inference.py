"""Tests for brinksmanship.coaching.bayesian_inference module.

Tests cover:
- OpponentType enum
- OpponentTypeDistribution dataclass (initialization, normalization, to_dict)
- ObservedAction dataclass
- BayesianInference class (update, likelihoods, inference, trace)

These tests are self-contained and verify the mathematical correctness
of the Bayesian inference implementation.
"""

import pytest

from brinksmanship.coaching.bayesian_inference import (
    BayesianInference,
    ObservedAction,
    OpponentType,
    OpponentTypeDistribution,
)
from brinksmanship.models.actions import ActionType


# =============================================================================
# OpponentType Enum Tests
# =============================================================================


class TestOpponentType:
    """Tests for OpponentType enum."""

    def test_all_types_exist(self):
        """Test all expected opponent types exist."""
        expected_types = {
            "tit_for_tat",
            "grim_trigger",
            "opportunist",
            "always_cooperate",
            "always_defect",
            "random",
        }
        actual_types = {t.value for t in OpponentType}
        assert actual_types == expected_types

    def test_enum_has_six_members(self):
        """Test OpponentType has exactly six members."""
        members = list(OpponentType)
        assert len(members) == 6


# =============================================================================
# OpponentTypeDistribution Tests
# =============================================================================


class TestOpponentTypeDistribution:
    """Tests for OpponentTypeDistribution dataclass."""

    def test_default_uniform_prior(self):
        """Test default initialization gives uniform prior."""
        dist = OpponentTypeDistribution()
        # Each of 6 types should have ~1/6 probability
        assert abs(dist.tit_for_tat - 1 / 6) < 0.001
        assert abs(dist.grim_trigger - 1 / 6) < 0.001
        assert abs(dist.opportunist - 1 / 6) < 0.001
        assert abs(dist.always_cooperate - 1 / 6) < 0.001
        assert abs(dist.always_defect - 1 / 6) < 0.001
        assert abs(dist.random - 1 / 6) < 0.001

    def test_normalization_on_init(self):
        """Test probabilities are normalized to sum to 1 on initialization."""
        dist = OpponentTypeDistribution(
            tit_for_tat=2.0,
            grim_trigger=2.0,
            opportunist=2.0,
            always_cooperate=2.0,
            always_defect=2.0,
            random=2.0,
        )
        total = (
            dist.tit_for_tat
            + dist.grim_trigger
            + dist.opportunist
            + dist.always_cooperate
            + dist.always_defect
            + dist.random
        )
        assert abs(total - 1.0) < 0.001

    def test_get_probability(self):
        """Test get_probability returns correct values."""
        dist = OpponentTypeDistribution(
            tit_for_tat=0.5,
            grim_trigger=0.1,
            opportunist=0.1,
            always_cooperate=0.1,
            always_defect=0.1,
            random=0.1,
        )
        # After normalization
        assert dist.get_probability(OpponentType.TIT_FOR_TAT) == dist.tit_for_tat
        assert dist.get_probability(OpponentType.GRIM_TRIGGER) == dist.grim_trigger

    def test_to_dict(self):
        """Test to_dict returns correct dictionary."""
        dist = OpponentTypeDistribution()
        d = dist.to_dict()
        assert "tit_for_tat" in d
        assert "grim_trigger" in d
        assert "opportunist" in d
        assert "always_cooperate" in d
        assert "always_defect" in d
        assert "random" in d
        assert len(d) == 6


# =============================================================================
# ObservedAction Tests
# =============================================================================


class TestObservedAction:
    """Tests for ObservedAction dataclass."""

    def test_create_first_turn_observation(self):
        """Test creating observation for first turn (no previous action)."""
        obs = ObservedAction(
            turn=1,
            opponent_action=ActionType.COOPERATIVE,
            player_previous_action=None,
            position_difference=0.0,
            was_betrayed_before=False,
        )
        assert obs.turn == 1
        assert obs.opponent_action == ActionType.COOPERATIVE
        assert obs.player_previous_action is None
        assert obs.was_betrayed_before is False

    def test_create_later_turn_observation(self):
        """Test creating observation for later turn with context."""
        obs = ObservedAction(
            turn=5,
            opponent_action=ActionType.COMPETITIVE,
            player_previous_action=ActionType.COOPERATIVE,
            position_difference=1.5,
            was_betrayed_before=True,
        )
        assert obs.turn == 5
        assert obs.opponent_action == ActionType.COMPETITIVE
        assert obs.player_previous_action == ActionType.COOPERATIVE
        assert obs.position_difference == 1.5
        assert obs.was_betrayed_before is True


# =============================================================================
# BayesianInference Tests
# =============================================================================


class TestBayesianInference:
    """Tests for BayesianInference class."""

    def test_init_with_default_prior(self):
        """Test initialization with uniform prior."""
        inference = BayesianInference()
        dist = inference.get_distribution()
        assert abs(dist.tit_for_tat - 1 / 6) < 0.001

    def test_init_with_custom_prior(self):
        """Test initialization with custom prior."""
        prior = OpponentTypeDistribution(
            tit_for_tat=0.5,
            grim_trigger=0.1,
            opportunist=0.1,
            always_cooperate=0.1,
            always_defect=0.1,
            random=0.1,
        )
        inference = BayesianInference(prior=prior)
        dist = inference.get_distribution()
        # After normalization, tit_for_tat should be 0.5
        assert dist.tit_for_tat == prior.tit_for_tat

    def test_update_always_cooperate_pattern(self):
        """Test inference correctly identifies always cooperate pattern."""
        inference = BayesianInference()

        # Simulate opponent always cooperating for 5 turns
        for turn in range(1, 6):
            obs = ObservedAction(
                turn=turn,
                opponent_action=ActionType.COOPERATIVE,
                player_previous_action=ActionType.COMPETITIVE if turn > 1 else None,
                position_difference=0.0,
                was_betrayed_before=False,
            )
            inference.update(obs)

        best_type, prob = inference.get_most_likely_type()
        # Should strongly favor always_cooperate
        assert best_type == OpponentType.ALWAYS_COOPERATE
        assert prob > 0.5

    def test_update_always_defect_pattern(self):
        """Test inference correctly identifies always defect pattern."""
        inference = BayesianInference()

        # Simulate opponent always defecting for 5 turns
        for turn in range(1, 6):
            obs = ObservedAction(
                turn=turn,
                opponent_action=ActionType.COMPETITIVE,
                player_previous_action=ActionType.COOPERATIVE if turn > 1 else None,
                position_difference=0.0,
                was_betrayed_before=turn > 1,  # Betrayed after first turn
            )
            inference.update(obs)

        best_type, prob = inference.get_most_likely_type()
        # Should strongly favor always_defect
        assert best_type == OpponentType.ALWAYS_DEFECT
        assert prob > 0.5

    def test_update_tit_for_tat_pattern(self):
        """Test inference correctly identifies tit-for-tat pattern."""
        inference = BayesianInference()

        # Turn 1: Opponent cooperates (TFT cooperates first)
        obs1 = ObservedAction(
            turn=1,
            opponent_action=ActionType.COOPERATIVE,
            player_previous_action=None,
            position_difference=0.0,
            was_betrayed_before=False,
        )
        inference.update(obs1)

        # Turn 2: Player cooperated, opponent cooperates (mirrors)
        obs2 = ObservedAction(
            turn=2,
            opponent_action=ActionType.COOPERATIVE,
            player_previous_action=ActionType.COOPERATIVE,
            position_difference=0.0,
            was_betrayed_before=False,
        )
        inference.update(obs2)

        # Turn 3: Player defected, opponent defects (mirrors)
        obs3 = ObservedAction(
            turn=3,
            opponent_action=ActionType.COMPETITIVE,
            player_previous_action=ActionType.COMPETITIVE,
            position_difference=0.0,
            was_betrayed_before=False,
        )
        inference.update(obs3)

        # Turn 4: Player cooperated, opponent cooperates (mirrors)
        obs4 = ObservedAction(
            turn=4,
            opponent_action=ActionType.COOPERATIVE,
            player_previous_action=ActionType.COOPERATIVE,
            position_difference=0.0,
            was_betrayed_before=False,
        )
        inference.update(obs4)

        best_type, prob = inference.get_most_likely_type()
        # Should favor tit_for_tat
        assert best_type == OpponentType.TIT_FOR_TAT
        assert prob > 0.3  # Should be reasonably confident

    def test_update_grim_trigger_pattern(self):
        """Test inference correctly identifies grim trigger pattern."""
        inference = BayesianInference()

        # Turns 1-3: Opponent cooperates
        for turn in range(1, 4):
            obs = ObservedAction(
                turn=turn,
                opponent_action=ActionType.COOPERATIVE,
                player_previous_action=ActionType.COOPERATIVE if turn > 1 else None,
                position_difference=0.0,
                was_betrayed_before=False,
            )
            inference.update(obs)

        # Turn 4: Player defects, opponent still cooperated this turn
        # but will switch next turn
        # Turn 5+: Player cooperates but opponent defects forever
        for turn in range(5, 8):
            obs = ObservedAction(
                turn=turn,
                opponent_action=ActionType.COMPETITIVE,
                player_previous_action=ActionType.COOPERATIVE,
                position_difference=0.0,
                was_betrayed_before=True,  # Was betrayed in turn 4
            )
            inference.update(obs)

        best_type, prob = inference.get_most_likely_type()
        # Should favor grim_trigger or always_defect (both defect after betrayal)
        assert best_type in [OpponentType.GRIM_TRIGGER, OpponentType.ALWAYS_DEFECT]

    def test_get_most_likely_type(self):
        """Test get_most_likely_type returns tuple of type and probability."""
        inference = BayesianInference()
        best_type, prob = inference.get_most_likely_type()
        assert isinstance(best_type, OpponentType)
        assert 0.0 <= prob <= 1.0

    def test_format_inference_trace_empty(self):
        """Test trace format with no observations."""
        inference = BayesianInference()
        trace = inference.format_inference_trace()
        assert "No observations recorded" in trace

    def test_format_inference_trace_with_observations(self):
        """Test trace format with observations."""
        inference = BayesianInference()
        obs = ObservedAction(
            turn=1,
            opponent_action=ActionType.COOPERATIVE,
            player_previous_action=None,
            position_difference=0.0,
            was_betrayed_before=False,
        )
        inference.update(obs)

        trace = inference.format_inference_trace()
        assert "Turn 1" in trace
        assert "Likelihoods" in trace
        assert "Posteriors" in trace
        assert "Most likely type" in trace

    def test_reset(self):
        """Test reset clears observations and restores prior."""
        inference = BayesianInference()

        # Make some updates
        obs = ObservedAction(
            turn=1,
            opponent_action=ActionType.COMPETITIVE,
            player_previous_action=None,
            position_difference=0.0,
            was_betrayed_before=False,
        )
        inference.update(obs)

        # Reset
        inference.reset()

        # Should be back to uniform
        dist = inference.get_distribution()
        assert abs(dist.tit_for_tat - 1 / 6) < 0.001
        assert abs(dist.always_defect - 1 / 6) < 0.001

        # Trace should be empty
        trace = inference.format_inference_trace()
        assert "No observations recorded" in trace

    def test_reset_with_custom_prior(self):
        """Test reset with custom prior."""
        inference = BayesianInference()

        # Make some updates
        obs = ObservedAction(
            turn=1,
            opponent_action=ActionType.COMPETITIVE,
            player_previous_action=None,
            position_difference=0.0,
            was_betrayed_before=False,
        )
        inference.update(obs)

        # Reset with custom prior
        custom_prior = OpponentTypeDistribution(
            tit_for_tat=0.8,
            grim_trigger=0.04,
            opportunist=0.04,
            always_cooperate=0.04,
            always_defect=0.04,
            random=0.04,
        )
        inference.reset(custom_prior)

        # Should match custom prior
        dist = inference.get_distribution()
        assert dist.tit_for_tat == custom_prior.tit_for_tat


# =============================================================================
# Likelihood Computation Tests
# =============================================================================


class TestLikelihoodComputation:
    """Tests for likelihood computation in specific scenarios."""

    def test_tit_for_tat_first_turn_cooperate_high_likelihood(self):
        """Test TFT has high likelihood for cooperation on turn 1."""
        inference = BayesianInference()
        obs = ObservedAction(
            turn=1,
            opponent_action=ActionType.COOPERATIVE,
            player_previous_action=None,
            position_difference=0.0,
            was_betrayed_before=False,
        )
        likelihoods = inference._compute_likelihoods(obs)
        # TFT should have high likelihood for cooperating on turn 1
        assert likelihoods[OpponentType.TIT_FOR_TAT] > 0.9

    def test_tit_for_tat_first_turn_defect_low_likelihood(self):
        """Test TFT has low likelihood for defection on turn 1."""
        inference = BayesianInference()
        obs = ObservedAction(
            turn=1,
            opponent_action=ActionType.COMPETITIVE,
            player_previous_action=None,
            position_difference=0.0,
            was_betrayed_before=False,
        )
        likelihoods = inference._compute_likelihoods(obs)
        # TFT should have very low likelihood for defecting on turn 1
        assert likelihoods[OpponentType.TIT_FOR_TAT] < 0.1

    def test_grim_trigger_cooperate_before_betrayal(self):
        """Test GrimTrigger has high likelihood for cooperation before betrayal."""
        inference = BayesianInference()
        obs = ObservedAction(
            turn=3,
            opponent_action=ActionType.COOPERATIVE,
            player_previous_action=ActionType.COOPERATIVE,
            position_difference=0.0,
            was_betrayed_before=False,
        )
        likelihoods = inference._compute_likelihoods(obs)
        assert likelihoods[OpponentType.GRIM_TRIGGER] > 0.9

    def test_grim_trigger_defect_after_betrayal(self):
        """Test GrimTrigger has high likelihood for defection after betrayal."""
        inference = BayesianInference()
        obs = ObservedAction(
            turn=5,
            opponent_action=ActionType.COMPETITIVE,
            player_previous_action=ActionType.COOPERATIVE,
            position_difference=0.0,
            was_betrayed_before=True,
        )
        likelihoods = inference._compute_likelihoods(obs)
        assert likelihoods[OpponentType.GRIM_TRIGGER] > 0.9

    def test_opportunist_defects_when_ahead(self):
        """Test Opportunist has high likelihood for defection when ahead."""
        inference = BayesianInference()
        obs = ObservedAction(
            turn=3,
            opponent_action=ActionType.COMPETITIVE,
            player_previous_action=ActionType.COOPERATIVE,
            position_difference=-2.0,  # Opponent is ahead (negative for player)
            was_betrayed_before=False,
        )
        likelihoods = inference._compute_likelihoods(obs)
        assert likelihoods[OpponentType.OPPORTUNIST] > 0.7

    def test_opportunist_cooperates_when_behind(self):
        """Test Opportunist has high likelihood for cooperation when behind."""
        inference = BayesianInference()
        obs = ObservedAction(
            turn=3,
            opponent_action=ActionType.COOPERATIVE,
            player_previous_action=ActionType.COMPETITIVE,
            position_difference=2.0,  # Opponent is behind (positive for player)
            was_betrayed_before=False,
        )
        likelihoods = inference._compute_likelihoods(obs)
        assert likelihoods[OpponentType.OPPORTUNIST] > 0.7

    def test_random_has_0_5_likelihood(self):
        """Test Random always has 0.5 likelihood regardless of action."""
        inference = BayesianInference()

        obs_coop = ObservedAction(
            turn=1,
            opponent_action=ActionType.COOPERATIVE,
            player_previous_action=None,
            position_difference=0.0,
            was_betrayed_before=False,
        )
        obs_defect = ObservedAction(
            turn=1,
            opponent_action=ActionType.COMPETITIVE,
            player_previous_action=None,
            position_difference=0.0,
            was_betrayed_before=False,
        )

        likelihoods_coop = inference._compute_likelihoods(obs_coop)
        likelihoods_defect = inference._compute_likelihoods(obs_defect)

        assert likelihoods_coop[OpponentType.RANDOM] == 0.5
        assert likelihoods_defect[OpponentType.RANDOM] == 0.5


# =============================================================================
# Mathematical Correctness Tests
# =============================================================================


class TestBayesianMathematics:
    """Tests verifying Bayesian mathematics are correct."""

    def test_posteriors_sum_to_one(self):
        """Test posteriors always sum to 1 after update."""
        inference = BayesianInference()

        obs = ObservedAction(
            turn=1,
            opponent_action=ActionType.COOPERATIVE,
            player_previous_action=None,
            position_difference=0.0,
            was_betrayed_before=False,
        )
        inference.update(obs)

        dist = inference.get_distribution()
        total = (
            dist.tit_for_tat
            + dist.grim_trigger
            + dist.opportunist
            + dist.always_cooperate
            + dist.always_defect
            + dist.random
        )
        assert abs(total - 1.0) < 0.001

    def test_multiple_updates_posteriors_sum_to_one(self):
        """Test posteriors sum to 1 after multiple updates."""
        inference = BayesianInference()

        for turn in range(1, 10):
            obs = ObservedAction(
                turn=turn,
                opponent_action=ActionType.COOPERATIVE if turn % 2 == 1 else ActionType.COMPETITIVE,
                player_previous_action=ActionType.COOPERATIVE if turn > 1 else None,
                position_difference=float(turn - 5),
                was_betrayed_before=turn > 3,
            )
            inference.update(obs)

        dist = inference.get_distribution()
        total = (
            dist.tit_for_tat
            + dist.grim_trigger
            + dist.opportunist
            + dist.always_cooperate
            + dist.always_defect
            + dist.random
        )
        assert abs(total - 1.0) < 0.001

    def test_epsilon_prevents_zero_probabilities(self):
        """Test EPSILON smoothing prevents any type from reaching zero."""
        inference = BayesianInference()

        # Give evidence strongly favoring always_cooperate
        for turn in range(1, 20):
            obs = ObservedAction(
                turn=turn,
                opponent_action=ActionType.COOPERATIVE,
                player_previous_action=ActionType.COMPETITIVE,  # Against TFT pattern
                position_difference=-5.0,  # Against opportunist
                was_betrayed_before=True,  # Against grim trigger
            )
            inference.update(obs)

        dist = inference.get_distribution()
        # No probability should be exactly zero due to EPSILON
        assert dist.tit_for_tat > 0
        assert dist.grim_trigger > 0
        assert dist.opportunist > 0
        assert dist.always_defect > 0
        assert dist.random > 0
