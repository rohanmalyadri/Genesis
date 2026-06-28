from typing import Literal

class QueryRouter:
    async def route(self, query: str) -> Literal["vector_search", "web_search", "code_search"]:
        # Logic to determine the best search tool
        query_lower = query.lower()
        if any(kw in query_lower for kw in ["how to code", "function", "class", "import"]):
            return "code_search"
        if any(kw in query_lower for kw in ["current news", "today", "weather"]):
            return "web_search"
        return "vector_search"

query_router = QueryRouter()
