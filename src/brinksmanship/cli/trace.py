"""Game trace logging for Brinksmanship CLI.

Records all game events for debugging and analysis:
- Player and opponent actions
- State changes
- Settlement attempts
- Game outcomes
"""

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class StateSnapshot:
    """Snapshot of game state at a point in time."""

    turn: int
    act: int
    risk_level: float
    cooperation_score: float
    stability: float
    position_a: float
    position_b: float
    resources_a: float
    resources_b: float


@dataclass
class ActionRecord:
    """Record of an action taken."""

    player: str  # "human" or "opponent"
    action_name: str
    action_type: str  # "cooperative" or "competitive"
    action_category: str  # "standard", "settlement", etc.
    resource_cost: float


@dataclass
class TurnRecord:
    """Record of a complete turn."""

    turn_number: int
    state_before: StateSnapshot
    human_action: ActionRecord
    opponent_action: ActionRecord
    outcome_code: str
    narrative: str
    state_after: StateSnapshot
    state_deltas: dict[str, float] = field(default_factory=dict)


@dataclass
class GameTrace:
    """Complete trace of a game session."""

    game_id: str
    scenario_id: str
    opponent_type: str
    human_player: str  # "A" or "B"
    start_time: str
    end_time: str | None = None
    turns: list[TurnRecord] = field(default_factory=list)
    ending: dict[str, Any] | None = None
    settlement_attempts: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "game_id": self.game_id,
            "scenario_id": self.scenario_id,
            "opponent_type": self.opponent_type,
            "human_player": self.human_player,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "turns": [asdict(t) for t in self.turns],
            "ending": self.ending,
            "settlement_attempts": self.settlement_attempts,
        }


class TraceLogger:
    """Logger for game trace events."""

    def __init__(
        self,
        scenario_id: str,
        opponent_type: str,
        human_player: str = "A",
        output_dir: Path | None = None,
    ):
        """Initialize trace logger.

        Args:
            scenario_id: ID of the scenario being played
            opponent_type: Type of opponent (e.g., "bismarck", "nash")
            human_player: Which side the human is playing ("A" or "B")
            output_dir: Directory for trace files (default: ./traces)
        """
        self.output_dir = output_dir or Path("traces")
        self.output_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        game_id = f"{scenario_id}_{opponent_type}_{timestamp}"

        self.trace = GameTrace(
            game_id=game_id,
            scenario_id=scenario_id,
            opponent_type=opponent_type,
            human_player=human_player,
            start_time=datetime.now().isoformat(),
        )

        self._current_state_before: StateSnapshot | None = None
        self._output_file = self.output_dir / f"{game_id}.json"

    def capture_state(self, state) -> StateSnapshot:
        """Capture a snapshot of the current game state.

        Args:
            state: GameState object from the engine

        Returns:
            StateSnapshot for the trace
        """
        return StateSnapshot(
            turn=state.turn,
            act=state.act,
            risk_level=state.risk_level,
            cooperation_score=state.cooperation_score,
            stability=state.stability,
            position_a=state.position_a,
            position_b=state.position_b,
            resources_a=state.resources_a,
            resources_b=state.resources_b,
        )

    def start_turn(self, state) -> None:
        """Record the state at the start of a turn.

        Args:
            state: GameState object from the engine
        """
        self._current_state_before = self.capture_state(state)

    def record_turn(
        self,
        human_action,
        opponent_action,
        result,
        state_after,
        human_is_player_a: bool = True,
    ) -> None:
        """Record a complete turn.

        Args:
            human_action: Action object for human's choice
            opponent_action: Action object for opponent's choice
            result: TurnResult from the engine
            state_after: GameState after the turn
            human_is_player_a: Whether human is player A
        """
        if self._current_state_before is None:
            return

        state_after_snapshot = self.capture_state(state_after)

        # Calculate deltas
        deltas = {
            "risk_delta": state_after_snapshot.risk_level - self._current_state_before.risk_level,
            "coop_delta": state_after_snapshot.cooperation_score - self._current_state_before.cooperation_score,
            "stability_delta": state_after_snapshot.stability - self._current_state_before.stability,
            "position_a_delta": state_after_snapshot.position_a - self._current_state_before.position_a,
            "position_b_delta": state_after_snapshot.position_b - self._current_state_before.position_b,
            "resources_a_delta": state_after_snapshot.resources_a - self._current_state_before.resources_a,
            "resources_b_delta": state_after_snapshot.resources_b - self._current_state_before.resources_b,
        }

        human_record = ActionRecord(
            player="human",
            action_name=human_action.name,
            action_type=human_action.action_type.value,
            action_category=human_action.category.value,
            resource_cost=human_action.resource_cost,
        )

        opponent_record = ActionRecord(
            player="opponent",
            action_name=opponent_action.name,
            action_type=opponent_action.action_type.value,
            action_category=opponent_action.category.value,
            resource_cost=opponent_action.resource_cost,
        )

        outcome_code = result.action_result.outcome_code if result.action_result else "UNKNOWN"

        turn_record = TurnRecord(
            turn_number=self._current_state_before.turn,
            state_before=self._current_state_before,
            human_action=human_record,
            opponent_action=opponent_record,
            outcome_code=outcome_code,
            narrative=result.narrative or "",
            state_after=state_after_snapshot,
            state_deltas=deltas,
        )

        self.trace.turns.append(turn_record)
        self._current_state_before = None

        # Auto-save after each turn
        self.save()

    def record_settlement_attempt(
        self,
        proposer: str,
        offered_vp: int,
        argument: str,
        response: str,
        counter_vp: int | None = None,
    ) -> None:
        """Record a settlement attempt.

        Args:
            proposer: "human" or "opponent"
            offered_vp: VP offered to proposer
            argument: Settlement argument
            response: "accept", "reject", or "counter"
            counter_vp: Counter-proposal VP if applicable
        """
        self.trace.settlement_attempts.append(
            {
                "turn": len(self.trace.turns) + 1,
                "proposer": proposer,
                "offered_vp": offered_vp,
                "argument": argument,
                "response": response,
                "counter_vp": counter_vp,
                "timestamp": datetime.now().isoformat(),
            }
        )
        self.save()

    def record_ending(
        self,
        ending_type: str,
        vp_a: float,
        vp_b: float,
        description: str,
    ) -> None:
        """Record the game ending.

        Args:
            ending_type: Type of ending (e.g., "settlement", "catastrophe")
            vp_a: Victory points for player A
            vp_b: Victory points for player B
            description: Ending description
        """
        self.trace.end_time = datetime.now().isoformat()
        self.trace.ending = {
            "type": ending_type,
            "vp_a": vp_a,
            "vp_b": vp_b,
            "description": description,
        }
        self.save()

    def save(self) -> Path:
        """Save the trace to a JSON file.

        Returns:
            Path to the saved file
        """
        with open(self._output_file, "w") as f:
            json.dump(self.trace.to_dict(), f, indent=2)
        return self._output_file

    def get_summary(self) -> str:
        """Get a human-readable summary of the trace.

        Returns:
            Summary string
        """
        lines = [
            f"Game: {self.trace.game_id}",
            f"Scenario: {self.trace.scenario_id}",
            f"Opponent: {self.trace.opponent_type}",
            f"Turns played: {len(self.trace.turns)}",
            "",
            "Turn History:",
        ]

        for turn in self.trace.turns:
            h_type = "C" if turn.human_action.action_type == "cooperative" else "D"
            o_type = "C" if turn.opponent_action.action_type == "cooperative" else "D"
            lines.append(
                f"  T{turn.turn_number}: "
                f"You={turn.human_action.action_name[:30]}({h_type}) "
                f"vs Opp={turn.opponent_action.action_name[:30]}({o_type}) "
                f"→ {turn.outcome_code}"
            )
            lines.append(
                f"         Δ Risk={turn.state_deltas.get('risk_delta', 0):+.1f}, "
                f"Δ Coop={turn.state_deltas.get('coop_delta', 0):+.1f}, "
                f"Δ Stab={turn.state_deltas.get('stability_delta', 0):+.1f}"
            )

        if self.trace.ending:
            lines.append("")
            lines.append(f"Ending: {self.trace.ending['type']}")
            lines.append(f"  VP A: {self.trace.ending['vp_a']:.1f}")
            lines.append(f"  VP B: {self.trace.ending['vp_b']:.1f}")

        lines.append("")
        lines.append(f"Trace saved to: {self._output_file}")

        return "\n".join(lines)
