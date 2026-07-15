import pytest
import json
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from agents.graph_reasoner import GraphReasoningAgent
from app.models import (
    Thought, Observation, ReActTrace, RetrievedDoc, NeighborResult, EntityNode, EntityContext
)

@pytest.fixture
def mock_agent():
    with patch("agents.graph_reasoner.settings") as mock_settings:
        mock_settings.OPENAI_API_KEY = "sk-test-key"
        with patch("agents.graph_reasoner.AsyncOpenAI") as mock_openai:
            agent = GraphReasoningAgent()
            agent.client = AsyncMock()
            return agent

async def make_mock_stream(chunk):
    yield chunk

@pytest.mark.asyncio
async def test_graph_reasoner_stops_at_finish(mock_agent):
    mock_thought = {
        "reasoning": "I have all the info.",
        "action": "FINISH",
        "action_input": {"answer": "The answer is 42", "citations": ["doc1"]},
        "confidence": 0.9,
        "confidence_reason": "High confidence"
    }
    
    mock_thought_res = MagicMock()
    mock_thought_res.choices = [MagicMock(message=MagicMock(content=json.dumps(mock_thought)))]
    
    mock_chunk = MagicMock()
    mock_chunk.choices = [MagicMock(delta=MagicMock(content="Final answer"))]
    
    async def mock_call(*args, **kwargs):
        if kwargs.get("stream"):
            return make_mock_stream(mock_chunk)
        else:
            return mock_thought_res

    mock_agent.client.chat.completions.create = AsyncMock(side_effect=mock_call)

    events = []
    async for event in mock_agent.run("What is the meaning of life?", "session1"):
        events.append(event)

    assert any(e["type"] == "thought" and e["action"] == "FINISH" for e in events)
    trace_event = next(e for e in events if e["type"] == "trace")
    assert trace_event["trace"].stopped_reason == "finished"
    assert "Final answer" in trace_event["trace"].final_answer

@pytest.mark.asyncio
async def test_graph_reasoner_max_hops(mock_agent):
    mock_thought = {
        "reasoning": "Need more hops.",
        "action": "vector_search",
        "action_input": {"query": "test"},
        "confidence": 0.5,
        "confidence_reason": "More info needed"
    }
    
    mock_thought_res = MagicMock()
    mock_thought_res.choices = [MagicMock(message=MagicMock(content=json.dumps(mock_thought)))]
    
    mock_chunk = MagicMock()
    mock_chunk.choices = [MagicMock(delta=MagicMock(content="Done"))]
    
    async def mock_call(*args, **kwargs):
        if kwargs.get("stream"):
            return make_mock_stream(mock_chunk)
        else:
            return mock_thought_res

    mock_agent.client.chat.completions.create = AsyncMock(side_effect=mock_call)
    
    mock_agent._vector_search_tool = AsyncMock(return_value=Observation(
        step=1, tool="vector_search", result=[], result_confidence=0.5, latency_ms=10.0
    ))

    events = []
    async for event in mock_agent.run("test query", "session1", max_hops=2):
        events.append(event)

    trace_event = next(e for e in events if e["type"] == "trace")
    assert trace_event["trace"].hops == 2
    assert trace_event["trace"].stopped_reason == "max_hops"

@pytest.mark.asyncio
async def test_graph_reasoner_no_new_info(mock_agent):
    mock_thought = {
        "reasoning": "Checking Einstein again.",
        "action": "entity_context",
        "action_input": {"entity_name": "Einstein"},
        "confidence": 0.5,
        "confidence_reason": "Re-checking"
    }
    
    mock_thought_res = MagicMock()
    mock_thought_res.choices = [MagicMock(message=MagicMock(content=json.dumps(mock_thought)))]
    
    mock_chunk = MagicMock()
    mock_chunk.choices = [MagicMock(delta=MagicMock(content="Done"))]
    
    async def mock_call(*args, **kwargs):
        if kwargs.get("stream"):
            return make_mock_stream(mock_chunk)
        else:
            return mock_thought_res

    mock_agent.client.chat.completions.create = AsyncMock(side_effect=mock_call)
    
    mock_agent._entity_context_tool = AsyncMock(return_value=Observation(
        step=1, tool="entity_context", result="Einstein info", result_confidence=0.9, latency_ms=10.0
    ))

    events = []
    async for event in mock_agent.run("Who is Einstein?", "session1", max_hops=3):
        events.append(event)
    
    trace_event = next(e for e in events if e["type"] == "trace")
    assert trace_event["trace"].stopped_reason == "no_new_info"

@pytest.mark.asyncio
async def test_tool_failure_recovery(mock_agent):
    mock_thought = {
        "reasoning": "Let's search.",
        "action": "vector_search",
        "action_input": {"query": "fail"},
        "confidence": 0.4,
        "confidence_reason": "Searching"
    }
    mock_finish = {
        "reasoning": "done",
        "action": "FINISH",
        "action_input": {"answer": "fail"},
        "confidence": 1.0
    }
    
    res1 = MagicMock()
    res1.choices = [MagicMock(message=MagicMock(content=json.dumps(mock_thought)))]
    res2 = MagicMock()
    res2.choices = [MagicMock(message=MagicMock(content=json.dumps(mock_finish)))]
    
    mock_chunk = MagicMock()
    mock_chunk.choices = [MagicMock(delta=MagicMock(content="Done"))]
    
    responses = [res1, res2]
    
    async def mock_call(*args, **kwargs):
        if kwargs.get("stream"):
            return make_mock_stream(mock_chunk)
        else:
            return responses.pop(0)

    mock_agent.client.chat.completions.create = AsyncMock(side_effect=mock_call)
    
    with patch("agents.graph_reasoner.hybrid_retriever.search", side_effect=Exception("Database down")):
        events = []
        async for event in mock_agent.run("fail", "session1"):
            events.append(event)
        
        assert any(e["type"] == "observation" and "Error" in e["result_summary"] for e in events)
        trace_event = next(e for e in events if e["type"] == "trace")
        assert trace_event["trace"].stopped_reason == "finished"
