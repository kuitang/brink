"""Game record model for persisting game state."""

from datetime import datetime
from typing import Any

from ..extensions import db


class TurnHistory(db.Model):
    """Normalized turn history for a game."""

    __tablename__ = "turn_history"

    id = db.Column(db.Integer, primary_key=True)
    game_id = db.Column(db.Integer, db.ForeignKey("game_records.id"), nullable=False, index=True)
    turn = db.Column(db.Integer, nullable=False)
    player_action = db.Column(db.String(1), nullable=False)  # 'C' or 'D'
    opponent_action = db.Column(db.String(1), nullable=False)

    __table_args__ = (
        db.UniqueConstraint('game_id', 'turn', name='unique_game_turn'),
    )


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

    @property
    def history(self) -> list[dict[str, Any]]:
        """Get turn history as list of dicts."""
        return [
            {"turn": t.turn, "player": t.player_action, "opponent": t.opponent_action}
            for t in self.turns.all()
        ]

    def add_turn(self, turn: int, player: str, opponent: str) -> None:
        """Add a turn to history.

        Args:
            turn: Turn number
            player: 'C' for cooperative, 'D' for competitive
            opponent: 'C' for cooperative, 'D' for competitive
        """
        entry = TurnHistory(game_id=self.id, turn=turn, player_action=player, opponent_action=opponent)
        db.session.add(entry)

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
