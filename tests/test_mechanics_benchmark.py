"""Performance benchmark tests for mechanics analysis.

These tests verify that mechanics analysis completes within expected time limits.

From ENGINEERING_DESIGN.md Milestone 5.3:
- Performance benchmark (<10 seconds for 100 games) - NOT BENCHMARKED

This module implements that benchmark.
"""

import json
import time
import tempfile
from pathlib import Path

import pytest

from brinksmanship.testing.playtester import (
    PlaytestRunner,
    PlaytestResults,
)

# Import analyze_mechanics from script
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from analyze_mechanics import (
    analyze_mechanics,
    compute_summary_from_results,
    load_playtest_results,
    format_text_report,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def sample_playtest_results_100_games():
    """Generate playtest results for 100 games."""
    runner = PlaytestRunner()

    # Run 100 games across a few pairings for realistic distribution
    results = runner.run_playtest(
        pairings=[
            ("TitForTat", "Nash"),
            ("TitForTat", "AlwaysDefect"),
            ("Nash", "Nash"),
            ("AlwaysCooperate", "Opportunist"),
        ],
        games_per_pairing=25,  # 25 * 4 = 100 games
        output_dir=tempfile.mkdtemp(),
        max_workers=1,  # Sequential for consistent timing
        seed=42,
    )

    return results


@pytest.fixture
def sample_playtest_results_dict(sample_playtest_results_100_games):
    """Convert playtest results to dict format for analysis."""
    return sample_playtest_results_100_games.to_dict()


# =============================================================================
# Benchmark Tests
# =============================================================================


class TestMechanicsAnalysisBenchmark:
    """Benchmark tests for mechanics analysis performance."""

    def test_analysis_completes_under_10_seconds(self, sample_playtest_results_dict):
        """Test that analysis of 100 games completes in under 10 seconds.

        This is the primary benchmark from ENGINEERING_DESIGN.md Milestone 5.3.
        """
        start_time = time.time()

        report = analyze_mechanics(sample_playtest_results_dict)

        elapsed = time.time() - start_time

        assert elapsed < 10.0, f"Analysis took {elapsed:.2f}s, expected < 10s"
        print(f"\nAnalysis completed in {elapsed:.4f} seconds")

    def test_analysis_completes_under_1_second(self, sample_playtest_results_dict):
        """Test that analysis is actually fast (< 1 second for 100 games).

        Since this is pure Python with no LLM calls, it should be very fast.
        """
        start_time = time.time()

        report = analyze_mechanics(sample_playtest_results_dict)

        elapsed = time.time() - start_time

        assert elapsed < 1.0, f"Analysis took {elapsed:.2f}s, expected < 1s"
        print(f"\nAnalysis completed in {elapsed:.4f} seconds (well under requirement)")

    def test_compute_summary_performance(self, sample_playtest_results_dict):
        """Test performance of summary computation."""
        start_time = time.time()

        for _ in range(100):
            summary = compute_summary_from_results(sample_playtest_results_dict)

        elapsed = time.time() - start_time

        # 100 summaries should take < 1 second
        assert elapsed < 1.0, f"100 summaries took {elapsed:.2f}s"
        print(f"\n100 summary computations in {elapsed:.4f} seconds")

    def test_text_report_generation_performance(self, sample_playtest_results_dict):
        """Test performance of text report generation."""
        report = analyze_mechanics(sample_playtest_results_dict)

        start_time = time.time()

        for _ in range(100):
            text = format_text_report(report)

        elapsed = time.time() - start_time

        # 100 text reports should take < 1 second
        assert elapsed < 1.0, f"100 text reports took {elapsed:.2f}s"
        print(f"\n100 text report generations in {elapsed:.4f} seconds")


class TestPlaytestGenerationBenchmark:
    """Benchmark tests for playtest result generation."""

    def test_100_games_generation_time(self):
        """Test how long it takes to generate 100 games worth of results."""
        runner = PlaytestRunner()

        start_time = time.time()

        results = runner.run_playtest(
            pairings=[("TitForTat", "Nash")],
            games_per_pairing=100,
            output_dir=tempfile.mkdtemp(),
            max_workers=1,
            seed=42,
        )

        elapsed = time.time() - start_time

        # 100 games should complete quickly (< 5 seconds)
        # Note: This depends on system performance
        print(f"\n100 games generated in {elapsed:.2f} seconds")
        assert results.aggregate["total_games"] == 100


class TestJSONSerializationBenchmark:
    """Benchmark tests for JSON serialization."""

    def test_results_serialization_performance(self, sample_playtest_results_100_games):
        """Test JSON serialization performance."""
        start_time = time.time()

        for _ in range(100):
            json_str = sample_playtest_results_100_games.to_json()

        elapsed = time.time() - start_time

        assert elapsed < 1.0, f"100 serializations took {elapsed:.2f}s"
        print(f"\n100 JSON serializations in {elapsed:.4f} seconds")

    def test_load_from_file_performance(self, sample_playtest_results_100_games):
        """Test loading results from file performance."""
        # Write to temp file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write(sample_playtest_results_100_games.to_json())
            temp_path = Path(f.name)

        try:
            start_time = time.time()

            for _ in range(100):
                data = load_playtest_results(temp_path)

            elapsed = time.time() - start_time

            assert elapsed < 1.0, f"100 file loads took {elapsed:.2f}s"
            print(f"\n100 file loads in {elapsed:.4f} seconds")
        finally:
            temp_path.unlink()


# =============================================================================
# Combined Benchmark
# =============================================================================


class TestFullPipelineBenchmark:
    """Benchmark for the full analysis pipeline."""

    def test_full_pipeline_under_10_seconds(self):
        """Test the entire pipeline: generate results + analyze.

        This tests the complete flow a user would experience.
        """
        total_start = time.time()

        # Step 1: Generate playtest results
        gen_start = time.time()
        runner = PlaytestRunner()
        results = runner.run_playtest(
            pairings=[
                ("TitForTat", "Nash"),
                ("TitForTat", "AlwaysDefect"),
            ],
            games_per_pairing=50,  # 100 total
            output_dir=tempfile.mkdtemp(),
            max_workers=1,
            seed=42,
        )
        gen_elapsed = time.time() - gen_start

        # Step 2: Analyze results
        analysis_start = time.time()
        report = analyze_mechanics(results.to_dict())
        analysis_elapsed = time.time() - analysis_start

        # Step 3: Generate text report
        report_start = time.time()
        text = format_text_report(report)
        report_elapsed = time.time() - report_start

        total_elapsed = time.time() - total_start

        print(f"\n=== Full Pipeline Benchmark ===")
        print(f"Game generation: {gen_elapsed:.2f}s")
        print(f"Analysis: {analysis_elapsed:.4f}s")
        print(f"Report generation: {report_elapsed:.4f}s")
        print(f"TOTAL: {total_elapsed:.2f}s")

        # The specification says analysis should be < 10 seconds
        # The whole pipeline should still be reasonable
        assert analysis_elapsed < 10.0, "Analysis alone exceeded 10 seconds"
        assert total_elapsed < 30.0, "Full pipeline exceeded 30 seconds"


# =============================================================================
# Scalability Tests
# =============================================================================


class TestScalability:
    """Test how analysis scales with more games."""

    @pytest.mark.parametrize("num_games", [10, 50, 100, 500])
    def test_scaling_with_game_count(self, num_games):
        """Test analysis time scales linearly with game count."""
        runner = PlaytestRunner()
        results = runner.run_pairing("TitForTat", "Nash", num_games=num_games, seed=42)

        # Create results dict
        from brinksmanship.testing.playtester import PlaytestResults
        full_results = PlaytestResults(
            pairings={"TitForTat:Nash": results}
        )
        full_results.compute_aggregate()

        start_time = time.time()
        report = analyze_mechanics(full_results.to_dict())
        elapsed = time.time() - start_time

        print(f"\n{num_games} games: {elapsed:.4f}s")

        # Even 500 games should be fast
        assert elapsed < 1.0, f"{num_games} games took {elapsed:.2f}s"
