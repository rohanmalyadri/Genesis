import json
from typing import List

from app.models import SearchResult
from services import llm

RRF_K = 60


class GeminiReranker:
    """LLM reranker that is blended with the retriever's own (PageRank-boosted) order.

    The final order fuses two rankings with reciprocal rank fusion: the LLM's
    relevance order and the incoming order (RRF + PageRank authority). Authority
    mode gives the incoming order a larger weight so authority actually matters.
    """

    async def _llm_order(self, query: str, results: List[SearchResult]) -> List[int]:
        docs_text = "\n".join(f"ID {i}: {res.content[:1200]}" for i, res in enumerate(results))
        prompt = f"""Rerank the following documents based on their relevance to the query.
Return ONLY a JSON array of document numbers, most relevant first, e.g. [2, 0, 1].

Query: {query}
Documents:
{docs_text}
"""
        raw = json.loads(await llm.generate(prompt, json_mode=True))
        order: List[int] = []
        for item in raw if isinstance(raw, list) else []:
            try:
                idx = int(str(item).replace("ID", "").strip())
            except ValueError:
                continue
            if 0 <= idx < len(results) and idx not in order:
                order.append(idx)
        return order

    async def rerank(self, query: str, results: List[SearchResult], top_n: int = 5, authority_weight: float = 1.0) -> List[SearchResult]:
        if not results:
            return []
        if len(results) == 1:
            return results[:top_n]

        try:
            llm_order = await self._llm_order(query, results)
        except Exception as e:
            print(f"Reranker: LLM rerank failed ({type(e).__name__}: {e}); keeping retrieval order.")
            return results[:top_n]

        llm_rank = {idx: pos for pos, idx in enumerate(llm_order)}
        worst = len(results)  # documents the LLM did not mention rank last
        fused = []
        for original_pos, res in enumerate(results):
            score = 1.0 / (RRF_K + llm_rank.get(original_pos, worst) + 1)
            score += authority_weight / (RRF_K + original_pos + 1)
            fused.append((score, original_pos, res))
        fused.sort(key=lambda x: (-x[0], x[1]))
        return [res for _, _, res in fused[:top_n]]

reranker = GeminiReranker()
