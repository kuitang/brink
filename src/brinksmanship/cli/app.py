"""Brinksmanship CLI Application.

A simple terminal interface for playing Brinksmanship using simple-term-menu.

Implements:
- Main menu
- Opponent selection
- Scenario selection
- Game screen with state, briefing, actions, history
- Settlement negotiation UI
- End-game results
"""

from __future__ import annotations

import asyncio
import os
import readline  # noqa: F401 - enables input() history
import sys
from typing import TYPE_CHECKING, Optional

from simple_term_menu import TerminalMenu

from brinksmanship.engine.game_engine import (
    EndingType,
    GameEnding,
    GameEngine,
    TurnResult,
    create_game,
)
from brinksmanship.models.actions import (
    Action,
    ActionCategory,
    ActionType,
)
from brinksmanship.models.state import GameState
from brinksmanship.opponents.base import (
    Opponent,
    SettlementProposal,
    SettlementResponse,
    get_opponent_by_type,
    list_opponent_types,
)
from brinksmanship.storage import get_scenario_repository
from brinksmanship.cli.trace import TraceLogger

if TYPE_CHECKING:
    pass


def clear_screen() -> None:
    """Clear the terminal screen."""
    os.system("cls" if os.name == "nt" else "clear")


def print_header(title: str) -> None:
    """Print a formatted header."""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60 + "\n")


def print_section(title: str) -> None:
    """Print a section header."""
    print(f"\n--- {title} ---\n")


def run_async(coro):
    """Run an async coroutine synchronously."""
    return asyncio.run(coro)


class BrinksmanshipCLI:
    """Main CLI application for Brinksmanship."""

    def __init__(self):
        self.repo = get_scenario_repository()
        self.game: Optional[GameEngine] = None
        self.opponent: Optional[Opponent] = None
        self.human_is_player_a: bool = True
        self.human_player: str = "A"
        self.opponent_player: str = "B"
        self.turn_history: list[str] = []
        self.trace_logger: Optional[TraceLogger] = None

    def run(self) -> None:
        """Run the main menu loop."""
        while True:
            clear_screen()
            print_header("BRINKSMANSHIP")
            print("A Game-Theoretic Strategy Simulation\n")

            menu = TerminalMenu(
                ["New Game", "Load Scenario", "Quit"],
                title="Main Menu",
            )
            choice = menu.show()

            if choice == 0 or choice == 1:  # New Game or Load Scenario
                self.scenario_select()
            elif choice == 2 or choice is None:  # Quit or Escape
                print("Goodbye!")
                break

    def scenario_select(self) -> None:
        """Select a scenario to play."""
        clear_screen()
        print_header("SELECT SCENARIO")

        scenarios = self.repo.list_scenarios()
        if not scenarios:
            print("No scenarios available.")
            input("Press Enter to continue...")
            return

        options = []
        for scenario in scenarios:
            name = scenario.get("name", scenario.get("id", "Unknown"))
            setting = scenario.get("setting", "")
            label = f"{name}" + (f" - {setting}" if setting else "")
            options.append(label)
        options.append("Back")

        menu = TerminalMenu(options, title="Choose a scenario:")
        choice = menu.show()

        if choice is None or choice == len(options) - 1:
            return

        scenario_id = scenarios[choice].get("id", scenarios[choice].get("name"))
        self.opponent_select(scenario_id)

    def opponent_select(self, scenario_id: str) -> None:
        """Select an opponent type."""
        clear_screen()
        print_header("SELECT OPPONENT")

        opponent_types = list_opponent_types()
        options = []
        type_list = []

        for category, types in opponent_types.items():
            category_name = category.replace("_", " ").title()
            options.append(f"-- {category_name} --")
            type_list.append(None)  # Separator
            for opponent_type in types:
                display_name = opponent_type.replace("_", " ").title()
                options.append(f"  {display_name}")
                type_list.append(opponent_type)

        options.append("Back")
        type_list.append(None)

        menu = TerminalMenu(options, title="Choose an opponent:")
        choice = menu.show()

        if choice is None or choice == len(options) - 1:
            return

        selected_type = type_list[choice]
        if selected_type is None:
            # Selected a category header, try again
            self.opponent_select(scenario_id)
            return

        self.side_select(scenario_id, selected_type)

    def side_select(self, scenario_id: str, opponent_type: str) -> None:
        """Select which side to play."""
        clear_screen()
        print_header("CHOOSE YOUR SIDE")

        scenario = self.repo.get_scenario(scenario_id)
        if scenario:
            player_a_name = scenario.get("player_a_name", "Player A")
            player_a_role = scenario.get("player_a_role", "Side A")
            player_b_name = scenario.get("player_b_name", "Player B")
            player_b_role = scenario.get("player_b_role", "Side B")

            print(f"Scenario: {scenario.get('name', scenario_id)}\n")
            options = [
                f"{player_a_name} ({player_a_role})",
                f"{player_b_name} ({player_b_role})",
                "Back",
            ]
        else:
            options = ["Player A", "Player B", "Back"]

        menu = TerminalMenu(options, title="Choose which side you want to play:")
        choice = menu.show()

        if choice is None or choice == 2:
            return

        self.human_is_player_a = choice == 0
        self.human_player = "A" if self.human_is_player_a else "B"
        self.opponent_player = "B" if self.human_is_player_a else "A"

        self.start_game(scenario_id, opponent_type)

    def start_game(self, scenario_id: str, opponent_type: str) -> None:
        """Start a new game."""
        clear_screen()
        print("Initializing game...")

        self.game = create_game(scenario_id, self.repo)
        self.turn_history = []

        # Get scenario information for opponent role context
        scenario = self.repo.get_scenario(scenario_id)
        role_name = None
        role_description = None
        if scenario:
            if self.human_is_player_a:
                role_name = scenario.get("player_b_role")
                role_description = scenario.get("player_b_description")
            else:
                role_name = scenario.get("player_a_role")
                role_description = scenario.get("player_a_description")

        self.opponent = get_opponent_by_type(
            opponent_type,
            is_player_a=not self.human_is_player_a,
            role_name=role_name,
            role_description=role_description,
        )

        # Initialize trace logger
        self.trace_logger = TraceLogger(
            scenario_id=scenario_id,
            opponent_type=opponent_type,
            human_player=self.human_player,
        )

        self.game_loop()

    def game_loop(self) -> None:
        """Main game loop."""
        while True:
            if self.game.get_ending():
                self.show_ending()
                return

            self.show_game_screen()
            action = self.get_player_action()

            if action is None:
                # Player quit
                return

            if action == "settlement":
                self.propose_settlement()
                continue

            self.execute_turn(action)

    def show_game_screen(self) -> None:
        """Display the current game state."""
        clear_screen()
        state = self.game.get_current_state()

        # Status line
        act_str = {1: "Act I", 2: "Act II", 3: "Act III"}.get(state.act, f"Act {state.act}")
        print(f"Turn {state.turn} | {act_str}")
        print("=" * 60)

        # Briefing
        print_section("BRIEFING")
        briefing = self.game.get_briefing()
        if briefing:
            # Wrap long lines
            words = briefing.split()
            line = ""
            for word in words:
                if len(line) + len(word) + 1 > 70:
                    print(line)
                    line = word
                else:
                    line = f"{line} {word}" if line else word
            if line:
                print(line)
        else:
            print("The situation develops...")

        # State summary
        print_section("CRISIS STATUS")
        print(f"  Risk Level:   {state.risk_level:.1f}/10")
        print(f"  Cooperation:  {state.cooperation_score:.1f}/10")
        print(f"  Stability:    {state.stability:.1f}/10")
        print(f"  Surplus Pool: {state.cooperation_surplus:.1f} VP")
        # Show captured VP from perspective of human player
        if self.human_is_player_a:
            your_captured = state.surplus_captured_a
            opp_captured = state.surplus_captured_b
        else:
            your_captured = state.surplus_captured_b
            opp_captured = state.surplus_captured_a
        print(f"  Your Captured: {your_captured:.1f} VP  Opponent Captured: {opp_captured:.1f} VP")

        # Recent history
        print_section("RECENT HISTORY")
        if self.turn_history:
            # Show last 3 entries
            for entry in self.turn_history[-3:]:
                print(f"  {entry}")
        else:
            print("  Awaiting first action...")

    def get_player_action(self) -> Optional[Action | str]:
        """Get the player's action choice."""
        available_actions = self.game.get_available_actions(self.human_player)
        state = self.game.get_current_state()

        print_section("AVAILABLE ACTIONS")

        # Build menu options
        options = []
        action_indices = []

        # Check if settlement is available
        menu = self.game.get_action_menu(self.human_player)
        can_settle = menu.can_propose_settlement

        for i, action in enumerate(available_actions):
            if action.action_type == ActionType.COOPERATIVE:
                marker = "[C]"
            else:
                marker = "[D]"

            cost_str = f" (Cost: {action.resource_cost:.1f}R)" if action.resource_cost > 0 else ""
            options.append(f"{marker} {action.name}{cost_str}")
            action_indices.append(i)

        if can_settle:
            options.append("[S] Propose Settlement")
            action_indices.append("settlement")

        options.append("[Q] Quit Game")
        action_indices.append(None)

        menu = TerminalMenu(
            options,
            title="Select your action:",
        )
        choice = menu.show()

        if choice is None:
            return None

        selected = action_indices[choice]
        if selected is None:
            return None
        if selected == "settlement":
            return "settlement"
        return available_actions[selected]

    def execute_turn(self, human_action: Action) -> None:
        """Execute a turn with the given human action."""
        print("\nOpponent is thinking...")

        state = self.game.get_current_state()

        # Record state before turn for trace
        if self.trace_logger:
            self.trace_logger.start_turn(state)

        opponent_actions = self.game.get_available_actions(self.opponent_player)

        # Get opponent's action (async)
        opponent_action = run_async(
            self.opponent.choose_action(state, opponent_actions)
        )

        # Validate opponent action
        if opponent_action not in opponent_actions:
            opponent_action = opponent_actions[0] if opponent_actions else None
            if opponent_action is None:
                print("Error: Opponent has no valid actions!")
                input("Press Enter to continue...")
                return

        # Submit actions in correct order (action_a, action_b)
        if self.human_is_player_a:
            result = self.game.submit_actions(human_action, opponent_action)
        else:
            result = self.game.submit_actions(opponent_action, human_action)

        # Get state after turn for trace
        state_after = self.game.get_current_state()

        if result.success:
            # Record turn in trace
            if self.trace_logger:
                self.trace_logger.record_turn(
                    human_action=human_action,
                    opponent_action=opponent_action,
                    result=result,
                    state_after=state_after,
                    human_is_player_a=self.human_is_player_a,
                )

            # Build history entry
            you_type = "C" if human_action.action_type == ActionType.COOPERATIVE else "D"
            opp_type = "C" if opponent_action.action_type == ActionType.COOPERATIVE else "D"
            outcome_code = result.action_result.outcome_code if result.action_result else "??"
            entry = f"Turn {state.turn}: You ({you_type}) vs Opponent ({opp_type}) -> {outcome_code}"
            self.turn_history.append(entry)

            # Show narrative if any
            if result.narrative:
                print(f"\n{result.narrative}")
                input("\nPress Enter to continue...")

            # Check for game ending
            if result.ending:
                if self.trace_logger:
                    self.trace_logger.record_ending(
                        ending_type=result.ending.ending_type.value,
                        vp_a=result.ending.vp_a,
                        vp_b=result.ending.vp_b,
                        description=result.ending.description,
                    )
        else:
            print(f"Error: {result.error}")
            input("Press Enter to continue...")

    def propose_settlement(self) -> None:
        """Handle settlement proposal from human player."""
        clear_screen()
        print_header("PROPOSE SETTLEMENT")

        state = self.game.get_current_state()

        # Calculate suggested VP
        if self.human_is_player_a:
            my_position = state.position_a
        else:
            my_position = state.position_b

        total_pos = state.position_a + state.position_b
        if total_pos > 0:
            suggested = int((my_position / total_pos) * 100)
        else:
            suggested = 50

        coop_bonus = int((state.cooperation_score - 5) * 2)
        suggested = max(20, min(80, suggested + coop_bonus))

        min_vp = max(20, suggested - 10)
        max_vp = min(80, suggested + 10)

        print(f"Suggested VP: {suggested} (based on situation)")
        print(f"Valid range: {min_vp}-{max_vp}")
        print()

        # Get VP offer
        while True:
            try:
                vp_str = input(f"Enter VP for yourself [{suggested}]: ").strip()
                if not vp_str:
                    offered_vp = suggested
                else:
                    offered_vp = int(vp_str)

                if not (min_vp <= offered_vp <= max_vp):
                    print(f"VP must be between {min_vp} and {max_vp}")
                    continue
                break
            except ValueError:
                print("Please enter a valid number")

        # Get argument
        print("\nSettlement argument (max 500 chars, press Enter to skip):")
        argument = input("> ").strip()[:500]

        # Create proposal
        proposal = SettlementProposal(offered_vp=offered_vp, argument=argument)

        print("\nEvaluating settlement...")

        # Get opponent response (async)
        response = run_async(
            self.opponent.evaluate_settlement(proposal, state, False)
        )

        # Record in trace
        if self.trace_logger:
            self.trace_logger.record_settlement_attempt(
                proposer="human",
                offered_vp=offered_vp,
                argument=argument,
                response=response.action,
                counter_vp=response.counter_vp if response.action == "counter" else None,
            )

        self._handle_settlement_response(response, offered_vp, state.turn)

    def _handle_settlement_response(
        self,
        response: SettlementResponse,
        offered_vp: int,
        turn: int,
    ) -> None:
        """Handle the opponent's response to a settlement proposal."""
        if response.action == "accept":
            # Settlement accepted
            if self.human_is_player_a:
                vp_a = offered_vp
                vp_b = 100 - offered_vp
            else:
                vp_b = offered_vp
                vp_a = 100 - offered_vp

            ending = GameEnding(
                ending_type=EndingType.SETTLEMENT,
                vp_a=float(vp_a),
                vp_b=float(vp_b),
                turn=turn,
                description=f"Settlement accepted. Player A: {vp_a} VP, Player B: {vp_b} VP",
            )
            self.game.ending = ending

            if self.trace_logger:
                self.trace_logger.record_ending(
                    ending_type=ending.ending_type.value,
                    vp_a=ending.vp_a,
                    vp_b=ending.vp_b,
                    description=ending.description,
                )

            print("\nSettlement ACCEPTED!")
            input("Press Enter to continue...")

        elif response.action == "counter":
            print(f"\nOpponent counters with {response.counter_vp} VP for themselves")
            if response.counter_argument:
                print(f"Argument: {response.counter_argument}")

            # Ask if player accepts counter
            menu = TerminalMenu(
                ["Accept counter-offer", "Reject"],
                title="What do you want to do?",
            )
            choice = menu.show()

            if choice == 0:
                # Accept counter
                state = self.game.get_current_state()
                their_vp = response.counter_vp
                your_vp = 100 - their_vp

                if self.human_is_player_a:
                    vp_a = your_vp
                    vp_b = their_vp
                else:
                    vp_a = their_vp
                    vp_b = your_vp

                ending = GameEnding(
                    ending_type=EndingType.SETTLEMENT,
                    vp_a=float(vp_a),
                    vp_b=float(vp_b),
                    turn=state.turn,
                    description=f"Settlement accepted. Player A: {vp_a} VP, Player B: {vp_b} VP",
                )
                self.game.ending = ending

                if self.trace_logger:
                    self.trace_logger.record_ending(
                        ending_type=ending.ending_type.value,
                        vp_a=ending.vp_a,
                        vp_b=ending.vp_b,
                        description=ending.description,
                    )

                print("\nYou accepted the counter-offer!")
                input("Press Enter to continue...")
            else:
                print("\nSettlement rejected. Risk +1")
                input("Press Enter to continue...")

        else:
            # Rejected
            print(f"\nSettlement REJECTED: {response.rejection_reason or 'No reason given'}")
            print("Risk +1")
            input("Press Enter to continue...")

    def show_ending(self) -> None:
        """Display the game ending."""
        ending = self.game.get_ending()
        if not ending:
            return

        clear_screen()
        print_header("GAME OVER")

        ending_name = ending.ending_type.value.replace("_", " ").title()
        print(f"Ending: {ending_name}")
        print(f"Turn: {ending.turn}")
        print()

        if self.human_is_player_a:
            your_vp = ending.vp_a
            opp_vp = ending.vp_b
        else:
            your_vp = ending.vp_b
            opp_vp = ending.vp_a

        print(f"Your VP:      {your_vp:.1f}")
        print(f"Opponent VP:  {opp_vp:.1f}")
        print()
        print(ending.description)

        if self.trace_logger:
            print(f"\nTrace saved to: {self.trace_logger._output_file}")

        print_section("OPTIONS")
        menu = TerminalMenu(
            ["View Coaching Analysis", "Return to Main Menu", "Quit"],
        )
        choice = menu.show()

        if choice == 0:
            self.show_coaching()
        elif choice == 2:
            sys.exit(0)

    def show_coaching(self) -> None:
        """Display post-game coaching analysis."""
        clear_screen()
        print_header("POST-GAME COACHING")

        history = self.game.get_history()
        ending = self.game.get_ending()

        # Overall assessment
        print_section("Overall Assessment")
        if ending:
            if self.human_is_player_a:
                your_vp = ending.vp_a
            else:
                your_vp = ending.vp_b

            if your_vp > 60:
                print("Strong Victory - You achieved a decisive advantage.")
            elif your_vp > 50:
                print("Marginal Victory - You came out slightly ahead.")
            elif your_vp > 40:
                print("Marginal Loss - Your opponent had a slight edge.")
            else:
                print("Significant Loss - Review your strategy carefully.")

        # Turn history
        print_section("Turn History")
        for record in history:
            if record.action_a and record.action_b and record.outcome:
                print(
                    f"Turn {record.turn}: {record.action_a.name} vs {record.action_b.name} "
                    f"-> {record.outcome.outcome_code}"
                )

        # Key insights
        print_section("Key Insights")
        coop_count = sum(1 for r in history if r.outcome and r.outcome.is_mutual_cooperation)
        comp_count = sum(1 for r in history if r.outcome and r.outcome.is_mutual_defection)
        total = len(history)

        if total > 0:
            print(f"Mutual cooperation rate: {coop_count}/{total} ({100*coop_count/total:.0f}%)")
            print(f"Mutual competition rate: {comp_count}/{total} ({100*comp_count/total:.0f}%)")

        # Recommendations
        print_section("Recommendations")
        if total > 0:
            if coop_count < total * 0.3:
                print("- Consider using more cooperative strategies to build trust")
            if comp_count > total * 0.5:
                print("- High competition led to instability - balance risk vs reward")

        input("\nPress Enter to return to main menu...")


def main() -> None:
    """Entry point for the CLI application."""
    try:
        app = BrinksmanshipCLI()
        app.run()
    except KeyboardInterrupt:
        print("\nGoodbye!")


if __name__ == "__main__":
    main()
