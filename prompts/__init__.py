from .templates import TEMPLATES
from .grading import DOCUMENT_GRADER_PROMPT, HALLUCINATION_GRADER_PROMPT

class PromptRegistry:
    def __init__(self):
        self._prompts = {**TEMPLATES}
        self._prompts["doc_grader"] = DOCUMENT_GRADER_PROMPT
        self._prompts["hallucination_grader"] = HALLUCINATION_GRADER_PROMPT

    def get(self, name: str) -> str:
        return self._prompts.get(name, "")

    def update(self, name: str, template: str):
        """Hot-swap a prompt template at runtime."""
        self._prompts[name] = template

registry = PromptRegistry()
