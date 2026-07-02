import hashlib
import chromadb
import os
import asyncio
import redis.asyncio as redis
from typing import List, Dict, Any
from app.config import settings

class ChromaShardManager:
    def __init__(self):
        self.num_shards = settings.NUM_SHARDS
        self.persist_directory = os.path.join(os.getcwd(), settings.CHROMA_PERSIST_DIRECTORY)
        self.client = chromadb.PersistentClient(path=self.persist_directory)
        self.redis = redis.from_url(settings.REDIS_URL)
        self.shards: Dict[int, chromadb.Collection] = {}
        
    def get_shard_id(self, document_id: str) -> int:
        """Compute shard_id using consistent hashing."""
        return int(hashlib.md5(document_id.encode()).hexdigest(), 16) % self.num_shards

    def get_collection_name(self, shard_id: int) -> str:
        return f"genesis_shard_{shard_id:02d}"

    def get_collection(self, shard_id: int) -> chromadb.Collection:
        if shard_id not in self.shards:
            name = self.get_collection_name(shard_id)
            self.shards[shard_id] = self.client.get_or_create_collection(
                name=name,
                metadata={
                    "hnsw:space": "cosine",
                    "hnsw:construction_ef": 200,
                    "hnsw:M": 16
                }
            )
        return self.shards[shard_id]

    def get_enterprise_collection(self) -> chromadb.Collection:
        """Returns the non-sharded enterprise collection."""
        return self.client.get_or_create_collection(
            name="genesis_enterprise",
            metadata={"hnsw:space": "cosine"}
        )

    async def initialize_shards(self):
        """Initialize all shards on startup."""
        for i in range(self.num_shards):
            self.get_collection(i)
        print(f"ChromaShardManager: Initialized {self.num_shards} shards.")

    async def get_shard_for_doc(self, document_id: str) -> int:
        """Lookup shard_id from Redis, or compute if missing."""
        shard_id = await self.redis.hget("shard:doc_map", document_id)
        if shard_id is not None:
            return int(shard_id)
        
        # Fallback to hash if not in Redis (e.g. for new docs)
        shard_id = self.get_shard_id(document_id)
        await self.redis.hset("shard:doc_map", document_id, shard_id)
        return shard_id

    async def register_doc_shard(self, document_id: str, shard_id: int):
        """Register document_id to shard_id mapping in Redis."""
        await self.redis.hset("shard:doc_map", document_id, shard_id)

shard_manager = ChromaShardManager()
