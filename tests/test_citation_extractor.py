import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from pipeline.citation_extractor import CitationExtractor, citation_extractor

@pytest.fixture
def extractor():
    return CitationExtractor()

@pytest.mark.parametrize("content, expected_target, expected_type", [
    # Hyperlink tests
    ("Visit https://google.com/search?q=test for more info.", "https://google.com/search/", "hyperlink"),
    ("Check http://openai.com/blog/ as well.", "http://openai.com/blog/", "hyperlink"),
    
    # Cross-reference tests
    ("As described in Section 4.2 of the manual.", "4.2", "crossref"),
    ("See [Smith2023] for details.", "Smith2023", "crossref"),
    ("Refer to Appendix B for charts.", "Appendix B", "crossref"),
    
    # Footnote/Endnote tests
    ("This claim is supported by evidence [1].", "1", "footnote"),
    ("Multiple sources agree (Jones, 2022).", "Jones, 2022", "footnote"),
    ("The same point was made ibid.", "ibid", "footnote"),
])
def test_extraction_logic(extractor, content, expected_target, expected_type):
    edges = extractor.extract("doc_source", content, {})
    
    # Check if target exists in edges
    found = False
    for edge in edges:
        if edge.target_doc_id == expected_target and edge.citation_type == expected_type:
            found = True
            break
    assert found, f"Target {expected_target} with type {expected_type} not found in {edges}"

def test_weight_aggregation(extractor):
    content = "Check https://test.com. Also see https://test.com again."
    edges = extractor.extract("source", content, {})
    
    # Hyperlink weight is 1.0. Two citations should be 2.0.
    target_edge = next(e for e in edges if e.target_doc_id == "https://test.com/")
    assert target_edge.weight == 2.0

def test_weight_capping(extractor):
    # Footnote weight is 0.6. 6 citations = 3.6, should cap at 3.0.
    content = "Data [1], more data [1], even more [1], still more [1], lots [1], finally [1]."
    edges = extractor.extract("source", content, {})
    
    target_edge = next(e for e in edges if e.target_doc_id == "1")
    assert target_edge.weight == 3.0

@pytest.mark.asyncio
async def test_redis_storage(extractor):
    mock_redis = MagicMock()
    mock_pipe = AsyncMock()
    mock_redis.pipeline.return_value.__aenter__.return_value = mock_pipe
    
    with patch("redis.asyncio.from_url", return_value=mock_redis):
        edges = extractor.extract("source", "https://google.com [1]", {})
        await extractor.store_edges(edges)
        
        # Verify zadd and rpush were called
        assert mock_pipe.zadd.call_count >= 2
        assert mock_pipe.rpush.call_count >= 2
        assert mock_pipe.execute.called
