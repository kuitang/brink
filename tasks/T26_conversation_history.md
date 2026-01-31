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
- [x] `HistoricalPersona` maintains conversation history across a game session
- [x] Settlement evaluations reference prior proposals/responses
- [x] Action choices can reference prior reasoning
- [x] Unit tests verify history is maintained (not just stored)
- [ ] Manual CLI test confirms LLM references prior context
- [x] No regression in existing playtest performance

## Files to Modify
- `src/brinksmanship/opponents/historical.py` - Hold ClaudeSDKClient instance, reuse across turns

## Files to Add
- `tests/unit/test_llm_conversation.py` - Unit tests for conversation history

---

## Implementation Plan

### Key Insight: Use ClaudeSDKClient Directly

The Claude SDK already tracks conversation history internally. No wrapper class needed:
- `ClaudeSDKClient` maintains message history across calls
- Each `HistoricalPersona` holds its own client instance (lazy initialized)
- Reuse the same client for all turns within a game
- At game end, client is garbage collected when persona is discarded

### BARRIER 1: ClaudeSDKClient Instance in HistoricalPersona
**Tasks:**
1. Add `_client: ClaudeSDKClient | None` attribute to HistoricalPersona
2. Lazy initialize client on first LLM call
3. Reuse same client instance for all subsequent calls in the game

**Code Pattern:**
```python
class HistoricalPersona:
    def __init__(self, ...):
        ...
        self._client: ClaudeSDKClient | None = None

    def _get_client(self) -> ClaudeSDKClient:
        """Lazy initialize and return the client."""
        if self._client is None:
            self._client = ClaudeSDKClient()
        return self._client

    def choose_action(self, state: GameState) -> Action:
        client = self._get_client()
        # Use client.query() - history accumulates automatically
        ...

    def evaluate_settlement(self, state: GameState, proposal: Settlement) -> bool:
        client = self._get_client()
        # Same client, so LLM sees prior reasoning
        ...
```

**Verification:**
```bash
uv run pytest tests/unit/test_llm_conversation.py -v
```

**Tests to Add:**
- `test_persona_reuses_client_across_turns`: Verify same client instance used
- `test_persona_conversation_persists`: Mock client, verify history accumulates

**Commit:** `"Barrier 1: HistoricalPersona holds ClaudeSDKClient instance (T26)"`

---

### BARRIER 2: Playtest Integration & Manual Test
**Tasks:**
1. Verify playtest creates fresh persona (and thus fresh client) per game
2. Add logging to show conversation turn count
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

**Commit:** `"Barrier 2: Playtest integration and manual test (T26)"`

---

## Design Notes

### Why No Wrapper Class?
The original plan called for a `ConversationalClient` wrapper class. This is unnecessary:
- `ClaudeSDKClient` already tracks message history internally
- No need for a `reset()` method - create new client for new game
- Simpler code, fewer abstractions

### Why Not Prompt Prefix Caching?
Prompt prefix caching was considered but rejected:
- Games are ~15 turns - not enough repetition to benefit significantly
- Adds complexity for minimal gain
- SDK handles caching internally where beneficial

### Memory Considerations
Conversation history grows linearly with game length (~15 turns typical). Each turn adds ~500-1000 tokens of context. This is manageable but should be monitored.

### Fresh Client Per Game
The playtest infrastructure creates new persona instances per game, so each game automatically gets a fresh client with empty history. No explicit reset needed.
