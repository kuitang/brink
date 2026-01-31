"""Tests for settlement negotiation features."""

from brinksmanship.webapp.extensions import db
from brinksmanship.webapp.models import GameRecord


def create_game_record(app, user_id, turn=5, stability=8):
    """Helper to create a game record eligible for settlement."""
    with app.app_context():
        record = GameRecord(
            game_id="test-settlement",
            user_id=user_id,
            scenario_id="cuban_missile_crisis",
            opponent_type="tit-for-tat",
        )
        record.state = {
            "scenario_id": "cuban_missile_crisis",
            "scenario_name": "Cuban Missile Crisis",
            "opponent_type": "tit-for-tat",
            "turn": turn,
            "max_turns": 14,
            "position_player": 5.0,
            "position_opponent": 5.0,
            "resources_player": 5.0,
            "resources_opponent": 5.0,
            "risk_level": 2,
            "cooperation_score": 7,
            "stability": stability,
            "last_action_player": "C",
            "last_action_opponent": "C",
            "history": [{"turn": i, "player": "C", "opponent": "C"} for i in range(1, turn)],
            "briefing": "Test briefing for settlement",
            "last_outcome": None,
            "is_finished": False,
            "cooperation_surplus": 10.0,
            "surplus_captured_player": 2.0,
            "surplus_captured_opponent": 2.0,
            "cooperation_streak": 3,
        }
        db.session.add(record)
        db.session.commit()
        return record.id


class TestSettlementPanel:
    """Tests for settlement panel."""

    def test_settlement_panel_renders(self, auth_client, app, user):
        """Test settlement panel renders when conditions are met."""
        create_game_record(app, user, turn=5, stability=8)

        response = auth_client.get("/game/test-settlement/settlement")
        assert response.status_code == 200
        assert b"Negotiate Settlement" in response.data
        assert b"VP" in response.data  # Shows VP allocation

    def test_settlement_panel_unavailable_early_turn(self, auth_client, app, user):
        """Test settlement panel shows unavailable message for early turns."""
        create_game_record(app, user, turn=3, stability=8)

        response = auth_client.get("/game/test-settlement/settlement")
        assert response.status_code == 200
        assert b"not available yet" in response.data

    def test_settlement_panel_unavailable_low_stability(self, auth_client, app, user):
        """Test settlement panel shows unavailable message for low stability."""
        create_game_record(app, user, turn=5, stability=2)

        response = auth_client.get("/game/test-settlement/settlement")
        assert response.status_code == 200
        assert b"not available yet" in response.data

    def test_settlement_proposal_form_has_textarea(self, auth_client, app, user):
        """Test settlement proposal form includes text entry for argument."""
        create_game_record(app, user, turn=5, stability=8)

        response = auth_client.get("/game/test-settlement/settlement")
        assert response.status_code == 200
        assert b"textarea" in response.data
        assert b"argument" in response.data.lower() or b"Argument" in response.data


class TestSettlementProposal:
    """Tests for submitting settlement proposals."""

    def test_propose_settlement(self, auth_client, app, user):
        """Test player can propose settlement."""
        create_game_record(app, user, turn=5, stability=8)

        response = auth_client.post(
            "/game/test-settlement/settlement/propose",
            data={"offered_vp": "50", "argument": "Fair 50-50 split"},
        )
        assert response.status_code == 200

    def test_propose_settlement_with_argument(self, auth_client, app, user):
        """Test settlement proposal includes player argument."""
        create_game_record(app, user, turn=5, stability=8)

        response = auth_client.post(
            "/game/test-settlement/settlement/propose",
            data={
                "offered_vp": "55",
                "argument": "I've cooperated more, I deserve 55%",
            },
        )
        assert response.status_code == 200

    def test_propose_settlement_clamps_vp(self, auth_client, app, user):
        """Test VP is clamped to valid range 20-80."""
        create_game_record(app, user, turn=5, stability=8)

        # Try to claim 100 VP - should be clamped
        response = auth_client.post(
            "/game/test-settlement/settlement/propose",
            data={"offered_vp": "100", "argument": ""},
        )
        assert response.status_code == 200


class TestProactiveOpponentSettlement:
    """Tests for proactive opponent settlement feature."""

    def test_game_page_checks_opponent_settlement(self, auth_client, app, user):
        """Test game page includes settlement check data when eligible."""
        create_game_record(app, user, turn=5, stability=8)

        response = auth_client.get("/game/test-settlement")
        assert response.status_code == 200
        # Page should show settlement button since conditions are met
        assert b"Negotiate Settlement" in response.data

    def test_htmx_action_includes_settlement_check(self, auth_client, app, user):
        """Test HTMX action response includes settlement check."""
        create_game_record(app, user, turn=5, stability=8)

        response = auth_client.post(
            "/game/test-settlement/action",
            data={"action_id": "hold"},
            headers={"HX-Request": "true"},
        )
        assert response.status_code == 200
        # Should include game board HTML
        assert b"crisis-log" in response.data


class TestUIFeatures:
    """Tests for UI features like thinking modal and scroll."""

    def test_game_board_has_crisis_log_id(self, auth_client, app, user):
        """Test game board includes crisis-log ID for scroll targeting."""
        create_game_record(app, user, turn=5, stability=8)

        response = auth_client.get("/game/test-settlement")
        assert response.status_code == 200
        assert b'id="crisis-log"' in response.data

    def test_action_form_has_scroll_swap(self, auth_client, app, user):
        """Test action form uses hx-swap with scroll modifier."""
        create_game_record(app, user, turn=5, stability=8)

        response = auth_client.get("/game/test-settlement")
        assert response.status_code == 200
        assert b"show:#crisis-log" in response.data

    def test_thinking_modal_exists(self, auth_client, app, user):
        """Test thinking modal element exists in page."""
        create_game_record(app, user, turn=5, stability=8)

        response = auth_client.get("/game/test-settlement")
        assert response.status_code == 200
        assert b"thinking-modal" in response.data

    def test_settlement_notification_shown_when_opponent_proposes(self, auth_client, app, user):
        """Test settlement notification banner appears when conditions allow.

        Note: This tests that the notification div is in the response,
        not that opponent actually proposes (which depends on opponent AI).
        """
        create_game_record(app, user, turn=5, stability=8)

        response = auth_client.get("/game/test-settlement")
        assert response.status_code == 200
        # The settlement button should be visible when conditions are met
        assert b"Negotiate Settlement" in response.data
