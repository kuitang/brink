"""Mock game engine for UI development."""

import random
import time
from typing import Any


class MockGameEngine:
    """Mock implementation of game engine for UI development."""

    SCENARIOS = [
        {
            "id": "cuban-missile-crisis",
            "name": "Cuban Missile Crisis",
            "setting": "Cold War, 1962",
            "max_turns": 14,
            "description": "Soviet missiles in Cuba trigger a superpower standoff.",
        },
        {
            "id": "corporate-takeover",
            "name": "Hostile Takeover",
            "setting": "Corporate Boardroom, Present Day",
            "max_turns": 12,
            "description": "A rival corporation attempts a hostile acquisition.",
        },
        {
            "id": "succession-crisis",
            "name": "The Succession Crisis",
            "setting": "Medieval Kingdom, 1200s",
            "max_turns": 16,
            "description": "Two claimants vie for the throne after the king's death.",
        },
    ]

    OPPONENT_TYPES = [
        # Algorithmic opponents
        {
            "id": "tit_for_tat",
            "name": "Tit-for-Tat",
            "category": "algorithmic",
            "description": "Cooperates first, then mirrors your last action.",
        },
        {
            "id": "nash_calculator",
            "name": "Nash Calculator",
            "category": "algorithmic",
            "description": "Plays game-theoretic optimal strategy with risk awareness.",
        },
        {
            "id": "security_seeker",
            "name": "Security Seeker",
            "category": "algorithmic",
            "description": "Defaults to cooperation; escalates only defensively.",
        },
        {
            "id": "opportunist",
            "name": "Opportunist",
            "category": "algorithmic",
            "description": "Probes for weakness and exploits when opponent appears weak.",
        },
        {
            "id": "grim_trigger",
            "name": "Grim Trigger",
            "category": "algorithmic",
            "description": "Cooperates until betrayed, then defects forever.",
        },
        {
            "id": "erratic",
            "name": "Erratic",
            "category": "algorithmic",
            "description": "Unpredictable: 60% competitive, 40% cooperative.",
        },
        # Historical Political
        {
            "id": "bismarck",
            "name": "Otto von Bismarck",
            "category": "historical_political",
            "description": "Master of realpolitik. Seeks advantageous settlements through calculated pressure.",
        },
        {
            "id": "richelieu",
            "name": "Cardinal Richelieu",
            "category": "historical_political",
            "description": "Patient schemer. Builds coalitions while undermining rivals.",
        },
        {
            "id": "metternich",
            "name": "Prince Metternich",
            "category": "historical_political",
            "description": "Architect of balance. Prefers stability over dramatic gains.",
        },
        # Cold War
        {
            "id": "khrushchev",
            "name": "Nikita Khrushchev",
            "category": "historical_cold_war",
            "description": "Mercurial Soviet leader. Alternates bluster and pragmatism.",
        },
        {
            "id": "kissinger",
            "name": "Henry Kissinger",
            "category": "historical_cold_war",
            "description": "Strategic realist. Pursues détente while maintaining leverage.",
        },
        {
            "id": "nixon",
            "name": "Richard Nixon",
            "category": "historical_cold_war",
            "description": "Unpredictable strategist. Uses madman theory for advantage.",
        },
        # Corporate
        {
            "id": "carl_icahn",
            "name": "Carl Icahn",
            "category": "historical_corporate",
            "description": "Corporate raider. Aggressive pressure for maximum extraction.",
        },
        {
            "id": "warren_buffett",
            "name": "Warren Buffett",
            "category": "historical_corporate",
            "description": "Patient value investor. Seeks win-win through fair dealing.",
        },
        # Palace Intrigue
        {
            "id": "empress_wu",
            "name": "Empress Wu Zetian",
            "category": "historical_palace",
            "description": "Ruthless climber. Eliminates threats while appearing virtuous.",
        },
        {
            "id": "livia",
            "name": "Livia Drusilla",
            "category": "historical_palace",
            "description": "Shadow power. Achieves goals through influence over others.",
        },
        # Custom persona option
        {
            "id": "custom",
            "name": "Custom Persona",
            "category": "custom",
            "description": "Describe any historical or fictional figure for AI-powered gameplay.",
        },
    ]

    ACTIONS = {
        "low_risk": [
            {"id": "deescalate", "name": "De-escalate", "type": "cooperative", "cost": 0},
            {"id": "hold", "name": "Hold Position", "type": "cooperative", "cost": 0},
            {"id": "probe", "name": "Probe", "type": "competitive", "cost": 0.5},
            {"id": "pressure", "name": "Apply Pressure", "type": "competitive", "cost": 0.3},
        ],
        "high_risk": [
            {"id": "concede", "name": "Concede", "type": "cooperative", "cost": 0},
            {"id": "propose", "name": "Propose Settlement", "type": "cooperative", "cost": 0},
            {"id": "escalate", "name": "Escalate", "type": "competitive", "cost": 0.5},
            {"id": "ultimatum", "name": "Issue Ultimatum", "type": "competitive", "cost": 1.0},
        ],
    }

    def create_game(
        self, scenario_id: str, opponent_type: str, user_id: int
    ) -> dict[str, Any]:
        """Create a new game with initial state."""
        scenario = next(
            (s for s in self.SCENARIOS if s["id"] == scenario_id),
            self.SCENARIOS[0],
        )

        return {
            "scenario_id": scenario_id,
            "scenario_name": scenario["name"],
            "opponent_type": opponent_type,
            "turn": 1,
            "max_turns": scenario["max_turns"],
            "position_player": 5.0,
            "position_opponent": 5.0,
            "resources_player": 5.0,
            "resources_opponent": 5.0,
            "risk_level": 2,
            "cooperation_score": 5,
            "stability": 5,
            "last_action_player": None,
            "last_action_opponent": None,
            "history": [],
            "briefing": self._get_briefing(scenario_id, 1),
            "last_outcome": None,
            "is_finished": False,
        }

    def get_scenarios(self) -> list[dict[str, Any]]:
        """Get available scenarios."""
        return self.SCENARIOS

    def get_opponent_types(self) -> list[dict[str, Any]]:
        """Get available opponent types."""
        return self.OPPONENT_TYPES

    def get_available_actions(self, state: dict[str, Any]) -> list[dict[str, Any]]:
        """Get actions available in current state."""
        if state.get("risk_level", 0) >= 6:
            return self.ACTIONS["high_risk"]
        return self.ACTIONS["low_risk"]

    def submit_action(self, state: dict[str, Any], action_id: str) -> dict[str, Any]:
        """Process player action and return updated state."""
        # Simulate thinking delay
        time.sleep(0.5)

        # Find action
        all_actions = self.ACTIONS["low_risk"] + self.ACTIONS["high_risk"]
        action = next((a for a in all_actions if a["id"] == action_id), all_actions[0])

        # Simulate opponent response
        opponent_cooperative = random.random() > 0.4  # 60% cooperative

        # Update state
        new_state = state.copy()
        new_state["turn"] = state["turn"] + 1
        new_state["last_action_player"] = action["id"]
        new_state["last_action_opponent"] = "cooperate" if opponent_cooperative else "defect"

        # Position changes
        player_coop = action["type"] == "cooperative"
        if player_coop and opponent_cooperative:
            # Mutual cooperation
            new_state["position_player"] += 0.5
            new_state["position_opponent"] += 0.5
            new_state["cooperation_score"] = min(10, state["cooperation_score"] + 1)
            new_state["risk_level"] = max(0, state["risk_level"] - 0.5)
            outcome = "Mutual cooperation. Tensions ease."
        elif player_coop and not opponent_cooperative:
            # Player exploited
            new_state["position_player"] -= 1.0
            new_state["position_opponent"] += 1.0
            new_state["risk_level"] = min(10, state["risk_level"] + 0.5)
            outcome = "Your opponent pressed their advantage while you sought peace."
        elif not player_coop and opponent_cooperative:
            # Opponent exploited
            new_state["position_player"] += 1.0
            new_state["position_opponent"] -= 1.0
            new_state["risk_level"] = min(10, state["risk_level"] + 0.5)
            outcome = "Your aggressive move caught them off guard."
        else:
            # Mutual defection
            new_state["position_player"] -= 0.3
            new_state["position_opponent"] -= 0.3
            new_state["resources_player"] = max(0, state["resources_player"] - 0.5)
            new_state["resources_opponent"] = max(0, state["resources_opponent"] - 0.5)
            new_state["cooperation_score"] = max(0, state["cooperation_score"] - 1)
            new_state["risk_level"] = min(10, state["risk_level"] + 1.0)
            outcome = "Both sides escalated. The situation grows more dangerous."

        # Deduct action cost
        new_state["resources_player"] = max(
            0, new_state["resources_player"] - action["cost"]
        )

        # Update history
        player_symbol = "C" if player_coop else "D"
        opp_symbol = "C" if opponent_cooperative else "D"
        new_state["history"] = state.get("history", []) + [
            {"turn": state["turn"], "player": player_symbol, "opponent": opp_symbol}
        ]

        new_state["last_outcome"] = outcome
        new_state["briefing"] = self._get_briefing(
            state["scenario_id"], new_state["turn"]
        )

        # Check endings
        if new_state["risk_level"] >= 10:
            new_state["is_finished"] = True
            new_state["ending_type"] = "mutual_destruction"
            new_state["vp_player"] = 20
            new_state["vp_opponent"] = 20
        elif new_state["position_player"] <= 0:
            new_state["is_finished"] = True
            new_state["ending_type"] = "player_eliminated"
            new_state["vp_player"] = 10
            new_state["vp_opponent"] = 90
        elif new_state["position_opponent"] <= 0:
            new_state["is_finished"] = True
            new_state["ending_type"] = "opponent_eliminated"
            new_state["vp_player"] = 90
            new_state["vp_opponent"] = 10
        elif new_state["turn"] > state.get("max_turns", 14):
            new_state["is_finished"] = True
            new_state["ending_type"] = "natural"
            # Calculate VP from position
            total = new_state["position_player"] + new_state["position_opponent"]
            if total > 0:
                new_state["vp_player"] = int(
                    (new_state["position_player"] / total) * 100
                )
            else:
                new_state["vp_player"] = 50
            new_state["vp_opponent"] = 100 - new_state["vp_player"]

        return new_state

    def _get_briefing(self, scenario_id: str, turn: int) -> str:
        """Get narrative briefing for current turn."""
        briefings = {
            "cuban-missile-crisis": [
                "U-2 reconnaissance photographs reveal Soviet missile installations in Cuba.",
                "ExComm convenes. The President demands options.",
                "Naval quarantine of Cuba begins. Soviet ships approach.",
                "Tensions mount as the world holds its breath.",
                "Back-channel communications suggest a possible resolution.",
            ],
            "corporate-takeover": [
                "A rival corporation has announced a hostile tender offer.",
                "Your board meets in emergency session.",
                "Proxy fight for shareholder votes intensifies.",
                "Regulatory agencies take notice of the conflict.",
                "Negotiations for a potential settlement begin.",
            ],
            "succession-crisis": [
                "The old king is dead. You and your rival both claim the throne.",
                "Noble houses begin choosing sides.",
                "Armies gather on the borders of your respective territories.",
                "Emissaries arrive with proposals for partition.",
                "The decisive moment approaches.",
            ],
        }

        scenario_briefings = briefings.get(scenario_id, briefings["cuban-missile-crisis"])
        index = min(turn - 1, len(scenario_briefings) - 1)
        return scenario_briefings[index]
