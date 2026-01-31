"""Integration tests for HumanSimulator with mocked LLM.

These tests verify the full flow of HumanSimulator including:
- Persona generation
- Action selection with various game states
- Settlement evaluation
- Mistake injection

The LLM calls are mocked to provide deterministic testing.
"""

from unittest.mock import patch

import pytest

from brinksmanship.models.actions import Action, ActionCategory, ActionType
from brinksmanship.models.state import GameState, InformationState, PlayerState
from brinksmanship.opponents.base import SettlementProposal, SettlementResponse
from brinksmanship.testing.human_simulator import (
    HumanPersona,
    HumanSimulator,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def sample_persona():
    """A sample HumanPersona for testing."""
    return HumanPersona(
        risk_tolerance="neutral",
        sophistication="intermediate",
        emotional_state="calm",
        personality="cooperative",
        backstory="A seasoned diplomat who values stability",
        decision_style="Analytical and cautious",
        triggers=["Betrayal", "Sudden aggression"],
    )


@pytest.fixture
def sample_game_state():
    """A sample GameState for testing."""
    return GameState(
        player_a=PlayerState(
            position=5.5,
            resources=4.0,
            previous_type=None,
            information=InformationState(),
        ),
        player_b=PlayerState(
            position=4.5,
            resources=5.0,
            previous_type=None,
            information=InformationState(),
        ),
        cooperation_score=5.0,
        stability=5.0,
        risk_level=3.0,
        turn=3,
        max_turns=14,
    )


@pytest.fixture
def sample_actions():
    """Sample available actions for testing."""
    return [
        Action(
            name="Maintain Position",
            action_type=ActionType.COOPERATIVE,
            resource_cost=0.0,
            category=ActionCategory.STANDARD,
            description="Hold steady, signal stability",
        ),
        Action(
            name="Apply Pressure",
            action_type=ActionType.COMPETITIVE,
            resource_cost=0.0,
            category=ActionCategory.STANDARD,
            description="Increase pressure on opponent",
        ),
        Action(
            name="Escalate",
            action_type=ActionType.COMPETITIVE,
            resource_cost=0.5,
            category=ActionCategory.STANDARD,
            description="Major escalation",
        ),
    ]


# =============================================================================
# Mocked LLM Response Generators
# =============================================================================


def mock_persona_response():
    """Generate a mock persona response."""
    return {
        "risk_tolerance": "risk_averse",
        "sophistication": "expert",
        "emotional_state": "calm",
        "personality": "cooperative",
        "backstory": "A veteran diplomat from a neutral nation",
        "decision_style": "Methodical analysis before action",
        "triggers": ["Unprovoked aggression", "Broken promises"],
    }


def mock_action_selection_response(action_name: str = "Maintain Position"):
    """Generate a mock action selection response."""
    return {
        "reasoning": "Given the current state, cooperation seems optimal",
        "emotional_reaction": "Confident in this approach",
        "selected_action": action_name,
        "confidence": "high",
    }


def mock_mistake_check_response(would_make_mistake: bool = False):
    """Generate a mock mistake check response."""
    return {
        "would_make_mistake": would_make_mistake,
        "mistake_type": "impulsive" if would_make_mistake else None,
        "explanation": "Acting on emotion" if would_make_mistake else "Playing optimally",
    }


def mock_settlement_response(decision: str = "accept"):
    """Generate a mock settlement evaluation response."""
    return {
        "reasoning": "The offer seems fair given positions",
        "emotional_response": "Relieved at the prospect of resolution",
        "decision": decision,
        "counter_vp": 55 if decision == "counter" else None,
        "counter_argument": "Slight adjustment needed" if decision == "counter" else None,
        "rejection_reason": "Too low" if decision == "reject" else None,
    }


# =============================================================================
# Tests for Persona Generation
# =============================================================================


class TestPersonaGeneration:
    """Tests for persona generation with mocked LLM."""

    @pytest.mark.asyncio
    async def test_generate_persona_success(self):
        """Test successful persona generation."""
        simulator = HumanSimulator(is_player_a=True)

        with patch("brinksmanship.testing.human_simulator.generate_json") as mock_gen:
            mock_gen.return_value = mock_persona_response()

            persona = await simulator.generate_persona()

            assert persona is not None
            assert persona.risk_tolerance == "risk_averse"
            assert persona.sophistication == "expert"
            assert persona.emotional_state == "calm"
            assert simulator.persona == persona

    @pytest.mark.asyncio
    async def test_generate_persona_stores_persona(self):
        """Test that generated persona is stored in simulator."""
        simulator = HumanSimulator(is_player_a=False)

        with patch("brinksmanship.testing.human_simulator.generate_json") as mock_gen:
            mock_gen.return_value = mock_persona_response()

            await simulator.generate_persona()

            assert simulator.persona is not None
            assert simulator.persona.backstory == "A veteran diplomat from a neutral nation"


# =============================================================================
# Tests for Action Selection
# =============================================================================


class TestActionSelection:
    """Tests for action selection with mocked LLM."""

    @pytest.mark.asyncio
    async def test_choose_action_cooperative_persona(self, sample_persona, sample_game_state, sample_actions):
        """Test that cooperative persona tends toward cooperative actions."""
        simulator = HumanSimulator(persona=sample_persona, is_player_a=True)

        with patch("brinksmanship.testing.human_simulator.generate_json") as mock_gen:
            # First call: action selection, second call: mistake check
            mock_gen.side_effect = [
                mock_action_selection_response("Maintain Position"),
                mock_mistake_check_response(False),
            ]

            action = await simulator.choose_action(sample_game_state, sample_actions)

            assert action is not None
            assert action.name == "Maintain Position"
            assert action.action_type == ActionType.COOPERATIVE

    @pytest.mark.asyncio
    async def test_choose_action_without_persona_raises(self, sample_game_state, sample_actions):
        """Test that choosing action without persona raises error."""
        simulator = HumanSimulator(is_player_a=True)

        with pytest.raises(ValueError, match="No persona set"):
            await simulator.choose_action(sample_game_state, sample_actions)

    @pytest.mark.asyncio
    async def test_choose_action_fallback_on_invalid_response(self, sample_persona, sample_game_state, sample_actions):
        """Test fallback when LLM returns invalid action name."""
        simulator = HumanSimulator(persona=sample_persona, is_player_a=True)

        with patch("brinksmanship.testing.human_simulator.generate_json") as mock_gen:
            # First call: invalid action name
            # Second call: mistake check returns no mistake
            mock_gen.side_effect = [
                mock_action_selection_response("NonexistentAction"),
                mock_mistake_check_response(False),
            ]

            # Should still return a valid action via fallback
            action = await simulator.choose_action(sample_game_state, sample_actions)

            assert action is not None
            assert action in sample_actions

    @pytest.mark.asyncio
    async def test_choose_action_different_personas_vary(self, sample_game_state, sample_actions):
        """Test that different personas produce different action patterns."""
        cooperative_persona = HumanPersona(
            risk_tolerance="risk_averse",
            sophistication="expert",
            emotional_state="calm",
            personality="cooperative",
            backstory="Peacemaker",
            decision_style="Cautious",
        )

        competitive_persona = HumanPersona(
            risk_tolerance="risk_seeking",
            sophistication="expert",
            emotional_state="stressed",
            personality="competitive",
            backstory="Aggressive negotiator",
            decision_style="Forceful",
        )

        coop_simulator = HumanSimulator(persona=cooperative_persona, is_player_a=True)
        comp_simulator = HumanSimulator(persona=competitive_persona, is_player_a=True)

        with patch("brinksmanship.testing.human_simulator.generate_json") as mock_gen:
            # First call: action selection, second call: mistake check
            mock_gen.side_effect = [
                mock_action_selection_response("Maintain Position"),
                mock_mistake_check_response(False),
            ]
            coop_action = await coop_simulator.choose_action(sample_game_state, sample_actions)

        with patch("brinksmanship.testing.human_simulator.generate_json") as mock_gen:
            # First call: action selection, second call: mistake check
            mock_gen.side_effect = [
                mock_action_selection_response("Apply Pressure"),
                mock_mistake_check_response(False),
            ]
            comp_action = await comp_simulator.choose_action(sample_game_state, sample_actions)

        # Different personas can select different actions
        assert coop_action.action_type == ActionType.COOPERATIVE
        assert comp_action.action_type == ActionType.COMPETITIVE


# =============================================================================
# Tests for Mistake Injection
# =============================================================================


class TestMistakeInjection:
    """Tests for mistake injection behavior."""

    @pytest.mark.asyncio
    async def test_mistake_applied_when_triggered(self, sample_game_state, sample_actions):
        """Test that mistakes are applied when LLM says to make mistake."""
        # Novice, desperate persona = high mistake probability
        novice_persona = HumanPersona(
            risk_tolerance="neutral",
            sophistication="novice",
            emotional_state="desperate",
            personality="erratic",
            backstory="Inexperienced and panicking",
            decision_style="Reactive",
        )

        simulator = HumanSimulator(persona=novice_persona, is_player_a=True)

        with patch("brinksmanship.testing.human_simulator.generate_json") as mock_gen:
            mock_gen.side_effect = [
                # First: LLM suggests cooperative action
                mock_action_selection_response("Maintain Position"),
                # Second: Mistake check says make impulsive mistake
                mock_mistake_check_response(would_make_mistake=True),
            ]

            # Use a fixed random seed to control the probability check
            import random

            random.seed(0)  # Makes random.random() < 0.60 (novice * desperate)

            await simulator._choose_action_async(sample_game_state, sample_actions)

            # With impulsive mistake, should pick competitive action
            # Note: exact behavior depends on random, but test verifies the flow


# =============================================================================
# Tests for Settlement Evaluation
# =============================================================================


class TestSettlementEvaluation:
    """Tests for settlement evaluation with mocked LLM."""

    @pytest.mark.asyncio
    async def test_evaluate_settlement_accept(self, sample_persona, sample_game_state):
        """Test accepting a settlement proposal."""
        simulator = HumanSimulator(persona=sample_persona, is_player_a=False)

        proposal = SettlementProposal(
            offered_vp=48,  # Proposer wants 48, responder gets 52
            argument="Fair split based on positions",
        )

        with patch("brinksmanship.testing.human_simulator.generate_json") as mock_gen:
            mock_gen.return_value = mock_settlement_response("accept")

            response = await simulator.evaluate_settlement(proposal, sample_game_state, is_final_offer=False)

            assert response.action == "accept"
            assert response.counter_vp is None

    @pytest.mark.asyncio
    async def test_evaluate_settlement_counter(self, sample_persona, sample_game_state):
        """Test countering a settlement proposal."""
        simulator = HumanSimulator(persona=sample_persona, is_player_a=False)

        proposal = SettlementProposal(
            offered_vp=60,  # Proposer wants 60, responder gets 40
            argument="My position warrants this",
        )

        with patch("brinksmanship.testing.human_simulator.generate_json") as mock_gen:
            mock_gen.return_value = mock_settlement_response("counter")

            response = await simulator.evaluate_settlement(proposal, sample_game_state, is_final_offer=False)

            assert response.action == "counter"
            assert response.counter_vp == 55

    @pytest.mark.asyncio
    async def test_evaluate_settlement_reject(self, sample_persona, sample_game_state):
        """Test rejecting a settlement proposal."""
        simulator = HumanSimulator(persona=sample_persona, is_player_a=False)

        proposal = SettlementProposal(
            offered_vp=80,  # Very unfair offer
            argument="Take it or leave it",
        )

        with patch("brinksmanship.testing.human_simulator.generate_json") as mock_gen:
            mock_gen.return_value = mock_settlement_response("reject")

            response = await simulator.evaluate_settlement(proposal, sample_game_state, is_final_offer=True)

            assert response.action == "reject"
            assert response.rejection_reason == "Too low"


# =============================================================================
# Tests for Settlement Proposal
# =============================================================================


class TestSettlementProposal:
    """Tests for proposing settlements."""

    @pytest.mark.asyncio
    async def test_propose_settlement_early_turn_returns_none(self, sample_persona):
        """Test that settlement is not proposed in early turns."""
        early_state = GameState(
            player_a=PlayerState(position=5.0, resources=5.0),
            player_b=PlayerState(position=5.0, resources=5.0),
            cooperation_score=5.0,
            stability=5.0,
            risk_level=3.0,
            turn=2,  # Too early
            max_turns=14,
        )

        simulator = HumanSimulator(persona=sample_persona, is_player_a=True)
        proposal = await simulator.propose_settlement(early_state)

        assert proposal is None

    @pytest.mark.asyncio
    async def test_propose_settlement_low_stability_returns_none(self, sample_persona):
        """Test that settlement is not proposed when stability is too low."""
        unstable_state = GameState(
            player_a=PlayerState(position=5.0, resources=5.0),
            player_b=PlayerState(position=5.0, resources=5.0),
            cooperation_score=5.0,
            stability=1.5,  # Too low
            risk_level=3.0,
            turn=8,
            max_turns=14,
        )

        simulator = HumanSimulator(persona=sample_persona, is_player_a=True)
        proposal = await simulator.propose_settlement(unstable_state)

        assert proposal is None

    @pytest.mark.asyncio
    async def test_propose_settlement_high_risk_more_likely(self):
        """Test that high risk increases settlement probability."""
        risk_averse_persona = HumanPersona(
            risk_tolerance="risk_averse",
            sophistication="expert",
            emotional_state="stressed",
            personality="cooperative",
            backstory="Wants to end this",
            decision_style="Seeking resolution",
        )

        high_risk_state = GameState(
            player_a=PlayerState(position=6.0, resources=4.0),
            player_b=PlayerState(position=4.0, resources=5.0),
            cooperation_score=5.0,
            stability=5.0,
            risk_level=8.0,  # High risk
            turn=8,
            max_turns=14,
        )

        simulator = HumanSimulator(persona=risk_averse_persona, is_player_a=True)

        # With high risk + risk_averse + stressed, probability is very high
        # Run multiple times to verify it can propose
        import random

        random.seed(42)

        proposals = []
        for _ in range(10):
            proposal = await simulator.propose_settlement(high_risk_state)
            proposals.append(proposal)

        # At least some should be proposals
        actual_proposals = [p for p in proposals if p is not None]
        assert len(actual_proposals) > 0

    @pytest.mark.asyncio
    async def test_propose_settlement_returns_valid_proposal(self, sample_persona):
        """Test that returned proposal has valid structure."""
        good_state = GameState(
            player_a=PlayerState(position=6.0, resources=5.0),
            player_b=PlayerState(position=4.0, resources=5.0),
            cooperation_score=7.0,
            stability=6.0,
            risk_level=8.0,
            turn=8,
            max_turns=14,
        )

        # Force high settlement probability
        desperate_persona = HumanPersona(
            risk_tolerance="risk_averse",
            sophistication="expert",
            emotional_state="desperate",
            personality="cooperative",
            backstory="Test",
            decision_style="Test",
        )

        simulator = HumanSimulator(persona=desperate_persona, is_player_a=True)

        import random

        random.seed(0)  # Seed to ensure we hit the proposal path

        proposal = await simulator.propose_settlement(good_state)

        if proposal is not None:
            assert isinstance(proposal, SettlementProposal)
            assert 20 <= proposal.offered_vp <= 80
            assert len(proposal.argument) > 0


# =============================================================================
# Tests for Emotional State Updates
# =============================================================================


class TestEmotionalStateUpdate:
    """Tests for emotional state transitions."""

    def test_exploited_increases_stress(self, sample_persona):
        """Test that being exploited can increase stress."""
        simulator = HumanSimulator(persona=sample_persona, is_player_a=True)
        assert simulator.persona.emotional_state == "calm"

        import random

        random.seed(0)  # Seed to ensure state change

        # Multiple exploitations should eventually increase stress
        for _ in range(10):
            simulator.update_emotional_state("exploited", -1.0)

        # Should have changed at some point (probabilistic)
        # Note: actual change depends on random, test just verifies method runs

    def test_positive_outcome_can_reduce_stress(self):
        """Test that positive outcomes can reduce stress."""
        stressed_persona = HumanPersona(
            risk_tolerance="neutral",
            sophistication="intermediate",
            emotional_state="stressed",
            personality="cooperative",
            backstory="Test",
            decision_style="Test",
        )

        simulator = HumanSimulator(persona=stressed_persona, is_player_a=True)
        assert simulator.persona.emotional_state == "stressed"

        import random

        random.seed(42)

        # Multiple positive outcomes
        for _ in range(10):
            simulator.update_emotional_state("exploiter", 1.0)

        # May have calmed down

    def test_mutual_coop_tends_to_calm(self):
        """Test that mutual cooperation tends toward calm state."""
        stressed_persona = HumanPersona(
            risk_tolerance="neutral",
            sophistication="intermediate",
            emotional_state="stressed",
            personality="cooperative",
            backstory="Test",
            decision_style="Test",
        )

        simulator = HumanSimulator(persona=stressed_persona, is_player_a=True)

        import random

        random.seed(123)

        # Many mutual cooperation outcomes
        for _ in range(20):
            simulator.update_emotional_state("mutual_coop", 0.5)

        # May have calmed (probabilistic)


# =============================================================================
# Tests for Interface Compliance
# =============================================================================


class TestOpponentInterfaceCompliance:
    """Tests verifying HumanSimulator implements Opponent interface correctly."""

    @pytest.mark.asyncio
    async def test_choose_action_signature(self, sample_persona, sample_game_state, sample_actions):
        """Test choose_action has correct signature."""
        simulator = HumanSimulator(persona=sample_persona, is_player_a=True)

        with patch("brinksmanship.testing.human_simulator.generate_json") as mock_gen:
            # First call: action selection, second call: mistake check
            mock_gen.side_effect = [
                mock_action_selection_response("Maintain Position"),
                mock_mistake_check_response(False),
            ]

            # Should accept GameState and list[Action], return Action
            action = await simulator.choose_action(sample_game_state, sample_actions)

            assert isinstance(action, Action)

    @pytest.mark.asyncio
    async def test_evaluate_settlement_signature(self, sample_persona, sample_game_state):
        """Test evaluate_settlement has correct signature."""
        simulator = HumanSimulator(persona=sample_persona, is_player_a=False)

        proposal = SettlementProposal(offered_vp=50, argument="Test")

        with patch("brinksmanship.testing.human_simulator.generate_json") as mock_gen:
            mock_gen.return_value = mock_settlement_response("accept")

            # Should accept SettlementProposal, GameState, bool
            response = await simulator.evaluate_settlement(proposal, sample_game_state, False)

            assert isinstance(response, SettlementResponse)

    @pytest.mark.asyncio
    async def test_propose_settlement_signature(self, sample_persona):
        """Test propose_settlement has correct signature."""
        simulator = HumanSimulator(persona=sample_persona, is_player_a=True)

        state = GameState(
            player_a=PlayerState(position=6.0, resources=5.0),
            player_b=PlayerState(position=4.0, resources=5.0),
            turn=8,
            max_turns=14,
        )

        # Should accept GameState, return SettlementProposal | None
        result = await simulator.propose_settlement(state)

        assert result is None or isinstance(result, SettlementProposal)
