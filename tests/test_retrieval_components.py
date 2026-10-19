import pytest
from unittest.mock import AsyncMock

from retrieval.sparse_index import SparseIndex
from retrieval.hybrid_retriever import _build_where
from retrieval.reranker import GeminiReranker
from retrieval.filters import FilterParams
from app.models import SearchResult, RetrievedDoc, CRAGResult, GradingResult
from security.content_filter import ContentFilter


class FakeRedis:
    """Just enough of redis.asyncio for the sparse index."""
    def __init__(self):
        self.items = []

    async def rpush(self, key, *values):
        self.items.extend(values)

    async def llen(self, key):
        return len(self.items)

    async def lrange(self, key, a, b):
        return list(self.items)


def make_index():
    idx = SparseIndex()
    idx.redis = FakeRedis()
    return idx


def doc(i, text, collection="sharded", **meta):
    return {"id": i, "content": text, "metadata": {"filename": i, **meta}, "collection": collection}


@pytest.mark.asyncio
async def test_sparse_index_returns_chunk_ids_and_bm25_scores():
    idx = make_index()
    await idx.add([doc("a_0", "documents are spread over sixteen shards"), doc("b_0", "cats sleep all day"),
                   doc("c_0", "revenue grew in the third quarter")])
    hits = await idx.search("how are documents spread over shards", limit=5)
    assert [h.id for h in hits][0] == "a_0"
    assert hits[0].score > 0


@pytest.mark.asyncio
async def test_sparse_index_keeps_sharded_and_enterprise_copies_apart():
    idx = make_index()
    await idx.add([doc("a_0", "genesis shards documents", "sharded"), doc("a_0", "genesis shards documents", "enterprise"),
                   doc("z_0", "unrelated filler text here", "sharded")])
    assert len(await idx.search("shards", collection="sharded")) == 1
    assert len(await idx.search("shards", collection="enterprise")) == 1


@pytest.mark.asyncio
async def test_sparse_index_reingest_replaces_older_chunk_and_filters_document():
    idx = make_index()
    await idx.add([doc("a_0", "old text about apples", document_id="a")])
    await idx.add([doc("a_0", "new text about oranges", document_id="a"), doc("b_0", "oranges too", document_id="b")])
    hits = await idx.search("oranges", document_id="a")
    assert [h.id for h in hits] == ["a_0"]
    assert await idx.search("apples") == []


def test_sparse_index_stores_json_not_pickle():
    import inspect, retrieval.sparse_index as mod
    assert "pickle" not in inspect.getsource(mod).replace("never pickle", "")


def test_where_clause_has_no_empty_dict_and_supports_document_id():
    assert _build_where(None) is None
    assert _build_where(FilterParams()) is None
    assert _build_where(FilterParams(document_id="d.pdf")) == {"document_id": "d.pdf"}
    both = _build_where(FilterParams(document_id="d.pdf", source_type="pdf"))
    assert both == {"$and": [{"source_type": "pdf"}, {"document_id": "d.pdf"}]}


@pytest.mark.asyncio
async def test_reranker_blends_llm_order_with_authority_order(monkeypatch):
    r = GeminiReranker()
    docs = [SearchResult(id=str(i), content=f"c{i}", metadata={}, score=1.0) for i in range(4)]
    monkeypatch.setattr(r, "_llm_order", AsyncMock(return_value=[3, 2, 1, 0]))  # LLM reverses the order
    # equal weights: two opposite rankings largely cancel, extremes of each list stay on top
    assert [d.id for d in await r.rerank("q", docs, top_n=4)] == ["0", "3", "1", "2"]
    # LLM trusted more by shrinking authority weight
    assert (await r.rerank("q", docs, top_n=1, authority_weight=0.0))[0].id == "3"
    # a strong authority weight keeps the retriever's order
    assert (await r.rerank("q", docs, top_n=1, authority_weight=5.0))[0].id == "0"


@pytest.mark.asyncio
async def test_reranker_falls_back_to_retrieval_order_if_llm_fails(monkeypatch):
    r = GeminiReranker()
    docs = [SearchResult(id=str(i), content="c", metadata={}, score=1.0) for i in range(3)]
    monkeypatch.setattr(r, "_llm_order", AsyncMock(side_effect=RuntimeError("quota")))
    assert [d.id for d in await r.rerank("q", docs, top_n=2)] == ["0", "1"]


@pytest.mark.asyncio
async def test_content_filter_keeps_keyword_only_hits_and_drops_low_cosine():
    cf = ContentFilter()
    keep_dense = RetrievedDoc(id="1", content="x", metadata={}, score=0.01, dense_score=0.5)
    keyword_only = RetrievedDoc(id="2", content="x", metadata={}, score=0.01, dense_score=0.0, bm25_score=4.0)
    irrelevant = RetrievedDoc(id="3", content="x", metadata={}, score=0.01, dense_score=0.02)
    low_cosine_but_keyword_match = RetrievedDoc(id="4", content="x", metadata={}, score=0.01, dense_score=0.12, bm25_score=2.0)
    kept = await cf.validate_results([], [keep_dense, keyword_only, irrelevant, low_cosine_but_keyword_match])
    assert [d.id for d in kept] == ["1", "2", "4"]


@pytest.mark.asyncio
async def test_crag_uses_correct_docs_when_at_least_one_is_correct(monkeypatch):
    from agents.crag import crag_agent
    from services.document_grader import document_grader
    docs = [RetrievedDoc(id=str(i), content=f"c{i}", metadata={}, score=1.0) for i in range(3)]
    grades = [GradingResult(relevance="correct", confidence=0.9, reason=""),
              GradingResult(relevance="incorrect", confidence=0.9, reason=""),
              GradingResult(relevance="incorrect", confidence=0.9, reason="")]
    monkeypatch.setattr(document_grader, "grade_batch", AsyncMock(return_value=grades))
    result = await crag_agent.run("q", docs, "s")
    assert result.path == "correct" and [d.id for d in result.documents] == ["0"]


@pytest.mark.asyncio
async def test_grader_trusts_retrieval_when_llm_is_unavailable(monkeypatch):
    from services.document_grader import document_grader
    from services import llm
    monkeypatch.setattr(llm, "generate", AsyncMock(side_effect=llm.gexc.ResourceExhausted("quota")))
    grades = await document_grader.grade_batch("q", ["a", "b"])
    assert [g.relevance for g in grades] == ["correct", "correct"]


def test_chunker_splits_long_text_without_tiktoken():
    from pipeline.chunker import Chunker
    text = "\n\n".join(f"Paragraph {i}. " + "word " * 120 for i in range(12))
    chunks = Chunker(max_tokens=128, overlap=16).split_text(text)
    assert len(chunks) > 3
    assert all(len(c) <= 128 * 4 + 40 for c in chunks)
    assert "Paragraph 11" in "".join(chunks)


def test_deduplicator_near_duplicate_signatures():
    import numpy as np
    from pipeline import deduplicator as mod
    d = mod.Deduplicator.__new__(mod.Deduplicator)
    rng = np.random.default_rng(1)
    d.num_perm = 128
    d._a = rng.integers(1, mod._PRIME, size=128, dtype=np.uint64)
    d._b = rng.integers(0, mod._PRIME, size=128, dtype=np.uint64)
    import random
    words = [w for w in "alpha river stone cloud engine garden window silver paper violin market planet forest ocean bridge candle".split()]
    r = random.Random(3)
    base = " ".join(r.choice(words) + str(r.randint(0, 999)) for _ in range(1500))
    near = base + " one extra closing sentence"
    r2 = random.Random(99)
    import string
    other = "".join(r2.choice(string.ascii_lowercase + " ") for _ in range(12000))
    assert float(np.mean(d._signature(base) == d._signature(near))) > 0.85
    assert float(np.mean(d._signature(base) == d._signature(other))) < 0.2
