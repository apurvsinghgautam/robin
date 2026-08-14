import pytest
from fastapi.testclient import TestClient
from main import app
import json
from unittest.mock import patch, MagicMock

client = TestClient(app)

def test_health_endpoint():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

@patch("main.get_search_results")
@patch("main.filter_results")
@patch("main.scrape_multiple")
@patch("main.generate_summary")
@patch("main.suggest_pivots")
@patch("main.refine_query")
@patch("main.get_llm")
def test_investigation_pipeline(mock_get_llm, mock_refine_query, mock_suggest_pivots, mock_generate_summary, mock_scrape, mock_filter, mock_search):
    # Mock return values
    mock_search.return_value = [{"title": "Test Title", "link": "http://test.onion"}]
    mock_filter.return_value = [{"title": "Test Title", "link": "http://test.onion"}]
    mock_scrape.return_value = {"http://test.onion": "Test Title - Scraped content"}
    mock_generate_summary.return_value = "Test Summary"
    mock_suggest_pivots.return_value = ["test pivot 1", "test pivot 2"]
    mock_refine_query.return_value = "refined test query"
    
    # 1. Start investigation
    req = {
        "query": "test query",
        "model": "gpt4o"
    }
    response = client.post("/api/investigation", json=req)
    assert response.status_code == 200
    data = response.json()
    assert "job_id" in data
    assert data["status"] in ["pending", "running", "completed"]
    job_id = data["job_id"]
    
    # Wait a bit for bg task
    import time
    time.sleep(1)
    
    # 2. Check investigation status
    res = client.get(f"/api/investigation/{job_id}")
    assert res.status_code == 200
    job_data = res.json()
    assert job_data["status"] == "completed"
    assert job_data["stage"] == "done"
    
    # 3. Verify structured data preservation
    # Search Results
    assert len(job_data["search_results"]) == 1
    assert job_data["search_results"][0]["title"] == "Test Title"
    
    # Scraped Data (list of dicts in API)
    assert len(job_data["scraped_data"]) == 1
    assert job_data["scraped_data"][0]["url"] == "http://test.onion"
    assert job_data["scraped_data"][0]["content"] == "Test Title - Scraped content"
    
    # Summary & Pivots
    assert job_data["summary"] == "Test Summary"
    assert job_data["pivots"] == ["test pivot 1", "test pivot 2"]

def test_investigation_not_found():
    res = client.get("/api/investigation/invalid-job-id")
    assert res.status_code == 404

@patch("main.get_llm")
@patch("main.answer_followup")
def test_chat_endpoint(mock_answer_followup, mock_get_llm):
    mock_answer_followup.return_value = "This is a follow up answer."
    
    # Pre-populate a job
    from jobs import create_job, update_job_data
    job_id = create_job("test query", "gpt4o", "threat_intel", "")
    
    # We store scraped_data as list of dicts in jobs.py as per API format
    update_job_data(job_id, "scraped_data", [{"url": "http://test.onion", "content": "Test content"}])
    update_job_data(job_id, "summary", "Test Summary")
    
    # 1. Ask a question
    req = {
        "job_id": job_id,
        "question": "What is this?"
    }
    response = client.post("/api/chat", json=req)
    assert response.status_code == 200
    assert response.json()["answer"] == "This is a follow up answer."
    
    # Also verify that the context builder successfully parses the job's list-of-dicts
    # back into dict[str, str] before calling build_followup_context.
    # We can check that answer_followup was called with the correct context string.
    call_args = mock_answer_followup.call_args[0]
    context_str = call_args[2] # 3rd argument is context
    
    # The context should contain the actual VALUES of the scraped data, not just keys
    assert "Test content" in context_str

from llm import build_followup_context, suggest_pivots, generate_summary

def test_json_serialization_in_llm_prompts():
    scraped_dict = {"http://test.onion": "Actual secret text"}
    
    # Test build_followup_context
    context = build_followup_context(
        query="q", refined="r", sources=[], 
        scraped=scraped_dict, summary="s"
    )
    # Important: verify the VALUE is present
    assert "Actual secret text" in context
    
    # Test suggest_pivots (using mock llm)
    mock_llm = MagicMock()
    mock_chain = MagicMock()
    mock_chain.invoke.return_value = '["pivot1"]'
    # we don't need to mock Langchain completely, just verifying the serialization logic
    # but suggest_pivots creates a chain. We'll just verify the manual logic.
    # Actually, we can test it directly:
    
    with patch("llm.ChatPromptTemplate") as mock_prompt:
        # Prevent it from actually running LLM
        mock_prompt.return_value.__or__.return_value.__or__.return_value.invoke.return_value = '["test"]'
        
        suggest_pivots(mock_llm, "query", scraped_dict)
        
        # Check what arguments the prompt template chain was invoked with
        chain_invoke_args = mock_prompt.return_value.__or__.return_value.__or__.return_value.invoke.call_args[0][0]
        # The content should be serialized JSON string containing the value
        assert "Actual secret text" in chain_invoke_args["content"]

    with patch("llm.ChatPromptTemplate") as mock_prompt_gen:
        mock_prompt_gen.return_value.__or__.return_value.__or__.return_value.invoke.return_value = "summary"
        generate_summary(mock_llm, "query", scraped_dict)
        
        chain_invoke_args = mock_prompt_gen.return_value.__or__.return_value.__or__.return_value.invoke.call_args[0][0]
        # Content should be JSON string
        assert "Actual secret text" in chain_invoke_args["content"]
