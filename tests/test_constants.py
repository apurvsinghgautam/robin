"""Tests for the constants module."""

import os
import pytest


class TestTorConfiguration:
    """Tests for Tor proxy configuration."""

    def test_get_tor_proxies_default(self):
        """Test default Tor proxy configuration."""
        from constants import get_tor_proxies

        proxies = get_tor_proxies()

        assert "http" in proxies
        assert "https" in proxies
        assert "socks5h://" in proxies["http"]
        assert "socks5h://" in proxies["https"]

    def test_get_tor_proxies_custom_host(self, monkeypatch):
        """Test Tor proxy with custom host."""
        monkeypatch.setenv("TOR_PROXY_HOST", "192.168.1.100")

        # Need to reimport to pick up new env var
        import importlib
        import constants
        importlib.reload(constants)

        proxies = constants.get_tor_proxies()
        assert "192.168.1.100" in proxies["http"]

    def test_get_tor_proxies_custom_port(self, monkeypatch):
        """Test Tor proxy with custom port."""
        monkeypatch.setenv("TOR_PROXY_PORT", "9150")

        import importlib
        import constants
        importlib.reload(constants)

        proxies = constants.get_tor_proxies()
        assert "9150" in proxies["http"]


class TestUserAgents:
    """Tests for user agent configuration."""

    def test_user_agents_not_empty(self):
        """Test that user agents list is not empty."""
        from constants import USER_AGENTS

        assert len(USER_AGENTS) > 0

    def test_user_agents_are_strings(self):
        """Test that all user agents are strings."""
        from constants import USER_AGENTS

        for ua in USER_AGENTS:
            assert isinstance(ua, str)
            assert len(ua) > 0


class TestSearchEngineEndpoints:
    """Tests for search engine endpoints configuration."""

    def test_endpoints_not_empty(self):
        """Test that endpoints list is not empty."""
        from constants import SEARCH_ENGINE_ENDPOINTS

        assert len(SEARCH_ENGINE_ENDPOINTS) > 0

    def test_endpoints_are_onion_urls(self):
        """Test that all endpoints are .onion URLs."""
        from constants import SEARCH_ENGINE_ENDPOINTS

        for endpoint in SEARCH_ENGINE_ENDPOINTS:
            assert ".onion" in endpoint
            assert "{query}" in endpoint

    def test_endpoints_are_http(self):
        """Test that all endpoints use HTTP (Tor requires this)."""
        from constants import SEARCH_ENGINE_ENDPOINTS

        for endpoint in SEARCH_ENGINE_ENDPOINTS:
            assert endpoint.startswith("http://")


class TestConfigurationValues:
    """Tests for configuration value defaults."""

    def test_timeout_defaults(self):
        """Test timeout configuration defaults."""
        from constants import SEARCH_TIMEOUT, SCRAPE_TIMEOUT, CLEARWEB_TIMEOUT

        assert SEARCH_TIMEOUT > 0
        assert SCRAPE_TIMEOUT > 0
        assert CLEARWEB_TIMEOUT > 0

    def test_max_scrape_chars_default(self):
        """Test max scrape characters default."""
        from constants import MAX_SCRAPE_CHARS

        assert MAX_SCRAPE_CHARS > 0

    def test_max_workers_default(self):
        """Test default max workers."""
        from constants import DEFAULT_MAX_WORKERS

        assert DEFAULT_MAX_WORKERS > 0
        assert DEFAULT_MAX_WORKERS <= 50

    def test_query_length_limits(self):
        """Test query length limit configuration."""
        from constants import MAX_QUERY_LENGTH, MIN_QUERY_LENGTH

        assert MIN_QUERY_LENGTH > 0
        assert MAX_QUERY_LENGTH > MIN_QUERY_LENGTH
