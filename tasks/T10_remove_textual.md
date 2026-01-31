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
- [x] No imports from `textual` package
- [x] `pyproject.toml` removes textual from dependencies
- [x] CLI uses `simple-term-menu` for menus
- [x] CLI uses `readline` for text input
- [x] `uv run brinksmanship` launches without textual

**Note**: CLI completely rewritten from 1800+ line Textual TUI to ~680 line simple-term-menu interface. All core functionality preserved.

## Files to Modify
- `pyproject.toml`
- `src/brinksmanship/cli/app.py`
