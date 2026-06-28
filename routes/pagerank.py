from fastapi import APIRouter, HTTPException
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/trigger")
async def trigger_pagerank():
    try:
        from pipeline.pagerank_job import run_pagerank_task
        task = run_pagerank_task.delay()
        return {"status": "success", "message": "PageRank computation queued successfully", "task_id": str(task.id)}
    except Exception as e:
        logger.error(f"Failed to trigger PageRank task: {e}")
        raise HTTPException(status_code=500, detail=str(e))
