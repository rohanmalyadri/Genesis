from fastapi import APIRouter, HTTPException
import chromadb
import redis.asyncio as redis
from app.config import settings

router = APIRouter()

from services.shard_health import shard_health_service

@router.get("/shards")
async def shard_health():
    return await shard_health_service.get_shards_status()
@router.get("/")
async def health_check():
    health_status = {
        "status": "healthy",
        "chroma": "unknown",
        "redis": "unknown",
        "neo4j": "unknown",
        "model": "healthy"
    }
    
    # 1. Check Chroma
    try:
        from pipeline.indexer import indexer
        indexer.client.heartbeat()
        health_status["chroma"] = "healthy"
    except Exception as e:
        health_status["chroma"] = f"unhealthy: {str(e)}"
        health_status["status"] = "unhealthy"

    # 2. Check Redis
    try:
        r = redis.from_url(settings.REDIS_URL)
        await r.ping()
        health_status["redis"] = "healthy"
        await r.aclose()
    except Exception as e:
        health_status["redis"] = f"unhealthy: {str(e)}"
        health_status["status"] = "unhealthy"

    # 3. Check Neo4j
    try:
        from retrieval.graph_store import graph_store
        is_graph_healthy = await graph_store.ping()
        health_status["neo4j"] = "healthy" if is_graph_healthy else "unhealthy: connection failed"
        if not is_graph_healthy:
            health_status["status"] = "unhealthy"
    except Exception as e:
        health_status["neo4j"] = f"unhealthy: {str(e)}"
        health_status["status"] = "unhealthy"

    return health_status

@router.get("/ready")
async def readiness_check():
    try:
        from pipeline.indexer import indexer
        indexer.client.heartbeat()
        return {"status": "ready"}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Service not ready: {str(e)}")
