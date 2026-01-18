# Claude Code Instructions

## Required Reading

**CRITICAL**: Before starting any task, read `GAME_MANUAL.md` in the project root. This document contains the authoritative game rules and mechanics. All implementation must conform to this specification.

Estimated tokens: ~10,000 tokens (44KB, 6600 words - worth the context cost for correctness)

## Document Hierarchy

**IF YOU FIND A CONTRADICTION BETWEEN DOCUMENTS, FLAG IT LOUDLY** in your response so it can be fixed. However, when proceeding with implementation:

1. **GAME_MANUAL.md** is the authoritative source for all game mechanics, formulas, and numeric parameters
2. **ENGINEERING_DESIGN.md** is secondary - it describes implementation approach but defers to GAME_MANUAL.md for game rules
3. If ENGINEERING_DESIGN.md contradicts GAME_MANUAL.md, follow GAME_MANUAL.md and flag the inconsistency

---

## Code Style

### Imports
- All imports must be at the top of the file
- No inline imports inside functions or methods
- Group imports: stdlib, third-party, local

### Exception Handling
- Do NOT add try/except blocks unless you have a meaningful alternative action
- Let exceptions propagate naturally
- Only catch exceptions when you can actually recover or need to transform the error
- "Log and continue" is not a valid recovery strategy

### General
- Avoid over-engineering
- No defensive programming against impossible states
- Trust internal code; only validate at system boundaries

## Webapp

### htmx
**CRITICAL**: Always use the latest version of htmx. Check https://htmx.org for the current version before downloading or referencing. Do NOT use outdated CDN links or old versions from examples.
