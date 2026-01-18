# Claude Code Instructions

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
