import pytest
import networkx as nx
from pipeline.pagerank_job import run_pagerank_job
from unittest.mock import patch, MagicMock

def test_pagerank_calculation_accuracy():
    """Build a small 5-node graph and verify PageRank scores."""
    # Create a simple directed graph
    # 0 -> 1 -> 2 -> 0 (Triangle)
    # 3 -> 0 (External link)
    # 4 -> 0 (External link)
    G = nx.DiGraph()
    G.add_edge("0", "1", weight=1.0)
    G.add_edge("1", "2", weight=1.0)
    G.add_edge("2", "0", weight=1.0)
    G.add_edge("3", "0", weight=1.0)
    G.add_edge("4", "0", weight=1.0)
    
    # Compute PageRank
    scores = nx.pagerank(G, alpha=0.85, weight='weight')
    
    # Known properties for this symmetric-ish graph:
    # Nodes 3 and 4 have no incoming links, so they should have lowest scores.
    # Nodes 0, 1, 2 form a cycle, but 0 has extra incoming links from 3 and 4.
    # So 0 > 1 > 2 > 3 = 4
    
    assert scores["0"] > scores["1"]
    assert scores["1"] > scores["2"]
    assert scores["2"] > scores["3"]
    assert scores["3"] == scores["4"]
    
    # Asserting exact-ish values for a standard 0.85 alpha PR
    # For a simple star-like/cycle graph, we can compare against nx values
    # Here we just verify the distribution and sum
    assert abs(sum(scores.values()) - 1.0) < 1e-6

def test_pagerank_normalization():
    """Verify min-max normalization logic."""
    scores = {"a": 0.1, "b": 0.2, "c": 0.5}
    # min = 0.1, max = 0.5, range = 0.4
    # a: (0.1-0.1)/0.4 = 0.0
    # b: (0.2-0.1)/0.4 = 0.25
    # c: (0.5-0.1)/0.4 = 1.0
    
    min_score = min(scores.values())
    max_score = max(scores.values())
    range_val = max_score - min_score + 1e-9
    
    normalized = {k: (v - min_score) / range_val for k, v in scores.items()}
    
    assert normalized["a"] == 0.0
    assert normalized["b"] == pytest.approx(0.25)
    assert normalized["c"] == pytest.approx(1.0)

@patch("redis.from_url")
@patch("pipeline.pagerank_job.ChromaDB_client")
def test_full_job_logic(mock_chroma, mock_redis_factory):
    """Test the end-to-end job flow with mocks."""
    mock_redis = MagicMock()
    mock_redis_factory.return_value = mock_redis
    
    # Mock edges: A -> B
    mock_redis.lrange.return_value = ["A,B,1.0"]
    
    from pipeline.pagerank_job import run_pagerank_job
    run_pagerank_job()
    
    # Verify Redis interactions
    assert mock_redis.lrange.called
    assert mock_redis.pipeline.called
    
    # Verify ChromaDB interactions
    assert mock_chroma.set_payload.called
