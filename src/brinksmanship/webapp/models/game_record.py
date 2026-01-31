"""Game record model for persisting game state."""

from datetime import datetime
from typing import Any

from ..extensions import db


class TurnHistory(db.Model):
    """Normalized turn history for a game with full trace data."""

    __tablename__ = "turn_history"

    id = db.Column(db.Integer, primary_key=True)
    game_id = db.Column(db.Integer, db.ForeignKey("game_records.id"), nullable=False, index=True)
    turn = db.Column(db.Integer, nullable=False)

    # Action types (C/D for quick filtering)
    player_action = db.Column(db.String(1), nullable=False)  # 'C' or 'D'
    opponent_action = db.Column(db.String(1), nullable=False)

    # Full action names for trace
    player_action_name = db.Column(db.String(128), nullable=True)
    opponent_action_name = db.Column(db.String(128), nullable=True)

    # Outcome
    outcome_code = db.Column(db.String(8), nullable=True)  # e.g., 'CC', 'CD', 'DC', 'DD'
    narrative = db.Column(db.Text, nullable=True)

    # State snapshot after this turn (JSON)
    state_after = db.Column(db.JSON, nullable=True)

    # Timestamp
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('game_id', 'turn', name='unique_game_turn'),
    )


class SettlementAttempt(db.Model):
    """Settlement negotiation attempts for a game."""

    __tablename__ = "settlement_attempts"

    id = db.Column(db.Integer, primary_key=True)
    game_id = db.Column(db.Integer, db.ForeignKey("game_records.id"), nullable=False, index=True)
    turn = db.Column(db.Integer, nullable=False)

    # Who proposed
    proposer = db.Column(db.String(16), nullable=False)  # 'player' or 'opponent'

    # Proposal details
    offered_vp = db.Column(db.Integer, nullable=False)
    argument = db.Column(db.Text, nullable=True)

    # Response
    response_action = db.Column(db.String(16), nullable=True)  # 'accept', 'reject', 'counter'
    counter_vp = db.Column(db.Integer, nullable=True)
    counter_argument = db.Column(db.Text, nullable=True)
    rejection_reason = db.Column(db.Text, nullable=True)

    # Timestamp
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class GameRecord(db.Model):
    """Persisted game state with normalized columns."""

    __tablename__ = "game_records"

    # Primary key and relationships
    id = db.Column(db.Integer, primary_key=True)
    game_id = db.Column(db.String(64), unique=True, nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    # Scenario and opponent configuration
    scenario_id = db.Column(db.String(64), nullable=False)
    scenario_name = db.Column(db.String(128), nullable=True)
    opponent_type = db.Column(db.String(64), nullable=False)
    custom_persona = db.Column(db.Text, nullable=True)

    # Normalized game state
    turn = db.Column(db.Integer, default=1, nullable=False)
    max_turns = db.Column(db.Integer, default=14, nullable=False)
    position_player = db.Column(db.Float, default=5.0, nullable=False)
    position_opponent = db.Column(db.Float, default=5.0, nullable=False)
    resources_player = db.Column(db.Float, default=5.0, nullable=False)
    resources_opponent = db.Column(db.Float, default=5.0, nullable=False)
    risk_level = db.Column(db.Float, default=2.0, nullable=False)
    cooperation_score = db.Column(db.Integer, default=5, nullable=False)
    stability = db.Column(db.Integer, default=5, nullable=False)

    # Surplus mechanics (Joint Investment model)
    cooperation_surplus = db.Column(db.Float, default=0.0, nullable=False)
    surplus_captured_player = db.Column(db.Float, default=0.0, nullable=False)
    surplus_captured_opponent = db.Column(db.Float, default=0.0, nullable=False)
    cooperation_streak = db.Column(db.Integer, default=0, nullable=False)

    # Last actions (for display)
    last_action_player = db.Column(db.String(64), nullable=True)
    last_action_opponent = db.Column(db.String(64), nullable=True)
    last_outcome = db.Column(db.Text, nullable=True)
    briefing = db.Column(db.Text, nullable=True)

    # Game completion status
    is_finished = db.Column(db.Boolean, default=False)
    ending_type = db.Column(db.String(32), nullable=True)
    final_vp_player = db.Column(db.Integer, nullable=True)
    final_vp_opponent = db.Column(db.Integer, nullable=True)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    finished_at = db.Column(db.DateTime, nullable=True)

    # Relationship to turn history
    turns = db.relationship('TurnHistory', backref='game', lazy='dynamic',
                           order_by='TurnHistory.turn', cascade='all, delete-orphan')

    # Relationship to settlement attempts
    settlement_attempts = db.relationship('SettlementAttempt', backref='game', lazy='dynamic',
                                          order_by='SettlementAttempt.turn', cascade='all, delete-orphan')

    @property
    def history(self) -> list[dict[str, Any]]:
        """Get turn history as list of dicts (includes narrative for display)."""
        return [
            {
                "turn": t.turn,
                "player": t.player_action,
                "opponent": t.opponent_action,
                "narrative": t.narrative,
            }
            for t in self.turns.all()
        ]

    def add_turn(
        self,
        turn: int,
        player: str,
        opponent: str,
        player_action_name: str | None = None,
        opponent_action_name: str | None = None,
        outcome_code: str | None = None,
        narrative: str | None = None,
        state_after: dict | None = None,
    ) -> None:
        """Add a turn to history with full trace data.

        Args:
            turn: Turn number
            player: 'C' for cooperative, 'D' for competitive
            opponent: 'C' for cooperative, 'D' for competitive
            player_action_name: Full name of player's action
            opponent_action_name: Full name of opponent's action
            outcome_code: Result code (CC, CD, DC, DD)
            narrative: Narrative text for this turn
            state_after: State snapshot after this turn
        """
        entry = TurnHistory(
            game_id=self.id,
            turn=turn,
            player_action=player,
            opponent_action=opponent,
            player_action_name=player_action_name,
            opponent_action_name=opponent_action_name,
            outcome_code=outcome_code,
            narrative=narrative,
            state_after=state_after,
        )
        db.session.add(entry)

    def add_settlement_attempt(
        self,
        turn: int,
        proposer: str,
        offered_vp: int,
        argument: str | None = None,
        response_action: str | None = None,
        counter_vp: int | None = None,
        counter_argument: str | None = None,
        rejection_reason: str | None = None,
    ) -> None:
        """Record a settlement attempt.

        Args:
            turn: Turn number
            proposer: 'player' or 'opponent'
            offered_vp: VP offered by proposer
            argument: Argument for the proposal
            response_action: 'accept', 'reject', or 'counter'
            counter_vp: Counter VP if countered
            counter_argument: Counter argument if countered
            rejection_reason: Reason if rejected
        """
        attempt = SettlementAttempt(
            game_id=self.id,
            turn=turn,
            proposer=proposer,
            offered_vp=offered_vp,
            argument=argument,
            response_action=response_action,
            counter_vp=counter_vp,
            counter_argument=counter_argument,
            rejection_reason=rejection_reason,
        )
        db.session.add(attempt)

    def get_trace(self) -> dict[str, Any]:
        """Get full game trace for export/analysis."""
        return {
            "game_id": self.game_id,
            "scenario_id": self.scenario_id,
            "scenario_name": self.scenario_name,
            "opponent_type": self.opponent_type,
            "custom_persona": self.custom_persona,
            "start_time": self.created_at.isoformat() if self.created_at else None,
            "end_time": self.finished_at.isoformat() if self.finished_at else None,
            "turns": [
                {
                    "turn": t.turn,
                    "player_action": t.player_action,
                    "player_action_name": t.player_action_name,
                    "opponent_action": t.opponent_action,
                    "opponent_action_name": t.opponent_action_name,
                    "outcome_code": t.outcome_code,
                    "narrative": t.narrative,
                    "state_after": t.state_after,
                    "timestamp": t.created_at.isoformat() if t.created_at else None,
                }
                for t in self.turns.all()
            ],
            "settlement_attempts": [
                {
                    "turn": s.turn,
                    "proposer": s.proposer,
                    "offered_vp": s.offered_vp,
                    "argument": s.argument,
                    "response_action": s.response_action,
                    "counter_vp": s.counter_vp,
                    "counter_argument": s.counter_argument,
                    "rejection_reason": s.rejection_reason,
                    "timestamp": s.created_at.isoformat() if s.created_at else None,
                }
                for s in self.settlement_attempts.all()
            ],
            "ending": {
                "type": self.ending_type,
                "vp_player": self.final_vp_player,
                "vp_opponent": self.final_vp_opponent,
            } if self.is_finished else None,
        }

    @property
    def state(self) -> dict[str, Any]:
        """Get complete game state as dictionary (for compatibility)."""
        return {
            "game_id": self.game_id,
            "scenario_id": self.scenario_id,
            "scenario_name": self.scenario_name or self.scenario_id,
            "opponent_type": self.opponent_type,
            "custom_persona": self.custom_persona,
            "turn": self.turn,
            "max_turns": self.max_turns,
            "position_player": self.position_player,
            "position_opponent": self.position_opponent,
            "resources_player": self.resources_player,
            "resources_opponent": self.resources_opponent,
            "risk_level": self.risk_level,
            "cooperation_score": self.cooperation_score,
            "stability": self.stability,
            "last_action_player": self.last_action_player,
            "last_action_opponent": self.last_action_opponent,
            "last_outcome": self.last_outcome,
            "briefing": self.briefing,
            "history": self.history,
            "is_finished": self.is_finished,
            "ending_type": self.ending_type,
            "vp_player": self.final_vp_player,
            "vp_opponent": self.final_vp_opponent,
            # Surplus mechanics
            "cooperation_surplus": self.cooperation_surplus,
            "surplus_captured_player": self.surplus_captured_player,
            "surplus_captured_opponent": self.surplus_captured_opponent,
            "cooperation_streak": self.cooperation_streak,
        }

    def update_from_state(self, value: dict[str, Any]) -> None:
        """Update game record from state dictionary.

        Note: History is handled via add_turn(), not through this method.
        """
        field_map = {
            "turn": "turn",
            "max_turns": "max_turns",
            "position_player": "position_player",
            "position_opponent": "position_opponent",
            "resources_player": "resources_player",
            "resources_opponent": "resources_opponent",
            "risk_level": "risk_level",
            "cooperation_score": "cooperation_score",
            "stability": "stability",
            "last_action_player": "last_action_player",
            "last_action_opponent": "last_action_opponent",
            "last_outcome": "last_outcome",
            "briefing": "briefing",
            "is_finished": "is_finished",
            "ending_type": "ending_type",
            "scenario_name": "scenario_name",
            "custom_persona": "custom_persona",
            # Surplus mechanics
            "cooperation_surplus": "cooperation_surplus",
            "surplus_captured_player": "surplus_captured_player",
            "surplus_captured_opponent": "surplus_captured_opponent",
            "cooperation_streak": "cooperation_streak",
        }
        for key, attr in field_map.items():
            if key in value:
                setattr(self, attr, value[key])

        if "vp_player" in value:
            self.final_vp_player = value["vp_player"]
        if "vp_opponent" in value:
            self.final_vp_opponent = value["vp_opponent"]

    # Keep state setter for backward compatibility
    @state.setter
    def state(self, value: dict[str, Any]) -> None:
        """Set game state from dictionary."""
        self.update_from_state(value)

    def __repr__(self) -> str:
        return f"<GameRecord {self.game_id} turn={self.turn}>"
