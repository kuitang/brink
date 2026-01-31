"""Manual routes - serves the game manual as HTML.

Reads GAME_MANUAL.md directly and converts to HTML on the fly,
eliminating the need for a pre-generation step.
"""

from pathlib import Path

import markdown
from flask import Blueprint, render_template

bp = Blueprint("manual", __name__, url_prefix="/manual")

# Cache for rendered manual content
_manual_cache: dict[str, tuple[str, str, float]] = {}


def _get_manual_path() -> Path:
    """Get path to GAME_MANUAL.md in project root."""
    # Navigate from routes/ -> webapp/ -> brinksmanship/ -> src/ -> project_root/
    return Path(__file__).parent.parent.parent.parent.parent / "GAME_MANUAL.md"


def _render_manual() -> tuple[str, str]:
    """Convert GAME_MANUAL.md to HTML with table of contents.

    Returns:
        Tuple of (html_content, toc_html)
    """
    manual_path = _get_manual_path()

    if not manual_path.exists():
        return (
            "<p class='text-muted'>GAME_MANUAL.md not found.</p>",
            "",
        )

    md_content = manual_path.read_text()

    # Convert to HTML with extensions for tables, fenced code blocks, and TOC
    md = markdown.Markdown(
        extensions=[
            "tables",
            "fenced_code",
            "toc",
            "sane_lists",
        ],
        extension_configs={
            "toc": {
                "title": "Table of Contents",
                "toc_depth": 3,
            },
        },
    )
    html_content = md.convert(md_content)
    toc = md.toc

    return html_content, toc


def _get_cached_manual() -> tuple[str, str]:
    """Get manual content with file-based cache invalidation.

    Returns cached content if GAME_MANUAL.md hasn't been modified,
    otherwise re-renders and updates cache.
    """
    manual_path = _get_manual_path()

    if not manual_path.exists():
        return _render_manual()

    current_mtime = manual_path.stat().st_mtime

    if "manual" in _manual_cache:
        content, toc, cached_mtime = _manual_cache["manual"]
        if cached_mtime == current_mtime:
            return content, toc

    # Cache miss or file modified - re-render
    content, toc = _render_manual()
    _manual_cache["manual"] = (content, toc, current_mtime)
    return content, toc


@bp.route("/")
def index():
    """Render the game manual page."""
    manual_content, toc_content = _get_cached_manual()

    return render_template(
        "pages/manual.html",
        manual_content=manual_content,
        toc_content=toc_content,
    )
