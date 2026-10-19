import asyncio
from typing import List
from sentence_transformers import SentenceTransformer

class Embedder:
    """Sentence-transformer wrapper. The model loads on first use, not at import."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model_name = model_name
        self._model = None
        self.batch_size = 64

    @property
    def model(self) -> SentenceTransformer:
        if self._model is None:
            self._model = SentenceTransformer(self.model_name)
        return self._model

    async def embed_text(self, text: str) -> List[float]:
        """Embed a single text without blocking the event loop."""
        loop = asyncio.get_running_loop()
        embedding = await loop.run_in_executor(
            None, lambda: self.model.encode(text, normalize_embeddings=True)
        )
        return embedding.tolist()

    def embed_batches(self, texts: List[str]) -> List[List[float]]:
        embeddings = self.model.encode(
            texts,
            batch_size=self.batch_size,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return embeddings.tolist()

embedder = Embedder()
