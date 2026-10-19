import re
import time
import unicodedata
from dataclasses import dataclass
from typing import Optional

MAX_QUERY_CHARS = 4000


@dataclass
class GuardResult:
    safe: bool
    reason: Optional[str] = None
    latency_ms: float = 0.0


# These are a cheap first filter, not a complete defence. They target phrases that
# are almost only used to attack the assistant, so normal questions about prompts,
# SQL or files are not blocked.
INJECTION_PATTERNS = re.compile(
    r"(ignore|disregard|forget)\s+(all\s+|any\s+|the\s+)?(previous|prior|above|earlier)\s+(instructions?|prompts?|rules?)"
    r"|\bjailbreak\b|\bdan\s+mode\b|developer\s+mode\s+enabled"
    r"|(reveal|print|show|repeat)\s+(me\s+)?(your|the)\s+(hidden\s+|secret\s+)?(system\s+prompt|instructions)"
    r"|you\s+are\s+now\s+(an?\s+)?(unrestricted|uncensored|jailbroken)",
    re.IGNORECASE,
)

SQL_PATTERNS = re.compile(
    r"\bunion\s+(all\s+)?select\b"
    r"|;\s*(drop|truncate|delete|insert|update)\s+\w+"
    r"|'\s*(or|and)\s+'?\d+'?\s*=\s*'?\d+"
    r"|\bxp_cmdshell\b",
    re.IGNORECASE,
)

PATH_TRAVERSAL_PATTERNS = re.compile(
    r"(\.\./|\.\.\\|/etc/passwd|/etc/shadow|[\\/]windows[\\/]win\.ini)",
    re.IGNORECASE,
)


def _normalize(text: str) -> str:
    """Fold unicode tricks and repeated whitespace so simple obfuscation still matches."""
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r"[​-‏⁠﻿]", "", text)
    return re.sub(r"\s+", " ", text)


class InputGuard:
    async def inspect(self, query: str) -> GuardResult:
        start = time.perf_counter()

        def result(safe: bool, reason: Optional[str] = None) -> GuardResult:
            return GuardResult(safe=safe, reason=reason, latency_ms=(time.perf_counter() - start) * 1000)

        if len(query) > MAX_QUERY_CHARS:
            return result(False, f"Query too long (max {MAX_QUERY_CHARS} characters)")

        text = _normalize(query)
        if INJECTION_PATTERNS.search(text):
            return result(False, "Prompt injection detected")
        if SQL_PATTERNS.search(text):
            return result(False, "SQL injection detected")
        if PATH_TRAVERSAL_PATTERNS.search(text):
            return result(False, "Path traversal detected")
        return result(True)

input_guard = InputGuard()
