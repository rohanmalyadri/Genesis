import asyncio
import logging
import os
from typing import Any, Dict, List, Optional, Tuple

import magic
import redis.asyncio as aioredis

from app.config import settings
from app.models import Chunk, DocumentMetadata
from .extractors.pdf_extractor import pdf_extractor
from .extractors.html_extractor import html_extractor
from .extractors.docx_extractor import docx_extractor
from .extractors.image_extractor import image_extractor
from .extractors.text_extractor import text_extractor
from .preprocessor import preprocessor
from .deduplicator import deduplicator
from .chunker import chunker, Chunker
from .embedder import embedder
from .indexer import indexer

logger = logging.getLogger("IngestionPipeline")

DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


class IngestionPipeline:
    def __init__(self):
        self.mime = magic.Magic(mime=True)
        self.redis = aioredis.from_url(settings.REDIS_URL)

    def _extract_pages(self, file_path: str, mime_type: str) -> List[str]:
        """Return the document as a list of pages (non-PDF files are one page)."""
        if mime_type == "application/pdf":
            return pdf_extractor.extract_pages(file_path)
        if mime_type == "text/html":
            return [html_extractor.extract(text_extractor.extract(file_path))]
        if mime_type == DOCX_MIME:
            return [docx_extractor.extract(file_path)]
        if mime_type.startswith("image/"):
            return [image_extractor.extract(file_path)]
        return [text_extractor.extract(file_path)]

    def _prepare(self, file_path: str, ext: str, scope: str, document_id: str, chunk_size: int = 512) -> Optional[Tuple[str, List[Tuple[str, int]]]]:
        """CPU-bound work: extract, clean, dedupe, chunk. Runs in a worker thread."""
        mime_type = self.mime.from_file(file_path)
        logger.info(f"Ingesting {document_id} (mime={mime_type}, ext={ext})")

        pages = preprocessor.strip_headers_footers(self._extract_pages(file_path, mime_type))
        pages = [preprocessor.normalize(p) for p in pages]
        full_content = "\n".join(pages)
        if not full_content.strip():
            raise ValueError("No text could be extracted from this file")

        if deduplicator.is_duplicate(full_content, doc_id=document_id, scope=scope):
            return None

        page_chunker = chunker if chunk_size == chunker.max_tokens else Chunker(max_tokens=chunk_size, overlap=min(64, chunk_size // 8))
        chunk_texts: List[Tuple[str, int]] = []
        for page_no, page_text in enumerate(pages, start=1):
            for text in page_chunker.split_text(page_text, file_ext=ext):
                if text.strip():
                    chunk_texts.append((text, page_no))
        return full_content, chunk_texts

    async def _extract_graph(self, document_id: str, chunk_texts: List[str]) -> Optional[Dict[str, int]]:
        """Knowledge-graph extraction. Skipped quietly when Neo4j is unreachable."""
        from retrieval.graph_store import graph_store
        try:
            await graph_store.connect()
            if not await asyncio.wait_for(graph_store.ping(), timeout=5):
                raise ConnectionError("Neo4j not reachable")
        except Exception as e:
            logger.warning(f"Skipping graph extraction for {document_id}: {e}")
            return None

        try:
            from .relation_extractor import get_relation_extractor
        except ImportError as e:  # PyTorch/transformers are an optional extra: pip install ".[graph]"
            logger.warning(f"Skipping graph extraction for {document_id}: {e}")
            return None
        extractor = await get_relation_extractor()
        entities, relations = {}, []
        for text in chunk_texts:
            ents, rels = await extractor.extract(text, document_id)
            entities.update({e.id: e for e in ents})
            relations.extend(rels)
        if entities:
            entity_list = list(entities.values())
            loop = asyncio.get_running_loop()
            embeddings = await loop.run_in_executor(
                None, lambda: embedder.embed_batches([f"{e.name} {e.type}" for e in entity_list])
            )
            for ent, emb in zip(entity_list, embeddings):
                ent.embedding = list(emb)
            await graph_store.upsert_all(entity_list, relations)
        return {"entities": len(entities), "relations": len(relations)}

    async def process_file(
        self,
        file_path: str,
        use_sharding: bool = True,
        skip_graph: bool = False,
        original_name: Optional[str] = None,
        chunk_size: int = 512,
    ) -> Dict[str, Any]:
        loop = asyncio.get_running_loop()
        document_id = original_name or os.path.basename(file_path)
        ext = os.path.splitext(document_id)[1].lower()
        scope = "sharded" if use_sharding else "enterprise"

        prepared = await loop.run_in_executor(None, lambda: self._prepare(file_path, ext, scope, document_id, chunk_size))
        if prepared is None:
            logger.info(f"Skipping duplicate document: {document_id}")
            return {"status": "duplicate", "document_id": document_id, "chunks": 0}
        full_content, chunk_texts = prepared
        logger.info(f"Split {document_id} into {len(chunk_texts)} chunks")

        # Citation graph (feeds PageRank)
        from .citation_extractor import citation_extractor
        edges = citation_extractor.extract(document_id, full_content, {"file_path": document_id})
        await citation_extractor.store_edges(edges)

        graph_stats = None
        if not skip_graph:
            graph_stats = await self._extract_graph(document_id, [t for t, _ in chunk_texts])

        vectors = await loop.run_in_executor(
            None, lambda: embedder.embed_batches([t for t, _ in chunk_texts])
        )

        source_type = ext.replace(".", "") or "text"
        chunks = [
            Chunk(
                id=f"{document_id}_{i}",
                content=text,
                embedding=vec,
                metadata=DocumentMetadata(
                    title=document_id,
                    filename=document_id,
                    document_id=document_id,
                    page=page,
                    source_url=document_id,
                    source_type=source_type,
                ),
            )
            for i, ((text, page), vec) in enumerate(zip(chunk_texts, vectors))
        ]
        await indexer.upsert_chunks(chunks, use_sharding=use_sharding)

        # chunk map used by the PageRank job
        chunk_ids = [c.id for c in chunks]
        if chunk_ids:
            await self.redis.sadd(f"doc_chunks:{document_id}", *chunk_ids)
            await self.redis.expire(f"doc_chunks:{document_id}", 604800)

        logger.info(f"Ingestion complete for {document_id}")
        return {
            "status": "indexed",
            "document_id": document_id,
            "chunks": len(chunks),
            "graph": graph_stats,
        }

ingest_pipeline = IngestionPipeline()

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("file", help="File to ingest")
    parser.add_argument("--skip-graph", action="store_true", help="Skip graph extraction")
    parser.add_argument("--no-sharding", action="store_false", dest="use_sharding", help="Disable sharding")
    parser.set_defaults(use_sharding=True)
    args = parser.parse_args()
    print(asyncio.run(ingest_pipeline.process_file(args.file, use_sharding=args.use_sharding, skip_graph=args.skip_graph)))
