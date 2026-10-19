# Retrieval design notes

These notes explain two design choices in Genesis RAG and cite the sources they build on.

## Why hybrid search

Dense vector search finds passages with a similar meaning, even when the words differ. BM25 finds passages that contain the exact rare words in the question, such as names and identifiers. Combining both with Reciprocal Rank Fusion (RRF) is more robust than either alone. RRF scores a passage by summing 1 / (60 + rank) over every ranked list that contains it. The idea of retrieval-augmented generation comes from https://arxiv.org/abs/2005.11401 and the ranking idea behind authority scores is described at https://en.wikipedia.org/wiki/PageRank.

## Why corrective RAG

A plain RAG system answers from whatever it retrieves, even when the passages are irrelevant. Corrective RAG grades each passage first. Genesis keeps only the passages graded correct. When nothing is correct, Genesis refuses to guess and says it could not find reliable information, instead of inventing an answer.

## Sharding

Genesis stores vectors in 16 ChromaDB shards. The shard of a document is the MD5 hash of its document id modulo 16. A query without a document filter fans out to all shards in parallel and merges the results with RRF. A query with a document filter goes to the single shard that owns the document.

See also https://arxiv.org/abs/2005.11401 for the original retrieval-augmented generation paper.
