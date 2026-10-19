import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List

from app.models import Chunk
from retrieval.chroma_shard_manager import shard_manager
from retrieval.sparse_index import sparse_index

logger = logging.getLogger("ChromaIndexer")


class ChromaIndexer:
    def __init__(self):
        self._nlp = None
        self._nlp_checked = False

    @property
    def nlp(self):
        """spaCy model for entity tags. Optional: indexing works without it."""
        if not self._nlp_checked:
            self._nlp_checked = True
            try:
                import spacy
                self._nlp = spacy.load("en_core_web_sm")
            except Exception as e:
                logger.warning(f"spaCy model unavailable, skipping entity tags: {e}")
        return self._nlp

    def _extract_entities(self, text: str) -> List[str]:
        if not self.nlp:
            return []
        doc = self.nlp(text[:1000])
        return sorted({ent.text for ent in doc.ents})

    def _prepare(self, chunks: List[Chunk], extra: Dict[str, Any]):
        ids, documents, embeddings, metadatas = [], [], [], []
        for c in chunks:
            meta = {}
            for k, v in c.metadata.model_dump().items():
                if v is None:
                    continue  # Chroma rejects None metadata values
                meta[k] = v.isoformat() if isinstance(v, datetime) else v
            meta["entities"] = ",".join(self._extract_entities(c.content))
            meta.update(extra)
            ids.append(c.id)
            documents.append(c.content)
            embeddings.append(c.embedding)
            metadatas.append(meta)
        return ids, documents, embeddings, metadatas

    async def _upsert(self, collection, chunks: List[Chunk], extra: Dict[str, Any], collection_label: str):
        loop = asyncio.get_running_loop()
        ids, documents, embeddings, metadatas = await loop.run_in_executor(
            None, lambda: self._prepare(chunks, extra)
        )
        await loop.run_in_executor(None, lambda: collection.upsert(
            ids=ids, embeddings=embeddings, documents=documents, metadatas=metadatas
        ))
        await sparse_index.add([
            {"id": i, "content": d, "metadata": m, "collection": collection_label}
            for i, d, m in zip(ids, documents, metadatas)
        ])

    async def _upsert_to_shard(self, shard_id: int, shard_chunks: List[Chunk]):
        collection = shard_manager.get_collection(shard_id)
        await self._upsert(collection, shard_chunks, {"shard_id": shard_id, "is_sharded": True}, "sharded")
        for doc_id in {c.metadata.document_id or c.id for c in shard_chunks}:
            await shard_manager.register_doc_shard(doc_id, shard_id)
        logger.info(f"Indexed {len(shard_chunks)} chunks into shard {shard_id}")

    async def _upsert_to_enterprise(self, chunks: List[Chunk]):
        collection = shard_manager.get_enterprise_collection()
        await self._upsert(collection, chunks, {"is_sharded": False}, "enterprise")
        logger.info(f"Indexed {len(chunks)} chunks into enterprise collection")

    async def upsert_chunks(self, chunks: List[Chunk], use_sharding: bool = True):
        await self.index_chunks(chunks, use_sharding=use_sharding)

    async def index_chunks(self, chunks: List[Chunk], use_sharding: bool = True):
        if not chunks:
            return
        if not use_sharding:
            await self._upsert_to_enterprise(chunks)
            return

        # Shard by *document* id so every chunk of a document lands on one shard
        groups: Dict[int, List[Chunk]] = {}
        for c in chunks:
            sid = shard_manager.get_shard_id(c.metadata.document_id or c.id)
            groups.setdefault(sid, []).append(c)
        await asyncio.gather(*[self._upsert_to_shard(sid, g) for sid, g in groups.items()])

indexer = ChromaIndexer()
