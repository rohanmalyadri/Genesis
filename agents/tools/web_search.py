import os
import aiohttp
from typing import List
from app.models import SearchResult

class WebSearchTool:
    def __init__(self):
        self.api_key = os.getenv("TAVILY_API_KEY")
        self.url = "https://api.tavily.com/search"

    async def run(self, query: str) -> List[SearchResult]:
        if not self.api_key:
            print("WebSearchTool: TAVILY_API_KEY not found.")
            return []

        print(f"Tool: Web Search for '{query}' using Tavily")
        
        payload = {
            "api_key": self.api_key,
            "query": query,
            "search_depth": "basic",
            "include_answer": False,
            "max_results": 3
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(self.url, json=payload) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        results = []
                        for res in data.get("results", []):
                            results.append(SearchResult(
                                content=res.get("content", ""),
                                metadata={
                                    "source": "web",
                                    "url": res.get("url"),
                                    "title": res.get("title")
                                },
                                score=res.get("score", 0.0)
                            ))
                        return results
                    else:
                        print(f"WebSearchTool error: {resp.status}")
                        return []
        except Exception as e:
            print(f"WebSearchTool exception: {e}")
            return []

web_search_tool = WebSearchTool()
