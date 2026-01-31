#!/usr/bin/env python3
"""Simple documentation browser for markdown files."""

import re
from pathlib import Path

from flask import Flask, render_template_string
from markdown import markdown

app = Flask(__name__)

# Project root
ROOT = Path(__file__).parent

# Files to show (in order)
DOC_FILES = [
    ("GAME_MANUAL.md", "Game Manual"),
    ("ENGINEERING_DESIGN.md", "Engineering Design"),
    ("CLAUDE.md", "Claude Instructions"),
    ("README.md", "README"),
    ("WEBAPP_ENGINEERING_DESIGN.md", "Webapp Design"),
]

TASK_DIR = ROOT / "tasks"

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ title }} - Doc Browser</title>
    <script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
    <style>
        :root {
            --bg: #1a1a2e;
            --bg-secondary: #16213e;
            --text: #e8e8e8;
            --text-muted: #a0a0a0;
            --accent: #e94560;
            --accent-hover: #ff6b6b;
            --link: #4fc3f7;
            --link-hover: #81d4fa;
            --border: #2a2a4a;
            --code-bg: #0f0f1a;
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }

        body {
            font-family: Georgia, 'Times New Roman', serif;
            background: var(--bg);
            color: var(--text);
            line-height: 1.7;
            display: flex;
            min-height: 100vh;
        }

        /* Sidebar */
        .sidebar {
            width: 280px;
            background: var(--bg-secondary);
            border-right: 1px solid var(--border);
            padding: 20px;
            position: fixed;
            height: 100vh;
            overflow-y: auto;
        }

        .sidebar h2 {
            font-size: 1.1rem;
            color: var(--accent);
            margin-bottom: 15px;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            text-transform: uppercase;
            letter-spacing: 1px;
        }

        .sidebar ul {
            list-style: none;
        }

        .sidebar li {
            margin: 5px 0;
        }

        .sidebar a {
            color: var(--text-muted);
            text-decoration: none;
            font-size: 0.95rem;
            display: block;
            padding: 8px 12px;
            border-radius: 6px;
            transition: all 0.2s;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
        }

        .sidebar a:hover {
            background: var(--border);
            color: var(--text);
        }

        .sidebar a.active {
            background: var(--accent);
            color: white;
        }

        .sidebar .section-divider {
            border-top: 1px solid var(--border);
            margin: 20px 0;
        }

        /* Main content */
        .main {
            margin-left: 280px;
            flex: 1;
            padding: 40px 60px;
            max-width: 900px;
        }

        .main h1 {
            font-size: 2.2rem;
            margin-bottom: 30px;
            color: var(--accent);
            border-bottom: 2px solid var(--border);
            padding-bottom: 15px;
        }

        .main h2 {
            font-size: 1.6rem;
            margin: 35px 0 20px;
            color: var(--text);
        }

        .main h3 {
            font-size: 1.3rem;
            margin: 25px 0 15px;
            color: var(--text-muted);
        }

        .main p {
            margin: 15px 0;
        }

        .main a {
            color: var(--link);
            text-decoration: none;
        }

        .main a:hover {
            color: var(--link-hover);
            text-decoration: underline;
        }

        .main ul, .main ol {
            margin: 15px 0 15px 25px;
        }

        .main li {
            margin: 8px 0;
        }

        .main code {
            background: var(--code-bg);
            padding: 2px 6px;
            border-radius: 4px;
            font-family: 'SF Mono', Monaco, 'Courier New', monospace;
            font-size: 0.9em;
        }

        .main pre {
            background: var(--code-bg);
            padding: 20px;
            border-radius: 8px;
            overflow-x: auto;
            margin: 20px 0;
            border: 1px solid var(--border);
        }

        .main pre code {
            background: none;
            padding: 0;
        }

        .main blockquote {
            border-left: 4px solid var(--accent);
            padding-left: 20px;
            margin: 20px 0;
            color: var(--text-muted);
            font-style: italic;
        }

        .main table {
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }

        .main th, .main td {
            border: 1px solid var(--border);
            padding: 12px;
            text-align: left;
        }

        .main th {
            background: var(--bg-secondary);
            color: var(--accent);
        }

        .main tr:nth-child(even) {
            background: rgba(255,255,255,0.02);
        }

        /* Mermaid diagrams */
        .mermaid {
            background: var(--bg-secondary);
            padding: 20px;
            border-radius: 8px;
            margin: 20px 0;
        }

        /* Task status badges */
        .status-done {
            color: #4caf50;
        }

        .status-pending {
            color: #ff9800;
        }

        /* DAG clickable nodes */
        .mermaid .node rect, .mermaid .node circle, .mermaid .node ellipse, .mermaid .node polygon {
            cursor: pointer;
        }

        /* Scrollbar */
        ::-webkit-scrollbar {
            width: 8px;
            height: 8px;
        }

        ::-webkit-scrollbar-track {
            background: var(--bg);
        }

        ::-webkit-scrollbar-thumb {
            background: var(--border);
            border-radius: 4px;
        }

        ::-webkit-scrollbar-thumb:hover {
            background: var(--text-muted);
        }
    </style>
</head>
<body>
    <nav class="sidebar">
        <h2>Documentation</h2>
        <ul>
        {% for file, name in docs %}
            <li><a href="/doc/{{ file }}"
                {% if current == file %}class="active"{% endif %}>{{ name }}</a></li>
        {% endfor %}
        </ul>

        <div class="section-divider"></div>

        <h2>Tasks</h2>
        <ul>
            <li><a href="/doc/tasks/INDEX.md"
                {% if current == 'tasks/INDEX.md' %}class="active"{% endif %}
                >Task Index (DAG)</a></li>
        {% for task in tasks %}
            <li><a href="/doc/tasks/{{ task }}"
                {% if current == 'tasks/' + task %}class="active"{% endif %}
                >{{ task[:-3] }}</a></li>
        {% endfor %}
        </ul>
    </nav>

    <main class="main">
        <article>{{ content | safe }}</article>
    </main>

    <script>
        mermaid.initialize({
            startOnLoad: true,
            theme: 'dark',
            themeVariables: {
                primaryColor: '#e94560',
                primaryTextColor: '#e8e8e8',
                primaryBorderColor: '#2a2a4a',
                lineColor: '#4fc3f7',
                secondaryColor: '#16213e',
                tertiaryColor: '#1a1a2e'
            }
        });

        // Make DAG nodes clickable
        document.addEventListener('DOMContentLoaded', function() {
            setTimeout(function() {
                document.querySelectorAll('.mermaid .node').forEach(function(node) {
                    node.style.cursor = 'pointer';
                    node.addEventListener('click', function() {
                        var text = node.textContent || node.innerText;
                        var match = text.match(/T(\\d+)/);
                        if (match) {
                            var taskNum = match[1].padStart(2, '0');
                            // Find the task file
                            var links = document.querySelectorAll('.sidebar a');
                            for (var i = 0; i < links.length; i++) {
                                if (links[i].href.includes('T' + taskNum)) {
                                    window.location = links[i].href;
                                    break;
                                }
                            }
                        }
                    });
                });
            }, 1000);
        });
    </script>
</body>
</html>
"""


def convert_ascii_dag_to_mermaid(content: str) -> str:
    """Convert ASCII DAG in INDEX.md to Mermaid diagram."""
    # Check if this is the INDEX.md with the DAG
    if "Implementation DAG" not in content:
        return content

    # Define the DAG structure based on the task dependencies
    mermaid_dag = """
```mermaid
graph TD
    T01[T01: Delete Docs]
    T02[T02: GameState Surplus]
    T03[T03: CLAUDE.md Cleanup]
    T04[T04: Remove Textual]
    T05[T05: State Deltas]
    T06[T06: CLI Scaffolding]
    T07[T07: Engine Surplus]
    T08[T08: Variance/VP]
    T09[T09: CLI Game Loop]
    T10[T10: Settlement]
    T11[T11: Scenario Schema]
    T12[T12: CLI Settlement]
    T13[T13: Update Scenarios]
    T14[T14: Balance Metrics]
    T15[T15: CLI Scorecard]
    T16[T16: Webapp Surplus]
    T17[T17: CSS Themes]
    T18[T18: Theme UI]
    T19[T19: Webapp Scorecard]
    T20[T20: Game Manual]
    T21[T21: E2E Tests]
    T22[T22: Visual QA]

    T01 --> T02
    T01 --> T03
    T01 --> T04
    T02 --> T05
    T04 --> T06
    T05 --> T07
    T07 --> T08
    T06 --> T09
    T07 --> T09
    T08 --> T10
    T10 --> T11
    T09 --> T12
    T10 --> T12
    T11 --> T13
    T10 --> T14
    T12 --> T15
    T14 --> T15
    T10 --> T16
    T16 --> T17
    T16 --> T18
    T17 --> T18
    T16 --> T19
    T14 --> T19
    T14 --> T20
    T13 --> T21
    T14 --> T21
    T15 --> T21
    T17 --> T22
    T18 --> T22
    T19 --> T22

    style T01 fill:#4caf50
    style T02 fill:#4caf50
    style T03 fill:#4caf50
    style T04 fill:#4caf50
    style T05 fill:#4caf50
    style T06 fill:#4caf50
    style T07 fill:#4caf50
    style T08 fill:#4caf50
    style T09 fill:#4caf50
    style T10 fill:#4caf50
    style T11 fill:#4caf50
    style T12 fill:#4caf50
    style T13 fill:#4caf50
    style T14 fill:#4caf50
    style T15 fill:#4caf50
    style T16 fill:#4caf50
    style T17 fill:#4caf50
    style T18 fill:#4caf50
    style T19 fill:#4caf50
    style T20 fill:#4caf50
    style T21 fill:#4caf50
    style T22 fill:#4caf50

    click T01 "/doc/tasks/T01_delete_obsolete_docs.md"
    click T02 "/doc/tasks/T02_gamestate_surplus.md"
    click T03 "/doc/tasks/T03_cleanup_claude_md.md"
    click T04 "/doc/tasks/T04_remove_textual_deps.md"
    click T05 "/doc/tasks/T05_state_deltas_surplus.md"
    click T06 "/doc/tasks/T06_cli_scaffolding.md"
    click T07 "/doc/tasks/T07_engine_surplus_logic.md"
    click T08 "/doc/tasks/T08_variance_vp_calculation.md"
    click T09 "/doc/tasks/T09_cli_game_loop.md"
    click T10 "/doc/tasks/T10_settlement_surplus.md"
    click T11 "/doc/tasks/T11_scenario_schema_theme.md"
    click T12 "/doc/tasks/T12_cli_settlement_ui.md"
    click T13 "/doc/tasks/T13_update_scenarios.md"
    click T14 "/doc/tasks/T14_balance_dual_metrics.md"
    click T15 "/doc/tasks/T15_cli_scorecard.md"
    click T16 "/doc/tasks/T16_webapp_surplus_display.md"
    click T17 "/doc/tasks/T17_css_era_themes.md"
    click T18 "/doc/tasks/T18_theme_selection_ui.md"
    click T19 "/doc/tasks/T19_webapp_scorecard.md"
    click T20 "/doc/tasks/T20_game_manual_rewrite.md"
    click T21 "/doc/tasks/T21_e2e_balance_test.md"
    click T22 "/doc/tasks/T22_visual_qa_themes.md"
```
"""

    # Replace ASCII DAG with Mermaid
    # Find the ASCII art block and replace it
    pattern = r"```\n\s+┌─────────────────┐.*?└─────────────────┘\n```"
    content = re.sub(pattern, mermaid_dag, content, flags=re.DOTALL)

    return content


def render_markdown(content: str) -> str:
    """Render markdown to HTML."""

    # Handle mermaid blocks specially
    def mermaid_replacer(match):
        return f'<div class="mermaid">{match.group(1)}</div>'

    content = re.sub(r"```mermaid\n(.*?)```", mermaid_replacer, content, flags=re.DOTALL)

    # Render markdown
    html = markdown(content, extensions=["tables", "fenced_code", "codehilite", "toc"])

    return html


def get_tasks():
    """Get sorted list of task files."""
    if not TASK_DIR.exists():
        return []
    tasks = [f.name for f in TASK_DIR.glob("T*.md")]
    return sorted(tasks)


@app.route("/")
def index():
    """Redirect to first doc."""
    return render_doc("GAME_MANUAL.md")


@app.route("/doc/<path:filename>")
def render_doc(filename):
    """Render a markdown document."""
    filepath = ROOT / filename

    if not filepath.exists():
        return f"File not found: {filename}", 404

    content = filepath.read_text()

    # Convert ASCII DAG to Mermaid for INDEX.md
    if "INDEX.md" in filename:
        content = convert_ascii_dag_to_mermaid(content)

    html_content = render_markdown(content)

    return render_template_string(
        HTML_TEMPLATE, title=filepath.stem, content=html_content, docs=DOC_FILES, tasks=get_tasks(), current=filename
    )


def main():
    """Run the doc browser."""
    port = 5001
    print(f"\n📚 Doc Browser running at http://0.0.0.0:{port}\n")
    print("Documents:")
    for file, name in DOC_FILES:
        print(f"  - {name}: http://localhost:{port}/doc/{file}")
    print(f"\nTasks: http://localhost:{port}/doc/tasks/INDEX.md\n")

    app.run(host="0.0.0.0", port=port, debug=False)


if __name__ == "__main__":
    main()
