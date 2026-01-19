# Test Removal Log

This document captures the reasoning for test consolidation and removal to reduce unit test volume by ~50% while maintaining coverage of critical end-to-end flows.

## Guiding Principles

1. **Favor E2E tests over unit tests**: Integration tests that exercise full flows are more valuable than isolated unit tests
2. **Test subsumption**: If difficult test A makes easy tests t1, t2, t3 redundant, remove t1, t2, t3
3. **Remove trivial accessor tests**: Don't test Pydantic validation, enum membership, or simple data structure accessors
4. **Remove over-mocked tests**: Tests with heavy mocking that don't test real behavior add little value
5. **Keep sync/async boundary tests**: These are critical for correctness

---

## Tests to REMOVE

### test_variance.py (~400 lines removed)

**Remove entire classes:**
- `TestClamp` (lines 23-55): Trivial tests for a simple clamp function. Subsumed by integration tests that use clamped values.
- `TestBaseSigma` (lines 58-95): Tests `risk * 0.03`. Subsumed by `TestCalculateSharedSigma`.
- `TestChaosFactor` (lines 98-130): Tests chaos factor formula. Subsumed by `TestCalculateSharedSigma`.
- `TestInstabilityFactor` (lines 133-165): Tests linear formula. Subsumed by `TestCalculateSharedSigma`.
- `TestActMultiplier` (lines 168-195): Tests simple dict lookup. Subsumed by `TestCalculateSharedSigma`.

**Reasoning**: `TestCalculateSharedSigma` and `TestFinalResolution` test the full variance calculation pipeline, making component tests redundant.

### test_endings.py (~250 lines removed)

**Remove:**
- `TestEndingType` (lines 39-55): Enum membership tests (MUTUAL_DESTRUCTION in EndingType, etc.)
- `TestGameEnding` (lines 58-95): Dataclass instantiation tests
- Individual ending check tests (`TestCheckMutualDestruction`, `TestCheckPositionLoss`, `TestCheckResourceLoss`, `TestCheckCrisisTermination`, `TestCheckMaxTurns`) - each ~30-50 lines

**Reasoning**: `TestCheckAllEndings` (lines 380-500) is a comprehensive integration test that checks all ending conditions together, making individual tests redundant.

### test_state_deltas.py (~400 lines removed)

**Remove:**
- `TestStateDeltaOutcome` (lines 45-90): Dataclass tests
- Individual ordinal consistency test classes (`TestOrdinalConsistencyPD`, `TestOrdinalConsistencyChicken`, `TestOrdinalConsistencyStagHunt`, `TestOrdinalConsistencyDeadlock`, `TestOrdinalConsistencyHarmony`) - each ~40-60 lines

**Reasoning**: `TestDeltaTemplates` uses parametrized fixtures to test all 14 MatrixTypes, subsuming individual game type tests. The integration tests at the end cover full workflows.

### test_storage.py (~200 lines removed)

**Remove:**
- `TestSlugify` (lines 23-75): 9 tests for a trivial utility function. Consolidate to 2-3 edge case tests.
- Duplicate backend-specific tests (File and SQLite have nearly identical test bodies)

**Keep**: Parametrized integration tests (`TestScenarioRepositoryIntegration`, `TestGameRecordRepositoryIntegration`)

### test_human_simulator.py (~350 lines removed)

**Remove entire classes:**
- `TestHumanPersona` validation tests (lines 30-107): Tests Pydantic validation (invalid_risk_tolerance, etc.). Pydantic is trusted.
- `TestHumanPersonaMethods` (lines 110-220): Tests trivial getter methods (get_mistake_probability returns dict lookup)
- `TestEffectiveMistakeProbability` (lines 258-299): Tests multiplication
- `TestActionSelection`, `TestMistakeCheck`, `TestSettlementResponse` model tests: Trivial dataclass tests
- `TestEdgeCases` (lines 494-607): Tests listing all enum values work

**Keep**: `TestHumanSimulator` class (non-LLM tests for interface)

### test_human_simulator_integration.py (~300 lines removed)

**Remove:**
- Most mocked tests that don't exercise real LLM behavior
- `TestPersonaGeneration` (heavily mocked)
- `TestMistakeInjection` (mocks randomness and LLM)

**Reasoning**: The real LLM integration tests in `test_real_llm_integration.py` provide actual coverage.

### test_post_game.py (~200 lines removed)

**Remove:**
- `TestCriticalDecision` (lines 39-56): Simple dataclass test
- `TestCoachingReport` (lines 63-92): Simple dataclass test
- `TestGetActForTurn` (lines 99-116): Tests trivial turn-to-act mapping
- `TestGetOutcomeDescription`, `TestFormatMatrixType`, `TestFormatEndingType`: Test string formatting helpers

**Keep**: `TestPostGameCoachBayesianInference`, `TestPostGameCoachParsing`, `TestFormatTurnHistory`

### test_analyze_mechanics.py (~150 lines removed)

**Remove:**
- `TestIssueSeverity` (lines 49-68): Enum value tests
- `TestIssue` (lines 75-108): Dataclass tests
- `TestDefaultThresholds` (lines 175-196): Tests constant values

**Keep**: `TestCheckDominantStrategy`, `TestCheckVarianceCalibration`, `TestCheckSettlementRate`, `TestAnalyzeMechanics`, `TestIntegration`

### test_playtester.py (~200 lines removed)

**Remove:**
- `TestActionChoice` (lines 60-75): Enum tests
- `TestSimplePlayerState` clamp tests (lines 82-115): Trivial
- `TestSimpleGameState` clamp tests (lines 163-173): Trivial

**Keep**: `TestApplyOutcome`, `TestCheckCrisisTermination`, `TestCheckEnding`, `TestFinalResolution`, `TestStrategies`, `TestRunGame`, `TestPairingStats`, `TestPlaytestRunner`, `TestIntegration`

### test_state.py (~300 lines removed)

**Remove:**
- Trivial accessor tests for PlayerState, GameState properties
- Dataclass instantiation tests
- Tests that just verify default values

**Keep**: Tests for state transitions, boundary conditions, and integration scenarios

### test_matrices.py (~400 lines removed)

**Remove:**
- Individual ordinal consistency tests for each matrix type
- Tests that just verify constant values in payoff matrices
- `TestMatrixType` enum tests

**Keep**: Parametrized tests covering all matrix types, `TestGetDeltaOutcome`, integration tests

### test_actions.py (~300 lines removed)

**Remove:**
- `TestActionType` enum tests
- `TestActionCategory` enum tests
- Trivial Action dataclass tests
- Tests for default values

**Keep**: `TestActionRegistry`, `TestGetAvailableActions` with complex filtering logic

---

## Tests to KEEP (Critical)

### Sync/Async Boundary Tests
- `tests/cli/test_app.py::TestAsyncSyncHandling` - Critical for correctness
- `run_opponent_method` tests - Ensures proper handling of sync/async opponent methods

### End-to-End Integration Tests
- `test_real_llm_integration.py` - Full game flows with real LLM
- `tests/webapp/test_real_engine_integration.py` - Full webapp game flows
- `tests/webapp/test_engine_adapter.py` - RealGameEngine tests

### Parametrized Tests
- All tests using `@pytest.fixture` with `params` to cover multiple matrix types/backends

### Integration Test Classes
- `TestIntegration` classes in each module
- `TestCheckAllEndings` in test_endings.py
- `TestFinalResolution` in test_variance.py

---

## Missing E2E Tests to ADD

### 1. Full Settlement Negotiation Flow
```python
# test_real_llm_integration.py
@pytest.mark.slow
@pytest.mark.llm_integration
def test_full_settlement_negotiation(self, cuban_missile_game):
    """Play until settlement conditions, propose settlement, handle response."""
    # Advance to turn 5+ with stability > 2
    # Propose settlement
    # Verify opponent evaluation
    # Handle counter-offer
    # Complete settlement
```

### 2. Mutual Destruction Ending
```python
def test_mutual_destruction_ending(self):
    """Play aggressively until risk_level = 10 triggers mutual destruction."""
```

### 3. Position/Resource Loss Endings
```python
def test_position_loss_ending_player_a(self):
    """Play until player A position drops to 0."""

def test_resource_exhaustion_ending(self):
    """Play until resources deplete."""
```

### 4. CLI Full Game with Settlement
```python
@pytest.mark.asyncio
async def test_cli_full_game_with_settlement_modal(self):
    """Test opening settlement modal and completing negotiation in CLI."""
```

### 5. Webapp Post-Game Coaching Flow
```python
def test_webapp_post_game_coaching(self, auth_real_engine_client):
    """Complete game and verify coaching report renders correctly."""
```

### 6. Multi-Turn Settlement Negotiation
```python
def test_multi_round_settlement_negotiation(self):
    """Test counter-offer loop until agreement or rejection."""
```

---

## Actual Impact (Final Results)

| File | Before | After | Reduction |
|------|--------|-------|-----------|
| test_variance.py | 772 | 457 | 41% |
| test_endings.py | 767 | 707 | 8% |
| test_state_deltas.py | 1029 | 850 | 17% |
| test_storage.py | 818 | 315 | 62% |
| test_human_simulator.py | 607 | 71 | 88% |
| test_post_game.py | 598 | 436 | 27% |
| test_analyze_mechanics.py | 710 | 549 | 23% |
| test_playtester.py | 812 | 685 | 16% |
| test_state.py | 1143 | 603 | 47% |
| test_matrices.py | 1358 | 948 | 30% |
| test_actions.py | 1142 | 573 | 50% |
| test_resolution.py | 1200 | 1088 | 9% |
| test_game_engine.py | 1200 | 884 | 26% |
| test_bayesian_inference.py | 600 | 434 | 28% |
| test_mechanics_benchmark.py | 300 | 207 | 31% |

**Summary:**
- Lines removed: ~4,200 lines across two commits
- Tests remaining: 660 (all passing)
- Test volume reduction: ~32% overall

---

## Implementation Order

1. Remove trivial enum/dataclass tests first (low risk)
2. Remove individual tests subsumed by parametrized tests
3. Remove over-mocked tests
4. Add missing E2E tests
5. Run full test suite to verify coverage
6. Commit with detailed message
