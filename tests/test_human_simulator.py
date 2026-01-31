"""Tests for brinksmanship.testing.human_simulator module.

Tests cover:
- HumanSimulator class (without requiring actual LLM calls)
- Integration with Opponent interface

Note: Trivial Pydantic validation tests, accessor tests (get_mistake_probability,
get_emotional_modifier, etc.), and model tests (TestActionSelection, TestMistakeCheck,
TestSettlementResponse) were removed as they test Pydantic internals.
Actual LLM testing is in test_real_llm_integration.py.
See test_removal_log.md for details.
"""

from brinksmanship.testing.human_simulator import (
    HumanPersona,
    HumanSimulator,
)


class TestHumanSimulator:
    """Tests for HumanSimulator class that don't require LLM calls."""

    def test_create_without_persona(self):
        """Test creating simulator without initial persona."""
        simulator = HumanSimulator()
        assert simulator.persona is None

    def test_create_with_persona(self):
        """Test creating simulator with initial persona."""
        persona = HumanPersona(
            risk_tolerance="neutral",
            sophistication="intermediate",
            emotional_state="calm",
            personality="cooperative",
            backstory="Test",
            decision_style="Test",
        )
        simulator = HumanSimulator(persona=persona)
        assert simulator.persona == persona

    def test_persona_calculation_methods_work(self):
        """Test persona calculation methods return expected values."""
        persona = HumanPersona(
            risk_tolerance="risk_seeking",
            sophistication="expert",
            emotional_state="stressed",
            personality="competitive",
            backstory="A high-stakes player",
            decision_style="Quick and aggressive",
        )
        # Verify the key calculations work (not exhaustive, just sanity check)
        assert persona.get_mistake_probability() == 0.05  # expert
        assert persona.get_emotional_modifier() == 1.5  # stressed
        assert persona.get_risk_preference_bias() == 0.3  # risk_seeking
        assert persona.get_cooperation_bias() == -0.3  # competitive

    def test_effective_mistake_probability(self):
        """Test combined effective mistake probability calculation."""
        # Novice + desperate = 30% * 2.0 = 60%
        persona = HumanPersona(
            risk_tolerance="neutral",
            sophistication="novice",
            emotional_state="desperate",
            personality="cooperative",
            backstory="Test",
            decision_style="Test",
        )
        effective = persona.get_mistake_probability() * persona.get_emotional_modifier()
        assert effective == 0.60
