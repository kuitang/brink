#!/usr/bin/env python3
"""
Settlement Protocol Simulation for Brinksmanship

Tests the settlement mechanic to verify offer ranges and acceptance probabilities.

Settlement Constraints:
    position_diff = my_position - opp_position
    coop_bonus = (cooperation_score - 5) * 2
    suggested_vp = 50 + (position_diff * 5) + coop_bonus
    min_offer = max(20, suggested_vp - 10)
    max_offer = min(80, suggested_vp + 10)

Test Scenarios:
    - When ahead (+2 position): higher suggested VP
    - When behind (-2 position): lower suggested VP
    - With high cooperation: bonus to suggested VP
    - With low cooperation: penalty to suggested VP
"""

import argparse
import random
from dataclasses import dataclass


@dataclass
class SettlementParams:
    """Parameters for computing settlement offers."""

    my_position: float
    opp_position: float
    cooperation_score: float


def compute_settlement_offer_range(params: SettlementParams) -> tuple[float, float, float]:
    """Compute the suggested VP and valid offer range.

    Args:
        params: Settlement parameters

    Returns:
        Tuple of (suggested_vp, min_offer, max_offer)
    """
    position_diff = params.my_position - params.opp_position
    coop_bonus = (params.cooperation_score - 5) * 2
    suggested_vp = 50 + (position_diff * 5) + coop_bonus
    min_offer = max(20, suggested_vp - 10)
    max_offer = min(80, suggested_vp + 10)
    return suggested_vp, min_offer, max_offer


def compute_acceptance_probability(offer: float, fair_value: float, personality_factor: float = 1.0) -> float:
    """Compute probability that opponent accepts an offer.

    A simple model where:
    - Offers at or above fair value are likely accepted
    - Offers below fair value have decreasing acceptance probability
    - Personality factor adjusts acceptance threshold

    Args:
        offer: The VP offer to opponent (what they would receive)
        fair_value: What opponent considers fair (typically 100 - suggested_vp)
        personality_factor: 0.5 = aggressive (wants more), 1.5 = accommodating

    Returns:
        Probability of acceptance [0, 1]
    """
    # Difference between offer and what opponent wants
    delta = offer - (fair_value * personality_factor)

    # Sigmoid-like acceptance curve
    if delta >= 10:
        return 0.95
    elif delta >= 0:
        return 0.7 + (delta / 10) * 0.25
    elif delta >= -10:
        return 0.3 + (delta + 10) / 10 * 0.4
    elif delta >= -20:
        return 0.05 + (delta + 20) / 10 * 0.25
    else:
        return 0.05


# Test scenarios
SCENARIOS = {
    "ahead_high_coop": SettlementParams(
        my_position=7.0,
        opp_position=5.0,
        cooperation_score=8.0,
    ),
    "ahead_low_coop": SettlementParams(
        my_position=7.0,
        opp_position=5.0,
        cooperation_score=2.0,
    ),
    "behind_high_coop": SettlementParams(
        my_position=3.0,
        opp_position=5.0,
        cooperation_score=8.0,
    ),
    "behind_low_coop": SettlementParams(
        my_position=3.0,
        opp_position=5.0,
        cooperation_score=2.0,
    ),
    "equal_neutral": SettlementParams(
        my_position=5.0,
        opp_position=5.0,
        cooperation_score=5.0,
    ),
    "far_ahead": SettlementParams(
        my_position=9.0,
        opp_position=3.0,
        cooperation_score=5.0,
    ),
    "far_behind": SettlementParams(
        my_position=3.0,
        opp_position=9.0,
        cooperation_score=5.0,
    ),
}


def run_offer_range_verification():
    """Verify that settlement offer ranges are computed correctly."""
    print("=" * 90)
    print("SETTLEMENT OFFER RANGE VERIFICATION")
    print("=" * 90)
    print()

    print(f"{'Scenario':<20} {'My Pos':>8} {'Opp Pos':>8} {'Coop':>6} {'Suggested':>10} {'Min':>8} {'Max':>8}")
    print("-" * 68)

    for name, params in SCENARIOS.items():
        suggested, min_offer, max_offer = compute_settlement_offer_range(params)

        print(
            f"{name:<20} {params.my_position:>8.1f} {params.opp_position:>8.1f} "
            f"{params.cooperation_score:>6.1f} {suggested:>10.1f} {min_offer:>8.1f} {max_offer:>8.1f}"
        )

    print("-" * 68)
    print()

    # Verify constraints
    print("Constraint verification:")
    all_valid = True

    for name, params in SCENARIOS.items():
        suggested, min_offer, max_offer = compute_settlement_offer_range(params)

        valid = True
        issues = []

        if min_offer < 20:
            valid = False
            issues.append("min < 20")
        if max_offer > 80:
            valid = False
            issues.append("max > 80")
        if min_offer > max_offer:
            valid = False
            issues.append("min > max")

        status = "VALID" if valid else f"INVALID: {', '.join(issues)}"
        all_valid = all_valid and valid
        print(f"  {name}: {status}")

    print()
    print(f"Overall: {'ALL VALID' if all_valid else 'SOME INVALID'}")
    print()

    return all_valid


def run_acceptance_simulation(num_trials: int = 10000):
    """Simulate settlement acceptance probabilities."""
    print("=" * 90)
    print("SETTLEMENT ACCEPTANCE SIMULATION")
    print(f"Trials per scenario: {num_trials}")
    print("=" * 90)
    print()

    # Test acceptance at different offer levels
    print("Acceptance rates at different offer levels (neutral personality):")
    print()
    print(f"{'Offer to Opp':>14} {'Fair Value':>12} {'Delta':>8} {'Accept %':>12}")
    print("-" * 46)

    fair_value = 50.0  # Assume equal position baseline
    test_offers = [30, 35, 40, 45, 50, 55, 60, 65, 70]

    for offer in test_offers:
        accepts = 0
        for _ in range(num_trials):
            prob = compute_acceptance_probability(offer, fair_value)
            if random.random() < prob:
                accepts += 1

        accept_rate = accepts / num_trials * 100
        delta = offer - fair_value
        print(f"{offer:>14.1f} {fair_value:>12.1f} {delta:>8.1f} {accept_rate:>11.1f}%")

    print("-" * 46)
    print()

    return True


def run_personality_analysis(num_trials: int = 10000):
    """Analyze how personality affects acceptance."""
    print("=" * 90)
    print("PERSONALITY EFFECT ON ACCEPTANCE")
    print(f"Trials per test: {num_trials}")
    print("=" * 90)
    print()

    fair_value = 50.0
    offer = 45.0  # Slightly below fair

    personalities = [
        (0.5, "Aggressive (wants 25% more)"),
        (0.75, "Somewhat aggressive"),
        (1.0, "Neutral"),
        (1.25, "Somewhat accommodating"),
        (1.5, "Accommodating (accepts 25% less)"),
    ]

    print(f"Test: Offer {offer} VP when fair value is {fair_value} VP")
    print()
    print(f"{'Personality':>35} {'Factor':>8} {'Accept %':>12}")
    print("-" * 55)

    for factor, description in personalities:
        accepts = 0
        for _ in range(num_trials):
            prob = compute_acceptance_probability(offer, fair_value, factor)
            if random.random() < prob:
                accepts += 1

        accept_rate = accepts / num_trials * 100
        print(f"{description:>35} {factor:>8.2f} {accept_rate:>11.1f}%")

    print("-" * 55)
    print()


def run_strategic_offer_analysis():
    """Analyze optimal offer strategies for different scenarios."""
    print("=" * 90)
    print("STRATEGIC OFFER ANALYSIS")
    print("=" * 90)
    print()

    for name, params in SCENARIOS.items():
        suggested, min_offer, max_offer = compute_settlement_offer_range(params)

        # What I keep = 100 - what I offer opponent
        # Opponent's fair value = 100 - suggested
        opp_fair_value = 100 - suggested

        print(f"Scenario: {name}")
        print(f"  Position diff: {params.my_position - params.opp_position:+.1f}")
        print(f"  Cooperation: {params.cooperation_score:.1f}")
        print(f"  Suggested VP for me: {suggested:.1f}")
        print(f"  Valid offer range: [{min_offer:.1f}, {max_offer:.1f}] (what I keep)")
        print(f"  Opponent fair value: {opp_fair_value:.1f} (what they want)")
        print()

        # Analyze offers
        print(f"  {'Offer (I keep)':>16} {'Opp Gets':>12} {'Opp Accept %':>14} {'My EV':>10}")
        print("  " + "-" * 52)

        for my_share in range(int(min_offer), int(max_offer) + 1, 5):
            opp_gets = 100 - my_share
            accept_prob = compute_acceptance_probability(opp_gets, opp_fair_value)
            expected_value = my_share * accept_prob
            print(f"  {my_share:>16.0f} {opp_gets:>12.0f} {accept_prob * 100:>13.1f}% {expected_value:>10.1f}")

        print()

    return True


def run_edge_case_tests():
    """Test edge cases for settlement mechanics."""
    print("=" * 90)
    print("EDGE CASE TESTS")
    print("=" * 90)
    print()

    edge_cases = [
        ("extreme_ahead", SettlementParams(10.0, 0.1, 10.0)),
        ("extreme_behind", SettlementParams(0.1, 10.0, 0.0)),
        ("zero_coop", SettlementParams(5.0, 5.0, 0.0)),
        ("max_coop", SettlementParams(5.0, 5.0, 10.0)),
    ]

    print(f"{'Case':<20} {'Suggested':>10} {'Min':>8} {'Max':>8} {'Clamped':>10}")
    print("-" * 58)

    for name, params in edge_cases:
        suggested, min_offer, max_offer = compute_settlement_offer_range(params)

        # Check if clamping was applied (range constraints kicked in)
        raw_min = suggested - 10
        raw_max = suggested + 10
        clamped = min_offer != raw_min or max_offer != raw_max
        status = "YES" if clamped else "NO"

        print(f"{name:<20} {suggested:>10.1f} {min_offer:>8.1f} {max_offer:>8.1f} {status:>10}")

    print("-" * 58)
    print()

    # Verify all ranges are valid after clamping
    print("Constraint verification (min >= 20, max <= 80, min <= max):")
    all_valid = True
    for name, params in edge_cases:
        suggested, min_offer, max_offer = compute_settlement_offer_range(params)
        valid = min_offer >= 20 and max_offer <= 80 and min_offer <= max_offer
        if not valid:
            all_valid = False
            print(f"  {name}: INVALID (min={min_offer:.1f}, max={max_offer:.1f})")
        else:
            print(f"  {name}: VALID")

    print()
    if not all_valid:
        print("Note: Invalid ranges indicate edge cases where clamping creates")
        print("impossible settlement zones. These should be handled specially in game.")
    print()

    # Show raw suggested values before clamping
    print("Raw suggested values (before range clamping):")
    for name, params in edge_cases:
        position_diff = params.my_position - params.opp_position
        coop_bonus = (params.cooperation_score - 5) * 2
        raw_suggested = 50 + (position_diff * 5) + coop_bonus
        print(f"  {name}: {raw_suggested:.1f}")

    print()


def main():
    """Run all settlement simulations."""
    parser = argparse.ArgumentParser(description="Run settlement protocol simulation")
    parser.add_argument("--trials", type=int, default=10000, help="Number of trials per test (default: 10000)")
    parser.add_argument("--seed", type=int, default=None, help="Random seed for reproducibility")
    args = parser.parse_args()

    if args.seed is not None:
        random.seed(args.seed)

    print()
    print("SETTLEMENT PROTOCOL SIMULATION")
    print("=" * 90)
    print()

    # Run all tests
    run_offer_range_verification()
    run_acceptance_simulation(args.trials)
    run_personality_analysis(args.trials)
    run_strategic_offer_analysis()
    run_edge_case_tests()

    print("=" * 90)
    print("SIMULATION COMPLETE")
    print("=" * 90)


if __name__ == "__main__":
    main()
