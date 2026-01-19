"""Engine adapter - wraps GameEngine for webapp use.

This adapter provides a stateless interface to the game engine.
Game state is stored in the database, and engines are created
on-demand from the scenario and synced with stored state.
"""

import asyncio
import inspect
import random
from typing import Any, Optional


def _run_opponent_method(method, *args, **kwargs):
    """Run an opponent method, handling both sync and async implementations.

    Since Flask is sync, we use asyncio.run() for async methods.
    This must be called from a non-async context (standard Flask request handler).
    """
    if inspect.iscoroutinefunction(method):
        return asyncio.run(method(*args, **kwargs))
    return method(*args, **kwargs)

from brinksmanship.engine import GameEngine, create_game
from brinksmanship.models.actions import Action, ActionCategory, ActionType, get_action_by_name
from brinksmanship.opponents import Opponent, get_opponent_by_type, list_opponent_types as _list_opponent_types
from brinksmanship.opponents.historical import PERSONA_DISPLAY_NAMES
from brinksmanship.opponents.persona_generator import create_opponent_from_persona
from brinksmanship.storage import get_scenario_repository


class RealGameEngine:
    """Stateless adapter that wraps GameEngine for webapp use.

    Each operation creates a fresh engine from the scenario and
    syncs it with the stored game state. This eliminates the need
    for in-memory caching and makes the webapp properly stateless.
    """

    def __init__(self) -> None:
        """Initialize the adapter."""
        self._scenario_repo = get_scenario_repository()

    def create_game(
        self,
        scenario_id: str,
        opponent_type: str,
        user_id: int,
        game_id: Optional[str] = None,
        custom_persona: Optional[str] = None,
        player_is_a: bool = True,
    ) -> dict[str, Any]:
        """Create a new game with initial state.

        Args:
            scenario_id: ID of the scenario to play
            opponent_type: Type of opponent AI
            user_id: User ID
            game_id: Optional custom game ID
            custom_persona: Custom persona description (if opponent_type is "custom")
            player_is_a: Whether the human player is Player A (default True)

        Returns:
            Game state dict to be stored in database
        """
        engine = create_game(scenario_id, self._scenario_repo)

        if not game_id:
            game_id = f"{user_id}_{scenario_id}_{random.randint(10000, 99999)}"

        scenario = self._scenario_repo.get_scenario(scenario_id)
        scenario_name = scenario.get("name", scenario_id) if scenario else scenario_id

        # Get positions/resources based on which side the player is
        if player_is_a:
            player_position = engine.state.position_a
            player_resources = engine.state.resources_a
            opponent_position = engine.state.position_b
            opponent_resources = engine.state.resources_b
        else:
            player_position = engine.state.position_b
            player_resources = engine.state.resources_b
            opponent_position = engine.state.position_a
            opponent_resources = engine.state.resources_a

        return {
            "game_id": game_id,
            "scenario_id": scenario_id,
            "scenario_name": scenario_name,
            "opponent_type": opponent_type,
            "custom_persona": custom_persona,
            "player_is_a": player_is_a,  # Track which side the player is
            "turn": engine.state.turn,
            "max_turns": engine.state.max_turns,
            "position_player": player_position,
            "position_opponent": opponent_position,
            "resources_player": player_resources,
            "resources_opponent": opponent_resources,
            "risk_level": engine.state.risk_level,
            "cooperation_score": int(engine.state.cooperation_score),
            "stability": int(engine.state.stability),
            "briefing": engine.get_briefing(),
            "history": [],
            "is_finished": False,
        }

    def get_scenarios(self) -> list[dict[str, Any]]:
        """Get available scenarios with role information."""
        scenarios = self._scenario_repo.list_scenarios()
        return [
            {
                "id": s.get("id", s.get("scenario_id", "")),
                "name": s.get("name", ""),
                "setting": s.get("setting", ""),
                "max_turns": s.get("max_turns", 14),
                "description": s.get("description", ""),
                # Role information for side selection
                "player_a_name": s.get("player_a_name", "Player A"),
                "player_a_role": s.get("player_a_role", "Side A"),
                "player_b_name": s.get("player_b_name", "Player B"),
                "player_b_role": s.get("player_b_role", "Side B"),
            }
            for s in scenarios
        ]

    def get_opponent_types(self) -> list[dict[str, Any]]:
        """Get available opponent types."""
        types_by_category = _list_opponent_types()
        result = []

        descriptions = {
            "nash_calculator": "Plays game-theoretic optimal strategy.",
            "security_seeker": "Defaults to cooperation; escalates defensively.",
            "opportunist": "Probes for weakness and exploits.",
            "erratic": "Unpredictable: 60% competitive, 40% cooperative.",
            "tit_for_tat": "Cooperates first, then mirrors your last action.",
            "grim_trigger": "Cooperates until betrayed, then defects forever.",
            "bismarck": "Master of realpolitik. Calculated pressure.",
            "richelieu": "Patient schemer. Builds coalitions.",
            "metternich": "Architect of balance. Prefers stability.",
            "pericles": "Democratic leader balancing opinion with strategy.",
            "nixon": "Unpredictable strategist. Madman theory.",
            "kissinger": "Strategic realist. Pursues detente.",
            "khrushchev": "Mercurial. Alternates bluster and pragmatism.",
            "tito": "Balances superpowers. Master of non-alignment.",
            "kekkonen": "Finlandization expert. Careful accommodation.",
            "lee_kuan_yew": "Pragmatic authoritarian. Long-term thinking.",
            "gates": "Aggressive competitor. Technical leverage.",
            "jobs": "Visionary perfectionist. Reality distortion.",
            "icahn": "Corporate raider. Maximum extraction.",
            "zuckerberg": "Move fast. Acquire or eliminate.",
            "buffett": "Patient investor. Fair dealing.",
            "theodora": "Rose from nothing. Unflinching in crisis.",
            "wu_zetian": "Ruthless climber. Appears virtuous.",
            "cixi": "Plays factions against each other.",
            "livia": "Shadow power through influence.",
        }

        category_map = {
            "deterministic": "algorithmic",
            "historical_political": "historical_political",
            "historical_cold_war": "historical_cold_war",
            "historical_corporate": "historical_corporate",
            "historical_palace": "historical_palace",
        }

        for category, types in types_by_category.items():
            for type_id in types:
                display_name = PERSONA_DISPLAY_NAMES.get(type_id, type_id.replace("_", " ").title())
                result.append({
                    "id": type_id,
                    "name": display_name,
                    "category": category_map.get(category, category),
                    "description": descriptions.get(type_id, ""),
                })

        result.append({
            "id": "custom",
            "name": "Custom Persona",
            "category": "custom",
            "description": "Describe any figure for AI-powered gameplay.",
        })

        return result

    def get_available_actions(self, state: dict[str, Any]) -> list[dict[str, Any]]:
        """Get actions available in current state.

        Creates engine from scenario and syncs to stored state.
        """
        engine = self._create_engine_from_state(state)
        player_side = "A" if state.get("player_is_a", True) else "B"
        actions = engine.get_available_actions(player_side)
        return [self._format_action(a) for a in actions]

    def submit_action(self, state: dict[str, Any], action_id: str) -> dict[str, Any]:
        """Process player action and return updated state.

        Creates engine from scenario, syncs state, processes action,
        and returns new state to be saved to database.
        """
        engine = self._create_engine_from_state(state)
        opponent = self._create_opponent(state)

        # Determine which side is which
        player_is_a = state.get("player_is_a", True)
        player_side = "A" if player_is_a else "B"
        opponent_side = "B" if player_is_a else "A"

        # Find player's action
        player_actions = engine.get_available_actions(player_side)
        player_action = self._match_action(action_id, player_actions)
        if not player_action:
            raise ValueError(f"Invalid action: {action_id}")

        # Get opponent's choice (async method, run in sync context)
        opponent_actions = engine.get_available_actions(opponent_side)
        opponent_action = _run_opponent_method(
            opponent.choose_action, engine.state, opponent_actions
        )

        # Submit actions in correct order (action_a, action_b)
        if player_is_a:
            result = engine.submit_actions(player_action, opponent_action)
        else:
            result = engine.submit_actions(opponent_action, player_action)

        if result.action_result:
            opponent.receive_result(result.action_result)

        # Build updated state
        gs = engine.state
        player_symbol = "C" if player_action.action_type == ActionType.COOPERATIVE else "D"
        opponent_symbol = "C" if opponent_action.action_type == ActionType.COOPERATIVE else "D"

        # Get positions/resources based on which side the player is
        if player_is_a:
            player_position = gs.position_a
            player_resources = gs.resources_a
            opponent_position = gs.position_b
            opponent_resources = gs.resources_b
        else:
            player_position = gs.position_b
            player_resources = gs.resources_b
            opponent_position = gs.position_a
            opponent_resources = gs.resources_a

        # Maintain history in state dict
        history = list(state.get("history", []))
        history.append({
            "turn": state.get("turn", 1),
            "player": player_symbol,
            "opponent": opponent_symbol,
        })

        new_state = {
            "game_id": state.get("game_id"),
            "scenario_id": state.get("scenario_id"),
            "scenario_name": state.get("scenario_name"),
            "opponent_type": state.get("opponent_type"),
            "custom_persona": state.get("custom_persona"),
            "player_is_a": player_is_a,
            "turn": gs.turn,
            "max_turns": gs.max_turns,
            "position_player": player_position,
            "position_opponent": opponent_position,
            "resources_player": player_resources,
            "resources_opponent": opponent_resources,
            "risk_level": gs.risk_level,
            "cooperation_score": int(gs.cooperation_score),
            "stability": int(gs.stability),
            "last_action_player": action_id,
            "last_action_opponent": opponent_symbol,
            "last_outcome": result.narrative,
            "briefing": engine.get_briefing(),
            "history": history,
            # Turn info for GameRecord.add_turn()
            "new_turn_player": player_symbol,
            "new_turn_opponent": opponent_symbol,
            "new_turn_number": state.get("turn", 1),
            "is_finished": result.ending is not None,
        }

        if result.ending:
            new_state["ending_type"] = result.ending.ending_type.value
            # VPs are relative to player A and B, need to map correctly
            if player_is_a:
                new_state["vp_player"] = int(result.ending.vp_a)
                new_state["vp_opponent"] = int(result.ending.vp_b)
            else:
                new_state["vp_player"] = int(result.ending.vp_b)
                new_state["vp_opponent"] = int(result.ending.vp_a)

        return new_state

    def _create_engine_from_state(self, state: dict[str, Any]) -> GameEngine:
        """Create a fresh engine and sync it to stored state."""
        scenario_id = state.get("scenario_id")
        if not scenario_id:
            raise ValueError("No scenario_id in state")

        engine = create_game(scenario_id, self._scenario_repo)

        # Sync engine state to stored values
        saved_turn = state.get("turn", 1)
        engine.state.turn = saved_turn
        engine._current_turn_key = f"turn_{saved_turn}"

        # Map player/opponent positions back to A/B based on which side player is
        player_is_a = state.get("player_is_a", True)
        if player_is_a:
            engine.state.player_a.position = state.get("position_player", 5.0)
            engine.state.player_b.position = state.get("position_opponent", 5.0)
            engine.state.player_a.resources = state.get("resources_player", 5.0)
            engine.state.player_b.resources = state.get("resources_opponent", 5.0)
        else:
            engine.state.player_b.position = state.get("position_player", 5.0)
            engine.state.player_a.position = state.get("position_opponent", 5.0)
            engine.state.player_b.resources = state.get("resources_player", 5.0)
            engine.state.player_a.resources = state.get("resources_opponent", 5.0)

        engine.state.risk_level = state.get("risk_level", 2.0)
        engine.state.cooperation_score = float(state.get("cooperation_score", 5))
        engine.state.stability = float(state.get("stability", 5))

        return engine

    def _create_opponent(self, state: dict[str, Any]) -> Opponent:
        """Create opponent instance from state with role information."""
        opponent_type = state.get("opponent_type", "tit_for_tat")
        custom_persona = state.get("custom_persona")
        player_is_a = state.get("player_is_a", True)

        if opponent_type == "custom" and custom_persona:
            return create_opponent_from_persona(custom_persona)

        # Get scenario role information for the opponent's side
        scenario_id = state.get("scenario_id")
        role_name = None
        role_description = None

        if scenario_id:
            scenario = self._scenario_repo.get_scenario(scenario_id)
            if scenario:
                if player_is_a:
                    # Player is A, opponent is B
                    role_name = scenario.get("player_b_role")
                    role_description = scenario.get("player_b_description")
                else:
                    # Player is B, opponent is A
                    role_name = scenario.get("player_a_role")
                    role_description = scenario.get("player_a_description")

        return get_opponent_by_type(
            opponent_type,
            is_player_a=not player_is_a,  # Opponent is opposite of player
            role_name=role_name,
            role_description=role_description,
        )

    def _match_action(self, action_id: str, available: list[Action]) -> Optional[Action]:
        """Find action matching the ID."""
        action_id_lower = action_id.lower().replace("-", "").replace(" ", "_")

        for a in available:
            # Match by converting name to id format
            name_as_id = a.name.lower().replace("-", "").replace(" ", "_").replace(",", "")
            if name_as_id == action_id_lower:
                return a

        # Try action registry
        action = get_action_by_name(action_id)
        if action:
            return action

        # Match by type as fallback
        cooperative_ids = {"hold", "deescalate", "concede", "propose"}
        is_cooperative = action_id.lower() in cooperative_ids
        for a in available:
            if (is_cooperative and a.action_type == ActionType.COOPERATIVE) or \
               (not is_cooperative and a.action_type == ActionType.COMPETITIVE):
                return a

        return None

    # Mechanics hints by category (cooperative actions)
    _COOPERATIVE_HINTS = {
        ActionCategory.SETTLEMENT: "Proposes negotiated end to crisis",
        ActionCategory.RECONNAISSANCE: "Learn opponent's Position",
        ActionCategory.INSPECTION: "Learn opponent's Resources",
        ActionCategory.COSTLY_SIGNALING: "Reveal your strength credibly",
    }
    _DEFAULT_COOPERATIVE_HINT = "Builds trust & stability"
    _COMPETITIVE_HINT = "May gain position, increases risk"

    def _format_action(self, a: Action) -> dict[str, Any]:
        """Format an Action for webapp display."""
        is_coop = a.action_type == ActionType.COOPERATIVE
        mechanics_hint = (
            self._COOPERATIVE_HINTS.get(a.category, self._DEFAULT_COOPERATIVE_HINT)
            if is_coop else self._COMPETITIVE_HINT
        )

        return {
            "id": a.name.lower().replace("-", "").replace(" ", "_").replace(",", ""),
            "name": a.name,
            "type": "cooperative" if is_coop else "competitive",
            "cost": a.resource_cost,
            "description": a.description,
            "mechanics_hint": mechanics_hint,
        }
