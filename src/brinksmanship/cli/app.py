"""Brinksmanship CLI Application.

A Textual-based terminal interface for playing Brinksmanship.

Milestone 7.1 deliverable - implements:
- Main menu
- Opponent selection
- Scenario selection
- Game screen with state, briefing, actions, history
- Settlement negotiation UI
- End-game results
- Coaching display
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Optional

from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.message import Message
from textual.screen import Screen
from textual.widgets import (
    Button,
    Footer,
    Header,
    Input,
    Label,
    ListItem,
    ListView,
    Markdown,
    OptionList,
    Placeholder,
    Rule,
    Static,
    TextArea,
)
from textual.widgets.option_list import Option

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
    ActionMenu,
    ActionType,
    format_action_for_display,
)
from brinksmanship.models.state import GameState, InformationState
from brinksmanship.opponents.base import (
    Opponent,
    SettlementProposal,
    SettlementResponse,
    get_opponent_by_type,
    list_opponent_types,
)
from brinksmanship.storage import get_scenario_repository

if TYPE_CHECKING:
    from brinksmanship.coaching.post_game import CoachingReport


# =============================================================================
# Theme and Styles
# =============================================================================

CSS = """
Screen {
    background: $surface;
}

#main-menu {
    align: center middle;
    width: 100%;
    height: 100%;
}

.menu-container {
    width: 60;
    height: auto;
    border: solid green;
    padding: 1 2;
}

.menu-title {
    text-align: center;
    text-style: bold;
    color: $success;
    margin-bottom: 1;
}

.menu-button {
    width: 100%;
    margin: 1 0;
}

.panel {
    border: solid $primary;
    padding: 1;
    margin: 0 0 1 0;
}

.panel-title {
    text-style: bold;
    color: $secondary;
    margin-bottom: 1;
}

.state-display {
    height: auto;
}

.state-row {
    height: 1;
}

.state-label {
    width: 20;
    color: $text-muted;
}

.state-value {
    color: $text;
}

.intel-unknown {
    color: $warning;
}

.intel-stale {
    color: $error;
}

.action-coop {
    color: $success;
}

.action-comp {
    color: $error;
}

.action-special {
    color: $warning;
}

.history-panel {
    height: 3;
    border: solid $primary;
    padding: 0 1;
}

#game-screen {
    layout: grid;
    grid-size: 2;
    grid-columns: 1fr 1fr;
}

.left-column {
    padding: 1;
}

.right-column {
    padding: 1;
}

#briefing-panel {
    height: auto;
    max-height: 10;
}

#state-panel {
    height: auto;
}

#actions-panel {
    height: auto;
}

#history-bar {
    dock: bottom;
    height: 3;
}

.vp-display {
    text-style: bold;
    text-align: center;
}

.vp-a {
    color: $success;
}

.vp-b {
    color: $warning;
}

.coaching-section {
    margin-bottom: 2;
}

.coaching-title {
    text-style: bold;
    color: $primary;
    margin-bottom: 1;
}

#settlement-modal {
    align: center middle;
}

.modal-container {
    width: 70;
    height: auto;
    border: solid $warning;
    background: $surface;
    padding: 2;
}

.modal-title {
    text-style: bold;
    text-align: center;
    color: $warning;
    margin-bottom: 1;
}

.input-label {
    margin-top: 1;
}

.button-row {
    margin-top: 2;
    align: center middle;
}

.button-row Button {
    margin: 0 1;
}

OptionList {
    height: auto;
    max-height: 12;
}
"""


# =============================================================================
# Screens
# =============================================================================


class MainMenuScreen(Screen):
    """Main menu screen with game options."""

    BINDINGS = [
        Binding("q", "quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Container(id="main-menu"):
            with Vertical(classes="menu-container"):
                yield Static("BRINKSMANSHIP", classes="menu-title")
                yield Static("A Game-Theoretic Strategy Simulation", classes="menu-title")
                yield Rule()
                yield Button("New Game", id="new-game", classes="menu-button", variant="success")
                yield Button("Load Scenario", id="load-scenario", classes="menu-button", variant="primary")
                yield Button("Settings", id="settings", classes="menu-button", variant="default")
                yield Button("Quit", id="quit", classes="menu-button", variant="error")
        yield Footer()

    @on(Button.Pressed, "#new-game")
    def start_new_game(self) -> None:
        self.app.push_screen(ScenarioSelectScreen())

    @on(Button.Pressed, "#load-scenario")
    def load_scenario(self) -> None:
        self.app.push_screen(ScenarioSelectScreen())

    @on(Button.Pressed, "#settings")
    def show_settings(self) -> None:
        self.notify("Settings not yet implemented", severity="warning")

    @on(Button.Pressed, "#quit")
    def quit_app(self) -> None:
        self.app.exit()


class ScenarioSelectScreen(Screen):
    """Screen for selecting a scenario."""

    BINDINGS = [
        Binding("escape", "go_back", "Back"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        with Container(id="main-menu"):
            with Vertical(classes="menu-container"):
                yield Static("SELECT SCENARIO", classes="menu-title")
                yield Rule()
                yield OptionList(id="scenario-list")
                yield Rule()
                yield Button("Back", id="back", variant="default")
        yield Footer()

    def on_mount(self) -> None:
        """Load scenarios when screen mounts."""
        option_list = self.query_one("#scenario-list", OptionList)
        repo = get_scenario_repository()
        scenarios = repo.list_scenarios()

        if scenarios:
            for scenario in scenarios:
                name = scenario.get("name", scenario.get("id", "Unknown"))
                setting = scenario.get("setting", "")
                label = f"{name}" + (f" - {setting}" if setting else "")
                option_list.add_option(Option(label, id=scenario.get("id", name)))
        else:
            # Add a default scenario option
            option_list.add_option(Option("Default Scenario", id="default"))

    @on(OptionList.OptionSelected)
    def scenario_selected(self, event: OptionList.OptionSelected) -> None:
        scenario_id = str(event.option.id)
        self.app.push_screen(OpponentSelectScreen(scenario_id))

    @on(Button.Pressed, "#back")
    def go_back(self) -> None:
        self.app.pop_screen()

    def action_go_back(self) -> None:
        self.app.pop_screen()


class OpponentSelectScreen(Screen):
    """Screen for selecting an opponent."""

    BINDINGS = [
        Binding("escape", "go_back", "Back"),
    ]

    def __init__(self, scenario_id: str) -> None:
        super().__init__()
        self.scenario_id = scenario_id

    def compose(self) -> ComposeResult:
        yield Header()
        with Container(id="main-menu"):
            with Vertical(classes="menu-container"):
                yield Static("SELECT OPPONENT", classes="menu-title")
                yield Rule()
                yield OptionList(id="opponent-list")
                yield Rule()
                yield Button("Back", id="back", variant="default")
        yield Footer()

    def on_mount(self) -> None:
        """Load opponent types when screen mounts."""
        option_list = self.query_one("#opponent-list", OptionList)
        opponent_types = list_opponent_types()

        for category, types in opponent_types.items():
            # Add category as a separator
            category_name = category.replace("_", " ").title()
            option_list.add_option(Option(f"── {category_name} ──", disabled=True))
            for opponent_type in types:
                display_name = opponent_type.replace("_", " ").title()
                option_list.add_option(Option(display_name, id=opponent_type))

    @on(OptionList.OptionSelected)
    def opponent_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option.disabled:
            return
        opponent_type = str(event.option.id)
        self.app.push_screen(GameScreen(self.scenario_id, opponent_type))

    @on(Button.Pressed, "#back")
    def go_back(self) -> None:
        self.app.pop_screen()

    def action_go_back(self) -> None:
        self.app.pop_screen()


class GameScreen(Screen):
    """Main game screen with all game panels."""

    BINDINGS = [
        Binding("escape", "confirm_quit", "Quit Game"),
        Binding("s", "propose_settlement", "Settlement"),
        Binding("1", "select_action_1", "Action 1", show=False),
        Binding("2", "select_action_2", "Action 2", show=False),
        Binding("3", "select_action_3", "Action 3", show=False),
        Binding("4", "select_action_4", "Action 4", show=False),
        Binding("5", "select_action_5", "Action 5", show=False),
        Binding("6", "select_action_6", "Action 6", show=False),
        Binding("7", "select_action_7", "Action 7", show=False),
        Binding("8", "select_action_8", "Action 8", show=False),
        Binding("9", "select_action_9", "Action 9", show=False),
    ]

    def __init__(self, scenario_id: str, opponent_type: str) -> None:
        super().__init__()
        self.scenario_id = scenario_id
        self.opponent_type = opponent_type
        self.game: Optional[GameEngine] = None
        self.opponent: Optional[Opponent] = None
        self.available_actions: list[Action] = []
        self.turn_history: list[str] = []

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="game-screen"):
            with Vertical(classes="left-column"):
                yield Static("Turn 1 | Risk: 2.0 | Coop: 5.0 | Stability: 5.0 | Act I", id="header-bar")
                yield Rule()
                with VerticalScroll(id="briefing-panel", classes="panel"):
                    yield Static("BRIEFING", classes="panel-title")
                    yield Static("Loading...", id="briefing-text")
                yield Rule()
                with Vertical(id="state-panel", classes="panel"):
                    yield Static("YOUR STATUS", classes="panel-title")
                    yield Static("Position: --", id="your-position")
                    yield Static("Resources: --", id="your-resources")
            with Vertical(classes="right-column"):
                with Vertical(id="intel-panel", classes="panel"):
                    yield Static("INTELLIGENCE ON OPPONENT", classes="panel-title")
                    yield Static("Position: UNKNOWN", id="intel-position")
                    yield Static("Resources: UNKNOWN", id="intel-resources")
                yield Rule()
                with Vertical(id="actions-panel", classes="panel"):
                    yield Static("ACTIONS", classes="panel-title")
                    yield OptionList(id="action-list")
        with Horizontal(id="history-bar", classes="history-panel"):
            yield Static("HISTORY: ", id="history-label")
            yield Static("", id="history-text")
        yield Footer()

    def on_mount(self) -> None:
        """Initialize game when screen mounts."""
        self.initialize_game()

    @work(thread=True)
    def initialize_game(self) -> None:
        """Initialize the game engine and opponent."""
        repo = get_scenario_repository()
        self.game = create_game(self.scenario_id, repo)
        self.opponent = get_opponent_by_type(self.opponent_type)
        self.app.call_from_thread(self.update_display)

    def update_display(self) -> None:
        """Update all display elements."""
        if not self.game:
            return

        state = self.game.get_current_state()

        # Update header bar
        header = self.query_one("#header-bar", Static)
        act_str = {1: "Act I", 2: "Act II", 3: "Act III"}.get(state.act, f"Act {state.act}")
        header.update(
            f"Turn {state.turn} | Risk: {state.risk_level:.1f} | "
            f"Coop: {state.cooperation_score:.1f} | Stability: {state.stability:.1f} | {act_str}"
        )

        # Update briefing
        briefing_text = self.query_one("#briefing-text", Static)
        briefing = self.game.get_briefing()
        if briefing:
            briefing_text.update(briefing)
        else:
            briefing_text.update("The situation develops...")

        # Update your status (exact values - you are player A)
        self.query_one("#your-position", Static).update(f"Position: {state.position_a:.1f}")
        self.query_one("#your-resources", Static).update(f"Resources: {state.resources_a:.1f}")

        # Update intelligence on opponent (with uncertainty)
        info_state = self.game.get_information_state("A")
        self._update_intel_display(info_state, state.turn)

        # Update available actions
        self.available_actions = self.game.get_available_actions("A")
        self._update_action_list()

        # Update history
        self._update_history()

    def _update_intel_display(self, info: InformationState, current_turn: int) -> None:
        """Update intelligence display with uncertainty bounds."""
        pos_display = self.query_one("#intel-position", Static)
        res_display = self.query_one("#intel-resources", Static)

        # Position intelligence
        if info.known_position is not None and info.known_position_turn is not None:
            estimate, uncertainty = info.get_position_estimate(current_turn)
            turns_stale = current_turn - info.known_position_turn
            if uncertainty >= 5.0:
                pos_display.update(f"Position: STALE (was {info.known_position:.1f} on T{info.known_position_turn})")
                pos_display.add_class("intel-stale")
            else:
                low = max(0, estimate - uncertainty)
                high = min(10, estimate + uncertainty)
                pos_display.update(
                    f"Position: ~{estimate:.1f} ±{uncertainty:.1f} ({low:.1f}-{high:.1f})\n"
                    f"  Last recon: Turn {info.known_position_turn} ({turns_stale} turns stale)"
                )
                pos_display.remove_class("intel-stale")
                pos_display.remove_class("intel-unknown")
        else:
            pos_display.update("Position: UNKNOWN (no reconnaissance data)")
            pos_display.add_class("intel-unknown")

        # Resources intelligence
        if info.known_resources is not None and info.known_resources_turn is not None:
            estimate, uncertainty = info.get_resources_estimate(current_turn)
            turns_stale = current_turn - info.known_resources_turn
            if uncertainty >= 5.0:
                res_display.update(f"Resources: STALE (was {info.known_resources:.1f} on T{info.known_resources_turn})")
                res_display.add_class("intel-stale")
            else:
                low = max(0, estimate - uncertainty)
                high = min(10, estimate + uncertainty)
                res_display.update(
                    f"Resources: ~{estimate:.1f} ±{uncertainty:.1f} ({low:.1f}-{high:.1f})\n"
                    f"  Last inspection: Turn {info.known_resources_turn} ({turns_stale} turns stale)"
                )
                res_display.remove_class("intel-stale")
                res_display.remove_class("intel-unknown")
        else:
            res_display.update("Resources: UNKNOWN (no inspection data)")
            res_display.add_class("intel-unknown")

    # Mechanics hints for cooperative actions by category
    _COOP_HINTS = {
        ActionCategory.SETTLEMENT: "Negotiate end",
        ActionCategory.RECONNAISSANCE: "Learn position",
        ActionCategory.INSPECTION: "Learn resources",
        ActionCategory.COSTLY_SIGNALING: "Signal strength",
    }

    def _update_action_list(self) -> None:
        """Update the action list display with narrative descriptions and mechanics hints."""
        action_list = self.query_one("#action-list", OptionList)
        action_list.clear_options()

        for i, action in enumerate(self.available_actions):
            is_coop = action.action_type == ActionType.COOPERATIVE
            hint = self._COOP_HINTS.get(action.category, "Builds trust") if is_coop else "Risk +, position?"
            icon = "\u2764" if is_coop else "\u2694"  # heart or sword
            cost_str = f" | {action.resource_cost:.1f}R" if action.resource_cost > 0 else ""

            label = f"[{i+1}] {icon} {action.name}\n     {hint}{cost_str}"
            action_list.add_option(Option(label, id=str(i)))

    def _update_history(self) -> None:
        """Update the history bar."""
        history_text = self.query_one("#history-text", Static)
        if self.turn_history:
            history_text.update(" | ".join(self.turn_history[-10:]))  # Show last 10 turns
        else:
            history_text.update("No history yet")

    @on(OptionList.OptionSelected, "#action-list")
    def action_selected(self, event: OptionList.OptionSelected) -> None:
        """Handle action selection from the list."""
        action_index = int(str(event.option.id))
        self._execute_action(action_index)

    def _select_action(self, index: int) -> None:
        """Select an action by number."""
        if 0 <= index < len(self.available_actions):
            self._execute_action(index)

    def action_select_action_1(self) -> None:
        self._select_action(0)

    def action_select_action_2(self) -> None:
        self._select_action(1)

    def action_select_action_3(self) -> None:
        self._select_action(2)

    def action_select_action_4(self) -> None:
        self._select_action(3)

    def action_select_action_5(self) -> None:
        self._select_action(4)

    def action_select_action_6(self) -> None:
        self._select_action(5)

    def action_select_action_7(self) -> None:
        self._select_action(6)

    def action_select_action_8(self) -> None:
        self._select_action(7)

    def action_select_action_9(self) -> None:
        self._select_action(8)

    def _execute_action(self, action_index: int) -> None:
        """Execute the selected action."""
        if not self.game or not self.opponent:
            return

        if action_index >= len(self.available_actions):
            return

        player_action = self.available_actions[action_index]

        # Check if this is a settlement proposal
        if player_action.category == ActionCategory.SETTLEMENT:
            self.app.push_screen(SettlementProposalModal(self.game, self.opponent))
            return

        # Get opponent's action
        state = self.game.get_current_state()
        opponent_actions = self.game.get_available_actions("B")
        opponent_action = self.opponent.choose_action(state, opponent_actions)

        # Submit actions
        result = self.game.submit_actions(player_action, opponent_action)

        if result.success:
            # Update history
            if result.action_result:
                code = result.action_result.outcome_code
                self.turn_history.append(f"T{state.turn}:{code}")

            # Show result narrative
            if result.narrative:
                self.notify(result.narrative, timeout=5)

            # Check if game ended
            if result.ending:
                self.app.push_screen(EndGameScreen(result.ending, self.game, self.opponent_type))
                return

            # Update display for new turn
            self.update_display()
        else:
            self.notify(f"Action failed: {result.error}", severity="error")

    def action_propose_settlement(self) -> None:
        """Open settlement proposal modal."""
        if self.game and self.opponent:
            # Check if settlement is available
            menu = self.game.get_action_menu("A")
            if menu.can_propose_settlement:
                self.app.push_screen(SettlementProposalModal(self.game, self.opponent))
            else:
                self.notify("Settlement not available (requires Turn > 4 and Stability > 2)", severity="warning")

    def action_confirm_quit(self) -> None:
        """Confirm quitting the game."""
        self.notify("Press Q again to quit, or continue playing", severity="warning")
        self.app.pop_screen()


class SettlementProposalModal(Screen):
    """Modal screen for proposing a settlement."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    def __init__(self, game: GameEngine, opponent: Opponent) -> None:
        super().__init__()
        self.game = game
        self.opponent = opponent
        self._suggested_vp: int = 50

    def compose(self) -> ComposeResult:
        state = self.game.get_current_state()

        # Calculate suggested VP based on position
        total_pos = state.position_a + state.position_b
        if total_pos > 0:
            suggested = int((state.position_a / total_pos) * 100)
        else:
            suggested = 50

        # Apply cooperation bonus
        coop_bonus = int((state.cooperation_score - 5) * 2)
        suggested = max(20, min(80, suggested + coop_bonus))
        self._suggested_vp = suggested

        # Calculate valid range
        min_vp = max(20, suggested - 10)
        max_vp = min(80, suggested + 10)

        with Container(id="settlement-modal"):
            with Vertical(classes="modal-container"):
                yield Static("PROPOSE SETTLEMENT", classes="modal-title")
                yield Rule()
                yield Static(f"Your suggested VP: {suggested} (based on position)")
                yield Static(f"Valid range: {min_vp}-{max_vp}")
                yield Rule()
                yield Static("Enter VP for yourself:", classes="input-label")
                yield Input(value=str(suggested), id="vp-input", type="integer")
                yield Static("Settlement argument (max 500 chars):", classes="input-label")
                yield TextArea(id="argument-input")
                with Horizontal(classes="button-row"):
                    yield Button("Submit", id="submit", variant="success")
                    yield Button("Cancel", id="cancel", variant="default")

    @on(Button.Pressed, "#submit")
    def submit_proposal(self) -> None:
        """Submit the settlement proposal."""
        vp_input = self.query_one("#vp-input", Input)
        argument_input = self.query_one("#argument-input", TextArea)

        try:
            offered_vp = int(vp_input.value)
        except ValueError:
            self.notify("Invalid VP value", severity="error")
            return

        # Validate range
        min_vp = max(20, self._suggested_vp - 10)
        max_vp = min(80, self._suggested_vp + 10)

        if not (min_vp <= offered_vp <= max_vp):
            self.notify(f"VP must be between {min_vp} and {max_vp}", severity="error")
            return

        argument = argument_input.text[:500]

        # Create proposal
        proposal = SettlementProposal(offered_vp=offered_vp, argument=argument)

        # Get opponent response
        state = self.game.get_current_state()
        response = self.opponent.evaluate_settlement(proposal, state, is_final_offer=False)

        # Handle response
        if response.action == "accept":
            # Settlement accepted - game ends
            from brinksmanship.engine.game_engine import EndingType, GameEnding

            vp_a = offered_vp
            vp_b = 100 - offered_vp
            ending = GameEnding(
                ending_type=EndingType.SETTLEMENT,
                vp_a=float(vp_a),
                vp_b=float(vp_b),
                turn=state.turn,
                description=f"Settlement accepted. Player A: {vp_a} VP, Player B: {vp_b} VP",
            )
            self.game.ending = ending
            self.app.pop_screen()  # Remove modal
            self.app.push_screen(EndGameScreen(ending, self.game, ""))
        elif response.action == "counter":
            # Show counter-proposal
            self.notify(
                f"Opponent counters with {response.counter_vp} VP: {response.counter_argument or 'No argument'}",
                timeout=8,
            )
            self.app.pop_screen()
        else:
            # Rejected
            self.notify(f"Settlement rejected: {response.rejection_reason or 'No reason given'}", severity="warning")
            # Risk +1 for failed settlement
            self.app.pop_screen()

    @on(Button.Pressed, "#cancel")
    def cancel(self) -> None:
        """Cancel the settlement proposal."""
        self.app.pop_screen()

    def action_cancel(self) -> None:
        self.app.pop_screen()


class EndGameScreen(Screen):
    """Screen showing game results."""

    BINDINGS = [
        Binding("c", "show_coaching", "View Coaching"),
        Binding("m", "main_menu", "Main Menu"),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self, ending: GameEnding, game: GameEngine, opponent_type: str) -> None:
        super().__init__()
        self.ending = ending
        self.game = game
        self.opponent_type = opponent_type

    def compose(self) -> ComposeResult:
        yield Header()
        with Container(id="main-menu"):
            with Vertical(classes="menu-container"):
                yield Static("GAME OVER", classes="menu-title")
                yield Rule()

                # Ending type description
                ending_name = self.ending.ending_type.value.replace("_", " ").title()
                yield Static(f"Ending: {ending_name}")
                yield Static(f"Turn: {self.ending.turn}")
                yield Rule()

                # VP Display
                yield Static(f"Your VP: {self.ending.vp_a:.1f}", classes="vp-display vp-a")
                yield Static(f"Opponent VP: {self.ending.vp_b:.1f}", classes="vp-display vp-b")
                yield Rule()

                # Description
                yield Static(self.ending.description)
                yield Rule()

                # Buttons
                yield Button("View Coaching Analysis", id="coaching", variant="primary", classes="menu-button")
                yield Button("Main Menu", id="main-menu-btn", variant="default", classes="menu-button")
                yield Button("Quit", id="quit", variant="error", classes="menu-button")
        yield Footer()

    @on(Button.Pressed, "#coaching")
    def show_coaching(self) -> None:
        self.app.push_screen(CoachingScreen(self.game, self.opponent_type))

    @on(Button.Pressed, "#main-menu-btn")
    def go_to_main_menu(self) -> None:
        # Pop all screens and show main menu
        while len(self.app.screen_stack) > 1:
            self.app.pop_screen()

    @on(Button.Pressed, "#quit")
    def quit_app(self) -> None:
        self.app.exit()

    def action_show_coaching(self) -> None:
        self.show_coaching()

    def action_main_menu(self) -> None:
        self.go_to_main_menu()

    def action_quit(self) -> None:
        self.app.exit()


class CoachingScreen(Screen):
    """Screen showing post-game coaching analysis."""

    BINDINGS = [
        Binding("escape", "go_back", "Back"),
        Binding("m", "main_menu", "Main Menu"),
    ]

    def __init__(self, game: GameEngine, opponent_type: str) -> None:
        super().__init__()
        self.game = game
        self.opponent_type = opponent_type
        self._coaching_report: Optional["CoachingReport"] = None

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll():
            yield Static("POST-GAME COACHING", classes="menu-title")
            yield Rule()
            yield Static("Loading analysis...", id="coaching-content")
        yield Footer()

    def on_mount(self) -> None:
        """Load coaching analysis when screen mounts."""
        self.load_coaching()

    @work(thread=True)
    def load_coaching(self) -> None:
        """Load coaching analysis asynchronously."""
        content = self._generate_coaching_content()
        self.app.call_from_thread(self._update_coaching_display, content)

    def _generate_coaching_content(self) -> str:
        """Generate coaching content from game history."""
        history = self.game.get_history()
        ending = self.game.get_ending()

        lines = []

        # Overall assessment
        lines.append("## Overall Assessment\n")
        if ending:
            if ending.vp_a > 60:
                lines.append("**Strong Victory** - You achieved a decisive advantage.\n")
            elif ending.vp_a > 50:
                lines.append("**Marginal Victory** - You came out slightly ahead.\n")
            elif ending.vp_a > 40:
                lines.append("**Marginal Loss** - Your opponent had a slight edge.\n")
            else:
                lines.append("**Significant Loss** - Review your strategy carefully.\n")

        # Turn-by-turn summary
        lines.append("\n## Turn History\n")
        for record in history:
            if record.action_a and record.action_b and record.outcome:
                lines.append(
                    f"- **Turn {record.turn}**: {record.action_a.name} vs {record.action_b.name} "
                    f"→ {record.outcome.outcome_code}\n"
                )

        # Key insights
        lines.append("\n## Key Insights\n")

        # Analyze cooperation patterns
        coop_count = sum(1 for r in history if r.outcome and r.outcome.is_mutual_cooperation)
        comp_count = sum(1 for r in history if r.outcome and r.outcome.is_mutual_defection)
        total = len(history)

        if total > 0:
            lines.append(f"- Mutual cooperation rate: {coop_count}/{total} ({100*coop_count/total:.0f}%)\n")
            lines.append(f"- Mutual competition rate: {comp_count}/{total} ({100*comp_count/total:.0f}%)\n")

        # Recommendations
        lines.append("\n## Recommendations\n")
        if coop_count < total * 0.3:
            lines.append("- Consider using more cooperative strategies to build trust\n")
        if comp_count > total * 0.5:
            lines.append("- High competition led to instability - balance risk vs reward\n")

        lines.append(f"\n*Opponent type: {self.opponent_type.replace('_', ' ').title()}*\n")

        return "".join(lines)

    def _update_coaching_display(self, content: str) -> None:
        """Update the coaching display with content."""
        coaching_content = self.query_one("#coaching-content", Static)
        coaching_content.update(content)

    def action_go_back(self) -> None:
        self.app.pop_screen()

    def action_main_menu(self) -> None:
        while len(self.app.screen_stack) > 1:
            self.app.pop_screen()


# =============================================================================
# Main Application
# =============================================================================


class BrinksmanshipApp(App):
    """Main Brinksmanship CLI application."""

    TITLE = "Brinksmanship"
    SUB_TITLE = "A Game-Theoretic Strategy Simulation"
    CSS = CSS

    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit", show=True, priority=True),
    ]

    def on_mount(self) -> None:
        """Show main menu when app starts."""
        self.push_screen(MainMenuScreen())


def main() -> None:
    """Entry point for the CLI application."""
    app = BrinksmanshipApp()
    app.run()


if __name__ == "__main__":
    main()
