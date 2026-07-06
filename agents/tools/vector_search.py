from typing import List
from app.models import SearchResult
from retrieval.hybrid_retriever import hybrid_retriever

class VectorSearchTool:
    async def run(self, query: str) -> List[SearchResult]:
        print(f"Tool: Vector Search for '{query}'")
        return await hybrid_retriever.search(query)

vector_search_tool = VectorSearchTool()
