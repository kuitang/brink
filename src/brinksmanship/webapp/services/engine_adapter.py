"""Engine adapter - wraps real GameEngine for webapp use.

This adapter bridges the real game engine (which expects two players) with
the webapp's single-player vs AI interface. It maintains both engine and
opponent state and translates between formats.
"""

import pickle
import random
from typing import Any, Optional

from brinksmanship.engine import GameEngine, create_game, EndingType
from brinksmanship.models.actions import Action, ActionType, get_action_by_name
from brinksmanship.opponents import (
    Opponent,
    get_opponent_by_type,
    list_opponent_types as _list_opponent_types,
)
from brinksmanship.opponents.historical import PERSONA_DISPLAY_NAMES
from brinksmanship.opponents.persona_generator import create_opponent_from_persona
from brinksmanship.storage import get_scenario_repository


class RealGameEngine:
    """Adapter that wraps real GameEngine for single-player vs AI gameplay.

    The real engine expects simultaneous two-player actions. This adapter:
    1. Stores engine and opponent instances per game
    2. Gets opponent decision when player submits action
    3. Translates between engine state and webapp state dict format
    """

    def __init__(self) -> None:
        """Initialize the adapter."""
        self._scenario_repo = get_scenario_repository()
        # In-memory cache of active games (game_id -> (engine, opponent))
        # In production, these would be serialized to database
        self._active_games: dict[str, tuple[GameEngine, Opponent]] = {}

    def create_game(
        self,
        scenario_id: str,
        opponent_type: str,
        user_id: int,
        game_id: Optional[str] = None,
        custom_persona: Optional[str] = None,
    ) -> dict[str, Any]:
        """Create a new game with initial state.

        Args:
            scenario_id: ID of scenario to play
            opponent_type: Type of opponent (e.g., "tit_for_tat", "bismarck", "custom")
            user_id: ID of the player
            game_id: Optional game ID (generated if not provided)
            custom_persona: Description for custom persona (if opponent_type="custom")

        Returns:
            Game state dict in webapp format
        """
        # Create the game engine
        engine = create_game(scenario_id, self._scenario_repo)

        # Create the opponent
        if opponent_type == "custom" and custom_persona:
            # Generate custom persona from description
            opponent = create_opponent_from_persona(custom_persona)
        else:
            opponent = get_opponent_by_type(opponent_type)

        # Use provided game ID or generate unique one
        if not game_id:
            game_id = f"{user_id}_{scenario_id}_{random.randint(10000, 99999)}"

        # Store in cache
        self._active_games[game_id] = (engine, opponent)

        # Get scenario details
        scenario = self._scenario_repo.get_scenario(scenario_id)
        scenario_name = scenario.get("name", scenario_id) if scenario else scenario_id

        # Convert to webapp format
        state = self._engine_to_webapp_state(engine, scenario_id, scenario_name, opponent_type)
        state["game_id"] = game_id

        return state

    def get_game(self, game_id: str) -> Optional[dict[str, Any]]:
        """Get game state by ID.

        Args:
            game_id: Game identifier

        Returns:
            Game state dict or None if not found
        """
        if game_id not in self._active_games:
            return None

        engine, opponent = self._active_games[game_id]
        # Extract scenario info from game_id
        parts = game_id.split("_")
        scenario_id = parts[1] if len(parts) > 1 else "unknown"
        scenario = self._scenario_repo.get_scenario(scenario_id)
        scenario_name = scenario.get("name", scenario_id) if scenario else scenario_id
        opponent_type = getattr(opponent, "persona_name", opponent.__class__.__name__.lower())

        state = self._engine_to_webapp_state(engine, scenario_id, scenario_name, opponent_type)
        state["game_id"] = game_id

        return state

    def get_scenarios(self) -> list[dict[str, Any]]:
        """Get available scenarios.

        Returns:
            List of scenario metadata dicts
        """
        scenarios = self._scenario_repo.list_scenarios()
        return [
            {
                "id": s.get("id", s.get("scenario_id", "")),
                "name": s.get("name", ""),
                "setting": s.get("setting", ""),
                "max_turns": s.get("max_turns", 14),
                "description": s.get("description", ""),
            }
            for s in scenarios
        ]

    def get_opponent_types(self) -> list[dict[str, Any]]:
        """Get available opponent types with descriptions.

        Returns:
            List of opponent type dicts with id, name, category, description
        """
        types_by_category = _list_opponent_types()
        result = []

        # Descriptions for each opponent type
        descriptions = {
            # Deterministic
            "nash_calculator": "Plays game-theoretic optimal strategy with risk awareness.",
            "security_seeker": "Defaults to cooperation; escalates only defensively.",
            "opportunist": "Probes for weakness and exploits when opponent appears weak.",
            "erratic": "Unpredictable: 60% competitive, 40% cooperative.",
            "tit_for_tat": "Cooperates first, then mirrors your last action.",
            "grim_trigger": "Cooperates until betrayed, then defects forever.",
            # Historical Political
            "bismarck": "Master of realpolitik. Seeks advantageous settlements through calculated pressure.",
            "richelieu": "Patient schemer. Builds coalitions while undermining rivals.",
            "metternich": "Architect of balance. Prefers stability over dramatic gains.",
            "pericles": "Democratic leader balancing public opinion with strategic necessity.",
            # Cold War
            "nixon": "Unpredictable strategist. Uses madman theory for advantage.",
            "kissinger": "Strategic realist. Pursues détente while maintaining leverage.",
            "khrushchev": "Mercurial Soviet leader. Alternates bluster and pragmatism.",
            "tito": "Balances superpowers against each other. Master of non-alignment.",
            "kekkonen": "Finlandization expert. Preserves autonomy through careful accommodation.",
            "lee_kuan_yew": "Pragmatic authoritarian. Long-term thinking over short-term gains.",
            # Corporate
            "gates": "Aggressive competitor. Dominates through technical and business leverage.",
            "jobs": "Visionary perfectionist. Reality distortion field in negotiations.",
            "icahn": "Corporate raider. Aggressive pressure for maximum extraction.",
            "zuckerberg": "Move fast. Acquire or eliminate competition.",
            "buffett": "Patient value investor. Seeks win-win through fair dealing.",
            # Palace
            "theodora": "Empress who rose from nothing. Unflinching in crisis.",
            "wu_zetian": "Ruthless climber. Eliminates threats while appearing virtuous.",
            "cixi": "Dowager who controlled China. Plays factions against each other.",
            "livia": "Shadow power. Achieves goals through influence over others.",
        }

        category_map = {
            "deterministic": "algorithmic",
            "historical_political": "historical_political",
            "historical_cold_war": "historical_cold_war",
            "historical_corporate": "historical_corporate",
            "historical_palace": "historical_palace",
        }

        for category, types in types_by_category.items():
            webapp_category = category_map.get(category, category)
            for type_id in types:
                display_name = PERSONA_DISPLAY_NAMES.get(
                    type_id, type_id.replace("_", " ").title()
                )
                result.append({
                    "id": type_id,
                    "name": display_name,
                    "category": webapp_category,
                    "description": descriptions.get(type_id, ""),
                })

        # Add custom persona option
        result.append({
            "id": "custom",
            "name": "Custom Persona",
            "category": "custom",
            "description": "Describe any historical or fictional figure for AI-powered gameplay.",
        })

        return result

    def get_available_actions(self, state: dict[str, Any]) -> list[dict[str, Any]]:
        """Get actions available in current state.

        Args:
            state: Game state dict

        Returns:
            List of action dicts
        """
        game_id = state.get("game_id")
        if not game_id or game_id not in self._active_games:
            # Fall back to mock-style action generation
            return self._get_mock_actions(state)

        engine, _ = self._active_games[game_id]

        # Player is always "A" in webapp
        actions = engine.get_available_actions("A")

        return [
            {
                # Convert name to id format: "De-escalate" -> "deescalate"
                "id": a.name.lower().replace("-", "").replace(" ", "_"),
                "name": a.name,
                "type": "cooperative" if a.action_type == ActionType.COOPERATIVE else "competitive",
                "cost": a.resource_cost,
                "description": a.description,
            }
            for a in actions
        ]

    def submit_action(
        self, state: dict[str, Any], action_id: str
    ) -> dict[str, Any]:
        """Process player action and return updated state.

        Args:
            state: Current game state dict
            action_id: ID of the action to take

        Returns:
            Updated game state dict
        """
        game_id = state.get("game_id")
        if not game_id or game_id not in self._active_games:
            raise ValueError(f"Game not found: {game_id}")

        engine, opponent = self._active_games[game_id]

        # Get player's action
        # The webapp uses lowercase IDs (e.g., "deescalate") while
        # the engine uses Action objects with names (e.g., "De-escalate")
        player_actions = engine.get_available_actions("A")
        player_action = None

        # Try to match by converting name to id format
        for a in player_actions:
            # Convert "De-escalate" -> "deescalate" for comparison
            action_id_from_name = a.name.lower().replace("-", "").replace(" ", "_")
            if action_id_from_name == action_id.lower().replace("-", "").replace(" ", "_"):
                player_action = a
                break

        if not player_action:
            # Try to find by exact name lookup
            player_action = get_action_by_name(action_id)

        if not player_action and player_actions:
            # Last resort: match by action type from the id
            # "hold", "deescalate", "concede", "propose" -> cooperative
            # "probe", "pressure", "escalate", "ultimatum" -> competitive
            cooperative_ids = {"hold", "deescalate", "concede", "propose"}
            is_cooperative = action_id.lower() in cooperative_ids
            for a in player_actions:
                if (is_cooperative and a.action_type == ActionType.COOPERATIVE) or \
                   (not is_cooperative and a.action_type == ActionType.COMPETITIVE):
                    player_action = a
                    break

        if not player_action:
            raise ValueError(f"Invalid action: {action_id}")

        # Get opponent's action choice
        opponent_actions = engine.get_available_actions("B")
        opponent_action = opponent.choose_action(engine.state, opponent_actions)

        # Submit both actions to engine
        result = engine.submit_actions(player_action, opponent_action)

        # Notify opponent of result (for learning opponents)
        if result.action_result:
            opponent.receive_result(result.action_result)

        # Get updated state
        scenario_id = state.get("scenario_id", "unknown")
        scenario_name = state.get("scenario_name", "Unknown")
        opponent_type = state.get("opponent_type", "unknown")

        new_state = self._engine_to_webapp_state(
            engine, scenario_id, scenario_name, opponent_type
        )
        new_state["game_id"] = game_id
        new_state["last_action_player"] = action_id
        new_state["last_action_opponent"] = (
            "cooperate" if opponent_action.action_type == ActionType.COOPERATIVE else "defect"
        )
        new_state["last_outcome"] = result.narrative

        # Add history entry
        history = state.get("history", [])
        player_symbol = "C" if player_action.action_type == ActionType.COOPERATIVE else "D"
        opponent_symbol = "C" if opponent_action.action_type == ActionType.COOPERATIVE else "D"
        history.append({
            "turn": state.get("turn", 1),
            "player": player_symbol,
            "opponent": opponent_symbol,
        })
        new_state["history"] = history

        # Handle game ending
        if result.ending:
            new_state["is_finished"] = True
            new_state["ending_type"] = result.ending.ending_type.value
            new_state["vp_player"] = int(result.ending.vp_a)
            new_state["vp_opponent"] = int(result.ending.vp_b)
            new_state["ending_description"] = result.ending.description

            # Clean up from cache
            del self._active_games[game_id]

        return new_state

    def _engine_to_webapp_state(
        self,
        engine: GameEngine,
        scenario_id: str,
        scenario_name: str,
        opponent_type: str,
    ) -> dict[str, Any]:
        """Convert engine state to webapp state dict format.

        The webapp expects a flat dict with specific keys.
        The engine stores state in a nested GameState dataclass.
        """
        gs = engine.state

        return {
            "scenario_id": scenario_id,
            "scenario_name": scenario_name,
            "opponent_type": opponent_type,
            "turn": gs.turn,
            "max_turns": gs.max_turns,
            "position_player": gs.position_a,
            "position_opponent": gs.position_b,
            "resources_player": gs.resources_a,
            "resources_opponent": gs.resources_b,
            "risk_level": gs.risk_level,
            "cooperation_score": int(gs.cooperation_score),
            "stability": int(gs.stability),
            "last_action_player": None,
            "last_action_opponent": None,
            "history": [],
            "briefing": engine.get_briefing(),
            "last_outcome": None,
            "is_finished": engine.is_game_over(),
        }

    def _get_mock_actions(self, state: dict[str, Any]) -> list[dict[str, Any]]:
        """Fallback action generation when game not in cache.

        This is used when loading a game from database that hasn't been
        restored to the engine cache yet.
        """
        risk_level = state.get("risk_level", 0)

        if risk_level >= 6:
            return [
                {"id": "concede", "name": "Concede", "type": "cooperative", "cost": 0},
                {"id": "propose", "name": "Propose Settlement", "type": "cooperative", "cost": 0},
                {"id": "escalate", "name": "Escalate", "type": "competitive", "cost": 0.5},
                {"id": "ultimatum", "name": "Issue Ultimatum", "type": "competitive", "cost": 1.0},
            ]
        else:
            return [
                {"id": "deescalate", "name": "De-escalate", "type": "cooperative", "cost": 0},
                {"id": "hold", "name": "Hold Position", "type": "cooperative", "cost": 0},
                {"id": "probe", "name": "Probe", "type": "competitive", "cost": 0.5},
                {"id": "pressure", "name": "Apply Pressure", "type": "competitive", "cost": 0.3},
            ]

    def restore_game(
        self,
        game_id: str,
        state: dict[str, Any],
        engine_data: Optional[bytes] = None,
        opponent_data: Optional[bytes] = None,
    ) -> bool:
        """Restore a game from serialized state.

        Args:
            game_id: Game identifier
            state: Webapp state dict
            engine_data: Pickled engine state (if available)
            opponent_data: Pickled opponent state (if available)

        Returns:
            True if game was restored to active cache
        """
        if engine_data and opponent_data:
            try:
                engine = pickle.loads(engine_data)
                opponent = pickle.loads(opponent_data)
                self._active_games[game_id] = (engine, opponent)
                return True
            except Exception:
                pass

        # Cannot restore without serialized engine/opponent
        # The game can still be displayed but not continued
        return False

    def serialize_game(self, game_id: str) -> tuple[Optional[bytes], Optional[bytes]]:
        """Serialize game state for persistence.

        Args:
            game_id: Game identifier

        Returns:
            Tuple of (engine_bytes, opponent_bytes) or (None, None) if not found
        """
        if game_id not in self._active_games:
            return None, None

        engine, opponent = self._active_games[game_id]
        try:
            engine_data = pickle.dumps(engine)
            opponent_data = pickle.dumps(opponent)
            return engine_data, opponent_data
        except Exception:
            return None, None
