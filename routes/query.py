import json
import time
import asyncio
import google.generativeai as genai
from typing import AsyncGenerator
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from opik import track

from app.config import settings
from app.models import QueryRequest, SearchResult, PipelineTrace, FinalQueryResponse
from security.input_guard import input_guard
from security.content_filter import content_filter
from security.output_guard import output_guard
from services.semantic_cache import semantic_cache
from services.conversation import conversation_memory
from retrieval.hybrid_retriever import hybrid_retriever
from retrieval.reranker import cohere_reranker # Reranker still works but uses Cohere. If user wants ONLY Gemini, I should update this too.
from agents.adaptive_router import adaptive_router
from agents.crag import crag_agent
from agents.graph_reasoner import graph_reasoner

router = APIRouter()

class RAGStreamer:
    def __init__(self, request: QueryRequest):
        self.request = request
        self.latencies = {}
        self.start_time = 0
        self.full_answer = ""
        self.cache_hit = False
        self.crag_path = "normal"
        self.sources = []
        self.shard_stats = {}
        genai.configure(api_key=settings.GOOGLE_API_KEY)
        self.model = genai.GenerativeModel(settings.GEMINI_MODEL)

    def _start_step(self):
        self.start_time = time.perf_counter()

    def _end_step(self, name: str):
        self.latencies[name] = (time.perf_counter() - self.start_time) * 1000

    @track(name="query_pipeline_gemini")
    async def stream(self) -> AsyncGenerator[str, None]:
        # 1. Input Guard
        self._start_step()
        guard_res = await input_guard.inspect(self.request.query)
        self._end_step("input_guard")
        if not guard_res.safe:
            yield f"data: {json.dumps({'error': f'Security Block: {guard_res.reason}', 'done': True})}\n\n"
            return

        # 2. Semantic Cache
        self._start_step()
        cached = await semantic_cache.get(self.request.query)
        self._end_step("semantic_cache")
        if cached:
            self.cache_hit = True
            self.sources = cached.sources
            for token in cached.answer.split():
                yield f"data: {json.dumps({'token': token + ' ', 'done': False})}\n\n"
                await asyncio.sleep(0.01)
            yield await self._final_event()
            return

        # 3. Conversation Memory
        self._start_step()
        rewritten_query = await conversation_memory.rewrite_query(self.request.session_id, self.request.query)
        self._end_step("conversation_memory")

        # 4. Adaptive Router
        self._start_step()
        route_config = await adaptive_router.classify_and_route(rewritten_query)
        self._end_step("adaptive_router")

        # New: Direct routing for multi-hop
        if self.request.use_reasoning or route_config.get("category") == "multi_hop":
            reasoning_msg = "Forcing multi-hop reasoning as requested..." if self.request.use_reasoning else "Complex multi-hop query detected. Engaging GraphReasoningAgent..."
            yield f"data: {json.dumps({'type': 'thought', 'reasoning': reasoning_msg, 'step': 0})}\n\n"
            async for event in graph_reasoner.run(rewritten_query, self.request.session_id):
                if event["type"] in ["thought", "observation"]:
                    yield f"data: {json.dumps(event)}\n\n"
                elif event["type"] == "answer_token":
                    token = event["token"]
                    self.full_answer += token
                    yield f"data: {json.dumps({'token': token, 'done': False})}\n\n"
                elif event["type"] == "trace":
                    self.sources = [SearchResult(content=f"Step {o.step} - {o.tool}: {str(o.result)[:200]}...", metadata={}, score=1.0) for o in event["trace"].observations]
                    yield f"data: {json.dumps(event)}\n\n"
            
            yield await self._final_event()
            return

        # 5. Retrieval & Reranking
        self._start_step()
        raw_results = await hybrid_retriever.search(
            rewritten_query, 
            limit=route_config["top_k"], 
            filters=self.request.filters,
            use_sharding=self.request.use_sharding
        )
        
        # Convert RetrievedDoc to SearchResult for the reranker if needed
        # (Actually, search returns RetrievedDoc, but reranker expects SearchResult)
        search_results_for_rank = [
            SearchResult(
                id=doc.id,
                content=doc.content,
                metadata=doc.metadata,
                score=doc.dense_score
            ) for doc in raw_results
        ]
        
        ranked_results = await cohere_reranker.rerank(rewritten_query, search_results_for_rank, top_n=5)
        
        # 5b. Content Filtering (Source, Toxicity, Relevance)
        from pipeline.embedder import embedder
        query_vec = await embedder.embed_text(rewritten_query)
        results = await content_filter.validate_results(query_vec, ranked_results)
        
        self.shard_stats = hybrid_retriever.last_shard_stats
        self._end_step("retrieval_rerank")

        # 6. CRAG Agent
        self._start_step()
        agent_res = await crag_agent.run(rewritten_query, results, self.request.session_id)
        self._end_step("crag_agent")
        
        if hasattr(agent_res, "message"): # RefusalResponse
             yield f"data: {json.dumps({'token': agent_res.message, 'done': True})}\n\n"
             return

        # New: Ambiguous path escalation
        if hasattr(agent_res, "path") and agent_res.path == "ambiguous":
             yield f"data: {json.dumps({'type': 'thought', 'reasoning': 'Retrieval ambiguous. Escalating to GraphReasoningAgent...', 'step': 0})}\n\n"
             async for event in graph_reasoner.run(rewritten_query, self.request.session_id):
                if event["type"] in ["thought", "observation"]:
                    yield f"data: {json.dumps(event)}\n\n"
                elif event["type"] == "answer_token":
                    token = event["token"]
                    self.full_answer += token
                    yield f"data: {json.dumps({'token': token, 'done': False})}\n\n"
                elif event["type"] == "trace":
                    self.sources = agent_res.documents # Combine sources
                    yield f"data: {json.dumps(event)}\n\n"
             
             yield await self._final_event()
             return
             
        self.sources = agent_res.documents
        self.crag_path = agent_res.path

        # 7. Build Prompt
        self._start_step()
        system_prompt = "You are a precise assistant. Answer using ONLY the provided context. After each factual claim insert [N] where N is the source number. Be concise and accurate."
        context_str = "\n".join([f"[{i+1}] {s.content}" for i, s in enumerate(self.sources)])
        full_prompt = f"{system_prompt}\n\nContext:\n{context_str}\n\nQuestion: {rewritten_query}"
        self._end_step("prompt_build")

        # 8. Stream Gemini
        self._start_step()
        loop = asyncio.get_event_loop()
        # Gemini streaming call
        response_stream = await loop.run_in_executor(
            None, 
            lambda: self.model.generate_content(full_prompt, stream=True)
        )
        
        for chunk in response_stream:
            token = chunk.text
            self.full_answer += token
            yield f"data: {json.dumps({'token': token, 'done': False})}\n\n"
            await asyncio.sleep(0.01) # Yield to event loop
        self._end_step("gemini_stream")

        # 9. Output Guard
        self._start_step()
        redacted_answer, entities = output_guard.redact(self.full_answer)
        self._end_step("output_guard")

        # 10. Final Event
        yield await self._final_event()

    async def _final_event(self) -> str:
        trace = PipelineTrace(
            latencies=self.latencies,
            model=settings.GEMINI_MODEL,
            cache_hit=self.cache_hit,
            crag_path=self.crag_path,
            shard_stats=self.shard_stats
        )
        final_res = FinalQueryResponse(
            token="",
            sources=self.sources,
            trace=trace,
            done=True
        )
        return f"data: {final_res.model_dump_json()}\n\n"

@router.post("/")
async def query_endpoint(request: QueryRequest):
    streamer = RAGStreamer(request)
    return StreamingResponse(streamer.stream(), media_type="text/event-stream")
