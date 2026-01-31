#!/usr/bin/env python3
"""Generate markdown report from playtest results.

Reads all result JSON files from the work directory and generates
a comprehensive markdown report.

Usage:
    uv run python scripts/playtest/generate_report.py --work-dir playtest_work --output docs/PLAYTEST_REPORT.md
"""

import argparse
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path


def load_results(work_dir: Path) -> list[dict]:
    """Load all result JSON files from work directory."""
    results_dir = work_dir / "results"
    all_results = []

    for result_file in results_dir.glob("*.json"):
        try:
            with open(result_file) as f:
                data = json.load(f)
                all_results.append(data)
        except Exception as e:
            print(f"Warning: Could not load {result_file}: {e}")

    return all_results


def generate_report(results: list[dict], output_path: Path) -> None:
    """Generate markdown report from results."""
    lines = [
        "# Comprehensive LLM Playtest Report",
        "",
        f"**Generated:** {datetime.now().isoformat()}",
        "",
        "---",
        "",
    ]

    # Aggregate all games
    all_games = []
    for result in results:
        for game in result.get("games", []):
            game["matchup_scenario"] = result.get("scenario", "unknown")
            game["matchup_player_a"] = result.get("player_a", "unknown")
            game["matchup_player_b"] = result.get("player_b", "unknown")
            all_games.append(game)

    if not all_games:
        lines.append("No games found in results.")
        output_path.write_text("\n".join(lines))
        return

    valid_games = [g for g in all_games if g.get("error") is None]

    # Overall summary
    lines.extend([
        "## Overall Summary",
        "",
        f"**Total Games:** {len(all_games)}",
        f"**Valid Games:** {len(valid_games)}",
        f"**Errors:** {len(all_games) - len(valid_games)}",
        "",
    ])

    if valid_games:
        settlements = sum(1 for g in valid_games if g.get("ending_type") == "settlement")
        md = sum(1 for g in valid_games if g.get("ending_type") == "mutual_destruction")
        a_wins = sum(1 for g in valid_games if g.get("winner") == "A")
        b_wins = sum(1 for g in valid_games if g.get("winner") == "B")
        avg_turns = sum(g.get("turns", 0) for g in valid_games) / len(valid_games)
        avg_risk = sum(g.get("final_risk", 0) for g in valid_games) / len(valid_games)

        lines.extend([
            "| Metric | Value |",
            "|--------|-------|",
            f"| Settlement Rate | {settlements / len(valid_games) * 100:.1f}% |",
            f"| Mutual Destruction Rate | {md / len(valid_games) * 100:.1f}% |",
            f"| Player A Win Rate | {a_wins / len(valid_games) * 100:.1f}% |",
            f"| Player B Win Rate | {b_wins / len(valid_games) * 100:.1f}% |",
            f"| Average Game Length | {avg_turns:.1f} turns |",
            f"| Average Final Risk | {avg_risk:.2f} |",
            "",
        ])

        # By matchup type
        lines.extend([
            "## Results by Matchup Type",
            "",
        ])

        matchup_types = {
            "historical_vs_historical": [],
            "smart_vs_historical": [],
        }

        for g in valid_games:
            pa = g.get("matchup_player_a", "")
            pb = g.get("matchup_player_b", "")
            if "smart" in pa or "smart" in pb:
                matchup_types["smart_vs_historical"].append(g)
            else:
                matchup_types["historical_vs_historical"].append(g)

        for matchup_name, games in matchup_types.items():
            if not games:
                continue

            lines.append(f"### {matchup_name.replace('_', ' ').title()}")
            lines.append("")

            settlements = sum(1 for g in games if g.get("ending_type") == "settlement")
            md = sum(1 for g in games if g.get("ending_type") == "mutual_destruction")

            lines.extend([
                "| Metric | Value |",
                "|--------|-------|",
                f"| Games | {len(games)} |",
                f"| Settlement Rate | {settlements / len(games) * 100:.1f}% |",
                f"| MD Rate | {md / len(games) * 100:.1f}% |",
                "",
            ])

        # By scenario
        lines.extend([
            "## Results by Scenario",
            "",
            "| Scenario | Games | Settlement | MD | A Wins | B Wins |",
            "|----------|-------|------------|-----|--------|--------|",
        ])

        by_scenario = defaultdict(list)
        for g in valid_games:
            by_scenario[g.get("matchup_scenario", "unknown")].append(g)

        for scenario, games in sorted(by_scenario.items()):
            settlements = sum(1 for g in games if g.get("ending_type") == "settlement")
            md = sum(1 for g in games if g.get("ending_type") == "mutual_destruction")
            a_wins = sum(1 for g in games if g.get("winner") == "A")
            b_wins = sum(1 for g in games if g.get("winner") == "B")

            lines.append(
                f"| {scenario} | {len(games)} | "
                f"{settlements} ({settlements/len(games)*100:.0f}%) | "
                f"{md} ({md/len(games)*100:.0f}%) | "
                f"{a_wins} | {b_wins} |"
            )

        lines.append("")

        # Detailed results table
        lines.extend([
            "## Detailed Matchup Results",
            "",
            "| Scenario | Player A | Player B | Games | A Wins | B Wins | Settlement | MD |",
            "|----------|----------|----------|-------|--------|--------|------------|-----|",
        ])

        for result in results:
            scenario = result.get("scenario", "unknown")
            player_a = result.get("player_a", "unknown")
            player_b = result.get("player_b", "unknown")
            games = [g for g in result.get("games", []) if g.get("error") is None]

            if not games:
                continue

            a_wins = sum(1 for g in games if g.get("winner") == "A")
            b_wins = sum(1 for g in games if g.get("winner") == "B")
            settlements = sum(1 for g in games if g.get("ending_type") == "settlement")
            md = sum(1 for g in games if g.get("ending_type") == "mutual_destruction")

            # Simplify player names
            pa_short = player_a.replace("historical:", "").replace("smart", "Smart")
            pb_short = player_b.replace("historical:", "").replace("smart", "Smart")

            lines.append(
                f"| {scenario} | {pa_short} | {pb_short} | "
                f"{len(games)} | {a_wins} | {b_wins} | {settlements} | {md} |"
            )

    # Errors
    error_games = [g for g in all_games if g.get("error")]
    if error_games:
        lines.extend([
            "",
            "## Errors",
            "",
        ])
        for g in error_games[:20]:
            lines.append(f"- {g.get('scenario_id', 'unknown')}: {g.get('error', 'unknown error')}")
        if len(error_games) > 20:
            lines.append(f"- ... and {len(error_games) - 20} more errors")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines))
    print(f"Report written to: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Generate playtest report")
    parser.add_argument("--work-dir", required=True, help="Work directory with results")
    parser.add_argument("--output", required=True, help="Output markdown file")
    args = parser.parse_args()

    work_dir = Path(args.work_dir)
    output_path = Path(args.output)

    results = load_results(work_dir)
    print(f"Loaded {len(results)} result files")

    generate_report(results, output_path)


if __name__ == "__main__":
    main()
