import pickle
import redis
import asyncio
from typing import List
from sentence_transformers import SentenceTransformer
from rank_bm25 import BM25Okapi
from app.config import settings

class Embedder:
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model = SentenceTransformer(model_name)
        self.redis = redis.from_url(settings.REDIS_URL)
        self.batch_size = 64
        self.bm25_key = "bm25:corpus"

    async def embed_text(self, text: str) -> List[float]:
        """Embed a single query text (async wrapper)."""
        loop = asyncio.get_event_loop()
        embedding = await loop.run_in_executor(
            None, 
            lambda: self.model.encode(text, normalize_embeddings=True)
        )
        return embedding.tolist()

    def embed_batches(self, texts: List[str]) -> List[List[float]]:
        # Encode in batches
        embeddings = self.model.encode(
            texts, 
            batch_size=self.batch_size, 
            normalize_embeddings=True,
            show_progress_bar=False
        )
        return embeddings.tolist()

    def build_bm25_index(self, chunks: List[str], metadata: List[dict]):
        """Build and serialize BM25 index to Redis (Cumulative)."""
        existing_data = self.redis.get(self.bm25_key)
        
        all_data = []
        if existing_data:
            try:
                _, prev_data = pickle.loads(existing_data)
                all_data = prev_data
            except Exception as e:
                print(f"Embedder: Failed to load existing BM25 index: {e}")

        # Merge new chunks and metadata
        for text, meta in zip(chunks, metadata):
            all_data.append({"content": text, "metadata": meta})

        all_chunks = [d["content"] for d in all_data]
        tokenized_corpus = [doc.lower().split() for doc in all_chunks]
        bm25 = BM25Okapi(tokenized_corpus)
        
        # Pickle both index and associated data (content + metadata)
        serialized_data = pickle.dumps((bm25, all_data))
        self.redis.set(self.bm25_key, serialized_data)
        print(f"Embedder: BM25 index updated with {len(all_chunks)} total documents.")

embedder = Embedder()
