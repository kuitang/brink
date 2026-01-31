# Claude Code Instructions

## Required Reading

**CRITICAL**: Before starting any task, read `GAME_MANUAL.md` in the project root. This document contains the authoritative game rules and mechanics.

## Document Hierarchy

**IF YOU FIND A CONTRADICTION BETWEEN DOCUMENTS, FLAG IT LOUDLY** so it can be fixed. When proceeding:

1. **GAME_MANUAL.md** - authoritative source for game mechanics and formulas
2. **ENGINEERING_DESIGN.md** - implementation approach, defers to GAME_MANUAL.md

---

## Code Style

- All imports at top of file (stdlib, third-party, local)
- No try/except unless you have meaningful recovery
- No defensive programming against impossible states
- Trust internal code; only validate at system boundaries

---

## Running the Application

**CLI:**
```bash
uv run brinksmanship
```

**Webapp:**
```bash
uv sync --extra webapp
uv run python scripts/generate_manual.py
uv run brinksmanship-web
```

---

## Testing

**Balance simulation:**
```bash
uv run python scripts/balance_simulation.py --games 100
```

**Webapp E2E with Playwright MCP:**
1. Start webapp: `uv run brinksmanship-web`
2. Use `browser_navigate` to http://localhost:5000
3. Use `browser_snapshot` to verify UI state

---

## Key Files

| File | Purpose |
|------|---------|
| `src/brinksmanship/engine/state_deltas.py` | Outcome matrices, surplus mechanics |
| `src/brinksmanship/engine/game_engine.py` | Turn phases, game loop |
| `src/brinksmanship/models/state.py` | GameState with cooperation_surplus |
| `src/brinksmanship/webapp/static/css/style.css` | CSS themes |
| `scenarios/*.json` | Scenario definitions |
