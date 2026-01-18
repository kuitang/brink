# Brinksmanship: Webapp Engineering Design Document

## Implementation Guide for Claude Code

---

## Overview

This document describes the webapp frontend for Brinksmanship, built with Flask + htmx. It is designed to be developed **in parallel** with the core game engine, starting with mocks that allow rapid iteration on UI/UX.

**Stack:**
- **Backend**: Flask + Jinja2
- **Frontend**: htmx + hand-written CSS
- **Database**: SQLite (via SQLAlchemy)
- **Auth**: Flask-Login + argon2-cffi (RFC 9106 compliant password hashing)
- **Aesthetic**: Kingdom of Loathing-inspired (text-heavy, minimal, lo-fi)

**Design Principle**: Start with mocks. The webapp should be fully navigable and visually complete before the real game engine exists.

---

## Dependency Map: Webapp → Core Engine

| Webapp Milestone | Depends On (Core) | Can Start After |
|------------------|-------------------|-----------------|
| W1: Project Setup | None | Immediately |
| W2: Pages & Routing | None | Immediately |
| W3: Game Interface (htmx) | None (uses mocks) | W1 |
| W4: Auth & Sessions | None | W1 |
| W5: Database Schema | Phase 1.1 (state.py) for schema alignment | W1 |
| W6: Scenario Management | Phase 3.1 (schemas.py) | Phase 3 complete |
| W7: Persona Selection | Phase 4.1-4.3 (opponents/) | Phase 4 complete |
| W8: Integration | Phase 2 (engine) complete | Phase 2 complete |

**Critical Interfaces** (defined in this document):
1. `GameEngineInterface` - contract between webapp and engine
2. `ScenarioRepository` - load/save scenarios (file or SQLite)
3. `OpponentFactory` - create opponent instances by type/persona

---

## Integration with Existing Structure

The webapp integrates with the existing `brinksmanship` package structure:

```
brinksmanship/                      # Project root
├── pyproject.toml                  # Add webapp optional deps
├── CLAUDE.md
├── GAME_MANUAL.md
├── ENGINEERING_DESIGN.md
├── WEBAPP_ENGINEERING_DESIGN.md
├── instance/                       # NEW: SQLite database (gitignored)
│   └── brinksmanship.db
├── scenarios/                      # Existing: scenario JSON files
│   └── *.json
├── scripts/                        # Existing: utility scripts
│   ├── test_argon2.py
│   └── ...
└── src/brinksmanship/
    ├── __init__.py
    ├── llm.py                      # Existing: LLM utilities
    ├── prompts.py                  # Existing: all prompts
    ├── cli/                        # Existing: Textual CLI
    ├── coaching/                   # Existing
    ├── engine/                     # Existing: game engine
    ├── generation/                 # Existing: scenario generation
    ├── models/                     # Existing: game state, matrices, actions
    ├── opponents/                  # Existing: AI opponents
    ├── testing/                    # Existing: playtesting
    ├── storage/                    # NEW: shared storage layer
    │   ├── __init__.py
    │   ├── repository.py           # Abstract interfaces
    │   ├── file_repo.py            # JSON file backend
    │   └── sqlite_repo.py          # SQLite backend
    └── webapp/                     # NEW: Flask webapp
        ├── __init__.py
        ├── app.py                  # Flask app factory
        ├── config.py               # Configuration
        ├── extensions.py           # Flask extensions (db, login)
        ├── models/                 # SQLAlchemy models (webapp-specific)
        │   ├── __init__.py
        │   ├── user.py             # User accounts
        │   ├── game_record.py      # Persisted games
        │   └── scenario.py         # Scenario metadata (for SQLite backend)
        ├── routes/
        │   ├── __init__.py
        │   ├── auth.py             # Login/register/logout
        │   ├── lobby.py            # Game setup, scenario selection
        │   ├── game.py             # Main game routes
        │   ├── scenarios.py        # Scenario management
        │   ├── leaderboard.py      # Leaderboard routes
        │   └── api.py              # htmx endpoints
        ├── services/
        │   ├── __init__.py
        │   ├── game_service.py     # Wraps GameEngine for webapp
        │   ├── mock_engine.py      # Mock engine for development
        │   └── leaderboard.py      # Leaderboard queries
        ├── templates/
        │   ├── base.html
        │   ├── pages/
        │   │   ├── index.html
        │   │   ├── login.html
        │   │   ├── register.html
        │   │   ├── lobby.html
        │   │   ├── new_game.html
        │   │   ├── game.html
        │   │   ├── game_over.html
        │   │   ├── scenarios.html
        │   │   ├── generate_scenario.html
        │   │   ├── leaderboard.html
        │   │   └── leaderboards.html
        │   └── components/
        │       ├── game_board.html
        │       ├── action_menu.html
        │       ├── status_bar.html
        │       ├── narrative.html
        │       ├── history.html
        │       └── opponent_thinking.html
        └── static/
            ├── css/
            │   └── style.css       # Hand-written, KoL-inspired
            └── js/
                └── htmx.min.js     # Only JS dependency
```

### Key Integration Points

| Component | Location | Shared By |
|-----------|----------|-----------|
| Game engine | `engine/` | CLI, webapp |
| Opponents | `opponents/` | CLI, webapp |
| Models (state, matrices) | `models/` | CLI, webapp |
| Storage repositories | `storage/` | CLI, webapp |
| LLM utilities | `llm.py` | CLI, webapp, generation |
| Prompts | `prompts.py` | All LLM-using components |
| User accounts | `webapp/models/user.py` | Webapp only |
| Game records (DB) | `webapp/models/game_record.py` | Webapp only |

### pyproject.toml Updates

```toml
[project.optional-dependencies]
dev = [
    "pytest>=7.0.0",
    "pytest-asyncio>=0.21.0",
    "mypy>=1.0.0",
    "ruff>=0.1.0",
]
webapp = [
    "flask>=3.0.0",
    "flask-login>=0.6.0",
    "flask-sqlalchemy>=3.1.0",
    "argon2-cffi>=23.1.0",
]

[project.scripts]
brinksmanship = "brinksmanship.cli.app:main"
brinksmanship-web = "brinksmanship.webapp.app:main"
```

### Entry Point

**File**: `src/brinksmanship/webapp/app.py`

```python
def main():
    """Entry point for `brinksmanship-web` command."""
    app = create_app()
    app.run(debug=True, port=5000)
```

### Installation

```bash
# Install with webapp dependencies
uv sync --extra webapp

# Or with pip
pip install -e ".[webapp]"

# Run the webapp
brinksmanship-web

# Or with flask directly (for development)
cd src/brinksmanship/webapp
flask run --debug
```

### Imports from Existing Code

The webapp imports from the existing package:

```python
# In webapp/services/game_service.py
from brinksmanship.engine.game_engine import GameEngine
from brinksmanship.engine.interface import GameStateView, Action
from brinksmanship.opponents import get_opponent
from brinksmanship.storage import get_scenario_repo

# In webapp/services/mock_engine.py
from brinksmanship.models.state import ActionType
from brinksmanship.models.actions import Action
```

---

## Phase W1: Project Setup

**Deliverables**: Flask app skeleton, static files, base templates

### Milestone W1.1: Flask App Factory

**File**: `src/brinksmanship/webapp/app.py`

```python
from flask import Flask
from .extensions import db, login_manager
from .config import Config

def create_app(config_class=Config):
    app = Flask(__name__,
                template_folder='templates',
                static_folder='static')
    app.config.from_object(config_class)

    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)

    # Register blueprints
    from .routes import auth, lobby, game, scenarios, leaderboard, api
    app.register_blueprint(auth.bp)
    app.register_blueprint(lobby.bp)
    app.register_blueprint(game.bp)
    app.register_blueprint(scenarios.bp)
    app.register_blueprint(leaderboard.bp)
    app.register_blueprint(api.bp)

    return app
```

### Milestone W1.2: Configuration

**File**: `src/brinksmanship/webapp/config.py`

```python
import os
from pathlib import Path

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-key-change-in-prod')

    # Database
    INSTANCE_PATH = Path(__file__).parent.parent.parent.parent / 'instance'
    SQLALCHEMY_DATABASE_URI = f'sqlite:///{INSTANCE_PATH}/brinksmanship.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Scenarios
    SCENARIOS_PATH = Path(__file__).parent.parent.parent.parent / 'scenarios'
    SCENARIO_STORAGE = 'sqlite'  # 'file' or 'sqlite'

    # Game engine
    USE_MOCK_ENGINE = True  # Set False when real engine is ready

    # LLM
    LLM_TIMEOUT = 60  # seconds to wait for persona responses

class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    USE_MOCK_ENGINE = True
```

### Milestone W1.3: CSS Foundation

**File**: `src/brinksmanship/webapp/static/css/style.css`

**Design Principles** (Kingdom of Loathing inspired):
- Serif fonts for body, monospace for data
- Muted earth-tone palette
- Visible borders, box-based layout
- Dense text, minimal whitespace
- No gradients, no shadows, no rounded corners

**Theming Architecture**:
- All colors defined as CSS custom properties in `:root`
- Components reference variables only (no hardcoded colors)
- Theme switching via class on `<body>` (e.g., `class="theme-crisis"`)
- Theme classes override the CSS variables

**Required CSS Variables**:
```css
:root {
    /* Colors */
    --bg, --bg-alt, --text, --text-muted
    --border, --accent, --link
    --danger, --success
    /* Typography */
    --font-body, --font-mono
}
```

**Component Classes**:
- `.box`, `.box-header` - bordered content containers
- `.btn`, `.btn-action`, `.btn-cooperative`, `.btn-competitive` - buttons
- `.status-bar`, `.status-item` - game state display
- `.narrative` - briefing text
- `.history`, `.history-turn` - turn history
- `.thinking` - opponent thinking indicator (with CSS animation)
- `.flash`, `.flash-error`, `.flash-success` - messages

**htmx Integration**:
- `.htmx-indicator` - hidden by default, shown during request
- `.htmx-request .hide-on-request` - hidden during request

**Acceptance Criteria**:
- [ ] All colors use CSS variables (no hardcoded values)
- [ ] Theme can be switched by changing body class
- [ ] Flask app starts with `flask run`
- [ ] Static CSS loads correctly

---

## Phase W2: Core Pages & Routing

**Depends on**: W1 complete

### Milestone W2.1: Base Template

**File**: `src/brinksmanship/webapp/templates/base.html`

**Structure**:
- `<head>`: Load CSS, htmx.min.js (deferred)
- `<body class="theme-{{ theme }}">`: Theme class for styling
- `<header>`: Nav with auth-aware links (Games, Scenarios, Leaderboards, Login/Logout)
- `<main>`: Flash messages + `{% block content %}`
- `<footer>`: Minimal

**Template Blocks**:
- `{% block title %}` - page title
- `{% block content %}` - main content

### Milestone W2.2: Auth Routes

**File**: `src/brinksmanship/webapp/routes/auth.py`

**Routes**:
- `GET/POST /auth/login` - login form and handler
- `GET/POST /auth/register` - registration form and handler
- `GET /auth/logout` - logout (requires login)

**Password Hashing**: argon2-cffi with RFC 9106 LOW_MEMORY defaults
- Hash on registration: `ph.hash(password)`
- Verify on login: `ph.verify(stored_hash, password)`
- Auto-rehash if parameters changed: `ph.check_needs_rehash()`

**Security Requirements**:
- Same error message for invalid user vs invalid password (prevent enumeration)
- Minimum password length: 8 characters
- Redirect authenticated users away from login/register pages

### Milestone W2.3: Page Templates

**Files**: `src/brinksmanship/webapp/templates/pages/`

Each page extends base.html. Lobby shows:
- New Game button
- List of in-progress games
- List of completed games

**Acceptance Criteria**:
- [ ] User can register, login, logout
- [ ] Auth state persists across requests
- [ ] Protected routes redirect to login
- [ ] Flash messages display correctly

---

## Phase W3: Game Interface (htmx)

**Depends on**: W2 complete, Mock Engine (W3.1)

This is the core gameplay loop. Built entirely against mock data first.

### Milestone W3.1: Mock Engine

**File**: `src/brinksmanship/webapp/services/mock_engine.py`

**Purpose**: Minimal `GameEngineInterface` implementation with canned/random data. Allows full UI development before real engine exists.

**Implements**:
- `create_game(scenario_id, opponent_type, user_id) -> GameState`
- `get_game(game_id) -> GameState`
- `get_available_actions(game_id) -> list[Action]`
- `submit_action(game_id, action_id) -> GameState` (with simulated delay)
- `get_opponent_types() -> list[dict]`

**Behavior**:
- Random opponent choice (cooperative/competitive)
- Simulated 2s "thinking" delay
- Basic state updates (position, resources, risk, cooperation)
- Game end detection (turn limit, risk=10, position=0, resources=0)
- Canned briefing and outcome narratives

### Milestone W3.2: Game Service

**File**: `src/brinksmanship/webapp/services/game_service.py`

**Purpose**: Thin wrapper that delegates to mock or real engine based on `USE_MOCK_ENGINE` config.

**Functions**: `create_game`, `get_game`, `get_available_actions`, `submit_action`, `get_opponent_types`

### Milestone W3.3: Game Routes

**File**: `src/brinksmanship/webapp/routes/game.py`

**Routes**:
- `GET /game/<game_id>` - main game page (redirects to game_over if finished)
- `POST /game/<game_id>/action` - submit action (htmx partial or redirect)
- `GET /game/<game_id>/over` - game over screen

**htmx Handling**:
- Check `HX-Request` header
- Return component partial for htmx, redirect for regular requests
- Use `HX-Redirect` header when game ends during htmx request

### Milestone W3.4: Game Templates

**Page Template**: `pages/game.html`
- Extends base.html
- Contains `<div id="game-board">` as htmx swap target
- Includes `components/game_board.html`

**Component Templates** (all in `components/`):

| Component | Purpose | Data |
|-----------|---------|------|
| `game_board.html` | Main container, returned by htmx | state, actions |
| `status_bar.html` | Turn, Position, Resources, Risk, Cooperation, Stability | state |
| `narrative.html` | Briefing + last outcome | state.briefing, state.last_outcome |
| `action_menu.html` | Action buttons with htmx form | actions |
| `history.html` | Turn history (T1:CC, T2:CD, ...) | state.history |
| `opponent_thinking.html` | Loading indicator | (none) |

**htmx Pattern** (in action_menu.html):
```html
<form hx-post="/game/{id}/action"
      hx-target="#game-board"
      hx-swap="innerHTML"
      hx-indicator="#thinking">
    <!-- buttons hidden during request -->
    <div class="hide-on-request">...</div>
    <!-- shown during request -->
    <div id="thinking" class="htmx-indicator">...</div>
</form>
```

**Acceptance Criteria**:
- [ ] Game page renders with all components
- [ ] Clicking action shows "opponent thinking" indicator
- [ ] After opponent "responds", board updates without page refresh
- [ ] Game over redirects correctly
- [ ] History accumulates across turns
- [ ] Status bar shows all state variables

---

## Phase W4: Database & Persistence

**Depends on**: W2 complete, Core Phase 1.1 (state.py) for schema alignment

### Milestone W4.1: Database Models

**User** (`webapp/models/user.py`):
| Column | Type | Notes |
|--------|------|-------|
| id | Integer | PK |
| username | String(64) | unique, indexed |
| password_hash | String(256) | argon2id hash |
| created_at | DateTime | |

**GameRecord** (`webapp/models/game_record.py`):
| Column | Type | Notes |
|--------|------|-------|
| id | Integer | PK |
| game_id | String(64) | unique, indexed |
| user_id | Integer | FK → users.id |
| scenario_id | String(64) | |
| opponent_type | String(64) | |
| state_json | Text | Full game state as JSON |
| is_finished | Boolean | |
| ending_type | String(32) | nullable |
| final_vp_player | Integer | nullable |
| final_vp_opponent | Integer | nullable |
| created_at, updated_at, finished_at | DateTime | |

**Property**: `state` getter/setter for JSON serialization

### Milestone W4.2: Scenario Storage (Shared Infrastructure)

**Location**: `src/brinksmanship/storage/`

**Interface** (`repository.py`):
```python
class ScenarioRepository(ABC):
    def list_scenarios(self) -> list[dict]: ...      # Returns {id, name, setting, max_turns}
    def get_scenario(self, scenario_id: str) -> Optional[dict]: ...
    def get_scenario_by_name(self, name: str) -> Optional[dict]: ...  # Case-insensitive
    def save_scenario(self, scenario: dict) -> str: ...  # Returns ID (slugified name)
    def delete_scenario(self, scenario_id: str) -> bool: ...
```

**Implementations**:
- `FileScenarioRepository` - JSON files in `scenarios/` directory, filename = `{slug}.json`
- `SQLiteScenarioRepository` - Uses webapp's SQLAlchemy session

**Utility**: `slugify(name)` converts "Cuban Missile Crisis" → "cuban-missile-crisis"

**Acceptance Criteria**:
- [ ] User records persist across server restarts
- [ ] Game records save complete state as JSON
- [ ] Games can be listed by user
- [ ] Scenarios accessible via repository interface
- [ ] Repository implementation switchable via config

---

## Phase W5: Lobby & Game Setup

**Depends on**: W4 complete

### Milestone W5.1: Lobby Routes

**File**: `src/brinksmanship/webapp/routes/lobby.py`

**Routes**:
- `GET /` - Main lobby (requires login)
  - Shows active games (sorted by updated_at desc)
  - Shows recent finished games (limit 10)
- `GET/POST /new` - New game setup
  - Lists scenarios from repository
  - Lists opponent types from game service
  - On POST: creates game, persists GameRecord, redirects to play

### Milestone W5.2: Lobby Templates

**Pages**:
- `lobby.html` - Two-column layout: active games + finished games, "Start New Game" button
- `new_game.html` - Scenario dropdown, opponent selection (algorithmic + personas + custom)

**Acceptance Criteria**:
- [ ] Lobby shows active and completed games
- [ ] New game flow: select scenario → select opponent → start
- [ ] Game records persist to database
- [ ] Can resume in-progress games

### Milestone W5.3: Leaderboards

**Design**: Leaderboards keyed by `(scenario_id, opponent_type)`. Public, all attempts shown.

**Ranking**: VP descending, then finished_at ascending (earlier wins ties)

**Service** (`services/leaderboard.py`):
- `get_leaderboard(scenario_id, opponent_type, limit=50)` → list of {rank, username, vp, turns, ending_type, finished_at}
- `get_available_leaderboards()` → list of {scenario_id, opponent_type, game_count}

**Routes** (`routes/leaderboard.py`):
- `GET /leaderboard/` - index of all scenario/opponent pairs with games
- `GET /leaderboard/<scenario_id>/<opponent_type>` - specific leaderboard

**Templates**:
- `leaderboards.html` - table of available leaderboards
- `leaderboard.html` - ranked entries, current user highlighted

**Nav Update** (in base.html):
```jinja2
| <a href="{{ url_for('leaderboard.index') }}">Leaderboards</a>
```

**Acceptance Criteria**:
- [ ] Leaderboard index shows all (scenario, opponent) pairs with games
- [ ] Individual leaderboard shows all attempts ranked by VP, then timestamp
- [ ] Current user's entries highlighted
- [ ] Leaderboard accessible without login (public)
- [ ] Links from game over screen to relevant leaderboard

---

## Phase W6: Scenario Management UI

**Depends on**: W5 complete, Core Phase 3 (scenario generation)

### Milestone W6.1: Scenario List & Generation

**Routes** (`routes/scenarios.py`):
- `GET /scenarios/` - list all scenarios from repository
- `GET /scenarios/<id>` - view scenario details
- `GET/POST /scenarios/generate` - generate new scenario via LLM

**Built-in Themes** (for generation):
- Cold War, Corporate Governance, Ancient History, Palace Intrigue

**Acceptance Criteria**:
- [ ] Scenario list page shows all available scenarios
- [ ] Generate page has theme selection + custom prompt field
- [ ] Scenario detail page shows structure (turns, game types used)
- [ ] Generation integrates with Core Phase 3 when available

---

## Phase W7: Persona Selection & Custom Personas

**Depends on**: W5 complete, Core Phase 4 (opponents)

### Milestone W7.1: Persona UI in Game Setup

**Opponent Selection** (in new_game.html):
1. **Algorithmic Opponents** - deterministic strategies (Nash, Tit-for-Tat, etc.)
2. **Historical Personas** - LLM-powered (Bismarck, Khrushchev, etc.)
3. **Custom Persona** - user describes character, passed to persona research agent

**UI Behavior**: Custom persona textarea shown only when "Custom Persona" selected (JS toggle)

**Acceptance Criteria**:
- [ ] All built-in personas visible with descriptions
- [ ] Custom persona text field appears when selected
- [ ] Custom persona prompts passed to persona research agent
- [ ] Persona selection persisted with game record

---

## Phase W8: Integration with Real Engine

**Depends on**: Core Phase 2 (engine) complete

### Milestone W8.1: Engine Interface Contract

**File**: `src/brinksmanship/engine/interface.py`

**Types**:
- `ActionType` enum: COOPERATIVE, COMPETITIVE
- `Action` dataclass: id, name, action_type, resource_cost, description
- `GameStateView` dataclass: read-only view for webapp (see fields in mock engine)

**Interface** (`GameEngineInterface`):
```python
def create_game(scenario_id, opponent_type, user_id) -> GameStateView
def get_game(game_id) -> Optional[GameStateView]
def get_available_actions(game_id) -> list[Action]
def submit_action(game_id, action_id) -> GameStateView  # May block for LLM
def get_opponent_types() -> list[dict]
```

### Milestone W8.2: Engine Adapter

**File**: `src/brinksmanship/webapp/services/engine_adapter.py`

**Purpose**: Wraps real `GameEngine` to implement `GameEngineInterface`
- Converts internal engine state → `GameStateView`
- Adds noise to opponent observations (±2, per GAME_MANUAL.md)

**Acceptance Criteria**:
- [ ] Config switch (`USE_MOCK_ENGINE`) toggles between mock and real
- [ ] Real engine passes all webapp integration tests
- [ ] LLM opponent "thinking" time handled gracefully
- [ ] Game state serialization matches between engine and webapp

---

## Implementation Order

| Week | Milestones | Deliverables |
|------|------------|--------------|
| 1 | W1, W2.1-W2.2 | Flask skeleton, CSS, base templates, auth |
| 1 | W3.1-W3.2 | Mock engine, game service abstraction |
| 2 | W3.3-W3.4 | Game routes, all game templates, htmx integration |
| 2 | W4.1-W4.2 | Database models, scenario repository |
| 3 | W5.1-W5.2 | Lobby routes and templates |
| 3 | W6.1 | Scenario management UI |
| 4 | W7.1 | Persona selection UI |
| 4+ | W8.1-W8.2 | Integration with real engine (after Core Phase 2) |

---

## Testing Strategy

### Unit Tests
- Route handlers return correct templates
- Mock engine state transitions
- Repository CRUD operations
- Auth flows

### Integration Tests
- Full game flow with mock engine
- Database persistence round-trip
- htmx partial updates

### Manual Testing Checklist
- [ ] Register → Login → Logout flow
- [ ] Create game → Play turns → Game over
- [ ] "Opponent thinking" indicator appears/disappears
- [ ] History accumulates correctly
- [ ] Game state persists across page refresh
- [ ] Resume in-progress game
- [ ] Mobile viewport renders acceptably

---

## Dependencies

See **pyproject.toml Updates** in the Integration section above.

```bash
# Install webapp dependencies
uv sync --extra webapp
```

**Notes**:
- htmx is included as a static file (`webapp/static/js/htmx.min.js`), not a Python dependency
- `argon2-cffi` uses RFC 9106 LOW_MEMORY profile by default (64 MiB, t=3, p=4)
- `flask-sqlalchemy` provides the SQLAlchemy integration for webapp-specific models

---

*Document Version: 1.0*
*Last Updated: January 2026*
