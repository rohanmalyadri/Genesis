import hashlib
from typing import Dict

import redis
from datasketch import MinHash, MinHashLSH

from app.config import settings


class Deduplicator:
    """Exact (SHA-256, stored in Redis) and near (MinHash LSH) duplicate detection.

    Detection is scoped (e.g. "sharded" / "enterprise") so the same file can be
    indexed into both systems.
    """

    def __init__(self, threshold: float = 0.85, num_perm: int = 128):
        self.redis = redis.from_url(settings.REDIS_URL)
        self.threshold = threshold
        self.num_perm = num_perm
        self.lsh: Dict[str, MinHashLSH] = {}

    def is_duplicate(self, text: str, doc_id: str = "new", scope: str = "default") -> bool:
        exact_key = f"dedup:hashes:{scope}"
        content_hash = hashlib.sha256(text.encode()).hexdigest()
        existing = self.redis.hget(exact_key, content_hash)
        if existing is not None:
            if existing.decode() == doc_id:
                return False  # same document re-uploaded: allow re-index (upsert)
            print(f"Deduplicator: exact duplicate of {existing.decode()} for {doc_id}")
            return True

        m = MinHash(num_perm=self.num_perm)
        for s in {text[i:i + 3] for i in range(len(text) - 2)}:
            m.update(s.encode("utf8"))

        lsh = self.lsh.setdefault(scope, MinHashLSH(threshold=self.threshold, num_perm=self.num_perm))
        matches = [k for k in lsh.query(m) if k != doc_id]
        if matches:
            print(f"Deduplicator: near-duplicate of {matches} for {doc_id}")
            return True

        self.redis.hset(exact_key, content_hash, doc_id)
        if doc_id not in lsh.keys:
            lsh.insert(doc_id, m)
        return False

deduplicator = Deduplicator()
