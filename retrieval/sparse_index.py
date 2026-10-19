"""BM25 sparse index backed by a Redis list of JSON documents.

Documents are appended incrementally on ingest (no re-pickling the corpus). The
BM25 model is rebuilt lazily in memory, and only when the list length changed.
Everything stored in Redis is plain JSON, never pickle.
"""
import asyncio
import json
import re
from typing import Any, Dict, List, Optional

import redis.asyncio as redis
from rank_bm25 import BM25Okapi

from app.config import settings
from app.models import SearchResult

_TOKEN = re.compile(r"\w+")


def tokenize(text: str) -> List[str]:
    return _TOKEN.findall(text.lower())


class SparseIndex:
    key = "bm25:docs"

    def __init__(self):
        self.redis = redis.from_url(settings.REDIS_URL)
        self._bm25: Optional[BM25Okapi] = None
        self._docs: List[Dict[str, Any]] = []
        self._token_sets: List[set] = []
        self._loaded_len = -1
        self._lock = asyncio.Lock()

    async def add(self, docs: List[Dict[str, Any]]) -> None:
        """docs: [{"id", "content", "metadata", "collection"}]"""
        if not docs:
            return
        await self.redis.rpush(self.key, *[json.dumps(d) for d in docs])

    async def _ensure_loaded(self) -> None:
        length = await self.redis.llen(self.key)
        if length == self._loaded_len:
            return
        async with self._lock:
            length = await self.redis.llen(self.key)
            if length == self._loaded_len:
                return
            raw = await self.redis.lrange(self.key, 0, -1)
            latest: Dict[tuple, Dict[str, Any]] = {}
            for item in raw:
                doc = json.loads(item)
                # re-ingested chunks replace older ones, per collection
                latest[(doc.get("collection"), doc["id"])] = doc
            docs = list(latest.values())
            loop = asyncio.get_running_loop()
            self._bm25 = await loop.run_in_executor(
                None, lambda: BM25Okapi([tokenize(d["content"]) for d in docs]) if docs else None
            )
            self._docs = docs
            self._token_sets = [set(tokenize(d["content"])) for d in docs]
            self._loaded_len = length

    async def search(
        self,
        query: str,
        limit: int = 50,
        collection: Optional[str] = None,
        source_type: Optional[str] = None,
        document_id: Optional[str] = None,
    ) -> List[SearchResult]:
        try:
            await self._ensure_loaded()
        except Exception as e:
            print(f"SparseIndex: could not load index: {e}")
            return []
        if not self._bm25 or not self._docs:
            return []

        query_tokens = tokenize(query)
        scores = self._bm25.get_scores(query_tokens)
        # BM25 gives zero/negative weight to terms found in half or more of the documents,
        # which happens in small knowledge bases. Any chunk that shares a query term is still a
        # keyword match, so overlap count is added as a small tie-breaker.
        overlap = [len(self._token_sets[i].intersection(query_tokens)) for i in range(len(scores))]
        final = [max(float(scores[i]), 0.0) + 0.01 * overlap[i] for i in range(len(scores))]
        order = sorted(range(len(final)), key=lambda i: final[i], reverse=True)
        results: List[SearchResult] = []
        for i in order:
            if overlap[i] == 0 or len(results) >= limit:
                break
            doc = self._docs[i]
            meta = doc.get("metadata", {})
            if collection and doc.get("collection") != collection:
                continue
            if source_type and meta.get("source_type") != source_type:
                continue
            if document_id and meta.get("document_id") != document_id:
                continue
            results.append(SearchResult(
                id=doc["id"], content=doc["content"], metadata=meta, score=final[i]
            ))
        return results

    async def count(self) -> int:
        return await self.redis.llen(self.key)


sparse_index = SparseIndex()
