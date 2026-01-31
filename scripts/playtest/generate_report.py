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
        data = json.loads(result_file.read_text())
        all_results.append(data)

    return all_results


def _calculate_stats(games: list[dict]) -> dict:
    """Calculate statistics for a list of games."""
    if not games:
        return {}
    return {
        "count": len(games),
        "settlements": sum(1 for g in games if g.get("ending_type") == "settlement"),
        "md": sum(1 for g in games if g.get("ending_type") == "mutual_destruction"),
        "a_wins": sum(1 for g in games if g.get("winner") == "A"),
        "b_wins": sum(1 for g in games if g.get("winner") == "B"),
        "avg_turns": sum(g.get("turns", 0) for g in games) / len(games),
        "avg_risk": sum(g.get("final_risk", 0) for g in games) / len(games),
    }


def _format_percent(count: int, total: int) -> str:
    """Format a count as a percentage."""
    return f"{count / total * 100:.1f}%" if total > 0 else "0%"


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

    # Aggregate all games with matchup metadata
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
    stats = _calculate_stats(valid_games)

    # Overall summary
    lines.extend(
        [
            "## Overall Summary",
            "",
            f"**Total Games:** {len(all_games)}",
            f"**Valid Games:** {len(valid_games)}",
            f"**Errors:** {len(all_games) - len(valid_games)}",
            "",
        ]
    )

    if valid_games:
        lines.extend(
            [
                "| Metric | Value |",
                "|--------|-------|",
                f"| Settlement Rate | {_format_percent(stats['settlements'], stats['count'])} |",
                f"| Mutual Destruction Rate | {_format_percent(stats['md'], stats['count'])} |",
                f"| Player A Win Rate | {_format_percent(stats['a_wins'], stats['count'])} |",
                f"| Player B Win Rate | {_format_percent(stats['b_wins'], stats['count'])} |",
                f"| Average Game Length | {stats['avg_turns']:.1f} turns |",
                f"| Average Final Risk | {stats['avg_risk']:.2f} |",
                "",
            ]
        )

        # By matchup type
        lines.extend(["## Results by Matchup Type", ""])

        historical_games = [
            g
            for g in valid_games
            if "smart" not in g.get("matchup_player_a", "") and "smart" not in g.get("matchup_player_b", "")
        ]
        smart_games = [g for g in valid_games if g not in historical_games]

        for matchup_name, games in [
            ("Historical vs Historical", historical_games),
            ("Smart vs Historical", smart_games),
        ]:
            if not games:
                continue
            game_stats = _calculate_stats(games)
            lines.extend(
                [
                    f"### {matchup_name}",
                    "",
                    "| Metric | Value |",
                    "|--------|-------|",
                    f"| Games | {game_stats['count']} |",
                    f"| Settlement Rate | {_format_percent(game_stats['settlements'], game_stats['count'])} |",
                    f"| MD Rate | {_format_percent(game_stats['md'], game_stats['count'])} |",
                    "",
                ]
            )

        # By scenario
        lines.extend(
            [
                "## Results by Scenario",
                "",
                "| Scenario | Games | Settlement | MD | A Wins | B Wins |",
                "|----------|-------|------------|-----|--------|--------|",
            ]
        )

        by_scenario = defaultdict(list)
        for g in valid_games:
            by_scenario[g.get("matchup_scenario", "unknown")].append(g)

        for scenario, games in sorted(by_scenario.items()):
            s = _calculate_stats(games)
            lines.append(
                f"| {scenario} | {s['count']} | "
                f"{s['settlements']} ({s['settlements'] * 100 // s['count']}%) | "
                f"{s['md']} ({s['md'] * 100 // s['count']}%) | "
                f"{s['a_wins']} | {s['b_wins']} |"
            )
        lines.append("")

        # Detailed results table
        lines.extend(
            [
                "## Detailed Matchup Results",
                "",
                "| Scenario | Player A | Player B | Games | A Wins | B Wins | Settlement | MD |",
                "|----------|----------|----------|-------|--------|--------|------------|-----|",
            ]
        )

        for result in results:
            games = [g for g in result.get("games", []) if g.get("error") is None]
            if not games:
                continue

            s = _calculate_stats(games)
            pa_short = result.get("player_a", "unknown").replace("historical:", "").replace("smart", "Smart")
            pb_short = result.get("player_b", "unknown").replace("historical:", "").replace("smart", "Smart")

            lines.append(
                f"| {result.get('scenario', 'unknown')} | {pa_short} | {pb_short} | "
                f"{s['count']} | {s['a_wins']} | {s['b_wins']} | {s['settlements']} | {s['md']} |"
            )

    # Errors
    error_games = [g for g in all_games if g.get("error")]
    if error_games:
        lines.extend(["", "## Errors", ""])
        for g in error_games[:20]:
            lines.append(f"- {g.get('scenario_id', 'unknown')}: {g.get('error', 'unknown error')}")
        if len(error_games) > 20:
            lines.append(f"- ... and {len(error_games) - 20} more errors")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines))
    print(f"Report written to: {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate playtest report")
    parser.add_argument("--work-dir", required=True, help="Work directory with results")
    parser.add_argument("--output", required=True, help="Output markdown file")
    args = parser.parse_args()

    results = load_results(Path(args.work_dir))
    print(f"Loaded {len(results)} result files")

    generate_report(results, Path(args.output))


if __name__ == "__main__":
    main()
