# T05: Balance Simulation with Dual Metrics

## Task ID
T05

## Title
Upgrade balance simulation to collect Total Value and implement dual-metric dominance threshold

## Description
The current balance simulation only tracks win rates. Upgrade it to track the PRIMARY balance metric: Total Value (VP_A + VP_B). Implement the dual-metric dominance test from GAME_MANUAL.md: a strategy is only dominant if it achieves BOTH >120 total value AND >55% share.

This task is HIGH PRIORITY because it provides the feedback loop for all subsequent balance tuning.

## Blocked By
- T02 (parameters.py - needed for thresholds)

## Acceptance Criteria
- [ ] `PairingStats` in batch_runner.py tracks:
  - Total Value (VP_A + VP_B) per game
  - VP Share (VP_A / Total) per game
  - Settlement rate (games ending in settlement)
  - Surplus metrics (final pool size, total captured, total created)
- [ ] `BatchResults` computes aggregates:
  - Average Total Value
  - Average VP Share per opponent
  - Settlement rate across all games
  - Mutual destruction rate (must be <20%)
- [ ] `print_results_summary` displays:
  - Total Value statistics (mean, std, min, max)
  - VP Share breakdown by opponent
  - Settlement vs other ending rates
- [ ] Dominance detection uses dual threshold:
  - OLD: >60% win rate = dominant (REMOVE)
  - NEW: >120 total value AND >55% share = dominant
- [ ] Balance pass criteria from GAME_MANUAL.md are checked:
  - No dominant strategy
  - Variance 10-40 range
  - Settlement rate 30-70%
  - Mutual destruction rate <20%
  - Game length 10-16 turns

## Files to Modify
- `src/brinksmanship/testing/batch_runner.py`
- `src/brinksmanship/testing/game_runner.py` (if GameResult needs new fields)
- `scripts/balance_simulation.py`

## Example Output
```
================================================================================
BATCH SIMULATION RESULTS
================================================================================
Scenario: cuban_missile_crisis
Total Games: 1050

TOTAL VALUE STATISTICS
--------------------------------------------------------------------------------
  Mean Total Value: 112.4 VP
  Std Dev: 18.2
  Min: 40 (mutual destruction)
  Max: 156 (high cooperation + settlement)

ENDING TYPE BREAKDOWN
--------------------------------------------------------------------------------
  Settlement: 45.2%
  Natural ending: 28.1%
  Crisis termination: 12.4%
  Mutual destruction: 14.3% ✓ (target <20%)

VP SHARE BY OPPONENT (when they win)
--------------------------------------------------------------------------------
  NashCalculator: 52.1% share (Total: 108.2)
  SecuritySeeker: 51.8% share (Total: 118.4)
  ...

DOMINANCE CHECK
--------------------------------------------------------------------------------
  No dominant strategy found. ✓
  (Dominant = >120 total AND >55% share)
================================================================================
```

## Notes
- This task enables continuous balance feedback
- Run simulation after ANY parameter change
- Settlement rate is critical - if too low, surplus mechanics aren't working
