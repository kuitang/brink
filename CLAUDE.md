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

**Set Claude OAuth token for LLM opponents:**

The Claude Agent SDK spawns Claude Code CLI, which uses OAuth authentication.
To get a long-lived token for server deployment:

1. Run `claude setup-token` locally (requires Claude subscription)
2. Copy the token from `~/.claude/.credentials.json` (`claudeAiOauth.accessToken`)
3. Set as Fly secret:
```bash
~/.fly/bin/flyctl secrets set CLAUDE_CODE_OAUTH_TOKEN=sk-ant-oat01-... --app brink
```

Note: NEVER commit the actual token to git.

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

---

## Common Mistakes to Avoid

### Docker & Claude CLI

- **Use `bash` for Claude install script** - The native installer uses bash-specific syntax. Use `bash` not `sh`:
  ```dockerfile
  RUN curl -fsSL https://claude.ai/install.sh | bash
  ```

- **Add Claude CLI to PATH** - After installing, add the install location:
  ```dockerfile
  ENV PATH="/root/.local/bin:${PATH}"
  ```

### Testing

- **Scenario IDs are filename stems** - Use underscores, not hyphens. The ID comes from the JSON filename:
  - File: `cuban_missile_crisis.json` → ID: `cuban_missile_crisis`
  - NOT: `cuban-missile-crisis`

- **Module cleanup in tests** - When deleting `sys.modules` entries in tests, ALWAYS save and restore them:
  ```python
  @pytest.fixture(autouse=True)
  def cleanup_modules():
      saved = {k: v for k, v in sys.modules.items() if k.startswith("mypackage")}
      for mod in saved:
          del sys.modules[mod]
      yield
      for mod in list(sys.modules.keys()):
          if mod.startswith("mypackage"):
              del sys.modules[mod]
      sys.modules.update(saved)
  ```

- **Mock webapp Claude check in fixtures** - All webapp test fixtures must mock the Claude check:
  ```python
  with patch("brinksmanship.webapp.app.check_claude_api_credentials", return_value=True):
      from brinksmanship.webapp import create_app
      app = create_app(TestConfig)
  ```

### Startup Checks

- **Use subprocess for CLI verification** - For simple power-on tests, use `subprocess.run()` not async SDK:
  ```python
  result = subprocess.run(["claude", "-p", "test", "--output-format", "text"], ...)
  if result.returncode != 0:
      raise RuntimeError(f"Claude CLI failed: {result.stderr}")
  ```

---

## Critical Process Rules

### Authentication

- **Use Claude Code OAuth, NOT Anthropic API keys** - The project uses `ClaudeSDKClient` with `CLAUDE_CODE_OAUTH_TOKEN`. Never add `ANTHROPIC_API_KEY` references.

### Package Management

- **No npm** - Use native installers for tools. Python packages via `uv` only.

### CI/CD Parity

- **Local CI must match GitHub Actions exactly** - No surprises on push. The push is just a double-check, not a discovery step. Run `scripts/ci.sh` locally before pushing.

### Documentation Consistency

- **Update GAME_MANUAL.md when changing mechanics** - Code and documentation must stay synchronized. Parameters and formulas in GAME_MANUAL.md are the source of truth.

### Balance Tuning

- **Fix mechanics before tuning parameters** - If something seems broken, write unit tests to reproduce the bug first. Only tune parameters if underlying mechanics are confirmed working.
- **Try parameter tuning first** - Before proposing mechanics changes, attempt to solve balance issues with parameter adjustments. Ask the user before making mechanics changes.

### Test Efficiency

- **Tests should be fast** - Be parsimonious with tests. Focus on end-to-end flows, remove redundant coverage.
- **Async Playwright, no static waits** - Use async Playwright and avoid `time.sleep()` or static wait calls.
- **Skip Claude CLI tests in CI** - Tests requiring Claude Code CLI must be conditionally skipped in CI (Docker only has Python packages, not the CLI binary).

### Engine State Persistence

- **Sync surplus fields when recreating engines** - When recreating a `GameEngine` from stored state, surplus fields (`cooperation_surplus`, etc.) must be synchronized from the persisted `GameState`.

### Deterministic Opponents

- **Deterministic opponents need deterministic settlement** - Don't use LLM-based `evaluate_settlement()` for deterministic opponents. Implement rule-based evaluation using game state metrics.
