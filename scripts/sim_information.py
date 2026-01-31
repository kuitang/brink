#!/usr/bin/env python3
"""
Information Games Simulation for Brinksmanship

Tests the information game mechanics from GAME_MANUAL.md Section 3.6:
1. Reconnaissance Game (Position Intelligence)
2. Inspection Game (Resource Intelligence)
3. Costly Signaling
4. Information Decay

Key design principle: Players never passively observe opponent state.
Information is acquired through games and decays over time.
"""

import random
import statistics
from dataclasses import dataclass
from enum import Enum


class ReconAction(Enum):
    PROBE = "probe"
    MASK = "mask"


class ReconResponse(Enum):
    VIGILANT = "vigilant"
    PROJECT = "project"


class InspectAction(Enum):
    INSPECT = "inspect"
    TRUST = "trust"


class InspectResponse(Enum):
    COMPLY = "comply"
    CHEAT = "cheat"


@dataclass
class InformationState:
    """What one player knows about another."""

    position_bounds: tuple = (0.0, 10.0)
    resources_bounds: tuple = (0.0, 10.0)
    known_position: float | None = None
    known_position_turn: int | None = None
    known_resources: float | None = None
    known_resources_turn: int | None = None

    def get_position_estimate(self, current_turn: int) -> tuple:
        """Returns (estimate, uncertainty_radius)."""
        if self.known_position is not None:
            turns_elapsed = current_turn - self.known_position_turn
            uncertainty = min(turns_elapsed * 0.8, 5.0)
            low = max(self.position_bounds[0], self.known_position - uncertainty)
            high = min(self.position_bounds[1], self.known_position + uncertainty)
            return (low + high) / 2, (high - low) / 2
        else:
            midpoint = sum(self.position_bounds) / 2
            radius = (self.position_bounds[1] - self.position_bounds[0]) / 2
            return midpoint, radius

    def get_resources_estimate(self, current_turn: int) -> tuple:
        """Returns (estimate, uncertainty_radius)."""
        if self.known_resources is not None:
            turns_elapsed = current_turn - self.known_resources_turn
            uncertainty = min(turns_elapsed * 0.8, 5.0)
            low = max(self.resources_bounds[0], self.known_resources - uncertainty)
            high = min(self.resources_bounds[1], self.known_resources + uncertainty)
            return (low + high) / 2, (high - low) / 2
        else:
            midpoint = sum(self.resources_bounds) / 2
            radius = (self.resources_bounds[1] - self.resources_bounds[0]) / 2
            return midpoint, radius

    def update_position(self, value: float, turn: int):
        """Update known position from reconnaissance."""
        self.known_position = value
        self.known_position_turn = turn

    def update_resources(self, value: float, turn: int):
        """Update known resources from inspection."""
        self.known_resources = value
        self.known_resources_turn = turn


@dataclass
class ReconOutcome:
    """Outcome of a reconnaissance game."""

    initiator_learns_position: bool
    responder_learns_position: bool
    risk_increase: float
    detected: bool  # Responder knows initiator probed


def resolve_reconnaissance(initiator_action: ReconAction, responder_action: ReconResponse) -> ReconOutcome:
    """
    Resolve reconnaissance game.

    Matrix:
                    Vigilant        Project
    Probe           Detected        Success
    Mask            Stalemate       Exposed
    """
    if initiator_action == ReconAction.PROBE:
        if responder_action == ReconResponse.VIGILANT:
            # Detected: Risk +0.5, no info gained, opponent knows you probed
            return ReconOutcome(
                initiator_learns_position=False, responder_learns_position=False, risk_increase=0.5, detected=True
            )
        else:  # PROJECT
            # Success: Learn opponent's position
            return ReconOutcome(
                initiator_learns_position=True, responder_learns_position=False, risk_increase=0.0, detected=False
            )
    else:  # MASK
        if responder_action == ReconResponse.VIGILANT:
            # Stalemate: Nothing happens
            return ReconOutcome(
                initiator_learns_position=False, responder_learns_position=False, risk_increase=0.0, detected=False
            )
        else:  # PROJECT
            # Exposed: Opponent learns YOUR position
            return ReconOutcome(
                initiator_learns_position=False, responder_learns_position=True, risk_increase=0.0, detected=False
            )


@dataclass
class InspectionOutcome:
    """Outcome of an inspection game."""

    inspector_learns_resources: bool
    cheater_caught: bool
    cheater_gains_position: float
    cheater_risk_increase: float
    cheater_position_penalty: float


def resolve_inspection(inspector_action: InspectAction, target_action: InspectResponse) -> InspectionOutcome:
    """
    Resolve inspection game.

    Matrix:
                    Comply          Cheat
    Inspect         Verified        Caught
    Trust           Nothing         Exploited
    """
    if inspector_action == InspectAction.INSPECT:
        if target_action == InspectResponse.COMPLY:
            # Verified: Learn opponent's resources
            return InspectionOutcome(
                inspector_learns_resources=True,
                cheater_caught=False,
                cheater_gains_position=0.0,
                cheater_risk_increase=0.0,
                cheater_position_penalty=0.0,
            )
        else:  # CHEAT
            # Caught: Learn resources, opponent gets penalty
            return InspectionOutcome(
                inspector_learns_resources=True,
                cheater_caught=True,
                cheater_gains_position=0.0,
                cheater_risk_increase=1.0,
                cheater_position_penalty=0.5,
            )
    else:  # TRUST
        if target_action == InspectResponse.COMPLY:
            # Nothing happens
            return InspectionOutcome(
                inspector_learns_resources=False,
                cheater_caught=False,
                cheater_gains_position=0.0,
                cheater_risk_increase=0.0,
                cheater_position_penalty=0.0,
            )
        else:  # CHEAT
            # Exploited: Cheater gains position
            return InspectionOutcome(
                inspector_learns_resources=False,
                cheater_caught=False,
                cheater_gains_position=0.5,
                cheater_risk_increase=0.0,
                cheater_position_penalty=0.0,
            )


def get_signal_cost(position: float) -> float:
    """
    Get cost of signaling based on true position.

    From GAME_MANUAL.md Section 3.6.3:
    - Position >= 7: Cost = 0.3
    - Position 4-6: Cost = 0.7
    - Position <= 3: Cost = 1.2
    """
    if position >= 7:
        return 0.3
    elif position >= 4:
        return 0.7
    else:
        return 1.2


def run_reconnaissance_nash_test(num_trials: int = 10000) -> dict:
    """
    Test that mixed strategy Nash equilibrium (50/50) gives expected outcomes.

    Expected:
    - 25% initiator learns position
    - 25% responder learns position
    - 12.5% detection (risk increase)
    """
    initiator_learns = 0
    responder_learns = 0
    detected = 0
    risk_increases = []

    for _ in range(num_trials):
        # Both play 50/50 Nash equilibrium
        init_action = random.choice([ReconAction.PROBE, ReconAction.MASK])
        resp_action = random.choice([ReconResponse.VIGILANT, ReconResponse.PROJECT])

        outcome = resolve_reconnaissance(init_action, resp_action)

        if outcome.initiator_learns_position:
            initiator_learns += 1
        if outcome.responder_learns_position:
            responder_learns += 1
        if outcome.detected:
            detected += 1
        risk_increases.append(outcome.risk_increase)

    return {
        "initiator_learns_rate": initiator_learns / num_trials,
        "responder_learns_rate": responder_learns / num_trials,
        "detection_rate": detected / num_trials,
        "avg_risk_increase": statistics.mean(risk_increases),
        "expected_initiator_learns": 0.25,
        "expected_responder_learns": 0.25,
        "expected_detection": 0.25,  # Probe + Vigilant = 25%
        "expected_risk_increase": 0.125,  # 25% * 0.5
    }


def run_inspection_analysis(num_trials: int = 10000) -> dict:
    """
    Analyze inspection game outcomes with various strategies.
    """
    results = {}

    # Scenario 1: Inspector always inspects, target mixes
    inspect_learns = 0
    catches = 0

    for _ in range(num_trials):
        target_action = random.choice([InspectResponse.COMPLY, InspectResponse.CHEAT])
        outcome = resolve_inspection(InspectAction.INSPECT, target_action)

        if outcome.inspector_learns_resources:
            inspect_learns += 1
        if outcome.cheater_caught:
            catches += 1

    results["always_inspect"] = {
        "learns_rate": inspect_learns / num_trials,
        "catch_rate": catches / num_trials,
    }

    # Scenario 2: Inspector mixes, target always complies
    inspect_learns = 0
    for _ in range(num_trials):
        inspector_action = random.choice([InspectAction.INSPECT, InspectAction.TRUST])
        outcome = resolve_inspection(inspector_action, InspectResponse.COMPLY)

        if outcome.inspector_learns_resources:
            inspect_learns += 1

    results["target_complies"] = {
        "learns_rate": inspect_learns / num_trials,
    }

    # Scenario 3: Inspector mixes, target always cheats
    catches = 0
    exploits = 0
    for _ in range(num_trials):
        inspector_action = random.choice([InspectAction.INSPECT, InspectAction.TRUST])
        outcome = resolve_inspection(inspector_action, InspectResponse.CHEAT)

        if outcome.cheater_caught:
            catches += 1
        if outcome.cheater_gains_position > 0:
            exploits += 1

    results["target_cheats"] = {
        "catch_rate": catches / num_trials,
        "exploit_rate": exploits / num_trials,
    }

    return results


def run_signaling_analysis() -> dict:
    """
    Analyze costly signaling mechanics.

    Key insight: Only strong players can profitably signal.
    """
    results = []

    for position in [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]:
        cost = get_signal_cost(position)
        # Signal reveals "position >= 4"
        signal_accurate = position >= 4

        results.append(
            {
                "position": position,
                "cost": cost,
                "signal_accurate": signal_accurate,
                "cost_per_info_value": cost / (10 - position + 1) if position < 10 else cost,
            }
        )

    return results


def run_information_decay_test() -> dict:
    """
    Test information decay over time.

    From GAME_MANUAL.md:
    uncertainty = min(turns_since_known * 0.8, 5.0)
    """
    info_state = InformationState()
    info_state.update_position(5.0, turn=1)

    results = []
    for turn in range(1, 15):
        estimate, uncertainty = info_state.get_position_estimate(turn)
        results.append(
            {
                "turn": turn,
                "turns_since_known": turn - 1,
                "estimate": estimate,
                "uncertainty": uncertainty,
                "range_low": max(0, estimate - uncertainty),
                "range_high": min(10, estimate + uncertainty),
            }
        )

    return results


def run_full_game_with_info(num_games: int = 1000) -> dict:
    """
    Simulate games where players use information games strategically.

    Compare strategies:
    1. Never recon (baseline)
    2. Recon early (turn 2)
    3. Recon mid-game (turn 6)
    4. Recon late (turn 10)
    """
    # This is a simplified simulation showing info value
    # In full game, info helps make better strategic decisions

    strategies = {
        "never_recon": {"recon_turns": []},
        "early_recon": {"recon_turns": [2]},
        "mid_recon": {"recon_turns": [6]},
        "late_recon": {"recon_turns": [10]},
        "periodic_recon": {"recon_turns": [3, 7, 11]},
    }

    results = {}

    for name, strategy in strategies.items():
        total_info_turns = 0
        total_uncertainty = 0.0

        for _game in range(num_games):
            max_turn = random.randint(12, 16)
            info_state = InformationState()

            for turn in range(1, max_turn + 1):
                if turn in strategy["recon_turns"]:
                    # Simplified: 25% chance of learning position
                    if random.random() < 0.25:
                        # Learn opponent position (random for simulation)
                        true_pos = random.uniform(0, 10)
                        info_state.update_position(true_pos, turn)
                        total_info_turns += 1

                # Track average uncertainty at game end
                if turn == max_turn:
                    _, uncertainty = info_state.get_position_estimate(turn)
                    total_uncertainty += uncertainty

        results[name] = {
            "avg_info_acquisitions": total_info_turns / num_games,
            "avg_final_uncertainty": total_uncertainty / num_games,
            "recon_attempts": len(strategy["recon_turns"]),
        }

    return results


def print_results():
    """Print all simulation results."""
    print("=" * 80)
    print("INFORMATION GAMES SIMULATION")
    print("=" * 80)

    # Reconnaissance Nash Test
    print("\n" + "-" * 80)
    print("RECONNAISSANCE GAME - Nash Equilibrium Test (50/50 mixed strategy)")
    print("-" * 80)

    recon_results = run_reconnaissance_nash_test()
    print(f"\n{'Metric':<30} {'Simulated':>15} {'Expected':>15}")
    print("-" * 60)
    print(
        f"{'Initiator learns position':<30} {recon_results['initiator_learns_rate'] * 100:>14.1f}% {recon_results['expected_initiator_learns'] * 100:>14.1f}%"
    )
    print(
        f"{'Responder learns position':<30} {recon_results['responder_learns_rate'] * 100:>14.1f}% {recon_results['expected_responder_learns'] * 100:>14.1f}%"
    )
    print(
        f"{'Detection rate':<30} {recon_results['detection_rate'] * 100:>14.1f}% {recon_results['expected_detection'] * 100:>14.1f}%"
    )
    print(
        f"{'Avg risk increase':<30} {recon_results['avg_risk_increase']:>15.3f} {recon_results['expected_risk_increase']:>15.3f}"
    )

    # Inspection Analysis
    print("\n" + "-" * 80)
    print("INSPECTION GAME - Strategy Analysis")
    print("-" * 80)

    inspect_results = run_inspection_analysis()
    print("\nScenario: Inspector always inspects, target mixes (50/50):")
    print(f"  Learn rate: {inspect_results['always_inspect']['learns_rate'] * 100:.1f}% (expected: 100%)")
    print(f"  Catch rate: {inspect_results['always_inspect']['catch_rate'] * 100:.1f}% (expected: 50%)")

    print("\nScenario: Inspector mixes, target always complies:")
    print(f"  Learn rate: {inspect_results['target_complies']['learns_rate'] * 100:.1f}% (expected: 50%)")

    print("\nScenario: Inspector mixes, target always cheats:")
    print(f"  Catch rate: {inspect_results['target_cheats']['catch_rate'] * 100:.1f}% (expected: 50%)")
    print(f"  Exploit rate: {inspect_results['target_cheats']['exploit_rate'] * 100:.1f}% (expected: 50%)")

    # Signaling Analysis
    print("\n" + "-" * 80)
    print("COSTLY SIGNALING - Cost by Position")
    print("-" * 80)

    signal_results = run_signaling_analysis()
    print(f"\n{'Position':<10} {'Cost':>10} {'Signal Accurate':>20}")
    print("-" * 45)
    for r in signal_results:
        accurate = "Yes (>= 4)" if r["signal_accurate"] else "No (bluff)"
        print(f"{r['position']:<10} {r['cost']:>10.1f} {accurate:>20}")

    print("\nKey insight: Positions 1-3 pay 1.2 to signal, but reveal false info.")
    print("Positions 7+ pay only 0.3 - strong players can afford credible signals.")

    # Information Decay
    print("\n" + "-" * 80)
    print("INFORMATION DECAY - Uncertainty Growth Over Time")
    print("-" * 80)
    print("(Position learned on Turn 1, value = 5.0)")

    decay_results = run_information_decay_test()
    print(f"\n{'Turn':<6} {'Turns Since':>12} {'Uncertainty':>12} {'Range':>20}")
    print("-" * 55)
    for r in decay_results:
        range_str = f"[{r['range_low']:.1f}, {r['range_high']:.1f}]"
        print(f"{r['turn']:<6} {r['turns_since_known']:>12} {r['uncertainty']:>12.1f} {range_str:>20}")

    print("\nAt ~6 turns, uncertainty = 5.0 (half the scale), info nearly useless.")

    # Strategic Value of Information
    print("\n" + "-" * 80)
    print("STRATEGIC VALUE - Comparing Recon Strategies")
    print("-" * 80)

    game_results = run_full_game_with_info()
    print(f"\n{'Strategy':<20} {'Recon Attempts':>15} {'Avg Acquired':>15} {'Final Uncertainty':>18}")
    print("-" * 70)
    for name, r in game_results.items():
        print(
            f"{name:<20} {r['recon_attempts']:>15} {r['avg_info_acquisitions']:>15.2f} {r['avg_final_uncertainty']:>18.2f}"
        )

    print("\nInterpretation:")
    print("- Never recon: Maximum uncertainty (5.0 = no information)")
    print("- Early recon: Info decays by game end, still ~4.6 uncertainty")
    print("- Late recon: Most valuable if you need info for endgame decisions")
    print("- Periodic: Best coverage but costs 3 turns and 1.5 resources")

    print("\n" + "=" * 80)
    print("SIMULATION COMPLETE")
    print("=" * 80)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Run information games simulation")
    parser.add_argument("--seed", type=int, default=None, help="Random seed for reproducibility")
    parser.add_argument("--trials", type=int, default=10000, help="Number of trials per test (default: 10000)")
    args = parser.parse_args()

    if args.seed is not None:
        random.seed(args.seed)

    print_results()


if __name__ == "__main__":
    main()
