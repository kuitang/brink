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
import inspect
from dataclasses import dataclass
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
from brinksmanship.cli.trace import TraceLogger

if TYPE_CHECKING:
    from brinksmanship.coaching.post_game import CoachingReport


# =============================================================================
# Helpers for async/sync opponent method handling
# =============================================================================


def run_opponent_method(method, *args, **kwargs):
    """Run an opponent method, handling both sync and async implementations.

    This must be called from a worker thread, not the main event loop.
    For async methods, uses asyncio.run() which is safe in a thread.
    For sync methods that internally use asyncio.run() (like HistoricalPersona),
    this also works correctly since we're in a separate thread.
    """
    if inspect.iscoroutinefunction(method):
        return asyncio.run(method(*args, **kwargs))
    return method(*args, **kwargs)


@dataclass
class ActionExecutionResult:
    """Result of executing an action in a worker thread."""

    success: bool
    turn_history_entry: Optional[str] = None
    narrative: Optional[str] = None
    ending: Optional[GameEnding] = None
    error: Optional[str] = None
    # For trace logging
    human_action: Optional[Action] = None
    opponent_action: Optional[Action] = None
    turn_result: Optional[TurnResult] = None
    state_after: Optional[GameState] = None


@dataclass
class SettlementExecutionResult:
    """Result of settlement proposal evaluation."""

    response: Optional[SettlementResponse] = None
    error: Optional[str] = None


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

#status-bar {
    dock: top;
    height: 1;
    background: $primary-darken-2;
    color: $text;
    padding: 0 1;
}

.history-title {
    text-style: bold;
    color: $success;
}

#latest-entry {
    border: heavy $warning;
    background: $surface-lighten-1;
    padding: 1;
    margin-bottom: 1;
    min-height: 4;
}

#latest-entry-header {
    text-style: bold;
    color: $warning;
}

#latest-entry-narrative {
    color: $text;
    text-style: italic;
    margin-top: 1;
}

#older-entries {
    height: 1fr;
}

.older-entry {
    color: $text-muted;
    margin-bottom: 1;
}

.history-turn-header {
    text-style: bold;
    color: $text;
}

.history-narrative {
    color: $text-muted;
    text-style: italic;
}

#game-content {
    height: 1fr;
}

#briefing-panel {
    width: 100%;
    min-height: 6;
    height: auto;
    max-height: 14;
    border: solid $primary;
    padding: 1 1;
}

#state-row {
    width: 100%;
    height: 4;
    layout: horizontal;
}

.state-box {
    width: 1fr;
    height: 100%;
    border: solid $secondary;
    padding: 0 1;
}

.state-box-player {
    border: solid $success;
}

.state-box-opponent {
    border: solid $error;
}

.state-box-shared {
    border: solid $warning;
}

.state-box-header {
    text-style: bold;
    color: $text-muted;
}

.state-box-values {
    layout: horizontal;
}

.state-item {
    width: 1fr;
}

.state-label {
    color: $text-muted;
}

.state-value {
    text-style: bold;
}

#bottom-row {
    height: 1fr;
    layout: horizontal;
}

#history-panel {
    width: 1fr;
    border: solid $success;
    padding: 0 1;
}

#actions-panel {
    width: 1fr;
    border: solid $primary;
    padding: 0 1;
}

.info-panel {
    border: solid $secondary;
    padding: 1;
    margin-bottom: 1;
}

.info-header {
    text-style: bold;
    margin-bottom: 1;
}

.player-info {
    border-left: wide $success;
}

.opponent-info {
    border-left: wide $error;
}

.shared-info {
    border-left: wide $warning;
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

#loading-modal {
    align: center middle;
    background: $surface 80%;
}

.loading-container {
    width: 50;
    height: 9;
    border: double $warning;
    background: $surface;
    padding: 2;
}

.loading-text {
    text-align: center;
    text-style: bold;
    color: $warning;
    margin-bottom: 1;
}

.loading-subtext {
    text-align: center;
    color: $text-muted;
}

.loading-spinner {
    text-align: center;
    color: $primary;
    text-style: bold;
}
"""


# =============================================================================
# Screens
# =============================================================================


class LoadingModal(Screen):
    """Modal showing a loading/thinking indicator with animation."""

    def __init__(self, message: str = "Opponent is thinking...") -> None:
        super().__init__()
        self.message = message
        self._spinner_frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        self._frame_index = 0
        self._dots = 0

    def compose(self) -> ComposeResult:
        with Container(id="loading-modal"):
            with Vertical(classes="loading-container"):
                yield Static(self.message, classes="loading-text")
                yield Static("Please wait...", id="subtext", classes="loading-subtext")
                yield Static("⠋", id="spinner", classes="loading-spinner")

    def on_mount(self) -> None:
        """Start spinner animation."""
        self.set_interval(0.08, self._update_spinner)

    def _update_spinner(self) -> None:
        """Animate the spinner."""
        self._frame_index = (self._frame_index + 1) % len(self._spinner_frames)
        self._dots = (self._dots + 1) % 4
        spinner = self.query_one("#spinner", Static)
        dots = "." * self._dots + " " * (3 - self._dots)
        spinner.update(f"{self._spinner_frames[self._frame_index]}  Processing{dots}")


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
        self.app.push_screen(SideSelectScreen(self.scenario_id, opponent_type))

    @on(Button.Pressed, "#back")
    def go_back(self) -> None:
        self.app.pop_screen()

    def action_go_back(self) -> None:
        self.app.pop_screen()


class SideSelectScreen(Screen):
    """Screen for selecting which side (Player A or B) to play."""

    BINDINGS = [
        Binding("escape", "go_back", "Back"),
    ]

    def __init__(self, scenario_id: str, opponent_type: str) -> None:
        super().__init__()
        self.scenario_id = scenario_id
        self.opponent_type = opponent_type
        self.scenario: dict | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Container(id="main-menu"):
            with Vertical(classes="menu-container"):
                yield Static("CHOOSE YOUR SIDE", classes="menu-title")
                yield Rule()
                yield Static("", id="side-description")
                yield Rule()
                yield OptionList(id="side-list")
                yield Rule()
                yield Button("Back", id="back", variant="default")
        yield Footer()

    def on_mount(self) -> None:
        """Load scenario roles when screen mounts."""
        repo = get_scenario_repository()
        self.scenario = repo.get_scenario(self.scenario_id)

        option_list = self.query_one("#side-list", OptionList)
        description = self.query_one("#side-description", Static)

        if self.scenario:
            # Get role information
            player_a_name = self.scenario.get("player_a_name", "Player A")
            player_a_role = self.scenario.get("player_a_role", "Side A")
            player_b_name = self.scenario.get("player_b_name", "Player B")
            player_b_role = self.scenario.get("player_b_role", "Side B")

            description.update(
                f"Scenario: {self.scenario.get('name', self.scenario_id)}\n\n"
                f"Choose which side you want to play:"
            )

            option_list.add_option(Option(
                f"{player_a_name} ({player_a_role})",
                id="player_a"
            ))
            option_list.add_option(Option(
                f"{player_b_name} ({player_b_role})",
                id="player_b"
            ))
        else:
            description.update("Choose your side:")
            option_list.add_option(Option("Player A", id="player_a"))
            option_list.add_option(Option("Player B", id="player_b"))

    @on(OptionList.OptionSelected)
    def side_selected(self, event: OptionList.OptionSelected) -> None:
        human_is_player_a = str(event.option.id) == "player_a"
        self.app.push_screen(GameScreen(
            self.scenario_id,
            self.opponent_type,
            human_is_player_a=human_is_player_a,
        ))

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

    def __init__(
        self,
        scenario_id: str,
        opponent_type: str,
        human_is_player_a: bool = True,
    ) -> None:
        super().__init__()
        self.scenario_id = scenario_id
        self.opponent_type = opponent_type
        self.human_is_player_a = human_is_player_a
        self.human_player = "A" if human_is_player_a else "B"
        self.opponent_player = "B" if human_is_player_a else "A"
        self.game: Optional[GameEngine] = None
        self.opponent: Optional[Opponent] = None
        self.available_actions: list[Action] = []
        self.turn_history: list[str] = []
        self._last_checked_turn: int = 0  # Track which turn we checked for opponent settlement
        self._settlement_check_in_progress: bool = False  # Prevent concurrent checks
        self._pending_opponent_proposal: Optional[SettlementProposal] = None
        # Initialize trace logger
        self.trace_logger = TraceLogger(
            scenario_id=scenario_id,
            opponent_type=opponent_type,
            human_player=self.human_player,
        )

    def compose(self) -> ComposeResult:
        yield Header()
        # Status bar at top
        yield Static("Turn 1 | Act I", id="status-bar")

        with Vertical(id="game-content"):
            # Briefing panel - full width at top
            with VerticalScroll(id="briefing-panel"):
                yield Static("BRIEFING", classes="panel-title")
                yield Static("Loading...", id="briefing-text")

            # State row - shared state only (positions are hidden per game design)
            # Players learn outcomes from history narratives, not raw numbers
            with Horizontal(id="state-row"):
                with Vertical(classes="state-box state-box-shared", id="crisis-status"):
                    yield Static("CRISIS STATUS", classes="state-box-header")
                    yield Static("Risk: -- Coop: -- Stab: -- Turn: --", id="shared-stats")

            # Bottom row: history and actions side by side
            with Horizontal(id="bottom-row"):
                with Vertical(id="history-panel"):
                    yield Static("CRISIS LOG", classes="history-title")
                    # Latest entry container - prominently styled
                    with Vertical(id="latest-entry"):
                        yield Static("Awaiting first action...", id="latest-entry-header")
                        yield Static("", id="latest-entry-narrative")
                    # Older entries in scrollable area
                    with VerticalScroll(id="older-entries"):
                        yield Static("", id="older-entries-content")
                with Vertical(id="actions-panel"):
                    yield Static("ACTIONS (1-9 to select)", classes="panel-title")
                    yield OptionList(id="action-list")

        yield Footer()

    def on_mount(self) -> None:
        """Initialize game when screen mounts."""
        self.initialize_game()

    @work(thread=True)
    def initialize_game(self) -> None:
        """Initialize the game engine and opponent."""
        repo = get_scenario_repository()
        self.game = create_game(self.scenario_id, repo)

        # Get scenario information for opponent role context
        # The opponent plays the opposite side of the human
        scenario = repo.get_scenario(self.scenario_id)
        role_name = None
        role_description = None
        if scenario:
            if self.human_is_player_a:
                # Human is A, opponent is B
                role_name = scenario.get("player_b_role")
                role_description = scenario.get("player_b_description")
            else:
                # Human is B, opponent is A
                role_name = scenario.get("player_a_role")
                role_description = scenario.get("player_a_description")

        self.opponent = get_opponent_by_type(
            self.opponent_type,
            is_player_a=not self.human_is_player_a,  # Opponent is opposite of human
            role_name=role_name,
            role_description=role_description,
        )
        self.app.call_from_thread(self.update_display)

    def update_display(self) -> None:
        """Update all display elements."""
        if not self.game:
            return

        state = self.game.get_current_state()

        # Update status bar - just turn and act
        status_bar = self.query_one("#status-bar", Static)
        act_str = {1: "Act I", 2: "Act II", 3: "Act III"}.get(state.act, f"Act {state.act}")
        status_bar.update(f"Turn {state.turn} | {act_str}")

        # Update briefing
        briefing_text = self.query_one("#briefing-text", Static)
        briefing = self.game.get_briefing()
        if briefing:
            briefing_text.update(briefing)
        else:
            briefing_text.update("The situation develops...")

        # Update shared stats only - positions are hidden per game design
        # Players learn outcomes from the history narratives
        self.query_one("#shared-stats", Static).update(
            f"Risk Level: {state.risk_level:.1f}/10    Cooperation: {state.cooperation_score:.1f}/10    Stability: {state.stability:.1f}/10    Turn: {state.turn}"
        )

        # Update available actions for human's side
        self.available_actions = self.game.get_available_actions(self.human_player)
        self._update_action_list()

        # Update history
        self._update_history()

        # Check if opponent wants to propose settlement (only once per turn, with lock)
        if (state.turn > self._last_checked_turn and
            state.turn > 4 and
            state.stability > 2 and
            not self._settlement_check_in_progress and
            self._pending_opponent_proposal is None):
            # Set flags BEFORE starting worker to prevent race
            self._last_checked_turn = state.turn
            self._settlement_check_in_progress = True
            self._check_opponent_settlement()

    @work(thread=True)
    def _check_opponent_settlement(self) -> None:
        """Check if opponent wants to propose settlement (runs in worker thread)."""
        if not self.game or not self.opponent:
            self.app.call_from_thread(self._clear_settlement_check_flag)
            return

        state = self.game.get_current_state()

        # Ask opponent if they want to propose settlement
        proposal = run_opponent_method(self.opponent.propose_settlement, state)

        if proposal is not None:
            # Opponent wants to propose - show response modal on main thread
            self.app.call_from_thread(self._show_opponent_settlement_proposal, proposal)
        else:
            # No proposal - clear the in-progress flag
            self.app.call_from_thread(self._clear_settlement_check_flag)

    def _clear_settlement_check_flag(self) -> None:
        """Clear the settlement check in-progress flag."""
        self._settlement_check_in_progress = False

    def _show_opponent_settlement_proposal(self, proposal: SettlementProposal) -> None:
        """Show the opponent's settlement proposal to the human."""
        # Check if a settlement modal is already showing
        if isinstance(self.app.screen, (SettlementProposalModal, SettlementResponseModal)):
            self._settlement_check_in_progress = False
            return

        self._pending_opponent_proposal = proposal
        self._settlement_check_in_progress = False  # Clear flag now that modal is being shown

        def handle_response(action: str, counter: Optional[SettlementProposal]) -> None:
            if action == "counter":
                # Human countered - now opponent decides on the counter
                self._handle_human_counter(counter)
            elif action == "reject":
                # Human rejected - Risk +1, continue turn
                self.notify("You rejected the settlement. Risk +1", severity="warning")
                # TODO: Actually apply Risk +1 to game state
                self._pending_opponent_proposal = None

        self.app.push_screen(SettlementResponseModal(
            self.game,
            proposal,
            human_is_player_a=self.human_is_player_a,
            is_final_offer=False,
            on_response=handle_response,
            trace_logger=self.trace_logger,
        ))

    @work(thread=True)
    def _handle_human_counter(self, counter: SettlementProposal) -> None:
        """Handle human's counter-proposal to opponent's settlement."""
        if not self.game or not self.opponent:
            return

        state = self.game.get_current_state()

        # Opponent evaluates human's counter-proposal
        response = run_opponent_method(
            self.opponent.evaluate_settlement, counter, state, False
        )

        self.app.call_from_thread(self._process_counter_response, response, counter)

    def _process_counter_response(
        self, response: SettlementResponse, counter: SettlementProposal
    ) -> None:
        """Process opponent's response to human's counter-proposal."""
        state = self.game.get_current_state()

        # Record the counter-proposal response
        if self.trace_logger:
            self.trace_logger.record_settlement_attempt(
                proposer="human",  # Human made the counter
                offered_vp=counter.offered_vp,
                argument=counter.argument or "",
                response=response.action,
                counter_vp=response.counter_vp if response.action == "counter" else None,
            )

        if response.action == "accept":
            # Opponent accepts human's counter
            if self.human_is_player_a:
                vp_a = counter.offered_vp
                vp_b = 100 - counter.offered_vp
            else:
                vp_b = counter.offered_vp
                vp_a = 100 - counter.offered_vp

            ending = GameEnding(
                ending_type=EndingType.SETTLEMENT,
                vp_a=float(vp_a),
                vp_b=float(vp_b),
                turn=state.turn,
                description=f"Settlement accepted. Player A: {vp_a} VP, Player B: {vp_b} VP",
            )
            self.game.ending = ending

            # Record ending in trace
            if self.trace_logger:
                self.trace_logger.record_ending(
                    ending_type=ending.ending_type.value,
                    vp_a=ending.vp_a,
                    vp_b=ending.vp_b,
                    description=ending.description,
                )

            self.app.push_screen(EndGameScreen(ending, self.game, self.opponent_type))

        elif response.action == "counter":
            # Opponent makes final offer
            final_offer = SettlementProposal(
                offered_vp=response.counter_vp,
                argument=response.counter_argument,
            )
            self.notify("Opponent makes a FINAL OFFER", timeout=3)

            def handle_final(action: str, _: Optional[SettlementProposal]) -> None:
                if action == "reject":
                    self.notify("Final offer rejected. Risk +1", severity="warning")
                # Accept is handled in the modal itself

            self.app.push_screen(SettlementResponseModal(
                self.game,
                final_offer,
                human_is_player_a=self.human_is_player_a,
                is_final_offer=True,
                on_response=handle_final,
                trace_logger=self.trace_logger,
            ))
        else:
            # Opponent rejects - settlement fails
            self.notify(
                f"Opponent rejects your counter: {response.rejection_reason or 'No reason'}. Risk +1",
                severity="warning"
            )
            self._pending_opponent_proposal = None

    # Mechanics hints for cooperative actions by category
    _COOP_HINTS = {
        ActionCategory.SETTLEMENT: "Negotiate end",
        ActionCategory.RECONNAISSANCE: "Learn position",
        ActionCategory.INSPECTION: "Learn resources",
        ActionCategory.COSTLY_SIGNALING: "Signal strength",
    }

    def _update_action_list(self) -> None:
        """Update the action list display with narrative descriptions and mechanics hints.

        Multiple actions of each type (C/D) offer strategic variety:
        - Different resource costs
        - Different risk/position impacts
        - Different narrative effects
        """
        action_list = self.query_one("#action-list", OptionList)
        action_list.clear_options()

        # Group actions by type for clarity
        coop_actions = [(i, a) for i, a in enumerate(self.available_actions) if a.action_type == ActionType.COOPERATIVE]
        comp_actions = [(i, a) for i, a in enumerate(self.available_actions) if a.action_type == ActionType.COMPETITIVE]

        # Add competitive actions first (more impactful)
        for i, action in comp_actions:
            hint = f"COMPETITIVE - Risk ↑, may gain position"
            cost_str = f" | Cost: {action.resource_cost:.1f}R" if action.resource_cost > 0 else ""
            label = f"[{i+1}] ⚔ {action.name}\n     {hint}{cost_str}"
            action_list.add_option(Option(label, id=str(i)))

        # Add cooperative actions
        for i, action in coop_actions:
            hint = self._COOP_HINTS.get(action.category, "COOPERATIVE - Builds trust, reduces risk")
            cost_str = f" | Cost: {action.resource_cost:.1f}R" if action.resource_cost > 0 else ""
            label = f"[{i+1}] ❤ {action.name}\n     {hint}{cost_str}"
            action_list.add_option(Option(label, id=str(i)))

    def _update_history(self) -> None:
        """Update the history panel with detailed turn-by-turn history including narratives.

        Uses separate Textual widgets for the latest entry (prominently styled) and
        older entries to create a clean visual distinction.
        """
        latest_header = self.query_one("#latest-entry-header", Static)
        latest_narrative = self.query_one("#latest-entry-narrative", Static)
        older_content = self.query_one("#older-entries-content", Static)

        if self.turn_history:
            # Parse the latest entry
            latest = self.turn_history[-1]
            latest_lines = latest.split("\n")

            # First line is the turn summary (e.g., "Turn 1: You (C) vs Opponent (D) → CD")
            header = latest_lines[0] if latest_lines else "Latest turn"
            # Remaining lines are the narrative
            narrative = "\n".join(line.strip() for line in latest_lines[1:] if line.strip())

            latest_header.update(f"★ {header}")
            latest_narrative.update(narrative if narrative else "")

            # Build older entries (all except the latest)
            if len(self.turn_history) > 1:
                older_lines = []
                for entry in reversed(self.turn_history[:-1]):
                    entry_lines = entry.split("\n")
                    older_lines.append(entry_lines[0])  # Turn header
                    for line in entry_lines[1:]:
                        if line.strip():
                            older_lines.append(f"  {line.strip()}")
                    older_lines.append("")  # Separator
                older_content.update("\n".join(older_lines))
            else:
                older_content.update("")
        else:
            latest_header.update("Awaiting first action...")
            latest_narrative.update("Press a number key (1-9) to select an action.")
            older_content.update("")

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
        """Execute the selected action (dispatches to worker thread)."""
        if not self.game or not self.opponent:
            return

        if action_index >= len(self.available_actions):
            return

        player_action = self.available_actions[action_index]

        # Check if this is a settlement proposal
        if player_action.category == ActionCategory.SETTLEMENT:
            self.app.push_screen(SettlementProposalModal(
                self.game,
                self.opponent,
                human_is_player_a=self.human_is_player_a,
                trace_logger=self.trace_logger,
            ))
            return

        # Show loading modal while opponent thinks
        self.app.push_screen(LoadingModal("Opponent is thinking..."))

        # Run the action execution in a worker thread to avoid blocking the event loop
        # This is necessary because opponent.choose_action may use asyncio.run() internally
        self._execute_action_worker(player_action)

    @work(thread=True)
    def _execute_action_worker(self, human_action: Action) -> None:
        """Execute action in worker thread (handles async opponent methods)."""
        state = self.game.get_current_state()

        # Record state before turn for trace
        self.trace_logger.start_turn(state)

        opponent_actions = self.game.get_available_actions(self.opponent_player)

        # Get opponent's action - this may call asyncio.run() internally
        opponent_action = run_opponent_method(
            self.opponent.choose_action, state, opponent_actions
        )

        # Validate opponent action is in available actions - if not, use first valid action
        if opponent_action not in opponent_actions:
            # LLM might have returned invalid action - fall back to first available
            opponent_action = opponent_actions[0] if opponent_actions else None
            if opponent_action is None:
                exec_result = ActionExecutionResult(
                    success=False,
                    error="Opponent has no valid actions available"
                )
                self.app.call_from_thread(self._handle_action_result, exec_result)
                return

        # Submit actions in correct order (action_a, action_b)
        if self.human_is_player_a:
            result = self.game.submit_actions(human_action, opponent_action)
        else:
            result = self.game.submit_actions(opponent_action, human_action)

        # Get state after turn for trace
        state_after = self.game.get_current_state()

        # Build result for main thread
        exec_result = ActionExecutionResult(success=result.success)
        if result.success:
            if result.action_result:
                # Create detailed history entry with full narrative
                you_type = "C" if human_action.action_type == ActionType.COOPERATIVE else "D"
                opp_type = "C" if opponent_action.action_type == ActionType.COOPERATIVE else "D"
                narrative_text = ""
                if result.narrative:
                    narrative_text = f"\n        {result.narrative}"
                exec_result.turn_history_entry = (
                    f"Turn {state.turn}: You ({you_type}) vs Opponent ({opp_type}) → {result.action_result.outcome_code}"
                    f"{narrative_text}"
                )
            exec_result.narrative = result.narrative
            exec_result.ending = result.ending
            # Add trace data
            exec_result.human_action = human_action
            exec_result.opponent_action = opponent_action
            exec_result.turn_result = result
            exec_result.state_after = state_after
        else:
            exec_result.error = result.error

        # Update UI from main thread
        self.app.call_from_thread(self._handle_action_result, exec_result)

    def _handle_action_result(self, result: ActionExecutionResult) -> None:
        """Handle action result on main thread."""
        # Dismiss the loading modal (only if it's still the current screen)
        # Don't pop if a settlement modal was pushed on top
        current_screen = self.app.screen
        if isinstance(current_screen, LoadingModal):
            self.app.pop_screen()
        elif current_screen is not self:
            # Something else is on top - might be a settlement modal, leave it
            pass

        if result.success:
            # Record turn in trace
            if result.human_action and result.opponent_action and result.turn_result and result.state_after:
                self.trace_logger.record_turn(
                    human_action=result.human_action,
                    opponent_action=result.opponent_action,
                    result=result.turn_result,
                    state_after=result.state_after,
                    human_is_player_a=self.human_is_player_a,
                )

            if result.turn_history_entry:
                self.turn_history.append(result.turn_history_entry)

            # Narrative is already included in turn_history_entry, no need to notify

            if result.ending:
                # Record ending in trace
                self.trace_logger.record_ending(
                    ending_type=result.ending.ending_type.value,
                    vp_a=result.ending.vp_a,
                    vp_b=result.ending.vp_b,
                    description=result.ending.description,
                )
                # Show trace summary
                trace_summary = self.trace_logger.get_summary()
                self.notify(f"Trace saved: {self.trace_logger._output_file}", timeout=10)
                self.app.push_screen(EndGameScreen(result.ending, self.game, self.opponent_type))
                return

            self.update_display()
        else:
            self.notify(f"Action failed: {result.error}", severity="error")

    def action_propose_settlement(self) -> None:
        """Open settlement proposal modal."""
        if self.game and self.opponent:
            # Check if settlement is available for human's side
            menu = self.game.get_action_menu(self.human_player)
            if menu.can_propose_settlement:
                self.app.push_screen(SettlementProposalModal(
                    self.game,
                    self.opponent,
                    human_is_player_a=self.human_is_player_a,
                    trace_logger=self.trace_logger,
                ))
            else:
                self.notify("Settlement not available (requires Turn > 4 and Stability > 2)", severity="warning")

    def action_confirm_quit(self) -> None:
        """Return to main menu (abandons current game)."""
        # Pop all screens back to main menu (keep base Screen + MainMenuScreen)
        while len(self.app.screen_stack) > 2:
            self.app.pop_screen()


class SettlementProposalModal(Screen):
    """Modal screen for proposing a settlement."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    def __init__(
        self,
        game: GameEngine,
        opponent: Opponent,
        human_is_player_a: bool = True,
        trace_logger: Optional["TraceLogger"] = None,
    ) -> None:
        super().__init__()
        self.game = game
        self.opponent = opponent
        self.human_is_player_a = human_is_player_a
        self.trace_logger = trace_logger
        self._suggested_vp: int = 50

    def compose(self) -> ComposeResult:
        state = self.game.get_current_state()

        # Calculate suggested VP based on human's position
        if self.human_is_player_a:
            my_position = state.position_a
        else:
            my_position = state.position_b

        total_pos = state.position_a + state.position_b
        if total_pos > 0:
            suggested = int((my_position / total_pos) * 100)
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
                yield Static(f"Suggested VP: {suggested} (based on situation)")
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

        # Create proposal and run evaluation in worker thread
        proposal = SettlementProposal(offered_vp=offered_vp, argument=argument)
        self.notify("Evaluating settlement...", timeout=2)
        self._evaluate_settlement_worker(proposal, offered_vp, argument)

    @work(thread=True)
    def _evaluate_settlement_worker(self, proposal: SettlementProposal, offered_vp: int, argument: str) -> None:
        """Evaluate settlement in worker thread (handles async opponent methods)."""
        state = self.game.get_current_state()

        # Get opponent response - this may call asyncio.run() internally
        response = run_opponent_method(
            self.opponent.evaluate_settlement, proposal, state, False
        )

        # Handle response on main thread
        self.app.call_from_thread(self._handle_settlement_response, response, offered_vp, state.turn, argument)

    def _handle_settlement_response(
        self, response: SettlementResponse, offered_vp: int, turn: int, argument: str = ""
    ) -> None:
        """Handle settlement response on main thread."""
        # Record the settlement attempt
        if self.trace_logger:
            self.trace_logger.record_settlement_attempt(
                proposer="human",
                offered_vp=offered_vp,
                argument=argument,
                response=response.action,
                counter_vp=response.counter_vp if response.action == "counter" else None,
            )

        if response.action == "accept":
            # Settlement accepted - game ends
            vp_a = offered_vp
            vp_b = 100 - offered_vp
            ending = GameEnding(
                ending_type=EndingType.SETTLEMENT,
                vp_a=float(vp_a),
                vp_b=float(vp_b),
                turn=turn,
                description=f"Settlement accepted. Player A: {vp_a} VP, Player B: {vp_b} VP",
            )
            self.game.ending = ending

            # Record ending in trace
            if self.trace_logger:
                self.trace_logger.record_ending(
                    ending_type=ending.ending_type.value,
                    vp_a=ending.vp_a,
                    vp_b=ending.vp_b,
                    description=ending.description,
                )

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


class SettlementResponseModal(Screen):
    """Modal screen for responding to opponent's settlement proposal."""

    BINDINGS = [
        Binding("escape", "reject", "Reject"),
    ]

    def __init__(
        self,
        game: GameEngine,
        proposal: SettlementProposal,
        human_is_player_a: bool = True,
        is_final_offer: bool = False,
        on_response: callable = None,
        trace_logger: Optional["TraceLogger"] = None,
    ) -> None:
        super().__init__()
        self.game = game
        self.proposal = proposal
        self.human_is_player_a = human_is_player_a
        self.is_final_offer = is_final_offer
        self.on_response = on_response  # Callback for response
        self.trace_logger = trace_logger
        self._suggested_vp: int = 50

    def compose(self) -> ComposeResult:
        state = self.game.get_current_state()

        # Calculate what VP the human would get
        their_vp = self.proposal.offered_vp
        your_vp = 100 - their_vp

        # Calculate human's suggested counter VP
        if self.human_is_player_a:
            my_position = state.position_a
            opp_position = state.position_b
        else:
            my_position = state.position_b
            opp_position = state.position_a

        pos_diff = my_position - opp_position
        coop_bonus = int((state.cooperation_score - 5) * 2)
        suggested = int(50 + (pos_diff * 5) + coop_bonus)
        suggested = max(20, min(80, suggested))
        self._suggested_vp = suggested
        min_vp = max(20, suggested - 10)
        max_vp = min(80, suggested + 10)

        title = "OPPONENT'S FINAL OFFER" if self.is_final_offer else "OPPONENT PROPOSES SETTLEMENT"

        with Container(id="settlement-modal"):
            with Vertical(classes="modal-container"):
                yield Static(title, classes="modal-title")
                yield Rule()
                yield Static(f"Opponent offers: {their_vp} VP for them, {your_vp} VP for you")
                yield Rule()
                yield Static("Their argument:", classes="input-label")
                yield Static(self.proposal.argument or "(No argument provided)")
                yield Rule()

                if self.is_final_offer:
                    yield Static("This is a FINAL OFFER. You can only Accept or Reject.")
                    with Horizontal(classes="button-row"):
                        yield Button("Accept", id="accept", variant="success")
                        yield Button("Reject", id="reject", variant="error")
                else:
                    yield Static(f"Your suggested counter: {suggested} VP (range: {min_vp}-{max_vp})")
                    yield Static("Counter VP (for yourself):", classes="input-label")
                    yield Input(value=str(suggested), id="counter-vp-input", type="integer")
                    yield Static("Counter argument:", classes="input-label")
                    yield TextArea(id="counter-argument-input")
                    with Horizontal(classes="button-row"):
                        yield Button("Accept", id="accept", variant="success")
                        yield Button("Counter", id="counter", variant="primary")
                        yield Button("Reject", id="reject", variant="error")

    @on(Button.Pressed, "#accept")
    def accept_proposal(self) -> None:
        """Accept the opponent's proposal."""
        state = self.game.get_current_state()
        their_vp = self.proposal.offered_vp
        your_vp = 100 - their_vp

        if self.human_is_player_a:
            vp_a = your_vp
            vp_b = their_vp
        else:
            vp_a = their_vp
            vp_b = your_vp

        # Record settlement attempt (opponent proposed, human accepted)
        if self.trace_logger:
            self.trace_logger.record_settlement_attempt(
                proposer="opponent",
                offered_vp=self.proposal.offered_vp,
                argument=self.proposal.argument or "",
                response="accept",
            )

        ending = GameEnding(
            ending_type=EndingType.SETTLEMENT,
            vp_a=float(vp_a),
            vp_b=float(vp_b),
            turn=state.turn,
            description=f"Settlement accepted. Player A: {vp_a} VP, Player B: {vp_b} VP",
        )
        self.game.ending = ending

        # Record ending in trace
        if self.trace_logger:
            self.trace_logger.record_ending(
                ending_type=ending.ending_type.value,
                vp_a=ending.vp_a,
                vp_b=ending.vp_b,
                description=ending.description,
            )

        self.app.pop_screen()  # Remove modal
        self.app.push_screen(EndGameScreen(ending, self.game, ""))

    @on(Button.Pressed, "#counter")
    def counter_proposal(self) -> None:
        """Submit a counter-proposal."""
        counter_vp_input = self.query_one("#counter-vp-input", Input)
        counter_arg_input = self.query_one("#counter-argument-input", TextArea)

        try:
            counter_vp = int(counter_vp_input.value)
        except ValueError:
            self.notify("Invalid VP value", severity="error")
            return

        # Validate range
        min_vp = max(20, self._suggested_vp - 10)
        max_vp = min(80, self._suggested_vp + 10)

        if not (min_vp <= counter_vp <= max_vp):
            self.notify(f"VP must be between {min_vp} and {max_vp}", severity="error")
            return

        counter_argument = counter_arg_input.text[:500]

        # Record counter-proposal in trace
        if self.trace_logger:
            self.trace_logger.record_settlement_attempt(
                proposer="opponent",
                offered_vp=self.proposal.offered_vp,
                argument=self.proposal.argument or "",
                response="counter",
                counter_vp=counter_vp,
            )

        # Create counter-proposal
        counter = SettlementProposal(offered_vp=counter_vp, argument=counter_argument)

        if self.on_response:
            self.app.pop_screen()
            self.on_response("counter", counter)
        else:
            self.notify("Counter-proposal submitted", timeout=3)
            self.app.pop_screen()

    @on(Button.Pressed, "#reject")
    def reject_proposal(self) -> None:
        """Reject the proposal."""
        # Record rejection in trace
        if self.trace_logger:
            self.trace_logger.record_settlement_attempt(
                proposer="opponent",
                offered_vp=self.proposal.offered_vp,
                argument=self.proposal.argument or "",
                response="reject",
            )

        if self.on_response:
            self.app.pop_screen()
            self.on_response("reject", None)
        else:
            self.notify("Settlement rejected. Risk +1", severity="warning")
            self.app.pop_screen()

    def action_reject(self) -> None:
        self.reject_proposal()


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
        # Pop all screens back to main menu (keep base Screen + MainMenuScreen)
        while len(self.app.screen_stack) > 2:
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
        # Pop all screens back to main menu (keep base Screen + MainMenuScreen)
        while len(self.app.screen_stack) > 2:
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
    """Entry point for the CLI application.

    For debugging with Textual devtools:
        1. In one terminal: textual console
        2. In another terminal: textual run --dev src/brinksmanship/cli/app.py
    Or set TEXTUAL=1 environment variable for basic logging.
    """
    import os

    app = BrinksmanshipApp()
    # Enable devtools if TEXTUAL environment variable is set
    if os.environ.get("TEXTUAL"):
        app.run(inline=False)
    else:
        app.run()


if __name__ == "__main__":
    main()
