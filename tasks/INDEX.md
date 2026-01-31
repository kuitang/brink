# Task Index

## Overview

Implement the Joint Investment model for Brinksmanship. Surplus mechanics fundamentally change the game - **many existing tests will be deleted or rewritten**.

---

## DAG

```
T00 ─────────────────────────────────────────────────────────────────────────┐
 │                                                                            │
 ▼                                                                            │
T01 ──┬── T02                                                                 │
      │    │                                                                  │
      │    ▼                                                                  │
      │   T03 ── T04 ── T05 ── T06 ── T07 ── T08                             │
      │                                 │                                     │
      │                                 ├── T09 ── T23 ── T24                │
      │                                 │                                     │
      ▼                                 │                                     │
     T10 ── T11 ── T12 ─────────────────┼── T15 ── T16                       │
                                        │                                     │
                                        ├── T13 ── T17                       │
                                        │                                     │
                                        └── T14 ── T18 ── T19 ── T20         │
                                                                              │
                                        T21, T22, T25 ◄───────────────────────┘
```

---

## Task List

| ID | Task | Depends | Tests to Add |
|----|------|---------|--------------|
| **Barrier 0** |
| T00 | Test harness setup | - | conftest.py, restructure dirs |
| **Barrier 1** |
| T01 | Delete obsolete docs | T00 | - |
| T02 | Create parameters.py | T00 | test_parameters.py |
| **Barrier 2** |
| T03 | GameState surplus fields | T01,T02 | test_state.py updates |
| **Barrier 3** |
| T04 | State deltas surplus | T03 | test_state_deltas.py |
| T05 | Engine surplus logic | T04 | test_game_engine.py updates |
| T06 | Variance/VP with surplus | T05 | test_variance.py |
| T07 | Settlement + rejection | T06 | test_settlement.py (new) |
| **Barrier 4** |
| T08 | Integration test | T07 | test_full_game_surplus.py |
| T09 | Balance sim dual metrics | T07 | test_balance_metrics.py |
| **Barrier 5a: CLI** |
| T10 | Remove Textual | T01 | - |
| T11 | CLI scaffolding | T10 | - |
| T12 | CLI game loop | T05,T11 | test_cli_game.py |
| T15 | CLI settlement UI | T07,T12 | test_cli_settlement.py |
| T16 | CLI scorecard | T15 | test_cli_scorecard.py |
| **Barrier 5b: Webapp** |
| T14 | Webapp surplus display | T07 | test_webapp_surplus.py |
| T18 | CSS era themes | T14 | test_themes.py |
| T19 | Theme selection UI | T18 | - |
| T20 | Webapp scorecard | T14 | test_webapp_scorecard.py |
| **Barrier 5c: Scenarios** |
| T13 | Scenario schema theme | T07 | test_scenario_schema.py |
| T17 | Update all scenarios | T13 | test_scenarios.py |
| **Barrier 5d: Simulations** |
| T23 | Exploitation timing sim | T09 | test_exploitation_timing.py |
| T24 | Parameter sweep sim | T23 | test_parameter_sweep.py |
| **Barrier 6: Validation** |
| T21 | E2E balance test | T08,T16,T17 | test_balance_validation.py |
| T22 | Visual QA themes | T18,T19,T20 | test_visual_qa.py |
| T25 | CLI/Webapp parity | T16,T20 | test_parity.py |

---

## Commit Barriers

### BARRIER 0: Test Harness
**Task:** T00

**Work:**
- Restructure `tests/` into `unit/`, `integration/`, `gameplay/`, `webapp/`, `cli/`, `e2e/`
- Add Playwright to dev dependencies
- Register pytest markers
- **DELETE** old tests assuming no surplus mechanics

**Commit:** `"Barrier 0: Test harness restructured"`

---

### BARRIER 1: Foundation
**Tasks:** T01, T02

**Work:**
- Delete obsolete docs
- Create `src/brinksmanship/parameters.py`

**Tests:** test_parameters.py

**Commit:** `"Barrier 1: Foundation (T01, T02)"`

---

### BARRIER 2: State Model
**Task:** T03

**Work:**
- Add surplus fields to GameState

**Tests:** Update test_state.py

**Commit:** `"Barrier 2: GameState with surplus (T03)"`

---

### BARRIER 3: Engine Mechanics
**Tasks:** T04 → T05 → T06 → T07

**Work:**
- State deltas with surplus create/capture/burn
- Engine integrates surplus
- VP includes captured surplus
- Settlement distributes surplus, escalating rejection

**Tests:** test_state_deltas.py, test_variance.py, test_settlement.py (new)

**Commit:** `"Barrier 3: Engine mechanics (T04-T07)"`

---

### BARRIER 4: Integration
**Tasks:** T08, T09

**Work:**
- Integration test: full game with surplus
- Balance sim: dual metrics, Total Value

**Tests:** test_full_game_surplus.py, test_balance_metrics.py

**Manual Verification:**
- Play CLI game via Opus subtask
- Run balance simulation, verify metrics

**Commit:** `"Barrier 4: Integration (T08, T09)"`

---

### BARRIER 5a: CLI
**Tasks:** T10 → T11 → T12 → T15 → T16

**Work:**
- Remove Textual, add simple-term-menu
- Game loop, settlement UI, scorecard

**Tests:** tests/cli/*.py

**Manual:** Play full game in CLI

**Commit:** `"Barrier 5a: CLI complete (T10-T16)"`

---

### BARRIER 5b: Webapp
**Tasks:** T14 → T18 → T19 → T20

**Work:**
- Surplus display, CSS themes, scorecard

**Tests:** tests/webapp/*.py, tests/e2e/*.py

**Manual:** Play via Playwright MCP

**Commit:** `"Barrier 5b: Webapp complete (T14, T18-T20)"`

---

### BARRIER 5c: Scenarios
**Tasks:** T13 → T17

**Work:**
- Add theme to schema
- Update all scenario files

**Tests:** test_scenario_schema.py, test_scenarios.py

**Commit:** `"Barrier 5c: Scenarios (T13, T17)"`

---

### BARRIER 5d: Simulations
**Tasks:** T23 → T24

**Work:**
- Exploitation timing analysis
- Parameter sweep

**Tests:** test_exploitation_timing.py, test_parameter_sweep.py

**Commit:** `"Barrier 5d: Simulations (T23, T24)"`

---

### BARRIER 6: Validation
**Tasks:** T21, T22, T25

**Merge:** Combine all barrier-5 branches

**Work:**
- E2E balance test
- Visual QA
- CLI/Webapp parity

**Tests:** test_balance_validation.py, test_visual_qa.py, test_parity.py

**Manual:**
- Play same scenario on CLI and Webapp
- Verify identical mechanics
- Balance simulation passes all criteria

**Commit:** `"Barrier 6: Validation complete (T21, T22, T25)"`

---

### BARRIER 7: Release

```bash
git checkout main
git merge feat/surplus-mechanics --no-ff
git tag v2.0.0
```

---

## Testing

### CI Script
```bash
./scripts/ci.sh    # Runs ALL tests + balance simulation
```

### During Tasks
- Add tests as you implement
- Run `uv run pytest` frequently
- UI tasks: also run Playwright

### At Barriers
1. Run `./scripts/ci.sh`
2. Do manual verification
3. Commit only if both pass

---

## Manual Verification

**Barrier 4+:**
- [ ] Play CLI via Opus subtask
- [ ] Surplus builds on CC
- [ ] Capture works on CD/DC

**Barrier 5b+:**
- [ ] Play webapp via Playwright MCP
- [ ] Surplus displays correctly
- [ ] Settlement shows surplus split

**Barrier 6:**
- [ ] CLI and Webapp identical mechanics
- [ ] Balance sim: settlement 30-70%, MD <20%, no dominant strategy
