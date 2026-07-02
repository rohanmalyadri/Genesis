import google.generativeai as genai
import json
import asyncio
from typing import List
from app.config import settings
from app.models import SearchResult

class GeminiReranker:
    def __init__(self):
        genai.configure(api_key=settings.GOOGLE_API_KEY)
        self.model = genai.GenerativeModel(settings.GEMINI_MODEL)

    async def rerank(self, query: str, results: List[SearchResult], top_n: int = 5) -> List[SearchResult]:
        if not results:
            return []
            
        # Extract documents for reranking
        docs_text = "\n".join([f"ID {i}: {res.content}" for i, res in enumerate(results)])
        
        prompt = f"""Rerank the following documents based on their relevance to the query.
Return ONLY a JSON array of document IDs in order of relevance, from most to least relevant.
Format: ["ID 0", "ID 2", ...]

Query: {query}
Documents:
{docs_text}
"""
        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.model.generate_content(
                    prompt,
                    generation_config=genai.types.GenerationConfig(response_mime_type="application/json")
                )
            )
            
            # Parse the list of IDs
            try:
                ranked_ids = json.loads(response.text)
                # If it's a list of strings like ["ID 0", "ID 2"]
                indices = []
                for rid in ranked_ids:
                    try:
                        idx = int(rid.replace("ID ", ""))
                        indices.append(idx)
                    except:
                        continue
                
                reranked_results = []
                for idx in indices[:top_n]:
                    if idx < len(results):
                        reranked_results.append(results[idx])
                
                return reranked_results
            except:
                return results[:top_n]
                
        except Exception as e:
            print(f"GeminiReranker Error: {e}")
            return results[:top_n]

gemini_reranker = GeminiReranker()
# Alias for backward compatibility if needed, but we'll use gemini_reranker
cohere_reranker = gemini_reranker 
