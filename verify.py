import requests
import time
import json
import traceback

BASE_URL = "http://127.0.0.1:8000"

def test_health():
    print("=== Testing Health Endpoint ===")
    try:
        r = requests.get(f"{BASE_URL}/api/health")
        print(f"Status Code: {r.status_code}")
        print(f"Response: {r.json()}")
    except Exception as e:
        print(f"Failed: {e}")

def test_swagger():
    print("\n=== Testing Swagger Endpoint ===")
    try:
        r = requests.get(f"{BASE_URL}/openapi.json")
        print(f"Status Code: {r.status_code}")
        data = r.json()
        print("Paths found:")
        for path in data.get("paths", {}):
            print(f"  {path}")
    except Exception as e:
        print(f"Failed: {e}")

def test_investigation():
    print("\n=== Testing Investigation Pipeline ===")
    try:
        req = {
            "query": "safe test query",
            "model": "gpt4o", # May fail locally if API keys aren't set, testing error handling
            "threads": 1,
            "max_results": 2,
            "max_scrape": 1
        }
        r = requests.post(f"{BASE_URL}/api/investigation", json=req)
        print(f"Create Job Status: {r.status_code}")
        print(f"Create Job Response: {r.json()}")
        
        if r.status_code != 200:
            return
            
        job_id = r.json().get("job_id")
        
        # Poll for completion
        for i in range(10):
            time.sleep(2)
            r_poll = requests.get(f"{BASE_URL}/api/investigation/{job_id}")
            job = r_poll.json()
            print(f"Poll {i+1}: stage={job.get('stage')}, status={job.get('status')}")
            if job.get("status") in ["completed", "failed"]:
                print(f"Final Job Data:\n  Status: {job.get('status')}\n  Error: {job.get('error')}")
                if job.get("status") == "completed":
                    print(f"  Search Results (count): {len(job.get('search_results', []))}")
                    if job.get('search_results'):
                        print(f"    First result structure: {type(job.get('search_results')[0])} - {job.get('search_results')[0]}")
                    print(f"  Scraped Data (count): {len(job.get('scraped_data', []))}")
                    if job.get('scraped_data'):
                        print(f"    First scraped item structure: {type(job.get('scraped_data')[0])} - {str(job.get('scraped_data')[0])[:100]}...")
                
                # Test chat endpoint with this job
                test_chat(job_id)
                break
    except Exception as e:
        print(f"Failed: {e}")

def test_chat(job_id):
    print("\n=== Testing Chat Endpoint ===")
    try:
        req = {
            "job_id": job_id,
            "question": "What is the summary?"
        }
        r = requests.post(f"{BASE_URL}/api/chat", json=req)
        print(f"Chat Status: {r.status_code}")
        print(f"Chat Response: {r.json()}")
    except Exception as e:
        print(f"Failed: {e}")

def test_error_handling():
    print("\n=== Testing Error Handling ===")
    try:
        # Invalid job ID
        r = requests.get(f"{BASE_URL}/api/investigation/invalid-id-123")
        print(f"Invalid Job ID Status: {r.status_code}")
        
        # Invalid payload
        r = requests.post(f"{BASE_URL}/api/investigation", json={"wrong": "payload"})
        print(f"Invalid Payload Status: {r.status_code}")
        
        # Empty query
        r = requests.post(f"{BASE_URL}/api/investigation", json={"query": ""})
        print(f"Empty Query Status: {r.status_code}")
    except Exception as e:
        print(f"Failed: {e}")

if __name__ == "__main__":
    test_health()
    test_swagger()
    test_investigation()
    test_error_handling()
