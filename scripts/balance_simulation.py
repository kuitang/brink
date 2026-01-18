#!/usr/bin/env python3
"""
Game Balance Simulation for Brinksmanship

Runs comprehensive simulations with various strategies to analyze game balance.
Implements simplified Prisoner's Dilemma-based mechanics as specified.

Game Parameters:
- Position: 0-10, starts at 5 (hitting 0 = loss)
- Resources: 0-10, starts at 5 (hitting 0 = loss)
- Risk: 0-10, starts at 2 (hitting 10 = mutual destruction)
- Game length: 12-16 turns

Strategies:
1. TitForTat - cooperate first, then mirror opponent
2. AlwaysDefect - always defect
3. AlwaysCooperate - always cooperate
4. Opportunist - defect when ahead, cooperate when behind
5. Nash - play Nash equilibrium (defect in Prisoner's Dilemma)
"""

import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Optional
from collections import defaultdict
import statistics


class Action(Enum):
    COOPERATE = "C"
    DEFECT = "D"


class EndingType(Enum):
    MAX_TURNS = "max_turns"
    POSITION_LOSS_A = "position_loss_a"
    POSITION_LOSS_B = "position_loss_b"
    RESOURCE_LOSS_A = "resource_loss_a"
    RESOURCE_LOSS_B = "resource_loss_b"
    MUTUAL_DESTRUCTION = "mutual_destruction"
    CRISIS_TERMINATION = "crisis_termination"


@dataclass
class PlayerState:
    position: float = 5.0
    resources: float = 5.0

    def clamp(self):
        """Clamp values to valid ranges."""
        self.position = max(0.0, min(10.0, self.position))
        self.resources = max(0.0, min(10.0, self.resources))


@dataclass
class GameState:
    player_a: PlayerState = field(default_factory=PlayerState)
    player_b: PlayerState = field(default_factory=PlayerState)
    risk: float = 2.0
    turn: int = 1
    max_turns: int = 14
    history_a: list = field(default_factory=list)
    history_b: list = field(default_factory=list)

    def clamp(self):
        """Clamp all values to valid ranges."""
        self.player_a.clamp()
        self.player_b.clamp()
        self.risk = max(0.0, min(10.0, self.risk))

    def get_act_multiplier(self) -> float:
        """Return act scaling based on turn number."""
        if self.turn <= 4:
            return 0.7  # Act I
        elif self.turn <= 8:
            return 1.0  # Act II
        else:
            return 1.3  # Act III


# State delta rules for Prisoner's Dilemma outcomes
# CC: both cooperate
# CD: a cooperates, b defects
# DC: a defects, b cooperates
# DD: both defect

def apply_outcome(state: GameState, action_a: Action, action_b: Action, add_noise: bool = True):
    """Apply outcome based on actions and state delta rules.

    Args:
        state: Current game state
        action_a: Action from player A
        action_b: Action from player B
        add_noise: If True, add small random variance to outcomes
    """
    multiplier = state.get_act_multiplier()

    # Small random variance (+/- 10%) to make games less deterministic
    noise_factor = 1.0
    if add_noise:
        noise_factor = random.uniform(0.9, 1.1)

    if action_a == Action.COOPERATE and action_b == Action.COOPERATE:
        # CC: pos_a +0.5, pos_b +0.5, risk -0.5
        state.player_a.position += 0.5 * multiplier * noise_factor
        state.player_b.position += 0.5 * multiplier * noise_factor
        state.risk -= 0.5 * multiplier * noise_factor
    elif action_a == Action.COOPERATE and action_b == Action.DEFECT:
        # CD: pos_a -1.0, pos_b +1.0, risk +0.5
        state.player_a.position -= 1.0 * multiplier * noise_factor
        state.player_b.position += 1.0 * multiplier * noise_factor
        state.risk += 0.5 * multiplier * noise_factor
    elif action_a == Action.DEFECT and action_b == Action.COOPERATE:
        # DC: pos_a +1.0, pos_b -1.0, risk +0.5
        state.player_a.position += 1.0 * multiplier * noise_factor
        state.player_b.position -= 1.0 * multiplier * noise_factor
        state.risk += 0.5 * multiplier * noise_factor
    else:  # DD
        # DD: pos_a -0.3, pos_b -0.3, resource_cost each 0.5, risk +1.0
        state.player_a.position -= 0.3 * multiplier * noise_factor
        state.player_b.position -= 0.3 * multiplier * noise_factor
        state.player_a.resources -= 0.5 * multiplier * noise_factor
        state.player_b.resources -= 0.5 * multiplier * noise_factor
        state.risk += 1.0 * multiplier * noise_factor

    state.clamp()


def check_crisis_termination(state: GameState) -> bool:
    """Check if crisis terminates this turn (probabilistic).

    From GAME_MANUAL.md:
    - Only checked for Turn >= 10 and Risk > 7
    - P(termination) = (Risk - 7) * 0.08
    - Risk 8: 8%, Risk 9: 16%, Risk 10: 100% (handled by mutual destruction)
    """
    if state.turn < 10 or state.risk <= 7:
        return False

    p_termination = (state.risk - 7) * 0.08
    return random.random() < p_termination


def check_ending(state: GameState) -> Optional[EndingType]:
    """Check if game has ended."""
    # Check mutual destruction (risk = 10)
    if state.risk >= 10.0:
        return EndingType.MUTUAL_DESTRUCTION

    # Check position losses
    if state.player_a.position <= 0:
        return EndingType.POSITION_LOSS_A
    if state.player_b.position <= 0:
        return EndingType.POSITION_LOSS_B

    # Check resource losses
    if state.player_a.resources <= 0:
        return EndingType.RESOURCE_LOSS_A
    if state.player_b.resources <= 0:
        return EndingType.RESOURCE_LOSS_B

    # Check crisis termination (probabilistic, Turn >= 10, Risk > 7)
    if check_crisis_termination(state):
        return EndingType.CRISIS_TERMINATION

    # Check max turns
    if state.turn > state.max_turns:
        return EndingType.MAX_TURNS

    return None


# Strategy implementations
Strategy = Callable[[GameState, list, list, str], Action]


def tit_for_tat(state: GameState, my_history: list, opp_history: list, player: str) -> Action:
    """TitForTat: cooperate first, then mirror opponent's last move."""
    if not opp_history:
        return Action.COOPERATE
    return opp_history[-1]


def always_defect(state: GameState, my_history: list, opp_history: list, player: str) -> Action:
    """AlwaysDefect: always defect."""
    return Action.DEFECT


def always_cooperate(state: GameState, my_history: list, opp_history: list, player: str) -> Action:
    """AlwaysCooperate: always cooperate."""
    return Action.COOPERATE


def opportunist(state: GameState, my_history: list, opp_history: list, player: str) -> Action:
    """Opportunist: defect when ahead in position, cooperate when behind.

    Also considers resources and risk to make more nuanced decisions.
    """
    if player == "A":
        my_pos = state.player_a.position
        opp_pos = state.player_b.position
        my_res = state.player_a.resources
    else:
        my_pos = state.player_b.position
        opp_pos = state.player_a.position
        my_res = state.player_b.resources

    # Consider position advantage
    pos_advantage = my_pos - opp_pos

    # Risk-aware: if risk is high, be more cautious
    if state.risk >= 7:
        return Action.COOPERATE

    # Resource-aware: if low on resources, defection is costly (DD costs resources)
    if my_res <= 2:
        return Action.COOPERATE

    if pos_advantage > 1.0:
        return Action.DEFECT
    elif pos_advantage < -1.0:
        return Action.COOPERATE
    else:
        # When roughly equal, mix based on turn (early cooperate, late defect)
        if state.turn <= 6:
            return Action.COOPERATE
        else:
            return Action.DEFECT


def nash_equilibrium(state: GameState, my_history: list, opp_history: list, player: str) -> Action:
    """Nash: play Nash equilibrium (defect in Prisoner's Dilemma).

    But with risk-awareness: if risk is very high, cooperate to avoid mutual destruction.
    """
    if state.risk >= 8:
        return Action.COOPERATE
    return Action.DEFECT


def grim_trigger(state: GameState, my_history: list, opp_history: list, player: str) -> Action:
    """GrimTrigger: cooperate until opponent defects, then defect forever."""
    if Action.DEFECT in opp_history:
        return Action.DEFECT
    return Action.COOPERATE


def random_strategy(state: GameState, my_history: list, opp_history: list, player: str) -> Action:
    """Random: 50/50 mix of cooperate and defect."""
    return random.choice([Action.COOPERATE, Action.DEFECT])


STRATEGIES = {
    "TitForTat": tit_for_tat,
    "AlwaysDefect": always_defect,
    "AlwaysCooperate": always_cooperate,
    "Opportunist": opportunist,
    "Nash": nash_equilibrium,
}


@dataclass
class GameResult:
    winner: Optional[str]  # "A", "B", "tie", or "mutual_destruction"
    ending_type: EndingType
    turns_played: int
    final_pos_a: float
    final_pos_b: float
    final_res_a: float
    final_res_b: float
    final_risk: float


def run_game(strategy_a: Strategy, strategy_b: Strategy, max_turns: int = None) -> GameResult:
    """Run a single game between two strategies."""
    if max_turns is None:
        max_turns = random.randint(12, 16)

    state = GameState(max_turns=max_turns)

    while True:
        # Check for ending before actions
        ending = check_ending(state)
        if ending:
            break

        # Get actions from both players
        action_a = strategy_a(state, state.history_a, state.history_b, "A")
        action_b = strategy_b(state, state.history_b, state.history_a, "B")

        # Record history
        state.history_a.append(action_a)
        state.history_b.append(action_b)

        # Apply outcome
        apply_outcome(state, action_a, action_b)

        # Advance turn
        state.turn += 1

        # Check for ending after actions
        ending = check_ending(state)
        if ending:
            break

    # Determine winner
    if ending == EndingType.MUTUAL_DESTRUCTION:
        winner = "mutual_destruction"
    elif ending == EndingType.POSITION_LOSS_A or ending == EndingType.RESOURCE_LOSS_A:
        winner = "B"
    elif ending == EndingType.POSITION_LOSS_B or ending == EndingType.RESOURCE_LOSS_B:
        winner = "A"
    else:  # MAX_TURNS - compare final positions
        if state.player_a.position > state.player_b.position:
            winner = "A"
        elif state.player_b.position > state.player_a.position:
            winner = "B"
        else:
            winner = "tie"

    return GameResult(
        winner=winner,
        ending_type=ending,
        turns_played=state.turn - 1,
        final_pos_a=state.player_a.position,
        final_pos_b=state.player_b.position,
        final_res_a=state.player_a.resources,
        final_res_b=state.player_b.resources,
        final_risk=state.risk,
    )


@dataclass
class PairingStats:
    wins_a: int = 0
    wins_b: int = 0
    ties: int = 0
    mutual_destructions: int = 0
    crisis_terminations: int = 0
    eliminations: int = 0  # Position or resource = 0
    total_games: int = 0
    total_turns: int = 0
    position_spreads: list = field(default_factory=list)

    def add_result(self, result: GameResult):
        self.total_games += 1
        self.total_turns += result.turns_played

        # Track winner
        if result.winner == "A":
            self.wins_a += 1
        elif result.winner == "B":
            self.wins_b += 1
        elif result.winner == "tie":
            self.ties += 1
        # mutual_destruction winner is tracked separately via ending_type

        # Track ending types (mutually exclusive)
        if result.ending_type == EndingType.MUTUAL_DESTRUCTION:
            self.mutual_destructions += 1
        elif result.ending_type == EndingType.CRISIS_TERMINATION:
            self.crisis_terminations += 1
        elif result.ending_type in [EndingType.POSITION_LOSS_A, EndingType.POSITION_LOSS_B,
                                     EndingType.RESOURCE_LOSS_A, EndingType.RESOURCE_LOSS_B]:
            self.eliminations += 1

        # Record position spread
        self.position_spreads.append(abs(result.final_pos_a - result.final_pos_b))

    @property
    def win_rate_a(self) -> float:
        if self.total_games == 0:
            return 0.0
        return self.wins_a / self.total_games

    @property
    def win_rate_b(self) -> float:
        if self.total_games == 0:
            return 0.0
        return self.wins_b / self.total_games

    @property
    def avg_game_length(self) -> float:
        if self.total_games == 0:
            return 0.0
        return self.total_turns / self.total_games

    @property
    def elimination_rate(self) -> float:
        if self.total_games == 0:
            return 0.0
        return self.eliminations / self.total_games

    @property
    def mutual_destruction_rate(self) -> float:
        if self.total_games == 0:
            return 0.0
        return self.mutual_destructions / self.total_games

    @property
    def crisis_termination_rate(self) -> float:
        if self.total_games == 0:
            return 0.0
        return self.crisis_terminations / self.total_games

    @property
    def avg_position_spread(self) -> float:
        if not self.position_spreads:
            return 0.0
        return statistics.mean(self.position_spreads)


def run_simulation(num_games: int = 500) -> dict:
    """Run simulation for all strategy pairings."""
    results = {}
    strategy_names = list(STRATEGIES.keys())

    for i, name_a in enumerate(strategy_names):
        for name_b in strategy_names[i:]:  # Only unique pairings
            pairing = f"{name_a} vs {name_b}"
            stats = PairingStats()

            for _ in range(num_games):
                result = run_game(STRATEGIES[name_a], STRATEGIES[name_b])
                stats.add_result(result)

            results[pairing] = stats

    return results


def print_summary_table(results: dict, num_games: int):
    """Print formatted summary table."""
    print("\n" + "=" * 100)
    print("GAME BALANCE SIMULATION RESULTS")
    print(f"Games per pairing: {num_games}")
    print("=" * 100)

    # Header
    print(f"\n{'Pairing':<35} {'Win A':>8} {'Win B':>8} {'Tie':>6} {'Avg Len':>8} "
          f"{'Elim %':>8} {'MD %':>6} {'Crisis %':>8}")
    print("-" * 110)

    for pairing, stats in sorted(results.items()):
        print(f"{pairing:<35} {stats.win_rate_a*100:>7.1f}% {stats.win_rate_b*100:>7.1f}% "
              f"{stats.ties/stats.total_games*100:>5.1f}% {stats.avg_game_length:>8.1f} "
              f"{stats.elimination_rate*100:>7.1f}% {stats.mutual_destruction_rate*100:>5.1f}% "
              f"{stats.crisis_termination_rate*100:>7.1f}%")

    print("-" * 100)

    # Dominant strategy analysis
    print("\n" + "=" * 100)
    print("DOMINANT STRATEGY ANALYSIS (>65% win rate against all others)")
    print("=" * 100)

    # Aggregate win rates per strategy
    strategy_wins = defaultdict(lambda: {"wins": 0, "games": 0})

    for pairing, stats in results.items():
        strats = pairing.split(" vs ")
        strat_a, strat_b = strats[0], strats[1]

        # Count wins for strategy A
        strategy_wins[strat_a]["wins"] += stats.wins_a
        strategy_wins[strat_a]["games"] += stats.total_games

        # Count wins for strategy B (if different)
        if strat_a != strat_b:
            strategy_wins[strat_b]["wins"] += stats.wins_b
            strategy_wins[strat_b]["games"] += stats.total_games

    print(f"\n{'Strategy':<20} {'Total Wins':>12} {'Total Games':>12} {'Overall Win Rate':>18}")
    print("-" * 65)

    dominant_strategies = []
    for strat, data in sorted(strategy_wins.items()):
        win_rate = data["wins"] / data["games"] if data["games"] > 0 else 0
        print(f"{strat:<20} {data['wins']:>12} {data['games']:>12} {win_rate*100:>17.1f}%")
        if win_rate > 0.65:
            dominant_strategies.append((strat, win_rate))

    print("\n" + "-" * 65)
    if dominant_strategies:
        print("DOMINANT STRATEGIES DETECTED:")
        for strat, rate in dominant_strategies:
            print(f"  - {strat}: {rate*100:.1f}% overall win rate")
    else:
        print("NO DOMINANT STRATEGY DETECTED (no strategy exceeds 65% overall win rate)")

    # Head-to-head analysis
    print("\n" + "=" * 100)
    print("HEAD-TO-HEAD WIN RATES (Row strategy vs Column strategy)")
    print("=" * 100)

    strategy_names = list(STRATEGIES.keys())

    # Build head-to-head matrix
    h2h = {}
    for pairing, stats in results.items():
        strats = pairing.split(" vs ")
        strat_a, strat_b = strats[0], strats[1]

        if strat_a not in h2h:
            h2h[strat_a] = {}
        if strat_b not in h2h:
            h2h[strat_b] = {}

        # Win rate of A vs B
        h2h[strat_a][strat_b] = stats.win_rate_a * 100
        # Win rate of B vs A
        if strat_a != strat_b:
            h2h[strat_b][strat_a] = stats.win_rate_b * 100

    # Print matrix header
    header = f"{'Strategy':<18}"
    for name in strategy_names:
        header += f"{name[:12]:>14}"
    print(f"\n{header}")
    print("-" * (18 + 14 * len(strategy_names)))

    for name_a in strategy_names:
        row = f"{name_a:<18}"
        for name_b in strategy_names:
            if name_a == name_b:
                row += f"{'---':>14}"
            elif name_b in h2h.get(name_a, {}):
                row += f"{h2h[name_a][name_b]:>13.1f}%"
            else:
                row += f"{'N/A':>14}"
        print(row)

    # Additional statistics
    print("\n" + "=" * 100)
    print("GAME ENDING STATISTICS")
    print("=" * 100)

    total_eliminations = sum(s.eliminations for s in results.values())
    total_mutual = sum(s.mutual_destructions for s in results.values())
    total_crisis = sum(s.crisis_terminations for s in results.values())
    total_games = sum(s.total_games for s in results.values())
    total_turns = sum(s.total_turns for s in results.values())
    total_max_turns = total_games - total_eliminations - total_mutual - total_crisis

    print(f"\nTotal games simulated: {total_games}")
    print(f"Average game length: {total_turns/total_games:.1f} turns")
    print(f"Games ending in elimination: {total_eliminations} ({total_eliminations/total_games*100:.1f}%)")
    print(f"Games ending in mutual destruction: {total_mutual} ({total_mutual/total_games*100:.1f}%)")
    print(f"Games ending in crisis termination: {total_crisis} ({total_crisis/total_games*100:.1f}%)")
    print(f"Games ending at max turns: {total_max_turns} ({total_max_turns/total_games*100:.1f}%)")


def main():
    """Run the full simulation."""
    import argparse

    parser = argparse.ArgumentParser(description="Run game balance simulation")
    parser.add_argument("--games", type=int, default=500,
                        help="Number of games per pairing (default: 500)")
    parser.add_argument("--seed", type=int, default=None,
                        help="Random seed for reproducibility")
    args = parser.parse_args()

    if args.seed is not None:
        random.seed(args.seed)

    print(f"Running simulation with {args.games} games per pairing...")
    results = run_simulation(args.games)
    print_summary_table(results, args.games)


if __name__ == "__main__":
    main()
