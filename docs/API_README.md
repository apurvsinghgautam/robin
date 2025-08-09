# Robin API Documentation

## Overview

The Robin API is a RESTful web service built with FastAPI that provides programmatic access to Robin's AI-powered dark web OSINT capabilities. The API allows developers to integrate Robin's intelligence gathering and analysis features into their own applications.

## Quick Start

### Starting the API Server

```bash
# Start with default settings (port 8000)
uv run python main.py api

# Start with custom port and host
uv run python main.py api --api-port 9000 --api-host 127.0.0.1

# Start with auto-reload for development
uv run python main.py api --reload
```

### Interactive Documentation
Once running, access:
- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`

## API Endpoints

### Health Check

#### `GET /health`
Check API status and version.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:00Z",
  "version": "0.1.0"
}
```

### Models

#### `GET /api/models`
List available LLM models.

**Response:**
```json
{
  "models": [
    "gpt4o",
    "gpt-4.1",
    "claude-3-5-sonnet-latest",
    "llama3.1",
    "gemini-2.5-flash"
  ]
}
```

### Investigation Endpoints

All investigation endpoints use the same request format:

**Request Body:**
```json
{
  "query": "your search query",
  "model": "gpt4o",
  "threads": 5
}
```

**Parameters:**
- `query` (required): Search query string
- `model` (optional): LLM model to use (default: "gpt4o")
- `threads` (optional): Number of parallel threads (1-20, default: 5)

#### `POST /api/refine-query`
Refine a search query using AI.

**Response:**
```json
{
  "original_query": "ransomware payments bitcoin",
  "refined_query": "ransomware bitcoin payment wallets cryptocurrency laundering",
  "model_used": "gpt4o"
}
```

#### `POST /api/search`
Search dark web with query refinement.

**Response:**
```json
{
  "query": "malware analysis",
  "refined_query": "malware reverse engineering analysis tools techniques",
  "results_count": 15,
  "results": [
    {
      "title": "Advanced Malware Analysis Techniques",
      "link": "http://analysis-site.onion/advanced-techniques"
    }
  ]
}
```

#### `POST /api/filter-results`
Search and filter results using AI.

**Response:**
```json
{
  "query": "cryptocurrency exchange hack",
  "original_results_count": 25,
  "filtered_results_count": 8,
  "filtered_results": [
    {
      "title": "Recent Exchange Vulnerabilities",
      "link": "http://crypto-intel.onion/exchange-hacks"
    }
  ]
}
```

#### `POST /api/scrape`
Search, filter, and scrape content from relevant sites.

**Response:**
```json
{
  "query": "threat intelligence IOCs",
  "scraped_count": 5,
  "scraped_results": {
    "http://threat-intel.onion/iocs": "Detailed threat intelligence content...",
    "http://malware-db.onion/indicators": "IOC database content..."
  }
}
```

#### `POST /api/investigate`
Complete investigation pipeline: search, filter, scrape, and summarize.

**Response:**
```json
{
  "original_query": "APT group infrastructure",
  "refined_query": "advanced persistent threat group infrastructure C2 domains",
  "search_results_count": 30,
  "filtered_results_count": 12,
  "scraped_results_count": 8,
  "summary": "Investigation revealed multiple APT infrastructure patterns...",
  "timestamp": "2024-01-15T10:45:30Z",
  "model_used": "claude-3-5-sonnet-latest"
}
```

## Processing Pipeline

The API follows a progressive pipeline for investigations:

1. **Query Refinement** → AI optimizes the search query
2. **Dark Web Search** → Search multiple engines with refined query
3. **Content Filtering** → AI filters results for relevance
4. **Content Scraping** → Extract content from relevant sites
5. **Summary Generation** → AI generates investigation summary

Each endpoint provides access to different stages of this pipeline.

## Error Handling

### HTTP Status Codes
- **200**: Success
- **400**: Bad Request (invalid model, validation errors)
- **422**: Unprocessable Entity (validation errors)
- **500**: Internal Server Error (LLM errors, service failures)

### Error Response Format
```json
{
  "detail": "Failed to refine query: OpenAI API key not found"
}
```
