import asyncio
import json
from typing import List, Dict, Any
from services import llm
from app.models import SearchResult, GradingResult

class DocumentGrader:
    async def grade_relevance(self, query: str, document: str) -> GradingResult:
        prompt = f"""Rate this document's relevance to the query. 
Return ONLY JSON: {{"relevance": "correct"|"ambiguous"|"incorrect", "confidence": float, "reason": str}}

Query: {query}
Document: {document}
"""
        try:
            data = json.loads(await llm.generate(prompt, json_mode=True))
            return GradingResult(**data)
        except Exception as e:
            # If the grader itself is unavailable (e.g. quota), trust retrieval rather than
            # wrongly concluding the knowledge base has nothing relevant.
            print(f"DocumentGrader unavailable ({type(e).__name__}); trusting retrieval order")
            return GradingResult(relevance="correct", confidence=0.0, reason="grader unavailable")

    async def grade_batch(self, query: str, documents: List[str]) -> List[GradingResult]:
        """Grade several documents with a single LLM call (falls back to one call each)."""
        if not documents:
            return []
        if len(documents) == 1:
            return [await self.grade_relevance(query, documents[0])]

        numbered = "\n\n".join(f"[{i}] {d[:1500]}" for i, d in enumerate(documents))
        prompt = f"""Rate how relevant each document is to the query.
Return ONLY a JSON array with one object per document, in order:
[{{"relevance": "correct"|"ambiguous"|"incorrect", "confidence": float, "reason": str}}, ...]

Query: {query}

Documents:
{numbered}
"""
        try:
            data = json.loads(await llm.generate(prompt, json_mode=True))
            if isinstance(data, list) and len(data) == len(documents):
                return [GradingResult(**item) for item in data]
        except Exception as e:
            print(f"DocumentGrader batch error: {e}")
            if isinstance(e, llm.RETRYABLE):
                return [GradingResult(relevance="correct", confidence=0.0, reason="grader unavailable") for _ in documents]
        return list(await asyncio.gather(*[self.grade_relevance(query, d) for d in documents]))

    async def filter_irrelevant(self, query: str, results: List[SearchResult]) -> List[SearchResult]:
        filtered = []
        for res in results:
            grading = await self.grade_relevance(query, res.content)
            if grading.relevance in ["correct", "ambiguous"]:
                filtered.append(res)
        return filtered

document_grader = DocumentGrader()
