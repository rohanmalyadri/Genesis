import redis
import json
import time
import argparse
import logging
from datetime import datetime, timezone
from typing import List, Dict, Tuple
from app.config import settings
from retrieval.chroma_shard_manager import shard_manager
import chromadb

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("PageRankJob")

from app.celery import app as celery_app

@celery_app.task(name="pipeline.pagerank_job.run_pagerank_task")
def run_pagerank_task():
    return run_pagerank_job()

class ChromaDB_client:
    """Writes PageRank payloads into the Chroma collections that hold a document."""
    @staticmethod
    def set_payload(collection_name: str, payload: dict, points: List[str]):
        r = redis.from_url(settings.REDIS_URL, decode_responses=True)

        for doc_id in points:
            chunk_ids = list(r.smembers(f"doc_chunks:{doc_id}"))
            if not chunk_ids:
                continue  # cited URL / unknown node: nothing indexed to update

            # Sharded copy: every chunk of a document lives on the shard of its document id
            targets = [
                (shard_manager.get_collection(shard_manager.get_shard_id(doc_id)), "sharded"),
                (shard_manager.get_enterprise_collection(), "enterprise"),
            ]
            for collection, label in targets:
                try:
                    existing = collection.get(ids=chunk_ids, include=[]).get("ids", [])
                    if existing:
                        collection.update(ids=existing, metadatas=[payload for _ in existing])
                except Exception as e:
                    logger.error(f"Failed to update {label} collection for {doc_id}: {e}")

def run_pagerank_job():
    import networkx as nx  # lazy: only needed when the job runs
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
        return {"nodes": 0, "edges": 0}

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
    timestamp = datetime.now(timezone.utc).isoformat()
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

    summary = {"nodes": G.number_of_nodes(), "edges": G.number_of_edges(), "seconds": round(duration, 2)}

    # Send to OPIK
    try:
        if not settings.OPIK_API_KEY:
            return summary
        from opik import Opik
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
    return summary

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run PageRank computation for document authority.")
    parser.add_argument("--force", action="store_true", help="Force immediate execution.")
    args = parser.parse_args()
    
    if args.force:
        run_pagerank_job()
