from typing import List, Tuple, Set
try:
    from presidio_analyzer import AnalyzerEngine
except ImportError:
    AnalyzerEngine = None

class OutputGuard:
    def __init__(self):
        if AnalyzerEngine:
            self.analyzer = AnalyzerEngine()
        else:
            self.analyzer = None
            print("Warning: presidio-analyzer not installed. OutputGuard will use basic regex redaction.")

    def redact(self, text: str) -> Tuple[str, List[str]]:
        if not self.analyzer:
            # Fallback to simple regex for demonstration if presidio is missing
            return self._fallback_redact(text)
            
        results = self.analyzer.analyze(
            text=text,
            entities=["EMAIL_ADDRESS", "PHONE_NUMBER", "US_SSN", "CREDIT_CARD", "IP_ADDRESS"],
            language='en'
        )
        
        redacted_text = text
        entity_types = set()
        
        # Sort results by start index in reverse to avoid offset issues during replacement
        results = sorted(results, key=lambda x: x.start, reverse=True)
        
        for res in results:
            entity_types.add(res.entity_type)
            # Clean up the entity type for the placeholder
            clean_type = res.entity_type.replace('_ADDRESS', '').replace('NUMBER', '').replace('US_', '').strip('_')
            placeholder = f"[REDACTED_{clean_type}]"
            redacted_text = redacted_text[:res.start] + placeholder + redacted_text[res.end:]
            
        return redacted_text, list(entity_types)

    def _fallback_redact(self, text: str) -> Tuple[str, List[str]]:
        import re
        patterns = {
            "EMAIL": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
            "PHONE": r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b",
            "IP": r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b"
        }
        
        redacted_text = text
        found_types = []
        for name, pattern in patterns.items():
            if re.search(pattern, redacted_text):
                found_types.append(name)
                redacted_text = re.sub(pattern, f"[REDACTED_{name}]", redacted_text)
        
        return redacted_text, found_types

output_guard = OutputGuard()
