import pytest
import math
from retrieval.hybrid_retriever import ChromaHybridRetriever
from app.models import SearchResult, FilterParams
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_pagerank_boosting_formula():
    """Verify that PageRank boosting correctly re-orders and calculates scores."""
    retriever = ChromaHybridRetriever()
    
    # Mock search results
    # Doc 0: High RRF, No PR (will default to 0.05)
    # Doc 1: Medium RRF, High PR (1.0) -> Should jump to #1
    # Doc 2: Low RRF, Explicitly Zero PR (0.0) -> Should stay low, boost=1.0
    
    dense_results = [
        SearchResult(id="0", content="c0", metadata={}, score=0.9),
        SearchResult(id="1", content="c1", metadata={"pagerank_score": 1.0}, score=0.8),
        SearchResult(id="2", content="c2", metadata={"pagerank_score": 0.0}, score=0.1),
    ]
    
    # Mocking dependencies
    retriever._dense_search = AsyncMock(return_value=dense_results)
    retriever._sparse_search = AsyncMock(return_value=[])
    
    # Run standard search (alpha = 0.3)
    results = await retriever.search("test", limit=3)
    
    # Verify IDs are in correct boosted order
    # Doc 1 (PR 1.0) gets ~21% boost, while Doc 0 (default 0.05) gets ~1.4% boost
    # This should be enough to swap 1 and 0 given their close RRF scores
    assert results[0].id == "1"
    assert results[1].id == "0"
    assert results[2].id == "2"
    
    # Step 4: Assert exact rule for pagerank_score=0.0
    doc_2 = next(r for r in results if r.id == "2")
    assert doc_2.pagerank_score == 0.0
    assert doc_2.boosted_score == pytest.approx(doc_2.rrf_score)
    
    # Step 5: Test authority_mode=True (alpha = 0.6)
    filters = FilterParams(authority_mode=True)
    results_auth = await retriever.search("test", limit=3, filters=filters)
    
    doc_1_auth = next(r for r in results_auth if r.id == "1")
    # boosted = rrf * (1 + 0.6 * log(1 + 1.0))
    expected_boost = 1 + 0.6 * math.log(2.0)
    assert doc_1_auth.boosted_score == pytest.approx(doc_1_auth.rrf_score * expected_boost)

@pytest.mark.asyncio
async def test_cold_start_handler():
    """Verify that documents missing PageRank score get a default 0.05 boost."""
    retriever = ChromaHybridRetriever()
    
    # Doc with no metadata
    dense_results = [SearchResult(id="new_doc", content="fresh", metadata={}, score=0.5)]
    retriever._dense_search = AsyncMock(return_value=dense_results)
    retriever._sparse_search = AsyncMock(return_value=[])
    
    results = await retriever.search("test", limit=1)
    
    assert results[0].pagerank_score == 0.05
    expected_boost = 1 + 0.3 * math.log(1.05)
    assert results[0].boosted_score == pytest.approx(results[0].rrf_score * expected_boost)
