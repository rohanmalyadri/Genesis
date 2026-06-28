import json
import asyncio
import google.generativeai as genai
from typing import List
from app.config import settings

class QueryDecomposer:
    def __init__(self):
        genai.configure(api_key=settings.GOOGLE_API_KEY)
        self.model = genai.GenerativeModel(settings.GEMINI_MODEL)

    async def decompose(self, query: str) -> List[str]:
        prompt = f"""You are an expert at breaking down complex questions into simpler sub-queries.
Given a user query, decompose it into 2-3 distinct search queries that will help find the answer.
Return ONLY JSON: {{"queries": ["q1", "q2", "q3"]}}

Query: {query}
"""
        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.model.generate_content(
                    prompt,
                    generation_config=genai.types.GenerationConfig(response_mime_type="application/json")
                )
            )
            data = json.loads(response.text)
            if isinstance(data, dict) and "queries" in data:
                return data["queries"]
            return [query]
        except Exception as e:
            print(f"Decomposition error: {e}")
            return [query]

query_decomposer = QueryDecomposer()
