import asyncio
import dataclasses
import json
import time
from typing import AsyncGenerator, List

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from app.tracing import track

from app.config import settings
from app.models import (
    QueryRequest, SearchResult, RetrievedDoc, PipelineTrace, FinalQueryResponse,
    CachedResponse, Message,
)
from security.input_guard import input_guard
from security.content_filter import content_filter
from security.output_guard import output_guard, StreamRedactor
from services.semantic_cache import semantic_cache
from services.conversation import conversation_memory
from services import llm
from services.llm import resolve_model
from services.query_decomposer import query_decomposer
from retrieval.hybrid_retriever import hybrid_retriever
from retrieval.reranker import reranker
from retrieval.filters import FilterParams
from agents.adaptive_router import adaptive_router
from agents.crag import crag_agent

router = APIRouter()

SYSTEM_PROMPT = (
    "You are a precise assistant. Answer using ONLY the provided context. "
    "After each factual claim insert [N] where N is the source number. Be concise and accurate."
)


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload, default=str)}\n\n"


def _friendly_error(e: Exception) -> str:
    text = str(e)
    low = text.lower()
    if "api key" in low or "api_key" in low or "permission" in low or "unauthenticated" in low:
        return "The Gemini API key is missing or invalid. Check GOOGLE_API_KEY in your .env file."
    if "perday" in low or "per day" in low:
        return ("The free-tier daily Gemini quota is used up for every available model. "
                "It resets daily; adding billing to the Google AI Studio project removes the limit.")
    if "quota" in low or "429" in low or "rate" in low:
        return "The Gemini API rate limit or quota was reached. Please try again in a moment."
    return f"The language model request failed: {text[:200]}"


def _display_score(doc: RetrievedDoc) -> float:
    """Relevance score shown in the UI (cosine similarity, or a squashed BM25 score)."""
    if doc.dense_score and doc.dense_score > 0:
        return float(doc.dense_score)
    if doc.bm25_score:
        return min(1.0, float(doc.bm25_score) / 20.0)
    return float(doc.score)


def _as_sources(docs: List[SearchResult]) -> List[SearchResult]:
    return [
        SearchResult(
            id=d.id, content=d.content, metadata=d.metadata,
            score=_display_score(d) if isinstance(d, RetrievedDoc) else d.score,
        )
        for d in docs
    ]


_reasoner_cache = {"checked_at": 0.0, "ok": False}


async def _graph_reasoner_available() -> bool:
    """The ReAct graph agent needs an OpenAI key and a reachable Neo4j (cached 30s)."""
    if not settings.OPENAI_API_KEY or not settings.GRAPH_ENABLED:
        return False
    if time.time() - _reasoner_cache["checked_at"] < 30:
        return _reasoner_cache["ok"]
    ok = False
    try:
        from retrieval.graph_store import graph_store
        await graph_store.connect()
        ok = await asyncio.wait_for(graph_store.ping(), timeout=3)
    except Exception:
        ok = False
    _reasoner_cache.update(checked_at=time.time(), ok=ok)
    return ok


class RAGStreamer:
    def __init__(self, request: QueryRequest):
        self.request = request
        self.latencies = {}
        self.start_time = 0.0
        self.full_answer = ""
        self.cache_hit = False
        self.crag_path = "normal"
        self.sources: List[SearchResult] = []
        self.shard_stats = {}
        self.model_name = resolve_model(request.model)
        self.redactor = StreamRedactor(output_guard, enabled=request.output_guard)
        filters = request.filters.model_dump() if request.filters else {}
        self.cache_ns = json.dumps({
            "sharding": request.use_sharding, "reasoning": request.use_reasoning,
            "model": self.model_name, "top_k": request.top_k, "filters": filters,
            "content_filter": request.content_filter, "output_guard": request.output_guard,
        }, sort_keys=True)

    def _start_step(self):
        self.start_time = time.perf_counter()

    def _end_step(self, name: str):
        self.latencies[name] = (time.perf_counter() - self.start_time) * 1000

    def _emit_token(self, token: str) -> str:
        """Redact (if enabled) and wrap a token as an SSE event; '' when still buffered."""
        safe = self.redactor.feed(token)
        self.full_answer += safe
        return _sse({"token": safe, "done": False}) if safe else ""

    def _flush(self) -> str:
        tail = self.redactor.flush()
        self.full_answer += tail
        return _sse({"token": tail, "done": False}) if tail else ""

    async def _decomposition_reasoning(self, query: str, filters) -> AsyncGenerator[str, None]:
        """Multi-hop fallback that only needs Gemini: split the question, retrieve per part."""
        self._start_step()
        yield _sse({"type": "thought", "step": 0, "reasoning": "Breaking the question into smaller sub-questions.",
                    "action": "decompose_query", "action_input": {"query": query}, "confidence": 0.5})
        sub_queries = (await query_decomposer.decompose(query))[:4] or [query]
        yield _sse({"type": "observation", "step": 0, "tool": "decompose_query",
                    "result_summary": f"{len(sub_queries)} sub-queries: " + " | ".join(sub_queries), "latency_ms": 0})

        merged = {}
        for i, sub in enumerate(sub_queries, start=1):
            yield _sse({"type": "thought", "step": i, "reasoning": f"Searching the knowledge base for: {sub}",
                        "action": "vector_search", "action_input": {"query": sub}, "confidence": 0.6})
            t0 = time.perf_counter()
            docs = await hybrid_retriever.search(sub, limit=5, filters=filters, use_sharding=self.request.use_sharding)
            for d in docs:
                merged.setdefault(d.id, d)
            yield _sse({"type": "observation", "step": i, "tool": "vector_search",
                        "result_summary": f"Found {len(docs)} relevant chunks", "latency_ms": (time.perf_counter() - t0) * 1000})
        self.reasoning_docs = list(merged.values())
        self.reasoning_hops = len(sub_queries)
        self._end_step("multi_hop_reasoning")

    @track(name="query_pipeline_gemini")
    async def stream(self) -> AsyncGenerator[str, None]:
        try:
            async for event in self._stream():
                yield event
        except Exception as e:  # noqa: BLE001
            print(f"Query pipeline error: {type(e).__name__}: {e}")
            yield _sse({"error": _friendly_error(e), "done": True})

    async def _stream(self) -> AsyncGenerator[str, None]:
        req = self.request

        # 1. Input guard
        if req.input_guard:
            self._start_step()
            guard_res = await input_guard.inspect(req.query)
            self._end_step("input_guard")
            if not guard_res.safe:
                yield _sse({"error": f"Security Block: {guard_res.reason}", "done": True})
                return

        # 2. Semantic cache
        self._start_step()
        cached = await semantic_cache.get(req.query, ns=self.cache_ns)
        self._end_step("semantic_cache")
        if cached:
            self.cache_hit = True
            self.sources = cached.sources
            for token in cached.answer.split(" "):
                yield _sse({"token": token + " ", "done": False})
                await asyncio.sleep(0.008)
            self.full_answer = cached.answer
            yield self._final_event()
            return

        # 3. Conversation memory
        self._start_step()
        rewritten_query = await conversation_memory.rewrite_query(req.session_id, req.query)
        self._end_step("conversation_memory")

        # 4. Adaptive router
        self._start_step()
        route_config = await adaptive_router.classify_and_route(rewritten_query)
        self._end_step("adaptive_router")

        filters = req.filters or FilterParams()
        wants_reasoning = req.use_reasoning or route_config.get("category") == "multi_hop"
        reasoning_hops = 0
        used_graph_agent = False

        # 5. Multi-hop reasoning (graph ReAct agent if available, else Gemini decomposition)
        if wants_reasoning:
            if await _graph_reasoner_available():
                used_graph_agent = True
                yield _sse({"type": "thought", "reasoning": "Engaging the graph reasoning agent...", "step": 0})
                from agents.graph_reasoner import graph_reasoner  # heavy imports only when used
                async for event in graph_reasoner.run(rewritten_query, req.session_id):
                    if event["type"] in ("thought", "observation"):
                        yield _sse(event)
                    elif event["type"] == "answer_token":
                        out = self._emit_token(event["token"])
                        if out:
                            yield out
                    elif event["type"] == "trace":
                        self.sources = [
                            SearchResult(content=f"Step {o.step} - {o.tool}: {str(o.result)[:200]}...", metadata={}, score=1.0)
                            for o in event["trace"].observations
                        ]
                        yield _sse({"type": "trace", "trace": dataclasses.asdict(event["trace"])})
                tail = self._flush()
                if tail:
                    yield tail
                await self._remember(req.query)
                yield self._final_event()
                return
            self.reasoning_docs, self.reasoning_hops = [], 0
            async for event in self._decomposition_reasoning(rewritten_query, filters):
                yield event
            reasoning_hops = self.reasoning_hops

        # 6. Retrieval + reranking
        self._start_step()
        if reasoning_hops:
            raw_results = self.reasoning_docs
        else:
            raw_results = await hybrid_retriever.search(
                rewritten_query,
                limit=max(route_config["top_k"], req.top_k),
                filters=filters,
                use_sharding=req.use_sharding,
            )
        authority_weight = 2.0 if filters.authority_mode else 1.0
        if len(raw_results) > req.top_k:
            results = await reranker.rerank(rewritten_query, raw_results, top_n=req.top_k, authority_weight=authority_weight)
        else:
            results = raw_results  # nothing to cut, so skip the extra LLM call

        if req.content_filter:
            from pipeline.embedder import embedder
            query_vec = await embedder.embed_text(rewritten_query)
            results = await content_filter.validate_results(query_vec, results)
        self.shard_stats = hybrid_retriever.last_shard_stats
        self._end_step("retrieval_rerank")

        # 7. Corrective RAG: grade the documents, fall back to web search if needed
        self._start_step()
        agent_res = await crag_agent.run(rewritten_query, results, req.session_id)
        self._end_step("crag_agent")

        if hasattr(agent_res, "message"):  # RefusalResponse
            self.crag_path = "refusal"
            yield _sse({"token": agent_res.message, "done": False})
            self.full_answer = agent_res.message
            yield self._final_event()
            return

        self.sources = _as_sources(agent_res.documents)
        self.crag_path = agent_res.path

        # 8. Build the prompt and stream Gemini
        self._start_step()
        context_str = "\n".join(f"[{i + 1}] {s.content}" for i, s in enumerate(self.sources))
        prompt = f"{SYSTEM_PROMPT}\n\nContext:\n{context_str}\n\nQuestion: {rewritten_query}"
        async for piece in llm.stream(prompt, model=self.model_name):
            out = self._emit_token(piece)
            if out:
                yield out
        tail = self._flush()
        if tail:
            yield tail
        self._end_step("gemini_stream")

        if reasoning_hops:
            yield _sse({"type": "trace", "trace": {
                "query": rewritten_query, "final_answer": self.full_answer, "final_confidence": 0.8,
                "hops": reasoning_hops, "stopped_reason": "confidence_threshold",
            }})

        # 9. Remember the answer (cache + conversation)
        await semantic_cache.set(
            req.query, CachedResponse(answer=self.full_answer, sources=self.sources), ns=self.cache_ns, ttl=req.cache_ttl
        )
        await self._remember(req.query)
        yield self._final_event()

    async def _remember(self, user_query: str):
        sid = self.request.session_id
        await conversation_memory.add_message(sid, Message(role="user", content=user_query))
        await conversation_memory.add_message(sid, Message(role="assistant", content=self.full_answer))

    def _final_event(self) -> str:
        trace = PipelineTrace(
            latencies=self.latencies,
            model=self.model_name,
            cache_hit=self.cache_hit,
            crag_path=self.crag_path,
            shard_stats=self.shard_stats,
        )
        final = FinalQueryResponse(token="", sources=self.sources, trace=trace, done=True)
        return f"data: {final.model_dump_json()}\n\n"


@router.post("/")
async def query_endpoint(request: QueryRequest):
    streamer = RAGStreamer(request)
    return StreamingResponse(
        streamer.stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
