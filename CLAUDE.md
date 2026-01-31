# Claude Code Instructions

## Required Reading

**CRITICAL**: Before starting any task, read `GAME_MANUAL.md` in the project root. This document contains the authoritative game rules and mechanics.

## Document Hierarchy

**IF YOU FIND A CONTRADICTION BETWEEN DOCUMENTS, FLAG IT LOUDLY** so it can be fixed. When proceeding:

1. **GAME_MANUAL.md** - authoritative source for game mechanics and formulas
2. **ENGINEERING_DESIGN.md** - implementation approach, defers to GAME_MANUAL.md

---

## Code Style

- **All imports at top of file** - group in order: stdlib, third-party, local. Never import inside functions or methods.
- No try/except unless you have meaningful recovery
- No defensive programming against impossible states
- Trust internal code; only validate at system boundaries

---

## Task Execution with Barriers

When implementing code according to a plan with commit barriers (see `tasks/INDEX.md`):

1. **Commit after each barrier** - Don't wait until the end. Each barrier is a stable checkpoint.
2. **Update task docs** - Check off completed items in task .md files as you work
3. **Run tests before commit** - `uv run pytest` must pass at each barrier
4. **Use barrier commit messages** - Format: `"Barrier N: Description (T01, T02, ...)"`

---

## Running the Application

**CLI:**
```bash
uv run brinksmanship
```

**Webapp:**
```bash
uv sync --extra webapp
uv run brinksmanship-web
```

---

## Testing

**Balance simulation:**
```bash
uv run python scripts/balance_simulation.py --games 100
```

**Webapp E2E with Playwright MCP (local):**
1. Start webapp: `uv run brinksmanship-web`
2. Use `browser_navigate` to http://localhost:5000
3. Use `browser_snapshot` to verify UI state

---

## Production Testing with Playwright

**Production URL:** https://brink.fly.dev/

### Running Playwright Tests Against Production

Use Playwright MCP to interactively test the production deployment:

1. Navigate to production:
   ```
   browser_navigate to https://brink.fly.dev/
   ```

2. Take snapshots to verify UI state:
   ```
   browser_snapshot
   ```

3. Interact with game elements using `browser_click`, `browser_type`, etc.

### Monitoring Fly Logs While Testing

Open a terminal to watch production logs in real-time:
```bash
~/.fly/bin/flyctl logs --app brink
```

This shows Flask request logs, errors, and any print/logging output from the app.

### Closed-Loop Testing Workflow

Follow this workflow for systematic production testing:

1. **Run test** - Use Playwright MCP to perform an action on https://brink.fly.dev/
2. **Check logs** - Watch `flyctl logs` output for errors or unexpected behavior
3. **Take snapshot** - Use `browser_snapshot` to capture UI state
4. **Fix issues** - If problems found, fix locally, test with `uv run pytest`, deploy
5. **Repeat** - Continue testing until all flows work correctly

**Example session:**
```
# Terminal 1: Watch logs
~/.fly/bin/flyctl logs --app brink

# Terminal 2 (Claude Code): Run Playwright tests
browser_navigate to https://brink.fly.dev/
browser_snapshot  # Verify home page
browser_click on "New Game"
browser_snapshot  # Verify game started
# Check Terminal 1 for any errors
```

---

## Key Files

| File | Purpose |
|------|---------|
| `src/brinksmanship/engine/state_deltas.py` | Outcome matrices, surplus mechanics |
| `src/brinksmanship/engine/game_engine.py` | Turn phases, game loop |
| `src/brinksmanship/models/state.py` | GameState with cooperation_surplus |
| `src/brinksmanship/webapp/static/css/style.css` | CSS themes |
| `scenarios/*.json` | Scenario definitions |

---

## Git Workflow

**After pushing, always check CI/CD status:**
```bash
# Check all recent workflow runs
gh run list --limit 5

# Watch a specific run
gh run watch

# View logs for a failed run
gh run view <run-id> --log
```

**Push and monitor:**
```bash
git push origin main && gh run list --limit 3
```

---

## Fly.io Deployment

**View logs:**
```bash
~/.fly/bin/flyctl logs --app brink
```

**Set secrets (NEVER commit secrets to git):**
```bash
~/.fly/bin/flyctl secrets set ANTHROPIC_API_KEY=sk-ant-... --app brink
```

**List current secrets:**
```bash
~/.fly/bin/flyctl secrets list --app brink
```

**Deploy manually:**
```bash
~/.fly/bin/flyctl deploy --app brink
```

**SSH into running container:**
```bash
~/.fly/bin/flyctl ssh console --app brink
```
