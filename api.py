from typing import List, Optional, Dict, Any
import asyncio
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, BackgroundTasks, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import uvicorn

from llm import get_llm, refine_query, filter_results, generate_summary
from search import get_search_results
from scrape import scrape_multiple


class SearchRequest(BaseModel):
    query: str = Field(..., description="Dark web search query", min_length=1)
    model: str = Field(default="gpt4o", description="LLM model to use")
    threads: int = Field(default=5, description="Number of threads for scraping", ge=1, le=20)


class SearchResult(BaseModel):
    title: str
    link: str


class RefinedQueryResponse(BaseModel):
    original_query: str
    refined_query: str
    model_used: str


class SearchResultsResponse(BaseModel):
    query: str
    refined_query: str
    results_count: int
    results: List[SearchResult]


class FilteredResultsResponse(BaseModel):
    query: str
    original_results_count: int
    filtered_results_count: int
    filtered_results: List[SearchResult]


class ScrapedContent(BaseModel):
    url: str
    content: str


class ScrapedResultsResponse(BaseModel):
    query: str
    scraped_count: int
    scraped_results: Dict[str, str]


class InvestigationSummary(BaseModel):
    query: str
    summary: str
    timestamp: datetime
    model_used: str


class CompleteInvestigationResponse(BaseModel):
    original_query: str
    refined_query: str
    search_results_count: int
    filtered_results_count: int
    scraped_results_count: int
    summary: str
    timestamp: datetime
    model_used: str


class HealthResponse(BaseModel):
    status: str
    timestamp: datetime
    version: str


# Global thread pool for async operations
thread_pool = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    global thread_pool
    thread_pool = ThreadPoolExecutor(max_workers=10)
    yield
    # Shutdown
    if thread_pool:
        thread_pool.shutdown(wait=True)


app = FastAPI(
    title="Robin API",
    description="AI-Powered Dark Web OSINT Tool API",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)


def validate_model(model: str) -> str:
    """Validate and normalize model name."""
    valid_models = ["gpt4o", "gpt-4.1", "claude-3-5-sonnet-latest", "llama3.1", "gemini-2.5-flash"]
    if model.lower() not in [m.lower() for m in valid_models]:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid model '{model}'. Supported models: {', '.join(valid_models)}"
        )
    # Return the properly cased model name
    for valid_model in valid_models:
        if model.lower() == valid_model.lower():
            return valid_model
    return model


async def run_in_thread(func, *args, **kwargs):
    """Run a synchronous function in a thread pool."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(thread_pool, func, *args, **kwargs)


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now(),
        version="0.1.0"
    )


@app.post("/api/refine-query", response_model=RefinedQueryResponse)
async def refine_search_query(request: SearchRequest):
    """Refine a search query using the specified LLM model."""
    # Validate model first - this can raise HTTPException(400) which should not be caught
    model = validate_model(request.model)
    
    try:
        llm = await run_in_thread(get_llm, model)
        refined = await run_in_thread(refine_query, llm, request.query)
        
        return RefinedQueryResponse(
            original_query=request.query,
            refined_query=refined,
            model_used=model
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to refine query: {str(e)}")


@app.post("/api/search", response_model=SearchResultsResponse)
async def search_dark_web(request: SearchRequest):
    """Search the dark web using multiple search engines."""
    model = validate_model(request.model)
    
    try:
        llm = await run_in_thread(get_llm, model)
        refined = await run_in_thread(refine_query, llm, request.query)
        
        search_results = await run_in_thread(
            get_search_results, 
            refined.replace(" ", "+"), 
            request.threads
        )
        
        results = [SearchResult(title=r["title"], link=r["link"]) for r in search_results]
        
        return SearchResultsResponse(
            query=request.query,
            refined_query=refined,
            results_count=len(results),
            results=results
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@app.post("/api/filter-results", response_model=FilteredResultsResponse)
async def filter_search_results(request: SearchRequest):
    """Search and filter results using LLM."""
    model = validate_model(request.model)
    
    try:
        llm = await run_in_thread(get_llm, model)
        refined = await run_in_thread(refine_query, llm, request.query)
        
        search_results = await run_in_thread(
            get_search_results, 
            refined.replace(" ", "+"), 
            request.threads
        )
        
        filtered_results = await run_in_thread(
            filter_results, 
            llm, 
            refined, 
            search_results
        )
        
        results = [SearchResult(title=r["title"], link=r["link"]) for r in filtered_results]
        
        return FilteredResultsResponse(
            query=request.query,
            original_results_count=len(search_results),
            filtered_results_count=len(results),
            filtered_results=results
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Filtering failed: {str(e)}")


@app.post("/api/scrape", response_model=ScrapedResultsResponse)
async def scrape_filtered_results(request: SearchRequest):
    """Search, filter, and scrape content from dark web results."""
    model = validate_model(request.model)
    
    try:
        llm = await run_in_thread(get_llm, model)
        refined = await run_in_thread(refine_query, llm, request.query)
        
        search_results = await run_in_thread(
            get_search_results, 
            refined.replace(" ", "+"), 
            request.threads
        )
        
        filtered_results = await run_in_thread(
            filter_results, 
            llm, 
            refined, 
            search_results
        )
        
        scraped_results = await run_in_thread(
            scrape_multiple, 
            filtered_results, 
            request.threads
        )
        
        return ScrapedResultsResponse(
            query=request.query,
            scraped_count=len(scraped_results),
            scraped_results=scraped_results
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Scraping failed: {str(e)}")


@app.post("/api/investigate", response_model=CompleteInvestigationResponse)
async def complete_investigation(request: SearchRequest):
    """Perform complete investigation: search, filter, scrape, and generate summary."""
    model = validate_model(request.model)
    
    try:
        llm = await run_in_thread(get_llm, model)
        refined = await run_in_thread(refine_query, llm, request.query)
        
        search_results = await run_in_thread(
            get_search_results, 
            refined.replace(" ", "+"), 
            request.threads
        )
        
        filtered_results = await run_in_thread(
            filter_results, 
            llm, 
            refined, 
            search_results
        )
        
        scraped_results = await run_in_thread(
            scrape_multiple, 
            filtered_results, 
            request.threads
        )
        
        summary = await run_in_thread(
            generate_summary, 
            llm, 
            request.query, 
            scraped_results
        )
        
        return CompleteInvestigationResponse(
            original_query=request.query,
            refined_query=refined,
            search_results_count=len(search_results),
            filtered_results_count=len(filtered_results),
            scraped_results_count=len(scraped_results),
            summary=summary,
            timestamp=datetime.now(),
            model_used=model
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Investigation failed: {str(e)}")


@app.get("/api/models")
async def list_available_models():
    """List all available LLM models."""
    return {
        "models": [
            "gpt4o",
            "gpt-4.1", 
            "claude-3-5-sonnet-latest",
            "llama3.1",
            "gemini-2.5-flash"
        ]
    }


if __name__ == "__main__":
    uvicorn.run(
        "api:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    ) 