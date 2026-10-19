# Genesis RAG overview

Genesis RAG is an agentic retrieval-augmented generation (RAG) platform built by Rohan Malyadri at Obscuron X Labs. You upload documents, ask questions in plain language, and Genesis answers using only your documents, with numbered citations that link back to the source passages.

## How a question is answered

1. The input guard blocks prompt-injection, SQL-injection and path-traversal attempts.
2. A semantic cache returns a stored answer when a very similar question was asked before.
3. A conversation memory rewrites follow-up questions such as "who built it?" into complete questions.
4. An adaptive router decides how many passages to fetch for the type of question.
5. Hybrid retrieval combines dense vector search in ChromaDB with BM25 keyword search. The two ranked lists are merged with Reciprocal Rank Fusion (RRF).
6. Corrective RAG (CRAG) grades every retrieved passage as correct, ambiguous or incorrect. If at least one passage is correct only the correct ones are kept. If none are, the question is decomposed or a web search is used.
7. Google Gemini writes the answer from the approved passages and cites them as [1], [2] and so on.
8. The output guard redacts emails, phone numbers, social security numbers and credit card numbers before the answer is sent to the user.

## Main features

- Hybrid retrieval: dense embeddings (all-MiniLM-L6-v2) plus BM25, fused with RRF.
- Sharding: documents are spread over 16 ChromaDB collections using an MD5 consistent hash of the document id, so all chunks of one document live on one shard.
- PageRank authority boost: citations between documents form a graph. Highly cited documents get a ranking boost: boosted = rrf * (1 + alpha * log(1 + pagerank)).
- Multi-hop reasoning: complex questions are split into sub-questions that are searched separately.
- Security guards: input guard, content filter and PII redaction.
- A Debugger page compares three retrieval modes (Enterprise, Multi-Tenant sharding and PageRank boost) side by side with their dense, BM25, RRF, PageRank and boosted scores.

## Contact

Made with love by Rohan Malyadri from Obscuron X Labs. Website: https://rohanmalyadri.in/
