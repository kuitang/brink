"""Tests for brinksmanship.testing.human_simulator module.

Tests cover:
- HumanPersona model and its methods
- ActionSelection, MistakeCheck, SettlementResponse models
- Module imports (without requiring actual LLM calls)

Note: Tests that require actual LLM calls (generate_persona, choose_action, etc.)
are not included here as they require the Claude Agent SDK with valid API keys.
These would be tested in integration tests.
"""

import pytest
from pydantic import ValidationError

from brinksmanship.testing.human_simulator import (
    HumanPersona,
    ActionSelection,
    MistakeCheck,
    SettlementResponse,
    HumanSimulator,
)


# =============================================================================
# HumanPersona Model Tests
# =============================================================================


class TestHumanPersona:
    """Tests for HumanPersona model."""

    def test_create_valid_persona(self):
        """Test creating a valid HumanPersona."""
        persona = HumanPersona(
            risk_tolerance="neutral",
            sophistication="intermediate",
            emotional_state="calm",
            personality="cooperative",
            backstory="A cautious diplomat",
            decision_style="Analytical and methodical",
            triggers=["Betrayal"],
        )
        assert persona.risk_tolerance == "neutral"
        assert persona.sophistication == "intermediate"
        assert persona.emotional_state == "calm"
        assert persona.personality == "cooperative"

    def test_create_with_defaults(self):
        """Test creating persona with default triggers."""
        persona = HumanPersona(
            risk_tolerance="risk_averse",
            sophistication="novice",
            emotional_state="stressed",
            personality="erratic",
            backstory="Test persona",
            decision_style="Random",
        )
        assert persona.triggers == []

    def test_invalid_risk_tolerance(self):
        """Test validation rejects invalid risk_tolerance."""
        with pytest.raises(ValidationError):
            HumanPersona(
                risk_tolerance="invalid",
                sophistication="novice",
                emotional_state="calm",
                personality="cooperative",
                backstory="Test",
                decision_style="Test",
            )

    def test_invalid_sophistication(self):
        """Test validation rejects invalid sophistication."""
        with pytest.raises(ValidationError):
            HumanPersona(
                risk_tolerance="neutral",
                sophistication="invalid",
                emotional_state="calm",
                personality="cooperative",
                backstory="Test",
                decision_style="Test",
            )

    def test_invalid_emotional_state(self):
        """Test validation rejects invalid emotional_state."""
        with pytest.raises(ValidationError):
            HumanPersona(
                risk_tolerance="neutral",
                sophistication="novice",
                emotional_state="invalid",
                personality="cooperative",
                backstory="Test",
                decision_style="Test",
            )

    def test_invalid_personality(self):
        """Test validation rejects invalid personality."""
        with pytest.raises(ValidationError):
            HumanPersona(
                risk_tolerance="neutral",
                sophistication="novice",
                emotional_state="calm",
                personality="invalid",
                backstory="Test",
                decision_style="Test",
            )


class TestHumanPersonaMethods:
    """Tests for HumanPersona calculation methods."""

    def test_mistake_probability_novice(self):
        """Test novice has 30% mistake probability."""
        persona = HumanPersona(
            risk_tolerance="neutral",
            sophistication="novice",
            emotional_state="calm",
            personality="cooperative",
            backstory="Test",
            decision_style="Test",
        )
        assert persona.get_mistake_probability() == 0.30

    def test_mistake_probability_intermediate(self):
        """Test intermediate has 15% mistake probability."""
        persona = HumanPersona(
            risk_tolerance="neutral",
            sophistication="intermediate",
            emotional_state="calm",
            personality="cooperative",
            backstory="Test",
            decision_style="Test",
        )
        assert persona.get_mistake_probability() == 0.15

    def test_mistake_probability_expert(self):
        """Test expert has 5% mistake probability."""
        persona = HumanPersona(
            risk_tolerance="neutral",
            sophistication="expert",
            emotional_state="calm",
            personality="cooperative",
            backstory="Test",
            decision_style="Test",
        )
        assert persona.get_mistake_probability() == 0.05

    def test_emotional_modifier_calm(self):
        """Test calm has 1.0x modifier."""
        persona = HumanPersona(
            risk_tolerance="neutral",
            sophistication="novice",
            emotional_state="calm",
            personality="cooperative",
            backstory="Test",
            decision_style="Test",
        )
        assert persona.get_emotional_modifier() == 1.0

    def test_emotional_modifier_stressed(self):
        """Test stressed has 1.5x modifier."""
        persona = HumanPersona(
            risk_tolerance="neutral",
            sophistication="novice",
            emotional_state="stressed",
            personality="cooperative",
            backstory="Test",
            decision_style="Test",
        )
        assert persona.get_emotional_modifier() == 1.5

    def test_emotional_modifier_desperate(self):
        """Test desperate has 2.0x modifier."""
        persona = HumanPersona(
            risk_tolerance="neutral",
            sophistication="novice",
            emotional_state="desperate",
            personality="cooperative",
            backstory="Test",
            decision_style="Test",
        )
        assert persona.get_emotional_modifier() == 2.0

    def test_risk_preference_bias_averse(self):
        """Test risk_averse has -0.3 bias."""
        persona = HumanPersona(
            risk_tolerance="risk_averse",
            sophistication="novice",
            emotional_state="calm",
            personality="cooperative",
            backstory="Test",
            decision_style="Test",
        )
        assert persona.get_risk_preference_bias() == -0.3

    def test_risk_preference_bias_neutral(self):
        """Test neutral has 0.0 bias."""
        persona = HumanPersona(
            risk_tolerance="neutral",
            sophistication="novice",
            emotional_state="calm",
            personality="cooperative",
            backstory="Test",
            decision_style="Test",
        )
        assert persona.get_risk_preference_bias() == 0.0

    def test_risk_preference_bias_seeking(self):
        """Test risk_seeking has +0.3 bias."""
        persona = HumanPersona(
            risk_tolerance="risk_seeking",
            sophistication="novice",
            emotional_state="calm",
            personality="cooperative",
            backstory="Test",
            decision_style="Test",
        )
        assert persona.get_risk_preference_bias() == 0.3

    def test_cooperation_bias_cooperative(self):
        """Test cooperative personality has +0.3 bias."""
        persona = HumanPersona(
            risk_tolerance="neutral",
            sophistication="novice",
            emotional_state="calm",
            personality="cooperative",
            backstory="Test",
            decision_style="Test",
        )
        assert persona.get_cooperation_bias() == 0.3

    def test_cooperation_bias_competitive(self):
        """Test competitive personality has -0.3 bias."""
        persona = HumanPersona(
            risk_tolerance="neutral",
            sophistication="novice",
            emotional_state="calm",
            personality="competitive",
            backstory="Test",
            decision_style="Test",
        )
        assert persona.get_cooperation_bias() == -0.3

    def test_cooperation_bias_erratic(self):
        """Test erratic personality has 0.0 bias."""
        persona = HumanPersona(
            risk_tolerance="neutral",
            sophistication="novice",
            emotional_state="calm",
            personality="erratic",
            backstory="Test",
            decision_style="Test",
        )
        assert persona.get_cooperation_bias() == 0.0


class TestEffectiveMistakeProbability:
    """Tests for combined mistake probability calculation."""

    def test_novice_calm(self):
        """Test novice + calm = 30% * 1.0 = 30%."""
        persona = HumanPersona(
            risk_tolerance="neutral",
            sophistication="novice",
            emotional_state="calm",
            personality="cooperative",
            backstory="Test",
            decision_style="Test",
        )
        effective = persona.get_mistake_probability() * persona.get_emotional_modifier()
        assert effective == 0.30

    def test_novice_desperate(self):
        """Test novice + desperate = 30% * 2.0 = 60%."""
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

    def test_expert_stressed(self):
        """Test expert + stressed = 5% * 1.5 = 7.5%."""
        persona = HumanPersona(
            risk_tolerance="neutral",
            sophistication="expert",
            emotional_state="stressed",
            personality="cooperative",
            backstory="Test",
            decision_style="Test",
        )
        effective = persona.get_mistake_probability() * persona.get_emotional_modifier()
        assert effective == pytest.approx(0.075)


# =============================================================================
# ActionSelection Model Tests
# =============================================================================


class TestActionSelection:
    """Tests for ActionSelection model."""

    def test_create_valid_selection(self):
        """Test creating a valid ActionSelection."""
        selection = ActionSelection(
            reasoning="Strategic analysis...",
            emotional_reaction="Feeling confident",
            selected_action="De-escalate",
            confidence="high",
        )
        assert selection.selected_action == "De-escalate"
        assert selection.confidence == "high"

    def test_invalid_confidence(self):
        """Test validation rejects invalid confidence."""
        with pytest.raises(ValidationError):
            ActionSelection(
                reasoning="Test",
                emotional_reaction="Test",
                selected_action="Test",
                confidence="invalid",
            )


# =============================================================================
# MistakeCheck Model Tests
# =============================================================================


class TestMistakeCheck:
    """Tests for MistakeCheck model."""

    def test_no_mistake(self):
        """Test creating a no-mistake result."""
        check = MistakeCheck(
            would_make_mistake=False,
            mistake_type=None,
            explanation="Playing optimally",
        )
        assert check.would_make_mistake is False
        assert check.mistake_type is None

    def test_impulsive_mistake(self):
        """Test creating an impulsive mistake."""
        check = MistakeCheck(
            would_make_mistake=True,
            mistake_type="impulsive",
            explanation="Acting without thinking",
        )
        assert check.would_make_mistake is True
        assert check.mistake_type == "impulsive"

    def test_overcautious_mistake(self):
        """Test creating an overcautious mistake."""
        check = MistakeCheck(
            would_make_mistake=True,
            mistake_type="overcautious",
            explanation="Too afraid to take risks",
        )
        assert check.mistake_type == "overcautious"

    def test_vindictive_mistake(self):
        """Test creating a vindictive mistake."""
        check = MistakeCheck(
            would_make_mistake=True,
            mistake_type="vindictive",
            explanation="Seeking revenge",
        )
        assert check.mistake_type == "vindictive"

    def test_overconfident_mistake(self):
        """Test creating an overconfident mistake."""
        check = MistakeCheck(
            would_make_mistake=True,
            mistake_type="overconfident",
            explanation="Too sure of themselves",
        )
        assert check.mistake_type == "overconfident"

    def test_invalid_mistake_type(self):
        """Test validation rejects invalid mistake_type."""
        with pytest.raises(ValidationError):
            MistakeCheck(
                would_make_mistake=True,
                mistake_type="invalid",
                explanation="Test",
            )


# =============================================================================
# SettlementResponse Model Tests
# =============================================================================


class TestSettlementResponse:
    """Tests for SettlementResponse model."""

    def test_accept_settlement(self):
        """Test creating an accept response."""
        response = SettlementResponse(
            reasoning="Good deal",
            emotional_response="Relieved",
            decision="accept",
        )
        assert response.decision == "accept"
        assert response.counter_vp is None

    def test_counter_settlement(self):
        """Test creating a counter response."""
        response = SettlementResponse(
            reasoning="Could be better",
            emotional_response="Negotiating",
            decision="counter",
            counter_vp=55,
            counter_argument="I deserve more",
        )
        assert response.decision == "counter"
        assert response.counter_vp == 55
        assert response.counter_argument == "I deserve more"

    def test_reject_settlement(self):
        """Test creating a reject response."""
        response = SettlementResponse(
            reasoning="Bad deal",
            emotional_response="Insulted",
            decision="reject",
            rejection_reason="Too low",
        )
        assert response.decision == "reject"
        assert response.rejection_reason == "Too low"

    def test_invalid_decision(self):
        """Test validation rejects invalid decision."""
        with pytest.raises(ValidationError):
            SettlementResponse(
                reasoning="Test",
                emotional_response="Test",
                decision="invalid",
            )


# =============================================================================
# HumanSimulator Class Tests (Non-LLM)
# =============================================================================


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

    def test_persona_attribute(self):
        """Test persona can be accessed after initialization."""
        persona = HumanPersona(
            risk_tolerance="risk_seeking",
            sophistication="expert",
            emotional_state="stressed",
            personality="competitive",
            backstory="A high-stakes player",
            decision_style="Quick and aggressive",
        )
        simulator = HumanSimulator(persona=persona)
        assert simulator.persona.risk_tolerance == "risk_seeking"
        assert simulator.persona.sophistication == "expert"


# =============================================================================
# Edge Cases and Validation Tests
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_persona_with_empty_triggers(self):
        """Test persona with explicitly empty triggers list."""
        persona = HumanPersona(
            risk_tolerance="neutral",
            sophistication="novice",
            emotional_state="calm",
            personality="cooperative",
            backstory="Test",
            decision_style="Test",
            triggers=[],
        )
        assert persona.triggers == []

    def test_persona_with_multiple_triggers(self):
        """Test persona with multiple triggers."""
        triggers = ["Betrayal", "Time pressure", "Being ignored"]
        persona = HumanPersona(
            risk_tolerance="neutral",
            sophistication="novice",
            emotional_state="calm",
            personality="cooperative",
            backstory="Test",
            decision_style="Test",
            triggers=triggers,
        )
        assert len(persona.triggers) == 3
        assert "Betrayal" in persona.triggers

    def test_all_risk_tolerance_values(self):
        """Test all valid risk_tolerance values work."""
        for risk in ["risk_averse", "neutral", "risk_seeking"]:
            persona = HumanPersona(
                risk_tolerance=risk,
                sophistication="novice",
                emotional_state="calm",
                personality="cooperative",
                backstory="Test",
                decision_style="Test",
            )
            assert persona.risk_tolerance == risk

    def test_all_sophistication_values(self):
        """Test all valid sophistication values work."""
        for soph in ["novice", "intermediate", "expert"]:
            persona = HumanPersona(
                risk_tolerance="neutral",
                sophistication=soph,
                emotional_state="calm",
                personality="cooperative",
                backstory="Test",
                decision_style="Test",
            )
            assert persona.sophistication == soph

    def test_all_emotional_state_values(self):
        """Test all valid emotional_state values work."""
        for state in ["calm", "stressed", "desperate"]:
            persona = HumanPersona(
                risk_tolerance="neutral",
                sophistication="novice",
                emotional_state=state,
                personality="cooperative",
                backstory="Test",
                decision_style="Test",
            )
            assert persona.emotional_state == state

    def test_all_personality_values(self):
        """Test all valid personality values work."""
        for pers in ["cooperative", "competitive", "erratic"]:
            persona = HumanPersona(
                risk_tolerance="neutral",
                sophistication="novice",
                emotional_state="calm",
                personality=pers,
                backstory="Test",
                decision_style="Test",
            )
            assert persona.personality == pers

    def test_persona_serialization(self):
        """Test persona can be serialized to dict."""
        persona = HumanPersona(
            risk_tolerance="neutral",
            sophistication="intermediate",
            emotional_state="calm",
            personality="cooperative",
            backstory="A test persona",
            decision_style="Careful",
            triggers=["Surprise"],
        )
        data = persona.model_dump()
        assert data["risk_tolerance"] == "neutral"
        assert data["sophistication"] == "intermediate"
        assert data["backstory"] == "A test persona"
        assert data["triggers"] == ["Surprise"]

    def test_persona_json_serialization(self):
        """Test persona can be serialized to JSON."""
        persona = HumanPersona(
            risk_tolerance="neutral",
            sophistication="intermediate",
            emotional_state="calm",
            personality="cooperative",
            backstory="Test",
            decision_style="Test",
        )
        json_str = persona.model_dump_json()
        assert "neutral" in json_str
        assert "intermediate" in json_str
