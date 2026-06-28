import asyncio
import json
import google.generativeai as genai
from typing import List, Dict, Any
from app.config import settings
from app.models import SearchResult, GradingResult

class DocumentGrader:
    def __init__(self):
        genai.configure(api_key=settings.GOOGLE_API_KEY)
        self.model = genai.GenerativeModel(settings.GEMINI_MODEL)

    async def grade_relevance(self, query: str, document: str) -> GradingResult:
        prompt = f"""Rate this document's relevance to the query. 
Return ONLY JSON: {{"relevance": "correct"|"ambiguous"|"incorrect", "confidence": float, "reason": str}}

Query: {query}
Document: {document}
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
            return GradingResult(**data)
        except Exception as e:
            print(f"DocumentGrader error: {e}")
            return GradingResult(relevance="incorrect", confidence=0.0, reason=str(e))

    async def filter_irrelevant(self, query: str, results: List[SearchResult]) -> List[SearchResult]:
        filtered = []
        for res in results:
            grading = await self.grade_relevance(query, res.content)
            if grading.relevance in ["correct", "ambiguous"]:
                filtered.append(res)
        return filtered

document_grader = DocumentGrader()
