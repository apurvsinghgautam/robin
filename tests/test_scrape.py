"""Tests for the scrape module."""

import pytest
from unittest.mock import patch, MagicMock


class TestGetTorSession:
    """Tests for the get_tor_session function."""

    def test_get_tor_session_creates_session(self):
        """Test that get_tor_session creates a properly configured session."""
        from scrape import get_tor_session

        session = get_tor_session()

        assert session is not None
        assert "http" in session.proxies
        assert "https" in session.proxies
        assert "socks5h://" in session.proxies["http"]


class TestScrapeSingle:
    """Tests for the scrape_single function."""

    @patch('scrape.get_tor_session')
    def test_scrape_single_onion_success(self, mock_session):
        """Test successful scraping of .onion URL."""
        from scrape import scrape_single

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '''
        <html>
            <head><script>alert("test")</script></head>
            <body>
                <h1>Test Page</h1>
                <p>This is test content.</p>
            </body>
        </html>
        '''

        mock_sess = MagicMock()
        mock_sess.get.return_value = mock_response
        mock_session.return_value = mock_sess

        url_data = {"link": "http://test.onion/page", "title": "Test Title"}
        url, content = scrape_single(url_data)

        assert url == "http://test.onion/page"
        assert "Test Title" in content
        assert "Test Page" in content
        assert "test content" in content
        # Scripts should be removed
        assert "alert" not in content

    @patch('scrape.get_tor_session')
    def test_scrape_single_timeout(self, mock_session):
        """Test handling of timeout during scraping."""
        from scrape import scrape_single
        from requests.exceptions import Timeout

        mock_sess = MagicMock()
        mock_sess.get.side_effect = Timeout()
        mock_session.return_value = mock_sess

        url_data = {"link": "http://test.onion/page", "title": "Test Title"}
        url, content = scrape_single(url_data)

        assert url == "http://test.onion/page"
        assert content == "Test Title"  # Falls back to title only

    @patch('scrape.get_tor_session')
    def test_scrape_single_non_200(self, mock_session):
        """Test handling of non-200 response."""
        from scrape import scrape_single

        mock_response = MagicMock()
        mock_response.status_code = 503

        mock_sess = MagicMock()
        mock_sess.get.return_value = mock_response
        mock_session.return_value = mock_sess

        url_data = {"link": "http://test.onion/page", "title": "Test Title"}
        url, content = scrape_single(url_data)

        assert url == "http://test.onion/page"
        assert content == "Test Title"

    @patch('scrape.requests.get')
    def test_scrape_single_clearweb(self, mock_get):
        """Test scraping of clearweb URL (no Tor)."""
        from scrape import scrape_single

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '<html><body><p>Clearweb content</p></body></html>'
        mock_get.return_value = mock_response

        url_data = {"link": "https://example.com/page", "title": "Clearweb Title"}
        url, content = scrape_single(url_data)

        assert url == "https://example.com/page"
        assert "Clearweb content" in content


class TestScrapeMultiple:
    """Tests for the scrape_multiple function."""

    @patch('scrape.scrape_single')
    def test_scrape_multiple_returns_dict(self, mock_scrape):
        """Test that scrape_multiple returns a dictionary."""
        from scrape import scrape_multiple

        mock_scrape.return_value = ("http://test.onion", "Test content")

        urls_data = [
            {"link": "http://test.onion", "title": "Test"}
        ]

        results = scrape_multiple(urls_data, max_workers=1)

        assert isinstance(results, dict)
        assert "http://test.onion" in results

    @patch('scrape.scrape_single')
    def test_scrape_multiple_truncates_long_content(self, mock_scrape):
        """Test that long content is truncated."""
        from scrape import scrape_multiple
        from constants import MAX_SCRAPE_CHARS

        long_content = "x" * (MAX_SCRAPE_CHARS + 500)
        mock_scrape.return_value = ("http://test.onion", long_content)

        urls_data = [
            {"link": "http://test.onion", "title": "Test"}
        ]

        results = scrape_multiple(urls_data, max_workers=1)

        assert len(results["http://test.onion"]) <= MAX_SCRAPE_CHARS + 20  # Allow for truncation message
        assert "truncated" in results["http://test.onion"]
