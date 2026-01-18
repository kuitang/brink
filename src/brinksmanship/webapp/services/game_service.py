"""Game service - abstraction over mock/real engine."""

from typing import Any, Protocol, Union

from flask import current_app

from .mock_engine import MockGameEngine


class GameEngineProtocol(Protocol):
    """Protocol defining the game engine interface."""

    def create_game(
        self, scenario_id: str, opponent_type: str, user_id: int
    ) -> dict[str, Any]: ...

    def get_scenarios(self) -> list[dict[str, Any]]: ...

    def get_opponent_types(self) -> list[dict[str, Any]]: ...

    def get_available_actions(self, state: dict[str, Any]) -> list[dict[str, Any]]: ...

    def submit_action(self, state: dict[str, Any], action_id: str) -> dict[str, Any]: ...


_mock_engine: MockGameEngine | None = None
_real_engine: Any = None


def get_game_service() -> GameEngineProtocol:
    """Get the game service (mock or real based on config).

    Uses USE_MOCK_ENGINE config to determine which engine to use.
    Default is True (mock engine) for development.
    """
    global _mock_engine, _real_engine

    use_mock = True
    try:
        use_mock = current_app.config.get("USE_MOCK_ENGINE", True)
    except RuntimeError:
        # Outside of application context
        pass

    if use_mock:
        if _mock_engine is None:
            _mock_engine = MockGameEngine()
        return _mock_engine
    else:
        if _real_engine is None:
            from .engine_adapter import RealGameEngine
            _real_engine = RealGameEngine()
        return _real_engine
