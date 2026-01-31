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
- [ ] Document all features in CLI
- [ ] Document all features in Webapp
- [ ] Identify gaps in either direction

### Required Parity Features
Both CLI and Webapp MUST support:
- [ ] New game creation with scenario selection
- [ ] Opponent selection (all 6 deterministic + LLM opponents)
- [ ] Turn-by-turn gameplay with action selection
- [ ] Surplus display (pool size, captured amounts)
- [ ] Settlement negotiation flow (propose/counter/accept/reject)
- [ ] Escalating rejection penalty visible
- [ ] Multi-criteria scorecard at game end
- [ ] Game state display:
  - Risk level
  - Cooperation score
  - Stability
  - Cooperation streak
  - Turn/Act indicator
- [ ] Historical turn log (outcome per turn)
- [ ] Save/load game (Webapp has sessions, CLI has file)

### Nice-to-Have (may differ):
- Theme selection (Webapp has CSS themes, CLI has text-only)
- Leaderboards (Webapp only)
- User accounts (Webapp only)

## Testing
- [ ] Play through complete game on CLI
- [ ] Play through same scenario on Webapp
- [ ] Verify same mechanics, same information shown
- [ ] Verify settlement flow works identically

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
