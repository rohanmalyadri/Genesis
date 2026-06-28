from fastapi import APIRouter, Query
from typing import List
from app.models import RetrievedDoc
from retrieval.hybrid_retriever import hybrid_retriever
from retrieval.reranker import cohere_reranker

router = APIRouter()

@router.get("/")
async def debug_search(
    q: str = Query(..., min_length=1),
    top_k: int = 10,
    use_sharding: bool = Query(True),
    authority_mode: bool = Query(False),
    use_reasoning: bool = Query(False)
):
    """Debug endpoint to inspect raw retrieval and reranking scores."""
    from retrieval.filters import FilterParams
    from services.query_decomposer import query_decomposer
    
    filters = FilterParams(authority_mode=authority_mode)
    
    search_queries = [q]
    if use_reasoning:
        search_queries = await query_decomposer.decompose(q)
    
    all_raw_results = []
    for query_str in search_queries:
        res = await hybrid_retriever.search(query_str, limit=20, use_sharding=use_sharding, filters=filters)
        all_raw_results.extend(res)
    
    # Deduplicate results by ID
    unique_results = {}
    for doc in all_raw_results:
        if doc.id not in unique_results:
            unique_results[doc.id] = doc
        else:
            # Keep the highest score
            if doc.boosted_score > unique_results[doc.id].boosted_score:
                unique_results[doc.id] = doc
    
    raw_results = list(unique_results.values())
    
    # 2. Reranking
    reranked_results = await cohere_reranker.rerank(q, raw_results, top_n=top_k)
    
    return {
        "query": q,
        "decomposed_queries": search_queries if use_reasoning else None,
        "results": reranked_results
    }
