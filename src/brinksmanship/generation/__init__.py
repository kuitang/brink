"""Scenario generation and validation for Brinksmanship.

This module provides tools for generating, validating, and loading scenarios.
Scenarios specify game structure using matrix_type + matrix_parameters pairs,
with matrices constructed at load time to guarantee type correctness.
"""

from .scenario_generator import (
    ACT_SCALING,
    GAME_TYPES_BY_THEME_AND_ACT,
    ScenarioGenerator,
    classify_theme,
    generate_scenario,
    get_act_for_turn,
    get_available_types_for_turn,
    parse_matrix_parameters,
    parse_matrix_type,
    scale_parameters_for_act,
    validate_and_build_matrix,
)
from .schemas import (
    BranchTargets,
    OutcomeCode,
    OutcomeNarratives,
    Scenario,
    TurnDefinition,
    load_scenario,
    save_scenario,
)
from .validator import (
    THRESHOLDS,
    BalanceSimulationResults,
    CheckResult,
    ScenarioValidator,
    ValidationIssue,
    ValidationResult,
    ValidationSeverity,
    check_act_structure,
    check_branching_validity,
    check_dominant_strategy,
    check_game_variety,
    check_settlement_config,
    run_balance_simulation,
    validate_scenario,
)

__all__ = [
    # From schemas.py
    "BranchTargets",
    "OutcomeCode",
    "OutcomeNarratives",
    "Scenario",
    "TurnDefinition",
    "load_scenario",
    "save_scenario",
    # From scenario_generator.py
    "ACT_SCALING",
    "GAME_TYPES_BY_THEME_AND_ACT",
    "ScenarioGenerator",
    "classify_theme",
    "generate_scenario",
    "get_act_for_turn",
    "get_available_types_for_turn",
    "parse_matrix_parameters",
    "parse_matrix_type",
    "scale_parameters_for_act",
    "validate_and_build_matrix",
    # From validator.py
    "THRESHOLDS",
    "BalanceSimulationResults",
    "CheckResult",
    "ScenarioValidator",
    "ValidationIssue",
    "ValidationResult",
    "ValidationSeverity",
    "check_act_structure",
    "check_branching_validity",
    "check_dominant_strategy",
    "check_game_variety",
    "check_settlement_config",
    "run_balance_simulation",
    "validate_scenario",
]
