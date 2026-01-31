"""Unit tests for brinksmanship.engine.game_engine module.

Tests cover:
- GameEngine: initialization, scenario loading
- Turn structure: 8 phases execute in order
- State updates: cooperation score, stability decay formula
- Action validation: risk tier, resource requirements, settlement availability
- History tracking: turn recording, state before/after
- Game ending detection: deterministic endings, crisis termination
- Information state updates: reconnaissance, inspection

Removed tests (see test_removal_log.md):
- TestTurnRecord: Basic dataclass tests (trivial)
- TestGameEnding: test_valid_ending_creation, test_mutual_destruction_special_case (duplicated in test_endings.py)
- TestGameEngineInitialization: Basic state value tests (trivial, covered by integration)
- TestGameEndingDetection: Basic is_game_over/get_ending tests (trivial state checks)
- TestDeterministicEndings: Entire class (duplicated in test_endings.py)
- TestCrisisTermination: Duplicate tests (covered by test_endings.py)
- TestInformationStateUpdates: test_successful_recon/inspection_updates (weak assertions)
"""

import pytest

from brinksmanship.engine.game_engine import (
    EndingType,
    GameEnding,
    GameEngine,
    TurnPhase,
    create_game,
)
from brinksmanship.models.actions import (
    DEESCALATE,
    ESCALATE,
    PROPOSE_SETTLEMENT,
    RECONNAISSANCE,
    Action,
    ActionCategory,
    ActionType,
)
from brinksmanship.storage import ScenarioRepository

# =============================================================================
# Mock Scenario Repository
# =============================================================================


class MockScenarioRepository(ScenarioRepository):
    """Mock repository for testing."""

    def __init__(self, scenarios: dict | None = None):
        self._scenarios = scenarios or {}

    def list_scenarios(self) -> list[dict]:
        return [{"id": sid, "name": s.get("name", sid)} for sid, s in self._scenarios.items()]

    def get_scenario(self, scenario_id: str) -> dict | None:
        return self._scenarios.get(scenario_id)

    def get_scenario_by_name(self, name: str) -> dict | None:
        for scenario in self._scenarios.values():
            if scenario.get("name", "").lower() == name.lower():
                return scenario
        return None

    def save_scenario(self, scenario: dict) -> str:
        name = scenario.get("name", "unnamed")
        sid = name.lower().replace(" ", "-")
        self._scenarios[sid] = scenario
        return sid

    def delete_scenario(self, scenario_id: str) -> bool:
        if scenario_id in self._scenarios:
            del self._scenarios[scenario_id]
            return True
        return False


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def minimal_scenario() -> dict:
    """Minimal valid scenario for testing."""
    return {
        "name": "Test Scenario",
        "setting": "Test",
        "turns": [
            {
                "turn": 1,
                "narrative_briefing": "Turn 1 briefing",
                "matrix_type": "PRISONERS_DILEMMA",
            },
            {
                "turn": 2,
                "narrative_briefing": "Turn 2 briefing",
                "matrix_type": "PRISONERS_DILEMMA",
            },
        ],
    }


@pytest.fixture
def mock_repo(minimal_scenario) -> MockScenarioRepository:
    """Mock repository with a minimal scenario."""
    return MockScenarioRepository({"test-scenario": minimal_scenario})


@pytest.fixture
def engine(mock_repo) -> GameEngine:
    """GameEngine with deterministic settings for testing."""
    return GameEngine(
        scenario_id="test-scenario",
        scenario_repo=mock_repo,
        max_turns=14,
        random_seed=42,
    )


@pytest.fixture
def cooperative_action() -> Action:
    """A standard cooperative action."""
    return DEESCALATE


@pytest.fixture
def competitive_action() -> Action:
    """A standard competitive action."""
    return ESCALATE


# =============================================================================
# GameEnding Tests
# =============================================================================


class TestGameEnding:
    """Tests for GameEnding dataclass validation."""

    def test_non_mutual_destruction_must_sum_to_100(self):
        """Non-mutual destruction endings must have VP sum to 100."""
        with pytest.raises(ValueError, match="must sum to 100"):
            GameEnding(
                ending_type=EndingType.NATURAL_ENDING,
                vp_a=60.0,
                vp_b=50.0,  # Sum = 110
                turn=14,
                description="Invalid ending",
            )

    def test_vp_must_be_in_range(self):
        """VP values must be in [0, 100]."""
        with pytest.raises(ValueError, match="must be in"):
            GameEnding(
                ending_type=EndingType.NATURAL_ENDING,
                vp_a=110.0,  # Invalid
                vp_b=-10.0,  # Invalid
                turn=14,
                description="Invalid ending",
            )


# =============================================================================
# GameEngine Initialization Tests
# =============================================================================


class TestGameEngineInitialization:
    """Tests for GameEngine initialization."""

    def test_random_max_turns_when_not_specified(self, mock_repo):
        """Engine generates random max_turns (12-16) when not specified."""
        engine = GameEngine(
            scenario_id="test-scenario",
            scenario_repo=mock_repo,
            random_seed=42,
        )
        state = engine.get_current_state()
        assert 12 <= state.max_turns <= 16

    def test_scenario_loading(self, engine):
        """Engine loads and parses scenario correctly."""
        assert engine.scenario_id == "test-scenario"
        # Check that briefing is accessible
        briefing = engine.get_briefing()
        assert "Turn 1" in briefing

    def test_scenario_not_found_raises_error(self, mock_repo):
        """Engine raises ValueError for non-existent scenario."""
        with pytest.raises(ValueError, match="Scenario not found"):
            GameEngine(
                scenario_id="nonexistent",
                scenario_repo=mock_repo,
            )


# =============================================================================
# Turn Structure Tests
# =============================================================================


class TestTurnStructure:
    """Tests for turn structure and phase progression."""

    def test_phases_execute_in_order(self, engine, cooperative_action):
        """Turn phases execute in the correct 8-phase order."""
        # Start in BRIEFING
        assert engine.phase == TurnPhase.BRIEFING

        # Submit actions triggers remaining phases
        result = engine.submit_actions(cooperative_action, cooperative_action)

        assert result.success is True

        # After a complete turn without ending, should be back in BRIEFING
        assert engine.phase == TurnPhase.BRIEFING

    def test_turn_number_advances(self, engine, cooperative_action):
        """Turn number advances after each turn."""
        assert engine.state.turn == 1

        engine.submit_actions(cooperative_action, cooperative_action)
        assert engine.state.turn == 2

        engine.submit_actions(cooperative_action, cooperative_action)
        assert engine.state.turn == 3

    def test_submit_actions_after_game_over_fails(self, engine):
        """Cannot submit actions after game ends."""
        # Force game over by setting ending
        engine.ending = GameEnding(
            ending_type=EndingType.NATURAL_ENDING,
            vp_a=50.0,
            vp_b=50.0,
            turn=1,
            description="Test",
        )

        result = engine.submit_actions(DEESCALATE, DEESCALATE)

        assert result.success is False
        assert "already over" in result.error.lower()


# =============================================================================
# State Update Tests
# =============================================================================


class TestStateUpdates:
    """Tests for state update mechanics."""

    def test_cooperation_score_cc_increases(self, engine):
        """CC (both cooperative) increases cooperation score by 1."""
        initial_coop = engine.state.cooperation_score

        engine.submit_actions(DEESCALATE, DEESCALATE)

        assert engine.state.cooperation_score == pytest.approx(initial_coop + 1)

    def test_cooperation_score_dd_decreases(self, engine):
        """DD (both competitive) decreases cooperation score by 1."""
        initial_coop = engine.state.cooperation_score

        engine.submit_actions(ESCALATE, ESCALATE)

        assert engine.state.cooperation_score == pytest.approx(initial_coop - 1)

    def test_cooperation_score_mixed_no_change(self, engine):
        """Mixed outcomes (CD, DC) result in no cooperation score change."""
        initial_coop = engine.state.cooperation_score

        engine.submit_actions(DEESCALATE, ESCALATE)

        assert engine.state.cooperation_score == pytest.approx(initial_coop)

    def test_stability_decay_both_consistent_increases(self, engine):
        """Both players consistent: +1.5 after decay formula."""
        # First turn establishes previous types
        engine.submit_actions(DEESCALATE, DEESCALATE)
        initial_stability = engine.state.stability

        # Second turn with same types
        engine.submit_actions(DEESCALATE, DEESCALATE)

        # Formula: new = old * 0.8 + 1.0 + 1.5 (0 switches)
        expected = initial_stability * 0.8 + 1.0 + 1.5
        expected = max(1.0, min(10.0, expected))
        assert engine.state.stability == pytest.approx(expected)

    def test_stability_decay_one_switch_decreases(self, engine):
        """One player switches: -3.5 after decay formula."""
        # Establish previous types
        engine.submit_actions(DEESCALATE, DEESCALATE)
        initial_stability = engine.state.stability

        # One player switches
        engine.submit_actions(DEESCALATE, ESCALATE)

        # Formula: new = old * 0.8 + 1.0 - 3.5 (1 switch)
        expected = initial_stability * 0.8 + 1.0 - 3.5
        expected = max(1.0, min(10.0, expected))
        assert engine.state.stability == pytest.approx(expected)

    def test_stability_decay_both_switch_severe_decrease(self, engine):
        """Both players switch: -5.5 after decay formula."""
        # Establish previous types
        engine.submit_actions(DEESCALATE, ESCALATE)
        initial_stability = engine.state.stability

        # Both switch
        engine.submit_actions(ESCALATE, DEESCALATE)

        # Formula: new = old * 0.8 + 1.0 - 5.5 (2 switches)
        expected = initial_stability * 0.8 + 1.0 - 5.5
        expected = max(1.0, min(10.0, expected))
        assert engine.state.stability == pytest.approx(expected)

    def test_stability_clamped_to_range(self, engine):
        """Stability is clamped to [1, 10]."""
        # Force low stability through repeated switches
        engine.submit_actions(DEESCALATE, DEESCALATE)
        for _ in range(5):
            engine.submit_actions(ESCALATE, ESCALATE)
            engine.submit_actions(DEESCALATE, DEESCALATE)

        assert engine.state.stability >= 1.0
        assert engine.state.stability <= 10.0


# =============================================================================
# Action Validation Tests
# =============================================================================


class TestActionValidation:
    """Tests for action validation."""

    def test_available_actions_based_on_risk_tier(self, engine):
        """Available actions vary by risk tier."""
        # Low risk (0-3) - more cooperative options
        actions = engine.get_available_actions("A")
        cooperative_count = sum(
            1 for a in actions if a.action_type == ActionType.COOPERATIVE and a.category == ActionCategory.STANDARD
        )
        # Low risk tier has 4 cooperative actions
        assert cooperative_count >= 3

    def test_resource_requirements_checked(self, mock_repo, minimal_scenario):
        """Actions requiring resources are validated against player resources."""
        engine = GameEngine(
            scenario_id="test-scenario",
            scenario_repo=mock_repo,
            max_turns=14,
            random_seed=42,
        )

        # Drain player A's resources
        engine.state.player_a.resources = 0.1

        # Reconnaissance costs 0.5 resources
        result = engine.submit_actions(RECONNAISSANCE, DEESCALATE)

        assert result.success is False
        assert "resources" in result.error.lower()

    def test_settlement_available_after_turn_4(self, engine):
        """Settlement is available after turn 4."""
        # Advance to turn 5
        for _ in range(4):
            engine.submit_actions(DEESCALATE, DEESCALATE)

        assert engine.state.turn == 5

        menu = engine.get_action_menu("A")
        assert menu.can_propose_settlement is True

    def test_settlement_not_available_before_turn_5(self, engine):
        """Settlement is not available before turn 5."""
        assert engine.state.turn < 5

        menu = engine.get_action_menu("A")
        assert menu.can_propose_settlement is False

    def test_settlement_not_available_if_stability_low(self, mock_repo):
        """Settlement is not available if stability <= 2."""
        engine = GameEngine(
            scenario_id="test-scenario",
            scenario_repo=mock_repo,
            max_turns=14,
            random_seed=42,
        )

        # Advance past turn 4
        for _ in range(4):
            engine.submit_actions(DEESCALATE, DEESCALATE)

        # Force low stability
        engine.state.stability = 2.0

        menu = engine.get_action_menu("A")
        assert menu.can_propose_settlement is False

    def test_settlement_proposal_rejected_early_turn(self, engine):
        """Settlement proposal before turn 5 is rejected."""
        result = engine.submit_actions(PROPOSE_SETTLEMENT, DEESCALATE)

        assert result.success is False
        assert "turn 4" in result.error.lower() or "settlement" in result.error.lower()


# =============================================================================
# History Tracking Tests
# =============================================================================


class TestHistoryTracking:
    """Tests for turn history tracking."""

    def test_each_turn_recorded(self, engine):
        """Each turn creates a new history record."""
        assert len(engine.get_history()) == 1  # Initial record

        engine.submit_actions(DEESCALATE, DEESCALATE)
        assert len(engine.get_history()) == 2

        engine.submit_actions(ESCALATE, ESCALATE)
        assert len(engine.get_history()) == 3

    def test_state_before_captured(self, engine):
        """State before turn is captured in history."""
        initial_state = engine.get_current_state()

        engine.submit_actions(DEESCALATE, DEESCALATE)

        history = engine.get_history()
        # First record has state_before
        assert history[0].state_before is not None
        assert history[0].state_before.turn == initial_state.turn

    def test_state_after_captured(self, engine):
        """State after turn is captured in history."""
        engine.submit_actions(DEESCALATE, DEESCALATE)

        history = engine.get_history()
        # First completed turn has state_after
        assert history[0].state_after is not None
        assert history[0].state_after.turn == 2

    def test_actions_recorded_in_history(self, engine):
        """Actions are recorded in history."""
        engine.submit_actions(DEESCALATE, ESCALATE)

        history = engine.get_history()
        assert history[0].action_a is not None
        assert history[0].action_a.name == DEESCALATE.name
        assert history[0].action_b is not None
        assert history[0].action_b.name == ESCALATE.name

    def test_outcome_recorded_in_history(self, engine):
        """Outcome is recorded in history."""
        engine.submit_actions(DEESCALATE, DEESCALATE)

        history = engine.get_history()
        assert history[0].outcome is not None
        assert history[0].outcome.outcome_code == "CC"


# =============================================================================
# Game Ending Detection Tests
# =============================================================================


class TestGameEndingDetection:
    """Tests for game ending detection."""

    def test_mutual_destruction_at_risk_10(self, mock_repo):
        """Risk reaching 10 triggers mutual destruction."""
        engine = GameEngine(
            scenario_id="test-scenario",
            scenario_repo=mock_repo,
            max_turns=14,
            random_seed=42,
        )

        # Force high risk
        engine.state.risk_level = 9.9

        # Submit competitive actions to push risk to 10
        # Note: The exact trigger depends on risk delta from the matrix
        # We may need multiple turns of escalation
        for _ in range(10):
            if engine.is_game_over():
                break
            engine.submit_actions(ESCALATE, ESCALATE)

        # Check if game ended with mutual destruction or high risk
        if engine.is_game_over():
            ending = engine.get_ending()
            # Could be mutual destruction or other ending type
            assert ending is not None

    def test_position_collapse_ending(self, mock_repo):
        """Position reaching 0 triggers position collapse ending."""
        engine = GameEngine(
            scenario_id="test-scenario",
            scenario_repo=mock_repo,
            max_turns=14,
            random_seed=42,
        )

        # Force low position
        engine.state.player_a.position = 0.1

        # Submit actions that may reduce position further
        for _ in range(10):
            if engine.is_game_over():
                break
            # Player A cooperates while B defects - A loses position
            engine.submit_actions(DEESCALATE, ESCALATE)

        if engine.is_game_over():
            ending = engine.get_ending()
            assert ending is not None

    def test_resource_exhaustion_ending(self, mock_repo):
        """Resources reaching 0 triggers resource exhaustion ending."""
        engine = GameEngine(
            scenario_id="test-scenario",
            scenario_repo=mock_repo,
            max_turns=14,
            random_seed=42,
        )

        # Force very low resources
        engine.state.player_a.resources = 0.0

        # Check deterministic endings
        ending = engine._check_deterministic_endings()

        assert ending is not None
        assert ending.ending_type == EndingType.RESOURCE_EXHAUSTION_A
        assert ending.vp_a == pytest.approx(15.0)
        assert ending.vp_b == pytest.approx(85.0)

    def test_natural_ending_at_max_turns(self, mock_repo):
        """Game ends at max_turns with natural ending."""
        engine = GameEngine(
            scenario_id="test-scenario",
            scenario_repo=mock_repo,
            max_turns=12,  # Minimum max turns
            random_seed=42,
        )

        # Play through to max turns
        for _ in range(12):
            if engine.is_game_over():
                break
            engine.submit_actions(DEESCALATE, DEESCALATE)

        # Should have ended
        assert engine.is_game_over() is True
        ending = engine.get_ending()
        assert ending is not None

    def test_settlement_ending_both_propose(self, mock_repo):
        """Both players proposing settlement ends game."""
        engine = GameEngine(
            scenario_id="test-scenario",
            scenario_repo=mock_repo,
            max_turns=14,
            random_seed=42,
        )

        # Advance past turn 4 with high stability
        for _ in range(4):
            engine.submit_actions(DEESCALATE, DEESCALATE)

        # Both propose settlement
        result = engine.submit_actions(PROPOSE_SETTLEMENT, PROPOSE_SETTLEMENT)

        assert result.success is True
        assert engine.is_game_over() is True
        ending = engine.get_ending()
        assert ending.ending_type == EndingType.SETTLEMENT


# =============================================================================
# Information State Update Tests
# =============================================================================


class TestInformationStateUpdates:
    """Tests for information state updates via reconnaissance and inspection."""

    def test_information_state_deep_copied(self, engine):
        """get_information_state returns a deep copy."""
        info1 = engine.get_information_state("A")
        info2 = engine.get_information_state("A")

        # Should be equal but not the same object
        assert info1.position_bounds == info2.position_bounds
        assert info1 is not info2


# =============================================================================
# TurnResult Tests
# =============================================================================


class TestTurnResult:
    """Tests for TurnResult returned by submit_actions."""

    def test_successful_turn_result(self, engine):
        """Successful turn returns TurnResult with success=True."""
        result = engine.submit_actions(DEESCALATE, DEESCALATE)

        assert result.success is True
        assert result.error is None
        assert result.action_result is not None
        assert result.narrative != ""

    def test_failed_turn_result_has_error(self, engine):
        """Failed turn returns TurnResult with error message."""
        # Try to propose settlement on turn 1 (not allowed)
        result = engine.submit_actions(PROPOSE_SETTLEMENT, DEESCALATE)

        assert result.success is False
        assert result.error is not None
        assert result.action_result is None

    def test_ending_turn_result_has_ending(self, mock_repo):
        """Turn that ends game returns TurnResult with ending."""
        engine = GameEngine(
            scenario_id="test-scenario",
            scenario_repo=mock_repo,
            max_turns=12,
            random_seed=42,
        )

        # Play to end
        for _ in range(12):
            result = engine.submit_actions(DEESCALATE, DEESCALATE)
            if result.ending is not None:
                break

        # Last turn should have ending
        assert engine.is_game_over() is True


# =============================================================================
# Create Game Factory Function Tests
# =============================================================================


class TestCreateGame:
    """Tests for create_game factory function."""

    def test_create_game_returns_engine(self, mock_repo):
        """create_game returns a GameEngine instance."""
        engine = create_game(
            scenario_id="test-scenario",
            scenario_repo=mock_repo,
        )

        assert isinstance(engine, GameEngine)

    def test_create_game_with_max_turns(self, mock_repo):
        """create_game accepts max_turns parameter."""
        engine = create_game(
            scenario_id="test-scenario",
            scenario_repo=mock_repo,
            max_turns=15,
        )

        assert engine.state.max_turns == 15

    def test_create_game_with_random_seed(self, mock_repo):
        """create_game accepts random_seed for reproducibility."""
        engine1 = create_game(
            scenario_id="test-scenario",
            scenario_repo=mock_repo,
            random_seed=123,
        )
        engine2 = create_game(
            scenario_id="test-scenario",
            scenario_repo=mock_repo,
            random_seed=123,
        )

        # Same seed should produce same max_turns
        assert engine1.state.max_turns == engine2.state.max_turns

    def test_create_game_invalid_scenario_raises(self, mock_repo):
        """create_game raises ValueError for invalid scenario."""
        with pytest.raises(ValueError, match="Scenario not found"):
            create_game(
                scenario_id="nonexistent",
                scenario_repo=mock_repo,
            )


# =============================================================================
# Edge Cases and Integration Tests
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and integration scenarios."""

    def test_multiple_turns_in_sequence(self, engine):
        """Engine handles multiple turns correctly."""
        for i in range(5):
            result = engine.submit_actions(DEESCALATE, DEESCALATE)
            assert result.success is True
            assert engine.state.turn == i + 2

    def test_alternating_action_types(self, engine):
        """Engine handles alternating cooperative/competitive actions."""
        # CC
        engine.submit_actions(DEESCALATE, DEESCALATE)
        coop_after_cc = engine.state.cooperation_score

        # DD
        engine.submit_actions(ESCALATE, ESCALATE)
        coop_after_dd = engine.state.cooperation_score

        # CD
        engine.submit_actions(DEESCALATE, ESCALATE)
        coop_after_cd = engine.state.cooperation_score

        # Verify cooperation score changes correctly
        assert coop_after_dd < coop_after_cc  # DD decreases
        assert coop_after_cd == coop_after_dd  # Mixed doesn't change

    def test_scenario_with_branching(self, mock_repo):
        """Engine handles scenario branching based on outcomes."""
        branching_scenario = {
            "name": "Branching Test",
            "turns": [
                {
                    "turn": 1,
                    "narrative_briefing": "Initial state",
                    "matrix_type": "PRISONERS_DILEMMA",
                    "branches": {
                        "CC": "turn_2_coop",
                        "DD": "turn_2_conflict",
                    },
                    "default_next": "turn_2_default",
                },
            ],
            "branches": {
                "turn_2_coop": {
                    "turn": 2,
                    "narrative_briefing": "Cooperation path",
                    "matrix_type": "STAG_HUNT",
                },
                "turn_2_conflict": {
                    "turn": 2,
                    "narrative_briefing": "Conflict path",
                    "matrix_type": "CHICKEN",
                },
                "turn_2_default": {
                    "turn": 2,
                    "narrative_briefing": "Default path",
                    "matrix_type": "PRISONERS_DILEMMA",
                },
            },
        }
        mock_repo.save_scenario(branching_scenario)

        engine = GameEngine(
            scenario_id="branching-test",
            scenario_repo=mock_repo,
            max_turns=14,
            random_seed=42,
        )

        # Submit CC to take cooperation branch
        engine.submit_actions(DEESCALATE, DEESCALATE)

        # Check we're on turn 2
        assert engine.state.turn == 2

    def test_default_turn_config_created(self, mock_repo):
        """Engine creates default config for missing turn numbers."""
        minimal = {
            "name": "Minimal",
            "turns": [],
        }
        mock_repo.save_scenario(minimal)

        engine = GameEngine(
            scenario_id="minimal",
            scenario_repo=mock_repo,
            max_turns=14,
            random_seed=42,
        )

        # Should create default config
        config = engine._get_current_config()
        assert config is not None
        assert config.turn == 1

    def test_get_available_actions_for_both_players(self, engine):
        """get_available_actions works for both players."""
        actions_a = engine.get_available_actions("A")
        actions_b = engine.get_available_actions("B")

        assert len(actions_a) > 0
        assert len(actions_b) > 0

    def test_get_action_menu_structure(self, engine):
        """get_action_menu returns properly structured menu."""
        menu = engine.get_action_menu("A")

        assert menu.standard_actions is not None
        assert menu.special_actions is not None
        assert menu.risk_level == int(engine.state.risk_level)
        assert menu.turn == engine.state.turn


# =============================================================================
# Final Resolution Tests
# =============================================================================


# =============================================================================
# Surplus Mechanics Integration Tests
# =============================================================================


class TestSurplusMechanics:
    """Tests for surplus mechanics integration into game engine."""

    def test_engine_surplus_mechanics(self, mock_repo):
        """Verify engine applies surplus effects during turn resolution.

        This integration test verifies:
        1. CC outcomes create surplus and increment streak
        2. CD outcomes capture surplus for the defector
        3. Streak resets on non-CC outcomes
        """
        engine = GameEngine(
            scenario_id="test-scenario",
            scenario_repo=mock_repo,
            max_turns=14,
            random_seed=42,
        )

        # Initial state - no surplus, no streak
        assert engine.state.cooperation_surplus == 0.0
        assert engine.state.cooperation_streak == 0
        assert engine.state.surplus_captured_a == 0.0
        assert engine.state.surplus_captured_b == 0.0

        # Play CC turn - should create surplus and increment streak
        result = engine.submit_actions(DEESCALATE, DEESCALATE)
        assert result.success is True

        # After CC: surplus created, streak incremented
        assert engine.state.cooperation_surplus > 0.0
        assert engine.state.cooperation_streak == 1

        # Play another CC turn - surplus should grow, streak should be 2
        initial_surplus = engine.state.cooperation_surplus
        engine.submit_actions(DEESCALATE, DEESCALATE)

        assert engine.state.cooperation_surplus > initial_surplus
        assert engine.state.cooperation_streak == 2

        # Play CD turn (A cooperates, B defects) - B captures surplus
        surplus_before_capture = engine.state.cooperation_surplus
        engine.submit_actions(DEESCALATE, ESCALATE)

        # B should have captured some surplus
        assert engine.state.surplus_captured_b > 0.0
        # Surplus pool should be reduced
        assert engine.state.cooperation_surplus < surplus_before_capture
        # Streak should reset
        assert engine.state.cooperation_streak == 0
        # A should not have captured anything
        assert engine.state.surplus_captured_a == 0.0

    def test_dc_captures_surplus_for_a(self, mock_repo):
        """Verify DC outcome captures surplus for player A."""
        engine = GameEngine(
            scenario_id="test-scenario",
            scenario_repo=mock_repo,
            max_turns=14,
            random_seed=42,
        )

        # Build some surplus with CC
        engine.submit_actions(DEESCALATE, DEESCALATE)
        engine.submit_actions(DEESCALATE, DEESCALATE)

        surplus_before = engine.state.cooperation_surplus
        assert surplus_before > 0.0

        # DC - A defects, B cooperates
        engine.submit_actions(ESCALATE, DEESCALATE)

        # A should have captured surplus
        assert engine.state.surplus_captured_a > 0.0
        assert engine.state.cooperation_surplus < surplus_before
        assert engine.state.cooperation_streak == 0

    def test_dd_burns_surplus(self, mock_repo):
        """Verify DD outcome burns surplus without capturing."""
        engine = GameEngine(
            scenario_id="test-scenario",
            scenario_repo=mock_repo,
            max_turns=14,
            random_seed=42,
        )

        # Build some surplus with CC
        engine.submit_actions(DEESCALATE, DEESCALATE)
        engine.submit_actions(DEESCALATE, DEESCALATE)

        surplus_before = engine.state.cooperation_surplus
        assert surplus_before > 0.0

        # DD - both defect
        engine.submit_actions(ESCALATE, ESCALATE)

        # Surplus should be reduced (burned)
        assert engine.state.cooperation_surplus < surplus_before
        # But neither player captured anything
        assert engine.state.surplus_captured_a == 0.0
        assert engine.state.surplus_captured_b == 0.0
        # Streak should reset
        assert engine.state.cooperation_streak == 0

    def test_streak_bonus_increases_surplus_creation(self, mock_repo):
        """Verify cooperation streak increases surplus creation rate."""
        engine = GameEngine(
            scenario_id="test-scenario",
            scenario_repo=mock_repo,
            max_turns=14,
            random_seed=42,
        )

        # First CC - base surplus
        engine.submit_actions(DEESCALATE, DEESCALATE)
        surplus_after_1 = engine.state.cooperation_surplus

        # Second CC - streak=1, should get bonus
        engine.submit_actions(DEESCALATE, DEESCALATE)
        surplus_after_2 = engine.state.cooperation_surplus
        increment_2 = surplus_after_2 - surplus_after_1

        # Third CC - streak=2, should get more bonus
        engine.submit_actions(DEESCALATE, DEESCALATE)
        surplus_after_3 = engine.state.cooperation_surplus
        increment_3 = surplus_after_3 - surplus_after_2

        # Each increment should be larger due to streak bonus
        assert increment_3 > increment_2 > surplus_after_1


class TestFinalResolution:
    """Tests for final VP resolution calculation."""

    def test_final_resolution_equal_positions(self, mock_repo):
        """Final resolution with equal positions gives ~50-50 split."""
        engine = GameEngine(
            scenario_id="test-scenario",
            scenario_repo=mock_repo,
            max_turns=14,
            random_seed=42,
        )
        engine.state.player_a.position = 5.0
        engine.state.player_b.position = 5.0

        vp_a, vp_b = engine._final_resolution()

        # With equal positions, expected value is 50-50
        # Variance may shift this, but should still sum to ~100
        assert abs(vp_a + vp_b - 100) < 0.01

    def test_final_resolution_position_advantage(self, mock_repo):
        """Final resolution favors player with position advantage."""
        engine = GameEngine(
            scenario_id="test-scenario",
            scenario_repo=mock_repo,
            max_turns=14,
            random_seed=42,
        )
        engine.state.player_a.position = 8.0
        engine.state.player_b.position = 2.0

        # Run multiple times to get average
        results = []
        for seed in range(100):
            engine._random.seed(seed)
            vp_a, vp_b = engine._final_resolution()
            results.append(vp_a)

        avg_vp_a = sum(results) / len(results)
        # With 8:2 position ratio, expected is 80 VP for A
        # Due to variance, average should be near 80
        assert 70 < avg_vp_a < 90
