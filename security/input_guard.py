import re
import time
import asyncio
from dataclasses import dataclass
from typing import Optional

@dataclass
class GuardResult:
    safe: bool
    reason: Optional[str] = None
    latency_ms: float = 0.0

# Compiled regex patterns cached at module load
INJECTION_PATTERNS = re.compile(
    r"(ignore\s+previous|jailbreak|dan\s+mode|system\s+prompt|reveal\s+your|you\s+are\s+now\s+a)",
    re.IGNORECASE
)

SQL_PATTERNS = re.compile(
    r"(union\s+select|drop\s+table|insert\s+into|delete\s+from|select\s+.*\s+from|xp_cmdshell)",
    re.IGNORECASE
)

PATH_TRAVERSAL_PATTERNS = re.compile(
    r"(\.\./|\.\.\\|/etc/passwd|/windows/win\.ini|/var/log/)",
    re.IGNORECASE
)

class InputGuard:
    async def inspect(self, query: str) -> GuardResult:
        start_time = time.perf_counter()
        
        # All checks are non-blocking regex matches
        if INJECTION_PATTERNS.search(query):
            latency = (time.perf_counter() - start_time) * 1000
            return GuardResult(safe=False, reason="Prompt injection detected", latency_ms=latency)
            
        if SQL_PATTERNS.search(query):
            latency = (time.perf_counter() - start_time) * 1000
            return GuardResult(safe=False, reason="SQL injection detected", latency_ms=latency)
            
        if PATH_TRAVERSAL_PATTERNS.search(query):
            latency = (time.perf_counter() - start_time) * 1000
            return GuardResult(safe=False, reason="Path traversal detected", latency_ms=latency)
            
        latency = (time.perf_counter() - start_time) * 1000
        return GuardResult(safe=True, latency_ms=latency)

input_guard = InputGuard()
