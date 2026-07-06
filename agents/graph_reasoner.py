import json
import time
import logging
import asyncio
from typing import List, Dict, Any, Optional, Tuple, AsyncGenerator
from openai import AsyncOpenAI
from app.config import settings
from app.models import (
    Thought, Observation, ReActTrace, EntityNode, RelationEdge,
    NeighborResult, PathStep, EntityContext
)
from retrieval.graph_store import graph_store
from retrieval.hybrid_retriever import hybrid_retriever
from tools.web_search import web_search

logger = logging.getLogger("GraphReasoner")

class GraphReasoningAgent:
    def __init__(self):
        if not settings.OPENAI_API_KEY:
            logger.warning("OPENAI_API_KEY not configured. GraphReasoningAgent will fail on run.")
            self.client = None
        else:
            self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = "gpt-4o"

    async def _vector_search_tool(self, query: str, top_k: int = 5) -> Observation:
        start_time = time.perf_counter()
        try:
            docs = await hybrid_retriever.search(query, limit=top_k)
            scores = [d.dense_score for d in docs]
            confidence = sum(scores) / len(scores) if scores else 0.0
            latency = (time.perf_counter() - start_time) * 1000
            return Observation(
                step=0,
                tool="vector_search",
                result=[{"id": d.id, "content": d.content, "metadata": d.metadata} for d in docs],
                result_confidence=min(1.0, confidence),
                latency_ms=latency
            )
        except Exception as e:
            return Observation(0, "vector_search", f"Error: {e}", 0.0, (time.perf_counter()-start_time)*1000)

    async def _graph_neighbors_tool(self, entity_name: str, relation_types: List[str] = None, min_confidence: float = 0.5) -> Observation:
        start_time = time.perf_counter()
        try:
            entities = await graph_store.search_entities_by_name(entity_name, fuzzy=True, limit=1)
            if not entities:
                return Observation(0, "graph_neighbors", f"Entity '{entity_name}' not found", 0.0, (time.perf_counter()-start_time)*1000)
            
            entity_id = entities[0].id
            neighbors = await graph_store.get_neighbors(entity_id, min_confidence=min_confidence)
            confidences = [n.confidence for n in neighbors]
            avg_conf = sum(confidences) / len(confidences) if confidences else 0.5
            latency = (time.perf_counter() - start_time) * 1000
            return Observation(
                step=0,
                tool="graph_neighbors",
                result=[{"entity": n.entity.name, "relation": n.relation, "confidence": n.confidence} for n in neighbors],
                result_confidence=avg_conf,
                latency_ms=latency
            )
        except Exception as e:
            return Observation(0, "graph_neighbors", f"Error: {e}", 0.0, (time.perf_counter()-start_time)*1000)

    async def _graph_path_tool(self, source_entity: str, target_entity: str, max_hops: int = 4) -> Observation:
        start_time = time.perf_counter()
        try:
            s_ents = await graph_store.search_entities_by_name(source_entity, fuzzy=True, limit=1)
            t_ents = await graph_store.search_entities_by_name(target_entity, fuzzy=True, limit=1)
            if not s_ents or not t_ents:
                return Observation(0, "graph_path", "One or both entities not found", 0.0, (time.perf_counter()-start_time)*1000)
            path = await graph_store.get_shortest_path(s_ents[0].id, t_ents[0].id, max_hops=max_hops)
            if not path:
                return Observation(0, "graph_path", "No path found", 0.0, (time.perf_counter()-start_time)*1000)
            latency = (time.perf_counter() - start_time) * 1000
            return Observation(
                step=0,
                tool="graph_path",
                result={"path": [s.entity.name for s in path], "relations": [s.relation for s in path if s.relation]},
                result_confidence=0.8,
                latency_ms=latency
            )
        except Exception as e:
            return Observation(0, "graph_path", f"Error: {e}", 0.0, (time.perf_counter()-start_time)*1000)

    async def _entity_context_tool(self, entity_name: str) -> Observation:
        start_time = time.perf_counter()
        try:
            entities = await graph_store.search_entities_by_name(entity_name, fuzzy=True, limit=1)
            if not entities:
                return Observation(0, "entity_context", "Entity not found", 0.1, (time.perf_counter()-start_time)*1000)
            context = await graph_store.get_entity_context(entities[0].id)
            latency = (time.perf_counter() - start_time) * 1000
            return Observation(
                step=0,
                tool="entity_context",
                result={"entity": context.entity.name, "relations": [{"target": r.entity.name, "type": r.relation} for r in context.relations]},
                result_confidence=0.9,
                latency_ms=latency
            )
        except Exception as e:
            return Observation(0, "entity_context", f"Error: {e}", 0.0, (time.perf_counter()-start_time)*1000)

    async def _web_search_tool(self, query: str) -> Observation:
        start_time = time.perf_counter()
        try:
            results = await web_search(query)
            latency = (time.perf_counter() - start_time) * 1000
            return Observation(step=0, tool="web_search", result=results, result_confidence=0.5, latency_ms=latency)
        except Exception as e:
            return Observation(0, "web_search", f"Error: {e}", 0.0, (time.perf_counter()-start_time)*1000)

    async def run(self, query: str, session_id: str, max_hops: int = 5, confidence_threshold: float = 0.85) -> AsyncGenerator[Dict[str, Any], None]:
        accumulated_context: List[Observation] = []
        thoughts: List[Thought] = []
        seen_entities = set()
        current_confidence = 0.0
        hops = 0
        stopped_reason = "max_hops"

        system_prompt = """
        You are a multi-hop reasoning agent. Your job is to answer complex questions by
        iteratively gathering evidence from a knowledge graph and document corpus.
        
        At each step, output ONLY valid JSON in this exact format:
        {
            "reasoning": "your step-by-step thinking about what you know and what's missing",
            "action": "tool_name",
            "action_input": {...tool arguments...},
            "confidence": 0.0-1.0,
            "confidence_reason": "why you assigned this confidence score"
        }
        
        Available tools: vector_search, graph_neighbors, graph_path, entity_context, web_search.
        
        Stop calling tools when confidence >= 0.85 OR you have called 5 tools.
        When ready to answer, set action = "FINISH" and action_input = {"answer": "your answer", "citations": ["source1"]}.
        """

        messages = [{"role": "system", "content": system_prompt}]

        for i in range(max_hops + 2):
            history = []
            for t, o in zip(thoughts, accumulated_context):
                history.append(f"Step {t.step} — Thought: {t.reasoning}\nAction: {t.action}({t.action_input})\nObservation: {o.result}")
            
            user_msg = "\n\n".join(history) + f"\n\nQuestion: {query}" if history else f"Question: {query}"
            curr_messages = messages + [{"role": "user", "content": user_msg}]

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=curr_messages,
                response_format={"type": "json_object"}
            )
            
            try:
                thought_data = json.loads(response.choices[0].message.content)
                thought = Thought(
                    step=i + 1,
                    reasoning=thought_data["reasoning"],
                    action=thought_data["action"],
                    action_input=thought_data["action_input"],
                    confidence=thought_data["confidence"]
                )
                thoughts.append(thought)
                yield {"type": "thought", "step": thought.step, "reasoning": thought.reasoning, "action": thought.action, "confidence": thought.confidence}
            except Exception as e:
                logger.error(f"Failed to parse thought JSON: {e}")
                stopped_reason = "error"
                break

            if thought.action == "FINISH":
                stopped_reason = "finished"
                break
            
            if thought.confidence >= confidence_threshold:
                stopped_reason = "confidence_threshold"
                break
            
            if hops >= max_hops:
                stopped_reason = "max_hops"
                break

            # NO NEW INFO CHECK
            tool_entities = []
            if "entity_name" in thought.action_input: tool_entities.append(thought.action_input["entity_name"])
            if "source_entity" in thought.action_input: tool_entities.append(thought.action_input["source_entity"])
            if "target_entity" in thought.action_input: tool_entities.append(thought.action_input["target_entity"])
            
            if tool_entities and all(e in seen_entities for e in tool_entities):
                stopped_reason = "no_new_info"
                break
            for e in tool_entities: seen_entities.add(e)

            # Execute Tool
            obs = None
            if thought.action == "vector_search":
                obs = await self._vector_search_tool(**thought.action_input)
            elif thought.action == "graph_neighbors":
                obs = await self._graph_neighbors_tool(**thought.action_input)
            elif thought.action == "graph_path":
                obs = await self._graph_path_tool(**thought.action_input)
            elif thought.action == "entity_context":
                obs = await self._entity_context_tool(**thought.action_input)
            elif thought.action == "web_search":
                obs = await self._web_search_tool(**thought.action_input)
            else:
                obs = Observation(i+1, thought.action, "Unknown tool", 0.0, 0.0)

            obs.step = i + 1
            accumulated_context.append(obs)
            yield {"type": "observation", "step": obs.step, "tool": obs.tool, "result_summary": str(obs.result)[:100] + "..."}
            
            current_confidence = 0.6 * current_confidence + 0.4 * obs.result_confidence
            hops += 1

        # Final generation
        context_summary = "\n".join([f"Step {o.step} ({o.tool}): {o.result}" for o in accumulated_context])
        final_prompt = f"Based on this evidence:\n{context_summary}\n\nAnswer the question: {query}"
        
        final_response = await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": final_prompt}],
            stream=True
        )
        
        full_answer = ""
        async for chunk in final_response:
            token = chunk.choices[0].delta.content or ""
            full_answer += token
            yield {"type": "answer_token", "token": token}

        trace = ReActTrace(
            query=query,
            thoughts=thoughts,
            observations=accumulated_context,
            final_answer=full_answer,
            final_confidence=0.9,
            hops=hops,
            stopped_reason=stopped_reason
        )
        yield {"type": "trace", "trace": trace}

graph_reasoner = GraphReasoningAgent()
