import chromadb
import asyncio
import redis.asyncio as redis
import pickle
import os
import time
import math
from typing import List, Optional, Dict, Any
from app.config import settings
from app.models import RetrievedDoc, FilterParams, SearchResult
from retrieval.chroma_shard_manager import shard_manager
from pipeline.embedder import embedder

class ChromaHybridRetriever:
    def __init__(self):
        self.redis = redis.from_url(settings.REDIS_URL)
        self.last_shard_stats = {}

    async def _query_shard(self, shard_id: int, query_vec: List[float], limit: int, where: dict, filters: Optional[FilterParams]) -> Dict[str, Any]:
        start_time = time.time()
        collection = shard_manager.get_collection(shard_id)
        
        # We need to run collection.query in a thread since it's blocking
        loop = asyncio.get_event_loop()
        results = await loop.run_in_executor(None, lambda: collection.query(
            query_embeddings=[query_vec],
            n_results=limit,
            where=where,
            include=["documents", "metadatas", "distances"]
        ))
        
        latency = (time.time() - start_time) * 1000
        return {
            "shard_id": shard_id,
            "results": results,
            "latency": latency
        }

    async def _dense_search(self, query_vec: List[float], limit: int, filters: Optional[FilterParams], use_sharding: bool = True) -> List[SearchResult]:
        where = {}
        if filters:
            conditions = []
            if filters.source_type:
                conditions.append({"source_type": filters.source_type})
            
            # Date range filtering (assuming metadata 'date' is ISO string)
            if filters.date_gte:
                conditions.append({"date": {"$gte": filters.date_gte}})
            if filters.date_lte:
                conditions.append({"date": {"$lte": filters.date_lte}})
                
            if len(conditions) > 1:
                where = {"$and": conditions}
            elif len(conditions) == 1:
                where = conditions[0]
        
        if not use_sharding:
            # Query the single enterprise collection
            collection = shard_manager.get_enterprise_collection()
            loop = asyncio.get_event_loop()
            results = await loop.run_in_executor(None, lambda: collection.query(
                query_embeddings=[query_vec],
                n_results=limit,
                where=where,
                include=["documents", "metadatas", "distances"]
            ))
            
            all_docs = []
            if results["ids"] and len(results["ids"]) > 0:
                for i in range(len(results["ids"][0])):
                    all_docs.append(SearchResult(
                        id=results["ids"][0][i],
                        content=results["documents"][0][i],
                        metadata=results["metadatas"][0][i],
                        score=1.0 - results["distances"][0][i]
                    ))
            return all_docs

        # Determine which shards to query (Original Sharding Logic)
        if filters and filters.document_id:
            shard_id = await shard_manager.get_shard_for_doc(filters.document_id)
            target_shards = [shard_id]
        else:
            target_shards = list(range(settings.NUM_SHARDS))

        # Parallel fan-out
        shard_tasks = [self._query_shard(sid, query_vec, 20, where, filters) for sid in target_shards]
        shard_responses = await asyncio.gather(*shard_tasks)
        
        all_docs = []
        shard_stats = {}
        
        for resp in shard_responses:
            sid = resp["shard_id"]
            results = resp["results"]
            latency = resp["latency"]
            
            hits = 0
            if results["ids"] and len(results["ids"]) > 0:
                for i in range(len(results["ids"][0])):
                    metadata = results["metadatas"][0][i]
                    
                    # Post-retrieval filtering for entities
                    # Since 'entities' is stored as a string "Entity1,Entity2"
                    if filters and filters.entity_names:
                        doc_entities = metadata.get("entities", "").split(",")
                        doc_entities = [e.strip() for e in doc_entities if e.strip()]
                        # Check if any requested entity is in the document
                        if not any(e in doc_entities for e in filters.entity_names):
                            continue

                    hits += 1
                    metadata["shard_id"] = sid
                    all_docs.append(SearchResult(
                        id=results["ids"][0][i],
                        content=results["documents"][0][i],
                        metadata=metadata,
                        score=1.0 - results["distances"][0][i]
                    ))
            
            shard_stats[sid] = {"hits": hits, "latency_ms": latency}
            
        # Store shard stats in a way that can be retrieved later if needed
        self.last_shard_stats = shard_stats
        return all_docs

    async def _sparse_search(self, query: str, limit: int) -> List[SearchResult]:
        try:
            bm25_data = await self.redis.get("bm25:corpus")
            if not bm25_data:
                return []
            
            # Data is pickled as (bm25, list_of_dicts_with_content_and_metadata)
            bm25, doc_data = pickle.loads(bm25_data)
            tokenized_query = query.lower().split()
            scores = bm25.get_scores(tokenized_query)
            
            # Sort and get top results
            import numpy as np
            top_indices = np.argsort(scores)[::-1][:limit]
            
            results = []
            for i in top_indices:
                if scores[i] > 0:
                    results.append(SearchResult(
                        id=f"sparse_{i}",
                        content=doc_data[i]["content"],
                        metadata=doc_data[i]["metadata"],
                        score=float(scores[i])
                    ))
            return results
        except Exception as e:
            print(f"Sparse search error: {e}")
            return []

    async def search(self, query: str, limit: int = 10, filters: Optional[FilterParams] = None, use_sharding: bool = True) -> List[RetrievedDoc]:
        query_vec = await embedder.embed_text(query)
        
        # Get results from both
        dense_results = await self._dense_search(query_vec, limit=50, filters=filters, use_sharding=use_sharding)
        sparse_results = await self._sparse_search(query, limit=50)
        
        # RRF Merging
        k = 60
        scores = {} # id -> rrf_score
        docs = {}   # id -> doc
        
        for i, res in enumerate(dense_results):
            doc_id = res.id or f"dense_{i}"
            scores[doc_id] = scores.get(doc_id, 0) + 1.0 / (k + i + 1)
            docs[doc_id] = res
            
        for i, res in enumerate(sparse_results):
            doc_id = res.id or f"sparse_{i}"
            scores[doc_id] = scores.get(doc_id, 0) + 1.0 / (k + i + 1)
            if doc_id not in docs:
                docs[doc_id] = res
                
        # Sort by RRF score
        sorted_ids = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)
        
        # PageRank Boosting
        alpha = settings.PAGERANK_ALPHA
        if filters and filters.authority_mode:
            alpha *= 2.0 # Step 5: Increase alpha to 0.6 if authority_mode is True
            
        fused_results = []
        for doc_id in sorted_ids[:20]: # Step 1: Process top-20 candidates
            res = docs[doc_id]
            # Step 1 & 6: Fetch pagerank_score from metadata, default to 0.05 for cold-start
            pr_score = res.metadata.get("pagerank_score", 0.05)
            rrf_score = scores[doc_id]
            
            # Step 2: Compute boosted score
            boosted_score = rrf_score * (1 + alpha * math.log(1 + pr_score))
            
            fused_results.append(RetrievedDoc(
                id=doc_id,
                content=res.content,
                metadata=res.metadata,
                score=boosted_score,
                dense_score=getattr(res, 'score', 0.0),
                bm25_score=0.0,
                rrf_score=rrf_score,
                pagerank_score=pr_score,
                boosted_score=boosted_score
            ))
            
        # Step 3: Re-sort by boosted_score
        fused_results.sort(key=lambda x: x.boosted_score, reverse=True)
        
        return fused_results[:limit]

hybrid_retriever = ChromaHybridRetriever()
