from pydantic import BaseModel
from typing import List, Optional, Dict, Any

class SearchResultItem(BaseModel):
    title: str
    link: str

class ScrapeResultItem(BaseModel):
    url: str
    content: str

class InvestigationRequest(BaseModel):
    query: str
    model: str = "gpt4o"
    preset: str = "threat_intel"
    custom_instructions: str = ""
    threads: int = 4
    max_results: int = 50
    max_scrape: int = 10

class InvestigationResponse(BaseModel):
    job_id: str
    status: str
    stage: str
    query: str
    refined_query: Optional[str] = None
    search_results: List[SearchResultItem] = []
    scraped_data: List[ScrapeResultItem] = []
    enrichment_data: List[Dict[str, Any]] = []
    summary: Optional[str] = None
    pivots: List[str] = []
    error: Optional[str] = None

class ChatRequest(BaseModel):
    job_id: str
    question: str

class ChatResponse(BaseModel):
    answer: str
