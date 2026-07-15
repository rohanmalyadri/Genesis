import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from routes.query import pipeline_step_1_guard, pipeline_step_2_cache, pipeline_step_6_agent
from app.models import QueryRequest, SearchResult, CRAGResult

@pytest.mark.asyncio
async def test_pipeline_security_guard():
    # Test that security guard stops unsafe input
    request = QueryRequest(query="'; DROP TABLE users; --")
    state = {"request": request, "metadata": {}, "logs": []}
    
    # Should raise HTTPException or return early
    # Step 1 logic: if not res.safe: raise HTTPException
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as excinfo:
        await pipeline_step_1_guard(state)
    assert excinfo.value.status_code == 400

@pytest.mark.asyncio
async def test_pipeline_cache_hit():
    # Test that cache hit skips retrieval
    request = QueryRequest(query="What is RAG?")
    state = {"request": request, "metadata": {}, "logs": []}
    
    mock_cache_res = [SearchResult(content="RAG is Retrieval Augmented Generation", metadata={"source": "cache"}, score=1.0)]
    
    with patch("services.semantic_cache.semantic_cache.lookup", return_value=mock_cache_res):
        next_step = await pipeline_step_2_cache(state)
        assert state["metadata"]["cache_hit"] is True
        assert state["documents"] == mock_cache_res
        assert next_step == "step_10_format"

@pytest.mark.asyncio
async def test_pipeline_agent_routing():
    # Test that agent correctly processes documents
    request = QueryRequest(query="Test query")
    docs = [SearchResult(content="Test content", metadata={"source": "local"}, score=0.8)]
    state = {
        "request": request,
        "documents": docs,
        "metadata": {},
        "logs": []
    }
    
    mock_crag_res = CRAGResult(
        documents=docs,
        path="correct",
        metadata={"grading": "relevant"}
    )
    
    with patch("agents.crag.crag_agent.run", return_value=mock_crag_res):
        await pipeline_step_6_agent(state)
        assert state["documents"] == docs
        assert state["metadata"]["agent_path"] == "correct"
