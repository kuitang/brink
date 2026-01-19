"""Scenario Validator for Brinksmanship.

This module provides deterministic Python validation for scenarios.
All checks use pure Python with no LLM orchestration.

What IS validated (deterministic Python):
1. Game type variety: >= 8 distinct types across scenario
2. Act structure compliance: Turns map to correct acts (1-4=Act I, 5-8=Act II, 9+=Act III)
3. Balance analysis: Run game simulations to detect dominant strategies
4. Branching structure: All branches have valid targets, default_next exists
5. Narrative consistency: Optional LLM check for thematic coherence

What is NO LONGER validated (guaranteed by constructors):
- Payoffs match game type (impossible to fail)
- Nash equilibria exist (guaranteed by ordinal constraints)
- Ordinal constraints hold (enforced by constructor)
- Payoff symmetry for symmetric games (constructor responsibility)

See ENGINEERING_DESIGN.md Milestone 3.3 for design rationale.
"""

from __future__ import annotations

import random
import statistics
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

# Import schema types - handle both dict and Scenario object inputs
try:
    from brinksmanship.generation.schemas import Scenario, load_scenario
except ImportError:
    Scenario = None
    load_scenario = None

# Import matrix building - for scenario-specific simulation
try:
    from brinksmanship.models.matrices import (
        MatrixType,
        MatrixParameters,
        PayoffMatrix,
        build_matrix,
    )
    MATRICES_AVAILABLE = True
except ImportError:
    MATRICES_AVAILABLE = False
    MatrixType = None
    MatrixParameters = None
    PayoffMatrix = None
    build_matrix = None


# =============================================================================
# Validation Thresholds (from ENGINEERING_DESIGN.md)
# =============================================================================

THRESHOLDS = {
    "dominant_strategy": 0.60,  # Fail if any pairing >60% win rate
    "variance_min": 10,  # VP std dev should be >= 10
    "variance_max": 40,  # VP std dev should be <= 40
    "settlement_rate_min": 0.30,  # At least 30% settlements
    "settlement_rate_max": 0.70,  # At most 70% settlements
    "avg_game_length_min": 8,  # Games shouldn't be too short
    "avg_game_length_max": 16,  # Games shouldn't exceed max turns
    "min_game_types": 8,  # Minimum distinct game types required
}


# =============================================================================
# Validation Result Data Classes
# =============================================================================


class ValidationSeverity(Enum):
    """Severity level for validation issues."""

    CRITICAL = "critical"  # Must fix before use
    MAJOR = "major"  # Should fix, affects gameplay
    MINOR = "minor"  # Nice to fix, minor impact
    INFO = "info"  # Informational only


@dataclass
class ValidationIssue:
    """A single validation issue found."""

    check_name: str
    severity: ValidationSeverity
    message: str
    details: dict | None = None


@dataclass
class CheckResult:
    """Result of a single validation check."""

    check_name: str
    passed: bool
    issues: list[ValidationIssue] = field(default_factory=list)
    metrics: dict = field(default_factory=dict)

    def add_issue(
        self,
        severity: ValidationSeverity,
        message: str,
        details: dict | None = None,
    ) -> None:
        """Add an issue to this check result."""
        self.issues.append(
            ValidationIssue(
                check_name=self.check_name,
                severity=severity,
                message=message,
                details=details,
            )
        )
        if severity in (ValidationSeverity.CRITICAL, ValidationSeverity.MAJOR):
            self.passed = False


@dataclass
class BalanceSimulationResults:
    """Results from running balance simulations."""

    games_played: int = 0
    strategy_win_rates: dict[str, float] = field(default_factory=dict)
    head_to_head: dict[str, dict[str, float]] = field(default_factory=dict)
    avg_game_length: float = 0.0
    elimination_rate: float = 0.0
    mutual_destruction_rate: float = 0.0
    crisis_termination_rate: float = 0.0
    settlement_rate: float = 0.0
    vp_std_dev: float = 0.0
    vp_mean: float = 50.0


@dataclass
class ValidationResult:
    """Complete validation result for a scenario."""

    scenario_path: str | None = None
    scenario_id: str | None = None
    overall_passed: bool = True

    # Individual check results
    game_variety: CheckResult | None = None
    intelligence_games: CheckResult | None = None
    act_structure: CheckResult | None = None
    branching: CheckResult | None = None
    settlement: CheckResult | None = None
    balance: CheckResult | None = None
    narrative: CheckResult | None = None  # Optional LLM check

    # Balance simulation data
    simulation_results: BalanceSimulationResults | None = None

    def get_all_issues(self) -> list[ValidationIssue]:
        """Get all issues from all checks."""
        issues = []
        for check in [
            self.game_variety,
            self.intelligence_games,
            self.act_structure,
            self.branching,
            self.settlement,
            self.balance,
            self.narrative,
        ]:
            if check is not None:
                issues.extend(check.issues)
        return issues

    def get_critical_issues(self) -> list[ValidationIssue]:
        """Get only critical issues."""
        return [
            i for i in self.get_all_issues() if i.severity == ValidationSeverity.CRITICAL
        ]

    def get_major_issues(self) -> list[ValidationIssue]:
        """Get only major issues."""
        return [
            i for i in self.get_all_issues() if i.severity == ValidationSeverity.MAJOR
        ]

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "scenario_path": self.scenario_path,
            "scenario_id": self.scenario_id,
            "overall_passed": self.overall_passed,
            "checks": {
                "game_variety": self._check_to_dict(self.game_variety),
                "intelligence_games": self._check_to_dict(self.intelligence_games),
                "act_structure": self._check_to_dict(self.act_structure),
                "branching": self._check_to_dict(self.branching),
                "settlement": self._check_to_dict(self.settlement),
                "balance": self._check_to_dict(self.balance),
                "narrative": self._check_to_dict(self.narrative),
            },
            "simulation_results": (
                {
                    "games_played": self.simulation_results.games_played,
                    "strategy_win_rates": self.simulation_results.strategy_win_rates,
                    "avg_game_length": self.simulation_results.avg_game_length,
                    "elimination_rate": self.simulation_results.elimination_rate,
                    "mutual_destruction_rate": self.simulation_results.mutual_destruction_rate,
                    "crisis_termination_rate": self.simulation_results.crisis_termination_rate,
                    "settlement_rate": self.simulation_results.settlement_rate,
                    "vp_std_dev": self.simulation_results.vp_std_dev,
                    "vp_mean": self.simulation_results.vp_mean,
                }
                if self.simulation_results
                else None
            ),
            "issues": [
                {
                    "check_name": i.check_name,
                    "severity": i.severity.value,
                    "message": i.message,
                    "details": i.details,
                }
                for i in self.get_all_issues()
            ],
        }

    def _check_to_dict(self, check: CheckResult | None) -> dict | None:
        """Convert a check result to dictionary."""
        if check is None:
            return None
        return {
            "check_name": check.check_name,
            "passed": check.passed,
            "metrics": check.metrics,
            "issue_count": len(check.issues),
        }


# =============================================================================
# Structural Validation Checks (Pure Python)
# =============================================================================


def check_game_variety(scenario: dict | Scenario) -> CheckResult:
    """Check that scenario uses >= 8 distinct game types.

    Args:
        scenario: Scenario object or dict with scenario data

    Returns:
        CheckResult with pass/fail and metrics
    """
    result = CheckResult(check_name="game_variety", passed=True)

    # Extract matrix types from all turns
    matrix_types = set()

    if hasattr(scenario, "get_all_matrix_types"):
        # Scenario object
        matrix_types = scenario.get_all_matrix_types()
    else:
        # Dict format
        for turn in scenario.get("turns", []):
            if "matrix_type" in turn:
                matrix_types.add(turn["matrix_type"])
        for branch_turn in scenario.get("branches", {}).values():
            if "matrix_type" in branch_turn:
                matrix_types.add(branch_turn["matrix_type"])

    result.metrics["distinct_types"] = len(matrix_types)
    result.metrics["types_found"] = sorted([str(t) for t in matrix_types])
    result.metrics["required_types"] = THRESHOLDS["min_game_types"]

    if len(matrix_types) < THRESHOLDS["min_game_types"]:
        result.add_issue(
            ValidationSeverity.MAJOR,
            f"Insufficient game type variety: found {len(matrix_types)}, "
            f"need at least {THRESHOLDS['min_game_types']}",
            details={
                "found": len(matrix_types),
                "required": THRESHOLDS["min_game_types"],
                "types": [str(t) for t in matrix_types],
            },
        )

    return result


def check_intelligence_games(scenario: dict | Scenario) -> CheckResult:
    """Check that scenario includes sufficient intelligence game turns.

    Intelligence games (INSPECTION_GAME, RECONNAISSANCE) are core mechanics for
    information acquisition under strategic uncertainty.

    Requirements:
    - At least 2 intelligence game turns per scenario
    - At least 1 in Act I or early Act II (turns 1-6)
    - At least 1 in Act II (turns 5-8)

    Args:
        scenario: Scenario object or dict with scenario data

    Returns:
        CheckResult with pass/fail and metrics
    """
    result = CheckResult(check_name="intelligence_games", passed=True)

    intelligence_types = {"inspection_game", "reconnaissance", "INSPECTION_GAME", "RECONNAISSANCE"}
    intelligence_turns: list[int] = []
    early_phase_intel = 0  # turns 1-6
    mid_phase_intel = 0    # turns 5-8

    def check_turn(turn_data: dict) -> None:
        nonlocal early_phase_intel, mid_phase_intel
        turn_num = turn_data.get("turn", 0)
        matrix_type = turn_data.get("matrix_type", "")

        # Handle both string and enum types
        type_str = str(matrix_type).lower().replace("matrixtype.", "")

        if type_str in {"inspection_game", "reconnaissance"}:
            intelligence_turns.append(turn_num)
            if turn_num <= 6:
                early_phase_intel += 1
            if 5 <= turn_num <= 8:
                mid_phase_intel += 1

    if hasattr(scenario, "turns"):
        # Scenario object
        for turn in scenario.turns:
            check_turn(turn.model_dump())
        for branch_turn in scenario.branches.values():
            check_turn(branch_turn.model_dump())
    else:
        # Dict format
        for turn in scenario.get("turns", []):
            check_turn(turn)
        for branch_turn in scenario.get("branches", {}).values():
            check_turn(branch_turn)

    result.metrics["intelligence_turns"] = intelligence_turns
    result.metrics["total_intelligence_games"] = len(intelligence_turns)
    result.metrics["early_phase_intel"] = early_phase_intel
    result.metrics["mid_phase_intel"] = mid_phase_intel

    # Check minimum total
    if len(intelligence_turns) < 2:
        result.add_issue(
            ValidationSeverity.MAJOR,
            f"Insufficient intelligence games: found {len(intelligence_turns)}, need at least 2",
            details={"found": len(intelligence_turns), "turns": intelligence_turns},
        )

    # Check early phase (at least 1 in turns 1-6)
    if early_phase_intel < 1:
        result.add_issue(
            ValidationSeverity.MINOR,
            "No intelligence games in early phase (turns 1-6)",
            details={"early_phase_intel": early_phase_intel},
        )

    # Check mid phase (at least 1 in turns 5-8)
    if mid_phase_intel < 1:
        result.add_issue(
            ValidationSeverity.MINOR,
            "No intelligence games in mid phase (turns 5-8)",
            details={"mid_phase_intel": mid_phase_intel},
        )

    return result


def check_act_structure(scenario: dict | Scenario) -> CheckResult:
    """Check that turns map to correct acts.

    Act I: turns 1-4
    Act II: turns 5-8
    Act III: turns 9+

    Args:
        scenario: Scenario object or dict with scenario data

    Returns:
        CheckResult with pass/fail and metrics
    """
    result = CheckResult(check_name="act_structure", passed=True)
    violations = []

    def get_expected_act(turn_num: int) -> int:
        if turn_num <= 4:
            return 1
        elif turn_num <= 8:
            return 2
        else:
            return 3

    def check_turn(turn_data: dict, source: str) -> None:
        turn_num = turn_data.get("turn", 0)
        act = turn_data.get("act", 0)
        expected = get_expected_act(turn_num)

        if act != expected:
            violations.append(
                {
                    "source": source,
                    "turn": turn_num,
                    "act": act,
                    "expected_act": expected,
                }
            )

    # Check all turns
    if hasattr(scenario, "turns"):
        # Scenario object
        for turn in scenario.turns:
            check_turn(turn.model_dump(), f"turn_{turn.turn}")
        for branch_id, branch_turn in scenario.branches.items():
            check_turn(branch_turn.model_dump(), branch_id)
    else:
        # Dict format
        for turn in scenario.get("turns", []):
            check_turn(turn, f"turn_{turn.get('turn', '?')}")
        for branch_id, branch_turn in scenario.get("branches", {}).items():
            check_turn(branch_turn, branch_id)

    result.metrics["violations_count"] = len(violations)
    result.metrics["violations"] = violations

    if violations:
        result.add_issue(
            ValidationSeverity.CRITICAL,
            f"Act structure violations: {len(violations)} turns have incorrect act numbers",
            details={"violations": violations},
        )

    return result


def check_branching_validity(scenario: dict | Scenario) -> CheckResult:
    """Check that all branch targets exist and default_next is set.

    Args:
        scenario: Scenario object or dict with scenario data

    Returns:
        CheckResult with pass/fail and metrics
    """
    result = CheckResult(check_name="branching", passed=True)

    # Collect all valid turn IDs
    valid_ids = set()
    missing_targets = []
    missing_default_next = []

    if hasattr(scenario, "turns"):
        # Scenario object - validation already done by Pydantic
        for turn in scenario.turns:
            valid_ids.add(f"turn_{turn.turn}")
        for branch_id in scenario.branches:
            valid_ids.add(branch_id)

        # Re-check for more detailed metrics
        for turn in scenario.turns:
            for outcome in ["CC", "CD", "DC", "DD"]:
                target = getattr(turn.branches, outcome)
                # None means "use default_next" - not an error
                if target is not None and target not in valid_ids:
                    missing_targets.append(
                        {"source": f"turn_{turn.turn}", "outcome": outcome, "target": target}
                    )
            # None is valid for last turn (no next turn) or when all branches are specified
            if turn.default_next is not None and turn.default_next not in valid_ids:
                missing_default_next.append(
                    {"source": f"turn_{turn.turn}", "default_next": turn.default_next}
                )

        for branch_id, branch_turn in scenario.branches.items():
            for outcome in ["CC", "CD", "DC", "DD"]:
                target = getattr(branch_turn.branches, outcome)
                # None means "use default_next" - not an error
                if target is not None and target not in valid_ids:
                    missing_targets.append(
                        {"source": branch_id, "outcome": outcome, "target": target}
                    )
            # None is valid for terminal branches
            if branch_turn.default_next is not None and branch_turn.default_next not in valid_ids:
                missing_default_next.append(
                    {"source": branch_id, "default_next": branch_turn.default_next}
                )
    else:
        # Dict format
        for turn in scenario.get("turns", []):
            valid_ids.add(f"turn_{turn.get('turn', 0)}")
        for branch_id in scenario.get("branches", {}):
            valid_ids.add(branch_id)

        for turn in scenario.get("turns", []):
            turn_id = f"turn_{turn.get('turn', '?')}"
            branches = turn.get("branches", {})
            for outcome in ["CC", "CD", "DC", "DD"]:
                target = branches.get(outcome)
                if target and target not in valid_ids:
                    missing_targets.append(
                        {"source": turn_id, "outcome": outcome, "target": target}
                    )
            default_next = turn.get("default_next")
            # None is valid for last turn (no next turn) or when all branches are specified
            if default_next is not None and default_next not in valid_ids:
                missing_default_next.append(
                    {"source": turn_id, "default_next": default_next}
                )

        for branch_id, branch_turn in scenario.get("branches", {}).items():
            branches = branch_turn.get("branches", {})
            for outcome in ["CC", "CD", "DC", "DD"]:
                target = branches.get(outcome)
                if target and target not in valid_ids:
                    missing_targets.append(
                        {"source": branch_id, "outcome": outcome, "target": target}
                    )
            default_next = branch_turn.get("default_next")
            # None is valid for terminal branches
            if default_next is not None and default_next not in valid_ids:
                missing_default_next.append(
                    {"source": branch_id, "default_next": default_next}
                )

    result.metrics["valid_turn_ids"] = sorted(valid_ids)
    result.metrics["missing_targets_count"] = len(missing_targets)
    result.metrics["missing_default_next_count"] = len(missing_default_next)

    if missing_targets:
        result.add_issue(
            ValidationSeverity.CRITICAL,
            f"Missing branch targets: {len(missing_targets)} branches point to non-existent turns",
            details={"missing_targets": missing_targets},
        )

    if missing_default_next:
        result.add_issue(
            ValidationSeverity.CRITICAL,
            f"Missing or invalid default_next: {len(missing_default_next)} turns",
            details={"missing_default_next": missing_default_next},
        )

    return result


def check_settlement_config(scenario: dict | Scenario) -> CheckResult:
    """Check that settlement configuration is valid.

    Validates:
    - default_next exists for all turns (handled by branching check)
    - settlement_available is appropriately set
    - settlement_failed_narrative exists when settlement is available

    Args:
        scenario: Scenario object or dict with scenario data

    Returns:
        CheckResult with pass/fail and metrics
    """
    result = CheckResult(check_name="settlement", passed=True)

    settlement_turns = []
    missing_narratives = []

    def check_turn(turn_data: dict, source: str) -> None:
        turn_num = turn_data.get("turn", 0)
        settlement_available = turn_data.get("settlement_available", True)
        settlement_narrative = turn_data.get("settlement_failed_narrative", "")

        if settlement_available:
            settlement_turns.append({"source": source, "turn": turn_num})
            if not settlement_narrative or settlement_narrative.strip() == "":
                missing_narratives.append({"source": source, "turn": turn_num})

    if hasattr(scenario, "turns"):
        # Scenario object
        for turn in scenario.turns:
            check_turn(turn.model_dump(), f"turn_{turn.turn}")
        for branch_id, branch_turn in scenario.branches.items():
            check_turn(branch_turn.model_dump(), branch_id)
    else:
        # Dict format
        for turn in scenario.get("turns", []):
            check_turn(turn, f"turn_{turn.get('turn', '?')}")
        for branch_id, branch_turn in scenario.get("branches", {}).items():
            check_turn(branch_turn, branch_id)

    result.metrics["settlement_enabled_turns"] = len(settlement_turns)
    result.metrics["missing_narratives_count"] = len(missing_narratives)

    if missing_narratives:
        result.add_issue(
            ValidationSeverity.MINOR,
            f"Missing settlement_failed_narrative: {len(missing_narratives)} turns",
            details={"missing_narratives": missing_narratives},
        )

    return result


# =============================================================================
# Balance Simulation (Pure Python)
# =============================================================================


class SimAction(Enum):
    """Action in balance simulation."""

    COOPERATE = "C"
    DEFECT = "D"


class SimEndingType(Enum):
    """Ending type in balance simulation."""

    MAX_TURNS = "max_turns"
    POSITION_LOSS_A = "position_loss_a"
    POSITION_LOSS_B = "position_loss_b"
    RESOURCE_LOSS_A = "resource_loss_a"
    RESOURCE_LOSS_B = "resource_loss_b"
    MUTUAL_DESTRUCTION = "mutual_destruction"
    CRISIS_TERMINATION = "crisis_termination"
    SETTLEMENT = "settlement"


@dataclass
class SimPlayerState:
    """Player state in simulation."""

    position: float = 5.0
    resources: float = 5.0

    def clamp(self) -> None:
        self.position = max(0.0, min(10.0, self.position))
        self.resources = max(0.0, min(10.0, self.resources))


@dataclass
class SimGameState:
    """Game state in simulation."""

    player_a: SimPlayerState = field(default_factory=SimPlayerState)
    player_b: SimPlayerState = field(default_factory=SimPlayerState)
    risk: float = 2.0
    cooperation_score: float = 5.0
    stability: float = 5.0
    turn: int = 1
    max_turns: int = 14
    history_a: list[SimAction] = field(default_factory=list)
    history_b: list[SimAction] = field(default_factory=list)

    def clamp(self) -> None:
        self.player_a.clamp()
        self.player_b.clamp()
        self.risk = max(0.0, min(10.0, self.risk))
        self.cooperation_score = max(0.0, min(10.0, self.cooperation_score))
        self.stability = max(1.0, min(10.0, self.stability))

    def get_act_multiplier(self) -> float:
        if self.turn <= 4:
            return 0.7
        elif self.turn <= 8:
            return 1.0
        else:
            return 1.3


@dataclass
class SimGameResult:
    """Result of a simulated game."""

    winner: str | None  # "A", "B", "tie", or "mutual_destruction"
    ending_type: SimEndingType
    turns_played: int
    final_pos_a: float
    final_pos_b: float
    final_res_a: float
    final_res_b: float
    final_risk: float
    vp_a: float = 50.0
    vp_b: float = 50.0


def _apply_sim_outcome(
    state: SimGameState, action_a: SimAction, action_b: SimAction
) -> None:
    """Apply outcome based on actions.

    CRITICAL: All payoffs must be SYMMETRIC. No "hand of god" asymmetry.
    If exploiter gets +X, victim gets -X (same magnitude).

    BALANCE TUNING: Narrowed T-R gap to reduce Nash dominance.
    - R (reward for mutual cooperation): +0.6
    - T (temptation to exploit): +0.7
    - P (punishment for mutual defection): -0.5
    - S (sucker's payoff): -0.7

    Ordinal: T=0.7 > R=0.6 > P=-0.5 > S=-0.7 (valid PD)
    T-R gap: 0.1 (narrowed from 0.5)
    Exploitation magnitude: 0.7 (reduced from 1.0)
    """
    multiplier = state.get_act_multiplier()
    noise = random.uniform(0.9, 1.1)

    if action_a == SimAction.COOPERATE and action_b == SimAction.COOPERATE:
        # R (reward): Both get +0.6
        state.player_a.position += 0.6 * multiplier * noise
        state.player_b.position += 0.6 * multiplier * noise
        state.risk -= 0.5 * multiplier * noise
        state.cooperation_score += 1.0
    elif action_a == SimAction.COOPERATE and action_b == SimAction.DEFECT:
        # SYMMETRIC: A gets S=-0.7, B gets T=+0.7
        # BALANCE: Increased risk from exploitation to punish aggressive play
        state.player_a.position -= 0.7 * multiplier * noise
        state.player_b.position += 0.7 * multiplier * noise
        state.risk += 0.8 * multiplier * noise  # Increased from 0.5 to 0.8
    elif action_a == SimAction.DEFECT and action_b == SimAction.COOPERATE:
        # SYMMETRIC: A gets T=+0.7, B gets S=-0.7
        # BALANCE: Increased risk from exploitation to punish aggressive play
        state.player_a.position += 0.7 * multiplier * noise
        state.player_b.position -= 0.7 * multiplier * noise
        state.risk += 0.8 * multiplier * noise  # Increased from 0.5 to 0.8
    else:  # DD
        # P (punishment): Both get -0.5
        # BALANCE: Very high risk from DD to force cooperation before crisis
        state.player_a.position -= 0.5 * multiplier * noise
        state.player_b.position -= 0.5 * multiplier * noise
        state.player_a.resources -= 0.5 * multiplier * noise
        state.player_b.resources -= 0.5 * multiplier * noise
        state.risk += 2.0 * multiplier * noise  # Increased from 1.5 to 2.0
        state.cooperation_score -= 1.0

    # Update stability
    switches = 0
    if len(state.history_a) >= 1 and state.history_a[-1] != action_a:
        switches += 1
    if len(state.history_b) >= 1 and state.history_b[-1] != action_b:
        switches += 1

    state.stability = state.stability * 0.8 + 1.0
    if switches == 0:
        state.stability += 1.5
    elif switches == 1:
        state.stability -= 3.5
    else:
        state.stability -= 5.5

    state.clamp()


def _check_sim_ending(state: SimGameState) -> SimEndingType | None:
    """Check if game has ended."""
    if state.risk >= 10.0:
        return SimEndingType.MUTUAL_DESTRUCTION
    if state.player_a.position <= 0:
        return SimEndingType.POSITION_LOSS_A
    if state.player_b.position <= 0:
        return SimEndingType.POSITION_LOSS_B
    if state.player_a.resources <= 0:
        return SimEndingType.RESOURCE_LOSS_A
    if state.player_b.resources <= 0:
        return SimEndingType.RESOURCE_LOSS_B

    # Crisis termination
    if state.turn >= 10 and state.risk > 7:
        p_termination = (state.risk - 7) * 0.08
        if random.random() < p_termination:
            return SimEndingType.CRISIS_TERMINATION

    if state.turn > state.max_turns:
        return SimEndingType.MAX_TURNS

    return None


def _calculate_final_vp(state: SimGameState) -> tuple[float, float]:
    """Calculate final VP using variance formula from GAME_MANUAL.md."""
    total_pos = state.player_a.position + state.player_b.position
    ev_a = 50.0 if total_pos == 0 else (state.player_a.position / total_pos) * 100

    ev_b = 100.0 - ev_a

    # Variance calculation
    base_sigma = 8 + (state.risk * 1.2)
    chaos_factor = 1.2 - (state.cooperation_score / 50)
    instability_factor = 1 + (10 - state.stability) / 20
    act_multiplier = 1.3  # Act III

    shared_sigma = base_sigma * chaos_factor * instability_factor * act_multiplier
    noise = random.gauss(0, shared_sigma)

    vp_a_raw = ev_a + noise
    vp_b_raw = ev_b - noise

    # Clamp and renormalize
    vp_a_clamped = max(5.0, min(95.0, vp_a_raw))
    vp_b_clamped = max(5.0, min(95.0, vp_b_raw))

    total = vp_a_clamped + vp_b_clamped
    vp_a = vp_a_clamped * 100 / total
    vp_b = vp_b_clamped * 100 / total

    return vp_a, vp_b


# Strategy implementations for simulation
def _tit_for_tat(
    state: SimGameState, my_history: list, opp_history: list, player: str
) -> SimAction:
    if not opp_history:
        return SimAction.COOPERATE
    return opp_history[-1]


def _always_defect(
    state: SimGameState, my_history: list, opp_history: list, player: str
) -> SimAction:
    return SimAction.DEFECT


def _always_cooperate(
    state: SimGameState, my_history: list, opp_history: list, player: str
) -> SimAction:
    return SimAction.COOPERATE


def _opportunist(
    state: SimGameState, my_history: list, opp_history: list, player: str
) -> SimAction:
    if player == "A":
        my_pos = state.player_a.position
        opp_pos = state.player_b.position
        my_res = state.player_a.resources
    else:
        my_pos = state.player_b.position
        opp_pos = state.player_a.position
        my_res = state.player_b.resources

    if state.risk >= 7:
        return SimAction.COOPERATE
    if my_res <= 2:
        return SimAction.COOPERATE

    pos_advantage = my_pos - opp_pos
    if pos_advantage > 1.0:
        return SimAction.DEFECT
    elif pos_advantage < -1.0:
        return SimAction.COOPERATE
    else:
        if state.turn <= 6:
            return SimAction.COOPERATE
        else:
            return SimAction.DEFECT


def _nash(
    state: SimGameState, my_history: list, opp_history: list, player: str
) -> SimAction:
    """Nash equilibrium strategy for stage game PD.

    In the stage game PD, defection is the dominant strategy (Nash equilibrium).
    The only exception is when risk is critically high - then cooperation is
    needed to avoid mutual destruction.
    """
    # Cooperate only at critically high risk to avoid mutual destruction
    if state.risk >= 8:
        return SimAction.COOPERATE
    return SimAction.DEFECT


SIM_STRATEGIES = {
    "TitForTat": _tit_for_tat,
    "AlwaysDefect": _always_defect,
    "AlwaysCooperate": _always_cooperate,
    "Opportunist": _opportunist,
    "Nash": _nash,
}


# =============================================================================
# Scenario-Specific Simulation (uses actual matrix types and parameters)
# =============================================================================


def _get_scenario_turn(
    scenario: dict, turn_id: str, turn_number: int
) -> dict | None:
    """Get a turn from either main turns array or branches dict."""
    # Check main turns array
    for turn in scenario.get("turns", []):
        if turn.get("turn") == turn_number:
            return turn

    # Check branches dict
    branches = scenario.get("branches", {})
    if turn_id in branches:
        return branches[turn_id]

    # Fallback: look for turn_N in branches
    fallback_id = f"turn_{turn_number}"
    if fallback_id in branches:
        return branches[fallback_id]

    return None


def _build_turn_matrix(turn_data: dict) -> PayoffMatrix | None:
    """Build a PayoffMatrix from turn's matrix_type and matrix_parameters."""
    if not MATRICES_AVAILABLE:
        return None

    matrix_type_str = turn_data.get("matrix_type", "")
    params_dict = turn_data.get("matrix_parameters", {})

    # Parse matrix type
    type_str = str(matrix_type_str).upper().replace("MATRIXTYPE.", "")
    try:
        matrix_type = MatrixType[type_str]
    except (KeyError, ValueError):
        return None

    # Build parameters
    params = MatrixParameters(**params_dict)

    # Build and return the matrix
    return build_matrix(matrix_type, params)


def _apply_matrix_outcome(
    state: SimGameState,
    action_a: SimAction,
    action_b: SimAction,
    matrix: PayoffMatrix | None,
) -> str:
    """Apply outcome using actual matrix payoffs. Returns outcome code (CC/CD/DC/DD)."""
    # Get outcome code
    if action_a == SimAction.COOPERATE and action_b == SimAction.COOPERATE:
        outcome_code = "CC"
        outcome = matrix.cc if matrix else None
    elif action_a == SimAction.COOPERATE and action_b == SimAction.DEFECT:
        outcome_code = "CD"
        outcome = matrix.cd if matrix else None
    elif action_a == SimAction.DEFECT and action_b == SimAction.COOPERATE:
        outcome_code = "DC"
        outcome = matrix.dc if matrix else None
    else:
        outcome_code = "DD"
        outcome = matrix.dd if matrix else None

    multiplier = state.get_act_multiplier()
    noise = random.uniform(0.95, 1.05)

    if outcome is not None:
        # Use actual matrix deltas
        deltas = outcome.deltas
        state.player_a.position += deltas.pos_a * multiplier * noise
        state.player_b.position += deltas.pos_b * multiplier * noise
        # res_cost is subtracted (it's a cost, not a delta)
        state.player_a.resources -= deltas.res_cost_a * multiplier * noise
        state.player_b.resources -= deltas.res_cost_b * multiplier * noise
        state.risk += deltas.risk_delta * multiplier * noise
        # Cooperation score based on outcome
        if outcome_code == "CC":
            state.cooperation_score += 1.0
        elif outcome_code == "DD":
            state.cooperation_score -= 1.0
    else:
        # Fallback to generic payoffs if matrix unavailable
        if outcome_code == "CC":
            state.player_a.position += 0.6 * multiplier * noise
            state.player_b.position += 0.6 * multiplier * noise
            state.risk -= 0.5 * multiplier * noise
            state.cooperation_score += 1.0
        elif outcome_code == "CD":
            state.player_a.position -= 0.7 * multiplier * noise
            state.player_b.position += 0.7 * multiplier * noise
            state.risk += 0.8 * multiplier * noise
        elif outcome_code == "DC":
            state.player_a.position += 0.7 * multiplier * noise
            state.player_b.position -= 0.7 * multiplier * noise
            state.risk += 0.8 * multiplier * noise
        else:  # DD
            state.player_a.position -= 0.5 * multiplier * noise
            state.player_b.position -= 0.5 * multiplier * noise
            state.player_a.resources -= 0.5 * multiplier * noise
            state.player_b.resources -= 0.5 * multiplier * noise
            state.risk += 2.0 * multiplier * noise
            state.cooperation_score -= 1.0

    # Update stability based on action switches
    switches = 0
    if len(state.history_a) >= 1 and state.history_a[-1] != action_a:
        switches += 1
    if len(state.history_b) >= 1 and state.history_b[-1] != action_b:
        switches += 1

    state.stability = state.stability * 0.8 + 1.0
    if switches == 0:
        state.stability += 1.5
    elif switches == 1:
        state.stability -= 3.5
    else:
        state.stability -= 5.5

    state.clamp()
    return outcome_code


def _run_scenario_sim_game(
    scenario: dict, strategy_a_name: str, strategy_b_name: str
) -> SimGameResult:
    """Run a single simulated game using the actual scenario's turns and matrices."""
    strategy_a = SIM_STRATEGIES[strategy_a_name]
    strategy_b = SIM_STRATEGIES[strategy_b_name]
    max_turns = scenario.get("max_turns", 14)

    state = SimGameState(max_turns=max_turns)

    current_turn_id = "turn_1"
    turn_number = 1
    ending = None

    while True:
        # Check for ending conditions
        ending = _check_sim_ending(state)
        if ending:
            break

        # Get current turn data
        turn_data = _get_scenario_turn(scenario, current_turn_id, turn_number)
        if turn_data is None:
            # No more turns defined, end game
            ending = SimEndingType.MAX_TURNS
            break

        # Build the matrix for this turn
        matrix = _build_turn_matrix(turn_data)

        # Get actions from strategies
        action_a = strategy_a(state, state.history_a, state.history_b, "A")
        action_b = strategy_b(state, state.history_b, state.history_a, "B")

        # Apply outcome using actual matrix
        outcome_code = _apply_matrix_outcome(state, action_a, action_b, matrix)

        # Record history
        state.history_a.append(action_a)
        state.history_b.append(action_b)
        state.turn += 1
        turn_number += 1

        # Follow branching based on outcome
        branches = turn_data.get("branches", {})
        next_turn_id = branches.get(outcome_code)

        if next_turn_id is None:
            # Use default_next
            next_turn_id = turn_data.get("default_next", f"turn_{turn_number}")

        current_turn_id = next_turn_id

        # Check for ending after turn
        ending = _check_sim_ending(state)
        if ending:
            break

    # Determine winner and VP
    vp_a, vp_b = _calculate_final_vp(state)

    if ending == SimEndingType.MUTUAL_DESTRUCTION:
        winner = "mutual_destruction"
        vp_a, vp_b = 20.0, 20.0
    elif ending in (SimEndingType.POSITION_LOSS_A, SimEndingType.RESOURCE_LOSS_A):
        winner = "B"
        vp_a, vp_b = 10.0, 90.0
    elif ending in (SimEndingType.POSITION_LOSS_B, SimEndingType.RESOURCE_LOSS_B):
        winner = "A"
        vp_a, vp_b = 90.0, 10.0
    else:
        if vp_a > vp_b + 1:
            winner = "A"
        elif vp_b > vp_a + 1:
            winner = "B"
        else:
            winner = "tie"

    return SimGameResult(
        winner=winner,
        ending_type=ending,
        turns_played=state.turn - 1,
        final_pos_a=state.player_a.position,
        final_pos_b=state.player_b.position,
        final_res_a=state.player_a.resources,
        final_res_b=state.player_b.resources,
        final_risk=state.risk,
        vp_a=vp_a,
        vp_b=vp_b,
    )


def _run_sim_game(strategy_a_name: str, strategy_b_name: str) -> SimGameResult:
    """Run a single simulated game."""
    strategy_a = SIM_STRATEGIES[strategy_a_name]
    strategy_b = SIM_STRATEGIES[strategy_b_name]
    max_turns = random.randint(12, 16)

    state = SimGameState(max_turns=max_turns)

    while True:
        ending = _check_sim_ending(state)
        if ending:
            break

        action_a = strategy_a(state, state.history_a, state.history_b, "A")
        action_b = strategy_b(state, state.history_b, state.history_a, "B")

        _apply_sim_outcome(state, action_a, action_b)

        state.history_a.append(action_a)
        state.history_b.append(action_b)
        state.turn += 1

        ending = _check_sim_ending(state)
        if ending:
            break

    # Determine winner and VP
    vp_a, vp_b = _calculate_final_vp(state)

    if ending == SimEndingType.MUTUAL_DESTRUCTION:
        winner = "mutual_destruction"
        vp_a, vp_b = 20.0, 20.0
    elif ending in (SimEndingType.POSITION_LOSS_A, SimEndingType.RESOURCE_LOSS_A):
        winner = "B"
        vp_a, vp_b = 10.0, 90.0
    elif ending in (SimEndingType.POSITION_LOSS_B, SimEndingType.RESOURCE_LOSS_B):
        winner = "A"
        vp_a, vp_b = 90.0, 10.0
    else:
        if vp_a > vp_b + 1:
            winner = "A"
        elif vp_b > vp_a + 1:
            winner = "B"
        else:
            winner = "tie"

    return SimGameResult(
        winner=winner,
        ending_type=ending,
        turns_played=state.turn - 1,
        final_pos_a=state.player_a.position,
        final_pos_b=state.player_b.position,
        final_res_a=state.player_a.resources,
        final_res_b=state.player_b.resources,
        final_risk=state.risk,
        vp_a=vp_a,
        vp_b=vp_b,
    )


def run_balance_simulation(
    scenario: dict | Scenario | None = None, games: int = 50, seed: int | None = None
) -> BalanceSimulationResults:
    """Run balance simulation to detect dominant strategies.

    Uses the ACTUAL scenario's matrix types and parameters to detect if any
    deterministic strategy dominates in THIS SPECIFIC scenario.

    Args:
        scenario: Scenario object or dict (REQUIRED for accurate simulation)
        games: Number of games per strategy pairing
        seed: Random seed for reproducibility

    Returns:
        BalanceSimulationResults with aggregated statistics
    """
    if seed is not None:
        random.seed(seed)

    # Convert Scenario object to dict if needed
    scenario_dict: dict | None = None
    if scenario is not None:
        if Scenario is not None and isinstance(scenario, Scenario):
            scenario_dict = scenario.model_dump()
        elif isinstance(scenario, dict):
            scenario_dict = scenario

    # Check if we can use scenario-specific simulation
    use_scenario_sim = scenario_dict is not None and MATRICES_AVAILABLE

    results = BalanceSimulationResults()
    strategy_names = list(SIM_STRATEGIES.keys())

    # Track statistics
    total_games = 0
    total_turns = 0
    strategy_wins: dict[str, int] = dict.fromkeys(strategy_names, 0)
    strategy_games: dict[str, int] = dict.fromkeys(strategy_names, 0)
    head_to_head: dict[str, dict[str, float]] = {
        name: {} for name in strategy_names
    }

    ending_counts = {
        "elimination": 0,
        "mutual_destruction": 0,
        "crisis_termination": 0,
        "max_turns": 0,
    }

    all_vps: list[float] = []

    # Run all pairings
    for i, name_a in enumerate(strategy_names):
        for name_b in strategy_names[i:]:
            wins_a = 0
            wins_b = 0

            for _ in range(games):
                # Use scenario-specific simulation if available
                if use_scenario_sim:
                    result = _run_scenario_sim_game(scenario_dict, name_a, name_b)
                else:
                    result = _run_sim_game(name_a, name_b)
                total_games += 1
                total_turns += result.turns_played

                all_vps.append(result.vp_a)
                all_vps.append(result.vp_b)

                if result.winner == "A":
                    wins_a += 1
                    strategy_wins[name_a] += 1
                elif result.winner == "B":
                    wins_b += 1
                    strategy_wins[name_b] += 1

                strategy_games[name_a] += 1
                if name_a != name_b:
                    strategy_games[name_b] += 1

                # Track endings
                if result.ending_type in (
                    SimEndingType.POSITION_LOSS_A,
                    SimEndingType.POSITION_LOSS_B,
                    SimEndingType.RESOURCE_LOSS_A,
                    SimEndingType.RESOURCE_LOSS_B,
                ):
                    ending_counts["elimination"] += 1
                elif result.ending_type == SimEndingType.MUTUAL_DESTRUCTION:
                    ending_counts["mutual_destruction"] += 1
                elif result.ending_type == SimEndingType.CRISIS_TERMINATION:
                    ending_counts["crisis_termination"] += 1
                else:
                    ending_counts["max_turns"] += 1

            # Record head-to-head
            win_rate_a = wins_a / games
            win_rate_b = wins_b / games

            head_to_head[name_a][name_b] = win_rate_a
            if name_a != name_b:
                head_to_head[name_b][name_a] = win_rate_b

    # Compute aggregated results
    results.games_played = total_games
    results.avg_game_length = total_turns / total_games if total_games > 0 else 0

    for name in strategy_names:
        if strategy_games[name] > 0:
            results.strategy_win_rates[name] = strategy_wins[name] / strategy_games[name]
        else:
            results.strategy_win_rates[name] = 0.0

    results.head_to_head = head_to_head
    results.elimination_rate = ending_counts["elimination"] / total_games
    results.mutual_destruction_rate = ending_counts["mutual_destruction"] / total_games
    results.crisis_termination_rate = ending_counts["crisis_termination"] / total_games
    results.settlement_rate = 0.0  # Simulation doesn't include settlement

    if all_vps:
        results.vp_mean = statistics.mean(all_vps)
        results.vp_std_dev = statistics.stdev(all_vps) if len(all_vps) > 1 else 0.0

    return results


def check_dominant_strategy(sim_results: BalanceSimulationResults) -> CheckResult:
    """Check for dominant strategies in simulation results.

    A strategy is dominant if it has >60% overall win rate.

    Args:
        sim_results: Results from run_balance_simulation

    Returns:
        CheckResult with pass/fail and metrics
    """
    result = CheckResult(check_name="balance", passed=True)

    dominant_strategies = []
    for strategy, win_rate in sim_results.strategy_win_rates.items():
        if win_rate > THRESHOLDS["dominant_strategy"]:
            dominant_strategies.append({"strategy": strategy, "win_rate": win_rate})

    result.metrics["strategy_win_rates"] = sim_results.strategy_win_rates
    result.metrics["dominant_strategies"] = dominant_strategies
    result.metrics["threshold"] = THRESHOLDS["dominant_strategy"]

    if dominant_strategies:
        result.add_issue(
            ValidationSeverity.CRITICAL,
            f"Dominant strategy detected: {len(dominant_strategies)} strategies "
            f"exceed {THRESHOLDS['dominant_strategy']*100:.0f}% win rate",
            details={"dominant_strategies": dominant_strategies},
        )

    # Check variance
    result.metrics["vp_std_dev"] = sim_results.vp_std_dev
    if sim_results.vp_std_dev < THRESHOLDS["variance_min"]:
        result.add_issue(
            ValidationSeverity.MAJOR,
            f"Variance too low: {sim_results.vp_std_dev:.1f} "
            f"(expected >= {THRESHOLDS['variance_min']})",
            details={"vp_std_dev": sim_results.vp_std_dev},
        )
    if sim_results.vp_std_dev > THRESHOLDS["variance_max"]:
        result.add_issue(
            ValidationSeverity.MAJOR,
            f"Variance too high: {sim_results.vp_std_dev:.1f} "
            f"(expected <= {THRESHOLDS['variance_max']})",
            details={"vp_std_dev": sim_results.vp_std_dev},
        )

    # Check game length
    result.metrics["avg_game_length"] = sim_results.avg_game_length
    if sim_results.avg_game_length < THRESHOLDS["avg_game_length_min"]:
        result.add_issue(
            ValidationSeverity.MINOR,
            f"Average game length too short: {sim_results.avg_game_length:.1f} "
            f"(expected >= {THRESHOLDS['avg_game_length_min']})",
        )
    if sim_results.avg_game_length > THRESHOLDS["avg_game_length_max"]:
        result.add_issue(
            ValidationSeverity.MINOR,
            f"Average game length too long: {sim_results.avg_game_length:.1f} "
            f"(expected <= {THRESHOLDS['avg_game_length_max']})",
        )

    return result


# =============================================================================
# Narrative Consistency (Optional LLM Check)
# =============================================================================


async def check_narrative_consistency(
    scenario: dict | Scenario,
) -> CheckResult:
    """Check narrative consistency using LLM (optional).

    This is the only validation that uses LLM, and it's optional.
    Focuses on thematic coherence, not game theory or balance.

    Args:
        scenario: Scenario object or dict with scenario data

    Returns:
        CheckResult with pass/fail and any narrative issues found
    """
    result = CheckResult(check_name="narrative", passed=True)

    # Extract narrative elements
    narratives = []
    if hasattr(scenario, "turns"):
        for turn in scenario.turns:
            narratives.append(turn.narrative_briefing)
            narratives.append(turn.outcome_narratives.CC)
            narratives.append(turn.outcome_narratives.CD)
            narratives.append(turn.outcome_narratives.DC)
            narratives.append(turn.outcome_narratives.DD)
        for branch_turn in scenario.branches.values():
            narratives.append(branch_turn.narrative_briefing)
    else:
        for turn in scenario.get("turns", []):
            narratives.append(turn.get("narrative_briefing", ""))
            outcomes = turn.get("outcome_narratives", {})
            for outcome in ["CC", "CD", "DC", "DD"]:
                narratives.append(outcomes.get(outcome, ""))

    result.metrics["narrative_count"] = len(narratives)
    result.metrics["total_characters"] = sum(len(n) for n in narratives)

    # For now, just do basic checks without LLM
    # LLM integration would go here using claude-agent-sdk

    empty_narratives = sum(1 for n in narratives if not n or n.strip() == "")
    if empty_narratives > 0:
        result.add_issue(
            ValidationSeverity.MINOR,
            f"Empty narratives found: {empty_narratives}",
            details={"empty_count": empty_narratives},
        )

    return result


# =============================================================================
# Main Validator Class
# =============================================================================


class ScenarioValidator:
    """Scenario validator with deterministic Python checks.

    Usage:
        validator = ScenarioValidator()
        result = validator.validate("scenarios/my_scenario.json")

        # Or validate with simulation
        result = validator.validate("scenarios/my_scenario.json", run_simulation=True)

        # Check results
        if not result.overall_passed:
            for issue in result.get_critical_issues():
                print(f"CRITICAL: {issue.message}")
    """

    def __init__(
        self,
        simulation_games: int = 50,
        simulation_seed: int | None = None,
    ):
        """Initialize validator.

        Args:
            simulation_games: Number of games per pairing for balance simulation
            simulation_seed: Random seed for reproducibility
        """
        self.simulation_games = simulation_games
        self.simulation_seed = simulation_seed

    def validate(
        self,
        scenario_path: str | Path | None = None,
        scenario: dict | Scenario | None = None,
        run_simulation: bool = True,
        check_narrative: bool = False,
    ) -> ValidationResult:
        """Validate a scenario.

        Provide either scenario_path OR scenario object.

        Args:
            scenario_path: Path to scenario JSON file
            scenario: Scenario object or dict
            run_simulation: Whether to run balance simulation
            check_narrative: Whether to run narrative consistency check

        Returns:
            ValidationResult with all check results
        """
        result = ValidationResult()

        # Load scenario if path provided
        if scenario_path is not None:
            result.scenario_path = str(scenario_path)
            if load_scenario is not None:
                scenario = load_scenario(str(scenario_path))
            else:
                import json
                with open(scenario_path) as f:
                    scenario = json.load(f)

        if scenario is None:
            raise ValueError("Either scenario_path or scenario must be provided")

        # Extract scenario_id
        if hasattr(scenario, "scenario_id"):
            result.scenario_id = scenario.scenario_id
        elif isinstance(scenario, dict):
            result.scenario_id = scenario.get("scenario_id")

        # Run structural checks
        result.game_variety = check_game_variety(scenario)
        result.intelligence_games = check_intelligence_games(scenario)
        result.act_structure = check_act_structure(scenario)
        result.branching = check_branching_validity(scenario)
        result.settlement = check_settlement_config(scenario)

        # Run balance simulation if requested
        if run_simulation:
            sim_results = run_balance_simulation(
                scenario=scenario,
                games=self.simulation_games,
                seed=self.simulation_seed,
            )
            result.simulation_results = sim_results
            result.balance = check_dominant_strategy(sim_results)

        # Run narrative check if requested (sync wrapper for async function)
        if check_narrative:
            import asyncio

            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            result.narrative = loop.run_until_complete(
                check_narrative_consistency(scenario)
            )

        # Determine overall pass/fail
        for check in [
            result.game_variety,
            result.intelligence_games,
            result.act_structure,
            result.branching,
            result.settlement,
            result.balance,
            result.narrative,
        ]:
            if check is not None and not check.passed:
                result.overall_passed = False
                break

        return result

    def validate_from_dict(
        self,
        scenario_dict: dict,
        run_simulation: bool = True,
        check_narrative: bool = False,
    ) -> ValidationResult:
        """Validate a scenario from a dictionary.

        Convenience method for validating scenarios not yet saved to disk.

        Args:
            scenario_dict: Scenario as a dictionary
            run_simulation: Whether to run balance simulation
            check_narrative: Whether to run narrative consistency check

        Returns:
            ValidationResult with all check results
        """
        return self.validate(
            scenario=scenario_dict,
            run_simulation=run_simulation,
            check_narrative=check_narrative,
        )


def validate_scenario(
    scenario_path: str,
    run_simulation: bool = True,
    simulation_games: int = 50,
    check_narrative: bool = False,
) -> ValidationResult:
    """Validate a scenario file (convenience function).

    Args:
        scenario_path: Path to scenario JSON file
        run_simulation: Whether to run balance simulation
        simulation_games: Number of games per strategy pairing
        check_narrative: Whether to run narrative consistency check

    Returns:
        ValidationResult with all check results
    """
    validator = ScenarioValidator(simulation_games=simulation_games)
    return validator.validate(
        scenario_path=scenario_path,
        run_simulation=run_simulation,
        check_narrative=check_narrative,
    )
