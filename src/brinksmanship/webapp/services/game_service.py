"""Game service - wraps real game engine for webapp use."""

from typing import Any, Protocol

from .engine_adapter import RealGameEngine


class GameEngineProtocol(Protocol):
    """Protocol defining the game engine interface."""

    def create_game(
        self,
        scenario_id: str,
        opponent_type: str,
        user_id: int,
        game_id: str | None = None,
        custom_persona: str | None = None,
        player_is_a: bool = True,
    ) -> dict[str, Any]: ...

    def get_scenarios(self) -> list[dict[str, Any]]: ...

    def get_opponent_types(self) -> list[dict[str, Any]]: ...

    def get_available_actions(self, state: dict[str, Any]) -> list[dict[str, Any]]: ...

    def submit_action(self, state: dict[str, Any], action_id: str) -> dict[str, Any]: ...

    # Settlement methods
    def can_propose_settlement(self, state: dict[str, Any]) -> bool: ...

    def get_suggested_settlement_vp(self, state: dict[str, Any]) -> int: ...

    def evaluate_settlement(self, state: dict[str, Any], offered_vp: int, argument: str = "") -> dict[str, Any]: ...

    def check_opponent_settlement(self, state: dict[str, Any]) -> dict[str, Any] | None: ...

    def finalize_settlement(self, state: dict[str, Any], player_vp: int) -> dict[str, Any]: ...


_engine: RealGameEngine | None = None


def get_game_service() -> GameEngineProtocol:
    """Get the game service (real engine).

    Returns the singleton RealGameEngine instance that wraps the
    actual game engine with scenario-specific narrative actions.
    """
    global _engine

    if _engine is None:
        _engine = RealGameEngine()
    return _engine
