import httpx
import logging
from typing import List, Dict, Any
from app.config import settings

logger = logging.getLogger("WebSearch")

async def web_search(query: str) -> List[Dict[str, Any]]:
    """
    Search the web using Tavily API.
    Returns a list of search results with title, url, and content.
    """
    if not settings.TAVILY_API_KEY:
        logger.warning("TAVILY_API_KEY not configured. Web search disabled.")
        return []

    url = "https://api.tavily.com/search"
    payload = {
        "api_key": settings.TAVILY_API_KEY,
        "query": query,
        "search_depth": "advanced",
        "include_answer": False,
        "max_results": 5
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
            
            results = []
            for res in data.get("results", []):
                results.append({
                    "title": res.get("title"),
                    "url": res.get("url"),
                    "content": res.get("content"),
                    "score": res.get("score", 0.5)
                })
            return results
    except Exception as e:
        logger.error(f"Tavily search failed: {e}")
        return []
