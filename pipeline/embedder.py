import asyncio
import os
from typing import List

import numpy as np

MODEL_NAME = "all-MiniLM-L6-v2"


class Embedder:
    """Text embeddings (all-MiniLM-L6-v2, 384 dimensions). The model loads on first use.

    Uses fastembed (ONNX runtime, ~150 MB of RAM) when it is installed, and falls back
    to sentence-transformers (PyTorch, ~1 GB). Both produce the same vectors, so an
    index built with one can be queried with the other.
    """

    def __init__(self, model_name: str = MODEL_NAME):
        self.model_name = model_name
        self._model = None
        self._backend = None
        self.batch_size = 4  # small batches keep the ONNX runtime's peak memory low

    def _load(self):
        if self._model is not None:
            return
        try:
            from fastembed import TextEmbedding
            self._model = TextEmbedding(f"sentence-transformers/{self.model_name}")
            self._backend = "fastembed"
        except ImportError:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self.model_name)
            self._backend = "sentence-transformers"

    def encode(self, texts: List[str]) -> np.ndarray:
        """Return an (n, 384) array of L2-normalised embeddings."""
        self._load()
        if self._backend == "fastembed":
            vectors = np.array(list(self._model.embed(texts, batch_size=self.batch_size)), dtype=np.float32)
        else:
            vectors = np.asarray(
                self._model.encode(texts, batch_size=self.batch_size, show_progress_bar=False), dtype=np.float32
            )
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        return vectors / np.clip(norms, 1e-12, None)

    async def embed_text(self, text: str) -> List[float]:
        """Embed a single text without blocking the event loop."""
        loop = asyncio.get_running_loop()
        vector = await loop.run_in_executor(None, lambda: self.encode([text])[0])
        return vector.tolist()

    def embed_batches(self, texts: List[str]) -> List[List[float]]:
        return self.encode(texts).tolist()

embedder = Embedder()
