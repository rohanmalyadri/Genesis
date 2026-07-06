import json
import asyncio
import google.generativeai as genai
from typing import Dict, Any
from app.config import settings

class AdaptiveRouter:
    def __init__(self):
        genai.configure(api_key=settings.GOOGLE_API_KEY)
        self.model = genai.GenerativeModel(settings.GEMINI_MODEL)
        self.configs = {
            "factual": {"top_k": 5, "prompt": "rag_v1"},
            "analytical": {"top_k": 8, "prompt": "analytical_v1"},
            "conversational": {"top_k": 3, "prompt": "conv_v1"},
            "code": {"top_k": 5, "prompt": "code_v1"},
            "multi_hop": {"top_k": 10, "prompt": "multi_hop_v1"}
        }

    async def classify_and_route(self, query: str) -> Dict[str, Any]:
        prompt = f"""Classify the following user query into exactly one of these categories: 
[factual, analytical, conversational, code, multi_hop]

Query: {query}

Return ONLY JSON: {{"category": "category_name"}}"""

        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.model.generate_content(
                    prompt,
                    generation_config=genai.types.GenerationConfig(response_mime_type="application/json")
                )
            )
            data = json.loads(response.text)
            category = data.get("category", "factual")
            
            config = self.configs.get(category, self.configs["factual"])
            print(f"AdaptiveRouter (Gemini): Classified as {category}, using top_k={config['top_k']}")
            
            return {
                "category": category,
                "top_k": config["top_k"],
                "prompt_template": config["prompt"]
            }
        except Exception as e:
            print(f"AdaptiveRouter error: {e}")
            return self.configs["factual"]

adaptive_router = AdaptiveRouter()
