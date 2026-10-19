from typing import List, Optional
from app.models import SearchResult
import numpy as np

class ContentFilter:
    def __init__(self, allowlist: Optional[List[str]] = None, relevance_threshold: float = 0.15):
        self.allowlist = allowlist
        self.relevance_threshold = relevance_threshold
        self.toxic_keywords = ["hate", "violence", "illegal", "explicit", "toxic"]

    def _is_toxic(self, text: str) -> bool:
        text_lower = text.lower()
        return any(kw in text_lower for kw in self.toxic_keywords)

    def _cosine_similarity(self, v1: List[float], v2: List[float]) -> float:
        if not v1 or not v2:
            return 0.0
        a, b = np.array(v1), np.array(v2)
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))

    def _relevance(self, res: SearchResult) -> Optional[float]:
        """Cosine similarity of the chunk to the query.

        None means "skip the cosine check": the chunk was matched by keywords (BM25),
        which is independent evidence of relevance, so a low embedding score alone
        must not discard it.
        """
        dense = getattr(res, "dense_score", None)
        if dense is None:
            return res.score
        if dense <= 0 or (getattr(res, "bm25_score", 0) or 0) > 0:
            return None
        return dense

    async def validate_results(self, query_vector: List[float], results: List[SearchResult]) -> List[SearchResult]:
        filtered = []
        for res in results:
            source = res.metadata.get("source", "")
            is_local = source.startswith("/") or (len(source) > 1 and source[1] == ":")
            if self.allowlist and not is_local and not any(d in source for d in self.allowlist):
                print(f"ContentFilter: Blocked untrusted source {source}")
                continue

            if self._is_toxic(res.content):
                print("ContentFilter: Flagged toxic content")
                continue

            # Keyword (BM25) only hits have no cosine score, so they skip this check
            relevance = self._relevance(res)
            if relevance is not None and relevance < self.relevance_threshold:
                print(f"ContentFilter: Low relevance score {relevance:.3f}")
                continue

            filtered.append(res)
        return filtered

content_filter = ContentFilter()
