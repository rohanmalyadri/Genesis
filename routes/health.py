import asyncio

import redis.asyncio as redis
from fastapi import APIRouter, HTTPException

from app.config import settings
from services.shard_health import shard_health_service

router = APIRouter()


@router.get("/shards")
async def shard_health():
    return await shard_health_service.get_shards_status()


@router.get("/")
async def health_check():
    """Per-dependency status. Neo4j is optional: without it only graph features are off."""
    status = {
        "status": "healthy",
        "chroma": "unknown",
        "redis": "unknown",
        "neo4j": "unknown",
        "model": "configured" if settings.GOOGLE_API_KEY else "missing GOOGLE_API_KEY",
        "name": settings.PROJECT_NAME,
    }

    try:
        from retrieval.chroma_shard_manager import shard_manager
        shard_manager.client.heartbeat()
        status["chroma"] = "healthy"
    except Exception as e:
        status["chroma"] = f"unhealthy: {e}"
        status["status"] = "unhealthy"

    try:
        r = redis.from_url(settings.REDIS_URL)
        await r.ping()
        status["redis"] = "healthy"
        await r.aclose()
    except Exception as e:
        status["redis"] = f"unhealthy: {e}"
        status["status"] = "unhealthy"

    try:
        from retrieval.graph_store import graph_store
        await graph_store.connect()
        ok = await asyncio.wait_for(graph_store.ping(), timeout=3)
        status["neo4j"] = "healthy" if ok else "offline (optional)"
    except Exception:
        status["neo4j"] = "offline (optional)"

    if not settings.GOOGLE_API_KEY:
        status["status"] = "unhealthy"
    return status


@router.get("/ready")
async def readiness_check():
    try:
        from retrieval.chroma_shard_manager import shard_manager
        shard_manager.client.heartbeat()
        return {"status": "ready"}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Service not ready: {e}")
