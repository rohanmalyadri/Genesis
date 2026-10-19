import asyncio
import math
import time
from contextvars import ContextVar
from typing import Any, Dict, List, Optional

from app.config import settings
from app.models import RetrievedDoc, FilterParams, SearchResult
from retrieval.chroma_shard_manager import shard_manager
from retrieval.sparse_index import sparse_index
from pipeline.embedder import embedder

SHARD_TIMEOUT_SECONDS = 15

_shard_stats: ContextVar[Dict[str, Any]] = ContextVar("shard_stats", default={})


def _build_where(filters: Optional[FilterParams]) -> Optional[dict]:
    """Translate FilterParams into a Chroma where clause (None when empty)."""
    if not filters:
        return None
    conditions = []
    if filters.source_type:
        conditions.append({"source_type": filters.source_type})
    if filters.document_id:
        conditions.append({"document_id": filters.document_id})
    if filters.date_gte:
        conditions.append({"date": {"$gte": filters.date_gte}})
    if filters.date_lte:
        conditions.append({"date": {"$lte": filters.date_lte}})
    if not conditions:
        return None
    return conditions[0] if len(conditions) == 1 else {"$and": conditions}


def _to_results(raw: dict, extra_meta: Optional[dict] = None) -> List[SearchResult]:
    docs = []
    if raw and raw.get("ids") and raw["ids"][0]:
        for i, doc_id in enumerate(raw["ids"][0]):
            meta = dict(raw["metadatas"][0][i] or {})
            if extra_meta:
                meta.update(extra_meta)
            docs.append(SearchResult(
                id=doc_id,
                content=raw["documents"][0][i],
                metadata=meta,
                score=1.0 - raw["distances"][0][i],
            ))
    return docs


class ChromaHybridRetriever:
    @property
    def last_shard_stats(self) -> Dict[str, Any]:
        """Stats of the most recent search made in the current request context."""
        return _shard_stats.get()

    async def _query_shard(self, shard_id: int, query_vec: List[float], limit: int, where: Optional[dict]) -> Dict[str, Any]:
        start = time.time()
        collection = shard_manager.get_collection(shard_id)
        loop = asyncio.get_running_loop()
        results = await loop.run_in_executor(None, lambda: collection.query(
            query_embeddings=[query_vec],
            n_results=limit,
            where=where,
            include=["documents", "metadatas", "distances"],
        ))
        return {"shard_id": shard_id, "results": results, "latency": (time.time() - start) * 1000}

    async def _dense_search(self, query_vec: List[float], limit: int, filters: Optional[FilterParams], use_sharding: bool = True) -> tuple[List[SearchResult], Dict[str, Any]]:
        where = _build_where(filters)
        loop = asyncio.get_running_loop()

        if not use_sharding:
            collection = shard_manager.get_enterprise_collection()
            if collection.count() == 0:
                return [], {}
            raw = await loop.run_in_executor(None, lambda: collection.query(
                query_embeddings=[query_vec],
                n_results=limit,
                where=where,
                include=["documents", "metadatas", "distances"],
            ))
            return _to_results(raw), {}

        # A document's chunks all live on one shard, so a document filter hits one shard
        if filters and filters.document_id:
            target_shards = [await shard_manager.get_shard_for_doc(filters.document_id)]
        else:
            target_shards = list(range(settings.NUM_SHARDS))

        async def guarded(sid: int):
            return await asyncio.wait_for(
                self._query_shard(sid, query_vec, limit, where), timeout=SHARD_TIMEOUT_SECONDS
            )

        responses = await asyncio.gather(*[guarded(sid) for sid in target_shards], return_exceptions=True)

        all_docs: List[SearchResult] = []
        stats: Dict[str, Any] = {}
        for sid, resp in zip(target_shards, responses):
            if isinstance(resp, Exception):
                print(f"HybridRetriever: shard {sid} failed: {resp!r}")
                stats[str(sid)] = {"hits": 0, "latency_ms": 0, "error": str(resp) or type(resp).__name__}
                continue
            hits = 0
            for doc in _to_results(resp["results"], {"shard_id": sid}):
                if filters and filters.entity_names:
                    ents = [e.strip() for e in str(doc.metadata.get("entities", "")).split(",") if e.strip()]
                    if not any(e in ents for e in filters.entity_names):
                        continue
                hits += 1
                all_docs.append(doc)
            stats[str(sid)] = {"hits": hits, "latency_ms": resp["latency"]}

        return all_docs, stats

    async def search(self, query: str, limit: int = 10, filters: Optional[FilterParams] = None, use_sharding: bool = True) -> List[RetrievedDoc]:
        query_vec = await embedder.embed_text(query)
        candidate_limit = max(limit * 4, 20)

        (dense_results, stats), sparse_results = await asyncio.gather(
            self._dense_search(query_vec, candidate_limit, filters, use_sharding),
            sparse_index.search(
                query,
                limit=candidate_limit,
                collection="sharded" if use_sharding else "enterprise",
                source_type=filters.source_type if filters else None,
                document_id=filters.document_id if filters else None,
            ),
        )

        _shard_stats.set(stats)

        # Reciprocal Rank Fusion. Dense and sparse hits share chunk ids, so a chunk
        # found by both lists gets both contributions.
        k = 60
        rrf: Dict[str, float] = {}
        docs: Dict[str, SearchResult] = {}
        dense_scores: Dict[str, float] = {}
        bm25_scores: Dict[str, float] = {}

        for rank, res in enumerate(dense_results):
            rrf[res.id] = rrf.get(res.id, 0.0) + 1.0 / (k + rank + 1)
            docs[res.id] = res
            dense_scores[res.id] = res.score
        for rank, res in enumerate(sparse_results):
            rrf[res.id] = rrf.get(res.id, 0.0) + 1.0 / (k + rank + 1)
            docs.setdefault(res.id, res)
            bm25_scores[res.id] = res.score

        alpha = settings.PAGERANK_ALPHA
        if filters and filters.authority_mode:
            alpha *= 2.0

        fused: List[RetrievedDoc] = []
        for doc_id in sorted(rrf, key=lambda x: rrf[x], reverse=True)[:max(limit, 20)]:
            res = docs[doc_id]
            pr_score = float(res.metadata.get("pagerank_score", 0.05))
            boosted = rrf[doc_id] * (1 + alpha * math.log(1 + pr_score))
            fused.append(RetrievedDoc(
                id=doc_id,
                content=res.content,
                metadata=res.metadata,
                score=boosted,
                dense_score=dense_scores.get(doc_id, 0.0),
                bm25_score=bm25_scores.get(doc_id, 0.0),
                rrf_score=rrf[doc_id],
                pagerank_score=pr_score,
                boosted_score=boosted,
            ))

        fused.sort(key=lambda x: x.boosted_score, reverse=True)
        return fused[:limit]

hybrid_retriever = ChromaHybridRetriever()
