# T24: Parameter Sweep Simulation

## Task ID
T24

## Title
Create parameter sweep simulation for balance tuning

## Description
Build a grid search simulation that tests combinations of key parameters and reports which combinations meet all balance criteria. This automates the tuning process.

## Blocked By
- T23 (Exploitation timing sim - uses similar infrastructure)

## Acceptance Criteria
- [x] Script `scripts/parameter_sweep.py` exists
- [x] Accepts parameter ranges as arguments
- [x] Default sweep:
  - CAPTURE_RATE: [0.3, 0.4, 0.5]
  - REJECTION_BASE_PENALTY: [1.0, 1.5, 2.0]
  - DD_RISK_INCREASE: [1.5, 1.8, 2.0]
- [x] For each combination, runs balance validation (100 games per pairing)
- [x] Checks all pass criteria:
  - No dominant strategy (>120 total AND >55% share)
  - Variance 10-40 range
  - Settlement rate 30-70%
  - Mutual destruction rate <20%
  - Game length 10-16 turns
- [x] Outputs ranked results showing which combinations pass/fail

**Note**: Uses monkey-patching in ProcessPoolExecutor workers to isolate parameter changes

## Expected Output
```
PARAMETER SWEEP RESULTS
================================================================================
                        | Total | Settle | MD   | Dominant | PASS
Params                  | Value | Rate   | Rate | Check    |
--------------------------------------------------------------------------------
CAPT=0.4 REJ=1.5 DD=1.8 | 112.4 | 45.2%  | 14%  | None     | ✓ PASS
CAPT=0.4 REJ=1.0 DD=1.8 | 108.2 | 32.1%  | 16%  | None     | ✓ PASS
CAPT=0.5 REJ=1.5 DD=2.0 | 118.7 | 38.4%  | 22%  | None     | ✗ MD>20%
CAPT=0.3 REJ=2.0 DD=1.5 |  98.2 | 68.1%  |  8%  | None     | ✗ Settle>70%
...
--------------------------------------------------------------------------------
RECOMMENDED: CAPTURE_RATE=0.4, REJECTION_BASE_PENALTY=1.5, DD_RISK_INCREASE=1.8
```

## Files to Create
- `scripts/parameter_sweep.py`

## Notes
- This script temporarily modifies parameters.py for each test
- Should restore original values after sweep
- Consider using subprocess to isolate parameter changes
