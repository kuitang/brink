"""Game record model for persisting game state."""

import json
from datetime import datetime
from typing import Any

from ..extensions import db


class GameRecord(db.Model):
    """Persisted game state."""

    __tablename__ = "game_records"

    id = db.Column(db.Integer, primary_key=True)
    game_id = db.Column(db.String(64), unique=True, nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    scenario_id = db.Column(db.String(64), nullable=False)
    opponent_type = db.Column(db.String(64), nullable=False)
    state_json = db.Column(db.Text, nullable=False, default="{}")
    is_finished = db.Column(db.Boolean, default=False)
    ending_type = db.Column(db.String(32), nullable=True)
    final_vp_player = db.Column(db.Integer, nullable=True)
    final_vp_opponent = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    finished_at = db.Column(db.DateTime, nullable=True)

    @property
    def state(self) -> dict[str, Any]:
        """Get game state as dictionary."""
        return json.loads(self.state_json)

    @state.setter
    def state(self, value: dict[str, Any]) -> None:
        """Set game state from dictionary."""
        self.state_json = json.dumps(value)

    def __repr__(self) -> str:
        return f"<GameRecord {self.game_id}>"
