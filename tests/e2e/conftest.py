"""Pytest fixtures for end-to-end Playwright tests.

Uses ASYNC Playwright for better performance and no static waits.
All tests should use dynamic element searches (wait_for_selector, expect).
"""

import pytest
import pytest_asyncio
from playwright.async_api import async_playwright, Page, Browser


@pytest.fixture(scope="session")
def event_loop_policy():
    """Use default event loop policy."""
    import asyncio
    return asyncio.DefaultEventLoopPolicy()


@pytest_asyncio.fixture(scope="session")
async def browser():
    """Launch browser once per test session."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        yield browser
        await browser.close()


@pytest_asyncio.fixture
async def page(browser: Browser) -> Page:
    """Create a new page for each test."""
    context = await browser.new_context(viewport={"width": 1280, "height": 720})
    page = await context.new_page()
    yield page
    await page.close()
    await context.close()


@pytest_asyncio.fixture
async def authenticated_page(page: Page) -> Page:
    """Page with a logged-in test user.

    To be implemented when auth tests are added.
    """
    # TODO: Implement login flow
    # await page.goto("http://localhost:5000/auth/login")
    # await page.fill("[name=username]", "testuser")
    # await page.fill("[name=password]", "testpass")
    # await page.click("button[type=submit]")
    # await page.wait_for_url("**/")
    yield page
