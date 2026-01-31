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

        # Show current surplus pool
        print(f"Current Surplus Pool: {state.cooperation_surplus:.1f} VP")
        print()

        # Calculate suggested VP and position advantage
        if self.human_is_player_a:
            my_position = state.position_a
            opp_position = state.position_b
        else:
            my_position = state.position_b
            opp_position = state.position_a

        position_diff = my_position - opp_position
        total_pos = state.position_a + state.position_b
        if total_pos > 0:
            suggested = int((my_position / total_pos) * 100)
        else:
            suggested = 50

        coop_bonus = int((state.cooperation_score - 5) * 2)
        suggested = max(20, min(80, suggested + coop_bonus))

        min_vp = max(20, suggested - 10)
        max_vp = min(80, suggested + 10)

        # Show position advantage
        if position_diff > 0:
            print(f"Your Position Advantage: +{position_diff:.1f} (suggested VP: {suggested})")
        elif position_diff < 0:
            print(f"Your Position Disadvantage: {position_diff:.1f} (suggested VP: {suggested})")
        else:
            print(f"Positions Equal (suggested VP: {suggested})")

        print(f"Valid VP range: {min_vp}-{max_vp}")
        print()

        # Get VP offer
        while True:
            try:
                vp_str = input(f"Enter your VP offer (valid range {min_vp}-{max_vp}) [{suggested}]: ").strip()
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

        # Get surplus split percentage
        print()
        while True:
            try:
                surplus_str = input("Enter your surplus share % (you get this much) [50]: ").strip()
                if not surplus_str:
                    surplus_split = 50
                else:
                    surplus_split = int(surplus_str)

                if not (0 <= surplus_split <= 100):
                    print("Surplus share must be between 0 and 100")
                    continue
                break
            except ValueError:
                print("Please enter a valid number")

        # Get argument
        print("\nEnter your argument (max 500 chars, press Enter to skip):")
        argument = input("> ").strip()[:500]

        # Create proposal with surplus split
        proposal = SettlementProposal(
            offered_vp=offered_vp,
            surplus_split_percent=surplus_split,
            argument=argument if argument else "Settlement proposed."
        )

        print("\nSubmitting proposal...")

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

        self._handle_settlement_response(response, offered_vp, surplus_split, state)

    def _handle_settlement_response(
        self,
        response: SettlementResponse,
        offered_vp: int,
        surplus_split: int,
        state: GameState,
        exchange_number: int = 1,
    ) -> None:
        """Handle the opponent's response to a settlement proposal.

        Args:
            response: The opponent's settlement response
            offered_vp: The VP offered in the proposal
            surplus_split: The surplus split percentage in the proposal
            state: Current game state
            exchange_number: Which exchange this is (1, 2, or 3)
        """
        from brinksmanship.parameters import calculate_rejection_penalty, REJECTION_BASE_PENALTY
        from brinksmanship.engine.resolution import MAX_SETTLEMENT_EXCHANGES

        if response.action == "accept":
            # Settlement accepted - distribute surplus
            surplus_pool = state.cooperation_surplus
            your_surplus = surplus_pool * (surplus_split / 100.0)
            their_surplus = surplus_pool - your_surplus

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

            print("\n" + "=" * 50)
            print("SETTLEMENT ACCEPTED!")
            print("=" * 50)
            print(f"\nVP Split:")
            print(f"  You: {offered_vp} VP")
            print(f"  Opponent: {100 - offered_vp} VP")
            print(f"\nSurplus Distribution (Pool: {surplus_pool:.1f} VP):")
            print(f"  You: {your_surplus:.1f} VP ({surplus_split}%)")
            print(f"  Opponent: {their_surplus:.1f} VP ({100 - surplus_split}%)")
            input("\nPress Enter to continue...")

        elif response.action == "counter":
            # Get counter surplus split if available
            counter_surplus = getattr(response, 'counter_surplus_split_percent', 50) or 50

            print("\n" + "-" * 50)
            print("Opponent Response: COUNTER")
            print("-" * 50)
            print(f"  Counter VP: {response.counter_vp}")
            print(f"  Counter Surplus Split: {counter_surplus}%")
            if response.counter_argument:
                print(f"  Argument: \"{response.counter_argument}\"")
            print()

            # Ask if player accepts counter
            menu = TerminalMenu(
                ["Accept counter-offer", "Reject (adds risk penalty)"],
                title="Accept counter?",
            )
            choice = menu.show()

            if choice == 0:
                # Accept counter - recalculate surplus distribution
                surplus_pool = state.cooperation_surplus
                their_vp = response.counter_vp
                your_vp = 100 - their_vp
                # When accepting counter, surplus split is from opponent's perspective
                their_surplus = surplus_pool * (counter_surplus / 100.0)
                your_surplus = surplus_pool - their_surplus

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

                print("\n" + "=" * 50)
                print("COUNTER-OFFER ACCEPTED!")
                print("=" * 50)
                print(f"\nVP Split:")
                print(f"  You: {your_vp} VP")
                print(f"  Opponent: {their_vp} VP")
                print(f"\nSurplus Distribution (Pool: {surplus_pool:.1f} VP):")
                print(f"  You: {your_surplus:.1f} VP ({100 - counter_surplus}%)")
                print(f"  Opponent: {their_surplus:.1f} VP ({counter_surplus}%)")
                input("\nPress Enter to continue...")
            else:
                # Rejection - apply escalating penalty
                risk_penalty = calculate_rejection_penalty(exchange_number)
                remaining = MAX_SETTLEMENT_EXCHANGES - exchange_number

                print(f"\nSettlement rejected.")
                print(f"Risk penalty: +{risk_penalty:.2f}")

                if remaining > 0:
                    next_penalty = calculate_rejection_penalty(exchange_number + 1)
                    print(f"Warning: {remaining} exchange(s) remaining. Next rejection: +{next_penalty:.2f} risk")
                else:
                    print("Maximum exchanges reached. Negotiation has ended.")

                # Apply the penalty to game state
                new_risk = min(10.0, state.risk_level + risk_penalty)
                self.game.state = state.model_copy(update={"risk_level": new_risk})

                input("\nPress Enter to continue...")

        else:
            # Rejected outright
            risk_penalty = calculate_rejection_penalty(exchange_number)
            remaining = MAX_SETTLEMENT_EXCHANGES - exchange_number

            print("\n" + "-" * 50)
            print("Opponent Response: REJECT")
            print("-" * 50)
            if response.rejection_reason:
                print(f"  Reason: \"{response.rejection_reason}\"")
            print(f"\nRisk penalty: +{risk_penalty:.2f}")

            if remaining > 0:
                next_penalty = calculate_rejection_penalty(exchange_number + 1)
                print(f"Warning: {remaining} exchange(s) remaining. Next rejection: +{next_penalty:.2f} risk")
            else:
                print("Maximum exchanges reached. Negotiation has ended.")

            # Apply the penalty to game state
            new_risk = min(10.0, state.risk_level + risk_penalty)
            self.game.state = state.model_copy(update={"risk_level": new_risk})

            input("\nPress Enter to continue...")

    def show_ending(self) -> None:
        """Display the game ending."""
        ending = self.game.get_ending()
        if not ending:
            return

        # Show the educational scorecard
        self.show_scorecard()

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

    def show_scorecard(self) -> None:
        """Display the multi-criteria educational scorecard.

        Shows Personal Success, Joint Success, and Strategic Profile
        metrics as described in GAME_MANUAL.md Section 4.4.
        """
        ending = self.game.get_ending()
        if not ending:
            return

        state = self.game.get_current_state()
        history = self.game.get_history()

        # Determine labels based on which side human played
        if self.human_is_player_a:
            your_label = "You"
            opp_label = "Opponent"
            your_vp = ending.vp_a
            opp_vp = ending.vp_b
            your_captured = state.surplus_captured_a
            opp_captured = state.surplus_captured_b
        else:
            your_label = "You"
            opp_label = "Opponent"
            your_vp = ending.vp_b
            opp_vp = ending.vp_a
            your_captured = state.surplus_captured_b
            opp_captured = state.surplus_captured_a

        # Calculate metrics
        total_value = your_vp + opp_vp
        your_share = (your_vp / total_value * 100) if total_value > 0 else 50.0
        opp_share = (opp_vp / total_value * 100) if total_value > 0 else 50.0
        value_vs_baseline = total_value - 100

        # Pareto Efficiency: min VP / (total / 2) * 100
        # This measures how evenly distributed the value is
        min_vp = min(your_vp, opp_vp)
        pareto_efficiency = (min_vp / (total_value / 2) * 100) if total_value > 0 else 0.0

        # Check if settlement was reached
        settlement_reached = ending.ending_type == EndingType.SETTLEMENT
        surplus_distributed = your_captured + opp_captured

        # Calculate strategic profile from history
        your_max_streak, opp_max_streak = self._calculate_max_streaks(history)
        your_times_exploited, opp_times_exploited = self._calculate_times_exploited(history)
        settlement_initiator = self._get_settlement_initiator()

        # Clear screen and display scorecard
        clear_screen()

        # Header
        print("=" * 55)
        print(" " * 18 + "GAME RESULTS")
        print("=" * 55)
        print()

        # Personal Success section
        print(f"PERSONAL SUCCESS{' ' * 21}{your_label:>8}  {opp_label:>8}")
        print("-" * 55)
        print(f"Final VP{' ' * 30}{your_vp:>8.1f}  {opp_vp:>8.1f}")
        print(f"VP Share{' ' * 30}{your_share:>7.1f}%  {opp_share:>7.1f}%")
        print()

        # Joint Success section
        print(f"JOINT SUCCESS{' ' * 26}BOTH")
        print("-" * 55)
        print(f"Total Value Created{' ' * 19}{total_value:>8.1f} VP")
        if value_vs_baseline >= 0:
            print(f"Value vs Zero-Sum Baseline{' ' * 12}+{value_vs_baseline:.1f} VP")
        else:
            print(f"Value vs Zero-Sum Baseline{' ' * 12}{value_vs_baseline:+.1f} VP")
        print(f"Pareto Efficiency{' ' * 21}{pareto_efficiency:>7.1f}%")
        print(f"Settlement Reached?{' ' * 19}{'Yes' if settlement_reached else 'No':>8}")
        print(f"Surplus Distributed{' ' * 19}{surplus_distributed:>8.1f} VP")
        print()

        # Strategic Profile section
        print(f"STRATEGIC PROFILE{' ' * 20}{your_label:>8}  {opp_label:>8}")
        print("-" * 55)
        print(f"Cooperation Streak (max){' ' * 14}{your_max_streak:>8}  {opp_max_streak:>8}")
        print(f"Times Exploited{' ' * 23}{your_times_exploited:>8}  {opp_times_exploited:>8}")

        # Settlement initiator
        if settlement_initiator == "you":
            print(f"Settlement Initiated By{' ' * 15}{your_label:>8}  {'-':>8}")
        elif settlement_initiator == "opponent":
            print(f"Settlement Initiated By{' ' * 15}{'-':>8}  {opp_label:>8}")
        elif settlement_initiator == "both":
            print(f"Settlement Initiated By{' ' * 15}{'Both':>8}  {'-':>8}")
        else:
            print(f"Settlement Initiated By{' ' * 15}{'-':>8}  {'-':>8}")

        print("=" * 55)
        print()

        # Wait for keypress
        input("Press Enter to continue...")

    def _calculate_max_streaks(self, history: list) -> tuple[int, int]:
        """Calculate max cooperation streak for each player.

        A player's streak increases when their action is cooperative
        and the outcome is CC. We track streaks separately for each player.

        Returns:
            Tuple of (your_max_streak, opponent_max_streak)
        """
        your_streak = 0
        opp_streak = 0
        your_max = 0
        opp_max = 0

        for record in history:
            if not record.outcome:
                continue

            outcome_code = record.outcome.outcome_code

            # Human's streak
            if self.human_is_player_a:
                human_cooperated = outcome_code.startswith("C")
            else:
                human_cooperated = outcome_code.endswith("C")

            # Opponent's streak
            if self.human_is_player_a:
                opp_cooperated = outcome_code.endswith("C")
            else:
                opp_cooperated = outcome_code.startswith("C")

            # Update streaks - streak increases on CC outcome
            if outcome_code == "CC":
                your_streak += 1
                opp_streak += 1
                your_max = max(your_max, your_streak)
                opp_max = max(opp_max, opp_streak)
            else:
                # Reset streaks on any non-CC outcome
                your_streak = 0
                opp_streak = 0

        return your_max, opp_max

    def _calculate_times_exploited(self, history: list) -> tuple[int, int]:
        """Calculate how many times each player was exploited.

        A player is exploited when they cooperate and opponent defects.

        Returns:
            Tuple of (your_times_exploited, opponent_times_exploited)
        """
        your_exploited = 0
        opp_exploited = 0

        for record in history:
            if not record.outcome:
                continue

            outcome_code = record.outcome.outcome_code

            if self.human_is_player_a:
                # CD means A (you) cooperated, B defected - you were exploited
                # DC means A (you) defected, B cooperated - opponent was exploited
                if outcome_code == "CD":
                    your_exploited += 1
                elif outcome_code == "DC":
                    opp_exploited += 1
            else:
                # CD means A defected, B (you) cooperated - opponent exploited (you)
                # Wait, CD = A cooperates, B defects. If you're B:
                # CD = A cooperated, B (you) defected - opponent was exploited
                # DC = A defected, B (you) cooperated - you were exploited
                if outcome_code == "DC":
                    your_exploited += 1
                elif outcome_code == "CD":
                    opp_exploited += 1

        return your_exploited, opp_exploited

    def _get_settlement_initiator(self) -> str:
        """Determine who initiated the settlement.

        Returns:
            "you", "opponent", "both", or "none"
        """
        if self.trace_logger and self.trace_logger.trace.settlement_attempts:
            # Get the last successful settlement attempt
            for attempt in reversed(self.trace_logger.trace.settlement_attempts):
                if attempt.get("response") == "accept":
                    proposer = attempt.get("proposer", "")
                    if proposer == "human":
                        return "you"
                    elif proposer == "opponent":
                        return "opponent"

            # If no accepted settlement, check who proposed
            if self.trace_logger.trace.settlement_attempts:
                first_attempt = self.trace_logger.trace.settlement_attempts[0]
                proposer = first_attempt.get("proposer", "")
                if proposer == "human":
                    return "you"
                elif proposer == "opponent":
                    return "opponent"

        return "none"

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
