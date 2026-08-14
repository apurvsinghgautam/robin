import uuid
from typing import Dict, Any, Optional

# In-memory store for investigation jobs
# In a future phase, this can be backed by Redis or a database.
_jobs: Dict[str, Dict[str, Any]] = {}

def create_job(query: str, model: str, preset: str, custom_instructions: str, threads: int = 4) -> str:
    job_id = str(uuid.uuid4())
    _jobs[job_id] = {
        "job_id": job_id,
        "status": "pending",
        "stage": "initialized",
        "query": query,
        "model": model,
        "preset": preset,
        "custom_instructions": custom_instructions,
        "threads": threads,
        "refined_query": None,
        "search_results": [],
        "scraped_data": [],
        "enrichment_data": [],
        "summary": None,
        "pivots": [],
        "error": None
    }
    return job_id

def get_job(job_id: str) -> Optional[Dict[str, Any]]:
    return _jobs.get(job_id)

def update_job_stage(job_id: str, stage: str, status: str = "running"):
    if job_id in _jobs:
        _jobs[job_id]["stage"] = stage
        _jobs[job_id]["status"] = status

def update_job_data(job_id: str, key: str, data: Any):
    if job_id in _jobs:
        _jobs[job_id][key] = data

def fail_job(job_id: str, error_message: str):
    if job_id in _jobs:
        _jobs[job_id]["status"] = "failed"
        _jobs[job_id]["error"] = error_message

def complete_job(job_id: str):
    if job_id in _jobs:
        _jobs[job_id]["status"] = "completed"
        _jobs[job_id]["stage"] = "done"
