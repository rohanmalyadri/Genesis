import asyncio
import json
from typing import List, Dict, Any, Union
import google.generativeai as genai
from app.config import settings
from app.models import RetrievedDoc, SearchResult, GradingResult, AgentResponse, RefusalResponse, CRAGResult
from services.query_decomposer import query_decomposer
from retrieval.hybrid_retriever import hybrid_retriever
from services.document_grader import document_grader
from .tools.web_search import web_search_tool

class CRAGAgent:
    def __init__(self):
        genai.configure(api_key=settings.GOOGLE_API_KEY)
        self.model = genai.GenerativeModel(settings.GEMINI_MODEL)

    async def run(self, query: str, retrieved_docs: List[RetrievedDoc], session_id: str, max_depth: int = 3) -> Union[CRAGResult, RefusalResponse]:
        if max_depth <= 0:
            print("CRAG: Max depth reached. Returning current context...")
            if not retrieved_docs:
                return RefusalResponse()
            return CRAGResult(documents=retrieved_docs, path="max_depth")

        print(f"CRAG: Grading {len(retrieved_docs)} documents using Gemini... (Depth: {4-max_depth})")
        
        # Step 1: Parallel grading using centralized service
        grading_tasks = [document_grader.grade_relevance(query, doc.content) for doc in retrieved_docs[:5]]
        grading_results = await asyncio.gather(*grading_tasks)
        
        correct_docs = [doc for doc, res in zip(retrieved_docs, grading_results) if res.relevance == "correct"]
        ambiguous_docs = [doc for doc, res in zip(retrieved_docs, grading_results) if res.relevance == "ambiguous"]
        
        # Step 2: Branching
        if len(correct_docs) >= 3:
            print("CRAG: Correct path selected.")
            return CRAGResult(documents=correct_docs, path="correct")
            
        elif len(ambiguous_docs) > 0 or (len(correct_docs) < 3 and len(correct_docs) > 0):
            print("CRAG: Ambiguous path selected. Decomposing query...")
            sub_queries = await query_decomposer.decompose(query)
            
            all_new_docs = []
            for sub_q in sub_queries:
                new_docs = await hybrid_retriever.search(sub_q, limit=5)
                all_new_docs.extend(new_docs)
            
            # Merge unique by ID
            unique_docs = {doc.id: doc for doc in all_new_docs}.values()
            return await self.run(query, list(unique_docs), session_id, max_depth=max_depth-1) # Recursive re-grade
            
        else:
            print("CRAG: Incorrect path selected. Triggering web search...")
            web_results = await web_search_tool.run(query)
            if not web_results:
                return RefusalResponse()
                
            # Re-grade web results
            web_grading_tasks = [document_grader.grade_relevance(query, doc.content) for doc in web_results]
            web_grading_results = await asyncio.gather(*web_grading_tasks)
            
            final_docs = [doc for doc, res in zip(web_results, web_grading_results) if res.relevance in ["correct", "ambiguous"]]
            
            if not final_docs:
                return RefusalResponse()
                
            return CRAGResult(documents=final_docs, path="incorrect")



crag_agent = CRAGAgent()
