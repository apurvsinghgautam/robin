#!/usr/bin/env python3
"""
Example script demonstrating how to use the Robin API.

This script shows how to interact with the Robin API programmatically
to perform dark web OSINT investigations.
"""

import httpx
import asyncio
import json
from typing import Dict, Any


class RobinAPIClient:
    """Client for interacting with the Robin API."""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.client = httpx.AsyncClient(base_url=base_url, timeout=300.0)
    
    async def health_check(self) -> Dict[str, Any]:
        """Check if the API is healthy."""
        response = await self.client.get("/health")
        response.raise_for_status()
        return response.json()
    
    async def list_models(self) -> Dict[str, Any]:
        """Get list of available models."""
        response = await self.client.get("/api/models")
        response.raise_for_status()
        return response.json()
    
    async def refine_query(self, query: str, model: str = "gpt4o") -> Dict[str, Any]:
        """Refine a search query."""
        data = {
            "query": query,
            "model": model,
            "threads": 5
        }
        response = await self.client.post("/api/refine-query", json=data)
        response.raise_for_status()
        return response.json()
    
    async def search(self, query: str, model: str = "gpt4o", threads: int = 5) -> Dict[str, Any]:
        """Search the dark web."""
        data = {
            "query": query,
            "model": model,
            "threads": threads
        }
        response = await self.client.post("/api/search", json=data)
        response.raise_for_status()
        return response.json()
    
    async def investigate(self, query: str, model: str = "gpt4o", threads: int = 5) -> Dict[str, Any]:
        """Perform complete investigation."""
        data = {
            "query": query,
            "model": model,
            "threads": threads
        }
        response = await self.client.post("/api/investigate", json=data)
        response.raise_for_status()
        return response.json()
    
    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()


async def example_investigation():
    """Example of performing a complete investigation."""
    client = RobinAPIClient()
    
    try:
        # Check API health
        print("Checking API health...")
        health = await client.health_check()
        print(f"API Status: {health['status']}")
        
        # List available models
        print("\nAvailable models:")
        models = await client.list_models()
        for model in models['models']:
            print(f"  - {model}")
        
        # Example query
        query = "ransomware payments bitcoin"
        model = "gpt4o"
        
        print(f"\nStarting investigation for: '{query}'")
        print(f"Using model: {model}")
        
        # Refine the query first (optional)
        print("\nRefining query...")
        refined = await client.refine_query(query, model)
        print(f"Original: {refined['original_query']}")
        print(f"Refined: {refined['refined_query']}")
        
        # Perform search only
        print("\nPerforming search...")
        search_results = await client.search(query, model)
        print(f"Found {search_results['results_count']} results")
        
        # Show first few results
        for i, result in enumerate(search_results['results'][:3]):
            print(f"  {i+1}. {result['title']}")
            print(f"     {result['link']}")
        
        # Perform complete investigation
        print(f"\nPerforming complete investigation...")
        investigation = await client.investigate(query, model, threads=8)
        
        print(f"\nInvestigation Results:")
        print(f"- Search results: {investigation['search_results_count']}")
        print(f"- Filtered results: {investigation['filtered_results_count']}")
        print(f"- Scraped results: {investigation['scraped_results_count']}")
        print(f"- Timestamp: {investigation['timestamp']}")
        
        print(f"\nSummary:")
        print(investigation['summary'][:500] + "..." if len(investigation['summary']) > 500 else investigation['summary'])
        
    except httpx.HTTPError as e:
        print(f"HTTP Error: {e}")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await client.close()


async def example_step_by_step():
    """Example of using the API step by step."""
    client = RobinAPIClient()
    
    try:
        query = "cryptocurrency exchange hack"
        
        print(f"Step-by-step investigation: '{query}'")
        
        # Step 1: Refine query
        print("\n1. Refining query...")
        refined = await client.refine_query(query)
        print(f"Refined: {refined['refined_query']}")
        
        # Step 2: Search
        print("\n2. Searching...")
        search_results = await client.search(query)
        print(f"Found {search_results['results_count']} results")
        
        # Step 3: Get filtered and scraped results (using investigate endpoint)
        print("\n3. Filtering and scraping...")
        investigation = await client.investigate(query, threads=6)
        
        print(f"Final summary generated with {investigation['scraped_results_count']} scraped pages")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await client.close()


async def main():
    """Main example function."""
    print("Robin API Examples")
    print("==================")
    
    print("\nExample 1: Complete Investigation")
    await example_investigation()
    
    print("\n" + "="*60)
    print("\nExample 2: Step-by-step Process")
    await example_step_by_step()


if __name__ == "__main__":
    print("Robin API Client Example")
    print("Make sure the Robin API server is running on http://localhost:8000")
    print("Start it with: python main.py api --reload")
    print()
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nExample interrupted by user")
    except Exception as e:
        print(f"Example failed: {e}") 