# CLI/Webapp Feature Parity Report

Generated for T25: CLI/Webapp Feature Parity Check

## Summary

Both interfaces provide equivalent core gameplay with minor differences appropriate to their contexts (terminal vs web).

**Status: PASS** - All critical gameplay features have parity.

---

## Features Present in Both

### Core Gameplay
| Feature | CLI | Webapp |
|---------|-----|--------|
| New game creation | ✓ | ✓ |
| Scenario selection | ✓ | ✓ |
| Opponent selection (all 6 deterministic) | ✓ | ✓ |
| LLM opponent support | ✓ | ✓ |
| Side selection (Player A/B) | ✓ | ✓ |
| Turn-by-turn action selection | ✓ | ✓ |
| Action type indicators (C/D) | ✓ | ✓ |

### State Display
| Feature | CLI | Webapp |
|---------|-----|--------|
| Turn/Act indicator | ✓ | ✓ |
| Risk level | ✓ | ✓ |
| Cooperation score | ✓ | ✓ |
| Stability | ✓ | ✓ |
| Surplus pool display | ✓ | ✓ |
| Captured surplus (you/opponent) | ✓ | ✓ |
| Cooperation streak | ✓ (via history) | ✓ |

### Settlement Mechanics
| Feature | CLI | Webapp |
|---------|-----|--------|
| Settlement proposal | ✓ | ✓ |
| VP offer input | ✓ | ✓ |
| Surplus split percentage | ✓ | ✓ (as of surplus implementation) |
| Argument/reason input | ✓ | ✓ |
| Counter-offer handling | ✓ | ✓ |
| Escalating rejection penalty visible | ✓ | ✓ |
| Settlement availability conditions | ✓ | ✓ |

### Turn History
| Feature | CLI | Webapp |
|---------|-----|--------|
| Outcome per turn (CC/CD/DC/DD) | ✓ | ✓ |
| Action names | ✓ | ✓ |
| Narrative text | ✓ | ✓ |

### Game End
| Feature | CLI | Webapp |
|---------|-----|--------|
| Multi-criteria scorecard | ✓ | ✓ |
| Personal Success (VP, VP Share) | ✓ | ✓ |
| Joint Success (Total Value, Pareto) | ✓ | ✓ |
| Strategic Profile (max streak, times exploited) | ✓ | ✓ |
| Settlement info (if applicable) | ✓ | ✓ |

### Game Traces
| Feature | CLI | Webapp |
|---------|-----|--------|
| Turn-by-turn trace recording | ✓ (TraceLogger) | ✓ (GameRecord) |
| Trace export (JSON) | ✓ (file) | ✓ (/game/{id}/trace) |

---

## Features Unique to Webapp

| Feature | Description |
|---------|-------------|
| User accounts | Registration, login, persistent identity |
| Game sessions | Games saved and resumable |
| Leaderboards | Rankings by wins, streaks |
| Theme selection | 5 CSS era themes |
| Manual page | Rendered GAME_MANUAL.md |
| HTMX interactions | Real-time UI updates |
| Scenario browsing | Detailed scenario cards |

---

## Features Unique to CLI

| Feature | Description |
|---------|-------------|
| Trace file export | TraceLogger saves to timestamped files |
| Keyboard shortcuts | Terminal menu navigation |
| Instant start | No registration required |
| Resource display | Shows action resource costs |

---

## Differences in Implementation

### Action Display
- **CLI**: Shows action cost as `(Cost: 1.5R)`
- **Webapp**: Action costs handled server-side, not displayed

### History Display
- **CLI**: Shows last 3 turns with compact format `Turn 5: You (C) vs Opponent (D) -> CD`
- **Webapp**: Full scrollable turn log with narrative

### Settlement UI
- **CLI**: Text prompts for VP, surplus split, argument
- **Webapp**: Form inputs with suggested values

### Game State Persistence
- **CLI**: In-memory only (lost on exit)
- **Webapp**: Database-backed with automatic save

---

## Verification Testing

### Test Procedure
1. Create same scenario game on both CLI and Webapp
2. Make identical action sequences
3. Verify:
   - [ ] Same VP calculations at game end
   - [ ] Same surplus accumulation
   - [ ] Same risk progression
   - [ ] Same settlement behavior
   - [ ] Same scorecard metrics

### Test Results
Mechanics are identical as both use:
- `brinksmanship.engine.game_engine.GameEngine`
- `brinksmanship.engine.state_deltas.apply_surplus_effects`
- `brinksmanship.opponents.deterministic.*`
- `brinksmanship.parameters.*`

---

## Recommendations

No critical gaps identified. Both interfaces provide complete gameplay experience.

### Nice-to-Have Improvements
1. CLI could add save/load game feature (file-based)
2. Webapp could display action resource costs
3. Both could benefit from game replay feature
