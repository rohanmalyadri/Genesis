import chromadb
from chromadb.config import Settings as ChromaSettings
from typing import List
from app.config import settings
from app.models import Chunk, DocumentMetadata
from datetime import datetime
import spacy
import os

from retrieval.chroma_shard_manager import shard_manager
import asyncio

class ChromaIndexer:
    def __init__(self):
        self.nlp = spacy.load("en_core_web_sm")

    def _extract_entities(self, text: str) -> List[str]:
        doc = self.nlp(text[:1000])
        return list(set([ent.text for ent in doc.ents]))

    async def upsert_chunks(self, chunks: List[Chunk], use_sharding: bool = True):
        await self.index_chunks(chunks, use_sharding=use_sharding)

    async def _upsert_to_shard(self, shard_id: int, shard_chunks: List[Chunk]):
        collection = shard_manager.get_collection(shard_id)
        
        ids = [c.id for c in shard_chunks]
        documents = [c.content for c in shard_chunks]
        embeddings = [c.embedding for c in shard_chunks]
        metadatas = []

        for c in shard_chunks:
            meta = c.metadata.model_dump()
            for k, v in meta.items():
                if isinstance(v, datetime):
                    meta[k] = v.isoformat()
            
            meta["entities"] = ",".join(self._extract_entities(c.content))
            meta["shard_id"] = shard_id
            metadatas.append(meta)

        # Chroma upsert is blocking, run in executor
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, lambda: collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas
        ))
        
        # Register in Redis
        for c in shard_chunks:
            await shard_manager.register_doc_shard(c.id, shard_id)
            
        print(f"ChromaIndexer: Indexed {len(shard_chunks)} chunks into shard {shard_id}")

    async def _upsert_to_enterprise(self, chunks: List[Chunk]):
        collection = shard_manager.get_enterprise_collection()
        ids = [c.id for c in chunks]
        documents = [c.content for c in chunks]
        embeddings = [c.embedding for c in chunks]
        metadatas = []

        for c in chunks:
            meta = c.metadata.model_dump()
            for k, v in meta.items():
                if isinstance(v, datetime):
                    meta[k] = v.isoformat()
            meta["entities"] = ",".join(self._extract_entities(c.content))
            meta["is_sharded"] = False
            metadatas.append(meta)

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, lambda: collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas
        ))
        print(f"ChromaIndexer: Indexed {len(chunks)} chunks into enterprise collection")

    async def index_chunks(self, chunks: List[Chunk], use_sharding: bool = True):
        if not chunks:
            return
            
        if not use_sharding:
            await self._upsert_to_enterprise(chunks)
            return

        # Group chunks by shard_id
        shard_groups = {}
        for c in chunks:
            sid = shard_manager.get_shard_id(c.id)
            if sid not in shard_groups:
                shard_groups[sid] = []
            shard_groups[sid].append(c)
            
        # Parallel upserts
        tasks = [self._upsert_to_shard(sid, grouped_chunks) for sid, grouped_chunks in shard_groups.items()]
        await asyncio.gather(*tasks)

indexer = ChromaIndexer()
