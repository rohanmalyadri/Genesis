import asyncio
import logging

import redis.asyncio as aioredis
from fastapi import APIRouter, HTTPException

from app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/trigger")
async def trigger_pagerank(inline: bool = False):
    """Queue the PageRank job on Celery, or run it right now with inline=true."""
    try:
        from pipeline.pagerank_job import run_pagerank_task, run_pagerank_job
        if inline:
            loop = asyncio.get_running_loop()
            summary = await loop.run_in_executor(None, run_pagerank_job)
            return {"status": "success", "message": "PageRank computed", "result": summary}
        task = run_pagerank_task.delay()
        return {"status": "success", "message": "PageRank computation queued successfully", "task_id": str(task.id)}
    except Exception as e:
        logger.error(f"Failed to trigger PageRank task: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def pagerank_stats(limit: int = 10):
    """Real citation-graph statistics and the top authority nodes from Redis."""
    r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    try:
        raw_edges = await r.lrange("citation_graph:edges", 0, -1)
        nodes, unique_edges = set(), set()
        for line in raw_edges:
            parts = line.rsplit(",", 2)
            if len(parts) != 3:
                continue
            nodes.update(parts[:2])
            unique_edges.add((parts[0], parts[1]))

        n = len(nodes)
        density = len(unique_edges) / (n * (n - 1)) if n > 1 else 0.0

        top = []
        for node_id, score in await r.zrevrange("pagerank:top", 0, max(limit, 1) - 1, withscores=True):
            top.append({
                "id": node_id,
                "score": float(score),
                "citations": await r.zcard(f"cited_by:{node_id}"),
            })
        return {
            "total_nodes": n,
            "total_edges": len(unique_edges),
            "density": density,
            "computed": bool(top),
            "top": top,
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Redis unavailable: {e}")
    finally:
        await r.aclose()
