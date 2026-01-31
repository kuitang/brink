#!/usr/bin/env python3
"""Visual QA for Theme Testing using Playwright.

Captures screenshots of all 5 themes on key pages for visual quality assurance.

Usage:
    # First start the webapp:
    uv run brinksmanship-web

    # Then run this script:
    uv run python scripts/visual_qa_themes.py

    # Or with Playwright MCP, use browser tools directly

Screenshots are saved to qa_screenshots/ directory.

See GAME_MANUAL.md for theme descriptions.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


async def capture_theme_screenshots(
    base_url: str = "http://localhost:5000",
    output_dir: str = "qa_screenshots",
) -> None:
    """Capture screenshots for all themes on key pages.

    Args:
        base_url: Webapp base URL
        output_dir: Directory to save screenshots
    """
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print("Playwright not installed. Install with: uv pip install playwright")
        print("Then run: playwright install chromium")
        sys.exit(1)

    themes = ["default", "cold-war", "renaissance", "byzantine", "corporate"]
    pages = [
        ("login", "/login"),
        ("register", "/register"),
        ("lobby", "/"),
        ("new_game", "/games/new"),
        ("manual", "/manual"),
    ]

    # Create output directory
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)

    print(f"Capturing screenshots to: {output_path.absolute()}")
    print(f"Themes: {', '.join(themes)}")
    print(f"Pages: {', '.join(p[0] for p in pages)}")
    print()

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        context = await browser.new_context(viewport={"width": 1280, "height": 800})
        page = await context.new_page()

        # First, register and login to access authenticated pages
        print("Setting up test user...")
        await page.goto(f"{base_url}/register")
        await page.fill('input[name="username"]', "qa_test_user")
        await page.fill('input[name="email"]', "qa@test.local")
        await page.fill('input[name="password"]', "testpassword123")
        await page.fill('input[name="password_confirm"]', "testpassword123")

        try:
            await page.click('button[type="submit"]')
            await page.wait_for_load_state("networkidle")
        except Exception:
            # User might already exist, try login instead
            await page.goto(f"{base_url}/login")
            await page.fill('input[name="username"]', "qa_test_user")
            await page.fill('input[name="password"]', "testpassword123")
            await page.click('button[type="submit"]')
            await page.wait_for_load_state("networkidle")

        total_screenshots = len(themes) * len(pages)
        captured = 0

        for theme in themes:
            print(f"\nTheme: {theme}")

            # Set theme via cookie
            await context.add_cookies(
                [
                    {
                        "name": "theme",
                        "value": theme,
                        "domain": "localhost",
                        "path": "/",
                    }
                ]
            )

            for page_name, page_path in pages:
                await page.goto(f"{base_url}{page_path}")
                await page.wait_for_load_state("networkidle")

                # Wait for styles to load
                await asyncio.sleep(0.5)

                # Capture screenshot
                filename = f"{theme}-{page_name}.png"
                filepath = output_path / filename
                await page.screenshot(path=str(filepath), full_page=True)

                captured += 1
                print(f"  [{captured}/{total_screenshots}] {filename}")

        await browser.close()

    print(f"\n{captured} screenshots captured to: {output_path.absolute()}")
    print("\nReview screenshots for:")
    print("  - Text readability (contrast)")
    print("  - Theme colors applied consistently")
    print("  - No broken layouts")
    print("  - Distinct visual identity per theme")


def main() -> None:
    """Run visual QA."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Capture theme screenshots for visual QA",
    )
    parser.add_argument(
        "--url",
        type=str,
        default="http://localhost:5000",
        help="Webapp base URL (default: http://localhost:5000)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="qa_screenshots",
        help="Output directory (default: qa_screenshots)",
    )

    args = parser.parse_args()

    asyncio.run(
        capture_theme_screenshots(
            base_url=args.url,
            output_dir=args.output,
        )
    )


if __name__ == "__main__":
    main()
