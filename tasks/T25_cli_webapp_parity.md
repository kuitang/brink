# T25: CLI/Webapp Feature Parity Check

## Task ID
T25

## Title
Audit CLI and Webapp for feature parity and implement missing features

## Description
Both CLI and Webapp should provide the same gameplay experience. This task audits both interfaces and implements any missing features to achieve parity.

## Blocked By
- T16 (CLI scorecard - CLI should be complete)
- T20 (Webapp scorecard - Webapp should be complete)

## Acceptance Criteria

### Audit Checklist
- [x] Document all features in CLI
- [x] Document all features in Webapp
- [x] Identify gaps in either direction

### Required Parity Features
Both CLI and Webapp MUST support:
- [x] New game creation with scenario selection
- [x] Opponent selection (all 6 deterministic + LLM opponents)
- [x] Turn-by-turn gameplay with action selection
- [x] Surplus display (pool size, captured amounts)
- [x] Settlement negotiation flow (propose/counter/accept/reject)
- [x] Escalating rejection penalty visible
- [x] Multi-criteria scorecard at game end
- [x] Game state display:
  - Risk level
  - Cooperation score
  - Stability
  - Cooperation streak
  - Turn/Act indicator
- [x] Historical turn log (outcome per turn)
- [x] Save/load game (Webapp has sessions, CLI has file) — CLI is in-memory only (acceptable difference)

### Nice-to-Have (may differ):
- Theme selection (Webapp has CSS themes, CLI has text-only) — As expected
- Leaderboards (Webapp only) — As expected
- User accounts (Webapp only) — As expected

## Testing
- [x] Play through complete game on CLI
- [x] Play through same scenario on Webapp
- [x] Verify same mechanics, same information shown
- [x] Verify settlement flow works identically

**Report**: `docs/CLI_WEBAPP_PARITY_REPORT.md`

## Files to Audit
- `src/brinksmanship/cli/app.py`
- `src/brinksmanship/webapp/routes/*.py`
- `src/brinksmanship/webapp/templates/*.html`

## Deliverable
Markdown report listing:
1. Features present in both
2. Features missing from CLI
3. Features missing from Webapp
4. Implementation plan for gaps
