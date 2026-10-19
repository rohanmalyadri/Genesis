import re
from typing import List, Tuple

ENTITIES = ["EMAIL_ADDRESS", "PHONE_NUMBER", "US_SSN", "CREDIT_CARD", "IP_ADDRESS"]

_FALLBACK_PATTERNS = {
    "EMAIL": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
    "SSN": r"\b\d{3}-\d{2}-\d{4}\b",
    "CREDIT_CARD": r"\b(?:\d[ -]?){13,16}\b",
    "PHONE": r"(?<!\d)(?:\+?\d{1,2}[ .-]?)?\(?\d{3}\)?[ .-]?\d{3}[ .-]?\d{4}(?!\d)",
    "IP": r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b",
}


class OutputGuard:
    """Redacts PII with Presidio, falling back to regexes if Presidio is unavailable."""

    def __init__(self):
        self._analyzer = None
        self._loaded = False

    @property
    def analyzer(self):
        if not self._loaded:
            self._loaded = True
            try:
                from presidio_analyzer import AnalyzerEngine
                from presidio_analyzer.nlp_engine import NlpEngineProvider
                # use the small spaCy model so Presidio does not download a 400 MB one
                nlp_engine = NlpEngineProvider(nlp_configuration={
                    "nlp_engine_name": "spacy",
                    "models": [{"lang_code": "en", "model_name": "en_core_web_sm"}],
                }).create_engine()
                self._analyzer = AnalyzerEngine(nlp_engine=nlp_engine, supported_languages=["en"])
            except Exception as e:
                print(f"OutputGuard: Presidio unavailable ({e}); using regex redaction.")
        return self._analyzer

    def redact(self, text: str) -> Tuple[str, List[str]]:
        if not text:
            return text, []
        analyzer = self.analyzer
        if not analyzer:
            return self._fallback_redact(text)

        results = analyzer.analyze(text=text, entities=ENTITIES, language="en")
        redacted, found = text, set()
        for res in sorted(results, key=lambda x: x.start, reverse=True):
            found.add(res.entity_type)
            label = res.entity_type.replace("_ADDRESS", "").replace("NUMBER", "").replace("US_", "").strip("_")
            redacted = redacted[:res.start] + f"[REDACTED_{label}]" + redacted[res.end:]
        return redacted, sorted(found)

    def _fallback_redact(self, text: str) -> Tuple[str, List[str]]:
        found = []
        for name, pattern in _FALLBACK_PATTERNS.items():
            if re.search(pattern, text):
                found.append(name)
                text = re.sub(pattern, f"[REDACTED_{name}]", text)
        return text, found


class StreamRedactor:
    """Redacts a token stream before anything reaches the client.

    Text is held back until a sentence/line boundary so PII is never split across
    emitted pieces, then each completed piece is redacted and released.
    """
    BOUNDARY = re.compile(r"(?<=[.!?])\s|\n")
    MAX_HOLD = 400

    def __init__(self, guard: "OutputGuard", enabled: bool = True):
        self.guard = guard
        self.enabled = enabled
        self.buffer = ""

    def feed(self, token: str) -> str:
        if not self.enabled:
            return token
        self.buffer += token
        cut = 0
        for m in self.BOUNDARY.finditer(self.buffer):
            cut = m.end()
        if not cut and len(self.buffer) > self.MAX_HOLD:
            cut = self.buffer.rfind(" ") + 1
        if not cut:
            return ""
        ready, self.buffer = self.buffer[:cut], self.buffer[cut:]
        return self.guard.redact(ready)[0]

    def flush(self) -> str:
        if not self.enabled or not self.buffer:
            return ""
        ready, self.buffer = self.buffer, ""
        return self.guard.redact(ready)[0]

output_guard = OutputGuard()
