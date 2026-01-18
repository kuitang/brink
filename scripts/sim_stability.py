#!/usr/bin/env python3
"""
Stability Update Simulation for Brinksmanship

Tests the stability update mechanic from GAME_MANUAL.md Section 5.2:

    At the end of each turn (Turn 2+):
        switches = count of players who switched this turn (0, 1, or 2)

        # Decay toward neutral (5)
        stability = stability * 0.8 + 1.0

        # Apply consistency bonus or switch penalty
        if switches == 0:
            stability += 1.5
        elif switches == 1:
            stability -= 3.5
        else:  # switches == 2
            stability -= 5.5

        stability = clamp(stability, 1, 10)

This simulation verifies the stability trajectories for various behavior patterns.
"""

import argparse
from dataclasses import dataclass
from enum import Enum


class ActionType(Enum):
    COOPERATE = "C"
    DEFECT = "D"


@dataclass
class StabilityTracker:
    """Tracks stability over turns for a pair of players."""
    stability: float = 5.0
    history: list = None

    def __post_init__(self):
        if self.history is None:
            self.history = [self.stability]

    def update(self, switches: int):
        """Update stability based on number of switches (0, 1, or 2)."""
        # Decay toward neutral (5)
        self.stability = self.stability * 0.8 + 1.0

        # Apply consistency bonus or switch penalty
        if switches == 0:
            self.stability += 1.5
        elif switches == 1:
            self.stability -= 3.5
        else:  # switches == 2
            self.stability -= 5.5

        # Clamp to valid range
        self.stability = max(1.0, min(10.0, self.stability))
        self.history.append(self.stability)

    def reset(self):
        """Reset tracker for a new simulation."""
        self.stability = 5.0
        self.history = [self.stability]


def count_switches(
    prev_action_a: ActionType | None,
    prev_action_b: ActionType | None,
    curr_action_a: ActionType,
    curr_action_b: ActionType
) -> int:
    """Count how many players switched their action type."""
    switches = 0
    if prev_action_a is not None and prev_action_a != curr_action_a:
        switches += 1
    if prev_action_b is not None and prev_action_b != curr_action_b:
        switches += 1
    return switches


def simulate_trajectory(
    actions_a: list[ActionType],
    actions_b: list[ActionType],
    initial_stability: float = 5.0
) -> list[float]:
    """Simulate stability trajectory for a given sequence of actions.

    Args:
        actions_a: List of actions for player A (one per turn)
        actions_b: List of actions for player B (one per turn)
        initial_stability: Starting stability value

    Returns:
        List of stability values (starting value + one per turn after Turn 1)
    """
    tracker = StabilityTracker(stability=initial_stability)

    prev_a = None
    prev_b = None

    for turn_idx, (action_a, action_b) in enumerate(zip(actions_a, actions_b)):
        # Turn 1 has no previous action, so no stability update
        if turn_idx > 0:
            switches = count_switches(prev_a, prev_b, action_a, action_b)
            tracker.update(switches)

        prev_a = action_a
        prev_b = action_b

    return tracker.history


def run_manual_examples():
    """Run the exact examples from GAME_MANUAL.md Section 5.3."""
    C = ActionType.COOPERATE
    D = ActionType.DEFECT

    results = {}

    # Trajectory 1: Consistent Cooperator (9 turns of C)
    # Both players cooperate every turn
    actions_a = [C] * 9
    actions_b = [C] * 9
    results["consistent_cooperator"] = simulate_trajectory(actions_a, actions_b)

    # Trajectory 2: Fake Cooperator (8C then D)
    # Player A cooperates 8 turns then defects, Player B always cooperates
    actions_a = [C] * 8 + [D]
    actions_b = [C] * 9
    results["fake_cooperator"] = simulate_trajectory(actions_a, actions_b)

    # Trajectory 3: Early Defector (2D then 7C)
    # Player A defects 2 turns then switches to cooperate, Player B always cooperates
    actions_a = [D, D] + [C] * 7
    actions_b = [C] * 9
    results["early_defector"] = simulate_trajectory(actions_a, actions_b)

    return results


def run_additional_scenarios():
    """Run additional scenarios to fully test the stability mechanics."""
    C = ActionType.COOPERATE
    D = ActionType.DEFECT

    results = {}

    # Consistent Defector (both players always defect)
    actions_a = [D] * 9
    actions_b = [D] * 9
    results["consistent_defector"] = simulate_trajectory(actions_a, actions_b)

    # Alternating (both players switch every turn)
    actions_a = [C, D, C, D, C, D, C, D, C]
    actions_b = [C, D, C, D, C, D, C, D, C]
    results["alternating_both"] = simulate_trajectory(actions_a, actions_b)

    # One player alternates, other is consistent
    actions_a = [C, D, C, D, C, D, C, D, C]
    actions_b = [C] * 9
    results["one_alternating"] = simulate_trajectory(actions_a, actions_b)

    # Late mutual switch (both switch on turn 9)
    actions_a = [C] * 8 + [D]
    actions_b = [C] * 8 + [D]
    results["late_mutual_switch"] = simulate_trajectory(actions_a, actions_b)

    return results


def verify_manual_values(results: dict):
    """Verify that simulation matches GAME_MANUAL.md stated values."""
    print("\n" + "=" * 80)
    print("VERIFICATION AGAINST GAME_MANUAL.md SECTION 5.3")
    print("=" * 80)

    # Expected values from manual
    expected = {
        "consistent_cooperator": {
            "Start": 5.0,
            "After T2": 6.5,
            "After T5": 9.2,
            "After T9": 10.0,
        },
        "fake_cooperator": {
            "Start": 5.0,
            "After T8": 10.0,
            "After T9": 5.5,
        },
        "early_defector": {
            "Start": 5.0,
            "After T2": 5.5,
            "After T3": 2.9,
            "After T9": 9.9,
        },
    }

    # Map turn descriptions to indices
    # history[0] = Start, history[1] = After T2, history[2] = After T3, etc.
    turn_to_index = {
        "Start": 0,
        "After T2": 1,
        "After T3": 2,
        "After T5": 4,
        "After T8": 7,
        "After T9": 8,
    }

    for trajectory_name, expected_values in expected.items():
        print(f"\n{'-' * 60}")
        print(f"Trajectory: {trajectory_name.replace('_', ' ').title()}")
        print(f"{'-' * 60}")
        print(f"{'Turn':<15} {'Manual':>12} {'Simulated':>12} {'Match':>10}")
        print("-" * 50)

        history = results[trajectory_name]

        for turn_desc, expected_val in expected_values.items():
            idx = turn_to_index[turn_desc]
            simulated = history[idx] if idx < len(history) else None

            if simulated is not None:
                match = "YES" if abs(simulated - expected_val) < 0.15 else "NO"
                print(f"{turn_desc:<15} {expected_val:>12.1f} {simulated:>12.1f} {match:>10}")
            else:
                print(f"{turn_desc:<15} {expected_val:>12.1f} {'N/A':>12} {'N/A':>10}")


def print_trajectory_table(name: str, history: list[float]):
    """Print a single trajectory as a table."""
    print(f"\n{name}:")
    print("-" * 60)

    # Header row
    header = "Turn:     "
    for i in range(len(history)):
        if i == 0:
            header += f"{'Start':>8}"
        else:
            header += f"{'T' + str(i+1):>8}"
    print(header)

    # Values row
    values = "Stability:"
    for val in history:
        values += f"{val:>8.1f}"
    print(values)


def print_all_results(manual_results: dict, additional_results: dict):
    """Print all simulation results."""
    print("\n" + "=" * 80)
    print("STABILITY UPDATE SIMULATION RESULTS")
    print("=" * 80)

    print("\n" + "-" * 80)
    print("STABILITY UPDATE FORMULA (from GAME_MANUAL.md Section 5.2):")
    print("-" * 80)
    print("""
    stability = stability * 0.8 + 1.0
    if switches == 0:
        stability += 1.5
    elif switches == 1:
        stability -= 3.5
    else:  # switches == 2
        stability -= 5.5
    stability = clamp(stability, 1, 10)
""")

    # Manual examples
    print("\n" + "=" * 80)
    print("GAME_MANUAL.md EXAMPLE TRAJECTORIES")
    print("=" * 80)

    print("\n1. Consistent Cooperator (9 turns of same action by both players)")
    print("   Actions: Both players play C every turn")
    print_trajectory_table("Consistent Cooperator", manual_results["consistent_cooperator"])

    print("\n2. Fake Cooperator (8C then switch to D)")
    print("   Actions: Player A plays CCCCCCCC then D; Player B always C")
    print_trajectory_table("Fake Cooperator", manual_results["fake_cooperator"])

    print("\n3. Early Defector (2D then 7C)")
    print("   Actions: Player A plays DD then CCCCCCC; Player B always C")
    print_trajectory_table("Early Defector", manual_results["early_defector"])

    # Verify against manual
    verify_manual_values(manual_results)

    # Additional scenarios
    print("\n" + "=" * 80)
    print("ADDITIONAL TEST SCENARIOS")
    print("=" * 80)

    print("\n4. Consistent Defector (both players always defect)")
    print("   Actions: Both players play D every turn")
    print_trajectory_table("Consistent Defector", additional_results["consistent_defector"])

    print("\n5. Alternating (both players switch every turn)")
    print("   Actions: Both players play CDCDCDCDC")
    print_trajectory_table("Alternating Both", additional_results["alternating_both"])

    print("\n6. One Alternating (one switches, other consistent)")
    print("   Actions: Player A plays CDCDCDCDC; Player B always C")
    print_trajectory_table("One Alternating", additional_results["one_alternating"])

    print("\n7. Late Mutual Switch (both switch on turn 9)")
    print("   Actions: Both players play CCCCCCCC then D")
    print_trajectory_table("Late Mutual Switch", additional_results["late_mutual_switch"])

    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY: KEY INSIGHTS FROM STABILITY MECHANICS")
    print("=" * 80)
    print("""
1. CONSISTENT BEHAVIOR IS REWARDED: Both consistent cooperators AND consistent
   defectors reach high stability (~10). Predictability matters, not cooperation.

2. LATE DEFECTION IS COSTLY: A player who cooperates 8 turns then defects sees
   stability crash from 10 to ~5.5 in a single turn. This discourages "cooperate
   then defect" strategies.

3. RECOVERY IS POSSIBLE: An early defector who switches to cooperation can
   rebuild stability over time (~9.9 by turn 9).

4. ALTERNATING IS DEVASTATING: Players who switch every turn see stability
   collapse to the minimum (1.0) because they're constantly unpredictable.

5. THE DECAY FACTOR (0.8) means old consistency fades - recent behavior matters
   more than historical behavior.
""")

    # Instability factor impact
    print("\n" + "-" * 80)
    print("INSTABILITY FACTOR IMPACT ON VARIANCE")
    print("(Formula: Instability_Factor = 1 + (10 - Stability) / 20)")
    print("-" * 80)
    print(f"\n{'Stability':<12} {'Instability Factor':>20} {'Variance Impact':>18}")
    print("-" * 50)

    for stab in [10, 8, 6, 5, 4, 2, 1]:
        instab = 1 + (10 - stab) / 20
        impact = f"+{(instab - 1) * 100:.0f}% variance" if instab > 1 else "Baseline"
        print(f"{stab:<12} {instab:>20.2f} {impact:>18}")


def main():
    """Run the stability update simulation."""
    parser = argparse.ArgumentParser(
        description="Simulate stability update mechanic"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Print detailed turn-by-turn analysis"
    )
    args = parser.parse_args()

    print("Running stability update simulation...")

    manual_results = run_manual_examples()
    additional_results = run_additional_scenarios()

    print_all_results(manual_results, additional_results)


if __name__ == "__main__":
    main()
