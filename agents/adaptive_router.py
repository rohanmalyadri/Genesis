import json
import re
from typing import Dict, Any
from app.config import settings
from services import llm

GREETING = re.compile(r"^\s*(hi|hello|hey|thanks|thank you|ok|okay|cool|good (morning|evening|afternoon))\b", re.I)
CODE_HINT = re.compile(r"\b(def|class|function|import|stack trace|exception|compile|bug|code|api|regex|sql)\b|[{};]|```", re.I)
MULTI_HOP_HINT = re.compile(
    r"\b(both|compare|versus|vs\.?|relationship|how (do|does|are|is) .+ (and|affect|influence|relate)|"
    r"and also|as well as|which .+ and which|what .+ and (how|why|what))\b",
    re.I,
)
ANALYTICAL_HINT = re.compile(r"\b(why|explain|analy[sz]e|summari[sz]e|difference|impact|pros and cons|trend)\b", re.I)


class AdaptiveRouter:
    """Chooses how many chunks to fetch and which prompt style fits the question.

    By default this uses fast local rules (no API call). Set ROUTER_USE_LLM=true
    to classify with Gemini instead.
    """

    def __init__(self):
        self.configs = {
            "factual": {"top_k": 5, "prompt": "rag_v1"},
            "analytical": {"top_k": 8, "prompt": "analytical_v1"},
            "conversational": {"top_k": 3, "prompt": "conv_v1"},
            "code": {"top_k": 5, "prompt": "code_v1"},
            "multi_hop": {"top_k": 10, "prompt": "multi_hop_v1"},
        }

    def _classify_locally(self, query: str) -> str:
        if GREETING.search(query) and len(query.split()) <= 6:
            return "conversational"
        if MULTI_HOP_HINT.search(query) or query.count("?") > 1 or len(query.split()) > 35:
            return "multi_hop"
        if CODE_HINT.search(query):
            return "code"
        if ANALYTICAL_HINT.search(query):
            return "analytical"
        return "factual"

    async def _classify_with_llm(self, query: str) -> str:
        prompt = f"""Classify the following user query into exactly one of these categories:
[factual, analytical, conversational, code, multi_hop]

Query: {query}

Return ONLY JSON: {{"category": "category_name"}}"""
        data = json.loads(await llm.generate(prompt, json_mode=True))
        return data.get("category", "factual")

    async def classify_and_route(self, query: str) -> Dict[str, Any]:
        category = self._classify_locally(query)
        if settings.ROUTER_USE_LLM:
            try:
                category = await self._classify_with_llm(query)
            except Exception as e:
                print(f"AdaptiveRouter: LLM classification failed ({e}); using local rules")
        if category not in self.configs:
            category = "factual"
        config = self.configs[category]
        print(f"AdaptiveRouter: classified as {category}, top_k={config['top_k']}")
        return {"category": category, "top_k": config["top_k"], "prompt_template": config["prompt"]}

adaptive_router = AdaptiveRouter()
