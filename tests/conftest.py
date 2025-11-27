"""Pytest configuration and fixtures for Robin tests."""

import os
import sys
import pytest

# Add the parent directory to the path so we can import the modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture(autouse=True)
def reset_constants_env(monkeypatch):
    """Reset environment variables before each test."""
    # Store original values
    env_vars = [
        "TOR_PROXY_HOST",
        "TOR_PROXY_PORT",
        "TOR_CONTROL_PORT",
        "ROBIN_SEARCH_TIMEOUT",
        "ROBIN_SCRAPE_TIMEOUT",
        "ROBIN_CLEARWEB_TIMEOUT",
        "ROBIN_MAX_SCRAPE_CHARS",
        "ROBIN_MAX_WORKERS",
    ]

    # Remove any test environment variables after test
    yield

    # Reimport constants to reset state
    import importlib
    import constants
    importlib.reload(constants)


@pytest.fixture
def sample_search_results():
    """Sample search results for testing."""
    return [
        {"title": "Dark Market Forum", "link": "http://darkmarket.onion/forum"},
        {"title": "Security Research", "link": "http://security.onion/research"},
        {"title": "Threat Intel", "link": "http://threatintel.onion/data"},
    ]


@pytest.fixture
def sample_scraped_content():
    """Sample scraped content for testing."""
    return {
        "http://darkmarket.onion/forum": "Dark Market Forum - This is a forum discussing...",
        "http://security.onion/research": "Security Research - Latest vulnerabilities...",
    }


@pytest.fixture
def mock_html_response():
    """Sample HTML response for testing."""
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Test Page</title>
        <script>console.log("test");</script>
        <style>body { color: black; }</style>
    </head>
    <body>
        <h1>Test Heading</h1>
        <p>This is test content for scraping.</p>
        <a href="http://example.onion/page1">Link 1</a>
        <a href="http://another.onion/page2">Link 2</a>
    </body>
    </html>
    '''
