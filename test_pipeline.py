from fastapi.testclient import TestClient
from main import app
from unittest.mock import patch, Mock
import time

client = TestClient(app)

@patch("main.get_search_results")
@patch("main.scrape_multiple")
@patch("main.enrich_iocs")
@patch("main.get_llm")
@patch("main.refine_query")
@patch("main.filter_results")
@patch("main.generate_summary")
@patch("main.suggest_pivots")
def test_investigation_pipeline(
    mock_suggest_pivots, mock_generate_summary, mock_filter_results, mock_refine_query,
    mock_get_llm, mock_enrich_iocs, mock_scrape, mock_search
):
    mock_get_llm.return_value = Mock()
    mock_refine_query.return_value = "refined query 8.8.8.8"
    mock_search.return_value = [{"title": "Title", "link": "http://onion.onion"}]
    mock_filter_results.return_value = [{"title": "Title", "link": "http://onion.onion"}]
    mock_scrape.return_value = {"http://onion.onion": "Content"}
    mock_generate_summary.return_value = "Summary"
    mock_suggest_pivots.return_value = ["pivot1"]
    mock_enrich_iocs.return_value = [{"provider": "ipinfo", "status": "ok", "data": {}}]
    
    response = client.post("/api/investigation", json={
        "query": "Investigate 8.8.8.8",
        "model": "gpt4o"
    })
    
    assert response.status_code == 200
    job_id = response.json()["job_id"]
    
    # Wait for completion
    completed = False
    for _ in range(10):
        res = client.get(f"/api/investigation/{job_id}")
        data = res.json()
        if data["status"] == "completed":
            completed = True
            break
        time.sleep(0.5)
        
    assert completed
    assert data["stage"] == "done"
    
    # Check enrichment data
    assert len(data["enrichment_data"]) == 1
    assert data["enrichment_data"][0]["provider"] == "ipinfo"
    
    # Check that enrich_iocs was called with the IOCs
    args, kwargs = mock_enrich_iocs.call_args
    assert "8.8.8.8" in args[0]["ip"]
