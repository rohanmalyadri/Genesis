"""Index the sample documents in demo_docs/ when the knowledge base is empty.

Hosts with an ephemeral disk (for example Render's free plan) lose the vector index
on every restart. Seeding keeps the hosted demo usable without manual uploads.
"""
import asyncio
import logging
import os

from app.config import settings

logger = logging.getLogger("Seed")
DEMO_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "demo_docs")


async def seed_demo_docs() -> None:
    if not settings.SEED_DEMO_DOCS or not os.path.isdir(DEMO_DIR):
        return
    try:
        from retrieval.chroma_shard_manager import shard_manager
        from pipeline.ingest import ingest_pipeline

        loop = asyncio.get_running_loop()
        counts = await loop.run_in_executor(None, lambda: (
            shard_manager.get_enterprise_collection().count(),
            sum(shard_manager.get_collection(i).count() for i in range(settings.NUM_SHARDS)),
        ))
        if counts[0] > 0 and counts[1] > 0:
            return

        for name in sorted(os.listdir(DEMO_DIR)):
            path = os.path.join(DEMO_DIR, name)
            if not os.path.isfile(path):
                continue
            for sharded, existing in ((False, counts[0]), (True, counts[1])):
                if existing == 0:
                    await ingest_pipeline.process_file(
                        path, use_sharding=sharded, skip_graph=True, original_name=name
                    )
        from pipeline.pagerank_job import run_pagerank_job
        await loop.run_in_executor(None, run_pagerank_job)
        logger.info("Demo documents indexed")
    except Exception as e:  # never block startup on seeding
        logger.warning(f"Demo seeding failed: {e}")
