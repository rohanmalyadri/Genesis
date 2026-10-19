import numpy as np
import pytest

from pipeline.embedder import Embedder


@pytest.fixture(scope="module")
def embedder():
    return Embedder()


def test_embeddings_are_384_dim_and_normalised(embedder):
    vectors = embedder.encode(["Genesis shards documents", "cats sleep a lot"])
    assert vectors.shape == (2, 384)
    assert np.allclose(np.linalg.norm(vectors, axis=1), 1.0, atol=1e-4)


def test_similar_sentences_are_closer_than_unrelated_ones(embedder):
    a, b, c = embedder.encode(["How are documents sharded?", "Documents are spread over shards", "I like pizza"])
    assert float(a @ b) > float(a @ c)


@pytest.mark.asyncio
async def test_embed_text_returns_a_plain_list(embedder):
    vector = await embedder.embed_text("hello")
    assert isinstance(vector, list) and len(vector) == 384
