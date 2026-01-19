#!/usr/bin/env python3
"""Generate HTML from GAME_MANUAL.md for the webapp.

This script converts the game manual markdown to HTML that can be
served by the webapp while maintaining the site's styling.

Usage:
    uv run python scripts/generate_manual.py

The generated file is gitignored and should be regenerated when
GAME_MANUAL.md changes.
"""

from pathlib import Path

import markdown


def generate_manual() -> None:
    """Convert GAME_MANUAL.md to HTML template."""
    project_root = Path(__file__).parent.parent
    manual_path = project_root / "GAME_MANUAL.md"
    output_dir = project_root / "src" / "brinksmanship" / "webapp" / "templates" / "generated"
    output_path = output_dir / "manual_content.html"

    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)

    # Read markdown
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

    # Get the table of contents
    toc = md.toc

    # Write the HTML content (just the body content, not a full HTML doc)
    output_path.write_text(html_content)

    # Also write a separate TOC file for potential sidebar use
    toc_path = output_dir / "manual_toc.html"
    toc_path.write_text(toc)

    print(f"Generated: {output_path}")
    print(f"Generated: {toc_path}")


if __name__ == "__main__":
    generate_manual()
