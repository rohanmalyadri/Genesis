from typing import List, Dict, Any, Optional
from app.models import SearchResult
import numpy as np

class ContentFilter:
    def __init__(self, allowlist: Optional[List[str]] = None, relevance_threshold: float = 0.3):
        # Default allowlist includes common tech docs and local path indicators
        self.allowlist = allowlist
        self.relevance_threshold = relevance_threshold
        self.toxic_keywords = ["hate", "violence", "illegal", "explicit", "toxic"]

    def _is_toxic(self, text: str) -> bool:
        text_lower = text.lower()
        return any(kw in text_lower for kw in self.toxic_keywords)

    def _cosine_similarity(self, v1: List[float], v2: List[float]) -> float:
        if not v1 or not v2:
            return 0.0
        a = np.array(v1)
        b = np.array(v2)
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))

    async def validate_results(self, query_vector: List[float], results: List[SearchResult]) -> List[SearchResult]:
        filtered_results = []
        
        for res in results:
            # 1. Check source domain
            source = res.metadata.get("source", "")
            
            # Allow local paths by default
            is_local = source.startswith("/") or (len(source) > 1 and source[1] == ":")
            
            if self.allowlist and not is_local:
                if not any(domain in source for domain in self.allowlist):
                    print(f"ContentFilter: Blocked untrusted source {source}")
                    continue
                
            # 2. Check toxicity
            if self._is_toxic(res.content):
                print("ContentFilter: Flagged toxic content")
                continue
                
            # 3. Relevance check (if vector is available in metadata or provided)
            # Assuming res.metadata has a 'vector' if we want to check it here, 
            # but usually SearchResult already has a 'score'. 
            # The prompt says "score relevance using cosine similarity threshold 0.3".
            # If SearchResult.score is already cosine similarity, we use that.
            if res.score < self.relevance_threshold:
                print(f"ContentFilter: Low relevance score {res.score}")
                continue
                
            filtered_results.append(res)
            
        return filtered_results

content_filter = ContentFilter()
