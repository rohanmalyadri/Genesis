import hashlib
import zlib
from typing import Dict

import numpy as np
import redis

from app.config import settings

_PRIME = (1 << 31) - 1  # Mersenne prime; keeps a*hash inside uint64


class Deduplicator:
    """Exact (SHA-256, stored in Redis) and near (MinHash) duplicate detection.

    Detection is scoped (e.g. "sharded" / "enterprise") so the same file can be
    indexed into both systems. Near-duplicate signatures live in memory; the exact
    hashes persist in Redis.
    """

    def __init__(self, threshold: float = 0.85, num_perm: int = 128):
        self.redis = redis.from_url(settings.REDIS_URL)
        self.threshold = threshold
        self.num_perm = num_perm
        rng = np.random.default_rng(1)
        self._a = rng.integers(1, _PRIME, size=num_perm, dtype=np.uint64)
        self._b = rng.integers(0, _PRIME, size=num_perm, dtype=np.uint64)
        self.signatures: Dict[str, Dict[str, np.ndarray]] = {}

    def _signature(self, text: str) -> np.ndarray:
        text = text[:200_000]
        shingles = {text[i:i + 3] for i in range(max(len(text) - 2, 1))}
        hashes = np.fromiter((zlib.crc32(s.encode()) for s in shingles), dtype=np.uint64, count=len(shingles)) % _PRIME
        # one universal hash (a*x+b mod p) per row; the minimum over all shingles is the MinHash
        return np.array([((a * hashes + b) % _PRIME).min() for a, b in zip(self._a, self._b)], dtype=np.uint64)

    def is_duplicate(self, text: str, doc_id: str = "new", scope: str = "default") -> bool:
        exact_key = f"dedup:hashes:{scope}"
        content_hash = hashlib.sha256(text.encode()).hexdigest()
        existing = self.redis.hget(exact_key, content_hash)
        if existing is not None:
            if existing.decode() == doc_id:
                return False  # same document re-uploaded: allow re-index (upsert)
            print(f"Deduplicator: exact duplicate of {existing.decode()} for {doc_id}")
            return True

        signature = self._signature(text)
        known = self.signatures.setdefault(scope, {})
        for other_id, other in known.items():
            if other_id != doc_id and float(np.mean(signature == other)) >= self.threshold:
                print(f"Deduplicator: near-duplicate of {other_id} for {doc_id}")
                return True

        self.redis.hset(exact_key, content_hash, doc_id)
        known[doc_id] = signature
        return False

deduplicator = Deduplicator()
