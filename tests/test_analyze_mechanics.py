"""Tests for scripts/analyze_mechanics.py module.

Tests cover:
- compute_summary_from_results function
- check_* threshold functions
- analyze_mechanics main function
- format_text_report function

Note: Trivial enum tests (TestIssueSeverity), dataclass tests (TestIssue,
TestAnalysisReport), and constant tests (TestDefaultThresholds) were removed.
See test_removal_log.md for details.
"""

import json
import tempfile
from pathlib import Path

import pytest

# Import from scripts directory - need to add to path or use importlib
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from analyze_mechanics import (
    # Enums and dataclasses
    IssueSeverity,
    Issue,
    AnalysisReport,
    # Constants
    DEFAULT_THRESHOLDS,
    # Functions
    compute_summary_from_results,
    check_dominant_strategy,
    check_variance_calibration,
    check_settlement_rate,
    check_game_length,
    analyze_mechanics,
    format_text_report,
    load_playtest_results,
)


class TestComputeSummaryFromResults:
    """Tests for compute_summary_from_results function."""

    def test_empty_results(self):
        """Test with empty results."""
        results = {"pairings": {}}
        summary = compute_summary_from_results(results)
        assert summary["total_games"] == 0
        assert summary["dominant_strategies"] == []

    def test_basic_computation(self):
        """Test basic summary computation."""
        results = {
            "pairings": {
                "A:B": {
                    "total_games": 100,
                    "total_turns": 1200,
                    "wins_a": 60,
                    "wins_b": 30,
                    "ties": 10,
                    "settlements": 40,
                }
            }
        }
        summary = compute_summary_from_results(results)
        assert summary["total_games"] == 100
        assert summary["avg_turns"] == 12.0
        assert summary["settlement_rate"] == 0.40

    def test_detects_dominant_strategy(self):
        """Test detection of dominant strategy (>60% win rate)."""
        results = {
            "pairings": {
                "DominantStrat:WeakStrat": {
                    "total_games": 100,
                    "total_turns": 1000,
                    "wins_a": 75,
                    "wins_b": 20,
                    "ties": 5,
                }
            }
        }
        summary = compute_summary_from_results(results)
        assert len(summary["dominant_strategies"]) == 1
        assert summary["dominant_strategies"][0]["strategy"] == "DominantStrat"
        assert summary["dominant_strategies"][0]["win_rate"] == 0.75

    def test_computes_from_pairings(self):
        """Test summary includes expected fields from pairings."""
        results = {
            "pairings": {
                "A:B": {
                    "total_games": 100,
                    "total_turns": 1200,
                    "wins_a": 50,
                    "wins_b": 45,
                    "ties": 5,
                    "settlements": 45,
                }
            },
            "aggregate": {}
        }
        summary = compute_summary_from_results(results)
        assert "total_games" in summary
        assert "avg_turns" in summary
        assert "settlement_rate" in summary
        assert "dominant_strategies" in summary
        assert summary["total_games"] == 100


# =============================================================================
# check_dominant_strategy Tests
# =============================================================================


class TestCheckDominantStrategy:
    """Tests for check_dominant_strategy function."""

    def test_no_dominant_strategy(self):
        """Test no issues when no dominant strategy."""
        results = {
            "pairings": {
                "A:B": {
                    "total_games": 100,
                    "wins_a": 55,
                    "wins_b": 40,
                }
            }
        }
        report = AnalysisReport()
        dominant = check_dominant_strategy(results, report, threshold=0.60)
        assert len(dominant) == 0
        assert len(report.issues) == 0
        assert report.passed is True

    def test_detects_dominant_strategy_a(self):
        """Test detects dominant strategy for player A."""
        results = {
            "pairings": {
                "Dominant:Weak": {
                    "total_games": 100,
                    "wins_a": 70,
                    "wins_b": 25,
                }
            }
        }
        report = AnalysisReport()
        dominant = check_dominant_strategy(results, report, threshold=0.60)
        assert len(dominant) == 1
        assert dominant[0]["strategy"] == "Dominant"
        assert report.passed is False  # Critical issue

    def test_detects_dominant_strategy_b(self):
        """Test detects dominant strategy for player B."""
        results = {
            "pairings": {
                "Weak:Dominant": {
                    "total_games": 100,
                    "wins_a": 25,
                    "wins_b": 70,
                }
            }
        }
        report = AnalysisReport()
        dominant = check_dominant_strategy(results, report, threshold=0.60)
        assert len(dominant) == 1
        assert dominant[0]["strategy"] == "Dominant"

    def test_multiple_dominant_strategies(self):
        """Test detects multiple dominant strategies."""
        results = {
            "pairings": {
                "A:B": {
                    "total_games": 100,
                    "wins_a": 70,
                    "wins_b": 25,
                },
                "C:D": {
                    "total_games": 100,
                    "wins_a": 20,
                    "wins_b": 75,
                },
            }
        }
        report = AnalysisReport()
        dominant = check_dominant_strategy(results, report, threshold=0.60)
        assert len(dominant) == 2


# =============================================================================
# check_variance_calibration Tests
# =============================================================================


class TestCheckVarianceCalibration:
    """Tests for check_variance_calibration function."""

    def test_variance_in_range(self):
        """Test no issues when variance is in range."""
        report = AnalysisReport()
        check_variance_calibration(25.0, report, variance_min=10.0, variance_max=40.0)
        assert len(report.issues) == 0

    def test_variance_too_low(self):
        """Test detects variance too low."""
        report = AnalysisReport()
        check_variance_calibration(5.0, report, variance_min=10.0, variance_max=40.0)
        assert len(report.issues) == 1
        assert report.issues[0].severity == IssueSeverity.MAJOR
        assert "too low" in report.issues[0].message

    def test_variance_too_high(self):
        """Test detects variance too high."""
        report = AnalysisReport()
        check_variance_calibration(50.0, report, variance_min=10.0, variance_max=40.0)
        assert len(report.issues) == 1
        assert report.issues[0].severity == IssueSeverity.MAJOR
        assert "too high" in report.issues[0].message

    def test_variance_at_boundaries(self):
        """Test variance at exact boundaries is OK."""
        report = AnalysisReport()
        check_variance_calibration(10.0, report, variance_min=10.0, variance_max=40.0)
        check_variance_calibration(40.0, report, variance_min=10.0, variance_max=40.0)
        assert len(report.issues) == 0


# =============================================================================
# check_settlement_rate Tests
# =============================================================================


class TestCheckSettlementRate:
    """Tests for check_settlement_rate function."""

    def test_settlement_rate_in_range(self):
        """Test no issues when settlement rate is in range."""
        report = AnalysisReport()
        check_settlement_rate(0.50, report, rate_min=0.30, rate_max=0.70)
        assert len(report.issues) == 0

    def test_settlement_rate_too_low(self):
        """Test detects settlement rate too low."""
        report = AnalysisReport()
        check_settlement_rate(0.20, report, rate_min=0.30, rate_max=0.70)
        assert len(report.issues) == 1
        assert report.issues[0].severity == IssueSeverity.MAJOR
        assert "low" in report.issues[0].message

    def test_settlement_rate_too_high(self):
        """Test detects settlement rate too high."""
        report = AnalysisReport()
        check_settlement_rate(0.80, report, rate_min=0.30, rate_max=0.70)
        assert len(report.issues) == 1
        assert report.issues[0].severity == IssueSeverity.MAJOR
        assert "high" in report.issues[0].message


# =============================================================================
# check_game_length Tests
# =============================================================================


class TestCheckGameLength:
    """Tests for check_game_length function."""

    def test_game_length_in_range(self):
        """Test no issues when game length is in range."""
        report = AnalysisReport()
        check_game_length(12.0, report, length_min=8.0, length_max=16.0)
        assert len(report.issues) == 0

    def test_game_length_too_short(self):
        """Test detects game length too short."""
        report = AnalysisReport()
        check_game_length(5.0, report, length_min=8.0, length_max=16.0)
        assert len(report.issues) == 1
        assert report.issues[0].severity == IssueSeverity.MINOR
        assert "short" in report.issues[0].message

    def test_game_length_too_long(self):
        """Test detects game length too long."""
        report = AnalysisReport()
        check_game_length(20.0, report, length_min=8.0, length_max=16.0)
        assert len(report.issues) == 1
        assert report.issues[0].severity == IssueSeverity.MINOR
        assert "long" in report.issues[0].message


# =============================================================================
# analyze_mechanics Tests
# =============================================================================


class TestAnalyzeMechanics:
    """Tests for analyze_mechanics main function."""

    def test_analyze_healthy_results(self):
        """Test analysis of healthy playtest results."""
        results = {
            "pairings": {
                "TitForTat:Nash": {
                    "total_games": 100,
                    "total_turns": 1100,
                    "wins_a": 48,
                    "wins_b": 45,
                    "ties": 7,
                    "settlements": 45,
                },
                "AlwaysDefect:AlwaysCooperate": {
                    "total_games": 100,
                    "total_turns": 1300,
                    "wins_a": 55,
                    "wins_b": 40,
                    "ties": 5,
                    "settlements": 50,
                },
            },
            "aggregate": {
                "vp_std_dev": 18.0,
            }
        }
        report = analyze_mechanics(results)
        # Should pass with no critical issues
        assert report.passed is True

    def test_analyze_with_dominant_strategy(self):
        """Test analysis detects dominant strategy."""
        results = {
            "pairings": {
                "Overpowered:Weak": {
                    "total_games": 100,
                    "total_turns": 1000,
                    "wins_a": 85,
                    "wins_b": 10,
                    "ties": 5,
                },
            },
            "aggregate": {
                "vp_std_dev": 20.0,
            }
        }
        report = analyze_mechanics(results)
        assert report.passed is False
        critical_issues = [i for i in report.issues if i.severity == IssueSeverity.CRITICAL]
        assert len(critical_issues) >= 1

    def test_analyze_with_custom_thresholds(self):
        """Test analysis with custom thresholds."""
        results = {
            "pairings": {
                "A:B": {
                    "total_games": 100,
                    "total_turns": 1000,
                    "wins_a": 55,
                    "wins_b": 40,
                    "ties": 5,
                },
            },
            "aggregate": {
                "vp_std_dev": 20.0,
            }
        }
        # With stricter threshold, 55% should trigger dominant
        thresholds = {"dominant_strategy": 0.50}
        report = analyze_mechanics(results, thresholds)
        assert report.passed is False

    def test_analyze_summary_populated(self):
        """Test summary is populated in report."""
        results = {
            "pairings": {
                "A:B": {
                    "total_games": 100,
                    "total_turns": 1200,
                    "wins_a": 50,
                    "wins_b": 45,
                    "settlements": 40,
                },
            },
            "aggregate": {
                "vp_std_dev": 18.0,
            }
        }
        report = analyze_mechanics(results)
        assert "total_games" in report.summary
        assert "avg_turns" in report.summary
        assert report.summary["total_games"] == 100


# =============================================================================
# format_text_report Tests
# =============================================================================


class TestFormatTextReport:
    """Tests for format_text_report function."""

    def test_format_passed_report(self):
        """Test formatting a passed report."""
        report = AnalysisReport()
        report.summary = {"total_games": 100, "avg_turns": 11.5}
        text = format_text_report(report)
        assert "PASSED" in text
        assert "100" in text
        assert "11.5" in text

    def test_format_failed_report(self):
        """Test formatting a failed report."""
        report = AnalysisReport()
        report.add_issue(
            severity="critical",
            message="Test critical issue",
            metric="test",
            value=0.75,
            threshold=0.60,
        )
        text = format_text_report(report)
        assert "FAILED" in text
        assert "CRITICAL" in text
        assert "Test critical issue" in text

    def test_format_multiple_severity_levels(self):
        """Test formatting with multiple severity levels."""
        report = AnalysisReport()
        report.add_issue(severity="critical", message="Critical", metric="a", value=1.0, threshold=0.5)
        report.add_issue(severity="major", message="Major", metric="b", value=2.0, threshold=1.0)
        report.add_issue(severity="minor", message="Minor", metric="c", value=3.0, threshold=2.0)
        text = format_text_report(report)
        assert "CRITICAL" in text
        assert "MAJOR" in text
        assert "MINOR" in text


# =============================================================================
# load_playtest_results Tests
# =============================================================================


class TestLoadPlaytestResults:
    """Tests for load_playtest_results function."""

    def test_load_valid_json(self):
        """Test loading valid JSON file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"pairings": {}, "aggregate": {}}, f)
            path = Path(f.name)

        try:
            results = load_playtest_results(path)
            assert "pairings" in results
            assert "aggregate" in results
        finally:
            path.unlink()

    def test_load_nonexistent_file(self):
        """Test loading non-existent file raises error."""
        with pytest.raises(FileNotFoundError):
            load_playtest_results(Path("/nonexistent/path.json"))

    def test_load_invalid_json(self):
        """Test loading invalid JSON raises error."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("not valid json {{{")
            path = Path(f.name)

        try:
            with pytest.raises(json.JSONDecodeError):
                load_playtest_results(path)
        finally:
            path.unlink()


# =============================================================================
# Integration Tests
# =============================================================================


class TestIntegration:
    """Integration tests for analyze_mechanics."""

    def test_full_analysis_cycle(self):
        """Test complete analysis from input to output."""
        results = {
            "pairings": {
                "TitForTat:Nash": {
                    "total_games": 200,
                    "total_turns": 2400,
                    "wins_a": 95,
                    "wins_b": 90,
                    "ties": 15,
                    "settlements": 80,
                    "mutual_destructions": 5,
                },
                "AlwaysDefect:Opportunist": {
                    "total_games": 200,
                    "total_turns": 2200,
                    "wins_a": 85,
                    "wins_b": 100,
                    "ties": 15,
                    "settlements": 70,
                },
            },
            "aggregate": {
                "vp_std_dev": 22.0,
            }
        }

        report = analyze_mechanics(results)

        # Check summary has required fields
        assert "total_games" in report.summary
        assert "avg_turns" in report.summary
        assert report.summary["total_games"] == 400

        # Format as text and JSON
        text = format_text_report(report)
        json_data = report.to_dict()

        assert "MECHANICS ANALYSIS REPORT" in text
        assert "passed" in json_data

    def test_edge_case_all_thresholds_violated(self):
        """Test when all thresholds are violated."""
        results = {
            "pairings": {
                "Dominant:Weak": {
                    "total_games": 100,
                    "total_turns": 500,  # Very short games (avg 5)
                    "wins_a": 90,  # Dominant strategy
                    "wins_b": 5,
                    "ties": 5,
                    "settlements": 5,  # Very low settlement rate (5%)
                },
            },
            "aggregate": {
                "vp_std_dev": 5.0,  # Low variance
            }
        }

        report = analyze_mechanics(results)

        # Should fail due to dominant strategy
        assert report.passed is False

        # Should have multiple issues
        assert len(report.issues) >= 3  # dominant, variance, settlement, maybe length
