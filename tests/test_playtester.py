"""Tests for brinksmanship.testing.playtester module.

Tests cover:
- SimplePlayerState and SimpleGameState dataclasses
- ActionChoice enum
- apply_outcome() function (game mechanics)
- check_crisis_termination() and check_ending() functions
- final_resolution() function
- Built-in strategies (TitForTat, AlwaysDefect, etc.)
- run_game() function
- PlaytestRunner class
- PairingStats and PlaytestResults dataclasses

These tests are self-contained and do not require external dependencies.
"""

import random
from pathlib import Path
import tempfile

import pytest

from brinksmanship.testing.playtester import (
    # Enums
    ActionChoice,
    EndingType,
    # State classes
    SimplePlayerState,
    SimpleGameState,
    # Game mechanics
    apply_outcome,
    check_crisis_termination,
    check_ending,
    final_resolution,
    # Strategies
    tit_for_tat,
    always_defect,
    always_cooperate,
    opportunist,
    nash_equilibrium,
    grim_trigger,
    random_strategy,
    STRATEGIES,
    # Game execution
    run_game,
    GameResult,
    # Statistics
    PairingStats,
    PlaytestResults,
    # Runner
    PlaytestRunner,
)


# =============================================================================
# ActionChoice Enum Tests
# =============================================================================


class TestActionChoice:
    """Tests for ActionChoice enum."""

    def test_cooperate_value(self):
        """Test COOPERATE has correct value."""
        assert ActionChoice.COOPERATE.value == "C"

    def test_defect_value(self):
        """Test DEFECT has correct value."""
        assert ActionChoice.DEFECT.value == "D"

    def test_enum_has_two_members(self):
        """Test ActionChoice has exactly two members."""
        members = list(ActionChoice)
        assert len(members) == 2


# =============================================================================
# SimplePlayerState Tests
# =============================================================================


class TestSimplePlayerState:
    """Tests for SimplePlayerState dataclass."""

    def test_default_values(self):
        """Test default player state values."""
        player = SimplePlayerState()
        assert player.position == 5.0
        assert player.resources == 5.0
        assert player.previous_type is None

    def test_clamp_position_max(self):
        """Test position clamped to max 10."""
        player = SimplePlayerState(position=15.0)
        player.clamp()
        assert player.position == 10.0

    def test_clamp_position_min(self):
        """Test position clamped to min 0."""
        player = SimplePlayerState(position=-5.0)
        player.clamp()
        assert player.position == 0.0

    def test_clamp_resources_max(self):
        """Test resources clamped to max 10."""
        player = SimplePlayerState(resources=15.0)
        player.clamp()
        assert player.resources == 10.0

    def test_clamp_resources_min(self):
        """Test resources clamped to min 0."""
        player = SimplePlayerState(resources=-5.0)
        player.clamp()
        assert player.resources == 0.0


# =============================================================================
# SimpleGameState Tests
# =============================================================================


class TestSimpleGameState:
    """Tests for SimpleGameState dataclass."""

    def test_default_values(self):
        """Test default game state values."""
        state = SimpleGameState()
        assert state.cooperation_score == 5.0
        assert state.stability == 5.0
        assert state.risk_level == 2.0
        assert state.turn == 1
        assert state.max_turns == 14
        assert len(state.history_a) == 0
        assert len(state.history_b) == 0

    def test_player_defaults(self):
        """Test default player states."""
        state = SimpleGameState()
        assert state.player_a.position == 5.0
        assert state.player_b.position == 5.0

    def test_get_act_multiplier_act_i(self):
        """Test Act I multiplier (turns 1-4)."""
        state = SimpleGameState()
        for turn in [1, 2, 3, 4]:
            state.turn = turn
            assert state.get_act_multiplier() == 0.7, f"Failed for turn {turn}"

    def test_get_act_multiplier_act_ii(self):
        """Test Act II multiplier (turns 5-8)."""
        state = SimpleGameState()
        for turn in [5, 6, 7, 8]:
            state.turn = turn
            assert state.get_act_multiplier() == 1.0, f"Failed for turn {turn}"

    def test_get_act_multiplier_act_iii(self):
        """Test Act III multiplier (turns 9+)."""
        state = SimpleGameState()
        for turn in [9, 10, 11, 14]:
            state.turn = turn
            assert state.get_act_multiplier() == 1.3, f"Failed for turn {turn}"

    def test_clamp(self):
        """Test clamp clamps all values."""
        state = SimpleGameState()
        state.cooperation_score = 15.0
        state.stability = -5.0
        state.risk_level = 20.0
        state.clamp()
        assert state.cooperation_score == 10.0
        assert state.stability == 1.0  # Min stability is 1
        assert state.risk_level == 10.0


# =============================================================================
# apply_outcome Tests
# =============================================================================


class TestApplyOutcome:
    """Tests for apply_outcome function."""

    def test_cc_increases_positions(self):
        """Test CC outcome increases both positions."""
        random.seed(42)
        state = SimpleGameState()
        initial_a = state.player_a.position
        initial_b = state.player_b.position
        apply_outcome(state, ActionChoice.COOPERATE, ActionChoice.COOPERATE, add_noise=False)
        # CC: +0.5 * 0.7 (Act I) = +0.35 each
        assert state.player_a.position > initial_a
        assert state.player_b.position > initial_b

    def test_cc_decreases_risk(self):
        """Test CC outcome decreases risk."""
        state = SimpleGameState()
        state.risk_level = 5.0
        apply_outcome(state, ActionChoice.COOPERATE, ActionChoice.COOPERATE, add_noise=False)
        # CC: risk -0.5 * 0.7 = -0.35
        assert state.risk_level < 5.0

    def test_cd_exploits_cooperator(self):
        """Test CD outcome punishes cooperator."""
        state = SimpleGameState()
        initial_a = state.player_a.position
        initial_b = state.player_b.position
        apply_outcome(state, ActionChoice.COOPERATE, ActionChoice.DEFECT, add_noise=False)
        # CD: A loses position, B gains
        assert state.player_a.position < initial_a
        assert state.player_b.position > initial_b

    def test_dc_exploits_cooperator(self):
        """Test DC outcome punishes cooperator."""
        state = SimpleGameState()
        initial_a = state.player_a.position
        initial_b = state.player_b.position
        apply_outcome(state, ActionChoice.DEFECT, ActionChoice.COOPERATE, add_noise=False)
        # DC: A gains position, B loses
        assert state.player_a.position > initial_a
        assert state.player_b.position < initial_b

    def test_dd_hurts_both(self):
        """Test DD outcome hurts both players."""
        state = SimpleGameState()
        initial_pos_a = state.player_a.position
        initial_pos_b = state.player_b.position
        initial_res_a = state.player_a.resources
        initial_res_b = state.player_b.resources
        apply_outcome(state, ActionChoice.DEFECT, ActionChoice.DEFECT, add_noise=False)
        # DD: both lose position and resources
        assert state.player_a.position < initial_pos_a
        assert state.player_b.position < initial_pos_b
        assert state.player_a.resources < initial_res_a
        assert state.player_b.resources < initial_res_b

    def test_dd_increases_risk(self):
        """Test DD outcome increases risk the most."""
        state = SimpleGameState()
        initial_risk = state.risk_level
        apply_outcome(state, ActionChoice.DEFECT, ActionChoice.DEFECT, add_noise=False)
        # DD: risk +1.0 * 0.7 = +0.7
        assert state.risk_level > initial_risk

    def test_updates_previous_types(self):
        """Test that previous action types are updated."""
        state = SimpleGameState()
        assert state.player_a.previous_type is None
        assert state.player_b.previous_type is None
        apply_outcome(state, ActionChoice.COOPERATE, ActionChoice.DEFECT, add_noise=False)
        assert state.player_a.previous_type == ActionChoice.COOPERATE
        assert state.player_b.previous_type == ActionChoice.DEFECT


# =============================================================================
# check_crisis_termination Tests
# =============================================================================


class TestCheckCrisisTermination:
    """Tests for check_crisis_termination function."""

    def test_no_termination_before_turn_10(self):
        """Test crisis never terminates before turn 10."""
        for turn in range(1, 10):
            state = SimpleGameState()
            state.turn = turn
            state.risk_level = 10.0  # Max risk
            assert check_crisis_termination(state) is False

    def test_no_termination_with_low_risk(self):
        """Test crisis never terminates with risk <= 7."""
        state = SimpleGameState()
        state.turn = 12
        for risk in [0, 3, 5, 7]:
            state.risk_level = risk
            assert check_crisis_termination(state) is False

    def test_termination_possible_high_risk_late_game(self):
        """Test crisis can terminate with high risk in late game."""
        random.seed(42)
        state = SimpleGameState()
        state.turn = 12
        state.risk_level = 10.0  # Max risk: P = 0.24
        # Run multiple times to check probability
        terminated_count = sum(
            1 for _ in range(1000)
            if check_crisis_termination(state)
        )
        # Should terminate roughly 24% of the time
        assert 180 < terminated_count < 300


# =============================================================================
# check_ending Tests
# =============================================================================


class TestCheckEnding:
    """Tests for check_ending function."""

    def test_no_ending_normal_state(self):
        """Test no ending in normal game state."""
        state = SimpleGameState()
        assert check_ending(state) is None

    def test_mutual_destruction_at_max_risk(self):
        """Test mutual destruction at risk = 10."""
        state = SimpleGameState()
        state.risk_level = 10.0
        assert check_ending(state) == EndingType.MUTUAL_DESTRUCTION

    def test_position_loss_a(self):
        """Test position loss for player A."""
        state = SimpleGameState()
        state.player_a.position = 0.0
        assert check_ending(state) == EndingType.POSITION_LOSS_A

    def test_position_loss_b(self):
        """Test position loss for player B."""
        state = SimpleGameState()
        state.player_b.position = 0.0
        assert check_ending(state) == EndingType.POSITION_LOSS_B

    def test_resource_loss_a(self):
        """Test resource loss for player A."""
        state = SimpleGameState()
        state.player_a.resources = 0.0
        assert check_ending(state) == EndingType.RESOURCE_LOSS_A

    def test_resource_loss_b(self):
        """Test resource loss for player B."""
        state = SimpleGameState()
        state.player_b.resources = 0.0
        assert check_ending(state) == EndingType.RESOURCE_LOSS_B

    def test_max_turns_ending(self):
        """Test max turns ending."""
        state = SimpleGameState()
        state.max_turns = 14
        state.turn = 15
        assert check_ending(state) == EndingType.MAX_TURNS


# =============================================================================
# final_resolution Tests
# =============================================================================


class TestFinalResolution:
    """Tests for final_resolution function."""

    def test_equal_positions_roughly_equal_vp(self):
        """Test equal positions give roughly equal VP."""
        random.seed(42)
        state = SimpleGameState()
        state.player_a.position = 5.0
        state.player_b.position = 5.0
        vp_a, vp_b = final_resolution(state)
        # Should sum to 100
        assert abs(vp_a + vp_b - 100.0) < 0.01
        # Should be roughly equal on average
        assert 30 < vp_a < 70
        assert 30 < vp_b < 70

    def test_higher_position_higher_expected_vp(self):
        """Test higher position leads to higher expected VP."""
        random.seed(42)
        vp_a_list = []
        for _ in range(100):
            state = SimpleGameState()
            state.player_a.position = 8.0
            state.player_b.position = 2.0
            vp_a, _ = final_resolution(state)
            vp_a_list.append(vp_a)
        # Average should favor player A
        avg_vp_a = sum(vp_a_list) / len(vp_a_list)
        assert avg_vp_a > 60

    def test_vp_sum_to_100(self):
        """Test VP always sums to 100."""
        random.seed(42)
        for _ in range(100):
            state = SimpleGameState()
            state.player_a.position = random.uniform(2, 8)
            state.player_b.position = random.uniform(2, 8)
            vp_a, vp_b = final_resolution(state)
            assert abs(vp_a + vp_b - 100.0) < 0.01


# =============================================================================
# Strategy Tests
# =============================================================================


class TestStrategies:
    """Tests for built-in strategies."""

    def test_tit_for_tat_initial_cooperate(self):
        """Test TitForTat cooperates first."""
        state = SimpleGameState()
        action = tit_for_tat(state, [], [], "A")
        assert action == ActionChoice.COOPERATE

    def test_tit_for_tat_mirrors_defect(self):
        """Test TitForTat mirrors opponent's defection."""
        state = SimpleGameState()
        action = tit_for_tat(state, [ActionChoice.COOPERATE], [ActionChoice.DEFECT], "A")
        assert action == ActionChoice.DEFECT

    def test_tit_for_tat_mirrors_cooperate(self):
        """Test TitForTat mirrors opponent's cooperation."""
        state = SimpleGameState()
        action = tit_for_tat(state, [ActionChoice.COOPERATE], [ActionChoice.COOPERATE], "A")
        assert action == ActionChoice.COOPERATE

    def test_always_defect(self):
        """Test AlwaysDefect always defects."""
        state = SimpleGameState()
        for _ in range(10):
            action = always_defect(state, [], [], "A")
            assert action == ActionChoice.DEFECT

    def test_always_cooperate(self):
        """Test AlwaysCooperate always cooperates."""
        state = SimpleGameState()
        for _ in range(10):
            action = always_cooperate(state, [], [], "A")
            assert action == ActionChoice.COOPERATE

    def test_grim_trigger_initial_cooperate(self):
        """Test GrimTrigger cooperates initially."""
        state = SimpleGameState()
        action = grim_trigger(state, [], [], "A")
        assert action == ActionChoice.COOPERATE

    def test_grim_trigger_defects_after_defection(self):
        """Test GrimTrigger defects forever after opponent defects."""
        state = SimpleGameState()
        opp_history = [ActionChoice.COOPERATE, ActionChoice.DEFECT, ActionChoice.COOPERATE]
        action = grim_trigger(state, [], opp_history, "A")
        assert action == ActionChoice.DEFECT

    def test_opportunist_defects_when_ahead(self):
        """Test Opportunist defects when ahead in position."""
        state = SimpleGameState()
        state.player_a.position = 8.0
        state.player_b.position = 3.0
        state.risk_level = 3.0  # Low risk
        action = opportunist(state, [], [], "A")
        assert action == ActionChoice.DEFECT

    def test_opportunist_cooperates_high_risk(self):
        """Test Opportunist cooperates when risk is high."""
        state = SimpleGameState()
        state.player_a.position = 8.0
        state.player_b.position = 3.0
        state.risk_level = 8.0  # High risk
        action = opportunist(state, [], [], "A")
        assert action == ActionChoice.COOPERATE

    def test_nash_defects_low_risk(self):
        """Test Nash defects when risk is low."""
        state = SimpleGameState()
        state.risk_level = 3.0
        action = nash_equilibrium(state, [], [], "A")
        assert action == ActionChoice.DEFECT

    def test_nash_cooperates_high_risk(self):
        """Test Nash cooperates when risk >= 8."""
        state = SimpleGameState()
        state.risk_level = 8.0
        action = nash_equilibrium(state, [], [], "A")
        assert action == ActionChoice.COOPERATE

    def test_random_produces_both_choices(self):
        """Test Random strategy produces both choices."""
        random.seed(42)
        state = SimpleGameState()
        choices = [random_strategy(state, [], [], "A") for _ in range(100)]
        assert ActionChoice.COOPERATE in choices
        assert ActionChoice.DEFECT in choices

    def test_strategies_registry(self):
        """Test all strategies are registered."""
        assert "TitForTat" in STRATEGIES
        assert "AlwaysDefect" in STRATEGIES
        assert "AlwaysCooperate" in STRATEGIES
        assert "Opportunist" in STRATEGIES
        assert "Nash" in STRATEGIES
        assert "GrimTrigger" in STRATEGIES
        assert "Random" in STRATEGIES
        assert len(STRATEGIES) == 7


# =============================================================================
# run_game Tests
# =============================================================================


class TestRunGame:
    """Tests for run_game function."""

    def test_run_game_completes(self):
        """Test run_game completes without error."""
        random.seed(42)
        result = run_game(always_cooperate, always_cooperate, seed=42)
        assert isinstance(result, GameResult)
        assert result.turns_played > 0

    def test_run_game_result_structure(self):
        """Test GameResult has all expected fields."""
        random.seed(42)
        result = run_game(always_cooperate, always_defect, seed=42)
        assert hasattr(result, "winner")
        assert hasattr(result, "ending_type")
        assert hasattr(result, "turns_played")
        assert hasattr(result, "final_pos_a")
        assert hasattr(result, "final_pos_b")
        assert hasattr(result, "vp_a")
        assert hasattr(result, "vp_b")
        assert hasattr(result, "history_a")
        assert hasattr(result, "history_b")

    def test_run_game_history_matches_turns(self):
        """Test history length matches turns played."""
        random.seed(42)
        result = run_game(tit_for_tat, always_defect, max_turns=10, seed=42)
        # History should have entries for each turn up to ending
        assert len(result.history_a) <= result.turns_played + 1
        assert len(result.history_b) <= result.turns_played + 1

    def test_run_game_winner_valid(self):
        """Test winner is one of expected values."""
        random.seed(42)
        result = run_game(always_cooperate, always_defect, seed=42)
        assert result.winner in ["A", "B", "tie", "mutual_destruction"]

    def test_run_game_vp_sum(self):
        """Test VP sums to 100 for normal endings."""
        random.seed(42)
        result = run_game(always_cooperate, always_cooperate, seed=42)
        if result.winner != "mutual_destruction":
            assert abs(result.vp_a + result.vp_b - 100.0) < 0.1

    def test_run_game_seed_reproducibility(self):
        """Test same seed produces same result."""
        result1 = run_game(tit_for_tat, always_defect, seed=12345)
        result2 = run_game(tit_for_tat, always_defect, seed=12345)
        assert result1.winner == result2.winner
        assert result1.turns_played == result2.turns_played
        assert result1.history_a == result2.history_a

    def test_run_game_to_dict(self):
        """Test GameResult.to_dict() works."""
        random.seed(42)
        result = run_game(always_cooperate, always_defect, seed=42)
        result_dict = result.to_dict()
        assert "winner" in result_dict
        assert "ending_type" in result_dict
        assert "vp_a" in result_dict


# =============================================================================
# PairingStats Tests
# =============================================================================


class TestPairingStats:
    """Tests for PairingStats dataclass."""

    def test_default_values(self):
        """Test default PairingStats values."""
        stats = PairingStats()
        assert stats.total_games == 0
        assert stats.wins_a == 0
        assert stats.wins_b == 0
        assert stats.ties == 0

    def test_add_result_increments_counts(self):
        """Test add_result increments appropriate counters."""
        stats = PairingStats()
        result = GameResult(
            winner="A",
            ending_type=EndingType.MAX_TURNS,
            turns_played=12,
            final_pos_a=6.0,
            final_pos_b=4.0,
            final_res_a=5.0,
            final_res_b=5.0,
            final_risk=5.0,
            final_cooperation=5.0,
            final_stability=5.0,
            vp_a=60.0,
            vp_b=40.0,
            history_a=["C", "C"],
            history_b=["D", "D"],
        )
        stats.add_result(result)
        assert stats.total_games == 1
        assert stats.wins_a == 1
        assert stats.wins_b == 0
        assert stats.max_turns_endings == 1

    def test_win_rate_calculation(self):
        """Test win rate properties."""
        stats = PairingStats()
        stats.wins_a = 60
        stats.wins_b = 30
        stats.ties = 10
        stats.total_games = 100
        assert stats.win_rate_a == 0.60
        assert stats.win_rate_b == 0.30
        assert stats.tie_rate == 0.10

    def test_avg_game_length(self):
        """Test average game length calculation."""
        stats = PairingStats()
        stats.total_games = 10
        stats.total_turns = 120
        assert stats.avg_game_length == 12.0

    def test_to_dict(self):
        """Test to_dict serialization."""
        stats = PairingStats()
        stats.total_games = 100
        stats.wins_a = 50
        data = stats.to_dict()
        assert "total_games" in data
        assert "win_rate_a" in data
        assert data["total_games"] == 100


# =============================================================================
# PlaytestResults Tests
# =============================================================================


class TestPlaytestResults:
    """Tests for PlaytestResults dataclass."""

    def test_default_values(self):
        """Test default PlaytestResults values."""
        results = PlaytestResults()
        assert len(results.pairings) == 0
        assert len(results.aggregate) == 0

    def test_compute_aggregate(self):
        """Test compute_aggregate calculates stats."""
        results = PlaytestResults()
        stats = PairingStats()
        stats.total_games = 100
        stats.total_turns = 1200
        stats.vp_a_list = [50.0] * 100
        stats.vp_b_list = [50.0] * 100
        results.pairings["TitForTat:Nash"] = stats
        results.compute_aggregate()
        assert "total_games" in results.aggregate
        assert results.aggregate["total_games"] == 100

    def test_to_json(self):
        """Test to_json serialization."""
        results = PlaytestResults()
        results.timestamp = "2024-01-01T00:00:00"
        json_str = results.to_json()
        assert "timestamp" in json_str
        assert "pairings" in json_str


# =============================================================================
# PlaytestRunner Tests
# =============================================================================


class TestPlaytestRunner:
    """Tests for PlaytestRunner class."""

    def test_list_strategies(self):
        """Test list_strategies returns all built-in strategies."""
        runner = PlaytestRunner()
        strategies = runner.list_strategies()
        assert "TitForTat" in strategies
        assert "AlwaysDefect" in strategies
        assert len(strategies) == 7

    def test_get_strategy(self):
        """Test get_strategy returns correct strategy."""
        runner = PlaytestRunner()
        strat = runner.get_strategy("TitForTat")
        assert strat == tit_for_tat

    def test_get_strategy_unknown_raises(self):
        """Test get_strategy raises for unknown strategy."""
        runner = PlaytestRunner()
        with pytest.raises(ValueError):
            runner.get_strategy("UnknownStrategy")

    def test_register_strategy(self):
        """Test registering custom strategy."""
        runner = PlaytestRunner()

        def custom_strat(state, my_hist, opp_hist, player):
            return ActionChoice.COOPERATE

        runner.register_strategy("Custom", custom_strat)
        assert "Custom" in runner.list_strategies()
        assert runner.get_strategy("Custom") == custom_strat

    def test_run_pairing(self):
        """Test run_pairing runs games and returns stats."""
        runner = PlaytestRunner()
        stats = runner.run_pairing("TitForTat", "AlwaysDefect", num_games=10, seed=42)
        assert isinstance(stats, PairingStats)
        assert stats.total_games == 10

    def test_run_pairing_with_function(self):
        """Test run_pairing accepts strategy functions."""
        runner = PlaytestRunner()
        stats = runner.run_pairing(always_cooperate, always_defect, num_games=5, seed=42)
        assert stats.total_games == 5

    def test_run_playtest(self):
        """Test run_playtest runs multiple pairings."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = PlaytestRunner()
            pairings = [("TitForTat", "AlwaysDefect"), ("AlwaysCooperate", "Nash")]
            results = runner.run_playtest(
                pairings,
                games_per_pairing=5,
                output_dir=tmpdir,
                max_workers=1,
                seed=42,
            )
            assert isinstance(results, PlaytestResults)
            assert len(results.pairings) == 2
            assert "TitForTat:AlwaysDefect" in results.pairings
            # Check output file was created
            assert Path(tmpdir, "playtest_results.json").exists()

    def test_run_all_pairings(self):
        """Test run_all_pairings generates all unique pairings."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = PlaytestRunner()
            results = runner.run_all_pairings(
                strategies=["TitForTat", "AlwaysDefect", "AlwaysCooperate"],
                games_per_pairing=3,
                output_dir=tmpdir,
                max_workers=1,
                seed=42,
            )
            # 3 strategies: (A,A), (A,B), (A,C), (B,B), (B,C), (C,C) = 6 pairings
            assert len(results.pairings) == 6


# =============================================================================
# Integration Tests
# =============================================================================


class TestIntegration:
    """Integration tests for the playtesting framework."""

    def test_full_playtest_cycle(self):
        """Test complete playtest cycle from runner to analysis."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = PlaytestRunner()

            # Run a small playtest
            results = runner.run_playtest(
                [("TitForTat", "AlwaysDefect")],
                games_per_pairing=20,
                output_dir=tmpdir,
                max_workers=1,
                seed=42,
            )

            # Verify results
            assert results.aggregate["total_games"] == 20
            stats = results.pairings["TitForTat:AlwaysDefect"]

            # AlwaysDefect should typically beat TitForTat in early game
            # but the variance makes this probabilistic
            assert stats.total_games == 20
            assert stats.avg_game_length > 0

    def test_deterministic_with_seed(self):
        """Test playtests are deterministic with same seed."""
        with tempfile.TemporaryDirectory() as tmpdir1, tempfile.TemporaryDirectory() as tmpdir2:
            runner = PlaytestRunner()

            results1 = runner.run_playtest(
                [("TitForTat", "Nash")],
                games_per_pairing=10,
                output_dir=tmpdir1,
                max_workers=1,
                seed=12345,
            )

            results2 = runner.run_playtest(
                [("TitForTat", "Nash")],
                games_per_pairing=10,
                output_dir=tmpdir2,
                max_workers=1,
                seed=12345,
            )

            stats1 = results1.pairings["TitForTat:Nash"]
            stats2 = results2.pairings["TitForTat:Nash"]

            assert stats1.wins_a == stats2.wins_a
            assert stats1.wins_b == stats2.wins_b
            assert stats1.total_turns == stats2.total_turns
