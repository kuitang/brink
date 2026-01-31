# Comprehensive LLM Playtest Report

**Generated:** 2026-01-31T06:52:17.422665

---

## Overall Summary

**Total Games:** 60
**Valid Games:** 54
**Errors:** 6

| Metric | Value |
|--------|-------|
| Settlement Rate | 63.0% |
| Mutual Destruction Rate | 3.7% |
| Player A Win Rate | 55.6% |
| Player B Win Rate | 40.7% |
| Average Game Length | 9.7 turns |
| Average Final Risk | 1.85 |

## Results by Matchup Type

### Historical vs Historical

| Metric | Value |
|--------|-------|
| Games | 20 |
| Settlement Rate | 10.0% |
| MD Rate | 10.0% |

### Smart vs Historical

| Metric | Value |
|--------|-------|
| Games | 34 |
| Settlement Rate | 94.1% |
| MD Rate | 0.0% |

## Results by Scenario

| Scenario | Games | Settlement | MD | A Wins | B Wins |
|----------|-------|------------|-----|--------|--------|
| berlin_blockade | 2 | 0 (0%) | 0 (0%) | 2 | 0 |
| brexit_negotiations | 4 | 2 (50%) | 0 (0%) | 2 | 2 |
| byzantine_succession | 6 | 4 (66%) | 0 (0%) | 4 | 2 |
| cold_war_espionage | 6 | 4 (66%) | 0 (0%) | 4 | 2 |
| cuban_missile_crisis | 6 | 4 (66%) | 0 (0%) | 2 | 4 |
| medici_banking_dynasty | 6 | 3 (50%) | 0 (0%) | 3 | 3 |
| nato_burden_sharing | 6 | 4 (66%) | 0 (0%) | 4 | 2 |
| opec_oil_politics | 6 | 5 (83%) | 0 (0%) | 3 | 3 |
| silicon_valley_tech_wars | 6 | 3 (50%) | 2 (33%) | 3 | 1 |
| taiwan_strait_crisis | 6 | 5 (83%) | 0 (0%) | 3 | 3 |

## Detailed Matchup Results

| Scenario | Player A | Player B | Games | A Wins | B Wins | Settlement | MD |
|----------|----------|----------|-------|--------|--------|------------|-----|
| opec_oil_politics | kissinger | bismarck | 2 | 1 | 1 | 1 | 0 |
| nato_burden_sharing | Smart | bismarck | 2 | 2 | 0 | 2 | 0 |
| silicon_valley_tech_wars | gates | jobs | 2 | 0 | 0 | 0 | 2 |
| nato_burden_sharing | nixon | bismarck | 2 | 2 | 0 | 0 | 0 |
| byzantine_succession | Smart | livia | 2 | 2 | 0 | 2 | 0 |
| cuban_missile_crisis | Smart | khrushchev | 2 | 0 | 2 | 2 | 0 |
| cold_war_espionage | kissinger | Smart | 2 | 0 | 2 | 2 | 0 |
| cold_war_espionage | Smart | khrushchev | 2 | 2 | 0 | 2 | 0 |
| brexit_negotiations | bismarck | Smart | 2 | 0 | 2 | 2 | 0 |
| cuban_missile_crisis | nixon | khrushchev | 2 | 2 | 0 | 0 | 0 |
| opec_oil_politics | kissinger | Smart | 2 | 0 | 2 | 2 | 0 |
| silicon_valley_tech_wars | gates | Smart | 2 | 1 | 1 | 1 | 0 |
| taiwan_strait_crisis | kissinger | Smart | 2 | 0 | 2 | 2 | 0 |
| cold_war_espionage | kissinger | khrushchev | 2 | 2 | 0 | 0 | 0 |
| silicon_valley_tech_wars | Smart | jobs | 2 | 2 | 0 | 2 | 0 |
| byzantine_succession | theodora | livia | 2 | 2 | 0 | 0 | 0 |
| opec_oil_politics | Smart | bismarck | 2 | 2 | 0 | 2 | 0 |
| medici_banking_dynasty | richelieu | metternich | 2 | 2 | 0 | 0 | 0 |
| cuban_missile_crisis | nixon | Smart | 2 | 0 | 2 | 2 | 0 |
| taiwan_strait_crisis | Smart | khrushchev | 2 | 2 | 0 | 2 | 0 |
| byzantine_succession | theodora | Smart | 2 | 0 | 2 | 2 | 0 |
| nato_burden_sharing | nixon | Smart | 2 | 0 | 2 | 2 | 0 |
| medici_banking_dynasty | richelieu | Smart | 2 | 1 | 1 | 1 | 0 |
| berlin_blockade | nixon | khrushchev | 2 | 2 | 0 | 0 | 0 |
| taiwan_strait_crisis | kissinger | khrushchev | 2 | 1 | 1 | 1 | 0 |
| brexit_negotiations | bismarck | metternich | 2 | 2 | 0 | 0 | 0 |
| medici_banking_dynasty | Smart | metternich | 2 | 0 | 2 | 2 | 0 |

## Errors

- berlin_blockade: 'GameState' object has no attribute 'scenario_id'
- berlin_blockade: 'GameState' object has no attribute 'scenario_id'
- berlin_blockade: 'GameState' object has no attribute 'scenario_id'
- berlin_blockade: 'GameState' object has no attribute 'scenario_id'
- brexit_negotiations: _try_settlement() missing 1 required positional argument: 'scenario_id'
- brexit_negotiations: _try_settlement() missing 1 required positional argument: 'scenario_id'