from typing import Dict, Any

RAG_PROMPT_V1 = """Use the following pieces of context to answer the user's question. 
If you don't know the answer, just say that you don't know, don't try to make up an answer.

Context: {context}

Question: {question}

Answer:"""

QUERY_DECOMPOSITION_PROMPT = """You are an expert at breaking down complex questions into simpler sub-questions.
Given a user query, decompose it into 1-3 distinct search queries that will help find the answer.

Query: {query}

Sub-questions:"""

TEMPLATES: Dict[str, str] = {
    "rag_v1": RAG_PROMPT_V1,
    "decompose": QUERY_DECOMPOSITION_PROMPT
}
