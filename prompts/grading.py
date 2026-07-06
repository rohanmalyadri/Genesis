DOCUMENT_GRADER_PROMPT = """You are a grader assessing relevance of a retrieved document to a user question. 
If the document contains keyword(s) or semantic meaning related to the user question, grade it as relevant. 
It does not need to be a perfect answer.

Question: {question}
Document: {document}

Give a binary score 'yes' or 'no' score to indicate whether the document is relevant to the question.
Score:"""

HALLUCINATION_GRADER_PROMPT = """You are a grader assessing whether an LLM generation is grounded in / supported by a set of retrieved facts. 
Give a binary score 'yes' or 'no'. 'yes' means that the answer is grounded in / supported by the set of facts.

Facts: {documents}
Answer: {generation}

Score:"""
