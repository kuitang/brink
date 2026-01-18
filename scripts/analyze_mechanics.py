#!/usr/bin/env python3
"""
Deterministic mechanics analysis - threshold-based issue detection.

This script analyzes playtest results against expected thresholds from GAME_MANUAL.md.
All analysis is pure Python with no LLM calls.

Usage:
    python scripts/analyze_mechanics.py playtest_results.json --output analysis.json
    python scripts/analyze_mechanics.py playtest_results.json --format text
    python scripts/analyze_mechanics.py --help

The input playtest_results.json should have the structure:
{
  "pairings": {
    "Strategy1:Strategy2": {
      "wins_a": 45,
      "wins_b": 42,
      "ties": 13,
      "total_games": 100,
      "total_turns": 1123,
      "mutual_destructions": 5,
      "crisis_terminations": 8,
      "eliminations": 12,
      "settlements": 35,
      "vp_scores_a": [52.3, 48.1, ...],
      "vp_scores_b": [47.7, 51.9, ...]
    },
    ...
  },
  "aggregate": {
    "avg_turns": 11.2,
    "settlement_rate": 0.35,
    "vp_std_dev": 18.5,
    ...
  }
}
"""

import argparse
import json
import statistics
import sys
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Optional


class IssueSeverity(Enum):
    """Severity levels for detected issues."""
    CRITICAL = "critical"
    MAJOR = "major"
    MINOR = "minor"


@dataclass
class Issue:
    """A detected issue in the mechanics analysis."""
    severity: IssueSeverity
    message: str
    metric: str
    value: float
    threshold: float

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "severity": self.severity.value,
            "message": self.message,
            "metric": self.metric,
            "value": self.value,
            "threshold": self.threshold,
        }


@dataclass
class AnalysisReport:
    """Report from mechanics analysis."""
    issues: list[Issue] = field(default_factory=list)
    passed: bool = True
    summary: dict = field(default_factory=dict)

    def add_issue(
        self,
        severity: str,
        message: str,
        metric: str = "",
        value: float = 0.0,
        threshold: float = 0.0,
    ) -> None:
        """Add an issue to the report.

        Args:
            severity: One of "critical", "major", "minor"
            message: Human-readable description of the issue
            metric: Name of the metric that triggered the issue
            value: Actual value of the metric
            threshold: Threshold that was violated
        """
        self.issues.append(Issue(
            severity=IssueSeverity(severity.lower()),
            message=message,
            metric=metric,
            value=value,
            threshold=threshold,
        ))
        if severity.lower() == "critical":
            self.passed = False

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "passed": self.passed,
            "issues": [issue.to_dict() for issue in self.issues],
            "summary": self.summary,
        }


# Default thresholds from GAME_MANUAL.md and ENGINEERING_DESIGN.md
DEFAULT_THRESHOLDS = {
    "dominant_strategy": 0.60,      # Fail if any pairing >60% win rate
    "variance_min": 10.0,           # VP std dev should be >=10
    "variance_max": 40.0,           # VP std dev should be <=40
    "settlement_rate_min": 0.30,    # At least 30% settlements
    "settlement_rate_max": 0.70,    # At most 70% settlements
    "avg_game_length_min": 8.0,     # Games shouldn't be too short
    "avg_game_length_max": 16.0,    # Games shouldn't exceed max turns
}


def compute_summary_from_results(playtest_results: dict) -> dict:
    """Compute summary statistics from playtest results.

    Args:
        playtest_results: Raw playtest results dictionary

    Returns:
        Summary dictionary with computed statistics
    """
    pairings = playtest_results.get("pairings", {})

    if not pairings:
        return {
            "total_games": 0,
            "avg_turns": 0.0,
            "dominant_strategies": [],
            "vp_std_dev": 0.0,
            "settlement_rate": 0.0,
        }

    # Aggregate statistics
    total_games = 0
    total_turns = 0
    total_settlements = 0
    all_vp_scores = []
    strategy_wins = {}
    strategy_games = {}
    dominant_strategies = []

    for pairing_name, stats in pairings.items():
        games = stats.get("total_games", 0)
        total_games += games
        total_turns += stats.get("total_turns", 0)
        total_settlements += stats.get("settlements", 0)

        # Collect VP scores for variance calculation
        if "vp_scores_a" in stats:
            all_vp_scores.extend(stats["vp_scores_a"])
        if "vp_scores_b" in stats:
            all_vp_scores.extend(stats["vp_scores_b"])

        # Parse strategy names from pairing
        strategies = pairing_name.split(":")
        if len(strategies) >= 2:
            strat_a, strat_b = strategies[0], strategies[1]

            # Track wins for strategy A
            if strat_a not in strategy_wins:
                strategy_wins[strat_a] = 0
                strategy_games[strat_a] = 0
            strategy_wins[strat_a] += stats.get("wins_a", 0)
            strategy_games[strat_a] += games

            # Track wins for strategy B (if different from A)
            if strat_a != strat_b:
                if strat_b not in strategy_wins:
                    strategy_wins[strat_b] = 0
                    strategy_games[strat_b] = 0
                strategy_wins[strat_b] += stats.get("wins_b", 0)
                strategy_games[strat_b] += games

    # Calculate average game length
    avg_turns = total_turns / total_games if total_games > 0 else 0.0

    # Calculate settlement rate
    settlement_rate = total_settlements / total_games if total_games > 0 else 0.0

    # Calculate VP standard deviation
    vp_std_dev = 0.0
    if len(all_vp_scores) >= 2:
        vp_std_dev = statistics.stdev(all_vp_scores)
    elif playtest_results.get("aggregate", {}).get("vp_std_dev"):
        # Fall back to pre-computed value if available
        vp_std_dev = playtest_results["aggregate"]["vp_std_dev"]

    # Use pre-computed values from aggregate if VP scores not provided
    aggregate = playtest_results.get("aggregate", {})
    if vp_std_dev == 0.0 and "vp_std_dev" in aggregate:
        vp_std_dev = aggregate["vp_std_dev"]
    if avg_turns == 0.0 and "avg_turns" in aggregate:
        avg_turns = aggregate["avg_turns"]
    if settlement_rate == 0.0 and "settlement_rate" in aggregate:
        settlement_rate = aggregate["settlement_rate"]

    # Identify dominant strategies (>60% win rate)
    for strat, wins in strategy_wins.items():
        games = strategy_games.get(strat, 0)
        if games > 0:
            win_rate = wins / games
            if win_rate > DEFAULT_THRESHOLDS["dominant_strategy"]:
                dominant_strategies.append({
                    "strategy": strat,
                    "win_rate": win_rate,
                    "games": games,
                })

    return {
        "total_games": total_games,
        "avg_turns": avg_turns,
        "dominant_strategies": dominant_strategies,
        "vp_std_dev": vp_std_dev,
        "settlement_rate": settlement_rate,
    }


def check_dominant_strategy(
    playtest_results: dict,
    report: AnalysisReport,
    threshold: float,
) -> list[dict]:
    """Check for dominant strategies.

    A dominant strategy is one with >60% win rate against all other strategies.

    Args:
        playtest_results: Playtest results dictionary
        report: Analysis report to add issues to
        threshold: Win rate threshold (default 0.60)

    Returns:
        List of dominant strategies found
    """
    pairings = playtest_results.get("pairings", {})
    dominant_strategies = []

    for pairing_name, stats in pairings.items():
        total_games = stats.get("total_games", 0)
        if total_games == 0:
            continue

        win_rate_a = stats.get("wins_a", 0) / total_games
        win_rate_b = stats.get("wins_b", 0) / total_games

        # Check if strategy A is dominant in this pairing
        if win_rate_a > threshold:
            strategies = pairing_name.split(":")
            strat_a = strategies[0] if strategies else pairing_name
            report.add_issue(
                severity="critical",
                message=f"Dominant strategy detected: {strat_a} wins {win_rate_a:.0%} in {pairing_name}",
                metric="dominant_strategy",
                value=win_rate_a,
                threshold=threshold,
            )
            dominant_strategies.append({
                "pairing": pairing_name,
                "strategy": strat_a,
                "win_rate": win_rate_a,
            })

        # Check if strategy B is dominant in this pairing
        if win_rate_b > threshold:
            strategies = pairing_name.split(":")
            strat_b = strategies[1] if len(strategies) > 1 else pairing_name
            report.add_issue(
                severity="critical",
                message=f"Dominant strategy detected: {strat_b} wins {win_rate_b:.0%} in {pairing_name}",
                metric="dominant_strategy",
                value=win_rate_b,
                threshold=threshold,
            )
            dominant_strategies.append({
                "pairing": pairing_name,
                "strategy": strat_b,
                "win_rate": win_rate_b,
            })

    return dominant_strategies


def check_variance_calibration(
    vp_std_dev: float,
    report: AnalysisReport,
    variance_min: float,
    variance_max: float,
) -> None:
    """Check if VP variance is within expected range.

    Args:
        vp_std_dev: Standard deviation of VP scores
        report: Analysis report to add issues to
        variance_min: Minimum acceptable variance (default 10)
        variance_max: Maximum acceptable variance (default 40)
    """
    if vp_std_dev < variance_min:
        report.add_issue(
            severity="major",
            message=f"VP variance too low: {vp_std_dev:.1f} (expected >= {variance_min})",
            metric="vp_variance",
            value=vp_std_dev,
            threshold=variance_min,
        )

    if vp_std_dev > variance_max:
        report.add_issue(
            severity="major",
            message=f"VP variance too high: {vp_std_dev:.1f} (expected <= {variance_max})",
            metric="vp_variance",
            value=vp_std_dev,
            threshold=variance_max,
        )


def check_settlement_rate(
    settlement_rate: float,
    report: AnalysisReport,
    rate_min: float,
    rate_max: float,
) -> None:
    """Check if settlement rate is within expected range.

    Args:
        settlement_rate: Proportion of games ending in settlement
        report: Analysis report to add issues to
        rate_min: Minimum acceptable settlement rate (default 0.30)
        rate_max: Maximum acceptable settlement rate (default 0.70)
    """
    if settlement_rate < rate_min:
        report.add_issue(
            severity="major",
            message=f"Settlement rate low: {settlement_rate:.0%} (expected >= {rate_min:.0%})",
            metric="settlement_rate",
            value=settlement_rate,
            threshold=rate_min,
        )

    if settlement_rate > rate_max:
        report.add_issue(
            severity="major",
            message=f"Settlement rate high: {settlement_rate:.0%} (expected <= {rate_max:.0%})",
            metric="settlement_rate",
            value=settlement_rate,
            threshold=rate_max,
        )


def check_game_length(
    avg_turns: float,
    report: AnalysisReport,
    length_min: float,
    length_max: float,
) -> None:
    """Check if average game length is within expected range.

    Args:
        avg_turns: Average number of turns per game
        report: Analysis report to add issues to
        length_min: Minimum acceptable average game length (default 8)
        length_max: Maximum acceptable average game length (default 16)
    """
    if avg_turns < length_min:
        report.add_issue(
            severity="minor",
            message=f"Average game length too short: {avg_turns:.1f} turns (expected >= {length_min})",
            metric="avg_game_length",
            value=avg_turns,
            threshold=length_min,
        )

    if avg_turns > length_max:
        report.add_issue(
            severity="minor",
            message=f"Average game length too long: {avg_turns:.1f} turns (expected <= {length_max})",
            metric="avg_game_length",
            value=avg_turns,
            threshold=length_max,
        )


def analyze_mechanics(
    playtest_results: dict,
    thresholds: Optional[dict] = None,
) -> AnalysisReport:
    """Analyze playtest results against expected thresholds.

    Args:
        playtest_results: Dictionary containing playtest results with structure:
            {
                "pairings": {"Strategy1:Strategy2": {...}, ...},
                "aggregate": {"avg_turns": ..., "vp_std_dev": ..., ...}
            }
        thresholds: Optional custom thresholds. Uses DEFAULT_THRESHOLDS if not provided.

    Returns:
        AnalysisReport with issues flagged and summary statistics.
    """
    if thresholds is None:
        thresholds = DEFAULT_THRESHOLDS.copy()

    report = AnalysisReport()

    # Compute summary statistics
    summary = compute_summary_from_results(playtest_results)
    report.summary = summary

    # Check 1: Dominant strategy (>60% win rate = CRITICAL)
    check_dominant_strategy(
        playtest_results,
        report,
        threshold=thresholds.get("dominant_strategy", DEFAULT_THRESHOLDS["dominant_strategy"]),
    )

    # Check 2: VP variance calibration (outside 10-40 range = MAJOR)
    check_variance_calibration(
        summary["vp_std_dev"],
        report,
        variance_min=thresholds.get("variance_min", DEFAULT_THRESHOLDS["variance_min"]),
        variance_max=thresholds.get("variance_max", DEFAULT_THRESHOLDS["variance_max"]),
    )

    # Check 3: Settlement rate (outside 30-70% = MAJOR)
    check_settlement_rate(
        summary["settlement_rate"],
        report,
        rate_min=thresholds.get("settlement_rate_min", DEFAULT_THRESHOLDS["settlement_rate_min"]),
        rate_max=thresholds.get("settlement_rate_max", DEFAULT_THRESHOLDS["settlement_rate_max"]),
    )

    # Check 4: Average game length (outside 8-16 = MINOR)
    check_game_length(
        summary["avg_turns"],
        report,
        length_min=thresholds.get("avg_game_length_min", DEFAULT_THRESHOLDS["avg_game_length_min"]),
        length_max=thresholds.get("avg_game_length_max", DEFAULT_THRESHOLDS["avg_game_length_max"]),
    )

    return report


def format_text_report(report: AnalysisReport) -> str:
    """Format analysis report as human-readable text.

    Args:
        report: Analysis report to format

    Returns:
        Formatted text string
    """
    lines = []
    lines.append("=" * 80)
    lines.append("MECHANICS ANALYSIS REPORT")
    lines.append("=" * 80)

    # Overall status
    status = "PASSED" if report.passed else "FAILED"
    lines.append(f"\nOverall Status: {status}")

    # Summary statistics
    lines.append("\n" + "-" * 40)
    lines.append("SUMMARY STATISTICS")
    lines.append("-" * 40)
    summary = report.summary
    lines.append(f"  Total Games: {summary.get('total_games', 'N/A')}")
    lines.append(f"  Average Turns: {summary.get('avg_turns', 0):.1f}")
    lines.append(f"  VP Std Dev: {summary.get('vp_std_dev', 0):.1f}")
    lines.append(f"  Settlement Rate: {summary.get('settlement_rate', 0):.0%}")

    dominant = summary.get("dominant_strategies", [])
    if dominant:
        lines.append(f"  Dominant Strategies: {len(dominant)} found")
        for d in dominant:
            lines.append(f"    - {d['strategy']}: {d['win_rate']:.0%} win rate")
    else:
        lines.append("  Dominant Strategies: None detected")

    # Issues
    lines.append("\n" + "-" * 40)
    lines.append("ISSUES DETECTED")
    lines.append("-" * 40)

    if not report.issues:
        lines.append("  No issues detected.")
    else:
        # Group by severity
        critical = [i for i in report.issues if i.severity == IssueSeverity.CRITICAL]
        major = [i for i in report.issues if i.severity == IssueSeverity.MAJOR]
        minor = [i for i in report.issues if i.severity == IssueSeverity.MINOR]

        if critical:
            lines.append(f"\n  CRITICAL ({len(critical)}):")
            for issue in critical:
                lines.append(f"    - {issue.message}")

        if major:
            lines.append(f"\n  MAJOR ({len(major)}):")
            for issue in major:
                lines.append(f"    - {issue.message}")

        if minor:
            lines.append(f"\n  MINOR ({len(minor)}):")
            for issue in minor:
                lines.append(f"    - {issue.message}")

    lines.append("\n" + "=" * 80)

    return "\n".join(lines)


def load_playtest_results(path: Path) -> dict:
    """Load playtest results from a JSON file.

    Args:
        path: Path to the JSON file

    Returns:
        Parsed playtest results dictionary

    Raises:
        FileNotFoundError: If the file doesn't exist
        json.JSONDecodeError: If the file isn't valid JSON
    """
    with open(path) as f:
        return json.load(f)


def main() -> int:
    """Main entry point for the analyze_mechanics script.

    Returns:
        Exit code (0 for success/passed, 1 for failed analysis)
    """
    parser = argparse.ArgumentParser(
        description="Analyze playtest results against expected thresholds.",
        epilog="""
Examples:
  python scripts/analyze_mechanics.py playtest_results.json
  python scripts/analyze_mechanics.py playtest_results.json --output analysis.json
  python scripts/analyze_mechanics.py playtest_results.json --format text
  python scripts/analyze_mechanics.py playtest_results.json --dominant-strategy 0.55

Thresholds (from GAME_MANUAL.md):
  - Dominant strategy: >60% win rate = CRITICAL
  - VP variance: outside 10-40 range = MAJOR
  - Settlement rate: outside 30-70% = MAJOR
  - Average game length: outside 8-16 turns = MINOR
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "input",
        type=Path,
        help="Path to playtest results JSON file",
    )

    parser.add_argument(
        "-o", "--output",
        type=Path,
        default=None,
        help="Output path for analysis report (default: stdout)",
    )

    parser.add_argument(
        "-f", "--format",
        choices=["json", "text"],
        default="json",
        help="Output format (default: json)",
    )

    # Custom threshold arguments
    parser.add_argument(
        "--dominant-strategy",
        type=float,
        default=DEFAULT_THRESHOLDS["dominant_strategy"],
        help=f"Win rate threshold for dominant strategy detection (default: {DEFAULT_THRESHOLDS['dominant_strategy']})",
    )

    parser.add_argument(
        "--variance-min",
        type=float,
        default=DEFAULT_THRESHOLDS["variance_min"],
        help=f"Minimum acceptable VP std dev (default: {DEFAULT_THRESHOLDS['variance_min']})",
    )

    parser.add_argument(
        "--variance-max",
        type=float,
        default=DEFAULT_THRESHOLDS["variance_max"],
        help=f"Maximum acceptable VP std dev (default: {DEFAULT_THRESHOLDS['variance_max']})",
    )

    parser.add_argument(
        "--settlement-rate-min",
        type=float,
        default=DEFAULT_THRESHOLDS["settlement_rate_min"],
        help=f"Minimum acceptable settlement rate (default: {DEFAULT_THRESHOLDS['settlement_rate_min']})",
    )

    parser.add_argument(
        "--settlement-rate-max",
        type=float,
        default=DEFAULT_THRESHOLDS["settlement_rate_max"],
        help=f"Maximum acceptable settlement rate (default: {DEFAULT_THRESHOLDS['settlement_rate_max']})",
    )

    parser.add_argument(
        "--avg-game-length-min",
        type=float,
        default=DEFAULT_THRESHOLDS["avg_game_length_min"],
        help=f"Minimum acceptable average game length (default: {DEFAULT_THRESHOLDS['avg_game_length_min']})",
    )

    parser.add_argument(
        "--avg-game-length-max",
        type=float,
        default=DEFAULT_THRESHOLDS["avg_game_length_max"],
        help=f"Maximum acceptable average game length (default: {DEFAULT_THRESHOLDS['avg_game_length_max']})",
    )

    args = parser.parse_args()

    # Load playtest results
    if not args.input.exists():
        print(f"Error: Input file not found: {args.input}", file=sys.stderr)
        return 1

    try:
        playtest_results = load_playtest_results(args.input)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in {args.input}: {e}", file=sys.stderr)
        return 1

    # Build custom thresholds
    thresholds = {
        "dominant_strategy": args.dominant_strategy,
        "variance_min": args.variance_min,
        "variance_max": args.variance_max,
        "settlement_rate_min": args.settlement_rate_min,
        "settlement_rate_max": args.settlement_rate_max,
        "avg_game_length_min": args.avg_game_length_min,
        "avg_game_length_max": args.avg_game_length_max,
    }

    # Run analysis
    report = analyze_mechanics(playtest_results, thresholds)

    # Format output
    if args.format == "json":
        output = json.dumps(report.to_dict(), indent=2)
    else:
        output = format_text_report(report)

    # Write output
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, "w") as f:
            f.write(output)
        print(f"Analysis written to {args.output}")
    else:
        print(output)

    # Return exit code based on analysis result
    return 0 if report.passed else 1


if __name__ == "__main__":
    sys.exit(main())
