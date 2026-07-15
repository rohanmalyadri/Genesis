import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from retrieval.chroma_shard_manager import shard_manager
from retrieval.hybrid_retriever import hybrid_retriever
from pipeline.indexer import indexer
from app.models import Chunk, DocumentMetadata, FilterParams
from datetime import datetime

# Mock Redis and ChromaDB
@pytest.fixture(autouse=True)
def mock_services():
    with patch("redis.asyncio.from_url") as mock_redis_url, \
         patch("chromadb.PersistentClient") as mock_chroma:
        
        mock_redis = AsyncMock()
        mock_redis_url.return_value = mock_redis
        
        mock_client = mock_chroma.return_value
        mock_collection = MagicMock()
        mock_client.get_or_create_collection.return_value = mock_collection
        
        # Mock query results
        mock_collection.query.return_value = {
            "ids": [["test_id"]],
            "documents": [["test content"]],
            "metadatas": [[{"title": "test doc"}]],
            "distances": [[0.1]]
        }
        mock_collection.count.return_value = 10
        
        # Setup shard_manager with mocks
        shard_manager.redis = mock_redis
        shard_manager.client = mock_client
        
        yield mock_redis, mock_client

@pytest.mark.asyncio
async def test_consistent_hash_distribution():
    """Test that document IDs are distributed across shards."""
    doc_ids = [f"doc_{i}" for i in range(100)]
    shard_counts = {}
    
    for doc_id in doc_ids:
        shard_id = shard_manager.get_shard_id(doc_id)
        shard_counts[shard_id] = shard_counts.get(shard_id, 0) + 1
    
    # Check that we are using multiple shards (not all hashed to the same one)
    assert len(shard_counts) > 1
    # For 100 docs and 16 shards, most should have some docs
    assert sum(shard_counts.values()) == 100

@pytest.mark.asyncio
async def test_parallel_fanout_retrieval():
    """Test that retrieval queries all shards and merges results."""
    # Index some test data into different shards
    test_chunks = [
        Chunk(
            id=f"test_doc_{i}",
            content=f"Content for document {i} which is very unique",
            embedding=[0.1] * 1536,
            metadata=DocumentMetadata(
                title=f"Doc {i}",
                source_type="test"
            )
        ) for i in range(20)
    ]
    
    await indexer.index_chunks(test_chunks)
    
    # Query
    results = await hybrid_retriever.search("unique", limit=5)
    
    assert len(results) > 0
    assert hasattr(hybrid_retriever, "last_shard_stats")
    assert len(hybrid_retriever.last_shard_stats) == 16
    
    # Check if we have hits in multiple shards
    total_hits = sum(s["hits"] for s in hybrid_retriever.last_shard_stats.values())
    assert total_hits > 0

@pytest.mark.asyncio
async def test_smart_routing():
    """Test that providing a document_id filter only queries one shard."""
    doc_id = "test_doc_5"
    filters = FilterParams(document_id=doc_id)
    
    # We need to make sure the mapping exists in Redis
    shard_id = await shard_manager.get_shard_for_doc(doc_id)
    
    query_vec = [0.1] * 1536
    results = await hybrid_retriever._dense_search(query_vec, limit=5, filters=filters)
    
    # Check shard stats - only 1 shard should have been queried
    queried_shards = [sid for sid, stats in hybrid_retriever.last_shard_stats.items() if stats.get("latency_ms", 0) > 0]
    
    # Depending on implementation, we might still have entries for all shards in the dict, 
    # but only one should have been actually queried (tasks were only for target_shards)
    assert len(hybrid_retriever.last_shard_stats) == 1 # In my implementation, I only return stats for target_shards
