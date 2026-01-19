"""Manual routes - serves the game manual as HTML."""

from pathlib import Path

from flask import Blueprint, render_template

bp = Blueprint("manual", __name__, url_prefix="/manual")


@bp.route("/")
def index():
    """Render the game manual page."""
    # Read the generated HTML content
    generated_dir = Path(__file__).parent.parent / "templates" / "generated"
    content_path = generated_dir / "manual_content.html"
    toc_path = generated_dir / "manual_toc.html"

    if content_path.exists():
        manual_content = content_path.read_text()
    else:
        manual_content = (
            "<p class='text-muted'>Manual not generated yet. "
            "Run <code>uv run python scripts/generate_manual.py</code> to generate.</p>"
        )

    if toc_path.exists():
        toc_content = toc_path.read_text()
    else:
        toc_content = ""

    return render_template(
        "pages/manual.html",
        manual_content=manual_content,
        toc_content=toc_content,
    )
