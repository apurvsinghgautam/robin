"""Tests for the search module."""

import pytest
from unittest.mock import patch, MagicMock


class TestFetchSearchResults:
    """Tests for the fetch_search_results function."""

    @patch('search.requests.get')
    def test_fetch_search_results_success(self, mock_get):
        """Test successful fetch of search results."""
        from search import fetch_search_results

        # Mock response with sample HTML containing onion links
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '''
        <html>
            <body>
                <a href="http://example.onion/page1">Test Link 1</a>
                <a href="http://another.onion/page2">Test Link 2</a>
                <a href="https://clearweb.com">Clear Web Link</a>
            </body>
        </html>
        '''
        mock_get.return_value = mock_response

        endpoint = "http://searchengine.onion/search?q={query}"
        results = fetch_search_results(endpoint, "test query")

        assert len(results) == 2
        assert results[0]["link"] == "http://example.onion/page1"
        assert results[0]["title"] == "Test Link 1"

    @patch('search.requests.get')
    def test_fetch_search_results_timeout(self, mock_get):
        """Test handling of timeout errors."""
        from search import fetch_search_results
        from requests.exceptions import Timeout

        mock_get.side_effect = Timeout()

        endpoint = "http://searchengine.onion/search?q={query}"
        results = fetch_search_results(endpoint, "test query")

        assert results == []

    @patch('search.requests.get')
    def test_fetch_search_results_connection_error(self, mock_get):
        """Test handling of connection errors."""
        from search import fetch_search_results
        from requests.exceptions import ConnectionError

        mock_get.side_effect = ConnectionError()

        endpoint = "http://searchengine.onion/search?q={query}"
        results = fetch_search_results(endpoint, "test query")

        assert results == []

    @patch('search.requests.get')
    def test_fetch_search_results_non_200(self, mock_get):
        """Test handling of non-200 status codes."""
        from search import fetch_search_results

        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        endpoint = "http://searchengine.onion/search?q={query}"
        results = fetch_search_results(endpoint, "test query")

        assert results == []


class TestGetSearchResults:
    """Tests for the get_search_results function."""

    @patch('search.fetch_search_results')
    def test_get_search_results_deduplicates(self, mock_fetch):
        """Test that duplicate results are removed."""
        from search import get_search_results

        # Return duplicate links from different "search engines"
        mock_fetch.return_value = [
            {"title": "Link 1", "link": "http://example.onion/page1"},
            {"title": "Link 1 Duplicate", "link": "http://example.onion/page1"},
        ]

        results = get_search_results("test query", max_workers=1)

        # Should only have one unique result
        unique_links = set(r["link"] for r in results)
        assert len(unique_links) == len(results)

    @patch('search.fetch_search_results')
    def test_get_search_results_empty(self, mock_fetch):
        """Test handling of empty results."""
        from search import get_search_results

        mock_fetch.return_value = []

        results = get_search_results("test query", max_workers=1)

        assert results == []
