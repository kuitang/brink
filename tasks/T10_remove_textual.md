# T10: Remove Textual Dependency

## Task ID
T10

## Title
Remove Textual library dependency from CLI

## Description
Replace any Textual-based CLI code with simple-term-menu. The CLI should use readline for input and simple-term-menu for menus.

## Blocked By
- T01 (Delete obsolete docs)

## Acceptance Criteria
- [ ] No imports from `textual` package
- [ ] `pyproject.toml` removes textual from dependencies
- [ ] CLI uses `simple-term-menu` for menus
- [ ] CLI uses `readline` for text input
- [ ] `uv run brinksmanship` launches without textual

## Files to Modify
- `pyproject.toml`
- `src/brinksmanship/cli/app.py`
