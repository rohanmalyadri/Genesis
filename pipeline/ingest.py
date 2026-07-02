import os
import magic
from typing import List
from app.models import Chunk, DocumentMetadata
from .extractors.pdf_extractor import pdf_extractor
from .extractors.html_extractor import html_extractor
from .extractors.docx_extractor import docx_extractor
from .extractors.image_extractor import image_extractor
from .extractors.text_extractor import text_extractor
from .preprocessor import preprocessor
from .deduplicator import deduplicator
from .chunker import chunker
from .embedder import embedder
from .indexer import indexer

class IngestionPipeline:
    def __init__(self):
        self.mime = magic.Magic(mime=True)

    async def process_file(self, file_path: str, use_sharding: bool = True, skip_graph: bool = False):
        print(f"Starting ingestion for: {file_path}")
        
        # 1. Detect MIME Type
        mime_type = self.mime.from_file(file_path)
        ext = os.path.splitext(file_path)[1].lower()
        print(f"MIME Type: {mime_type}, Extension: {ext}")
        
        # 2. Extract
        if mime_type == 'application/pdf':
            content = pdf_extractor.extract(file_path)
        elif mime_type == 'text/html':
            with open(file_path, 'r') as f:
                content = html_extractor.extract(f.read())
        elif mime_type == 'application/vnd.openxmlformats-officedocument.wordprocessingml.document':
            content = docx_extractor.extract(file_path)
        elif mime_type.startswith('image/'):
            content = image_extractor.extract(file_path)
        else:
            content = text_extractor.extract(file_path)
            
        # 3. Preprocess
        pages = [content]
        clean_pages = preprocessor.strip_headers_footers(pages)
        full_content = "\n".join([preprocessor.normalize(p) for p in clean_pages])
        
        # 4. Deduplicate (Near-Dedup)
        if deduplicator.is_duplicate(full_content, doc_id=file_path):
            print(f"Skipping duplicate file: {file_path}")
            return
            
        # 5. Chunk
        chunk_texts = chunker.split_text(full_content, file_ext=ext)
        print(f"Split into {len(chunk_texts)} chunks.")
        
        # 5b. Citation Graph Extraction
        from .citation_extractor import citation_extractor
        edges = citation_extractor.extract(file_path, full_content, {"file_path": file_path})
        await citation_extractor.store_edges(edges)

        # 5c. Knowledge Graph Relation Extraction
        if not skip_graph:
            print("Starting Relation Extraction...")
            from .relation_extractor import get_relation_extractor
            from retrieval.graph_store import graph_store
            extractor = await get_relation_extractor()
            
            all_entities = {}
            all_relations = []
            
            for chunk_text in chunk_texts:
                entities, relations = await extractor.extract(chunk_text, file_path)
                for ent in entities:
                    all_entities[ent.id] = ent
                all_relations.extend(relations)
            
            # Embed entities
            if all_entities:
                entity_list = list(all_entities.values())
                entity_texts = [f"{e.name} {e.type}" for e in entity_list]
                entity_embeddings = embedder.embed_batches(entity_texts)
                for ent, emb in zip(entity_list, entity_embeddings):
                    ent.embedding = emb.tolist()
                
                # Batch upsert to Neo4j
                await graph_store.connect()
                await graph_store.upsert_all(entity_list, all_relations)
                print(f"Graph updated: {len(entity_list)} entities, {len(all_relations)} relations.")
        
        # 6. Embed (Dense Chunks)
        vectors = embedder.embed_batches(chunk_texts)
        
        # 7. Create Chunk objects and Index (Chroma)
        doc_metadata = DocumentMetadata(
            title=os.path.basename(file_path),
            source_url=file_path,
            source_type=ext.replace(".", "") or "text"
        )
        
        chunks = []
        for i, (text, vec) in enumerate(zip(chunk_texts, vectors)):
            chunks.append(Chunk(
                id=f"{file_path}_{i}",
                content=text,
                embedding=vec,
                metadata=doc_metadata
            ))
            
        await indexer.upsert_chunks(chunks, use_sharding=use_sharding)
        
        # 7b. Store chunk mapping in Redis for PageRank job
        import redis
        from app.config import settings
        r = redis.from_url(settings.REDIS_URL)
        chunk_ids = [c.id for c in chunks]
        if chunk_ids:
            r.sadd(f"doc_chunks:{file_path}", *chunk_ids)
            r.expire(f"doc_chunks:{file_path}", 604800) # 1 week TTL
        
        # 8. Update BM25 Index (Redis)
        embedder.build_bm25_index(chunk_texts, [doc_metadata.model_dump() for _ in chunk_texts])
        
        print(f"Ingestion complete for: {file_path}")

ingest_pipeline = IngestionPipeline()

if __name__ == "__main__":
    import argparse
    import asyncio
    
    parser = argparse.ArgumentParser()
    parser.add_argument("file", help="File to ingest")
    parser.add_argument("--skip-graph", action="store_true", help="Skip graph extraction")
    parser.add_argument("--no-sharding", action="store_false", dest="use_sharding", help="Disable sharding")
    parser.set_defaults(use_sharding=True)
    args = parser.parse_args()
    
    asyncio.run(ingest_pipeline.process_file(args.file, use_sharding=args.use_sharding, skip_graph=args.skip_graph))
