import json
from typing import List
from services import llm

class QueryDecomposer:
    async def decompose(self, query: str) -> List[str]:
        prompt = f"""You are an expert at breaking down complex questions into simpler sub-queries.
Given a user query, decompose it into 2-3 distinct search queries that will help find the answer.
Return ONLY JSON: {{"queries": ["q1", "q2", "q3"]}}

Query: {query}
"""
        try:
            data = json.loads(await llm.generate(prompt, json_mode=True))
            if isinstance(data, dict) and "queries" in data:
                return data["queries"]
            return [query]
        except Exception as e:
            print(f"Decomposition error: {e}")
            return [query]

query_decomposer = QueryDecomposer()
