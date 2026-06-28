import redis.asyncio as redis
from redis.commands.search.field import VectorField, TextField
from redis.commands.search.index_definition import IndexDefinition, IndexType
from redis.commands.search.query import Query
import json
import hashlib
import numpy as np
from typing import Optional, List
from app.config import settings
from app.models import SearchResult, CachedResponse
from pipeline.embedder import embedder

class SemanticCache:
    def __init__(self):
        self.redis = None
        self.local_cache = {} # Fallback
        self.is_connected = False
        self.index_name = "idx:semantic_cache"
        self.vector_dim = 384 # For all-MiniLM-L6-v2
        
        try:
            self.redis = redis.from_url(settings.REDIS_URL, decode_responses=True)
        except Exception as e:
            print(f"SemanticCache: Failed to init Redis: {e}. Using in-memory fallback.")

    async def _check_conn(self):
        if self.is_connected:
            return True
        if not self.redis:
            return False
        try:
            await self.redis.ping()
            self.is_connected = True
            return True
        except Exception:
            self.is_connected = False
            return False

    async def init_index(self):
        """Initialize RediSearch HNSW index if it doesn't exist."""
        if not await self._check_conn():
            return

        try:
            await self.redis.ft(self.index_name).info()
        except Exception:
            # Index doesn't exist, create it
            schema = (
                TextField("query"),
                VectorField(
                    "vector", 
                    "HNSW", 
                    {
                        "TYPE": "FLOAT32", 
                        "DIM": self.vector_dim, 
                        "DISTANCE_METRIC": "COSINE"
                    }
                ),
                TextField("response")
            )
            try:
                await self.redis.ft(self.index_name).create_index(
                    schema,
                    definition=IndexDefinition(prefix=["cache:"], index_type=IndexType.HASH)
                )
                print(f"SemanticCache: Created RediSearch index {self.index_name}")
            except Exception as e:
                print(f"SemanticCache: Failed to create index: {e}")

    async def lookup(self, query: str, threshold: float = 0.90) -> Optional[CachedResponse]:
        """Perform semantic lookup using KNN."""
        if not await self._check_conn():
            return self.local_cache.get(hashlib.sha256(query.encode()).hexdigest())

        try:
            # Ensure index exists (lazy init)
            await self.init_index()

            # Embed query
            query_vector = embedder.model.encode(query, normalize_embeddings=True).astype(np.float32).tobytes()

            # KNN Query
            # Return top 1 result within distance threshold
            # Distances in COSINE metric are 1 - similarity. So similarity 0.90 means distance 0.10
            max_dist = 1 - threshold
            q = Query(f"*=>[KNN 1 @vector $vec AS score]").sort_by("score").return_fields("response", "score").dialect(2)
            
            res = await self.redis.ft(self.index_name).search(q, query_params={"vec": query_vector})
            
            if res.total > 0:
                score = float(res.docs[0].score)
                if score <= max_dist:
                    data = json.loads(res.docs[0].response)
                    return CachedResponse(**data)
            
        except Exception as e:
            print(f"SemanticCache lookup error: {e}")
        
        return None

    async def get(self, query: str, threshold: float = 0.90) -> Optional[CachedResponse]:
        return await self.lookup(query, threshold)

    async def store(self, query: str, response: CachedResponse, ttl: int = 3600):
        """Store query, embedding and response in Redis."""
        query_hash = hashlib.sha256(query.encode()).hexdigest()
        
        if await self._check_conn():
            try:
                query_vector = embedder.model.encode(query, normalize_embeddings=True).astype(np.float32).tobytes()
                
                # Store as HASH for RediSearch
                await self.redis.hset(
                    f"cache:{query_hash}",
                    mapping={
                        "query": query,
                        "vector": query_vector,
                        "response": response.model_dump_json()
                    }
                )
                await self.redis.expire(f"cache:{query_hash}", ttl)
            except Exception as e:
                print(f"SemanticCache store error: {e}")
        
        self.local_cache[query_hash] = response

    async def set(self, query: str, response: CachedResponse, ttl: int = 3600):
        await self.store(query, response, ttl)

semantic_cache = SemanticCache()
