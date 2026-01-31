# T26: LLM Opponent Conversation History

## Task ID
T26

## Title
Maintain conversation history across turns for LLM-based opponents

## Description
Currently, each LLM call for action selection/settlement evaluation is stateless - fresh context per call. This task adds conversation continuity so LLM opponents can:
- Remember their reasoning from previous turns
- Adapt strategy based on observed opponent patterns
- Build coherent negotiation narratives across settlement attempts

## Blocked By
- None (standalone feature)

## Acceptance Criteria
- [ ] `HistoricalPersona` maintains conversation history across a game session
- [ ] Settlement evaluations reference prior proposals/responses
- [ ] Action choices can reference prior reasoning
- [ ] Unit tests verify history is maintained (not just stored)
- [ ] Manual CLI test confirms LLM references prior context
- [ ] No regression in existing playtest performance

## Files to Modify
- `src/brinksmanship/llm.py` - Add `ConversationalClient` class
- `src/brinksmanship/opponents/historical.py` - Use ConversationalClient
- `scripts/playtest/run_matchup.py` - Ensure fresh client per game

## Files to Add
- `tests/unit/test_llm_conversation.py` - Unit tests for conversation history

---

## Implementation Plan

### BARRIER 1: ConversationalClient Infrastructure
**Tasks:**
1. Create `ConversationalClient` class in `llm.py` that wraps `ClaudeSDKClient`
2. Track message history as list of (role, content) tuples
3. Provide `query()` method that appends to history and returns response
4. Provide `reset()` method to clear history (for new game)

**Verification:**
```bash
uv run pytest tests/unit/test_llm_conversation.py -v
```

**Tests to Add:**
- `test_conversation_history_accumulates`: Verify messages accumulate
- `test_conversation_reset_clears_history`: Verify reset works
- `test_query_includes_prior_context`: Verify prior context sent to LLM

**Commit:** `"Barrier 1: ConversationalClient infrastructure (T26)"`

---

### BARRIER 2: Integrate with HistoricalPersona
**Tasks:**
1. Add `_conversation_client: ConversationalClient | None` to HistoricalPersona
2. Initialize client lazily on first LLM call
3. Modify `choose_action()` to use conversational client
4. Modify `evaluate_settlement()` to use same client
5. Add `reset_conversation()` method for game restart

**Verification:**
```bash
uv run pytest tests/unit/test_historical_persona.py -v -k conversation
```

**Tests to Add:**
- `test_persona_uses_conversation_client`: Verify client is used
- `test_persona_conversation_persists_across_turns`: Multi-turn test
- `test_persona_reset_clears_conversation`: Verify reset between games

**Commit:** `"Barrier 2: HistoricalPersona conversation integration (T26)"`

---

### BARRIER 3: Playtest Integration & Manual Test
**Tasks:**
1. Update `run_matchup.py` to reset conversation between games
2. Add logging to show conversation history length
3. Manual test: Run single game with verbose logging, verify LLM references prior turns

**Manual CLI Test:**
```bash
# Run single game with debug logging
LOG_LEVEL=DEBUG uv run python scripts/playtest/run_matchup.py \
    --scenario cuban_missile_crisis \
    --player-a historical:nixon \
    --player-b historical:khrushchev \
    --games 1 \
    --output /tmp/test_conversation.json

# Inspect logs for conversation history references
grep -i "prior\|previous\|earlier\|history" playtest_work/logs/*.log
```

**Verification:**
```bash
# Run full test suite
uv run pytest tests/ -v --ignore=tests/test_real_llm_integration.py

# Verify no regression in playtest
bash scripts/playtest/driver.sh --parallel 1 --games-per-matchup 1 --scenarios cuban_missile_crisis
```

**Commit:** `"Barrier 3: Playtest integration and manual test (T26)"`

---

## Design Notes

### Why ClaudeSDKClient over query()?
The `query()` function is stateless - each call starts fresh. `ClaudeSDKClient` (used in `generate_and_fix_json`) maintains conversation state via `async with` context.

### Memory Considerations
Conversation history grows linearly with game length (~15 turns typical). Each turn adds ~500-1000 tokens of context. This is manageable but should be monitored.

### Rollback Strategy
If conversation history causes issues (OOM, degraded quality), can be disabled by setting `use_conversation_history=False` on HistoricalPersona.
