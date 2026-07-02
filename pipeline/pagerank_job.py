import networkx as nx
import redis
import json
import time
import argparse
import logging
from datetime import datetime
from typing import List, Dict, Tuple
from opik import Opik
from app.config import settings
from retrieval.chroma_shard_manager import shard_manager
import chromadb

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("PageRankJob")

from app.celery import app as celery_app

@celery_app.task(name="pipeline.pagerank_job.run_pagerank_task")
def run_pagerank_task():
    run_pagerank_job()

class ChromaDB_client:
    """Wrapper to match the user-requested API pattern for ChromaDB updates."""
    @staticmethod
    def set_payload(collection_name: str, payload: dict, points: List[str]):
        # Connect to redis to expand doc_ids to chunk_ids
        r = redis.from_url(settings.REDIS_URL, decode_responses=True)
        
        all_chunk_ids = []
        for doc_id in points:
            chunk_set = r.smembers(f"doc_chunks:{doc_id}")
            if chunk_set:
                all_chunk_ids.extend(list(chunk_set))
            else:
                # Fallback to doc_id itself (useful for older docs or single-point updates)
                all_chunk_ids.append(doc_id)

        # Filter logic is implied by the 'points' argument (list of IDs)
        shard_to_ids = {}
        for cid in all_chunk_ids:
            # Compute shard ID for the chunk ID
            sid = shard_manager.get_shard_id(cid)
            if sid not in shard_to_ids:
                shard_to_ids[sid] = []
            shard_to_ids[sid].append(cid)
            
        for sid, ids in shard_to_ids.items():
            try:
                collection = shard_manager.get_collection(sid)
                # ChromaDB update requires metadatas list to match ids list
                metadatas = [payload for _ in ids]
                # Filter out IDs that might not exist in this shard to avoid errors
                # (Though consistent hashing should prevent this, it's safer)
                collection.update(ids=ids, metadatas=metadatas)
            except Exception as e:
                logger.error(f"Failed to update shard {sid}: {e}")
        
        # Also handle enterprise collection if it exists and contains these docs
        try:
            ent_collection = shard_manager.get_enterprise_collection()
            if ent_collection:
                # Find which IDs actually exist in the enterprise collection to avoid update errors
                existing = ent_collection.get(ids=all_chunk_ids, include=[])
                existing_ids = existing.get("ids", [])
                
                if existing_ids:
                    metadatas = [payload for _ in existing_ids]
                    ent_collection.update(ids=existing_ids, metadatas=metadatas)
        except Exception as e:
            logger.error(f"Failed to update enterprise collection: {e}")

def run_pagerank_job():
    start_time = time.time()
    logger.info("Starting PageRank computation job...")

    # Step 1 — Load graph from Redis
    r = redis.from_url(settings.REDIS_URL, decode_responses=True)
    edges_raw = r.lrange("citation_graph:edges", 0, -1)
    
    edges: List[Tuple[str, str, float]] = []
    for edge_str in edges_raw:
        try:
            source, target, weight = edge_str.split(',')
            edges.append((source, target, float(weight)))
        except ValueError:
            continue

    if not edges:
        logger.warning("No edges found in citation graph. Skipping.")
        return

    # Step 2 — Build weighted DiGraph
    G = nx.DiGraph()
    for source, target, weight in edges:
        if G.has_edge(source, target):
            G[source][target]['weight'] += weight
        else:
            G.add_edge(source, target, weight=weight)
            
    # Cap weights if they exceeded during manual construction (though extract does this)
    for u, v, d in G.edges(data=True):
        if d['weight'] > 3.0:
            d['weight'] = 3.0

    # Step 3 — Run PageRank
    scores = nx.pagerank(G, alpha=0.85, weight='weight', max_iter=200, tol=1e-6)

    # Step 4 — Normalize scores to [0.0, 1.0]
    if scores:
        min_score = min(scores.values())
        max_score = max(scores.values())
        range_val = max_score - min_score + 1e-9
        
        normalized_scores = {
            doc_id: (score - min_score) / range_val 
            for doc_id, score in scores.items()
        }
    else:
        normalized_scores = {}

    # Step 5 — Store scores in ChromaDB
    timestamp = datetime.utcnow().isoformat()
    doc_ids = list(normalized_scores.keys())
    
    # Batch updates in groups of 500
    batch_size = 500
    for i in range(0, len(doc_ids), batch_size):
        batch_ids = doc_ids[i:i + batch_size]
        for doc_id in batch_ids:
            payload = {
                "pagerank_score": normalized_scores[doc_id],
                "pagerank_computed_at": timestamp
            }
            # Using the requested API pattern
            ChromaDB_client.set_payload(
                collection_name="documents", 
                payload=payload, 
                points=[doc_id]
            )
        logger.info(f"Updated ChromaDB batch {i//batch_size + 1}")

    # Step 6 — Cache top-1000 in Redis
    # Clear old rankings
    r.delete("pagerank:top")
    sorted_scores = sorted(normalized_scores.items(), key=lambda x: x[1], reverse=True)
    top_1000 = sorted_scores[:1000]
    
    if top_1000:
        pipe = r.pipeline()
        for doc_id, score in top_1000:
            pipe.zadd("pagerank:top", {doc_id: score})
        pipe.expire("pagerank:top", 86400)
        pipe.execute()

    # Step 7 — Logging & Metrics
    duration = time.time() - start_time
    logger.info(f"PageRank job completed in {duration:.2f}s")
    logger.info(f"Total Nodes: {G.number_of_nodes()}")
    logger.info(f"Total Edges: {G.number_of_edges()}")
    
    top_10 = sorted_scores[:10]
    logger.info("Top 10 Nodes by PageRank:")
    for doc_id, score in top_10:
        logger.info(f"  {doc_id}: {score:.4f}")

    # Send to OPIK
    try:
        opik_client = Opik()
        trace = opik_client.trace(name="pagerank_computation")
        trace.update(
            metadata={
                "total_nodes": G.number_of_nodes(),
                "total_edges": G.number_of_edges(),
                "duration_seconds": duration,
                "top_10_nodes": [doc_id for doc_id, _ in top_10]
            }
        )
        logger.info("Successfully logged PageRank metrics to Opik")
    except Exception as e:
        logger.error(f"Failed to send metrics to OPIK: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run PageRank computation for document authority.")
    parser.add_argument("--force", action="store_true", help="Force immediate execution.")
    args = parser.parse_args()
    
    if args.force:
        run_pagerank_job()
