from typing import List, Optional, Dict, Any, Union
from app.models import SearchResult, QueryResponse, CachedResponse, Message, AgentResponse, RefusalResponse, RetrievedDoc
from retrieval.hybrid_retriever import hybrid_retriever
from agents.crag import crag_agent
from agents.adaptive_router import adaptive_router
from agents.graph_reasoner import graph_reasoner
from security.input_guard import input_guard
from security.content_filter import content_filter
from security.output_guard import output_guard
from .semantic_cache import semantic_cache
from .conversation import conversation_memory
from datetime import datetime

class RAGPipeline:
    async def run(self, query: str, conversation_id: Optional[str] = None, filters: Optional[Dict[str, Any]] = None) -> Union[QueryResponse, RefusalResponse]:
        # 1. Security Check (Input)
        guard_res = await input_guard.inspect(query)
        if not guard_res.safe:
            return QueryResponse(
                answer=f"Security Alert: {guard_res.reason}",
                sources=[],
                conversation_id=conversation_id or "security-error"
            )

        # 2. Context Awareness & Query Rewriting
        conv_id = conversation_id or "default-session"
        rewritten_query = await conversation_memory.rewrite_query(conv_id, query)

        # 3. Semantic Cache Check
        cached = await semantic_cache.get(rewritten_query)
        if cached:
            return QueryResponse(
                answer=cached.answer,
                sources=cached.sources,
                conversation_id=conv_id
            )

        # 4. Adaptive Routing
        route_config = await adaptive_router.classify_and_route(rewritten_query)
        
        # Route multi-hop directly to graph_reasoner
        if route_config.get("category") == "multi_hop":
            print("RAGPipeline: Routing to GraphReasoningAgent (Multi-Hop Intent)")
            final_trace = None
            async for event in graph_reasoner.run(rewritten_query, conv_id):
                if event["type"] == "trace":
                    final_trace = event["trace"]
            
            return QueryResponse(
                answer=final_trace.final_answer if final_trace else "No answer generated.",
                sources=[SearchResult(content=f"Step {o.step} - {o.tool}: {str(o.result)[:200]}...", metadata={}, score=1.0) for o in (final_trace.observations if final_trace else [])],
                conversation_id=conv_id
            )

        # 5. Retrieval
        raw_results = await hybrid_retriever.search(
            rewritten_query, 
            limit=route_config["top_k"], 
            filters=filters
        )
        
        # 5b. Content Filtering
        from pipeline.embedder import embedder
        query_vec = await embedder.embed_text(rewritten_query)
        
        search_results = [
            SearchResult(
                id=doc.id,
                content=doc.content,
                metadata=doc.metadata,
                score=doc.dense_score
            ) for doc in raw_results
        ]
        
        filtered_results = await content_filter.validate_results(query_vec, search_results)
        
        final_docs = [
            RetrievedDoc(
                id=res.id,
                content=res.content,
                metadata=res.metadata,
                dense_score=res.score,
                rrf_score=0.0
            ) for res in filtered_results
        ]

        # 6. CRAG (Corrective RAG) Agent
        agent_res = await crag_agent.run(rewritten_query, final_docs, conv_id)
        
        if isinstance(agent_res, RefusalResponse):
            return agent_res
            
        # Route AMBIGUOUS CRAG path to graph_reasoner
        if hasattr(agent_res, "path") and agent_res.path == "ambiguous":
            print("RAGPipeline: CRAG signaled ambiguous retrieval. Escalating to GraphReasoningAgent...")
            final_trace = None
            async for event in graph_reasoner.run(rewritten_query, conv_id):
                if event["type"] == "trace":
                    final_trace = event["trace"]
            return QueryResponse(
                answer=final_trace.final_answer if final_trace else "No answer.",
                sources=agent_res.documents,
                conversation_id=conv_id
            )

        # 7. Security Check (Output)
        redacted_answer, entity_types = output_guard.redact(agent_res.answer)
        
        # 8. Update Cache & Memory
        await semantic_cache.set(rewritten_query, CachedResponse(
            answer=redacted_answer,
            sources=agent_res.documents if hasattr(agent_res, "documents") else [],
            created_at=datetime.utcnow()
        ))
        
        await conversation_memory.add_message(conv_id, Message(role="user", content=query))
        await conversation_memory.add_message(conv_id, Message(role="assistant", content=redacted_answer))
        
        return QueryResponse(
            answer=redacted_answer,
            sources=agent_res.documents if hasattr(agent_res, "documents") else [],
            conversation_id=conv_id
        )

rag_pipeline = RAGPipeline()
