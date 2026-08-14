from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import asyncio
from typing import Dict, Any

from models import InvestigationRequest, InvestigationResponse, ChatRequest, ChatResponse
from jobs import create_job, get_job, update_job_stage, update_job_data, fail_job, complete_job

import health
from search import get_search_results
from scrape import scrape_multiple
from llm import (
    get_llm, refine_query, filter_results, generate_summary, 
    suggest_pivots, build_followup_context, answer_followup
)
from services.ioc_parser import extract_all_iocs_from_job_data
from services.enrichment import enrich_iocs

app = FastAPI(title="Robin Dark Web OSINT API", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/health")
def health_check():
    # Only return basic up status here. The UI calls health checks explicitly.
    return {"status": "ok"}

def _run_investigation(job_id: str, req: InvestigationRequest):
    try:
        update_job_stage(job_id, "loading_llm")
        llm = get_llm(req.model)
        
        update_job_stage(job_id, "refining_query")
        refined = refine_query(llm, req.query)
        update_job_data(job_id, "refined_query", refined)
        
        update_job_stage(job_id, "searching")
        # Run synchronous search in another thread since it blocks
        results = get_search_results(refined, max_workers=req.threads)
        if len(results) > req.max_results:
            results = results[:req.max_results]
        update_job_data(job_id, "search_results", results)
        
        update_job_stage(job_id, "filtering")
        filtered = filter_results(llm, refined, results)
        if len(filtered) > req.max_scrape:
            filtered = filtered[:req.max_scrape]
            
        update_job_stage(job_id, "scraping")
        scraped_dict = scrape_multiple(filtered, max_workers=req.threads)
        
        # Convert dict[str, str] to list of ScrapeResultItem for API response
        scraped_list = [{"url": k, "content": v} for k, v in scraped_dict.items()]
        update_job_data(job_id, "scraped_data", scraped_list)
        
        update_job_stage(job_id, "enriching")
        iocs = extract_all_iocs_from_job_data(req.query, results, scraped_list)
        enrichment_data = []
        if any(iocs.values()):
            enrichment_data = enrich_iocs(iocs)
        update_job_data(job_id, "enrichment_data", enrichment_data)
        
        update_job_stage(job_id, "summarizing")
        content_for_llm = {
            "scraped_data": scraped_dict
        }
        if enrichment_data:
            content_for_llm["enrichment_data"] = enrichment_data
            
        summary = generate_summary(
            llm, req.query, content_for_llm, 
            preset=req.preset, custom_instructions=req.custom_instructions
        )
        update_job_data(job_id, "summary", summary)
        
        update_job_stage(job_id, "pivots")
        pivots = suggest_pivots(llm, req.query, content_for_llm, preset=req.preset)
        update_job_data(job_id, "pivots", pivots)
        
        complete_job(job_id)
        
    except Exception as e:
        fail_job(job_id, str(e))

@app.post("/api/investigation", response_model=InvestigationResponse)
async def start_investigation(req: InvestigationRequest, bg_tasks: BackgroundTasks):
    job_id = create_job(req.query, req.model, req.preset, req.custom_instructions, req.threads)
    bg_tasks.add_task(asyncio.to_thread, _run_investigation, job_id, req)
    job = get_job(job_id)
    return InvestigationResponse(**job)

@app.get("/api/investigation/{job_id}", response_model=InvestigationResponse)
def get_investigation_status(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return InvestigationResponse(**job)

@app.post("/api/chat", response_model=ChatResponse)
def chat_followup(req: ChatRequest):
    job = get_job(req.job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
        
    # We must construct scraped data as dict[str, str] to match what build_followup_context expects
    # since we stored it as list of dicts.
    scraped_dict = {item["url"]: item["content"] for item in job.get("scraped_data", [])}
    
    context = build_followup_context(
        job.get("query", ""), 
        job.get("refined_query", ""),
        job.get("search_results", []), 
        scraped_dict, 
        job.get("summary", ""),
        job.get("enrichment_data", [])
    )
    
    try:
        llm = get_llm(job["model"])
        answer = answer_followup(llm, req.question, context, preset=job["preset"])
        return ChatResponse(answer=answer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
