import pytest
import asyncio
from datetime import datetime
from unittest.mock import Mock, patch, AsyncMock
from fastapi.testclient import TestClient
import httpx

from api import app, validate_model


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)


@pytest.fixture
def sample_search_request():
    """Sample search request payload."""
    return {
        "query": "test query",
        "model": "gpt4o",
        "threads": 5
    }


@pytest.fixture
def mock_search_results():
    """Mock search results."""
    return [
        {"title": "Test Result 1", "link": "http://test1.onion"},
        {"title": "Test Result 2", "link": "http://test2.onion"}
    ]


@pytest.fixture
def mock_scraped_results():
    """Mock scraped results."""
    return {
        "http://test1.onion": "Content from test1",
        "http://test2.onion": "Content from test2"
    }


class TestHealthEndpoint:
    """Tests for the health check endpoint."""
    
    def test_health_check(self, client):
        """Test health check endpoint returns correct response."""
        response = client.get("/health")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "healthy"
        assert data["version"] == "0.1.0"
        assert "timestamp" in data


class TestModelValidation:
    """Tests for model validation."""
    
    def test_validate_model_valid_cases(self):
        """Test model validation with valid models."""
        valid_models = ["gpt4o", "gpt-4.1", "claude-3-5-sonnet-latest", "llama3.1", "gemini-2.5-flash"]
        
        for model in valid_models:
            assert validate_model(model) == model
            assert validate_model(model.upper()) == model  # Test case insensitive
    
    def test_validate_model_invalid_case(self):
        """Test model validation with invalid model."""
        from fastapi import HTTPException
        
        with pytest.raises(HTTPException) as exc_info:
            validate_model("invalid-model")
        
        assert exc_info.value.status_code == 400
        assert "Invalid model" in str(exc_info.value.detail)


class TestModelsEndpoint:
    """Tests for the models listing endpoint."""
    
    def test_list_models(self, client):
        """Test models endpoint returns all available models."""
        response = client.get("/api/models")
        assert response.status_code == 200
        
        data = response.json()
        assert "models" in data
        models = data["models"]
        
        expected_models = ["gpt4o", "gpt-4.1", "claude-3-5-sonnet-latest", "llama3.1", "gemini-2.5-flash"]
        assert len(models) == len(expected_models)
        for model in expected_models:
            assert model in models


class TestRefineQueryEndpoint:
    """Tests for the refine query endpoint."""
    
    @patch('api.get_llm')
    @patch('api.refine_query')
    def test_refine_query_success(self, mock_refine_query, mock_get_llm, client, sample_search_request):
        """Test successful query refinement."""
        # Setup mocks
        mock_llm = Mock()
        mock_get_llm.return_value = mock_llm
        mock_refine_query.return_value = "refined test query"
        
        response = client.post("/api/refine-query", json=sample_search_request)
        assert response.status_code == 200
        
        data = response.json()
        assert data["original_query"] == "test query"
        assert data["refined_query"] == "refined test query"
        assert data["model_used"] == "gpt4o"
        
        # Verify mocks were called
        mock_get_llm.assert_called_once_with("gpt4o")
        mock_refine_query.assert_called_once_with(mock_llm, "test query")
    
    def test_refine_query_invalid_model(self, client):
        """Test refine query with invalid model."""
        request = {
            "query": "test query",
            "model": "invalid-model",
            "threads": 5
        }
        
        response = client.post("/api/refine-query", json=request)
        assert response.status_code == 400
        assert "Invalid model" in response.json()["detail"]
    
    def test_refine_query_missing_query(self, client):
        """Test refine query with missing query field."""
        request = {
            "model": "gpt4o",
            "threads": 5
        }
        
        response = client.post("/api/refine-query", json=request)
        assert response.status_code == 422  # Validation error
    
    @patch('api.get_llm')
    def test_refine_query_llm_error(self, mock_get_llm, client, sample_search_request):
        """Test refine query when LLM throws an error."""
        mock_get_llm.side_effect = Exception("LLM error")
        
        response = client.post("/api/refine-query", json=sample_search_request)
        assert response.status_code == 500
        assert "Failed to refine query" in response.json()["detail"]


class TestSearchEndpoint:
    """Tests for the search endpoint."""
    
    @patch('api.get_llm')
    @patch('api.refine_query')
    @patch('api.get_search_results')
    def test_search_success(self, mock_search, mock_refine, mock_get_llm, 
                           client, sample_search_request, mock_search_results):
        """Test successful dark web search."""
        # Setup mocks
        mock_llm = Mock()
        mock_get_llm.return_value = mock_llm
        mock_refine.return_value = "refined test query"
        mock_search.return_value = mock_search_results
        
        response = client.post("/api/search", json=sample_search_request)
        assert response.status_code == 200
        
        data = response.json()
        assert data["query"] == "test query"
        assert data["refined_query"] == "refined test query"
        assert data["results_count"] == 2
        assert len(data["results"]) == 2
        assert data["results"][0]["title"] == "Test Result 1"
        assert data["results"][0]["link"] == "http://test1.onion"
        
        # Verify mocks
        mock_search.assert_called_once_with("refined+test+query", 5)
    
    @patch('api.get_search_results')
    @patch('api.refine_query')
    @patch('api.get_llm')
    def test_search_error(self, mock_get_llm, mock_refine, mock_search, 
                         client, sample_search_request):
        """Test search endpoint when search fails."""
        mock_get_llm.return_value = Mock()
        mock_refine.return_value = "refined test query"
        mock_search.side_effect = Exception("Search error")
        
        response = client.post("/api/search", json=sample_search_request)
        assert response.status_code == 500
        assert "Search failed" in response.json()["detail"]


class TestFilterResultsEndpoint:
    """Tests for the filter results endpoint."""
    
    @patch('api.get_llm')
    @patch('api.refine_query')
    @patch('api.get_search_results')
    @patch('api.filter_results')
    def test_filter_results_success(self, mock_filter, mock_search, mock_refine, mock_get_llm,
                                   client, sample_search_request, mock_search_results):
        """Test successful results filtering."""
        # Setup mocks
        mock_llm = Mock()
        mock_get_llm.return_value = mock_llm
        mock_refine.return_value = "refined test query"
        mock_search.return_value = mock_search_results
        mock_filter.return_value = [mock_search_results[0]]  # Filter to 1 result
        
        response = client.post("/api/filter-results", json=sample_search_request)
        assert response.status_code == 200
        
        data = response.json()
        assert data["query"] == "test query"
        assert data["original_results_count"] == 2
        assert data["filtered_results_count"] == 1
        assert len(data["filtered_results"]) == 1
        
        # Verify mocks
        mock_filter.assert_called_once_with(mock_llm, "refined test query", mock_search_results)


class TestScrapeEndpoint:
    """Tests for the scrape endpoint."""
    
    @patch('api.get_llm')
    @patch('api.refine_query')
    @patch('api.get_search_results')
    @patch('api.filter_results')
    @patch('api.scrape_multiple')
    def test_scrape_success(self, mock_scrape, mock_filter, mock_search, mock_refine, mock_get_llm,
                           client, sample_search_request, mock_search_results, mock_scraped_results):
        """Test successful scraping."""
        # Setup mocks
        mock_llm = Mock()
        mock_get_llm.return_value = mock_llm
        mock_refine.return_value = "refined test query"
        mock_search.return_value = mock_search_results
        mock_filter.return_value = mock_search_results
        mock_scrape.return_value = mock_scraped_results
        
        response = client.post("/api/scrape", json=sample_search_request)
        assert response.status_code == 200
        
        data = response.json()
        assert data["query"] == "test query"
        assert data["scraped_count"] == 2
        assert "http://test1.onion" in data["scraped_results"]
        assert data["scraped_results"]["http://test1.onion"] == "Content from test1"
        
        # Verify mocks
        mock_scrape.assert_called_once_with(mock_search_results, 5)


class TestCompleteInvestigationEndpoint:
    """Tests for the complete investigation endpoint."""
    
    @patch('api.get_llm')
    @patch('api.refine_query')
    @patch('api.get_search_results')
    @patch('api.filter_results')
    @patch('api.scrape_multiple')
    @patch('api.generate_summary')
    def test_complete_investigation_success(self, mock_summary, mock_scrape, mock_filter, 
                                          mock_search, mock_refine, mock_get_llm,
                                          client, sample_search_request, mock_search_results, 
                                          mock_scraped_results):
        """Test successful complete investigation."""
        # Setup mocks
        mock_llm = Mock()
        mock_get_llm.return_value = mock_llm
        mock_refine.return_value = "refined test query"
        mock_search.return_value = mock_search_results
        mock_filter.return_value = mock_search_results
        mock_scrape.return_value = mock_scraped_results
        mock_summary.return_value = "Investigation summary"
        
        response = client.post("/api/investigate", json=sample_search_request)
        assert response.status_code == 200
        
        data = response.json()
        assert data["original_query"] == "test query"
        assert data["refined_query"] == "refined test query"
        assert data["search_results_count"] == 2
        assert data["filtered_results_count"] == 2
        assert data["scraped_results_count"] == 2
        assert data["summary"] == "Investigation summary"
        assert data["model_used"] == "gpt4o"
        assert "timestamp" in data
        
        # Verify all functions were called
        mock_summary.assert_called_once_with(mock_llm, "test query", mock_scraped_results)
    
    @patch('api.get_llm')
    def test_complete_investigation_error(self, mock_get_llm, client, sample_search_request):
        """Test complete investigation when an error occurs."""
        mock_get_llm.side_effect = Exception("Investigation error")
        
        response = client.post("/api/investigate", json=sample_search_request)
        assert response.status_code == 500
        assert "Investigation failed" in response.json()["detail"]


class TestRequestValidation:
    """Tests for request validation."""
    
    def test_invalid_threads_count(self, client):
        """Test request with invalid threads count."""
        request = {
            "query": "test query",
            "model": "gpt4o",
            "threads": 25  # Above maximum of 20
        }
        
        response = client.post("/api/refine-query", json=request)
        assert response.status_code == 422
    
    def test_empty_query(self, client):
        """Test request with empty query."""
        request = {
            "query": "",
            "model": "gpt4o",
            "threads": 5
        }
        
        response = client.post("/api/refine-query", json=request)
        assert response.status_code == 422
    
    def test_default_values(self, client):
        """Test request with only required fields uses defaults."""
        request = {
            "query": "test query"
        }
        
        with patch('api.get_llm') as mock_get_llm, \
             patch('api.refine_query') as mock_refine:
            
            mock_get_llm.return_value = Mock()
            mock_refine.return_value = "refined query"
            
            response = client.post("/api/refine-query", json=request)
            assert response.status_code == 200
            
            # Should use default model
            mock_get_llm.assert_called_once_with("gpt4o")


class TestAsyncBehavior:
    """Tests for async behavior and thread pool usage."""
    
    @pytest.mark.asyncio
    async def test_concurrent_requests(self):
        """Test that multiple concurrent requests work properly."""
        from fastapi.testclient import TestClient
        
        # Use the test client for concurrent requests
        client = TestClient(app)
        
        # Create multiple concurrent health check requests using asyncio
        async def make_request():
            # TestClient is synchronous, so we run it in a thread
            import asyncio
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(None, lambda: client.get("/health"))
            return response
        
        tasks = [make_request() for _ in range(5)]
        responses = await asyncio.gather(*tasks)
        
        for response in responses:
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy" 