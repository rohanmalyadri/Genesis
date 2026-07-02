import hashlib
import redis
from datasketch import MinHash, MinHashLSH
from app.config import settings

class Deduplicator:
    def __init__(self, threshold: float = 0.85, num_perm: int = 128):
        self.redis = redis.from_url(settings.REDIS_URL)
        self.lsh = MinHashLSH(threshold=threshold, num_perm=num_perm)
        self.num_perm = num_perm
        self.exact_key = "dedup:hashes"

    def is_duplicate(self, text: str, doc_id: str = "new") -> bool:
        # 1. Exact Deduplication (SHA-256)
        content_hash = hashlib.sha256(text.encode()).hexdigest()
        if self.redis.sismember(self.exact_key, content_hash):
            print(f"Deduplicator: Exact duplicate found for {doc_id}")
            return True
            
        # 2. Near-Deduplication (MinHash LSH)
        m = MinHash(num_perm=self.num_perm)
        # Shingle the text (3-grams)
        shingles = set(text[i:i+3] for i in range(len(text)-2))
        for s in shingles:
            m.update(s.encode('utf8'))
            
        # Check LSH
        results = self.lsh.query(m)
        if results:
            print(f"Deduplicator: Near-duplicate found for {doc_id} (matches: {results})")
            return True
            
        # If not duplicate, record it
        self.redis.sadd(self.exact_key, content_hash)
        self.lsh.insert(doc_id, m)
        return False

deduplicator = Deduplicator()
