import asyncio
from typing import Dict, Any, List
from retrieval.chroma_shard_manager import shard_manager
from app.config import settings

class ShardHealthService:
    async def get_shards_status(self) -> Dict[str, Any]:
        shard_stats = []
        total_docs = 0
        
        # Chroma operations are blocking, run in executor
        loop = asyncio.get_event_loop()
        
        def check_shard(sid: int):
            try:
                collection = shard_manager.get_collection(sid)
                count = collection.count()
                return {
                    "shard_id": sid,
                    "collection_name": shard_manager.get_collection_name(sid),
                    "status": "responsive",
                    "document_count": count
                }
            except Exception as e:
                return {
                    "shard_id": sid,
                    "collection_name": shard_manager.get_collection_name(sid),
                    "status": "unresponsive",
                    "error": str(e)
                }

        results = await asyncio.gather(*[
            loop.run_in_executor(None, check_shard, i) 
            for i in range(settings.NUM_SHARDS)
        ])
        
        for res in results:
            shard_stats.append(res)
            if res["status"] == "responsive":
                total_docs += res["document_count"]
                
        return {
            "total_shards": settings.NUM_SHARDS,
            "total_documents": total_docs,
            "shards": shard_stats
        }

shard_health_service = ShardHealthService()
