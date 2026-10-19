import hashlib
import json
import time
from collections import OrderedDict
from typing import List, Optional

import numpy as np
import redis.asyncio as redis
from redis.commands.search.field import VectorField, TextField
from redis.commands.search.index_definition import IndexDefinition, IndexType
from redis.commands.search.query import Query

from app.config import settings
from app.models import CachedResponse
from pipeline.embedder import embedder

LOCAL_CACHE_SIZE = 256


class SemanticCache:
    """Similarity cache for answers.

    Uses a RediSearch HNSW index when Redis Stack is available. Otherwise (or in
    addition) it keeps a bounded in-memory cache and compares embeddings with numpy,
    so caching still works on a plain Redis or no Redis at all.

    Entries carry a namespace (retrieval mode, model, filters), so an answer made
    with one configuration is never served for another.
    """

    def __init__(self):
        self.redis = None
        self.is_connected = False
        self.redisearch_ready = False
        self.index_name = "idx:semantic_cache"
        self.vector_dim = 384  # all-MiniLM-L6-v2
        # key -> (vector, response, namespace, expires_at)
        self.local_cache: "OrderedDict[str, tuple]" = OrderedDict()

        try:
            self.redis = redis.from_url(settings.REDIS_URL, decode_responses=True)
        except Exception as e:
            print(f"SemanticCache: Failed to init Redis: {e}. Using in-memory cache only.")

    async def _check_conn(self) -> bool:
        if self.is_connected:
            return True
        if not self.redis:
            return False
        try:
            await self.redis.ping()
            self.is_connected = True
        except Exception:
            self.is_connected = False
        return self.is_connected

    async def init_index(self):
        """Create the RediSearch index once (no-op when RediSearch is missing)."""
        if self.redisearch_ready or not await self._check_conn():
            return
        try:
            await self.redis.ft(self.index_name).info()
            self.redisearch_ready = True
            return
        except Exception:
            pass
        try:
            schema = (
                TextField("query"),
                TextField("ns"),
                VectorField("vector", "HNSW", {"TYPE": "FLOAT32", "DIM": self.vector_dim, "DISTANCE_METRIC": "COSINE"}),
                TextField("response"),
            )
            await self.redis.ft(self.index_name).create_index(
                schema, definition=IndexDefinition(prefix=["cache:"], index_type=IndexType.HASH)
            )
            self.redisearch_ready = True
            print(f"SemanticCache: Created RediSearch index {self.index_name}")
        except Exception as e:
            print(f"SemanticCache: RediSearch unavailable ({e}); using in-memory similarity cache.")

    @staticmethod
    def _key(query: str, ns: str) -> str:
        return hashlib.sha256(f"{ns}\x00{query}".encode()).hexdigest()

    async def get(self, query: str, ns: str = "", threshold: float = 0.92) -> Optional[CachedResponse]:
        try:
            vec = np.asarray(await embedder.embed_text(query), dtype=np.float32)
        except Exception as e:
            print(f"SemanticCache: embedding failed: {e}")
            return None

        now = time.time()
        best, best_sim = None, 0.0
        for key, (v, response, entry_ns, expires) in list(self.local_cache.items()):
            if expires < now:
                del self.local_cache[key]
            elif entry_ns == ns:
                sim = float(np.dot(vec, v))  # vectors are normalized
                if sim > best_sim:
                    best, best_sim = response, sim
        if best is not None and best_sim >= threshold:
            return best

        if self.redisearch_ready and await self._check_conn():
            try:
                q = (Query("*=>[KNN 5 @vector $vec AS score]")
                     .sort_by("score").return_fields("response", "score", "ns").dialect(2))
                res = await self.redis.ft(self.index_name).search(q, query_params={"vec": vec.tobytes()})
                for doc in res.docs:
                    if getattr(doc, "ns", "") == ns and 1 - float(doc.score) >= threshold:
                        return CachedResponse(**json.loads(doc.response))
            except Exception as e:
                print(f"SemanticCache lookup error: {e}")
        return None

    async def set(self, query: str, response: CachedResponse, ns: str = "", ttl: int = 3600):
        try:
            vec = np.asarray(await embedder.embed_text(query), dtype=np.float32)
        except Exception as e:
            print(f"SemanticCache: embedding failed: {e}")
            return

        key = self._key(query, ns)
        self.local_cache[key] = (vec, response, ns, time.time() + ttl)
        self.local_cache.move_to_end(key)
        while len(self.local_cache) > LOCAL_CACHE_SIZE:
            self.local_cache.popitem(last=False)

        if self.redisearch_ready and await self._check_conn():
            try:
                await self.redis.hset(f"cache:{key}", mapping={
                    "query": query, "ns": ns, "vector": vec.tobytes(), "response": response.model_dump_json(),
                })
                await self.redis.expire(f"cache:{key}", ttl)
            except Exception as e:
                print(f"SemanticCache store error: {e}")

    # kept for callers that use the older names
    async def lookup(self, query: str, threshold: float = 0.92):
        return await self.get(query, threshold=threshold)

    async def store(self, query: str, response: CachedResponse, ttl: int = 3600):
        await self.set(query, response, ttl=ttl)

semantic_cache = SemanticCache()
