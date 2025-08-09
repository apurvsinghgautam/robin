import pytest
from unittest.mock import patch, Mock
from fastapi.testclient import TestClient

from api import app


@pytest.fixture
def client():
    """Create a test client for integration tests."""
    return TestClient(app)


class TestAPIIntegration:
    """Integration tests for the complete API workflow."""
    
    @patch('api.generate_summary')
    @patch('api.scrape_multiple')
    @patch('api.filter_results')
    @patch('api.get_search_results')
    @patch('api.refine_query')
    @patch('api.get_llm')
    def test_complete_workflow_integration(self, mock_get_llm, mock_refine, mock_search,
                                         mock_filter, mock_scrape, mock_summary, client):
        """Test complete workflow from query to summary."""
        # Setup mocks for complete workflow
        mock_llm = Mock()
        mock_get_llm.return_value = mock_llm
        mock_refine.return_value = "refined malware analysis"
        
        search_results = [
            {"title": "Malware Report 1", "link": "http://darksite1.onion/report1"},
            {"title": "Malware Analysis 2", "link": "http://darksite2.onion/analysis"},
            {"title": "Threat Intel 3", "link": "http://darksite3.onion/intel"}
        ]
        mock_search.return_value = search_results
        
        filtered_results = search_results[:2]  # Filter to top 2
        mock_filter.return_value = filtered_results
        
        scraped_content = {
            "http://darksite1.onion/report1": "Detailed malware analysis content...",
            "http://darksite2.onion/analysis": "Advanced threat intelligence data..."
        }
        mock_scrape.return_value = scraped_content
        
        summary_text = """
        Investigation Summary:
        1. Identified new malware variant
        2. Found C&C infrastructure details
        3. Discovered threat actor IOCs
        """
        mock_summary.return_value = summary_text
        
        # Test the complete investigation endpoint
        request_data = {
            "query": "malware analysis",
            "model": "gpt4o",
            "threads": 8
        }
        
        response = client.post("/api/investigate", json=request_data)
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        
        assert data["original_query"] == "malware analysis"
        assert data["refined_query"] == "refined malware analysis"
        assert data["search_results_count"] == 3
        assert data["filtered_results_count"] == 2
        assert data["scraped_results_count"] == 2
        assert "Investigation Summary" in data["summary"]
        assert data["model_used"] == "gpt4o"
        
        # Verify all functions were called in correct order
        mock_get_llm.assert_called_once_with("gpt4o")
        mock_refine.assert_called_once_with(mock_llm, "malware analysis")
        mock_search.assert_called_once_with("refined+malware+analysis", 8)
        mock_filter.assert_called_once_with(mock_llm, "refined malware analysis", search_results)
        mock_scrape.assert_called_once_with(filtered_results, 8)
        mock_summary.assert_called_once_with(mock_llm, "malware analysis", scraped_content)
    
    def test_api_endpoints_exist(self, client):
        """Test that all API endpoints are properly mounted."""
        # Test health endpoint
        response = client.get("/health")
        assert response.status_code == 200
        
        # Test models endpoint
        response = client.get("/api/models")
        assert response.status_code == 200
        
        # Test that POST endpoints exist (will fail validation but endpoint exists)
        response = client.post("/api/refine-query", json={})
        assert response.status_code == 422  # Validation error, not 404
        
        response = client.post("/api/search", json={})
        assert response.status_code == 422
        
        response = client.post("/api/filter-results", json={})
        assert response.status_code == 422
        
        response = client.post("/api/scrape", json={})
        assert response.status_code == 422
        
        response = client.post("/api/investigate", json={})
        assert response.status_code == 422
    
    def test_openapi_docs_available(self, client):
        """Test that OpenAPI documentation is available."""
        # Test Swagger UI
        response = client.get("/docs")
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")
        
        # Test ReDoc
        response = client.get("/redoc")
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")
        
        # Test OpenAPI JSON schema
        response = client.get("/openapi.json")
        assert response.status_code == 200
        assert "application/json" in response.headers.get("content-type", "")
        
        schema = response.json()
        assert "openapi" in schema
        assert schema["info"]["title"] == "Robin API"
        assert schema["info"]["version"] == "0.1.0"
    
    @patch('api.get_llm')
    def test_error_handling_chain(self, mock_get_llm, client):
        """Test that errors propagate correctly through the call chain."""
        # Test LLM initialization error
        mock_get_llm.side_effect = Exception("Failed to initialize LLM")
        
        request_data = {"query": "test query", "model": "gpt4o"}
        
        # All endpoints should handle LLM errors gracefully
        endpoints = [
            "/api/refine-query",
            "/api/search", 
            "/api/filter-results",
            "/api/scrape",
            "/api/investigate"
        ]
        
        for endpoint in endpoints:
            response = client.post(endpoint, json=request_data)
            assert response.status_code == 500
            assert "Failed to initialize LLM" in response.json()["detail"] or \
                   "Failed to refine query" in response.json()["detail"] or \
                   "failed" in response.json()["detail"].lower()
    
    def test_concurrent_requests_different_endpoints(self, client):
        """Test handling concurrent requests to different endpoints."""
        import threading
        import time
        
        results = {}
        
        def make_health_request(thread_id):
            response = client.get("/health")
            results[f"health_{thread_id}"] = response.status_code
        
        def make_models_request(thread_id):
            response = client.get("/api/models")
            results[f"models_{thread_id}"] = response.status_code
        
        # Create and start threads
        threads = []
        for i in range(5):
            t1 = threading.Thread(target=make_health_request, args=(i,))
            t2 = threading.Thread(target=make_models_request, args=(i,))
            threads.extend([t1, t2])
        
        # Start all threads
        for t in threads:
            t.start()
        
        # Wait for all threads to complete
        for t in threads:
            t.join()
        
        # Verify all requests succeeded
        assert len(results) == 10  # 5 health + 5 models
        for status_code in results.values():
            assert status_code == 200 