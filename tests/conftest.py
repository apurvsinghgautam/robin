import pytest
import os
from unittest.mock import patch


@pytest.fixture(autouse=True)
def mock_env_variables():
    """Mock environment variables for testing."""
    with patch.dict(os.environ, {
        'OPENAI_API_KEY': 'test-openai-key',
        'ANTHROPIC_API_KEY': 'test-anthropic-key',
        'GOOGLE_API_KEY': 'test-google-key'
    }):
        yield


@pytest.fixture
def disable_tor():
    """Disable actual Tor connections during tests."""
    with patch('search.get_tor_proxies') as mock_proxies, \
         patch('scrape.scrape_single') as mock_scrape:
        
        mock_proxies.return_value = {
            "http": "http://localhost:9999",  # Non-existent proxy
            "https": "http://localhost:9999"
        }
        
        # Mock scrape_single to return test data
        mock_scrape.return_value = ("http://test.onion", "Test content")
        
        yield mock_scrape 