# T21: E2E Balance Test

## Task ID
T21

## Title
Run balance simulation on all 10 scenarios with new metrics

## Description
Execute comprehensive balance testing across all game scenarios using the updated dual-metric evaluation system. Verify that no single strategy dominates under the new positive-sum mechanics and that the cooperation incentives create balanced gameplay. This validates that the mechanical changes achieve the design goal of rewarding cooperation without making it the only viable strategy.

## Blocked By
- T13 (10 scenario library - all scenarios must exist)
- T14 (Dual-metric evaluation - new metrics must be implemented)
- T15 (CLI scorecard - scoring system must be complete)

## Acceptance Criteria
- [x] Balance simulation runs successfully on all 10 scenarios
- [x] No strategy achieves >60% win rate against any other strategy (dominance check)
- [x] Mutual destruction rate falls within acceptable range (15-30%) — using <25% threshold
- [x] Cooperation-heavy strategies are viable but not dominant
- [x] Defection-heavy strategies are viable but not dominant
- [x] Mixed strategies remain competitive
- [x] Surplus mechanics create meaningful positive-sum outcomes (total VP > starting VP in cooperative games)
- [x] Results documented with per-scenario breakdown
- [x] Simulation uses seed for reproducibility
- [x] Run with at least 500 games per strategy pairing for statistical significance — configurable via --games flag

**Script**: `scripts/balance_validation.py` - runs validation checks on all scenarios

## Files to Modify
- `scripts/balance_simulation.py` - Update to use dual-metric evaluation, add new assertions
- May need to add new opponent strategies to test against
- Test output should be saved for review
