from typing import List
from app.models import SearchResult

class CodeSearchTool:
    async def run(self, query: str) -> List[SearchResult]:
        print(f"Tool: Code Search for '{query}'")
        # In production, search github or local repo
        return [
            SearchResult(
                content=f"Code snippet for {query}",
                metadata={"source": "code", "file": "main.py"},
                score=0.9
            )
        ]

code_search_tool = CodeSearchTool()
